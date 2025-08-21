import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

csv_path = Path(__file__).parent / "reliability_summary_20250817T224243Z.csv"
df = pd.read_csv(csv_path)
# ensure temperature is ordered categorical for nice plotting
temps = sorted(df["temperature"].unique())
df["temperature"] = pd.Categorical(df["temperature"], categories=temps, ordered=True)

# build a 2x3 grid of plots 
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
axes = axes.ravel()

# 1–4) Similarity bar charts with error bars if *_std present
sim_specs = [
    ("sim_outcomes_mean",      "sim_outcomes_std",      "Outcomes"),
    ("sim_benefits_mean",      "sim_benefits_std",      "Benefits"),
    ("sim_deliverables_mean",  "sim_deliverables_std",  "Deliverables"),
    ("sim_tasks_mean",         "sim_tasks_std",         "Tasks"),
]
for i, (mean_col, std_col, label) in enumerate(sim_specs):
    ax = axes[i]
    if mean_col not in df.columns:
        ax.set_visible(False)
        continue
    gmean = df.groupby("temperature")[mean_col].mean()
    yerr = None
    if std_col in df.columns:
        gstd = df.groupby("temperature")[std_col].mean()
        yerr = gstd
    gmean.plot(kind="bar", yerr=yerr, ax=ax)
    ax.set_title(f"{label} similarity by Temperature")
    ax.set_ylabel("Jaccard similarity")
    ax.set_xlabel("temperature")
    ax.set_ylim(0, 1)

# 5) JSON schema success rate (line)
ax = axes[4]
if "json_ok_rate" in df.columns:
    json_mean = df.groupby("temperature")["json_ok_rate"].mean()
    json_mean.plot(kind="line", marker="o", ax=ax)
    ax.set_title("JSON Schema Success Rate vs Temperature")
    ax.set_xlabel("temperature")
    ax.set_ylabel("success rate")
    ax.set_ylim(0, 1)
else:
    ax.set_visible(False)

# 6) Latency: mean with error bars up to p95, and overlay p95/max
ax = axes[5]
for col in ["lat_mean", "lat_p95", "lat_max"]:
    if col not in df.columns:
        # If any latency columns are missing, hide plot and skip
        ax.set_visible(False)
        break
else:
    # all three present
    lat_mean = df.set_index("temperature")["lat_mean"].sort_index()
    lat_p95  = df.set_index("temperature")["lat_p95"].sort_index()
    lat_max  = df.set_index("temperature")["lat_max"].sort_index()

    # error bars from mean up to p95 (non-negative)
    yerr = (lat_p95 - lat_mean).clip(lower=0)

    lat_mean.plot(kind="line", marker="o", ax=ax, label="mean")
    ax.errorbar(lat_mean.index.astype(str), lat_mean.values, yerr=yerr.values, fmt="none", capsize=4, color=ax.lines[-1].get_color())
    lat_p95.plot(kind="line", marker="o", ax=ax, label="p95")
    lat_max.plot(kind="line", marker="o", ax=ax, label="max", alpha=0.7)
    ax.set_title("Latency vs Temperature")
    ax.set_xlabel("temperature")
    ax.set_ylabel("seconds")
    ax.legend()

fig.tight_layout()

plt.show()