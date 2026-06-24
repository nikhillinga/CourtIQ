"""
ShaiGilPT — FastAPI application entry point.

Run with:
    uvicorn backend.app:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from backend.routes import player_stats

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ShaiGilPT",
    description="NBA player statistics and AI-powered claim analysis",
    version="1.0.0",
    debug=config.DEBUG,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routes import player_stats, chart

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(player_stats.router)
app.include_router(chart.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
