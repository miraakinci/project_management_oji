# pm_eval/perf.py — JSON evaluation (real or mock) with GBP costing + debug
# Compatible with openai >= 1.x (tested with 1.97.1)

import os
import time
import json
import statistics
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI


# ---- load .env (.env can live in cwd or project root) ----
# Try auto-discovery first (current dir or parents)
load_dotenv(find_dotenv(), override=True)

# Fallback: also try ../.env (project root) if needed
if not os.getenv("OPENAI_API_KEY"):
    alt = Path(__file__).resolve().parents[1] / ".env"
    if alt.exists():
        load_dotenv(alt, override=True)

# Core config (with sensible defaults)
USE_MOCK   = os.getenv("USE_MOCK", "false").lower() == "true"
EVAL_MODEL = os.getenv("EVAL_MODEL", "gpt-4o")
API_KEY    = os.getenv("OPENAI_API_KEY")  # required for real runs

# Fail fast if we’re not mocking and the key is missing
if not USE_MOCK and not API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Create a .env with OPENAI_API_KEY=sk-... "
        "or export it in your shell, or set USE_MOCK=true."
    )

# Create OpenAI client only for real runs (OpenAI 1.x syntax)
client = OpenAI(api_key=API_KEY) if not USE_MOCK else None


#write logs OUTSIDE the repo 
def _default_log_dir() -> Path:
    base = os.getenv("EVAL_OUTPUT_DIR", str(Path.home() / "pm_eval_private" / "logs"))
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p

LOG_DIR = _default_log_dir()
API_LOG = LOG_DIR / "api_metrics.jsonl"


# 1) LLM call (real or mock), returning JSON text 
def _mock_llm_call(prompt: str):
    """
    Return a pre-saved JSON response from pm_eval/mocks/sample_responses.json.
    """
    mock_path = Path(__file__).parent / "mocks" / "sample_responses.json"
    if not mock_path.exists():
        raise RuntimeError(f"Mock file not found: {mock_path}")

    data = json.loads(mock_path.read_text(encoding="utf-8"))
    js = data.get(prompt) or data.get("default")
    if js is None:
        js = json.dumps({
            "vision": "Mock vision",
            "outcomes": ["Baseline"],
            "benefits": ["Baseline"],
            "deliverables": ["Baseline"],
            "tasks": ["Baseline task"]
        })
    time.sleep(0.2)  # simulate latency

    # Non-trivial usage numbers so cost isn’t 0 in mock runs
    usage = {"prompt_tokens": 700, "completion_tokens": 2200}
    return {"text": js, "usage": usage}


def _real_llm_call(prompt: str, *, model: str = "gpt-4o", temperature: float = 0.2):
    """
    Real OpenAI call for openai>=1.x using Chat Completions.
    Returns ONLY JSON (no prose, no code fences).
    """
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": (
                    "Return ONLY valid JSON (no surrounding text, no backticks). "
                    "Required keys: vision (string), outcomes (array of strings), "
                    "benefits (array of strings), deliverables (array of strings), "
                    "tasks (array of strings). No extra keys, no comments."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    text = resp.choices[0].message.content or ""
    # In 1.x, usage is available as attributes; keep fallbacks just in case.
    usage = {}
    if getattr(resp, "usage", None):
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
            # Some endpoints use input/output tokens; keep optional fallbacks:
            "input_tokens": getattr(resp.usage, "input_tokens", None),
            "output_tokens": getattr(resp.usage, "output_tokens", None),
        }
    return {"text": text, "usage": usage}


def llm_call(prompt: str, *, model: str = None, temperature: float = 0.2):
    model = model or EVAL_MODEL
    return _mock_llm_call(prompt) if USE_MOCK else _real_llm_call(
        prompt, model=model, temperature=temperature
    )


#  2) COSTING (per 1K tokens) in GBP 
# From your screenshot (Standard pricing, gpt-4o): $2.50 / $10.00 per 1M.
# Using ~0.79 GBP/USD → £1.98 / £7.90 per 1M → divide by 1000 for per 1K.
PRICES_PER_1K_GBP = {
    "gpt-4o": {"input": 0.00198, "output": 0.00790},  # £ per 1K tokens
    # Add others here if you ever use them:
    # "gpt-4.1": {"input": ..., "output": ...},
    # "gpt-4":   {"input": ..., "output": ...},
}

def estimate_cost_gbp(usage: dict, model: str) -> float:
    price = PRICES_PER_1K_GBP.get(model)
    if not price:
        return 0.0
    # Prefer prompt/completion; fall back to input/output if present
    tin  = usage.get("prompt_tokens")     or usage.get("input_tokens")      or 0
    tout = usage.get("completion_tokens") or usage.get("output_tokens")     or 0
    return (tin / 1000.0) * price["input"] + (tout / 1000.0) * price["output"]


#  3) timed call + log 
def call_with_timing(prompt: str, *, model=None, temperature=0.2, feature="vision2plan"):
    model = model or EVAL_MODEL
    t0 = time.perf_counter()
    resp = llm_call(prompt, model=model, temperature=temperature)
    latency = round(time.perf_counter() - t0, 3)

    text  = resp.get("text", "")
    usage = resp.get("usage", {}) or {}
    cost_gbp = round(estimate_cost_gbp(usage, model), 6)

    rec = {
        "ts": datetime.utcnow().isoformat(),
        "feature": feature,
        "model": model,
        "temperature": temperature,
        "latency_s": latency,
        "tokens_in":  usage.get("prompt_tokens")     or usage.get("input_tokens"),
        "tokens_out": usage.get("completion_tokens") or usage.get("output_tokens"),
        "est_cost": cost_gbp,     # in GBP
        "currency": "GBP",
        "raw_len": len(text),
        # helpful debug flags
        "pricing_model_key": model,
        "pricing_applied": model in PRICES_PER_1K_GBP,
        "used_mock": USE_MOCK,
        # filled by JSON checks in runner:
        "ok": None,
        "schema_ok": None,
    }
    with API_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return text, rec


#  4) latency summary
def summarise_latencies(records):
    xs = [r["latency_s"] for r in records if r.get("latency_s") is not None]
    if not xs:
        return {}
    xs_sorted = sorted(xs)
    p95_idx = int(0.95 * (len(xs_sorted) - 1))
    return {
        "n": len(xs),
        "mean":   round(statistics.fmean(xs), 3),
        "median": round(statistics.median(xs), 3),
        "p95":    round(xs_sorted[p95_idx], 3),
        "max":    round(max(xs), 3),
    }
