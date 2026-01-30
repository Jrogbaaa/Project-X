import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.database import init_db
from app.api.routes import search_router, influencers_router, exports_router, health_router, brands_router


def setup_logging():
    """Configure logging to show detailed search progress in terminal."""
    # Create a custom formatter for clean output
    formatter = logging.Formatter(
        fmt="%(message)s",  # Clean output for our formatted logs
        datefmt="%H:%M:%S"
    )
    
    # Console handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Configure the app logger (covers all app.* modules)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.handlers = []  # Clear any existing handlers
    app_logger.addHandler(console_handler)
    app_logger.propagate = False  # Don't propagate to root logger
    
    # Also log uvicorn access at INFO level (optional)
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.setLevel(logging.INFO)


# Initialize logging on module load
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Influencer Discovery Tool",
        description="""
        A streamlined influencer discovery tool for talent agents to find ideal
        influencer matches for brand partnerships.

        ## Features
        - Natural language search powered by GPT-4o
        - Configurable filtering (credibility, engagement, geography)
        - Multi-factor ranking algorithm
        - Export to CSV/Excel
        - Save searches for later reference

        ## Quick Start
        1. POST to `/search` with a natural language query
        2. Review ranked results with detailed metrics
        3. Export results or save the search
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS - allow Vercel domains and configured origins
    # In production on Vercel, requests come from same domain so CORS is less strict
    import os
    is_vercel = os.environ.get("VERCEL", False)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if is_vercel else settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(search_router, prefix="/api")
    app.include_router(influencers_router, prefix="/api")
    app.include_router(exports_router, prefix="/api")
    app.include_router(brands_router, prefix="/api")

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
