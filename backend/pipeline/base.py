"""BasePipeline abstract class with event hooks."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from api.event_bus import EventBus
from config.settings import Settings, settings
from config.schemas import MathAgentOutput, PipelineMode
from agents.formatter import Formatter
from utils.logger import logger as structured_logger

logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """Abstract base class for math agent pipelines.

    Provides common infrastructure for event emission, error handling,
    and result formatting. Subclasses implement the specific pipeline flow.
    """

    def __init__(self, config: Optional[Settings] = None, event_bus: Optional[EventBus] = None):
        """Initialize the pipeline.

        Args:
            config: Application settings.
            event_bus: SSE event bus for streaming progress.
        """
        self.config = config or settings
        self.event_bus = event_bus
        self.formatter = Formatter()
        self.stages_total = 9  # Total pipeline stages for progress calculation

    async def _emit_stage(self, stage: str, status: str, progress: int, message: str = ""):
        """Emit a stage event if event bus is available."""
        if self.event_bus:
            await self.event_bus.emit_stage(stage, status, progress, message)

    async def _emit_step(self, step: int, total: int, description: str, expression: str = "", progress: int = 0):
        """Emit a step event if event bus is available."""
        if self.event_bus:
            await self.event_bus.emit_step(step, total, description, expression, progress)

    async def _emit_complete(self, status: str, total_tokens: int = 0, duration_ms: int = 0):
        """Emit a completion event if event bus is available."""
        if self.event_bus:
            await self.event_bus.emit_complete(status, total_tokens, duration_ms)

    async def _emit_error(self, stage: str, error: str):
        """Emit an error event if event bus is available."""
        if self.event_bus:
            await self.event_bus.emit_error(stage, error)

    def _calc_progress(self, current_stage: int) -> int:
        """Calculate progress percentage for a given stage index."""
        stage_progress = {
            1: 10,   # understanding
            2: 20,   # classification
            3: 30,   # knowledge
            4: 40,   # planning
            5: 60,   # solving
            6: 80,   # verification / reflection
            7: 92,   # explanation
            8: 100,  # formatting
            9: 100,  # formatting complete
        }
        return stage_progress.get(current_stage, int((current_stage / self.stages_total) * 100))

    @abstractmethod
    async def solve(self, problem: str) -> MathAgentOutput:
        """Solve a math problem through the pipeline.

        Args:
            problem: The math problem text.

        Returns:
            MathAgentOutput with the complete solution.
        """
        ...