# IPC2BNS-Verify: Task Board / Work Breakdown Structure

This is the master task list, grouped by phase, matching the technical pipeline document. Each task maps to a real file/folder that should exist once it's done — that mapping is what the auto progress-checker script (`check_progress.py`, included alongside this doc) uses to tell you, at a glance, what's actually complete in your project folder, rather than relying on someone remembering to update a checklist by hand.

---

## How Progress Tracking Works

1. Every task below has a **file/folder it produces**, following the structure from the Data Management Plan (`data/`, `code/`, `results/`, `report/`).
2. Run `check_progress.py` from your project root any time:
   ```bash
   python check_progress.py --root /path/to/IPC2BNS-Verify --write-report
   ```
3. It scans the actual folder, checks whether each expected file/folder exists **and is non-empty** (an empty stub folder doesn't count as done), and prints:
   - Per-phase completion count and percentage
   - A markdown checklist (`[x]` / `[ ]`) you can paste straight into a status update
   - Overall project percentage
4. With `--write-report`, it also saves the same output to `results/progress_report.md` with a timestamp, so you have a dated snapshot every time you run it — useful for showing progress over time in a status meeting without manually maintaining a log.
5. **This checks presence, not correctness.** A file existing means that step was attempted and produced output — it does not mean the output is accurate (e.g., the concordance table existing doesn't mean it passed cross-validation). Treat the checker as a completeness tracker, not a quality gate — pair it with the validation steps from the Concordance Runbook and the evaluation metrics for actual quality checks.

---

## Phase 0 — Setup

| Task | Produces |
|---|---|
| Repo scaffolding + config system | `code/src/`, `code/configs/` |
| India Code raw text downloaded | `data/00_raw/india_code/` |
| Concordance source PDF(s) collected | `data/00_raw/concordance_source_pdfs/` |
| Data Management Plan written | `docs/IPC2BNS-Verify_Data_Management_Plan.md` |

## Phase 1 — Mapping Module

| Task | Produces |
|---|---|
| Ground-truth concordance table finalized | `data/02_ground_truth/concordance_v1.csv` |
| Concordance validation report reviewed | `data/02_ground_truth/validation_report.csv` |
| Deterministic lookup function implemented | `code/src/mapping/lookup.py` |
| Query normalizer implemented | `code/src/mapping/normalizer.py` |
| Mapping module unit tests | `code/tests/test_concordance.py` |

## Phase 2 — Ingestion & Retrieval

| Task | Produces |
|---|---|
| Section-level chunker implemented | `code/src/ingestion/chunker.py` |
| Cleaned section corpus produced | `data/01_cleaned/ipc_sections.jsonl`, `bns_sections.jsonl` |
| Benchmark question set drafted (dev) | `data/03_benchmark/benchmark_dev.csv` |
| Benchmark test set held out | `data/03_benchmark/benchmark_test.csv` |
| Embedding index built | `data/05_embeddings_index/stage2_index/` |
| Retrieval precision/recall evaluated | `results/stage2/retrieval_metrics.json` |

## Phase 3 — Generation

| Task | Produces |
|---|---|
| Prompt template + citation format defined | `code/src/generation/prompt_template.py` |
| Stage 1 (baseline, no retrieval) run complete | `results/stage1/stage1_baseline_results.json` |
| Stage 2 (+RAG) run complete | `results/stage2/stage2_rag_results.json` |

## Phase 4 — Verifier (hallucination gate)

| Task | Produces |
|---|---|
| Layer 1 hard citation-existence check implemented | `code/src/verifier/citation_check.py` |
| Layer 2 entity-grounding check implemented | `code/src/verifier/entity_grounding.py` |
| Injected-error test set built | `data/03_benchmark/injected_errors.csv` |
| Stage 3 (+Verifier) run complete | `results/stage3/stage3_verifier_results.json` |

## Phase 5 — Adaptivity / Refresh

| Task | Produces |
|---|---|
| Refresh simulation cases selected | `data/04_refresh_sim/injected_amendment_cases.csv` |
| Pre/post-refresh index snapshots built | `data/05_embeddings_index/stage4_post_refresh_index/` |
| Stage 4 (+Verifier+Refresh) run complete | `results/stage4/stage4_refresh_results.json` |

## Phase 6 — Evaluation & Write-up

| Task | Produces |
|---|---|
| Evaluation harness built | `code/src/eval/harness.py` |
| Human-review calibration done | `results/human_review_calibration.csv` |
| Ablation summary table compiled | `results/ablation_summary_table.csv` |
| Error analysis notes written | `results/error_analysis_notes.md` |
| Plagiarism/originality check run | `report/plagiarism_report.pdf` |
| Final report drafted | `report/final_report.docx` |
| Presentation deck built | `report/presentation_deck.pptx` |

---

## Customizing the Checker

The task list lives as a plain Python list (`TASKS`) at the top of `check_progress.py` — if your actual filenames diverge from this plan (they will, a little, as you build), just edit the `check_paths` for that task. No other code needs to change. Each task is marked done only if **all** listed paths exist and are non-empty, so you can require multiple files (e.g., both `ipc_sections.jsonl` and `bns_sections.jsonl`) for a single task to count as complete.
