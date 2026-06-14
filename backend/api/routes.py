"""API routes for the math agent system."""

import logging
import os
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
    PipelineMode,
)
from pipeline.single import SinglePipeline
from pipeline.multi import MultiPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Track server start time
_server_start_time = time.time()


def _create_pipeline(mode: str = "single", debate_agents: int = 1, event_bus: EventBus = None):
    """Create a pipeline instance based on mode."""
    if mode == "multi_debate":
        config = settings.model_copy(update={"debate_agents": debate_agents})
        return MultiPipeline(config=config, event_bus=event_bus)
    else:
        return SinglePipeline(config=settings, event_bus=event_bus)


@router.post("/solve", response_model=MathAgentOutput)
async def solve_problem(request: SolveRequest):
    """Solve a single math problem.

    If stream=True, returns SSE events during processing.
    If stream=False, returns the final JSON result.
    """
    if request.stream:
        event_bus = EventBus()
        pipeline = _create_pipeline(request.mode, request.debate_agents, event_bus)

        async def event_generator():
            # Run pipeline in background
            import asyncio
            import json

            result_container = {"result": None, "error": None}

            async def run_pipeline():
                try:
                    result = await pipeline.solve(request.problem)
                    result_container["result"] = result
                except Exception as e:
                    result_container["error"] = str(e)

            # Start pipeline task
            task = asyncio.create_task(run_pipeline())

            # Stream events — race pipeline task against event queue
            queue = await event_bus.create_queue()
            try:
                while True:
                    # Get next event with timeout
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=5)
                        yield event
                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield ": keepalive\n\n"

                    # Check if pipeline is done and queue is drained
                    if task.done():
                        # Drain remaining events
                        while not queue.empty():
                            try:
                                yield queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        break
            except Exception:
                pass
            finally:
                if not task.done():
                    await task

            # Send final result as a 'result' event
            if result_container["result"]:
                result_data = result_container["result"].model_dump(mode="json")
                yield f"event: result\ndata: {json.dumps(result_data, ensure_ascii=False)}\n\n"
            elif result_container["error"]:
                yield f"event: error\ndata: {json.dumps({'error': result_container['error']})}\n\n"

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
        pipeline = _create_pipeline(request.mode, request.debate_agents)
        try:
            result = await pipeline.solve(request.problem)
            return result
        except Exception as e:
            logger.error("Solve error: %s", e)
            raise HTTPException(status_code=500, detail="Solve failed. Check server logs.")


@router.post("/batch")
async def solve_batch(request: BatchSolveRequest):
    """Solve a batch of math problems."""
    import asyncio

    async def solve_one(problem: str):
        try:
            p = _create_pipeline(request.mode, request.debate_agents)
            return await p.solve(problem)
        except Exception as e:
            return {"error": str(e), "problem": problem}

    tasks = [solve_one(p) for p in request.problems]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Serialize results
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
    """Mask API key for safe display (show first 6 and last 4 chars)."""
    if not key or len(key) < 12:
        return "****" if key else ""
    return key[:6] + "****" + key[-4:]


def _save_env_file(updates: dict):
    """Persist configuration changes to the .env file.

    Reads existing .env, updates changed values, writes back.
    Only saves fields that are relevant to the .env file.
    """
    env_path = Path(__file__).parent.parent / ".env"

    # Keys we persist to .env
    env_keys = {
        "api_url": "MATH_AGENT_API_URL",
        "api_key": "MATH_AGENT_API_KEY",
        "model_name": "MATH_AGENT_MODEL_NAME",
        "temperature": "MATH_AGENT_TEMPERATURE",
        "max_tokens": "MATH_AGENT_MAX_TOKENS",
        "pipeline_mode": "MATH_AGENT_PIPELINE_MODE",
        "debate_agents": "MATH_AGENT_DEBATE_AGENTS",
        "max_retries": "MATH_AGENT_MAX_RETRIES",
        "verification_threshold": "MATH_AGENT_VERIFICATION_THRESHOLD",
        "confidence_threshold": "MATH_AGENT_CONFIDENCE_THRESHOLD",
    }

    # Read existing .env lines
    existing_lines: list[str] = []
    existing_keys: set[str] = set()
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                existing_keys.add(stripped.split("=", 1)[0].strip())

    # Build update lines
    env_updates: dict[str, str] = {}
    for field_name, env_key in env_keys.items():
        if field_name in updates:
            env_updates[env_key] = str(updates[field_name].value if isinstance(updates[field_name], Enum) else updates[field_name])

    if not env_updates:
        return

    # Merge: update existing lines or append new ones
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

    # Append any new keys not already in file
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
        pipeline_mode=settings.pipeline_mode,
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

    # Separate API key from other fields (need special handling)
    new_api_key = update_data.pop("api_key", None)

    # Update in-memory settings
    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    # Update API key if provided
    if new_api_key is not None:
        settings.api_key = new_api_key

    # Also reload LLM client to pick up new API config
    from utils.llm_client import llm_client
    llm_client.api_url = settings.api_url
    llm_client.api_key = settings.api_key
    llm_client.model_name = settings.model_name

    # Reset session to avoid stale connections to old URL
    await llm_client.reset_session()

    logger.info(
        "Config updated — URL: %s | Model: %s | Key set: %s",
        settings.api_url, settings.model_name, bool(settings.api_key),
    )

    # Persist all changes to .env file
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
        version="2.0.0",
        model=settings.model_name,
        uptime_seconds=uptime,
    )


@router.post("/config/test")
async def test_api_connection():
    """Test the current LLM API connection by sending a simple request."""
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
