"""
Vercel Serverless Function entry point for FastAPI backend.
This wraps the FastAPI app to work with Vercel's serverless Python runtime.
"""
import sys
import os
from pathlib import Path

# Add backend to Python path so imports work
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Mark as Vercel environment
os.environ["VERCEL"] = "1"

from mangum import Mangum
from app.main import app

# Mangum adapter for AWS Lambda / Vercel serverless
# lifespan="off" because serverless doesn't support persistent connections
handler = Mangum(app, lifespan="off")
