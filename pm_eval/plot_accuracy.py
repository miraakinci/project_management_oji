# pm_eval/plot_accuracy.py
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from collections import Counter

BASE = Path(__file__).parent
COMP_CSV = BASE / "accuracy_completeness_report.csv"
PROP_CSV = BASE / "accuracy_propagation_report.csv"

def read_rows(p):
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def plot_completeness(rows):
    total = len(rows)
    ok = sum(1 for r in rows if (r.get("status","").strip().upper() == "OK"))
    pct = 100 * ok / total if total else 0.0

    plt.figure()
    plt.bar(["Complete"], [pct])
    plt.ylim(0, 100)
    plt.ylabel("Percent (%)")
    plt.title(f"PRINCE2 Element Completeness\n{ok}/{total} files complete ({pct:.1f}%)")
    plt.grid(axis="y", alpha=0.3)
    out = BASE / "accuracy_completeness.png"
    plt.savefig(out, bbox_inches="tight", dpi=160)
    print(f"Saved -> {out}")

def plot_propagation(rows):
    total = len(rows)
    passed = sum(1 for r in rows if (r.get("result","").strip().upper() == "PASS"))
    pct = 100 * passed / total if total else 0.0

    # overall
    plt.figure()
    plt.bar(["Consistent"], [pct])
    plt.ylim(0, 100)
    plt.ylabel("Percent (%)")
    plt.title(f"Forward–Backward Propagation Consistency\n{passed}/{total} pairs passed ({pct:.1f}%)")
    plt.grid(axis="y", alpha=0.3)
    out = BASE / "accuracy_propagation_overall.png"
    plt.savefig(out, bbox_inches="tight", dpi=160)
    print(f"Saved -> {out}")

    # per update type
    by_type = Counter((r.get("update_type","").strip() for r in rows))
    passed_by_type = Counter((r.get("update_type","").strip() for r in rows if r.get("result","").strip().upper()=="PASS"))

    labels, vals = [], []
    for t in sorted(by_type):
        total_t = by_type[t]
        pass_t = passed_by_type[t]
        pct_t = 100 * pass_t / total_t if total_t else 0.0
        labels.append(t or "unknown")
        vals.append(pct_t)

    plt.figure()
    plt.bar(labels, vals)
    plt.ylim(0, 100)
    plt.ylabel("Percent (%)")
    plt.title("Propagation Consistency by Update Type")
    plt.grid(axis="y", alpha=0.3)
    out = BASE / "accuracy_propagation_by_type.png"
    plt.savefig(out, bbox_inches="tight", dpi=160)
    print(f"Saved -> {out}")

def main():
    comp_rows = read_rows(COMP_CSV)
    prop_rows = read_rows(PROP_CSV)
    plot_completeness(comp_rows)
    plot_propagation(prop_rows)

if __name__ == "__main__":
    main()
