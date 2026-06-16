"""API routes for the math agent system — adaptive pipeline only."""

import logging
import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.event_bus import EventBus
from config.settings import settings
from config.schemas import (
    SolveRequest,
    BatchSolveRequest,
    HealthResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    MathAgentOutput,
)
from pipeline.adaptive import AdaptivePipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_server_start_time = time.time()


@router.post("/solve", response_model=MathAgentOutput)
async def solve_problem(request: SolveRequest):
    """Solve a single math problem using the adaptive pipeline.

    Guard Layer (<100ms) selects the optimal route automatically:
    - simple: 1 LLM call (~15-30s)
    - standard: 3 LLM calls (~45-90s)
    - complex: 6 LLM calls (~2-3min, parallel solvers + consensus)
    - safe_fallback: high-verification multi-path

    If stream=True, returns SSE events during processing.
    If stream=False, returns the final JSON result.
    """
    if request.stream:
        event_bus = EventBus()
        pipeline = AdaptivePipeline(config=settings, event_bus=event_bus)

        async def event_generator():
            import asyncio
            import json

            result_container = {"result": None, "error": None}

            async def run_pipeline():
                try:
                    result = await pipeline.solve(request.problem)
                    result_container["result"] = result
                except asyncio.CancelledError:
                    result_container["error"] = "cancelled"
                except Exception as e:
                    result_container["error"] = str(e)

            task = asyncio.create_task(run_pipeline())
            queue = await event_bus.create_queue()

            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1)
                        yield event
                    except asyncio.TimeoutError:
                        if task.done():
                            break
                        continue
                    if task.done():
                        break

                # Drain remaining events
                while not queue.empty():
                    try:
                        yield queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                # Send terminal event
                if result_container["result"] is not None:
                    result_data = result_container["result"].model_dump(mode="json")
                    yield f"event: result\ndata: {json.dumps(result_data, ensure_ascii=False)}\n\n"
                elif result_container["error"]:
                    yield f"event: error\ndata: {json.dumps({'error': result_container['error']})}\n\n"
                else:
                    yield f'event: error\ndata: {json.dumps({"error": "Pipeline returned no result"})}\n\n'

            except asyncio.CancelledError:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                raise
            finally:
                async with event_bus._lock:
                    if queue in event_bus._subscribers:
                        event_bus._subscribers.remove(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming: return final result
        pipeline = AdaptivePipeline(config=settings)
        try:
            result = await pipeline.solve(request.problem)
            return result
        except Exception as e:
            logger.error("Solve error: %s", e)
            raise HTTPException(status_code=500, detail="Solve failed. Check server logs.")


@router.post("/batch")
async def solve_batch(request: BatchSolveRequest):
    """Solve a batch of math problems using the adaptive pipeline."""
    import asyncio

    async def solve_one(problem: str):
        try:
            p = AdaptivePipeline(config=settings)
            return await p.solve(problem)
        except Exception as e:
            return {"error": str(e), "problem": problem}

    tasks = [solve_one(p) for p in request.problems]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for r in results:
        if isinstance(r, MathAgentOutput):
            output.append(r.model_dump(mode="json"))
        elif isinstance(r, dict):
            output.append(r)
        else:
            output.append({"error": str(r)})

    return {"results": output, "count": len(output)}


def _mask_api_key(key: str) -> str:
    """Mask API key for safe display."""
    if not key or len(key) < 12:
        return "****" if key else ""
    return key[:6] + "****" + key[-4:]


def _save_env_file(updates: dict):
    """Persist configuration changes to the .env file."""
    env_path = Path(__file__).parent.parent / ".env"

    env_keys = {
        "api_url": "MATH_AGENT_API_URL",
        "api_key": "MATH_AGENT_API_KEY",
        "model_name": "MATH_AGENT_MODEL_NAME",
        "temperature": "MATH_AGENT_TEMPERATURE",
        "max_tokens": "MATH_AGENT_MAX_TOKENS",
        "debate_agents": "MATH_AGENT_DEBATE_AGENTS",
        "max_retries": "MATH_AGENT_MAX_RETRIES",
        "verification_threshold": "MATH_AGENT_VERIFICATION_THRESHOLD",
        "confidence_threshold": "MATH_AGENT_CONFIDENCE_THRESHOLD",
    }

    existing_lines: list[str] = []
    existing_keys: set[str] = set()
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                existing_keys.add(stripped.split("=", 1)[0].strip())

    env_updates: dict[str, str] = {}
    for field_name, env_key in env_keys.items():
        if field_name in updates:
            env_updates[env_key] = str(updates[field_name].value if isinstance(updates[field_name], Enum) else updates[field_name])

    if not env_updates:
        return

    new_lines: list[str] = []
    updated_keys: set[str] = set()

    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in env_updates:
                new_lines.append(f"{key}={env_updates[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for key, value in env_updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    logger.info("Saved config to %s", env_path)


def _build_config_response() -> ConfigResponse:
    """Build a ConfigResponse with masked API key."""
    has_key = bool(settings.api_key)
    return ConfigResponse(
        api_url=settings.api_url,
        api_key_masked=_mask_api_key(settings.api_key) if has_key else "",
        model_name=settings.model_name,
        has_api_key=has_key,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        debate_agents=settings.debate_agents,
        max_retries=settings.max_retries,
        verification_threshold=settings.verification_threshold,
        confidence_threshold=settings.confidence_threshold,
    )


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get current configuration."""
    return _build_config_response()


@router.put("/config", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest):
    """Update configuration and persist to .env file."""
    update_data = request.model_dump(exclude_none=True, mode="json")

    new_api_key = update_data.pop("api_key", None)

    for key, value in update_data.items():
        if hasattr(settings, key):
            field = settings.model_fields.get(key)
            if field and hasattr(field, 'annotation'):
                try:
                    value = field.annotation(value)
                except (ValueError, TypeError):
                    logger.warning("Invalid value for %s: %s, skipping", key, value)
                    continue
            setattr(settings, key, value)

    if new_api_key is not None:
        settings.api_key = new_api_key

    from utils.llm_client import llm_client
    llm_client.api_url = settings.api_url
    llm_client.api_key = settings.api_key
    llm_client.model_name = settings.model_name
    await llm_client.reset_session()

    logger.info(
        "Config updated — URL: %s | Model: %s | Key set: %s",
        settings.api_url, settings.model_name, bool(settings.api_key),
    )

    persist_data = {**update_data}
    if new_api_key is not None:
        persist_data["api_key"] = new_api_key
    _save_env_file(persist_data)

    return _build_config_response()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = time.time() - _server_start_time
    return HealthResponse(
        status="ok",
        version="3.0.0",
        model=settings.model_name,
        uptime_seconds=uptime,
    )


@router.post("/config/test")
async def test_api_connection():
    """Test the current LLM API connection."""
    from utils.llm_client import llm_client

    result = {
        "api_url": settings.api_url,
        "model_name": settings.model_name,
        "has_api_key": bool(settings.api_key),
    }

    try:
        test_messages = [
            {"role": "user", "content": "Reply with exactly: OK"},
        ]
        response = await llm_client.chat(test_messages, max_tokens=10, retries=1)
        result["status"] = "success"
        result["response_preview"] = response[:100]
    except Exception as e:
        result["status"] = "error"
        result["error"] = "Connection failed. Check URL, key, and server logs."
        logger.error("API test failed: %s", e)

    return result
