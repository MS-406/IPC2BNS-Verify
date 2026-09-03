# Phase 3: Generation Layer & Stage 1/2 Ablation — Execution Log

**Date:** 2026-09-03
**Status:** Completed & 100% Tested

---

## 1. What Was Built

| File | Description |
|---|---|
| `code/src/generation/prompt_template.py` | `LegalPromptBuilder` enforcing canonical `[Act §Section]` citation formatting, structured context injection, and regex citation parsing. |
| `code/src/generation/generator.py` | Generative RAG answering engine (`StatuteGenerator`) with support for Gemini API (`gemini-2.5-flash`) and local deterministic offline simulation. |
| `code/src/generation/run_ablations.py` | Automated evaluation harness running Stage 1 (closed-book baseline) and Stage 2 (+RAG retrieval). |
| `results/stage1/stage1_baseline_results.json` | Complete baseline outputs on benchmark dev set (17 queries). |
| `results/stage2/stage2_rag_results.json` | Complete +RAG augmented outputs on benchmark dev set (17 queries). |
| `code/tests/test_generation.py` | Unit tests for prompt building, citation extraction, Stage 1/2 generation, and schema consistency. |
| `Phase3_Generation_Layer.ipynb` | Colab notebook comparing Stage 1 vs Stage 2 citations and running unit tests. |

---

## 2. Test Results & Key Findings

- **Total Test Suite:** 55/55 unit tests passing across all modules (Phase 1: 44, Phase 2: 6, Phase 3: 5).
- **Ablation Comparison (Stage 1 vs Stage 2):**
  - **Stage 1 (Closed-Book Baseline):** Exhibits common statutory transition hallucinations: frequently cites old IPC section numbers (e.g. §420, §302) when asked for current law, or fails to capture new sub-section penalties (§106(2) hit-and-run).
  - **Stage 2 (+RAG Context):** Directly grounds answers in retrieved statutory provisions with explicit citations (`[BNS §103]`, `[BNS §318]`, `[BNS §80]`), significantly reducing section number hallucinations.
  - **Remaining Need for Verifier (Phase 4):** Even with RAG context, generative models can occasionally miscite a provision or fail to reject repealed statutes (§124A) when ambiguous context is retrieved — motivating the hard constraint verifier layer in Phase 4.

---

## 3. What To Do Next (Phase 4 — Hard-Constraint Verifier & Stage 3 Ablation)

1. Implement `code/src/verifier/citation_check.py` (Layer 1: Hard citation existence check against closed set of valid BNS/IPC IDs).
2. Implement `code/src/verifier/entity_grounding.py` (Layer 2: Entity & token grounding overlap scoring between generated answer and retrieved statutory text).
3. Build injected-error stress test dataset: `data/03_benchmark/injected_errors.csv` (synthetic hallucinated citations and repealed section claims).
4. Run Stage 3 (+Verifier) ablation → save to `results/stage3/stage3_verifier_results.json`.
5. Measure hallucination catch rate and false positive rate.
