# pm_eval/accuracy_tests.py
from __future__ import annotations
from pathlib import Path
import json, csv
from difflib import SequenceMatcher

# ========= CONFIG =========
BASE_DIR = Path(__file__).parent

OUTPUT_DIR = BASE_DIR / "outputs"                 
PROPAGATION_PAIRS_CSV = BASE_DIR / "propagation_pairs.csv" 

REQUIRED_TAGS = ["Vision", "Outcomes", "Benefits", "Deliverables", "Tasks"]

# Heuristic similarity thresholds
VISION_CHANGED_SIM_TH       = 0.80
DOWNSTREAM_CHANGED_SIM_TH   = 0.95
TASKS_CHANGED_SIM_TH        = 0.85
DELIVERABLES_CHANGED_SIM_TH = 0.95


# ---------- helpers ----------
def read_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def textify(x) -> str:
    if x is None: return ""
    if isinstance(x, str): return x
    if isinstance(x, (int, float, bool)): return str(x)
    if isinstance(x, list): return " | ".join(textify(i) for i in x)
    if isinstance(x, dict): return " ; ".join(f"{k}:{textify(v)}" for k, v in sorted(x.items()))
    return str(x)

def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def resolve_existing(path_str: str) -> Path:
    """
    Resolve a CSV path string to an existing file, trying a few sensible bases.
    Returns the first candidate (even if non-existent) for clearer error messages.
    """
    s = (path_str or "").strip()
    p = Path(s)
    candidates = []
    if p.is_absolute():
        candidates = [p]
    else:
        # common cases: relative to pm_eval/, or accidentally prefixed with 'pm_eval/'
        candidates = [BASE_DIR / p, BASE_DIR.parent / p]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # return best guess so caller can show which one failed

# ---------- 8.5.1 Completeness ----------
def check_completeness_one(doc: dict) -> tuple[bool, list[str]]:
    missing = [k for k in REQUIRED_TAGS if k not in doc or doc[k] in (None, "", [])]
    return (len(missing) == 0, missing)

def run_completeness(output_dir: Path) -> dict:
    rows = []
    json_files = sorted(output_dir.glob("*.json"))
    total = len(json_files)
    complete_count = 0

    for jf in json_files:
        try:
            doc = read_json(jf)
        except Exception as e:
            rows.append((jf.name, "ERROR", str(e), ""))
            continue

        ok, missing = check_completeness_one(doc)
        if ok: complete_count += 1
        rows.append((jf.name, "OK" if ok else "MISSING", "" if ok else ",".join(missing), ""))

    completeness_pct = 100.0 * complete_count / total if total else 0.0
    return {
        "total_files": total,
        "complete_count": complete_count,
        "completeness_pct": round(completeness_pct, 2),
        "rows": rows,
    }

# 8.5.2 Forward–Backward Propagation 
def run_propagation(pairs_csv: Path) -> dict:
    """
    Robust CSV reader:
    - utf-8-sig to strip BOM
    - normalize headers/keys to lowercase
    - strip whitespace
    - tolerate 'pm_eval/...' vs './...' relative paths
    - report errors per row instead of crashing
    """
    if not pairs_csv.exists():
        return {"pairs_total": 0, "passed": 0, "passed_pct": 0.0, "detail_rows": []}

    detail_rows = []
    passed = 0
    total = 0

    with open(pairs_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        # Normalize headers -> lowercase (handles 'ID' vs 'id', BOM, spaces)
        if reader.fieldnames:
            reader.fieldnames = [fn.strip().lstrip("\ufeff").lower() for fn in reader.fieldnames]
        print("Pairs CSV headers (normalized):", reader.fieldnames)

        # Verify we have the expected columns
        needed = {"id", "update_type", "before_path", "after_path"}
        if not reader.fieldnames or not needed.issubset(set(reader.fieldnames)):
            missing = needed - set(reader.fieldnames or [])
            detail_rows.append(("?", "?", "ERROR", f"Missing columns: {', '.join(sorted(missing))}", "", "", ""))
            return {"pairs_total": 0, "passed": 0, "passed_pct": 0.0, "detail_rows": detail_rows}

        for raw_row in reader:
            # Normalize row keys/values
            row = {
                (k.strip().lstrip("\ufeff").lower() if isinstance(k, str) else k):
                (v.strip() if isinstance(v, str) else v)
                for k, v in raw_row.items()
            }

            total += 1
            pid   = row.get("id")
            utype = (row.get("update_type") or "")
            bpath = (row.get("before_path") or "")
            apath = (row.get("after_path") or "")

            before_p = resolve_existing(bpath)
            after_p  = resolve_existing(apath)

            errs = []
            if not pid:   errs.append("missing id")
            if not utype: errs.append("missing update_type")
            if not bpath: errs.append("missing before_path")
            if not apath: errs.append("missing after_path")
            if bpath and not before_p.exists(): errs.append(f"not found: {before_p}")
            if apath and not after_p.exists():  errs.append(f"not found: {after_p}")

            if errs:
                detail_rows.append((pid or "?", utype or "?", "ERROR", "; ".join(errs), "", "", ""))
                continue

            try:
                before = read_json(before_p)
                after  = read_json(after_p)
            except Exception as e:
                detail_rows.append((pid, utype, "ERROR", str(e), "", "", ""))
                continue

            if utype == "vision_edit":
                s_vision   = sim(textify(before.get("Vision")),     textify(after.get("Vision")))
                s_outcomes = sim(textify(before.get("Outcomes")),   textify(after.get("Outcomes")))
                s_benefits = sim(textify(before.get("Benefits")),   textify(after.get("Benefits")))
                materially_changed  = (s_vision < VISION_CHANGED_SIM_TH)
                downstream_changed  = (s_outcomes < DOWNSTREAM_CHANGED_SIM_TH) or (s_benefits < DOWNSTREAM_CHANGED_SIM_TH)
                ok = (not materially_changed) or downstream_changed
                detail_rows.append((pid, utype, "PASS" if ok else "FAIL", "",
                                    f"s_vision={s_vision:.3f}", f"s_outcomes={s_outcomes:.3f}", f"s_benefits={s_benefits:.3f}"))
                if ok: passed += 1

            elif utype == "tasks_edit":
                s_tasks = sim(textify(before.get("Tasks")),        textify(after.get("Tasks")))
                s_deliv = sim(textify(before.get("Deliverables")), textify(after.get("Deliverables")))
                materially_changed = (s_tasks < TASKS_CHANGED_SIM_TH)
                downstream_changed = (s_deliv < DELIVERABLES_CHANGED_SIM_TH)
                ok = (not materially_changed) or downstream_changed
                detail_rows.append((pid, utype, "PASS" if ok else "FAIL", "",
                                    f"s_tasks={s_tasks:.3f}", f"s_deliverables={s_deliv:.3f}", ""))
                if ok: passed += 1

            else:
                detail_rows.append((pid or "?", utype or "?", "ERROR", "unknown update_type", "", "", ""))

    passed_pct = 100.0 * passed / total if total else 0.0
    return {"pairs_total": total, "passed": passed, "passed_pct": round(passed_pct, 2), "detail_rows": detail_rows}

#  write reports 
def save_reports(completeness: dict, propagation: dict) -> None:
    with open(BASE_DIR / "accuracy_completeness_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["file", "status", "missing_tags", "notes"]); w.writerows(completeness["rows"])

    with open(BASE_DIR / "accuracy_propagation_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id", "update_type", "result", "error", "metric_1", "metric_2", "metric_3"])
        w.writerows(propagation["detail_rows"])

    with open(BASE_DIR / "accuracy_summary.txt", "w", encoding="utf-8") as f:
        f.write(
            f"=== 8.5.1 Completeness ===\n"
            f"Files: {completeness['total_files']}\n"
            f"Complete: {completeness['complete_count']}\n"
            f"Completeness %: {completeness['completeness_pct']}\n\n"
            f"=== 8.5.2 Propagation ===\n"
            f"Pairs: {propagation['pairs_total']}\n"
            f"Passed: {propagation['passed']}\n"
            f"Pass %: {propagation['passed_pct']}\n"
        )


def main():
    comp = run_completeness(OUTPUT_DIR)
    prop = run_propagation(PROPAGATION_PAIRS_CSV)
    save_reports(comp, prop)
    print("Saved: accuracy_completeness_report.csv, accuracy_propagation_report.csv, accuracy_summary.txt")

if __name__ == "__main__":
    main()