"""
compare_stages.py — Inspect and Compare Stage 1 vs Stage 2 Results
"""

import json
import os

root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
s1_path = os.path.join(root, "results/stage1/stage1_baseline_results.json")
s2_path = os.path.join(root, "results/stage2/stage2_rag_results.json")

with open(s1_path, "r", encoding="utf-8") as f:
    s1 = json.load(f)
with open(s2_path, "r", encoding="utf-8") as f:
    s2 = json.load(f)

print("=" * 78)
print("PHASE 3 RESULTS ANALYSIS: STAGE 1 (BASELINE) vs STAGE 2 (+RAG)")
print("=" * 78)
print(f"Total Benchmark Queries Evaluated: {s1['total_queries']}\n")

s1_exact_matches = 0
s2_exact_matches = 0

for i, (r1, r2) in enumerate(zip(s1["results"], s2["results"]), start=1):
    q = r1["query_text"]
    gt = [s.strip().upper() for s in r1["ground_truth_sections"].replace("/", ",").split(",") if s.strip()]
    c1 = [s.strip().upper() for s in r1["cited_sections"]]
    c2 = [s.strip().upper() for s in r2["cited_sections"]]

    hit1 = any(s in gt or any(s in g for g in gt) for s in c1)
    hit2 = any(s in gt or any(s in g for g in gt) for s in c2)

    if hit1:
        s1_exact_matches += 1
    if hit2:
        s2_exact_matches += 1

    status1 = "MATCH" if hit1 else "MISS/OLD_IPC"
    status2 = "MATCH" if hit2 else "MISS"

    print(f"[{i:02d}] Query : {q}")
    print(f"     GT Target  : {gt}")
    print(f"     Stage 1    : {c1} [{status1}]")
    print(f"     Stage 2 RAG: {c2} [{status2}]")
    print("-" * 78)

total = s1["total_queries"]
print("\n" + "=" * 78)
print(f"STAGE 1 Citation Accuracy (Baseline LLM) : {s1_exact_matches}/{total} ({s1_exact_matches/total*100:.1f}%)")
print(f"STAGE 2 Citation Accuracy (+RAG Context) : {s2_exact_matches}/{total} ({s2_exact_matches/total*100:.1f}%)")
print("=" * 78)
