"""Application settings using Pydantic Settings for environment-based configuration."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Intern-S1 LLM API
    api_url: str = Field(
        default="https://intern-s1.example.com/v1/chat/completions",
        description="Intern-S1 API endpoint URL",
    )
    api_key: str = Field(
        default="",
        description="API key for Intern-S1 authentication",
    )
    model_name: str = Field(
        default="Intern-S1",
        description="Model name to use in API calls",
    )

    # LLM Parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=32768)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)

    # Pipeline Configuration (adaptive — no mode selector needed)
    max_retries: int = Field(default=3, ge=0, le=10)
    debate_agents: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=10, le=600)

    # Verification Thresholds
    verification_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # Server Configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    # Logging
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/math_agent.log")

    model_config = {
        "env_prefix": "MATH_AGENT_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# Global settings singleton
settings = Settings()
