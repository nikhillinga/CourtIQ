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
