# pm_eval/scalability_test.py
import os, time, csv, asyncio, statistics as stats
import aiohttp

# CONFIG 
API_KEY = ""
URL = "https://api.openai.com/v1/chat/completions"

sample_payload = {
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "Generate a concise PRINCE2 style project outline from this vision: ..."}
    ],
    "temperature": 0.2,
}
CONCURRENCY_LEVELS = [5, 10, 20, 50]
REPEATS_PER_LEVEL = 3
REQUEST_TIMEOUT_S = 60
CSV_NAME = "scalability_results.csv"


headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

async def call_api(session, payload):
    t0 = time.time()
    try:
        async with session.post(URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_S) as resp:
            _ = await resp.json()
            ok = 200 <= resp.status < 300
    except Exception:
        ok = False
    return (time.time() - t0, ok)

async def run_batch(concurrency, payload):
    async with aiohttp.ClientSession() as session:
        tasks = [call_api(session, payload) for _ in range(concurrency)]
        return await asyncio.gather(*tasks)

def p95(values):
    if not values:
        return float("nan")
    values = sorted(values)
    k = int(round(0.95 * (len(values) - 1)))
    return values[k]

def main():
    rows = [("ConcurrentUsers", "TotalRequests", "AvgLatency_s", "P95Latency_s", "FailureRate_%")]
    for n in CONCURRENCY_LEVELS:
        all_lat, all_ok = [], []
        for _ in range(REPEATS_PER_LEVEL):
            lat_ok = asyncio.run(run_batch(n, sample_payload))
            all_lat += [x[0] for x in lat_ok]
            all_ok  += [x[1] for x in lat_ok]
        avg_lat = stats.mean(all_lat) if all_lat else float("nan")
        p95_lat = p95(all_lat)
        failure = 100.0 * (1 - (sum(all_ok) / len(all_ok))) if all_ok else float("nan")
        print(f"[n={n:>3}] avg={avg_lat:.2f}s  p95={p95_lat:.2f}s  fail={failure:.1f}%")
        rows.append((n, len(all_lat), round(avg_lat, 4), round(p95_lat, 4), round(failure, 2)))

    with open(CSV_NAME, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"\nSaved CSV -> {CSV_NAME}")

if __name__ == "__main__":
    main()

