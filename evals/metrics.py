import json
import os

import sys

def calculate_metrics(results_file='results.json'):
    results_path = os.path.join(os.path.dirname(__file__), results_file)
    if not os.path.exists(results_path):
        print(f"No results found at {results_path}. Run runner.py first.")
        return

    with open(results_path, 'r') as f:
        results = json.load(f)

    total = len(results)
    completed = sum(1 for r in results if r.get('status') == 'completed')
    
    # In a real paper, you'd have more sophisticated checks
    # Here we show how categories can be analyzed
    categories = {}
    for r in results:
        cat = r.get('category', 'Unknown')
        if cat not in categories:
            categories[cat] = {"total": 0, "completed": 0}
        categories[cat]["total"] += 1
        if r.get('status') == 'completed':
            categories[cat]["completed"] += 1

    print(f"--- Evaluation Metrics ({results_file}) ---")
    print(f"Total Tasks: {total}")
    print(f"Overall Success Rate: {(completed/total)*100:.2f}%")
    print("\nCategory Breakdown:")
    for cat, stats in categories.items():
        sr = (stats["completed"] / stats["total"]) * 100
        print(f"  {cat}: {sr:.2f}% ({stats['completed']}/{stats['total']})")

if __name__ == "__main__":
    res_file = sys.argv[1] if len(sys.argv) > 1 else 'results.json'
    calculate_metrics(res_file)
