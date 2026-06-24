"""
Query Parser — translates natural-language basketball queries into
structured JSON via the OpenRouter LLM API.

Responsibilities:
  • Pre-filter: reject queries with no basketball relevance
  • Build a detailed prompt for the LLM
  • Parse + validate the model's JSON response

No NBA API calls or chart generation happen here — only parsing.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini client initialisation
# ---------------------------------------------------------------------------

_client = genai.Client(api_key=config.GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Basketball keyword pre-filter
# ---------------------------------------------------------------------------

_BASKETBALL_KEYWORDS: List[str] = [
    # General basketball terms
    "nba", "basketball", "hoops", "court", "dunk", "layup", "slam",
    "triple-double", "double-double", "quadruple-double",
    "playoff", "playoffs", "finals", "all-star", "all star", "mvp",
    "draft", "rookie", "sophomore",
    # Stat categories
    "points", "assists", "rebounds", "steals", "blocks", "turnovers",
    "field goal", "fg%", "fg ", "three point", "three-point", "3pt",
    "3-point", "free throw", "ft%", "ft ", "true shooting", "ts%",
    "per game", "ppg", "apg", "rpg", "spg", "bpg",
    "efficiency", "usage", "pace", "rating", "plus-minus", "+/-",
    "minutes", "mpg",
    # Positions & roles
    "guard", "forward", "center", "point guard", "shooting guard",
    "small forward", "power forward", "pg", "sg", "sf", "pf",
    # Team / league references
    "season", "regular season", "postseason",
    "lakers", "celtics", "warriors", "nets", "bucks", "nuggets",
    "heat", "suns", "76ers", "sixers", "knicks", "bulls", "spurs",
    "clippers", "rockets", "mavericks", "mavs", "thunder", "grizzlies",
    "timberwolves", "wolves", "cavaliers", "cavs", "raptors", "hawks",
    "pacers", "magic", "pistons", "hornets", "wizards", "blazers",
    "trail blazers", "jazz", "kings", "pelicans",
    # Common player name fragments used as shorthand
    "lebron", "curry", "steph", "giannis", "jokic", "luka", "embiid",
    "dame", "lillard", "kd", "durant", "harden", "tatum", "booker",
    "morant", "ja ", "sga", "shai", "wemby", "wembanyama",
    "kobe", "jordan", "shaq", "magic johnson", "bird",
    # Query-intent verbs common in basketball analysis
    "compare", "comparison", "vs", "versus", "head to head", "h2h",
    "rank", "ranking", "top", "leader", "leaders", "leaderboard",
    "trend", "average", "career", "stats", "stat", "statistics",
    "performance", "shooting", "scoring",
]

# Pre-compile a single regex for speed
_BASKETBALL_PATTERN: re.Pattern = re.compile(
    "|".join(re.escape(kw) for kw in _BASKETBALL_KEYWORDS),
    re.IGNORECASE,
)


def _is_basketball_query(query: str) -> bool:
    """Return True if *query* contains at least one basketball-related keyword."""
    return bool(_BASKETBALL_PATTERN.search(query))


# ---------------------------------------------------------------------------
# Prompt construction (separated for testability)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert NBA query parser. Your ONLY job is to extract structured
information from a user's natural-language basketball question.

Return a single JSON object (no markdown fences, no commentary) with exactly
these keys:

{
  "players":          [],       // list of player full names mentioned
                                // empty list if this is a top-N / leaderboard query
  "metrics":          [],       // list of stat keys (e.g. "three_point_percentage",
                                // "points_per_game", "rebounds_per_game", "assists_per_game",
                                // "fg_percentage", "free_throw_attempts",
                                // "true_shooting_percentage", "steals", "blocks")
  "season":           "",       // NBA season string like "2024-25"
  "time_range":       "",       // human-readable time description
                                // e.g. "2024-25 season", "last 5 seasons"
  "seasons_count":    1,        // integer — number of seasons to include
  "comparison_mode":  "",       // one of:
                                //   "single_player"       — one player, one or more stats
                                //   "multi_player_trend"  — multiple players over time
                                //   "top_n"               — leaderboard / ranking query
                                //   "head_to_head"        — direct comparison of 2 players
  "top_n":            null      // integer if comparison_mode is "top_n", else null
}

Rules:
- Use the FULL player name when you can infer it (e.g. "Curry" → "Stephen Curry",
  "Dame" → "Damian Lillard", "LeBron" → "LeBron James").
- Map natural stat names to snake_case keys matching this set:
  points_per_game, assists_per_game, rebounds_per_game, fg_percentage,
  three_point_percentage, free_throw_attempts, true_shooting_percentage,
  steals, blocks, turnovers, minutes_per_game, games_played.
- For "compare X and Y" or "X vs Y", use "head_to_head".
- For "top N" / "best" / "leaders", use "top_n" and set the top_n integer.
- If only one player is mentioned, use "single_player".
- If multiple players + a time span, use "multi_player_trend".
- ONLY output the JSON object. No explanation, no markdown."""


def build_parsing_prompt(query: str, current_season: str) -> str:
    """
    Build the user-message prompt sent to the LLM for query parsing.

    Kept as a pure function so it can be unit-tested without hitting the API.
    """
    return (
        f'Default season (use if not specified in query): "{current_season}"\n\n'
        f'User query: "{query}"'
    )


# ---------------------------------------------------------------------------
# Response parsing & validation
# ---------------------------------------------------------------------------

_VALID_COMPARISON_MODES = {
    "single_player",
    "multi_player_trend",
    "top_n",
    "head_to_head",
}


def _clean_json_response(raw: str) -> str:
    """Strip markdown code fences or stray whitespace from the model output."""
    text = raw.strip()
    # Remove ```json ... ``` wrappers that models sometimes add
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _validate_parsed(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise and validate the parsed result, filling in safe defaults
    for any missing keys.
    """
    data.setdefault("players", [])
    data.setdefault("metrics", [])
    data.setdefault("season", config.CURRENT_SEASON)
    data.setdefault("time_range", f"{config.CURRENT_SEASON} season")
    data.setdefault("seasons_count", 1)
    data.setdefault("comparison_mode", "single_player")
    data.setdefault("top_n", None)

    # Enforce types
    if not isinstance(data["players"], list):
        data["players"] = [data["players"]] if data["players"] else []

    if not isinstance(data["metrics"], list):
        data["metrics"] = [data["metrics"]] if data["metrics"] else []

    if not isinstance(data["seasons_count"], int) or data["seasons_count"] < 1:
        data["seasons_count"] = 1

    if data["comparison_mode"] not in _VALID_COMPARISON_MODES:
        logger.warning(
            "Unknown comparison_mode '%s' — falling back to 'single_player'",
            data["comparison_mode"],
        )
        data["comparison_mode"] = "single_player"

    if data["comparison_mode"] == "top_n" and data["top_n"] is None:
        data["top_n"] = 10  # sensible default

    if data["comparison_mode"] != "top_n":
        data["top_n"] = None

    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(query: str) -> Dict[str, Any]:
    """
    Parse a natural-language basketball query into structured JSON.

    Returns a dict with keys: players, metrics, season, time_range,
    seasons_count, comparison_mode, top_n.

    If the query is not basketball-related, returns an error dict with
    ``chart_data: null``.
    """
    query = query.strip()
    if not query:
        return {
            "error": "Empty query",
            "chart_data": None,
        }

    # ── Pre-filter: reject non-basketball queries ──────────────────────────
    if not _is_basketball_query(query):
        return {
            "error": "Query does not appear to be basketball-related",
            "chart_data": None,
        }

    # ── Call LLM via OpenRouter ────────────────────────────────────────────
    user_prompt = build_parsing_prompt(query, config.CURRENT_SEASON)

    try:
        response = _client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.0,
            ),
        )
        raw_text = response.text
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        exc_str = str(exc)
        if "429" in exc_str and "RESOURCE_EXHAUSTED" in exc_str:
            return {
                "error": "Tokens done for the day or something, 2 FT incoming for SGA",
                "chart_data": None,
            }
        return {
            "error": f"Failed to parse query — LLM error: {exc}",
            "chart_data": None,
        }

    if not raw_text:
        logger.error("Gemini returned empty response")
        return {
            "error": "Failed to parse query — empty model output",
            "chart_data": None,
        }

    # ── Parse JSON ────────────────────────────────────────────────────────
    cleaned = _clean_json_response(raw_text)

    try:
        parsed: Dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s\nRaw: %s", exc, raw_text)
        return {
            "error": "Failed to parse query — invalid model output",
            "chart_data": None,
        }

    # ── Validate & normalise ──────────────────────────────────────────────
    result = _validate_parsed(parsed)

    logger.info(
        "Parsed query → mode=%s  players=%s  metrics=%s  seasons=%d",
        result["comparison_mode"],
        result["players"],
        result["metrics"],
        result["seasons_count"],
    )

    return result
