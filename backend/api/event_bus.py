"""SSE Event Bus for real-time streaming of pipeline progress."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class EventBus:
    """Async event bus for SSE streaming.

    Supports multiple subscribers, each receiving events through
    an async queue. Events are JSON-formatted SSE data.
    """

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to the event stream.

        Yields:
            SSE-formatted event strings.
        """
        queue: asyncio.Queue = asyncio.Queue()

        async with self._lock:
            self._subscribers.append(queue)

        try:
            while True:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=300)
                    yield event_data
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    async def emit(self, event_type: str, data: dict):
        """Emit an SSE event to all subscribers.

        Args:
            event_type: The SSE event type (e.g., 'stage', 'step', 'complete').
            data: Event payload dict.
        """
        event_str = self._format_sse(event_type, data)

        async with self._lock:
            subscribers = list(self._subscribers)

        for queue in subscribers:
            try:
                await queue.put(event_str)
            except Exception as e:
                logger.warning("Failed to emit to subscriber: %s", e)

    async def emit_stage(
        self,
        stage: str,
        status: str,
        progress: int,
        message: str = "",
    ):
        """Emit a pipeline stage event.

        Args:
            stage: Stage name (e.g., 'understanding', 'solving').
            status: Stage status ('started', 'complete', 'error').
            progress: Progress percentage (0-100).
            message: Optional status message.
        """
        data = {
            "stage": stage,
            "status": status,
            "progress": progress,
        }
        if message:
            data["message"] = message
        await self.emit("stage", data)

    async def emit_step(
        self,
        step: int,
        total: int,
        description: str,
        expression: str = "",
        progress: int = 0,
    ):
        """Emit a reasoning step event.

        Args:
            step: Current step number.
            total: Total steps.
            description: Step description.
            expression: Mathematical expression for this step.
            progress: Overall progress percentage.
        """
        await self.emit("step", {
            "step": step,
            "total": total,
            "description": description,
            "expression": expression,
            "progress": progress,
        })

    async def emit_complete(
        self,
        status: str,
        total_tokens: int = 0,
        duration_ms: int = 0,
    ):
        """Emit a pipeline completion event.

        Args:
            status: 'success' or 'error'.
            total_tokens: Total tokens used.
            duration_ms: Total duration in milliseconds.
        """
        await self.emit("complete", {
            "status": status,
            "total_tokens": total_tokens,
            "duration_ms": duration_ms,
            "progress": 100,
        })

    async def emit_error(self, stage: str, error: str):
        """Emit an error event.

        Args:
            stage: Stage where error occurred.
            error: Error message.
        """
        await self.emit("error", {
            "stage": stage,
            "status": "error",
            "error": error,
        })

    @staticmethod
    def _format_sse(event_type: str, data: dict) -> str:
        """Format data as an SSE event string.

        Args:
            event_type: SSE event type.
            data: Event payload.

        Returns:
            Formatted SSE string.
        """
        json_data = json.dumps(data, ensure_ascii=False, default=str)
        return f"event: {event_type}\ndata: {json_data}\n\n"

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)