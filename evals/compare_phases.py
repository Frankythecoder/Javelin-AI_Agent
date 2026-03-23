"""Compare EATP Phase A (cold) vs Phase B (seeded) vs Phase C (warm) results.

Usage:
    python evals/compare_phases.py [--a results_phase_a.json] [--b results_phase_b.json] [--c results_phase_c.json]

Outputs:
    1. Overall metrics comparison table
    2. Per-task breakdown (which tasks improved, regressed, or stayed the same)
    3. Correction carryover analysis (did Phase B corrections help in Phase C?)
    4. Category-level breakdown
"""
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_results(path):
    full_path = os.path.join(os.path.dirname(__file__), path)
    if not os.path.exists(full_path):
        print(f"WARNING: {full_path} not found. Run the phase first.")
        return None
    with open(full_path, 'r') as f:
        return json.load(f)


def print_header(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def compare_phases(phase_a_file, phase_b_file, phase_c_file, correction_policy_file=None):
    a = load_results(phase_a_file)
    b = load_results(phase_b_file)
    c = load_results(phase_c_file)

    if not a or not c:
        print("\nNeed at least Phase A and Phase C results to compare.")
        print("Run:")
        print(f"  python evals/runner.py --eatp-mode cold --output {phase_a_file}")
        print(f"  python evals/runner.py --eatp-mode cold --correction-policy correction_policy.json --output {phase_b_file}")
        print(f"  python evals/runner.py --eatp-mode warm --output {phase_c_file}")
        return

    # Load correction policy to identify which tasks had corrections
    correction_policy = {}
    if correction_policy_file:
        policy_path = os.path.join(os.path.dirname(__file__), correction_policy_file)
        if os.path.exists(policy_path):
            with open(policy_path, 'r') as f:
                cp = json.load(f)
                correction_policy = {k: v for k, v in cp.items() if not k.startswith('_')}

    # ── Section 1: Overall Metrics ──────────────────────────────────────
    print_header("1. OVERALL METRICS COMPARISON")

    phases = {"Phase A (cold)": a, "Phase C (warm)": c}
    if b:
        phases = {"Phase A (cold)": a, "Phase B (seeded)": b, "Phase C (warm)": c}

    # Print header row
    phase_names = list(phases.keys())
    header = f"{'Metric':<40}" + "".join(f"{name:>18}" for name in phase_names)
    print(f"\n{header}")
    print("-" * (40 + 18 * len(phase_names)))

    metrics = [
        ("Success Rate (%)", lambda d: d["summary"]["accuracy_percent"]),
        ("Completed Tasks", lambda d: d["summary"]["completed_tasks"]),
        ("Total Tasks", lambda d: d["summary"]["total_tasks"]),
        ("Avg Duration (s)", lambda d: d["summary"]["average_task_duration_seconds"]),
        ("Total Duration (s)", lambda d: d["summary"]["total_duration_seconds"]),
        ("Total Tool Calls", lambda d: d["summary"]["total_tool_calls"]),
        ("Tool Calls / Completed Task", lambda d: d["summary"]["tool_calls_per_completed_task"]),
    ]

    for name, getter in metrics:
        row = f"{name:<40}"
        for phase_data in phases.values():
            row += f"{getter(phase_data):>18}"
        print(row)

    # Delta row (A vs C)
    print()
    a_rate = a["summary"]["accuracy_percent"]
    c_rate = c["summary"]["accuracy_percent"]
    delta_rate = c_rate - a_rate
    a_tools = a["summary"]["tool_calls_per_completed_task"]
    c_tools = c["summary"]["tool_calls_per_completed_task"]
    delta_tools = c_tools - a_tools
    a_dur = a["summary"]["average_task_duration_seconds"]
    c_dur = c["summary"]["average_task_duration_seconds"]
    delta_dur = c_dur - a_dur

    sign = lambda x: f"+{x}" if x > 0 else str(x)
    print(f"{'DELTA (C - A):':<40}")
    print(f"  {'Success Rate Change:':<38}{sign(round(delta_rate, 2)):>18} pp")
    print(f"  {'Tool Efficiency Change:':<38}{sign(round(delta_tools, 2)):>18} calls/task")
    print(f"  {'Avg Duration Change:':<38}{sign(round(delta_dur, 2)):>18} seconds")

    # ── Section 2: Per-Task Comparison ──────────────────────────────────
    print_header("2. PER-TASK COMPARISON (Phase A vs Phase C)")

    a_tasks = {r["id"]: r for r in a["results"]}
    c_tasks = {r["id"]: r for r in c["results"]}
    b_tasks = {r["id"]: r for r in b["results"]} if b else {}

    improved = []
    regressed = []
    unchanged = []
    corrected_tasks = set(correction_policy.keys())

    print(f"\n{'Task':<12} {'Category':<22} {'A Status':<12} {'C Status':<12} {'A Tools':<9} {'C Tools':<9} {'Corrected?':<10} {'Result'}")
    print("-" * 110)

    for task_id in sorted(a_tasks.keys()):
        at = a_tasks[task_id]
        ct = c_tasks.get(task_id)
        if not ct:
            continue

        had_correction = "YES" if task_id in corrected_tasks else ""
        a_status = at["status"]
        c_status = ct["status"]
        a_tc = at["tool_calls"]
        c_tc = ct["tool_calls"]

        # Determine improvement
        if a_status == "failed" and c_status == "completed":
            result = "IMPROVED"
            improved.append(task_id)
        elif a_status == "completed" and c_status == "failed":
            result = "REGRESSED"
            regressed.append(task_id)
        elif a_status == c_status and c_tc < a_tc:
            result = "MORE EFFICIENT"
            improved.append(task_id)
        elif a_status == c_status and c_tc > a_tc:
            result = "LESS EFFICIENT"
            regressed.append(task_id)
        else:
            result = "SAME"
            unchanged.append(task_id)

        print(f"{task_id:<12} {at['category']:<22} {a_status:<12} {c_status:<12} {a_tc:<9} {c_tc:<9} {had_correction:<10} {result}")

    print(f"\nSummary: {len(improved)} improved, {len(regressed)} regressed, {len(unchanged)} unchanged")

    # ── Section 3: Correction Carryover Analysis ────────────────────────
    if corrected_tasks:
        print_header("3. CORRECTION CARRYOVER ANALYSIS")
        print("\nDid tasks with Phase B corrections improve in Phase C?\n")

        carried = 0
        not_carried = 0

        for task_id in sorted(corrected_tasks):
            at = a_tasks.get(task_id)
            ct = c_tasks.get(task_id)
            if not at or not ct:
                continue

            policy = correction_policy[task_id]
            denied_tool = policy.get("deny", "?")
            correction = policy.get("correction", "")[:60]

            a_tc = at["tool_calls"]
            c_tc = ct["tool_calls"]
            a_st = at["status"]
            c_st = ct["status"]

            # A task "carried over" if Phase C is better or equal (didn't regress)
            did_carry = (c_st == "completed" and a_st != "completed") or \
                        (c_st == a_st and c_tc <= a_tc)

            if did_carry:
                carried += 1
                marker = "CARRIED OVER"
            else:
                not_carried += 1
                marker = "NOT CARRIED"

            print(f"  {task_id}: denied={denied_tool}")
            print(f"    Correction: {correction}...")
            print(f"    Phase A: {a_st} ({a_tc} tools) -> Phase C: {c_st} ({c_tc} tools) -> {marker}")
            print()

        total = carried + not_carried
        rate = (carried / total * 100) if total > 0 else 0
        print(f"  Correction Carryover Rate: {carried}/{total} = {rate:.1f}%")
        print(f"  (Target for paper: >60%)")

    # ── Section 4: Category-Level Breakdown ─────────────────────────────
    print_header("4. CATEGORY-LEVEL BREAKDOWN")

    categories = {}
    for task_id in a_tasks:
        cat = a_tasks[task_id]["category"]
        if cat not in categories:
            categories[cat] = {"a_pass": 0, "c_pass": 0, "a_tools": 0, "c_tools": 0, "count": 0}
        categories[cat]["count"] += 1
        if a_tasks[task_id]["status"] == "completed":
            categories[cat]["a_pass"] += 1
        categories[cat]["a_tools"] += a_tasks[task_id]["tool_calls"]
        ct = c_tasks.get(task_id)
        if ct:
            if ct["status"] == "completed":
                categories[cat]["c_pass"] += 1
            categories[cat]["c_tools"] += ct["tool_calls"]

    print(f"\n{'Category':<25} {'A Rate':<10} {'C Rate':<10} {'Delta':<10} {'A Avg Tools':<14} {'C Avg Tools':<14}")
    print("-" * 83)
    for cat in sorted(categories.keys()):
        d = categories[cat]
        n = d["count"]
        a_r = f"{d['a_pass']}/{n}"
        c_r = f"{d['c_pass']}/{n}"
        delta = d['c_pass'] - d['a_pass']
        a_avg_t = f"{d['a_tools']/n:.1f}"
        c_avg_t = f"{d['c_tools']/n:.1f}"
        print(f"{cat:<25} {a_r:<10} {c_r:<10} {sign(delta):<10} {a_avg_t:<14} {c_avg_t:<14}")

    # ── Section 5: Experience Store Stats ───────────────────────────────
    print_header("5. EXPERIENCE STORE INSPECTION")
    try:
        import django
        from pathlib import Path
        from django.conf import settings
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
        if not settings.configured:
            settings.configure(
                DEBUG=True,
                OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
                INSTALLED_APPS=['chat'],
                DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3',
                                       'NAME': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.sqlite3')}},
                BASE_DIR=Path(__file__).resolve().parent.parent,
            )
            django.setup()

        from agents.experience_store import ExperienceStore
        experience_dir = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_eval")
        if os.path.exists(experience_dir):
            store = ExperienceStore(persist_dir=experience_dir)
            records = store.get_all()
            print(f"\n  Total experiences stored: {len(records)}")

            with_corrections = [r for r in records if r.user_corrections]
            successes = [r for r in records if r.outcome == "success"]
            failures = [r for r in records if r.outcome in ("failure", "partial")]

            print(f"  With corrections: {len(with_corrections)}")
            print(f"  Successes: {len(successes)}")
            print(f"  Failures/Partial: {len(failures)}")

            if with_corrections:
                print(f"\n  Stored corrections:")
                for r in with_corrections:
                    print(f"    - [{r.task_category}] {r.task_description[:50]}...")
                    for c in r.user_corrections:
                        print(f"      Correction: {c[:80]}...")
        else:
            print(f"\n  No eval experience store found at {experience_dir}")
            print("  Run Phase B first to populate it.")
    except Exception as e:
        print(f"\n  Could not inspect experience store: {e}")

    # ── Section 6: Paper-Ready Summary ──────────────────────────────────
    print_header("6. PAPER-READY SUMMARY")
    print(f"""
Use these numbers in your paper's results section:

  "After accumulating experiences from {len(corrected_tasks)} corrected tasks in Phase B,
   the EATP-augmented agent in Phase C achieved a success rate of {c_rate}%
   (vs {a_rate}% cold baseline, {sign(round(delta_rate, 2))}pp improvement),
   with an average of {c_tools} tool calls per completed task
   (vs {a_tools} in baseline, {sign(round(delta_tools, 2))} change).
   {len(improved)} of {len(a_tasks)} tasks showed improvement,
   {len(regressed)} regressed, and {len(unchanged)} were unchanged."
""")
    if corrected_tasks:
        print(f"  Correction carryover rate: {rate:.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare EATP experiment phases")
    parser.add_argument("--a", default="results_phase_a.json", help="Phase A results file")
    parser.add_argument("--b", default="results_phase_b.json", help="Phase B results file")
    parser.add_argument("--c", default="results_phase_c.json", help="Phase C results file")
    parser.add_argument("--correction-policy", default="correction_policy.json", help="Correction policy file")
    args = parser.parse_args()
    compare_phases(args.a, args.b, args.c, args.correction_policy)
