import json
import os

import sys

def calculate_metrics(results_file='results.json'):
    results_path = os.path.join(os.path.dirname(__file__), results_file)
    if not os.path.exists(results_path):
        print(f"No results found at {results_path}. Run runner.py first.")
        return

    with open(results_path, 'r') as f:
        data = json.load(f)

    # Handle both new format (dict with 'results') and old format (list)
    if isinstance(data, dict) and 'results' in data:
        results = data['results']
        summary = data.get('summary', {})
    else:
        results = data
        summary = {}

    total = len(results)
    if total == 0:
        print("No tasks found in results.")
        return

    completed = sum(1 for r in results if r.get('status') == 'completed')
    
    # Analyze categories
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
    
    if summary:
        print(f"Average Speed: {summary.get('average_task_duration_seconds')}s/task")
        print(f"Tool Efficiency: {summary.get('tool_calls_per_completed_task')} calls/success")

    print("\nCategory Breakdown:")
    for cat, stats in categories.items():
        sr = (stats["completed"] / stats["total"]) * 100
        print(f"  {cat}: {sr:.2f}% ({stats['completed']}/{stats['total']})")

if __name__ == "__main__":
    res_file = sys.argv[1] if len(sys.argv) > 1 else 'results.json'
    calculate_metrics(res_file)
