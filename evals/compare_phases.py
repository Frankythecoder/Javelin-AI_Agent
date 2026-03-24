"""Compare EATP experiment configurations.

Supports 5+ configs: Off, Static Few-shot, Cold (A), Warm (successes-only), Warm (full EATP).
Uses the `validated` field as the primary success metric.

Usage:
    python evals/compare_phases.py [--configs ...] [--labels ...]

Outputs:
    1. Overall metrics comparison table
    2. Per-task breakdown (first vs last config)
    3. Correction carryover analysis (correctable + transfer tasks)
    4. Category-level breakdown
    5. Experience store stats
    6. Paper-ready summary
"""
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EVALS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_results(path):
    full_path = os.path.join(EVALS_DIR, path)
    if not os.path.exists(full_path):
        print(f"WARNING: {full_path} not found. Run the phase first.")
        return None
    with open(full_path, 'r') as f:
        return json.load(f)


def print_header(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def compare_configs(config_files, config_labels, correction_policy_file=None):
    # Load all configs
    configs = {}
    for fname, label in zip(config_files, config_labels):
        data = load_results(fname)
        if data:
            configs[label] = data

    if len(configs) < 2:
        print(f"\nFound {len(configs)} result file(s). Need at least 2 to compare.")
        print("Run the experiment phases first (see docs/superpowers/specs/2026-03-23-eatp-eval-expansion-design.md).")
        return

    # Load correction policy
    correction_policy = {}
    if correction_policy_file:
        policy_path = os.path.join(EVALS_DIR, correction_policy_file)
        if os.path.exists(policy_path):
            with open(policy_path, 'r') as f:
                cp = json.load(f)
                correction_policy = {k: v for k, v in cp.items() if not k.startswith('_')}

    # Load transfer map
    transfer_map = {}
    tm_path = os.path.join(EVALS_DIR, "transfer_map.json")
    if os.path.exists(tm_path):
        with open(tm_path, 'r') as f:
            raw = json.load(f)
            transfer_map = {k: v for k, v in raw.items() if not k.startswith('_')}

    sign = lambda x: f"+{x}" if x > 0 else str(x)

    # ── Section 1: Overall Metrics ──────────────────────────────────────
    print_header("1. OVERALL METRICS COMPARISON")

    labels = list(configs.keys())
    header = f"{'Metric':<40}" + "".join(f"{name:>18}" for name in labels)
    print(f"\n{header}")
    print("-" * (40 + 18 * len(labels)))

    metrics = [
        ("Validated Rate (%)", lambda d: d["summary"].get("validated_percent", d["summary"].get("accuracy_percent", 0))),
        ("Success Rate (%)", lambda d: d["summary"]["accuracy_percent"]),
        ("Validated Tasks", lambda d: d["summary"].get("validated_tasks", d["summary"]["completed_tasks"])),
        ("Completed Tasks", lambda d: d["summary"]["completed_tasks"]),
        ("Total Tasks", lambda d: d["summary"]["total_tasks"]),
        ("Avg Duration (s)", lambda d: d["summary"]["average_task_duration_seconds"]),
        ("Total Duration (s)", lambda d: d["summary"]["total_duration_seconds"]),
        ("Total Tool Calls", lambda d: d["summary"]["total_tool_calls"]),
        ("Tool Calls / Completed Task", lambda d: d["summary"]["tool_calls_per_completed_task"]),
    ]

    for name, getter in metrics:
        row = f"{name:<40}"
        for data in configs.values():
            row += f"{getter(data):>18}"
        print(row)

    # Delta row (first vs last config)
    first_label, last_label = labels[0], labels[-1]
    first_data, last_data = configs[first_label], configs[last_label]

    first_rate = first_data["summary"].get("validated_percent", first_data["summary"]["accuracy_percent"])
    last_rate = last_data["summary"].get("validated_percent", last_data["summary"]["accuracy_percent"])
    delta_rate = last_rate - first_rate
    first_tools = first_data["summary"]["tool_calls_per_completed_task"]
    last_tools = last_data["summary"]["tool_calls_per_completed_task"]
    delta_tools = last_tools - first_tools

    print(f"\n{'DELTA (' + last_label + ' - ' + first_label + '):':<40}")
    print(f"  {'Validated Rate Change:':<38}{sign(round(delta_rate, 2)):>18} pp")
    print(f"  {'Tool Efficiency Change:':<38}{sign(round(delta_tools, 2)):>18} calls/task")

    # ── Section 2: Per-Task Comparison ──────────────────────────────────
    print_header(f"2. PER-TASK COMPARISON ({first_label} vs {last_label})")

    first_tasks = {r["id"]: r for r in first_data["results"]}
    last_tasks = {r["id"]: r for r in last_data["results"]}
    corrected_task_ids = set(correction_policy.keys())
    transfer_task_ids = set(transfer_map.keys())

    improved = []
    regressed = []
    unchanged = []

    print(f"\n{'Task':<12} {'Category':<25} {'First':<10} {'Last':<10} {'F Tools':<9} {'L Tools':<9} {'Class':<12} {'Result'}")
    print("-" * 115)

    for task_id in sorted(first_tasks.keys()):
        ft = first_tasks[task_id]
        lt = last_tasks.get(task_id)
        if not lt:
            continue

        f_val = ft.get("validated", ft["status"] == "completed")
        l_val = lt.get("validated", lt["status"] == "completed")
        f_tc = ft["tool_calls"]
        l_tc = lt["tool_calls"]

        task_class = ""
        if task_id in corrected_task_ids:
            task_class = "correctable"
        elif task_id in transfer_task_ids:
            task_class = "transfer"

        if not f_val and l_val:
            result = "IMPROVED"
            improved.append(task_id)
        elif f_val and not l_val:
            result = "REGRESSED"
            regressed.append(task_id)
        elif f_val and l_val and l_tc < f_tc:
            result = "MORE EFFICIENT"
            improved.append(task_id)
        elif f_val and l_val and l_tc > f_tc:
            result = "LESS EFFICIENT"
            regressed.append(task_id)
        else:
            result = "SAME"
            unchanged.append(task_id)

        f_str = "PASS" if f_val else "FAIL"
        l_str = "PASS" if l_val else "FAIL"
        print(f"{task_id:<12} {ft['category']:<25} {f_str:<10} {l_str:<10} {f_tc:<9} {l_tc:<9} {task_class:<12} {result}")

    print(f"\nSummary: {len(improved)} improved, {len(regressed)} regressed, {len(unchanged)} unchanged")

    # ── Section 3: Correction Carryover Analysis ────────────────────────
    if corrected_task_ids or transfer_task_ids:
        print_header("3. CORRECTION CARRYOVER ANALYSIS")

        # 3a: Correctable tasks
        if corrected_task_ids:
            print("\n  3a. CORRECTABLE TASKS (directly taught)")
            carried_c = 0
            total_c = 0
            for task_id in sorted(corrected_task_ids):
                ft = first_tasks.get(task_id)
                lt = last_tasks.get(task_id)
                if not ft or not lt:
                    continue
                total_c += 1
                f_val = ft.get("validated", ft["status"] == "completed")
                l_val = lt.get("validated", lt["status"] == "completed")
                did_carry = l_val and (not f_val or lt["tool_calls"] <= ft["tool_calls"])
                if did_carry:
                    carried_c += 1
                policy = correction_policy[task_id]
                marker = "CARRIED" if did_carry else "NOT CARRIED"
                print(f"    {task_id}: denied={policy.get('deny', '?')} | {marker}")

            rate_c = (carried_c / total_c * 100) if total_c > 0 else 0
            print(f"\n  Correctable Carryover Rate: {carried_c}/{total_c} = {rate_c:.1f}%")

        # 3b: Transfer tasks
        if transfer_task_ids:
            print("\n  3b. TRANSFER TASKS (unseen tasks, same lesson)")
            lessons = {}
            carried_t = 0
            total_t = 0
            for task_id in sorted(transfer_task_ids):
                ft = first_tasks.get(task_id)
                lt = last_tasks.get(task_id)
                if not ft or not lt:
                    continue
                total_t += 1
                info = transfer_map[task_id]
                lid = info["lesson_id"]
                f_val = ft.get("validated", ft["status"] == "completed")
                l_val = lt.get("validated", lt["status"] == "completed")
                did_carry = l_val and (not f_val or lt["tool_calls"] <= ft["tool_calls"])
                if did_carry:
                    carried_t += 1
                if lid not in lessons:
                    lessons[lid] = {"carried": 0, "total": 0}
                lessons[lid]["total"] += 1
                if did_carry:
                    lessons[lid]["carried"] += 1
                marker = "CARRIED" if did_carry else "NOT CARRIED"
                print(f"    {task_id} ({lid}): sources={info['source_tasks']} | {marker}")

            rate_t = (carried_t / total_t * 100) if total_t > 0 else 0
            print(f"\n  Transfer Carryover Rate: {carried_t}/{total_t} = {rate_t:.1f}%")

            print("\n  Per-lesson transfer rates:")
            for lid in sorted(lessons.keys()):
                d = lessons[lid]
                r = (d["carried"] / d["total"] * 100) if d["total"] > 0 else 0
                print(f"    {lid}: {d['carried']}/{d['total']} = {r:.0f}%")

    # ── Section 4: Category-Level Breakdown ─────────────────────────────
    print_header("4. CATEGORY-LEVEL BREAKDOWN")

    categories = {}
    for task_id in first_tasks:
        cat = first_tasks[task_id]["category"]
        if cat not in categories:
            categories[cat] = {}
        for label in labels:
            if label not in categories[cat]:
                categories[cat][label] = {"pass": 0, "tools": 0, "count": 0}
        categories[cat][first_label]["count"] += 1

    for label, data in configs.items():
        for r in data["results"]:
            cat = r["category"]
            if cat not in categories:
                continue
            if label not in categories[cat]:
                categories[cat][label] = {"pass": 0, "tools": 0, "count": 0}
            categories[cat][label]["count"] += 1
            if r.get("validated", r["status"] == "completed"):
                categories[cat][label]["pass"] += 1
            categories[cat][label]["tools"] += r["tool_calls"]

    cat_header = f"{'Category':<28}" + "".join(f"{l:>14}" for l in labels)
    print(f"\n{cat_header}")
    print("-" * (28 + 14 * len(labels)))
    for cat in sorted(categories.keys()):
        row = f"{cat:<28}"
        for label in labels:
            d = categories[cat].get(label, {"pass": 0, "count": 0})
            n = d["count"]
            p = d["pass"]
            row += f"{f'{p}/{n}':>14}" if n > 0 else f"{'—':>14}"
        print(row)

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
        else:
            print(f"\n  No eval experience store found at {experience_dir}")
            print("  Run Phase B first to populate it.")
    except Exception as e:
        print(f"\n  Could not inspect experience store: {e}")

    # ── Section 6: Paper-Ready Summary ──────────────────────────────────
    print_header("6. PAPER-READY SUMMARY")

    correctable_rate = rate_c if corrected_task_ids else 0
    transfer_rate = rate_t if transfer_task_ids else 0

    print(f"""
Use these numbers in your paper's results section:

  "The EATP-augmented agent ({last_label}) achieved a validated success rate of {last_rate}%
   (vs {first_rate}% baseline [{first_label}], {sign(round(delta_rate, 2))}pp improvement),
   with an average of {last_tools} tool calls per completed task
   (vs {first_tools} in baseline, {sign(round(delta_tools, 2))} change).
   {len(improved)} of {len(first_tasks)} tasks showed improvement,
   {len(regressed)} regressed, and {len(unchanged)} were unchanged.
   Correction carryover rate: {correctable_rate:.1f}% (correctable), {transfer_rate:.1f}% (transfer)."
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare EATP experiment configurations")
    parser.add_argument("--configs", nargs="+",
        default=["results_off.json", "results_static_fewshot.json",
                 "results_phase_a.json", "results_warm_successes.json",
                 "results_phase_c.json"],
        help="Result files to compare")
    parser.add_argument("--labels", nargs="+",
        default=["Off", "Static Few-shot", "Cold (A)", "Warm (succ)", "Warm (full)"],
        help="Labels for each config")
    parser.add_argument("--correction-policy", default="correction_policy.json",
        help="Correction policy file")
    args = parser.parse_args()
    compare_configs(args.configs, args.labels, args.correction_policy)
