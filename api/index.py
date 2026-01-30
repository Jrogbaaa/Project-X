"""
Vercel Serverless Function entry point for FastAPI backend.
Vercel natively supports ASGI apps - just export the FastAPI app directly.
"""
import sys
import os
from pathlib import Path

# Add backend to Python path so imports work
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Mark as Vercel environment
os.environ["VERCEL"] = "1"

# Import the FastAPI app - Vercel handles ASGI natively
from app.main import app
