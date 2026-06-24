import json
from backend.services.query_parser import parse

queries = [
    "Show me Curry and Dame three point percentage over five seasons",
    "Compare Jokic and Embiid rebounds",
    "Show top 10 players in assists",
    "What is the weather today?",
]

for q in queries:
    print(f"Query: {q}")
    result = parse(q)
    print(json.dumps(result, indent=2))
    print()
