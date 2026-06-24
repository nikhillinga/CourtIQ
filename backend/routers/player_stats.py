"""
Router for the ``GET /player-stats`` endpoint.
"""

from fastapi import APIRouter, Query

import config
from backend.models.player_stats import PlayerStatsResponse
from backend.services.nba_service import get_player_stats

router = APIRouter(tags=["Player Stats"])


@router.get(
    "/player-stats",
    response_model=PlayerStatsResponse,
    summary="Fetch NBA player statistics",
    description=(
        "Look up a player by name and return per-game statistics for one or "
        "more seasons. Supports regular-season and playoff queries. Results "
        "are cached in Redis."
    ),
    responses={
        404: {"description": "Player not found or no stats for the requested season(s)"},
        400: {"description": "Invalid season format"},
        502: {"description": "NBA API unavailable after retries"},
    },
)
def player_stats(
    player_name: str = Query(
        ...,
        min_length=2,
        description="Full or partial player name (e.g. 'Shai Gilgeous-Alexander')",
    ),
    season: str = Query(
        default=config.CURRENT_SEASON,
        pattern=r"^\d{4}-\d{2}$",
        description="NBA season in YYYY-YY format (e.g. '2024-25')",
    ),
    seasons_count: int = Query(
        default=1,
        ge=1,
        le=20,
        description="Number of seasons to aggregate (going backwards from *season*)",
    ),
    playoffs: bool = Query(
        default=False,
        description="If true, return playoff stats instead of regular season",
    ),
) -> PlayerStatsResponse:
    """
    Synchronous handler — FastAPI runs it in a threadpool so the blocking
    ``time.sleep`` calls in the service layer don't starve the event loop.
    """
    return get_player_stats(
        player_name=player_name,
        season=season,
        seasons_count=seasons_count,
        playoffs=playoffs,
    )
