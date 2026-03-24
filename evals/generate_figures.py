"""Generate paper-quality figures from EATP experiment results.

Usage:
    python evals/generate_figures.py

Reads result files from evals/ and saves figures to evals/figures/.
"""
import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib required: pip install matplotlib")
    sys.exit(1)


EVALS_DIR = os.path.dirname(os.path.abspath(__file__))
FIGURES_DIR = os.path.join(EVALS_DIR, "figures")

RESULT_FILES = {
    "Off": "results_off.json",
    "Static\nFew-shot": "results_static_fewshot.json",
    "Cold (A)": "results_phase_a.json",
    "Warm\n(succ. only)": "results_warm_successes.json",
    "Warm\n(full EATP)": "results_phase_c.json",
}

# Colorblind-safe palette (Wong 2011)
COLORS = ["#999999", "#E69F00", "#56B4E9", "#009E73", "#D55E00"]

CATEGORIES = [
    "File Operations", "Code Tasks", "Document Creation/Editing",
    "Travel/Booking", "GitHub Operations", "Multimedia",
    "Multi-tool Orchestration", "Cross-category",
]


def load_all():
    """Load all result files. Returns {label: data} for those that exist."""
    configs = {}
    for label, fname in RESULT_FILES.items():
        path = os.path.join(EVALS_DIR, fname)
        if os.path.exists(path):
            with open(path, 'r') as f:
                configs[label] = json.load(f)
    return configs


def fig1_success_rate(configs):
    """Bar chart: validated success rate per config."""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    labels = list(configs.keys())
    rates = []
    for data in configs.values():
        s = data["summary"]
        rate = s.get("validated_percent", s.get("accuracy_percent", 0))
        rates.append(rate)

    bars = ax.bar(range(len(labels)), rates, color=COLORS[:len(labels)], width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Validated Success Rate (%)", fontsize=9)
    ax.set_ylim(0, 105)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{rate:.0f}%", ha='center', va='bottom', fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    return fig


def fig2_tool_efficiency(configs):
    """Bar chart: avg tool calls per validated task."""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    labels = list(configs.keys())
    efficiencies = []
    for data in configs.values():
        s = data["summary"]
        efficiencies.append(s.get("tool_calls_per_completed_task", 0))

    bars = ax.bar(range(len(labels)), efficiencies, color=COLORS[:len(labels)], width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Avg Tool Calls / Task", fontsize=9)
    for bar, val in zip(bars, efficiencies):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{val:.1f}", ha='center', va='bottom', fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    return fig


def fig3_category_heatmap(configs):
    """Heatmap: success rate per category per config."""
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    labels = list(configs.keys())
    matrix = []

    for cat in CATEGORIES:
        row = []
        for data in configs.values():
            tasks = [r for r in data["results"] if r["category"] == cat]
            if tasks:
                validated = sum(1 for r in tasks if r.get("validated", r["status"] == "completed"))
                row.append(validated / len(tasks) * 100)
            else:
                row.append(0)
        matrix.append(row)

    matrix = np.array(matrix)
    im = ax.imshow(matrix, cmap="Greens", aspect="auto", vmin=0, vmax=100)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_yticks(range(len(CATEGORIES)))
    ax.set_yticklabels(CATEGORIES, fontsize=7)

    for i in range(len(CATEGORIES)):
        for j in range(len(labels)):
            val = matrix[i, j]
            color = "white" if val > 60 else "black"
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=7, color=color)

    fig.colorbar(im, ax=ax, label="Success %", shrink=0.8)
    fig.tight_layout()
    return fig


def fig4_correction_carryover(configs):
    """Horizontal bar chart: carryover rate per lesson."""
    fig, ax = plt.subplots(figsize=(3.5, 3.0))

    # Load transfer map and tasks
    tm_path = os.path.join(EVALS_DIR, "transfer_map.json")
    tasks_path = os.path.join(EVALS_DIR, "tasks.json")
    if not os.path.exists(tm_path) or not os.path.exists(tasks_path):
        ax.text(0.5, 0.5, "transfer_map.json or tasks.json not found",
                transform=ax.transAxes, ha='center')
        return fig

    with open(tm_path) as f:
        transfer_map = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
    with open(tasks_path) as f:
        tasks = json.load(f)

    # Get results from "Off" and "Warm (full EATP)" configs
    off_key = [k for k in configs if "Off" in k]
    warm_key = [k for k in configs if "full" in k.lower() or "warm\n(full" in k.lower()]
    if not off_key or not warm_key:
        ax.text(0.5, 0.5, "Need Off and Warm (full) results", transform=ax.transAxes, ha='center')
        return fig

    off_results = {r["id"]: r for r in configs[off_key[0]]["results"]}
    warm_results = {r["id"]: r for r in configs[warm_key[0]]["results"]}

    # Group transfer tasks by lesson
    lessons = {}
    for tid, info in transfer_map.items():
        lid = info["lesson_id"]
        if lid not in lessons:
            lessons[lid] = []
        lessons[lid].append(tid)

    lesson_ids = sorted(lessons.keys())
    carryover_rates = []
    for lid in lesson_ids:
        task_ids = lessons[lid]
        carried = 0
        total = 0
        for tid in task_ids:
            if tid in off_results and tid in warm_results:
                total += 1
                off_ok = off_results[tid].get("validated", off_results[tid]["status"] == "completed")
                warm_ok = warm_results[tid].get("validated", warm_results[tid]["status"] == "completed")
                if warm_ok and not off_ok:
                    carried += 1
                elif warm_ok and off_ok:
                    warm_tools = warm_results[tid]["tool_calls"]
                    off_tools = off_results[tid]["tool_calls"]
                    if warm_tools <= off_tools:
                        carried += 1
        rate = (carried / total * 100) if total > 0 else 0
        carryover_rates.append(rate)

    y_pos = range(len(lesson_ids))
    bars = ax.barh(y_pos, carryover_rates, color="#009E73", height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(lesson_ids, fontsize=8)
    ax.set_xlabel("Transfer Carryover Rate (%)", fontsize=9)
    ax.set_xlim(0, 105)

    for bar, rate in zip(bars, carryover_rates):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{rate:.0f}%", va='center', fontsize=8)

    overall = np.mean(carryover_rates) if carryover_rates else 0
    ax.axvline(x=overall, color='red', linestyle='--', linewidth=1, label=f"Mean: {overall:.0f}%")
    ax.legend(fontsize=7, loc='lower right')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    return fig


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    configs = load_all()

    if len(configs) < 2:
        print(f"Found {len(configs)} result file(s). Need at least 2 to generate figures.")
        print("Run the experiment phases first.")
        return

    print(f"Loaded {len(configs)} configs: {', '.join(configs.keys())}")

    generators = [
        ("fig1_success_rate", fig1_success_rate),
        ("fig2_tool_efficiency", fig2_tool_efficiency),
        ("fig3_category_heatmap", fig3_category_heatmap),
        ("fig4_correction_carryover", fig4_correction_carryover),
    ]

    figs = []
    for name, gen_fn in generators:
        fig = gen_fn(configs)
        path = os.path.join(FIGURES_DIR, f"{name}.png")
        fig.savefig(path, dpi=300, bbox_inches='tight')
        print(f"Saved: {path}")
        figs.append(fig)

    for fig in figs:
        plt.close(fig)

    print(f"\nAll figures saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
