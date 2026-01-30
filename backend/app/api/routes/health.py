from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import traceback
import os

from app.core.database import get_db
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check - verifies database connectivity.
    """
    try:
        # Import here to catch any import errors
        from app.core.database import get_session_maker
        
        session_maker = get_session_maker()
        async with session_maker() as db:
            await db.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        # Log full traceback for debugging
        print(f"Database connection error: {traceback.format_exc()}")

    try:
        settings = get_settings()
        debug = settings.debug
    except Exception as e:
        debug = False

    return JSONResponse(content={
        "status": "ready" if db_status == "connected" else "not_ready",
        "database": db_status,
        "debug": debug,
        "vercel": os.environ.get("VERCEL", "false")
    })
