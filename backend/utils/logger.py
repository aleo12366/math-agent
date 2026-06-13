"""Module 9: Structured logging to JSON format."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class StructuredLogger:
    """Structured JSON logger for the math agent pipeline.

    Writes structured log entries to both console and file,
    capturing pipeline events, agent actions, and errors.
    """

    def __init__(self, name: str = "math_agent", log_file: Optional[str] = None, level: str = "INFO"):
        """Initialize the structured logger.

        Args:
            name: Logger name.
            log_file: Path to log file. If None, uses default.
            level: Logging level string.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        # Console handler with readable format
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                datefmt="%H:%M:%S",
            )
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)

        # File handler with JSON format
        self.log_file = log_file
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                Path(log_dir).mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(file_handler)

    def _write_entry(self, level: str, event: str, **kwargs):
        """Write a structured log entry.

        Args:
            level: Log level string.
            event: Event name/type.
            **kwargs: Additional fields to include in the log entry.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "event": event,
            **kwargs,
        }

        msg = json.dumps(entry, ensure_ascii=False, default=str)

        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(msg)

        # Also write to file if configured
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            except Exception:
                pass

    def pipeline_start(self, problem: str, mode: str, **kwargs):
        """Log pipeline start event."""
        self._write_entry("INFO", "pipeline_start", problem=problem[:200], mode=mode, **kwargs)

    def pipeline_complete(self, problem_id: str, duration_ms: int, **kwargs):
        """Log pipeline completion event."""
        self._write_entry("INFO", "pipeline_complete", problem_id=problem_id, duration_ms=duration_ms, **kwargs)

    def pipeline_error(self, problem_id: str, error: str, **kwargs):
        """Log pipeline error event."""
        self._write_entry("ERROR", "pipeline_error", problem_id=problem_id, error=error, **kwargs)

    def agent_start(self, agent_name: str, **kwargs):
        """Log agent start event."""
        self._write_entry("DEBUG", "agent_start", agent=agent_name, **kwargs)

    def agent_complete(self, agent_name: str, duration_ms: int, **kwargs):
        """Log agent completion event."""
        self._write_entry("DEBUG", "agent_complete", agent=agent_name, duration_ms=duration_ms, **kwargs)

    def agent_error(self, agent_name: str, error: str, **kwargs):
        """Log agent error event."""
        self._write_entry("WARNING", "agent_error", agent=agent_name, error=error, **kwargs)

    def llm_call(self, agent_name: str, messages_count: int, **kwargs):
        """Log LLM API call event."""
        self._write_entry("DEBUG", "llm_call", agent=agent_name, messages=messages_count, **kwargs)

    def llm_response(self, agent_name: str, response_length: int, **kwargs):
        """Log LLM response event."""
        self._write_entry("DEBUG", "llm_response", agent=agent_name, length=response_length, **kwargs)

    def tool_call(self, tool_name: str, params: dict, **kwargs):
        """Log tool execution event."""
        self._write_entry("DEBUG", "tool_call", tool=tool_name, params=str(params)[:200], **kwargs)

    def tool_result(self, tool_name: str, result: str, **kwargs):
        """Log tool result event."""
        self._write_entry("DEBUG", "tool_result", tool=tool_name, result=str(result)[:200], **kwargs)

    def verification(self, verified: bool, confidence: float, score: float, **kwargs):
        """Log verification result event."""
        self._write_entry("INFO", "verification", verified=verified, confidence=confidence, score=score, **kwargs)

    def retry(self, attempt: int, max_attempts: int, reason: str, **kwargs):
        """Log retry event."""
        self._write_entry("WARNING", "retry", attempt=attempt, max=max(max_attempts, 1), reason=reason, **kwargs)

    def info(self, message: str, **kwargs):
        """Log a general info message."""
        self._write_entry("INFO", "info", message=message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log an error message."""
        self._write_entry("ERROR", "error", message=message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log a debug message."""
        self._write_entry("DEBUG", "debug", message=message, **kwargs)


# Global logger instance
logger = StructuredLogger()