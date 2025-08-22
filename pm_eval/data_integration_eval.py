import openai
import time, csv, json
from pathlib import Path


openai.api_key = ""   

BASE_DIR = Path(__file__).parent
OUTPUT_FILE = BASE_DIR / "integration_eval_report.csv"

SAMPLE_QUERIES = [
    "Digital transformation project",
    "New hospital IT system rollout",
    "Offshore wind farm construction"
]

SAMPLE_PROJECTS = [
    "Sample project on digital customer service transformation",
    "Sample project on supply chain optimization",
    "Sample project on renewable energy transition",
    "Sample project on AI-augmented project management"
]

REQUIRED_TAGS = ["Vision", "Outcomes", "Benefits", "Deliverables", "Tasks"]

def check_completeness(doc: dict) -> bool:
    return all(tag in doc and doc[tag] not in ("", [], None) for tag in REQUIRED_TAGS)

def rag_generate(query: str):
    retrieved = max(
        SAMPLE_PROJECTS,
        key=lambda s: len(set(query.lower().split()) & set(s.lower().split()))
    )

    t0 = time.time()
    prompt = (
        "You are a project management assistant.\n"
        f"User query: {query}\n"
        f"Retrieved project context: {retrieved}\n\n"
        "Return a STRICT JSON object with keys exactly:\n"
        'Vision, Outcomes, Benefits, Deliverables, Tasks.\n'
        "Each key must be present. Outcomes/Benefits/Deliverables/Tasks can be lists."
    )

    resp = openai.ChatCompletion.create(
        model="gpt-4",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
    )
    latency = time.time() - t0

    content = resp["choices"][0]["message"]["content"]
    try:
        start = content.find("{")
        end = content.rfind("}")
        doc = json.loads(content[start:end+1])
    except Exception:
        doc = {}

    return retrieved, latency, doc, content[:120]

def run_eval():
    rows = []
    for q in SAMPLE_QUERIES:
        retrieved, latency, doc, snippet = rag_generate(q)
        complete = check_completeness(doc)
        relevance_score = 4  # placeholder
        rows.append([q, retrieved, round(latency, 2), relevance_score, "YES" if complete else "NO", snippet])

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "retrieved", "retrieval_time_s", "relevance_score", "all_tags_present", "snippet"])
        w.writerows(rows)

    print(f"Saved → {OUTPUT_FILE}")

if __name__ == "__main__":
    run_eval()

