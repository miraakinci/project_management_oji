# pm_eval/run_perf_suite.py  — JSON validity & performance runner

from pathlib import Path
import json

from pm_eval.perf import call_with_timing, summarise_latencies, API_LOG
from pm_eval.json_checks import is_well_formed, validate_against_schema  # <— use JSON checks

# Test prompts (add more to broaden coverage)
PROMPTS = [
    "Transition from a manual to fully automated product launch process.",
    "Consolidate disparate data sources into a single source of truth.",
    "Transition the client service team away from administrative activities towards sales."
]

def run_trials(prompts, n_per_prompt=5, *, model="gpt-4", temperature=0.2, use_schema=True):
    """
    Runs multiple trials and records latency + JSON validity.
    If use_schema is True, validate_against_schema() is called (no external file needed).
    """
    records = []
    for p in prompts:
        for _ in range(n_per_prompt):
            json_text, rec = call_with_timing(p, model=model, temperature=temperature)
            # JSON well-formed?
            rec["ok"] = is_well_formed(json_text)
            # JSON schema/structure check (lightweight; see json_checks.py)
            if use_schema:
                try:
                    rec["schema_ok"] = validate_against_schema(json_text)
                except Exception:
                    rec["schema_ok"] = False
            records.append(rec)

    # Append to the private JSONL log
    with Path(API_LOG).open("a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return records

def success_rates(records):
    n = len(records) or 1
    wf = sum(1 for r in records if r.get("ok"))
    sv = sum(1 for r in records if r.get("schema_ok"))
    return {
        "n": n,
        "well_formed_pct": round(100 * wf / n, 1),
        "schema_valid_pct": round(100 * sv / n, 1),
    }

if __name__ == "__main__":
    recs = run_trials(
        PROMPTS,
        n_per_prompt=5,
        model="gpt-4o",     
        temperature=0.2,
        use_schema=True
    )
    print("Latency:", summarise_latencies(recs))
    print("JSON success:", success_rates(recs))
    mean_cost = round(sum(r.get("est_cost", 0) for r in recs) / max(1, len(recs)), 6)
    print("Mean estimated cost per call:", mean_cost)
