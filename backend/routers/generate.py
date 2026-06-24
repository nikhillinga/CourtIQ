from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any, List

from backend.services.query_parser import parse_query
from backend.services.metric_resolver import resolve_metrics
from backend.services.chart_selector import select_chart
from backend.services.nba_service import get_player_stats

router = APIRouter(tags=["AI Generation"])

class GenerateRequest(BaseModel):
    query: str

class GenerateResponse(BaseModel):
    message: str
    chart_data: Optional[Dict[str, Any]] = None

@router.post("/generate-chart", response_model=GenerateResponse)
def generate_chart(req: GenerateRequest):
    # 1. Parse natural language query
    parsed = parse_query(req.query)
    if parsed.get("error"):
        return GenerateResponse(message=parsed["error"])

    players = parsed.get("players", [])
    metrics = parsed.get("metrics", [])
    season = parsed.get("season", "2024-25")
    seasons_count = parsed.get("seasons_count", 1)
    mode = parsed.get("comparison_mode", "single_player")
    
    # 2. Resolve slang metrics to official API fields
    resolved = resolve_metrics(metrics)
    # Filter out unrecognised metrics
    valid_metrics = [m for m in metrics if resolved[m] is not None]
    if not valid_metrics and metrics:
        return GenerateResponse(message=f"Could not map the requested metrics ({', '.join(metrics)}) to official NBA stats.")
    if not valid_metrics:
        # Default to points if no metrics found but we need one
        valid_metrics = ["points_per_game"]
        resolved["points_per_game"] = "PTS"

    # 3. Determine Chart Type
    chart_info = select_chart(parsed)
    chart_type = chart_info["chart_type"]

    # 4. Fetch Stats for each player
    # Note: top_n without players isn't supported by our basic get_player_stats yet
    # so we'll return a friendly message.
    if not players:
        return GenerateResponse(message="I need specific player names to compare! (Top-N queries across the whole league aren't supported yet).")

    all_stats = {}
    for p in players:
        try:
            p_stats = get_player_stats(player_name=p, season=season, seasons_count=seasons_count, playoffs=False)
            all_stats[p] = p_stats
        except HTTPException as e:
            return GenerateResponse(message=f"Could not find data for {p}: {e.detail}")
        except Exception as e:
            return GenerateResponse(message=f"Error fetching data for {p}: {str(e)}")

    # 5. Format the data for the frontend ChartRenderer
    labels: List[str] = []
    datasets: List[Dict[str, Any]] = []

    # Format based on the selected chart shape
    if mode == "multi_player_trend" or (mode == "single_player" and seasons_count > 1):
        # Time-series: x-axis = seasons
        # For simplicity, grab the seasons from the first player
        p1 = players[0]
        # Sort chronologically
        sorted_season_data = sorted(all_stats[p1].season_data, key=lambda x: x.season)
        labels = [s.season for s in sorted_season_data]
        
        target_metric = resolved[valid_metrics[0]].lower() # The frontend doesn't need to know the raw code, but let's use the snake_case from valid_metrics
        # Actually, our SeasonStats model has fields like `points_per_game`, `rebounds_per_game`.
        # So we can just use the valid_metrics[0] directly (it matches the Pydantic model field names!)
        field_name = valid_metrics[0]

        for p in players:
            sorted_sd = sorted(all_stats[p].season_data, key=lambda x: x.season)
            # Map values by season just in case a player missed a season
            val_map = {s.season: getattr(s, field_name, 0) for s in sorted_sd}
            datasets.append({
                "label": all_stats[p].player_name,
                "values": [val_map.get(lbl, 0) for lbl in labels]
            })

    elif chart_type == "radar" or (len(valid_metrics) > 1 and chart_type != "scatter"):
        # X-axis = metrics
        labels = valid_metrics
        for p in players:
            p_res = all_stats[p]
            datasets.append({
                "label": p_res.player_name,
                "values": [getattr(p_res, m, 0) for m in valid_metrics]
            })

    elif chart_type == "scatter":
        # Scatter needs exactly 2 metrics. X-axis = metric1, Y-axis = metric2
        labels = [all_stats[p].player_name for p in players]
        m1 = valid_metrics[0]
        m2 = valid_metrics[1] if len(valid_metrics) > 1 else valid_metrics[0]
        
        datasets = [
            {"label": m1, "values": [getattr(all_stats[p], m1, 0) for p in players]},
            {"label": m2, "values": [getattr(all_stats[p], m2, 0) for p in players]}
        ]

    else:
        # Default bar: X-axis = players
        labels = [all_stats[p].player_name for p in players]
        m1 = valid_metrics[0]
        datasets = [
            {"label": m1, "values": [getattr(all_stats[p], m1, 0) for p in players]}
        ]

    title = parsed.get("time_range", "Comparison")
    if len(players) == 1:
        title = f"{all_stats[players[0]].player_name} - {title}"
    else:
        title = f"{', '.join([all_stats[p].player_name for p in players])} - {title}"

    chart_data = {
        "chart_type": chart_type,
        "title": title.title(),
        "labels": labels,
        "datasets": datasets,
    }
    
    if chart_type == "scatter":
        chart_data["x_axis_label"] = valid_metrics[0]
        chart_data["y_axis_label"] = valid_metrics[1] if len(valid_metrics) > 1 else ""

    return GenerateResponse(
        message=f"I found the data! Here is the chart for {title}.",
        chart_data=chart_data
    )
