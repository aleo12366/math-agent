"""BaseAgent abstract class with LLM call and JSON extraction."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from config.settings import settings, Settings
from utils.llm_client import llm_client
from utils.json_parser import extract_json_from_text

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents in the math problem-solving pipeline.

    Provides common LLM call infrastructure and JSON extraction.
    Subclasses must implement the `run` method.
    """

    _shared_llm = None  # Set by ReasoningAgent to inject competition client

    def __init__(self, name: str, config: Optional[Settings] = None):
        """Initialize the agent.

        Args:
            name: Human-readable agent name for logging.
            config: Optional settings override.
        """
        self.name = name
        self.config = config or settings
        self.llm = BaseAgent._shared_llm or llm_client
        self.logger = logging.getLogger(f"agent.{name}")

    async def call_llm(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Call the Intern-S1 LLM API with the given messages.

        Args:
            messages: Chat messages in OpenAI format.
            temperature: Sampling temperature (defaults to config).
            max_tokens: Max response tokens (defaults to config).

        Returns:
            The LLM response text.
        """
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        self.logger.debug(
            "Calling LLM: %d messages, temp=%.2f, max_tokens=%d",
            len(messages),
            temp,
            tokens,
        )

        response = await self.llm.chat(
            messages=messages,
            temperature=temp,
            max_tokens=tokens,
        )

        self.logger.debug("LLM response: %d chars", len(response))
        return response

    def extract_json(self, text: str) -> Optional[dict]:
        """Extract a JSON object from LLM output text.

        Args:
            text: Raw LLM output that may contain JSON.

        Returns:
            Parsed JSON dict or None if extraction fails.
        """
        result = extract_json_from_text(text)
        if result is None:
            self.logger.warning("Failed to extract JSON from LLM output")
        return result

    def build_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build a message list for the LLM API.

        Args:
            system_prompt: System message content.
            user_prompt: User message content.
            history: Optional previous messages for context.

        Returns:
            List of message dicts.
        """
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})
        return messages

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """Execute the agent's primary function.

        Args:
            input_data: Dictionary with agent-specific input fields.

        Returns:
            Dictionary with agent-specific output fields.
        """
        ...