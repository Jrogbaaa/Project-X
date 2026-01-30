"""
Vercel Serverless Function entry point for FastAPI backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create a minimal test app first
app = FastAPI(title="Influencer Discovery API")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "healthy", "environment": "vercel"}


@app.get("/api/test")
async def test():
    return {"message": "API is working!"}
