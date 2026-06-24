import os
# os.environ["OPENROUTER_MODEL"] = "mistralai/mistral-small-3.1-24b-instruct"

import time
import json
from backend.services.query_parser import parse
from backend.services.metric_resolver import resolve
from backend.services.chart_selector import select_chart

queries = [
    # Slang-heavy with fouls drawn comparison
    "Who gets to the line more, Embiid or Giannis? Compare their fouls drawn over the last 3 seasons",
    # Multi-stat radar-style
    "Give me a full comparison of Luka vs SGA — points, assists, rebounds, steals, and turnovers",
    # Vague trend query
    "How has Steph's efficiency changed since 2019?",
    # Leaderboard with unusual stat
    "Top 5 players in blocks per game this season",
    # Multi-player single metric over time
    "Show me LeBron, KD, and Kawhi scoring trends over the last 6 seasons",
    # Non-basketball (should reject)
    "What is the capital of France?",
    # Ambiguous — could be single or comparison
    "Dame's three point shooting last 4 years",
    # Complex compound query
    "Compare Jokic and Embiid on assists, rebounds, and true shooting percentage this season",
]

print("Testing model accuracy and speed...")
print("-" * 50)

total_time = 0

for q in queries:
    print(f"Query: {q}")
    start = time.time()
    try:
        result = parse(q)
        end = time.time()
        elapsed = end - start
        total_time += elapsed
        
        print(f"Time taken: {elapsed:.2f} seconds")
        print("Result:")
        print(json.dumps(result, indent=2))
        
        # Test the metric resolver
        if result.get("metrics"):
            resolved_metrics = resolve(result["metrics"])
            print(f"Resolved Metrics: {json.dumps(resolved_metrics, indent=2)}")
        
        # Test the chart selector
        if not result.get("error"):
            chart = select_chart(result)
            print(f"Chart Selection: {json.dumps(chart, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 50)

print(f"Average time per query: {total_time / len(queries):.2f} seconds")
