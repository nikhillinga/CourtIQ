"""
Metric Resolver

Maps basketball slang and semi-official terminology to official NBA stat field names.
"""

from typing import List, Dict, Optional

# The core dictionary mapping slang/synonyms to official keys.
# To extend, simply add new keys pointing to the official NBA stat field.
_METRIC_MAP = {
    # Points
    "points": "PTS",
    "points_per_game": "PTS",
    "pts": "PTS",
    "scoring": "PTS",
    "buckets": "PTS",

    # Assists
    "assists": "AST",
    "assists_per_game": "AST",
    "ast": "AST",
    "dimes": "AST",
    "helpers": "AST",
    "passing": "AST",

    # Rebounds
    "rebounds": "REB",
    "rebounds_per_game": "REB",
    "reb": "REB",
    "boards": "REB",
    "glass": "REB",
    "offensive rebounds": "OREB",
    "oreb": "OREB",
    "defensive rebounds": "DREB",
    "dreb": "DREB",

    # Steals
    "steals": "STL",
    "steals_per_game": "STL",
    "stl": "STL",
    "thefts": "STL",
    "swipes": "STL",
    "pickpockets": "STL",

    # Blocks
    "blocks": "BLK",
    "blocks_per_game": "BLK",
    "blk": "BLK",
    "rejections": "BLK",
    "swats": "BLK",

    # Turnovers
    "turnovers": "TOV",
    "turnovers_per_game": "TOV",
    "tov": "TOV",
    "giveaways": "TOV",
    "tos": "TOV",

    # Field Goals
    "field goals": "FGM",
    "fgm": "FGM",
    "field goal percentage": "FG_PCT",
    "fg_percentage": "FG_PCT",
    "fg%": "FG_PCT",
    "fg percentage": "FG_PCT",
    "shooting percentage": "FG_PCT",

    # 3-Pointers
    "three pointers": "FG3M",
    "3 pointers": "FG3M",
    "threes": "FG3M",
    "3s": "FG3M",
    "triples": "FG3M",
    "treys": "FG3M",
    "3pt": "FG3M",
    "three point percentage": "FG3_PCT",
    "three_point_percentage": "FG3_PCT",
    "3pt%": "FG3_PCT",
    "3p%": "FG3_PCT",

    # Free Throws
    "free throws": "FTM",
    "ftm": "FTM",
    "fts": "FTM",
    "foul shots": "FTM",
    "free throw percentage": "FT_PCT",
    "free_throw_percentage": "FT_PCT",
    "free_throw_attempts": "FTA",
    "ft%": "FT_PCT",

    # Advanced / Other
    "minutes": "MIN",
    "minutes_per_game": "MIN",
    "min": "MIN",
    "true shooting percentage": "TS_PCT",
    "true_shooting_percentage": "TS_PCT",
    "ts%": "TS_PCT",
    "plus minus": "PLUS_MINUS",
    "+/-": "PLUS_MINUS",
    "games played": "GP",
    "games_played": "GP",
    "gp": "GP",
    
    # Add any official keys to themselves so they resolve correctly
    "pts": "PTS",
    "ast": "AST",
    "reb": "REB",
    "stl": "STL",
    "blk": "BLK",
    "tov": "TOV",
    "fgm": "FGM",
    "fga": "FGA",
    "fg_pct": "FG_PCT",
    "fg3m": "FG3M",
    "fg3a": "FG3A",
    "fg3_pct": "FG3_PCT",
    "ftm": "FTM",
    "fta": "FTA",
    "ft_pct": "FT_PCT",
    "oreb": "OREB",
    "dreb": "DREB",
    "min": "MIN",
    "plus_minus": "PLUS_MINUS",
    "gp": "GP"
}

def resolve_metrics(input_metrics: List[str]) -> Dict[str, Optional[str]]:
    """
    Resolve a list of input metric names (slang or official) to official NBA stat fields.
    
    Args:
        input_metrics: List of string metrics (e.g., ["dimes", "boards", "unknown"])
        
    Returns:
        Dictionary mapping the input string to the official stat field or None if not recognized.
        (e.g., {"dimes": "AST", "boards": "REB", "unknown": None})
    """
    resolved = {}
    for term in input_metrics:
        # Normalize the string: lower case, strip whitespace
        normalized_term = term.lower().strip()
        
        # Look up the term in the dictionary. If not found, return None.
        resolved[term] = _METRIC_MAP.get(normalized_term, None)
        
    return resolved
