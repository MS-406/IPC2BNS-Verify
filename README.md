# IPC2BNS-Verify

> **A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Pytest](https://img.shields.io/badge/pytest-65%20passed%20(100%25)-brightgreen.svg)](code/tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Google Colab](https://img.shields.io/badge/Google%20Colab-Ready-orange.svg)](Phase6_Full_Evaluation_Ablations.ipynb)

---

## 📌 Overview

On **July 1, 2024**, the Republic of India enacted the **Bharatiya Nyaya Sanhita, 2023 (BNS)**, officially repealing and replacing the 164-year-old **Indian Penal Code, 1860 (IPC)**. 

Because Large Language Models (LLMs) are pre-trained on corpora heavily weighted towards historical IPC jurisprudence, they suffer from severe **historical inertia** (hallucinating old IPC section numbers) and standard RAG models often **force-map repealed sections** (e.g., Sedition §124A, Adultery §497) into incorrect new provisions.

**IPC2BNS-Verify** solves this with a 4-stage modular pipeline:
1. **Deterministic Concordance Layer:** Pure hash-lookup with multi-tier query normalization.
2. **Statutory Chunker & Embedder:** Temporal validity metadata and hybrid vector indexing.
3. **Two-Layer Hard-Constraint Verifier:** Closed-set statutory ID gating + semantic ingredient grounding with automated repeal veto advisories.
4. **Incremental Hot-Patch Refresh Engine:** Ingests newly gazetted amendments in-memory without full corpus rebuilds.

---

## 📊 Master Ablation Results

| Stage | System Configuration | Citation Accuracy (%) | Hallucination Catch Rate (%) | False Positive Rate (FPR) | Adaptivity Gain |
|:---:|:---|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Zero-shot Closed-Book) | 35.3% | N/A | N/A | Baseline |
| **Stage 2** | +RAG (Retrieved Statutory Context) | 70.6% | N/A | N/A | +35.3% vs Baseline |
| **Stage 3** | +Two-Layer Hard-Constraint Verifier | 70.6% | **100.0%** (6/6 caught) | **0.0%** (0/4 rejected) | Vetoes Repeals & Phantoms |
| **Stage 4** | +Incremental Refresh (Full System) | **98.5%** | **100.0%** | **0.0%** | **+66.7%** on Amendments |

---

## 📂 Repository Structure

```
IPC2BNS-Verify/
├── Phase0_Environment_Setup.ipynb        # Phase 0: India Code scraping & concordance setup
├── Phase1_Mapping_Module.ipynb           # Phase 1: Deterministic lookup & query normalizer
├── Phase2_Ingestion_Retrieval.ipynb      # Phase 2: Corpus chunking, BM25 indexing & IR evaluation
├── Phase3_Generation_Layer.ipynb         # Phase 3: Stage 1 (baseline) vs Stage 2 (+RAG) ablations
├── Phase4_Verifier_Layer.ipynb           # Phase 4: Two-layer hard verifier & stress testing
├── Phase5_Adaptivity_Refresh.ipynb       # Phase 5: Zero-downtime hot-patching & Stage 4 ablation
├── Phase6_Full_Evaluation_Ablations.ipynb # Phase 6: Master evaluation harness & summary reports
├── Step1_Setup.ipynb                     # Scaffolding & Google Drive setup
├── check_progress.py                     # WBS task progress checker (100% complete)
│
├── code/
│   ├── configs/                          # pipeline_config.yaml
│   ├── src/
│   │   ├── mapping/                      # lookup.py, normalizer.py, cross_validate.py
│   │   ├── ingestion/                    # chunker.py, fetch_india_code.py, build_cleaned_corpus.py
│   │   ├── retrieval/                    # embedder.py, search.py
│   │   ├── generation/                   # prompt_template.py, generator.py, run_ablations.py
│   │   ├── verifier/                     # citation_check.py, entity_grounding.py, verifier_pipeline.py
│   │   ├── refresh/                      # updater.py
│   │   └── eval/                         # harness.py, retrieval_eval.py, build_benchmark.py
│   ├── scripts/                          # Automated notebook builder scripts
│   └── tests/                            # 65 automated unit tests (100% pass rate)
│
├── data/
│   ├── 00_raw/                           # India Code raw Bare Acts & concordance source data
│   ├── 01_cleaned/                       # Cleaned ipc_sections.jsonl & bns_sections.jsonl
│   ├── 02_ground_truth/                  # concordance_v1.csv, CHANGELOG.md, validation_report.csv
│   ├── 03_benchmark/                     # benchmark_dev.csv, benchmark_test.csv, injected_errors.csv
│   ├── 04_refresh_sim/                   # injected_amendment_cases.csv
│   └── 05_embeddings_index/              # stage2_index/ & stage4_post_refresh_index/
│
├── docs/                                 # Master planning docs, runbooks, DMP & technical pipeline
├── report/                               # Academic research paper draft & presentation deck
└── results/                              # Ablation summary table, calibration data & progress report
```

---

## 🚀 Quickstart

### 1. Run Tests Locally
```bash
# Clone the repository
git clone https://github.com/MS-406/IPC2BNS-Verify.git
cd IPC2BNS-Verify

# Run the full 65-test suite
python -m pytest code/tests/ -v
```

### 2. Run in Google Colab
Open any of the `Phase*.ipynb` notebooks in [Google Colab](https://colab.research.google.com). For the full end-to-end evaluation report, run:
👉 **[`Phase6_Full_Evaluation_Ablations.ipynb`](Phase6_Full_Evaluation_Ablations.ipynb)**

---

## 📜 Deliverables & Artifacts

- 📄 **[Full Academic Research Paper Draft](report/final_research_paper.md)**
- 📊 **[Slide-by-Slide Presentation Deck](report/presentation_deck.md)**
- 📈 **[Master Ablation Summary Table](results/ablation_summary_table.csv)**
- 🔍 **[Qualitative Error Analysis](results/error_analysis_notes.md)**
- 👥 **[Double-Blind Human Calibration](results/human_review_calibration.csv)**