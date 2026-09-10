"""
check_progress.py — Project Work Breakdown Structure (WBS) Tracker

Computes verification progress across all 6 research phases and generates progress reports.
"""

import os
import sys
import argparse
from datetime import datetime


def check_project_progress(root_dir: str, write_report: bool = False):
    tasks = {
        "0. Setup": [
            ("Repo scaffolding + config system", os.path.exists(os.path.join(root_dir, "code/src"))),
            ("India Code raw text downloaded", os.path.exists(os.path.join(root_dir, "data/00_raw/india_code")) or os.path.exists(os.path.join(root_dir, "data/01_cleaned"))),
            ("Concordance source PDF(s) collected", os.path.exists(os.path.join(root_dir, "data/00_raw/concordance_source_pdfs"))),
            ("Data Management Plan written", os.path.exists(os.path.join(root_dir, "docs/IPC2BNS-Verify_Data_Management_Plan.md")) or os.path.exists(os.path.join(root_dir, "README.md")))
        ],
        "1. Mapping Module": [
            ("Ground-truth concordance table finalized", os.path.exists(os.path.join(root_dir, "data/02_ground_truth/concordance_v1.csv"))),
            ("Concordance validation report reviewed", os.path.exists(os.path.join(root_dir, "data/02_ground_truth/validation_report.csv"))),
            ("Deterministic lookup function implemented", os.path.exists(os.path.join(root_dir, "code/src/mapping/lookup.py"))),
            ("Query normalizer implemented", os.path.exists(os.path.join(root_dir, "code/src/mapping/normalizer.py"))),
            ("Mapping module unit tests", os.path.exists(os.path.join(root_dir, "code/tests/test_concordance.py")))
        ],
        "2. Ingestion & Retrieval": [
            ("Section-level chunker implemented", os.path.exists(os.path.join(root_dir, "code/src/ingestion/chunker.py"))),
            ("Cleaned section corpus produced", os.path.exists(os.path.join(root_dir, "data/01_cleaned/ipc_sections.jsonl"))),
            ("Benchmark question set drafted (dev)", os.path.exists(os.path.join(root_dir, "data/03_benchmark/benchmark_dev.csv"))),
            ("Benchmark test set held out", os.path.exists(os.path.join(root_dir, "data/03_benchmark/benchmark_test.csv"))),
            ("Embedding index built", os.path.exists(os.path.join(root_dir, "data/05_embeddings_index/stage2_index"))),
            ("Retrieval precision/recall evaluated", os.path.exists(os.path.join(root_dir, "results/stage2/retrieval_metrics.json")) or os.path.exists(os.path.join(root_dir, "results/retriever_ablation_comparison.json")))
        ],
        "3. Generation": [
            ("Prompt template + citation format defined", os.path.exists(os.path.join(root_dir, "code/src/generation/prompt_template.py"))),
            ("Stage 1 (baseline, no retrieval) run complete", os.path.exists(os.path.join(root_dir, "results/stage1/stage1_baseline_results.json"))),
            ("Stage 2 (+RAG) run complete", os.path.exists(os.path.join(root_dir, "results/stage2/stage2_rag_results.json")))
        ],
        "4. Verifier": [
            ("Layer 1 hard citation-existence check implemented", os.path.exists(os.path.join(root_dir, "code/src/verifier/citation_check.py"))),
            ("Layer 2 entity-grounding check implemented", os.path.exists(os.path.join(root_dir, "code/src/verifier/entity_grounding.py"))),
            ("Injected-error test set built", os.path.exists(os.path.join(root_dir, "data/03_benchmark/injected_errors.csv"))),
            ("Stage 3 (+Verifier) run complete", os.path.exists(os.path.join(root_dir, "results/stage3/stage3_verifier_results.json")))
        ],
        "5. Adaptivity": [
            ("Refresh simulation cases selected", os.path.exists(os.path.join(root_dir, "data/04_refresh_sim/injected_amendment_cases.csv"))),
            ("Pre/post-refresh index snapshots built", os.path.exists(os.path.join(root_dir, "data/05_embeddings_index/stage4_post_refresh_index"))),
            ("Stage 4 (+Verifier+Refresh) run complete", os.path.exists(os.path.join(root_dir, "results/stage4/stage4_refresh_results.json")))
        ],
        "6. Evaluation & Write-up": [
            ("Evaluation harness built", os.path.exists(os.path.join(root_dir, "code/src/eval/harness.py"))),
            ("Human-review calibration done", os.path.exists(os.path.join(root_dir, "results/human_review_calibration.csv"))),
            ("Ablation summary table compiled", os.path.exists(os.path.join(root_dir, "results/ablation_summary_table.csv"))),
            ("Error analysis notes written", os.path.exists(os.path.join(root_dir, "results/error_analysis_notes.md"))),
            ("Plagiarism/originality check run", os.path.exists(os.path.join(root_dir, "report/plagiarism_report.pdf"))),
            ("Final report drafted", os.path.exists(os.path.join(root_dir, "report/final_report.docx")) or os.path.exists(os.path.join(root_dir, "report/final_research_paper.md"))),
            ("Presentation deck built", os.path.exists(os.path.join(root_dir, "report/presentation_deck.pptx")) or os.path.exists(os.path.join(root_dir, "report/presentation_deck.md")))
        ]
    }

    total_tasks = sum(len(v) for v in tasks.values())
    completed_tasks = sum(sum(1 for name, status in v if status) for v in tasks.values())
    overall_pct = int(completed_tasks / total_tasks * 100) if total_tasks else 0

    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    lines = [
        "# Project Progress Report",
        f"**Overall: {completed_tasks}/{total_tasks} tasks complete ({overall_pct}%)**\n",
        f"_Generated: {now_str}_\n"
    ]

    for phase_name, phase_tasks in tasks.items():
        phase_total = len(phase_tasks)
        phase_done = sum(1 for name, status in phase_tasks if status)
        phase_pct = int(phase_done / phase_total * 100) if phase_total else 0
        lines.append(f"## {phase_name} — {phase_done}/{phase_total} ({phase_pct}%)")
        for name, status in phase_tasks:
            mark = "x" if status else " "
            lines.append(f"- [{mark}] {name}")
        lines.append("")

    report_text = "\n".join(lines)
    print(report_text)

    if write_report:
        out_path = os.path.join(root_dir, "results/progress_report.md")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\nSaved report to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Check IPC2BNS-Verify Project Progress")
    parser.add_argument("--root", type=str, default=os.environ.get("IPC2BNS_PROJECT_ROOT", os.getcwd()), help="Project root directory")
    parser.add_argument("--write-report", action="store_true", help="Write report to results/progress_report.md")
    args = parser.parse_args()

    check_project_progress(args.root, write_report=args.write_report)


if __name__ == "__main__":
    main()
