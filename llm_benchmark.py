import os
import time
import json
import statistics
import csv
from dotenv import load_dotenv
from openai import OpenAI
from difflib import SequenceMatcher


# Models to benchmark (exact names from OpenAI)
MODELS = [
    {"provider": "openai", "name": "gpt-4.1", "input_cost": 5.0, "output_cost": 15.0},
    {"provider": "openai", "name": "gpt-4o", "input_cost": 5.0, "output_cost": 15.0},
    {"provider": "openai", "name": "gpt-4o-mini", "input_cost": 0.15, "output_cost": 0.60},
]

# Test prompt
PROMPT = {"role": "user", "content": "Return JSON with {\"ok\": true}"}

# Number of repetitions
N_RUNS = 10

# Output files
RAW_FILE = "benchmarks/benchmark_raw_results.csv"
SUMMARY_FILE = "benchmarks/benchmark_summary_stats.csv"
FAILURE_FILE = "benchmarks/benchmark_failures.json"

#os.makedirs("benchmarks", exist_ok=True)


def run_openai(model_name, client):
    """Run one request against OpenAI"""
    try:
        start = time.time()
        r = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content"
            "": "Return ONLY JSON."}, PROMPT],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        latency = time.time() - start
        content = r.choices[0].message.content
        tokens_in = r.usage.prompt_tokens
        tokens_out = r.usage.completion_tokens

        # Validate JSON
        try:
            json.loads(content)
            valid = True
        except:
            valid = False

        return {
            "success": valid,
            "latency": latency,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "content": content
        }
    except Exception as e:
        return {"success": False, "latency": None, "tokens_in": 0, "tokens_out": 0, "content": str(e)}


def jaccard_similarity(a, b):
    set_a, set_b = set(a.split()), set(b.split())
    return len(set_a & set_b) / len(set_a | set_b) if set_a | set_b else 1


def levenshtein_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def benchmark(client):
    raw_results = []
    failure_logs = []

    for m in MODELS:
        model_name = m["name"]
        print(f"\n=== Running {model_name} for {N_RUNS} runs ===")

        for i in range(N_RUNS):
            res = run_openai(model_name, client)
            res["model"] = model_name
            res["run"] = i + 1
            raw_results.append(res)

            if not res["success"]:
                failure_logs.append(res)

    # Save raw results
    with open(RAW_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=raw_results[0].keys())
        writer.writeheader()
        writer.writerows(raw_results)

    # Save failures
    with open(FAILURE_FILE, "w") as f:
        json.dump(failure_logs, f, indent=2)

    # Compute summary stats
    summary = []
    for m in MODELS:
        model_results = [r for r in raw_results if r["model"] == m["name"]]
        latencies = [r["latency"] for r in model_results if r["latency"] is not None]
        tokens_in = [r["tokens_in"] for r in model_results]
        tokens_out = [r["tokens_out"] for r in model_results]
        successes = [r["success"] for r in model_results]
        outputs = [r["content"] for r in model_results if r["success"]]

        if latencies:
            avg_latency = statistics.mean(latencies)
            std_latency = statistics.stdev(latencies) if len(latencies) > 1 else 0
        else:
            avg_latency = std_latency = 0

        avg_in = statistics.mean(tokens_in) if tokens_in else 0
        avg_out = statistics.mean(tokens_out) if tokens_out else 0
        success_rate = sum(successes) / len(successes) if successes else 0

        # Cost per call (USD)
        avg_cost = ((avg_in * m["input_cost"]) + (avg_out * m["output_cost"])) / 1_000_000

        # Diversity metrics
        if len(outputs) > 1:
            jaccards, levenshteins = [], []
            for i in range(len(outputs)):
                for j in range(i + 1, len(outputs)):
                    jaccards.append(jaccard_similarity(outputs[i], outputs[j]))
                    levenshteins.append(levenshtein_ratio(outputs[i], outputs[j]))
            avg_jaccard = statistics.mean(jaccards)
            avg_levenshtein = statistics.mean(levenshteins)
        else:
            avg_jaccard = avg_levenshtein = 1

        summary.append({
            "model": m["name"],
            "runs": len(model_results),
            "success_rate": round(success_rate, 3),
            "avg_latency": round(avg_latency, 3),
            "std_latency": round(std_latency, 3),
            "avg_tokens_in": round(avg_in, 1),
            "avg_tokens_out": round(avg_out, 1),
            "avg_cost_per_call_usd": round(avg_cost, 6),
            "diversity_jaccard": round(avg_jaccard, 3),
            "diversity_levenshtein": round(avg_levenshtein, 3)
        })

    # Save summary
    with open(SUMMARY_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    print(f"\n[OK] Saved {RAW_FILE}, {SUMMARY_FILE}, {FAILURE_FILE}")


def main():
    load_dotenv()
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    os.makedirs("benchmarks", exist_ok=True)
    benchmark(openai_client)


if __name__ == "__main__":
    main()


"""
=== Script Explanation ===
This script benchmarks multiple OpenAI models (gpt-4.1, gpt-4o, gpt-4o-mini).
It runs each model N times with the same JSON-returning prompt and collects:

- Success rate (valid JSON responses)
- Latency (average and std deviation)
- Token usage (input/output)
- Cost per call (based on pricing per million tokens)
- Output diversity (Jaccard and Levenshtein similarity)

Outputs:
1. benchmark_raw_results.csv → all raw run data
2. benchmark_summary_stats.csv → aggregated performance summary
3. benchmark_failures.json → any failed or invalid responses
"""
