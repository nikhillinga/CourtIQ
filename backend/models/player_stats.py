"""
Pydantic models for the player-stats endpoint.
"""

from typing import List

from pydantic import BaseModel, Field


class SeasonStats(BaseModel):
    """Per-season statistical breakdown."""

    season: str = Field(..., example="2024-25", description="NBA season identifier")
    team: str = Field(..., example="OKC", description="Team abbreviation")
    games_played: int = Field(..., ge=0, description="Games played in the season")
    points_per_game: float = Field(..., ge=0)
    assists_per_game: float = Field(..., ge=0)
    rebounds_per_game: float = Field(..., ge=0)
    fg_percentage: float = Field(..., ge=0, description="Field goal percentage (0-100)")
    three_point_percentage: float = Field(..., ge=0, description="Three-point percentage (0-100)")
    free_throw_attempts: float = Field(..., ge=0, description="Free throw attempts per game")
    true_shooting_percentage: float = Field(..., ge=0, description="True shooting percentage (0-100)")


class PlayerStatsResponse(BaseModel):
    """Aggregated player statistics across one or more seasons."""

    player_name: str = Field(..., description="Full player name as listed by the NBA")
    player_id: int = Field(..., description="NBA player ID")

    # Aggregated headline stats
    points_per_game: float = Field(..., ge=0)
    assists_per_game: float = Field(..., ge=0)
    rebounds_per_game: float = Field(..., ge=0)
    fg_percentage: float = Field(..., ge=0, description="Field goal percentage (0-100)")
    three_point_percentage: float = Field(..., ge=0, description="Three-point percentage (0-100)")
    free_throw_attempts: float = Field(..., ge=0, description="Free throw attempts per game")
    true_shooting_percentage: float = Field(..., ge=0, description="True shooting percentage (0-100)")

    seasons_aggregated: int = Field(..., ge=1, description="Number of seasons included")
    season_data: List[SeasonStats] = Field(
        ..., description="Per-season breakdown (most recent first)"
    )
