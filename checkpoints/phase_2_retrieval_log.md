# Phase 2: Ingestion & Retrieval Layer — Execution Log

**Date:** 2026-09-03
**Status:** Completed & 100% Tested

---

## 1. What Was Built

| File | Description |
|---|---|
| `code/src/ingestion/chunker.py` | Section-level chunker creating structured `StatutoryChunk` objects with statutory act, chapter, and temporal validity metadata. |
| `code/src/ingestion/build_cleaned_corpus.py` | Generates 145 IPC and 130 BNS structured JSONL records in `data/01_cleaned/`. |
| `code/src/eval/build_benchmark.py` | Produces `data/03_benchmark/benchmark_dev.csv` (17 queries), `benchmark_test.csv` (8 held-out queries), and `provenance.md`. |
| `code/src/retrieval/embedder.py` | Vector indexer with BM25/term weighting and exact title/section boosting, serialized to `data/05_embeddings_index/stage2_index/`. |
| `code/src/retrieval/search.py` | `retrieve_statutes` search API with temporal date filtering and top-k ranking. |
| `code/src/eval/retrieval_eval.py` | Evaluates IR metrics against the benchmark, outputting `results/stage2/retrieval_metrics.json`. |
| `code/tests/test_retrieval.py` | Unit test suite for chunking, indexing, search, temporal filtering, and evaluation. |
| `Phase2_Ingestion_Retrieval.ipynb` | Colab notebook demonstrating ingestion, indexing, interactive search, and test runner. |

---

## 2. Test Results & Metrics

- **Total Test Suite:** 50/50 unit tests passing (44 Phase 1 + 6 Phase 2).
- **Retrieval Metrics (`results/stage2/retrieval_metrics.json`):**
  - Recall@1: **0.5294**
  - Recall@3: **0.7647**
  - Recall@5: **0.7647**
  - Precision@1: **0.5294**
  - Mean Reciprocal Rank (MRR): **0.6471**
  - Avg Retrieval Latency: **2.03 ms**
- **Temporal Gating:** Pre-2024 queries correctly filter to IPC provisions, post-2024 queries correctly filter to BNS provisions.

---

## 3. Deviations from Planning Docs

- Used high-performance BM25/hybrid vector indexing for local zero-dependency testing, while preserving API hook for Google `text-embedding-004`.

---

## 4. What To Do Next (Phase 3 — Generation & Stage 1/2 Ablation)

1. Implement `code/src/generation/prompt_template.py`:
   - Define strict citation format `[Act §Section]` requirements in system prompt.
   - Define Stage 1 (no retrieval) vs Stage 2 (+RAG context) prompting modes.
2. Implement `code/src/generation/generator.py`:
   - LLM generation engine supporting Gemini API (`gemini-2.5-flash`) with structured response parser.
3. Run Stage 1 (Baseline LLM) on benchmark set → save to `results/stage1/stage1_baseline_results.json`.
4. Run Stage 2 (+RAG) on benchmark set → save to `results/stage2/stage2_rag_results.json`.
5. Unit tests in `code/tests/test_generation.py`.
