import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.cards import router as cards_router
from backend.api.auth import router as auth_router
from backend.core.config import settings
app = FastAPI(
    title="Business Card Scanner API",
    description="Backend API for scanning, extracting and managing business cards",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(cards_router)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {
        "success": True,
        "message": "Business Card Scanner API is running",
    }


@app.get("/api/health")
async def health():
    return {
        "success": True,
        "message": "Backend is healthy",
    }