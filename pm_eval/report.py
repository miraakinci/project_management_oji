import json
from pathlib import Path
import matplotlib.pyplot as plt

def load_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        for line in f: yield json.loads(line)

def plot_latency_hist(records):
    xs = [r["latency_s"] for r in records if r.get("latency_s") is not None]
    if not xs: return
    plt.figure(); plt.hist(xs, bins=20)
    plt.title("Latency distribution"); plt.xlabel("seconds"); plt.ylabel("count")
    plt.show()

def plot_xml_success(records):
    n = len(records); wf = sum(1 for r in records if r.get("ok"))
    plt.figure(); plt.bar(["well-formed","not"], [wf, n-wf])
    plt.title("XML well-formedness"); plt.show()
