import os
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

ENV = os.getenv("ENV", "development")  # "development" | "production"
DEBUG = ENV == "development"


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY is not set. Add it to your .env file.")


# ---------------------------------------------------------------------------
# LLM (Google Gemini)
# ---------------------------------------------------------------------------

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Redis Cache
# ---------------------------------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# TTLs in seconds
CACHE_TTL_CURRENT_SEASON = 60 * 60 * 24        # 24 hours
CACHE_TTL_HISTORICAL = 60 * 60 * 24 * 365      # 1 year (effectively permanent)

# Current NBA season — update at season start each year
CURRENT_SEASON = os.getenv("CURRENT_SEASON", "2024-25")


# ---------------------------------------------------------------------------
# NBA API
# ---------------------------------------------------------------------------

# Delay between nba_api calls to avoid rate limiting (seconds)
NBA_API_DELAY = float(os.getenv("NBA_API_DELAY", 0.6))

# Retry settings for nba_api calls
NBA_API_MAX_RETRIES = int(os.getenv("NBA_API_MAX_RETRIES", 3))
NBA_API_RETRY_BACKOFF = [1, 2, 4]   # seconds per retry attempt


# ---------------------------------------------------------------------------
# FastAPI Server
# ---------------------------------------------------------------------------

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# CORS — comma-separated list of allowed origins
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000"
).split(",")


# ---------------------------------------------------------------------------
# Verdict Engine Thresholds
# ---------------------------------------------------------------------------

VERDICT_THRESHOLDS = {
    "True":           0.80,
    "Mostly True":    0.60,
    "Mixed Evidence": 0.40,
    "Weak Claim":     0.20,
    # Below 0.20 → "False"
}