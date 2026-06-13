"""Async Intern-S1 API client with retry logic."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

import aiohttp

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Async HTTP client for the Intern-S1 LLM API."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_url = api_url
        self._api_key = api_key
        self._model_name = model_name
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def api_url(self) -> str:
        return self._api_url or settings.api_url

    @api_url.setter
    def api_url(self, value: str):
        self._api_url = value

    @property
    def api_key(self) -> str:
        return self._api_key or settings.api_key

    @api_key.setter
    def api_key(self, value: str):
        self._api_key = value

    @property
    def model_name(self) -> str:
        return self._model_name or settings.model_name

    @model_name.setter
    def model_name(self, value: str):
        self._model_name = value

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=settings.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def reset_session(self):
        """Close current session so a new one is created on next call."""
        await self.close()

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> dict:
        return {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": settings.top_p,
            "stream": stream,
        }

    def _log_request(self):
        """Log current API configuration for debugging."""
        url = self.api_url
        key = self.api_key
        model = self.model_name
        key_display = f"{key[:8]}...{key[-4:]}" if key and len(key) > 12 else ("****" if key else "(empty)")
        logger.info("LLM API → URL: %s | Model: %s | Key: %s", url, model, key_display)

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        retries: int = 3,
    ) -> str:
        """Send a chat completion request and return the response text.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            retries: Number of retry attempts on failure.

        Returns:
            The assistant's response text.

        Raises:
            Exception: After all retries exhausted.
        """
        session = await self._get_session()
        payload = self._build_payload(messages, temperature, max_tokens, stream=False)
        headers = self._build_headers()
        url = self.api_url

        self._log_request()

        last_error = None
        for attempt in range(retries):
            try:
                async with session.post(
                    url, json=payload, headers=headers
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise Exception(
                            f"LLM API error {resp.status}: {body} | URL: {url}"
                        )

                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.debug("LLM response received (%d chars)", len(content))
                    return content

            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM call attempt %d/%d failed: %s",
                    attempt + 1,
                    retries,
                    str(e),
                )
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # exponential backoff

        raise Exception(f"LLM API failed after {retries} retries: {last_error}")

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        retries: int = 3,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion response tokens.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            retries: Number of retry attempts on failure.

        Yields:
            Response text chunks as they arrive.
        """
        session = await self._get_session()
        payload = self._build_payload(messages, temperature, max_tokens, stream=True)
        headers = self._build_headers()
        url = self.api_url

        self._log_request()

        last_error = None
        for attempt in range(retries):
            try:
                async with session.post(
                    url, json=payload, headers=headers
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise Exception(
                            f"LLM API stream error {resp.status}: {body} | URL: {url}"
                        )

                    async for line in resp.content:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue
                        if line_str.startswith("data: "):
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
                    return

            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM stream attempt %d/%d failed: %s",
                    attempt + 1,
                    retries,
                    str(e),
                )
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise Exception(
            f"LLM API streaming failed after {retries} retries: {last_error}"
        )


# Global singleton
llm_client = LLMClient()