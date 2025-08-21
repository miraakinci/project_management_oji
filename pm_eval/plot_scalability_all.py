# pm_eval/plot_scalability_all.py
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# load CSV next to this script 
here = Path(__file__).parent
csv_path = here / "scalability_results.csv"
df = pd.read_csv(csv_path).sort_values("ConcurrentUsers")

# 1) Avg Latency vs Concurrent Users
plt.figure()
plt.plot(df["ConcurrentUsers"], df["AvgLatency_s"], marker="o")
plt.xlabel("Concurrent Users")
plt.ylabel("Average Latency (s)")
plt.title("Scalability Test - Average Latency vs Concurrency")
plt.grid(True)
plt.savefig(here / "scalability_avg_latency.png", bbox_inches="tight", dpi=160)

# 2) P95 Latency vs Concurrent Users
plt.figure()
plt.plot(df["ConcurrentUsers"], df["P95Latency_s"], marker="o")
plt.xlabel("Concurrent Users")
plt.ylabel("P95 Latency (s)")
plt.title("Scalability Test - P95 Latency vs Concurrency")
plt.grid(True)
plt.savefig(here / "scalability_p95_latency.png", bbox_inches="tight", dpi=160)

# 3) Failure Rate vs Concurrent Users
plt.figure()
plt.bar(df["ConcurrentUsers"], df["FailureRate_%"])
plt.xlabel("Concurrent Users")
plt.ylabel("Failure Rate (%)")
plt.title("Scalability Test - Failure Rate vs Concurrency")
plt.savefig(here / "scalability_failure_rate.png", bbox_inches="tight", dpi=160)

print("Saved plots:")
print(" - scalability_avg_latency.png")
print(" - scalability_p95_latency.png")
print(" - scalability_failure_rate.png")

