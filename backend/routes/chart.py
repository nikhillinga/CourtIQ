from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.services import query_parser
from backend.services import metric_resolver
from backend.services import nba_service
from backend.services import chart_selector

router = APIRouter(tags=["AI Generation"])

class GenerateRequest(BaseModel):
    query: str

class GenerateResponse(BaseModel):
    message: str
    chart_data: Optional[Dict[str, Any]] = None

@router.post("/generate-chart", response_model=GenerateResponse)
def generate_chart(req: GenerateRequest):
    try:
        # 1. Parse natural language query
        parsed = query_parser.parse(req.query)
        if parsed.get("error"):
            return GenerateResponse(message=parsed["error"])

        # 2. Resolve metrics
        raw_metrics = parsed.get("metrics", [])
        resolved_metrics_map = metric_resolver.resolve(raw_metrics)
        
        # We drop any invalid metrics, but if we drop all, we default to points
        valid_metrics = [m for m in raw_metrics if resolved_metrics_map.get(m)]
        if not valid_metrics and raw_metrics:
            return GenerateResponse(message=f"Could not map the requested metrics ({', '.join(raw_metrics)}) to official NBA stats.")
        if not valid_metrics:
            valid_metrics = ["points_per_game"]
            resolved_metrics_map["points_per_game"] = "PTS"
            
        parsed["metrics"] = valid_metrics # override with validated ones for downstream
        
        # 3. Fetch stats via nba_service
        try:
            data = nba_service.fetch(
                players=parsed.get("players", []),
                resolved_metrics=resolved_metrics_map,
                season=parsed.get("season", "2024-25"),
                seasons_count=parsed.get("seasons_count", 1)
            )
        except ValueError as ve:
            return GenerateResponse(message=str(ve))

        # 4. Shape the chart data
        chart_data = chart_selector.select(parsed, data)

        return GenerateResponse(
            message=f"I found the data! Here is the chart.",
            chart_data=chart_data
        )

    except Exception as e:
        # Top-level catch to ensure we never surface a 500 error to the frontend
        return GenerateResponse(message=f"An unexpected error occurred: {str(e)}")
