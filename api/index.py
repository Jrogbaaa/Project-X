"""
Vercel Serverless Function entry point for FastAPI backend.
"""
import sys
import os
from pathlib import Path

# Mark as Vercel environment FIRST before any other imports
os.environ["VERCEL"] = "1"

# Add backend to Python path so imports work
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Import FastAPI app from backend
# The create_app() function is used to avoid module-level side effects
from app.main import create_app

# Create the app instance
app = create_app()
# Triggered redeploy 1769774227
