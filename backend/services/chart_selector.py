"""
Chart Selector — picks the best chart type for a parsed basketball query.

Input:  Structured query dict (output of query_parser + metric_resolver)
Output: { "chart_type": "bar" | "line" | "scatter" | "radar", "reason": str }

Decision rules (evaluated top-to-bottom, first match wins):
  1. top_n query                                        → bar
  2. two metrics across multiple players (single season) → scatter
  3. two players, 3+ metrics, single season             → radar
  4. multi_player_trend                                 → line (multi-series)
  5. single player, seasons_count > 1                   → line
  6. head_to_head (default)                             → bar (grouped)
  7. fallback                                           → bar
"""

from __future__ import annotations

from typing import Any, Dict


def select_chart(query: Dict[str, Any]) -> Dict[str, str]:
    """
    Choose the most appropriate chart type for the given parsed query.

    Parameters
    ----------
    query : dict
        Must contain at minimum:
          - comparison_mode : str
          - players         : list[str]
          - metrics         : list[str]
          - seasons_count   : int
        Optional:
          - top_n           : int | None

    Returns
    -------
    dict  { "chart_type": str, "reason": str }
    """
    mode = query.get("comparison_mode", "")
    players = query.get("players", [])
    metrics = query.get("metrics", [])
    seasons = query.get("seasons_count", 1)
    top_n = query.get("top_n")

    num_players = len(players)
    num_metrics = len(metrics)

    # ── Rule 1: Leaderboard / top-N → bar ──────────────────────────────────
    if mode == "top_n":
        n = top_n or 10
        return {
            "chart_type": "bar",
            "reason": f"Top-{n} leaderboard query → horizontal bar chart",
        }

    # ── Rule 2: Two metrics, multiple players, single season → scatter ─────
    if num_metrics == 2 and num_players >= 2 and seasons == 1:
        return {
            "chart_type": "scatter",
            "reason": (
                f"Two metrics ({', '.join(metrics)}) across "
                f"{num_players} players in one season → scatter plot"
            ),
        }

    # ── Rule 3: Two players, 3+ metrics, single season → radar ─────────────
    if num_players == 2 and num_metrics >= 3 and seasons == 1:
        return {
            "chart_type": "radar",
            "reason": (
                f"Head-to-head ({players[0]} vs {players[1]}) with "
                f"{num_metrics} metrics → radar chart"
            ),
        }

    # ── Rule 4: Multi-player trend over time → line (multi-series) ─────────
    if mode == "multi_player_trend":
        return {
            "chart_type": "line",
            "reason": (
                f"Multi-player trend ({', '.join(players)}) over "
                f"{seasons} season(s) → multi-series line chart"
            ),
        }

    # ── Rule 5: Single player over multiple seasons → line ─────────────────
    if num_players == 1 and seasons > 1:
        return {
            "chart_type": "line",
            "reason": (
                f"Single player ({players[0]}) over {seasons} seasons "
                f"→ line chart"
            ),
        }

    # ── Rule 6: Head-to-head (two players, 1–2 metrics) → grouped bar ─────
    if mode == "head_to_head":
        return {
            "chart_type": "bar",
            "reason": (
                f"Head-to-head comparison ({', '.join(players)}) "
                f"→ grouped bar chart"
            ),
        }

    # ── Rule 7: Single player, single season → bar ─────────────────────────
    if mode == "single_player":
        player = players[0] if players else "unknown"
        return {
            "chart_type": "bar",
            "reason": f"Single player ({player}), single season → bar chart",
        }

    # ── Fallback ───────────────────────────────────────────────────────────
    return {
        "chart_type": "bar",
        "reason": f"Unrecognised query shape (mode={mode}) → default bar chart",
    }


def select(query: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a parsed query and the fetched NBA data, determine the chart type
    and format the data into the structure expected by the frontend ChartRenderer.
    """
    chart_info = select_chart(query)
    chart_type = chart_info["chart_type"]
    
    players = query.get("players", [])
    mode = query.get("comparison_mode", "single_player")
    seasons_count = query.get("seasons_count", 1)
    
    # We need to map metrics correctly based on what was resolved
    # Note: the input 'data' has keys matching the player names.
    # The actual metric keys we want to read off PlayerStatsResponse or SeasonStats
    # are just the original metric strings from query["metrics"] if they are valid field names.
    # Assuming 'data' values are PlayerStatsResponse objects.
    
    # Let's extract the valid metrics. We assume the caller filtered out invalid ones.
    # For shaping, we need the raw snake_case metric names (e.g. 'points_per_game')
    valid_metrics = query.get("metrics", [])
    if not valid_metrics:
        valid_metrics = ["points_per_game"]

    labels = []
    datasets = []

    if mode == "multi_player_trend" or (mode == "single_player" and seasons_count > 1):
        # Time-series: x-axis = seasons
        p1 = players[0]
        sorted_season_data = sorted(data[p1].season_data, key=lambda x: x.season)
        labels = [s.season for s in sorted_season_data]
        
        field_name = valid_metrics[0]

        for p in players:
            sorted_sd = sorted(data[p].season_data, key=lambda x: x.season)
            val_map = {s.season: getattr(s, field_name, 0) for s in sorted_sd}
            datasets.append({
                "label": data[p].player_name,
                "values": [val_map.get(lbl, 0) for lbl in labels]
            })

    elif chart_type == "radar" or (len(valid_metrics) > 1 and chart_type != "scatter"):
        # X-axis = metrics
        labels = valid_metrics
        for p in players:
            p_res = data[p]
            datasets.append({
                "label": p_res.player_name,
                "values": [getattr(p_res, m, 0) for m in valid_metrics]
            })

    elif chart_type == "scatter":
        # Scatter needs exactly 2 metrics. X-axis = metric1, Y-axis = metric2
        labels = [data[p].player_name for p in players]
        m1 = valid_metrics[0]
        m2 = valid_metrics[1] if len(valid_metrics) > 1 else valid_metrics[0]
        
        datasets = [
            {"label": m1, "values": [getattr(data[p], m1, 0) for p in players]},
            {"label": m2, "values": [getattr(data[p], m2, 0) for p in players]}
        ]

    else:
        # Default bar: X-axis = players
        labels = [data[p].player_name for p in players]
        m1 = valid_metrics[0]
        datasets = [
            {"label": m1, "values": [getattr(data[p], m1, 0) for p in players]}
        ]

    title = query.get("time_range", "Comparison")
    if len(players) == 1:
        title = f"{data[players[0]].player_name} - {title}"
    else:
        title = f"{', '.join([data[p].player_name for p in players])} - {title}"

    chart_data = {
        "chart_type": chart_type,
        "title": title.title(),
        "labels": labels,
        "datasets": datasets,
    }
    
    if chart_type == "scatter":
        chart_data["x_axis_label"] = valid_metrics[0]
        chart_data["y_axis_label"] = valid_metrics[1] if len(valid_metrics) > 1 else ""

    return chart_data
