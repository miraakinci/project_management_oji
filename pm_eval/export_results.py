import os, json, csv, statistics
from pathlib import Path
import matplotlib.pyplot as plt

def main():
    eval_dir = Path(os.environ.get("EVAL_OUTPUT_DIR", Path.home() / "pm_eval_private" / "logs"))
    src = eval_dir / "api_metrics.jsonl"
    if not src.exists():
        raise SystemExit(f"No log file found at {src}")

    records = [json.loads(line) for line in src.open(encoding="utf-8")]
    results_dir = Path(__file__).resolve().parents[1] / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    csv_path = results_dir / "evaluation_summary.csv"
    fields = ["ts","feature","model","temperature","latency_s","tokens_in","tokens_out","est_cost","ok","schema_ok"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in records: w.writerow({k: r.get(k) for k in fields})

    latencies = [r["latency_s"] for r in records if r.get("latency_s") is not None]
    wf = sum(1 for r in records if r.get("ok")); sv = sum(1 for r in records if r.get("schema_ok"))
    n = len(records) or 1

    plt.figure(); plt.hist(latencies, bins=20); plt.title("Latency distribution")
    plt.xlabel("seconds"); plt.ylabel("count"); plt.tight_layout()
    plt.savefig(results_dir / "latency_hist.png")

    plt.figure(); plt.bar(["well-formed","schema-valid"], [wf, sv]); plt.title("XML validity counts")
    plt.tight_layout(); plt.savefig(results_dir / "xml_validity.png")

    lat_summary = {
        "n": len(latencies),
        "mean": round(statistics.fmean(latencies), 3) if latencies else None,
        "median": round(statistics.median(latencies), 3) if latencies else None,
        "p95": round(sorted(latencies)[int(0.95*(len(latencies)-1))], 3) if latencies else None,
        "max": round(max(latencies), 3) if latencies else None,
    }
    print("Wrote:", csv_path)
    print("Wrote:", results_dir / "latency_hist.png")
    print("Wrote:", results_dir / "xml_validity.png")
    print("Latency summary:", lat_summary)
    print("Well-formed XML %:", round(100*wf/n,1))
    print("Schema-valid XML %:", round(100*sv/n,1))

if __name__ == "__main__":
    main()
