"""
NBA Service — core business logic for fetching and aggregating player statistics.

Responsibilities:
  • Player lookup via nba_api static data
  • Career stats retrieval with configurable retry + backoff
  • Per-season extraction and multi-season aggregation
  • Redis caching with separate TTLs for current vs. historical seasons
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

import pandas as pd
from fastapi import HTTPException
from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.static import players

import config
from backend.cache.redis_cache import cache_get, cache_set
from backend.models.player_stats import PlayerStatsResponse, SeasonStats

logger = logging.getLogger(__name__)


# =========================================================================
# Season helpers
# =========================================================================


def _parse_season_start_year(season: str) -> int:
    """Extract the start year from a season string like ``'2024-25'``."""
    try:
        return int(season.split("-")[0])
    except (ValueError, IndexError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid season format '{season}'. Expected 'YYYY-YY' (e.g. '2024-25').",
        ) from exc


def _format_season(start_year: int) -> str:
    """Convert a start year into an NBA season string (e.g. ``2024`` → ``'2024-25'``)."""
    end_suffix = (start_year + 1) % 100
    return f"{start_year}-{end_suffix:02d}"


def _compute_season_range(season: str, count: int) -> List[str]:
    """
    Return *count* season strings ending at *season*, ordered most-recent first.

    >>> _compute_season_range("2024-25", 3)
    ['2024-25', '2023-24', '2022-23']
    """
    start_year = _parse_season_start_year(season)
    return [_format_season(start_year - i) for i in range(count)]


def _is_current_season(season: str) -> bool:
    return season == config.CURRENT_SEASON


# =========================================================================
# Cache key
# =========================================================================


def _cache_key(player_id: int, season: str, seasons_count: int, playoffs: bool) -> str:
    mode = "playoffs" if playoffs else "regular"
    return f"nba:player_stats:{player_id}:{season}:x{seasons_count}:{mode}"


# =========================================================================
# NBA API calls — retry wrapper
# =========================================================================


def _call_with_retry(api_callable, description: str = "NBA API call"):
    """
    Execute *api_callable* (a zero-arg function) with retry logic.

    • Sleeps ``config.NBA_API_DELAY`` **before** each attempt (rate-limit).
    • On failure, waits ``config.NBA_API_RETRY_BACKOFF[attempt]`` seconds.
    • After ``config.NBA_API_MAX_RETRIES`` failures, re-raises the last exception.
    """
    last_exc: Exception | None = None

    for attempt in range(config.NBA_API_MAX_RETRIES):
        try:
            time.sleep(config.NBA_API_DELAY)
            return api_callable()
        except Exception as exc:
            last_exc = exc
            backoff_idx = min(attempt, len(config.NBA_API_RETRY_BACKOFF) - 1)
            backoff = config.NBA_API_RETRY_BACKOFF[backoff_idx]

            if attempt < config.NBA_API_MAX_RETRIES - 1:
                logger.warning(
                    "%s — attempt %d/%d failed (%s). Retrying in %ds…",
                    description,
                    attempt + 1,
                    config.NBA_API_MAX_RETRIES,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
            else:
                logger.error(
                    "%s — all %d attempts exhausted. Last error: %s",
                    description,
                    config.NBA_API_MAX_RETRIES,
                    exc,
                )

    # Should be unreachable unless MAX_RETRIES == 0
    raise HTTPException(
        status_code=502,
        detail=f"NBA API unavailable after {config.NBA_API_MAX_RETRIES} retries.",
    ) from last_exc


# =========================================================================
# Player lookup
# =========================================================================


def find_player(player_name: str) -> Dict[str, Any]:
    """
    Search for an NBA player by name.

    Uses ``nba_api.stats.static.players.find_players_by_full_name`` which
    does a case-insensitive regex search.  We escape the input to avoid
    accidental regex injection.

    Raises ``HTTPException(404)`` if no match is found.
    """
    escaped = re.escape(player_name)
    matches: List[Dict[str, Any]] = players.find_players_by_full_name(escaped)

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"Player '{player_name}' not found. Try the full name (e.g. 'LeBron James').",
        )

    # Prefer an exact (case-insensitive) match if present
    for m in matches:
        if m["full_name"].lower() == player_name.lower():
            return m

    # Otherwise return the first (best) match
    return matches[0]


# =========================================================================
# Stats fetching
# =========================================================================


def _fetch_career_dataframe(player_id: int, playoffs: bool) -> pd.DataFrame:
    """
    Fetch the full career stats DataFrame for a player.

    Returns the regular-season or post-season totals table from
    ``PlayerCareerStats`` in **PerGame** mode.
    """

    def _api_call() -> List[pd.DataFrame]:
        career = playercareerstats.PlayerCareerStats(
            player_id=player_id,
            per_mode36="PerGame",
        )
        return career.get_data_frames()

    dataframes: List[pd.DataFrame] = _call_with_retry(
        _api_call,
        description=f"PlayerCareerStats(player_id={player_id})",
    )

    if playoffs:
        # Post-season totals are typically at index 2
        if len(dataframes) > 2 and not dataframes[2].empty:
            return dataframes[2]
        raise HTTPException(
            status_code=404,
            detail="No playoff statistics available for this player.",
        )

    # Regular-season totals at index 0
    return dataframes[0]


# =========================================================================
# Row → SeasonStats extraction
# =========================================================================


def _row_to_season_stats(row: pd.Series, season: str) -> SeasonStats:
    """Transform a single DataFrame row into a ``SeasonStats`` model."""
    pts = float(row.get("PTS", 0))
    fga = float(row.get("FGA", 0))
    fta = float(row.get("FTA", 0))

    # True Shooting %:  PTS / (2 × (FGA + 0.44 × FTA))
    true_shooting_attempts = 2 * (fga + 0.44 * fta)
    ts_pct = round((pts / true_shooting_attempts) * 100, 1) if true_shooting_attempts > 0 else 0.0

    return SeasonStats(
        season=season,
        team=str(row.get("TEAM_ABBREVIATION", "N/A")),
        games_played=int(row.get("GP", 0)),
        points_per_game=round(pts, 1),
        assists_per_game=round(float(row.get("AST", 0)), 1),
        rebounds_per_game=round(float(row.get("REB", 0)), 1),
        fg_percentage=round(float(row.get("FG_PCT", 0)) * 100, 1),
        three_point_percentage=round(float(row.get("FG3_PCT", 0)) * 100, 1),
        free_throw_attempts=round(fta, 1),
        true_shooting_percentage=ts_pct,
    )


def _pick_season_row(season_rows: pd.DataFrame) -> pd.Series:
    """
    When a player was traded mid-season the API returns multiple rows.
    Prefer the ``TOT`` (total) row; fall back to the last row.
    """
    if len(season_rows) > 1:
        tot = season_rows[season_rows["TEAM_ABBREVIATION"] == "TOT"]
        if not tot.empty:
            return tot.iloc[0]
    return season_rows.iloc[-1]


# =========================================================================
# Multi-season aggregation (games-played weighted)
# =========================================================================

_AGGREGATION_FIELDS = [
    "points_per_game",
    "assists_per_game",
    "rebounds_per_game",
    "fg_percentage",
    "three_point_percentage",
    "free_throw_attempts",
    "true_shooting_percentage",
]


def _aggregate_seasons(season_data: List[SeasonStats]) -> Dict[str, float]:
    """
    Compute a games-played-weighted average across multiple seasons.
    """
    total_gp = sum(s.games_played for s in season_data)
    if total_gp == 0:
        return {field: 0.0 for field in _AGGREGATION_FIELDS}

    return {
        field: round(
            sum(getattr(s, field) * s.games_played for s in season_data) / total_gp,
            1,
        )
        for field in _AGGREGATION_FIELDS
    }


# =========================================================================
# Public entry point
# =========================================================================


def get_player_stats(
    player_name: str,
    season: str,
    seasons_count: int,
    playoffs: bool,
) -> PlayerStatsResponse:
    """
    Look up a player, fetch (or retrieve from cache) their stats for the
    requested season range, aggregate if needed, and return a response model.
    """
    # --- 1. Resolve player ---------------------------------------------------
    player = find_player(player_name)
    player_id: int = player["id"]
    player_full_name: str = player["full_name"]

    # --- 2. Season range ------------------------------------------------------
    seasons = _compute_season_range(season, seasons_count)

    # --- 3. Check cache -------------------------------------------------------
    key = _cache_key(player_id, season, seasons_count, playoffs)
    cached = cache_get(key)
    if cached is not None:
        logger.info("Cache hit: %s (%s)", player_full_name, key)
        return PlayerStatsResponse(**cached)

    # --- 4. Fetch from NBA API ------------------------------------------------
    logger.info(
        "Fetching stats for %s (id=%d) | seasons=%s | playoffs=%s",
        player_full_name,
        player_id,
        seasons,
        playoffs,
    )
    stats_df = _fetch_career_dataframe(player_id, playoffs)

    # --- 5. Extract per-season data -------------------------------------------
    season_data: List[SeasonStats] = []
    for s in seasons:
        rows = stats_df[stats_df["SEASON_ID"] == s]
        if rows.empty:
            logger.info("No data for %s in season %s — skipping", player_full_name, s)
            continue
        season_data.append(_row_to_season_stats(_pick_season_row(rows), s))

    if not season_data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No statistics found for {player_full_name} "
                f"in the requested season(s): {', '.join(seasons)}."
            ),
        )

    # --- 6. Aggregate ---------------------------------------------------------
    if len(season_data) == 1:
        agg = {field: getattr(season_data[0], field) for field in _AGGREGATION_FIELDS}
    else:
        agg = _aggregate_seasons(season_data)

    # --- 7. Build response ----------------------------------------------------
    response = PlayerStatsResponse(
        player_name=player_full_name,
        player_id=player_id,
        seasons_aggregated=len(season_data),
        season_data=season_data,
        **agg,
    )

    # --- 8. Cache -------------------------------------------------------------
    contains_current = any(_is_current_season(s.season) for s in season_data)
    ttl = config.CACHE_TTL_CURRENT_SEASON if contains_current else config.CACHE_TTL_HISTORICAL
    cache_set(key, response.model_dump(), ttl)
    logger.info("Cached %s (ttl=%ds)", key, ttl)

    return response


def fetch(
    players: List[str],
    resolved_metrics: Dict[str, str | None],
    season: str,
    seasons_count: int,
) -> Dict[str, PlayerStatsResponse]:
    """
    Fetch and aggregate stats for a list of players.
    
    Raises a ValueError with a user-friendly message if no players are provided.
    Returns a dictionary mapping the queried player name to their PlayerStatsResponse.
    """
    if not players:
        raise ValueError("I need specific player names to compare! (Top-N queries across the whole league aren't supported yet).")

    all_stats = {}
    for p in players:
        # We catch exceptions to wrap them in ValueError for the orchestrator to handle gracefully
        try:
            p_stats = get_player_stats(
                player_name=p,
                season=season,
                seasons_count=seasons_count,
                playoffs=False
            )
            all_stats[p] = p_stats
        except HTTPException as e:
            raise ValueError(f"Could not find data for {p}: {e.detail}") from e
        except Exception as e:
            raise ValueError(f"Error fetching data for {p}: {str(e)}") from e

    return all_stats
