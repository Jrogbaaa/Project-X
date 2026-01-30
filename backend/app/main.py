import logging
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Import here to avoid circular imports and module-level execution issues
    from app.config import get_settings
    from app.core.database import init_db
    from app.api.routes import search_router, influencers_router, exports_router, health_router, brands_router
    
    settings = get_settings()
    is_vercel = os.environ.get("VERCEL", False)

    # Lifespan for non-serverless environments (local dev)
    # Vercel doesn't support lifespan events
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan events (only for local dev)."""
        if not is_vercel:
            await init_db()
        yield

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
        lifespan=None if is_vercel else lifespan,
        docs_url="/api/docs" if is_vercel else "/docs",
        redoc_url="/api/redoc" if is_vercel else "/redoc",
    )

    # Configure CORS - allow all origins on Vercel
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if is_vercel else settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers - all under /api prefix for Vercel routing
    app.include_router(health_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(influencers_router, prefix="/api")
    app.include_router(exports_router, prefix="/api")
    app.include_router(brands_router, prefix="/api")

    return app


# Only create app instance when running directly (not when imported by Vercel)
# Vercel's api/index.py will call create_app() directly
if not os.environ.get("VERCEL"):
    app = create_app()


if __name__ == "__main__":
    import uvicorn
    # Ensure app exists for direct execution
    if "app" not in dir():
        app = create_app()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
