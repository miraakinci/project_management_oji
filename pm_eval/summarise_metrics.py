from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
import math

import pandas as pd
import matplotlib.pyplot as plt

#config 
LOG_PATH = Path.home() / "pm_eval_private" / "logs" / "api_metrics.jsonl"
OUT_DIR  = Path(__file__).parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Projection parameters (edit for your scenario)
USERS_PER_DAY   = 50   # active users/day
CALLS_PER_USER  = 5    # number of generations per user/day

# load 
if not LOG_PATH.exists():
    raise SystemExit(f"Log file not found: {LOG_PATH}")

df = pd.read_json(LOG_PATH, lines=True)

# Keep only the fields we need
cols = ["ts", "feature", "model", "temperature", "latency_s",
        "tokens_in", "tokens_out", "est_cost", "currency",
        "pricing_model_key", "used_mock"]
df = df[[c for c in cols if c in df.columns]].copy()

# Parse timestamp for optional resampling
df["ts"] = pd.to_datetime(df["ts"], errors="coerce")

# ------------------ helpers -----------------
def summary_block(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """Return a one-row summary for a frame."""
    if frame.empty:
        return pd.DataFrame([{
            "label": label, "n": 0,
            "latency_mean": None, "latency_p50": None, "latency_p95": None, "latency_max": None,
            "tokens_in_mean": None, "tokens_out_mean": None, "cost_mean_gbp": None
        }])
    q = frame["latency_s"].quantile
    return pd.DataFrame([{
        "label": label,
        "n": int(len(frame)),
        "latency_mean": round(frame["latency_s"].mean(), 3),
        "latency_p50":  round(frame["latency_s"].median(), 3),
        "latency_p95":  round(float(q(0.95)), 3),
        "latency_max":  round(frame["latency_s"].max(), 3),
        "tokens_in_mean":  round(frame["tokens_in"].mean(), 2),
        "tokens_out_mean": round(frame["tokens_out"].mean(), 2),
        "cost_mean_gbp":   round(frame["est_cost"].mean(), 6),
    }])

def percentiles(series: pd.Series, ps=(0.05,0.25,0.5,0.75,0.95)):
    return {f"p{int(p*100)}": round(float(series.quantile(p)), 3) for p in ps}

# ------------------ overall summary ------------------
overall = summary_block(df, "overall")

# Per-temperature
per_temp = []
for t, g in df.groupby("temperature", dropna=False):
    per_temp.append(summary_block(g, f"temp={t}"))
per_temp = pd.concat(per_temp, ignore_index=True)

# Per-feature (e.g., reliability:p6_long, vision2plan)
per_feat = []
for f, g in df.groupby("feature", dropna=False):
    per_feat.append(summary_block(g, f"feature={f}"))
per_feat = pd.concat(per_feat, ignore_index=True).sort_values("n", ascending=False)

#  outlier filtering (latency) 
# Define outliers as > Q3 + 3*IQR (very conservative) — adjust if needed
Q1 = df["latency_s"].quantile(0.25)
Q3 = df["latency_s"].quantile(0.75)
IQR = Q3 - Q1
hi  = Q3 + 3*IQR
df_nout = df[df["latency_s"] <= hi].copy()

overall_nout = summary_block(df_nout, f"overall_no_outliers(≤{hi:.2f}s)")
per_temp_nout = []
for t, g in df_nout.groupby("temperature", dropna=False):
    per_temp_nout.append(summary_block(g, f"temp={t}_no_outliers"))
per_temp_nout = pd.concat(per_temp_nout, ignore_index=True)

#save CSVs
all_blocks = pd.concat([overall, per_temp, per_feat], ignore_index=True)
all_blocks.to_csv(OUT_DIR / "metrics_summary.csv", index=False)

all_blocks_nout = pd.concat([overall_nout, per_temp_nout], ignore_index=True)
all_blocks_nout.to_csv(OUT_DIR / "metrics_summary_outlier_filtered.csv", index=False)

# print console recap 
print("\n=== OVERALL ===")
print(overall.to_string(index=False))
print("\n=== OVERALL (no outliers) ===")
print(overall_nout.to_string(index=False))

print("\n=== PER TEMPERATURE ===")
print(per_temp.to_string(index=False))

# Nice quick percentiles for latency & cost
print("\nLatency percentiles:", percentiles(df["latency_s"]))
print("Cost percentiles (GBP):", percentiles(df["est_cost"]))

# simple plots 
plt.figure()
df["latency_s"].plot(kind="hist", bins=40)
plt.xlabel("Latency (s)")
plt.ylabel("Count")
plt.title("Latency distribution")
plt.savefig(OUT_DIR / "latency_hist.png", bbox_inches="tight", dpi=160)

plt.figure()
df["est_cost"].plot(kind="hist", bins=40)
plt.xlabel("Cost per call (GBP)")
plt.ylabel("Count")
plt.title("Cost per call distribution")
plt.savefig(OUT_DIR / "cost_hist.png", bbox_inches="tight", dpi=160)

#  daily cost projection 
daily_calls = USERS_PER_DAY * CALLS_PER_USER
avg_cost = df["est_cost"].mean()
daily_cost = daily_calls * avg_cost if not math.isnan(avg_cost) else None

proj_path = OUT_DIR / "daily_cost_projection.txt"
with proj_path.open("w", encoding="utf-8") as f:
    f.write(
        f"Users/day = {USERS_PER_DAY}\n"
        f"Calls per user/day = {CALLS_PER_USER}\n"
        f"Average cost per call (GBP) = {avg_cost:.6f}\n"
        f"Estimated daily cost (GBP) = {daily_cost:.2f}\n"
    )

print(f"\nSaved: {OUT_DIR/'metrics_summary.csv'}")
print(f"Saved: {OUT_DIR/'metrics_summary_outlier_filtered.csv'}")
print(f"Saved: {OUT_DIR/'latency_hist.png'}")
print(f"Saved: {OUT_DIR/'cost_hist.png'}")
print(f"Saved: {proj_path}")