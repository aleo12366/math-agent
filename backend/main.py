"""FastAPI application entry point for the math agent system."""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from api.routes import router
from utils.llm_client import llm_client
from utils.logger import logger as structured_logger

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Starting Math Agent System v2.0.0")
    logger.info("Model: %s", settings.model_name)
    logger.info("API URL: %s", settings.api_url)
    # Ensure log directory exists
    if settings.log_file:
        log_dir = Path(settings.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    structured_logger.info("Application started", model=settings.model_name)

    yield

    # Shutdown
    logger.info("Shutting down Math Agent System")
    await llm_client.close()
    structured_logger.info("Application stopped")


app = FastAPI(
    title="Math Agent System",
    description="Multi-agent math problem-solving system powered by Intern-S1",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with system info."""
    return {
        "name": "Math Agent System",
        "version": "2.0.0",
        "model": settings.model_name,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )