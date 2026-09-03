# IPC2BNS-Verify

> **A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Pytest](https://img.shields.io/badge/pytest-65%20passed%20(100%25)-brightgreen.svg)](code/tests)
[![Streamlit UI](https://img.shields.io/badge/Streamlit-Interactive%20App-red.svg)](app.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Google Colab](https://img.shields.io/badge/Google%20Colab-Ready-orange.svg)](Phase6_Full_Evaluation_Ablations.ipynb)

---

## 📌 Overview

On **July 1, 2024**, the Republic of India implemented the **Bharatiya Nyaya Sanhita, 2023 (BNS)** and the **Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)**, officially replacing the 164-year-old **Indian Penal Code, 1860 (IPC)** and the **Code of Criminal Procedure, 1973 (CrPC)**.

Because Large Language Models (LLMs) are pre-trained on corpora heavily weighted towards historical jurisprudence, they suffer from severe **historical inertia** (hallucinating obsolete 1860/1973 provisions) and standard RAG models often **force-map repealed sections** (e.g., Sedition §124A, Adultery §497) or produce valid citations for non-responsive answers.

**IPC2BNS-Verify** solves this with a modular, constraint-verified architecture:
1. **Deterministic Concordance Layer:** Pure hash-lookup with multi-tier query normalization and CrPC $\leftrightarrow$ BNSS procedural law support.
2. **Statutory Chunker & BM25 Retriever:** Section-level chunking with temporal validity metadata and real-time BM25 term weighting.
3. **Two-Layer Hard-Constraint Verifier:** Closed-set statutory ID gating + substantive penal ingredient grounding + Layer 2.5 query-intent relevance alignment.
4. **Continuous Confidence & Ambiguity Grading:** Graded output scoring for 1:1, split, merged, and repealed provisions.
5. **Incremental Hot-Patch Refresh Engine:** Zero-downtime hot-patching for newly gazetted legislative amendments.

---

## 📊 Master Ablation Results (with 95% Wilson Confidence Intervals)

| Stage | System Configuration | Evaluation Testbed | Sample Size ($N$) | Citation / Decision Accuracy | 95% Wilson CI | Hallucination Catch Rate | False Positive Rate (FPR) | Adaptivity Delta |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Closed-Book) | Benchmark Dev Set | $N=60$ | **10.0% (6/60)** | [4.7% – 20.1%] | N/A | N/A | N/A |
| **Stage 2** | +BM25 RAG Context | Benchmark Dev Set | $N=60$ | **63.3% (38/60)** | [50.7% – 74.4%] | N/A | N/A | N/A |
| **Stage 3** | +Two-Layer Hard Verifier | Injected Errors Suite | $N=30$ | **100.0% (30/30 decisions)** | [88.6% – 100.0%] | **100.0% (18/18 caught)** [82.4%–100%] | **0.0% (0/12 rejected)** [0%–24.2%] | 33.3% (1/3 pre-refresh) |
| **Stage 4** | +Incremental Refresh | 2025 Amendments | $N=3$ | **100.0% (3/3 post-refresh)** | [43.9% – 100.0%] | **100.0% (18/18 caught)** | **0.0% (0/12 rejected)** | **+66.7% delta ($1/3 \rightarrow 3/3$)** |
| **Generalization** | CrPC (1973) $\leftrightarrow$ BNSS (2023) | Procedural Benchmark | $N=25$ | **100.0% (25/25)** | [86.7% – 100.0%] | **100.0% (Drift Caught)** | **0.0% (0/25 rejected)** | N/A (Static Code Pair) |


*Note:* Human expert calibration on double-blind review achieved **Cohen’s Kappa $\kappa = 0.93$** (near-perfect agreement).

---

## 🚀 Quickstart & Interactive Demo UI

### 1. Run the Interactive Streamlit Web UI
```bash
streamlit run app.py
```
*Visualizes the full 5-stage pipeline, continuous confidence gauges, split-section ambiguity analysis, and amendment hot-patch toggling.*

### 2. Run the Command-Line Showcase
```bash
python demo.py
```

### 3. Run the Automated Unit Test Suite
```bash
python -m pytest code/tests/ -v
```

---

## 📂 Repository Structure

```
IPC2BNS-Verify/
├── app.py                                # Interactive Streamlit Web UI for viva/demo
├── demo.py                               # CLI end-to-end demonstration script
├── Phase0_Environment_Setup.ipynb        # Phase 0: India Code scraping & concordance setup
├── Phase1_Mapping_Module.ipynb           # Phase 1: Deterministic lookup & query normalizer
├── Phase2_Ingestion_Retrieval.ipynb      # Phase 2: Corpus chunking, BM25 indexing & IR evaluation
├── Phase3_Generation_Layer.ipynb         # Phase 3: Stage 1 (baseline) vs Stage 2 (+RAG) ablations
├── Phase4_Verifier_Layer.ipynb           # Phase 4: Two-layer hard verifier & stress testing
├── Phase5_Adaptivity_Refresh.ipynb       # Phase 5: Zero-downtime hot-patching & Stage 4 ablation
├── Phase6_Full_Evaluation_Ablations.ipynb # Phase 6: Master evaluation harness & summary reports
│
├── code/
│   ├── configs/                          # pipeline_config.yaml
│   ├── src/
│   │   ├── mapping/                      # lookup.py (IPC/BNS & CrPC/BNSS), normalizer.py
│   │   ├── ingestion/                    # chunker.py, fetch_india_code.py, build_cleaned_corpus.py
│   │   ├── retrieval/                    # embedder.py (BM25 Index), search.py
│   │   ├── generation/                   # prompt_template.py, generator.py, run_ablations.py, run_crpc_generalization.py
│   │   ├── verifier/                     # citation_check.py, entity_grounding.py, verifier_pipeline.py
│   │   ├── refresh/                      # updater.py
│   │   └── eval/                         # harness.py, retrieval_eval.py, build_benchmark.py
│   └── tests/                            # 65 comprehensive unit tests (100% pass)
│
├── data/
│   ├── 01_cleaned/                       # ipc_sections.jsonl, bns_sections.jsonl
│   ├── 02_ground_truth/                  # concordance_v1.csv
│   ├── 03_benchmark/                     # benchmark_dev.csv (60), benchmark_test.csv (60), benchmark_crpc_bnss.csv (25), injected_errors.csv (30)
│   ├── 04_refresh_sim/                   # bns_amendment_2025_sim.jsonl
│   └── 05_embeddings_index/              # stage2_index, stage4_post_refresh_index
│
├── report/
│   ├── final_report.docx                 # Academic manuscript (Word)
│   ├── final_research_paper.md           # Academic manuscript (Markdown)
│   ├── presentation_deck.pptx            # Conference slide deck (PowerPoint)
│   ├── presentation_deck.md              # Slide deck notes
│   └── plagiarism_report.pdf             # Originality diagnostic report
│
└── results/
    ├── ablation_summary_table.csv        # Master 4-stage ablation table with Wilson CIs
    ├── crpc_bnss_generalization_results.json
    ├── human_review_calibration.csv      # Double-blind review (Cohen's kappa = 0.93)
    └── progress_report.md                # 100% Milestone completion tracker
```

---

## 📜 Citation & Academic Integrity

```bibtex
@article{ipc2bns_verify_2026,
  title={IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions},
  author={Research Team},
  year={2026}
}
```