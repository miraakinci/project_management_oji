# pm_eval/run_reliability.py
import os, json, itertools, csv
from pathlib import Path
from statistics import mean, pstdev
from datetime import datetime

from pm_eval.perf import call_with_timing, LOG_DIR, EVAL_MODEL  # uses your existing module

# Prompts 
CORE_PROMPTS = {
    "p1_normal": "Transition from a manual to fully automated product launch process.",
    "p2_normal": "Transition the client service team away from administrative activities towards generating sales.",
    "p3_normal": "Consolidate disparate data sources into a single source of truth."
}

EDGE_PROMPTS = {
    "p4_short": "Automate launch.",
    "p5_vague": "Make things better for sales.",
    # Provide your own long version here if you want a very long stress test
    "p6_long": (
        "Our company operates across six regions with fragmented processes for product ideation, "
        "market research, regulatory review, and coordinated release activities. We want to introduce "
        "a unified operating model that standardizes gates, artifacts, and responsibilities across PM, "
        "Engineering, QA, Legal, and Sales Enablement. The new process must integrate with our data "
        "warehouse, automate compliance evidence capture, and support parallel pilot launches while "
        "maintaining audit trails and risk sign-offs. Success criteria include shorter cycle time, "
        "fewer defects, and better traceability."
    ),
    "p7_conflict": "Cut scope but deliver twice as many features next sprint."
}

TEMPS = [0.0, 0.2, 0.7]  # sampling settings to test
REPEATS = 5              # runs per (prompt, temperature)

# ---------- Helpers ----------
def _try_parse_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None

def _norm_text(s: str) -> set:
    # Lowercase, alnum-only tokens for simple Jaccard
    import re
    toks = re.findall(r"[a-z0-9]+", (s or "").lower())
    return set(toks)

def _norm_items(xs):
    out = set()
    for x in xs or []:
        if isinstance(x, str):
            out.add(" ".join(_norm_text(x)))
        else:
            out.add(str(x))
    return out

def jaccard(a: set, b: set) -> float:
    if not a and not b: return 1.0
    if not a or not b:  return 0.0
    return len(a & b) / len(a | b)

def pairwise_stats(values):
    """Return mean, std (population), min, max for a list; handle small samples."""
    if not values: return {"mean": None, "std": None, "min": None, "max": None}
    m = mean(values)
    sd = pstdev(values) if len(values) > 1 else 0.0
    return {"mean": m, "std": sd, "min": min(values), "max": max(values)}

def compare_batch(json_objs):
    """
    Compute similarity across a batch of parsed JSON results from identical prompt runs.
    Returns metrics for: vision, outcomes, benefits, deliverables, tasks.
    """
    vis_sims, out_sims, ben_sims, deliv_sims, task_sims = [], [], [], [], []

    for a, b in itertools.combinations(json_objs, 2):
        if not a or not b:  # skip invalid pairs
            continue

        vis_a, vis_b = _norm_text(a.get("vision", "")), _norm_text(b.get("vision", ""))
        outs_a, outs_b = _norm_items(a.get("outcomes")), _norm_items(b.get("outcomes"))
        bens_a, bens_b = _norm_items(a.get("benefits")), _norm_items(b.get("benefits"))
        dels_a, dels_b = _norm_items(a.get("deliverables")), _norm_items(b.get("deliverables"))
        tasks_a, tasks_b = _norm_items(a.get("tasks")), _norm_items(b.get("tasks"))

        vis_sims.append(jaccard(vis_a, vis_b))
        out_sims.append(jaccard(outs_a, outs_b))
        ben_sims.append(jaccard(bens_a, bens_b))
        deliv_sims.append(jaccard(dels_a, dels_b))
        task_sims.append(jaccard(tasks_a, tasks_b))

    return {
        "vision":  pairwise_stats(vis_sims),
        "outcomes": pairwise_stats(out_sims),
        "benefits": pairwise_stats(ben_sims),
        "deliverables": pairwise_stats(deliv_sims),
        "tasks": pairwise_stats(task_sims),
        "pairs": len(vis_sims)
    }

# Runner
def run_suite():
    outputs_dir = Path(os.getenv("EVAL_OUTPUT_DIR", LOG_DIR)) / "reliability"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # CSV summary file
    csv_path = outputs_dir / f"reliability_summary_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
    fieldnames = [
        "prompt_id", "category", "temperature", "model",
        "n_calls", "json_ok_rate", "schema_ok_rate",
        "lat_mean", "lat_p95", "lat_max",
        "tokens_in_mean", "tokens_out_mean", "est_cost_mean_gbp",
        "pairwise_pairs",
        "sim_vision_mean", "sim_vision_std",
        "sim_outcomes_mean", "sim_outcomes_std",
        "sim_benefits_mean", "sim_benefits_std",
        "sim_deliverables_mean", "sim_deliverables_std",
        "sim_tasks_mean", "sim_tasks_std",
    ]
    writer = csv.DictWriter(csv_path.open("w", newline="", encoding="utf-8"), fieldnames=fieldnames)
    writer.writeheader()

    all_prompts = {**{k: ("core", v) for k, v in CORE_PROMPTS.items()},
                   **{k: ("edge", v) for k, v in EDGE_PROMPTS.items()}}

    for temp in TEMPS:
        for pid, (cat, prompt) in all_prompts.items():
            records, parsed = [], []

            # repeated calls
            for _ in range(REPEATS):
                text, rec = call_with_timing(prompt, model=EVAL_MODEL, temperature=temp, feature=f"reliability:{pid}")
                # try parse & mark ok flags (don’t fail the run if parse fails)
                jo = _try_parse_json(text)
                rec["ok"] = jo is not None
                rec["schema_ok"] = (jo is not None)  # treat JSON well-formed as schema_ok if you don’t run explicit schema
                records.append(rec)
                parsed.append(jo)

            # latency stats
            lats = [r["latency_s"] for r in records if r.get("latency_s") is not None]
            lats_sorted = sorted(lats)
            p95 = lats_sorted[int(0.95 * (len(lats_sorted) - 1))] if lats_sorted else None

            # token & cost means
            ti = [r.get("tokens_in")  or 0 for r in records]
            to = [r.get("tokens_out") or 0 for r in records]
            costs = [r.get("est_cost") or 0.0 for r in records]

            # json & schema rates
            json_ok = sum(1 for r in records if r.get("ok")) / max(1, len(records))
            sch_ok  = sum(1 for r in records if r.get("schema_ok")) / max(1, len(records))

            # pairwise content similarity
            sims = compare_batch(parsed)

            writer.writerow({
                "prompt_id": pid,
                "category": cat,
                "temperature": temp,
                "model": EVAL_MODEL,
                "n_calls": len(records),
                "json_ok_rate": round(json_ok, 3),
                "schema_ok_rate": round(sch_ok, 3),
                "lat_mean": round(mean(lats), 3) if lats else None,
                "lat_p95": round(p95, 3) if p95 is not None else None,
                "lat_max": round(max(lats), 3) if lats else None,
                "tokens_in_mean": round(mean(ti), 1) if ti else None,
                "tokens_out_mean": round(mean(to), 1) if to else None,
                "est_cost_mean_gbp": round(mean(costs), 6) if costs else None,
                "pairwise_pairs": sims["pairs"],
                "sim_vision_mean": round((sims["vision"]["mean"] or 0), 3) if sims["pairs"] else None,
                "sim_vision_std":  round((sims["vision"]["std"]  or 0), 3) if sims["pairs"] else None,
                "sim_outcomes_mean": round((sims["outcomes"]["mean"] or 0), 3) if sims["pairs"] else None,
                "sim_outcomes_std":  round((sims["outcomes"]["std"]  or 0), 3) if sims["pairs"] else None,
                "sim_benefits_mean": round((sims["benefits"]["mean"] or 0), 3) if sims["pairs"] else None,
                "sim_benefits_std":  round((sims["benefits"]["std"]  or 0), 3) if sims["pairs"] else None,
                "sim_deliverables_mean": round((sims["deliverables"]["mean"] or 0), 3) if sims["pairs"] else None,
                "sim_deliverables_std":  round((sims["deliverables"]["std"]  or 0), 3) if sims["pairs"] else None,
                "sim_tasks_mean": round((sims["tasks"]["mean"] or 0), 3) if sims["pairs"] else None,
                "sim_tasks_std":  round((sims["tasks"]["std"]  or 0), 3) if sims["pairs"] else None,
            })

            # dump raw per-run JSON and metrics too (handy for appendix)
            (outputs_dir / f"{pid}_temp{temp}_runs.json").write_text(
                json.dumps({"records": records}, indent=2), encoding="utf-8"
            )

    print(f"Reliability summary written to: {csv_path}")

if __name__ == "__main__":
    run_suite()
