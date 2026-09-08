# IPC2BNS-Verify: Constraint-Verified RAG for Indian Statutory Transitions

> **A Neuro-Symbolic, Explainable, and Incrementally Refreshable RAG Framework for Indian Criminal Law Statutory Transitions (IPC $\rightarrow$ BNS & CrPC $\rightarrow$ BNSS)**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Pytest](https://img.shields.io/badge/pytest-67%20passed%20(100%25)-brightgreen.svg)](code/tests)
[![Streamlit UI](https://img.shields.io/badge/Streamlit-Interactive%20App-red.svg)](app.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Google Colab](https://img.shields.io/badge/Google%20Colab-Ready-orange.svg)](Phase6_Full_Evaluation_Ablations.ipynb)

---

## 📌 1. Research Overview & Motivation

### The Legal Overhaul (July 1, 2024)
On **July 1, 2024**, the Republic of India overhauled its colonial-era criminal justice framework:
* **Substantive Penal Law:** The 164-year-old *Indian Penal Code (IPC 1860)* was replaced by the *Bharatiya Nyaya Sanhita (BNS 2023)*.
* **Procedural Criminal Law:** The 50-year-old *Code of Criminal Procedure (CrPC 1973)* was replaced by the *Bharatiya Nagarik Suraksha Sanhita (BNSS 2023)*.
* **Law of Evidence:** The *Indian Evidence Act (IEA 1872)* was replaced by the *Bharatiya Sakshya Adhiniyam (BSA 2023)*.

### The NLP Challenge: Historical Inertia & Hallucinations
Because foundation Large Language Models (LLMs) like GPT-4, LLaMA-3, Gemini, or InLegalBERT are pre-trained on decades of legal corpora, over **99% of Indian legal training tokens reference historical IPC and CrPC numbers**. When queried on current Indian law, standard LLMs suffer from critical failure modes:
1. **Historical Inertia (90% failure rate):** Closed-book models default to obsolete sections (e.g., citing IPC §302 for Murder instead of BNS §103, or IPC §420 for Cheating instead of BNS §318).
2. **Repeal Force-Mapping:** Standard RAG pipelines force-map struck-down/repealed offences (such as Sedition IPC §124A or Adultery IPC §497) to unrelated BNS provisions.
3. **Cross-Statutory Inconsistency:** Generating answers that cite conflicting old and new provisions (e.g., *"Cheating is under BNS §318 and was formerly IPC §302 [Murder]"*).
4. **Ungrounded Penal Duration Claims:** Generating inaccurate sentencing claims (e.g., asserting life imprisonment for offences carrying a 3-year ceiling).
5. **Non-Responsive Citations:** Retrieving valid statutory sections that do not answer the specific query (e.g., citing the definition of "Person" when asked about AI Deepfake Fraud).

---

## 💡 2. Core Architecture & Key Innovations

Instead of fine-tuning multi-billion parameter LLMs every time an amendment is gazetted, **IPC2BNS-Verify** introduces a **transparent, white-box, neuro-symbolic RAG architecture** that decouples probabilistic natural language generation from hard statutory verification.

```
                           USER LEGAL QUERY
                                  │
                                  ▼
              ┌───────────────────────────────────────┐
              │     1. Multi-Tier Query Normalizer    │
              │  (Regex -> Domain Lexicon -> Fallback)│
              └───────────────────┬───────────────────┘
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
┌──────────────────────────────┐                   ┌──────────────────────────────┐
│  2. Deterministic Concordance│                   │ 3. BM25 Statutory Retriever  │
│     Graph & Section Mapper   │                   │  (Temporal Validity Gated)   │
│  (1:1, Splits, Repeals Veto) │                   │  (k1=1.5, b=0.75, Section+25)│
└──────────────┬───────────────┘                   └──────────────┬───────────────┘
               │                                                   │
               │         ┌──────────────────────────────┐          │
               └────────►│ 4. Generative Answering RAG  │◄─────────┘
                         │ (Strict [Act §Sec] Grammar)  │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │ 5. Multi-Layer Hard Verifier │
                         │ ├─ Layer 1: Closed ID Gating │
                         │ ├─ Layer 1.5: Cross-Statute  │
                         │ ├─ Layer 2: Penal Grounding  │
                         │ └─ Layer 2.5: Intent Gating  │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │  6. Graded Output & Veto     │
                         │  (Confidence: 0.0 - 1.0)     │
                         │  (Ambiguity: 0.0 - 1.0)      │
                         └──────────────────────────────┘
```

### Innovative Modules:
* **Multi-Tier Query Normalization:** Extracts explicit section references in $<0.1\text{ ms}$ (Regex Tier 1) or maps colloquial offense names (*"dowry death"*, *"extortion"*) to canonical keys (Domain Lexicon Tier 2).
* **Deterministic Concordance Engine:** Maps 1:1 direct provisions, handles 1-to-many splits (e.g. IPC §33 $\rightarrow$ BNS §2(1) & §2(25)), consolidations, and flags repealed laws with automated statutory advisories.
* **BM25 Statutory Retriever:** Custom term-weighted BM25 indexing ($k_1=1.5, b=0.75$, with section boost $+25.0$) designed to eliminate dense vector collisions on numerical section IDs.
* **4-Tier Hard-Constraint Verifier:**
  - **Layer 1 (Closed-Vocabulary Gating):** Checks citations against the closed set of all 358 BNS, 511 IPC, 484 CrPC, and 531 BNSS provisions. Citing a repealed section triggers an immediate `VETOED_REPEALED_PROVISION` advisory.
  - **Layer 1.5 (Cross-Statute Consistency):** Detects and rejects mismatched dual citations (e.g. IPC §302 with BNS §318).
  - **Layer 2 (Penal Duration Grounding):** Bounds generated prison sentences against bare-act text chunks.
  - **Layer 2.5 (Query-Intent Gating):** Eliminates valid but non-responsive citations by measuring token overlap with query intent.
* **Zero-Downtime Hot-Patch Refresh:** Enables updating the statutory index for newly gazetted amendments in **$<5\text{ ms}$** without offline re-indexing.
* **Explainable White-Box Provenance:** Exposes the exact bare-act source chunk, BM25 score, concordance rule, and layer-by-layer pass/fail verification verdicts.

---

## 📊 3. Experimental Results

### Master 4-Stage Ablation Summary (with 95% Wilson Confidence Intervals)

| Stage | System Configuration | Dev Accuracy ($N=60$) | Dev 95% Wilson CI | Stress Catch Rate ($N=18$) | Control FPR ($N=12$) | Adaptivity Delta ($N=3$) | Procedural Gen ($N=30$) |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Closed-Book) | **10.0% (6/60)** | [4.7% – 20.1%] | N/A | N/A | N/A | **23.3% (7/30)** |
| **Stage 2** | +Hybrid Statutory RAG (Top-5 + Reranker) | **66.7% (40/60)** | [54.1% – 77.3%] | N/A | N/A | N/A | **60.0% (18/30)** |
| **Stage 3** | +Two-Layer Hard Verifier | **66.7% (40/60)** | [54.1% – 77.3%] | **100.0% (18/18)** | **0.0% (0/12)** | Pre: 33.3% (1/3) | **100.0% (30/30)** |
| **Stage 4** | +Incremental Refresh (Full System) | **66.7% (40/60)** | [54.1% – 77.3%] | **100.0% (18/18)** | **0.0% (0/12)** | Post: **100.0% (3/3)** [+66.7%] | **100.0% (30/30)** |
| **Generalization** | CrPC (1973) $\leftrightarrow$ BNSS (2023) | N/A (Procedural) | N/A | **100.0% (5/5 drift caught)** | **0.0% (0/25 rejected)** | N/A (Static Code Pair) | **100.0% (30/30)** |

### Independently-Sourced Benchmark (IndicLegalQA, $N=50$)

| Evaluation Stage | System Configuration | Accuracy (Full $N=50$) | Accuracy (Active $N=48$) | Wilson 95% CI | Verifier Status |
|:---:|:---|:---:|:---:|:---:|:---|
| **Stage 1** | Baseline LLM (Closed-Book) | **4.0% (2/50)** | **4.2% (2/48)** | [1.1% – 13.5%] | N/A (No Verifier) |
| **Stage 2a** | +BM25 Statutory RAG (Baseline) | **28.0% (14/50)** | **29.2% (14/48)** | [17.5% – 41.7%] | N/A (No Verifier) |
| **Stage 2b** | +Hybrid RRF + Expansion (Top-3) | **42.0% (21/50)** | **43.8% (21/48)** | [29.4% – 55.8%] | N/A (No Verifier) |
| **Stage 2c** | +Hybrid RRF + Expansion (Top-5) | **46.0% (23/50)** | **47.9% (23/48)** | [33.4% – 60.1%] | N/A (No Verifier) |
| **Stage 3** | +Two-Layer Hard Verifier | **42.0% (21/50)** | **43.8% (21/48)** | [29.4% – 55.8%] | **44/50 Passed**, **2 Vetoed**, **4 Rejected** |

### Systematic Retriever Ablation Comparison (Empirical Metrics on IndicLegalQA $N=50$)

| Retrieval Strategy | IndicLegalQA Recall@1 ($N=50$) | IndicLegalQA Recall@5 ($N=50$) | IndicLegalQA MRR | Downstream Hit Top-3 | Downstream Hit Top-5 (Valid $N=48$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **1. BM25 (Sparse Baseline)** | 10.0% (5/50) | 46.0% (23/50) | 0.248 | 32.0% (16/50) | 33.3% (16/48) |
| **2. BM25 + Concordance Expansion** | 28.0% (14/50) | 52.0% (26/50) | 0.383 | 46.0% (23/50) | 47.9% (23/48) |
| **3. Dense Semantic (Cosine)** | 16.0% (8/50) | 50.0% (25/50) | 0.310 | 46.0% (23/50) | 47.9% (23/48) |
| **4. Hybrid RRF (BM25 + Dense)** | 10.0% (5/50) | 48.0% (24/50) | 0.258 | 46.0% (23/50) | 47.9% (23/48) |
| **5. Hybrid RRF + Expansion** | **28.0% (14/50)** | **56.0% (28/50)** | **0.396** | **46.0% (23/50)** | **47.9% (23/48)** |
| **6. Hybrid RRF + Re-Ranking** | 18.0% (9/50) | 42.0% (21/50) | 0.280 | 46.0% (23/50) | 47.9% (23/48) |

### Statistical Rigor & Scale Highlights:
* **Statistical Significance:** McNemar's paired test confirms the Stage 1 $\rightarrow$ Stage 2 jump is highly significant ($\chi^2 = 30.25, p = 3.80 \times 10^{-8}$).
* **100% Adversarial Catch Rate:** The verifier caught 18/18 synthetic hallucinations with 0/12 false positives on controls.
* **Large-Scale Benchmark (Phase 7: $N=1,140$):** Evaluated across 10 statutory categories; the verifier maintained a **94.4% (17/18)** adversarial catch rate at scale.
* **Hybrid Retrieval Leap:** Concordance query expansion + Hybrid RRF boosts IndicLegalQA end-to-end citation accuracy from **4.0% $\rightarrow$ 42.0%** ($10.5\times$ gain over closed-book baseline).
* **Human Expert Calibration:** Double-blind review by legal annotators achieved **Cohen’s Kappa $\kappa = 0.87$** (95.0% concordance, $N=20$).

---



## 🗂️ 4. Datasets Used

All datasets are curated from official gazetted publications and stored in structured formats:
1. **Bare-Act Cleaned Corpora (`data/01_cleaned/`):**
   - `ipc_sections.jsonl` (511 sections of IPC 1860)
   - `bns_sections.jsonl` (358 sections of BNS 2023)
   - Procedural statutory definitions (CrPC 1973 & BNSS 2023)
2. **Concordance Ground Truths (`data/02_ground_truth/`):**
   - `ipc_to_bns_concordance.csv` (1:1 maps, 1-to-many splits, consolidations, and repeal tags)
3. **Benchmark Suites (`data/03_benchmark/`):**
   - `benchmark_dev_questions.jsonl` ($N=60$ dev testbed)
   - `stress_test_suite.jsonl` ($N=30$: 18 adversarial attacks + 12 valid controls)
   - `crpc_bnss_generalization_results.json` ($N=30$ procedural queries)
   - `external_indic_legal_qa.csv` ($N=50$ independently sourced IndicLegalQA queries)

4. **Production-Scale Benchmark (`phase7/benchmark/`):**
   - `phase7_master_benchmark_1140.jsonl` ($N=1,140$ queries across 10 categories)
5. **Human Annotation Calibration (`results/`):**
   - `human_review_calibration.csv` ($N=20$ double-blind calibrated legal reviews)

---

## 🛠️ 5. Technology Stack & Libraries

* **Core Language:** Python 3.10+ / 3.11+
* **Information Retrieval & NLP:**
  - `rank_bm25` (BM25Okapi statutory index with custom term weighting)
  - `regex` (statutory citation pattern extraction)
  - `pandas`, `numpy` (matrix processing, concordance indexing)
  - `scikit-learn` (evaluation metrics, Cohen's Kappa calculation)
* **Neural Generation (Optional Local Seq2Seq):**
  - `transformers`, `torch`, `sentencepiece` (`google/flan-t5-base`)
* **Interactive UI & Presentation:**
  - `streamlit` (interactive web demonstration interface)
  - `python-docx` (automated programmatic report generation)
  - `python-pptx` (automated slide deck compilation)
* **Testing & Quality Assurance:**
  - `pytest`, `pytest-asyncio` (67/67 automated unit tests)

---

## 🚀 6. Step-by-Step Operations Guide

### Step 1: Environment Setup
```powershell
# Clone the repository
git clone https://github.com/MS-406/IPC2BNS-Verify.git
cd IPC2BNS-Verify

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Run the Unit Test Suite (67/67 Passing)
```powershell
python -m pytest code/tests/ -v
```

### Step 3: Launch the Interactive Streamlit Web UI
```powershell
streamlit run app.py
```
*Allows you to test custom queries, toggle 2025 amendment hot-patches, inspect concordance graphs, and view real-time verifier advisories.*

### Step 4: Run the Command-Line Showcase
```powershell
python demo.py
```

### Step 5: Run Programmatic RAG Verification in Python
```python
from code.src.mapping.concordance_engine import ConcordanceEngine
from code.src.retrieval.bm25_retriever import BM25Retriever
from code.src.verifier.master_verifier import MasterVerifier

# Initialize components
concordance = ConcordanceEngine("data/02_ground_truth/ipc_to_bns_concordance.csv")
retriever = BM25Retriever("data/01_cleaned/bns_sections.jsonl")
verifier = MasterVerifier(concordance_engine=concordance)

# Query and retrieve
query = "What is the punishment for cheating under current Indian law?"
chunks = retriever.search(query, top_k=3)

# Verify generated legal assertion
answer = "Cheating is defined under [BNS §318] with imprisonment up to 3 years."
verdict = verifier.verify(query=query, generated_text=answer, retrieved_chunks=chunks)

print(f"Status: {verdict.status}")             # PASSED
print(f"Confidence: {verdict.confidence_score}") # 1.00
```

### Step 6: Regenerate Word Reports & Synchronize
* **Generate updated docx reports:**
  ```powershell
  python code/scripts/generate_all_reports.py
  ```
* **Sync repository to Google Drive backup:**
  ```powershell
  code\scripts\sync_to_drive.bat
  ```

---

## 📁 7. Repository Directory Structure

```
IPC2BNS-Verify/
├── app.py                                # Interactive Streamlit Web Demonstration UI
├── demo.py                               # CLI end-to-end demonstration script
├── requirements.txt                      # Python dependencies
├── README.md                             # Project documentation
│
├── code/
│   ├── configs/                          # pipeline_config.yaml
│   ├── src/
│   │   ├── mapping/                      # ConcordanceEngine & MultiTierNormalizer
│   │   ├── ingestion/                    # Chunker & bare-act preprocessors
│   │   ├── retrieval/                    # BM25Retriever & temporal search
│   │   ├── generation/                   # Prompt builders & statutory synthesizer
│   │   ├── verifier/                     # MasterVerifier, closed ID gating, penal grounding
│   │   ├── refresh/                      # Incremental amendment hot-patch engine
│   │   └── eval/                         # Benchmark evaluation harness
│   ├── scripts/                          # generate_all_reports.py, sync_to_drive.bat
│   └── tests/                            # 67 unit tests covering all modules
│
├── data/
│   ├── 01_cleaned/                       # ipc_sections.jsonl, bns_sections.jsonl
│   ├── 02_ground_truth/                  # ipc_to_bns_concordance.csv
│   ├── 03_benchmark/                     # dev, stress test, and procedural benchmarks
│   ├── 04_refresh_sim/                   # 2025 gazetted amendments simulation
│   └── 05_embeddings_index/              # Stage 2 and Stage 4 BM25 indices
│
├── phase7/
│   ├── benchmark/                        # Master benchmark (1,140 queries)
│   ├── generators/                       # Local neural Flan-T5 seq2seq baseline
│   ├── evaluation/                       # Phase 7 evaluation & metric scripts
│   └── results/                          # Phase 7 figures, tables, and reports
│
├── report/
│   ├── final_research_paper.md           # Academic manuscript (IEEE/ACM format)
│   ├── MASTER_RESULTS_CHALLENGES_AND_EVALUATION.md # Comprehensive synthesis & viva guide
│   ├── PHASE7_LARGE_SCALE_EVALUATION.md  # 21-section Phase 7 evaluation report
│   ├── COMPLETE_RESEARCH_GUIDE_AND_RESULTS.md # Complete research guide
│   ├── RESEARCH_PAPER_SIMPLIFIED_GUIDE.md# Plain-English guide for reviewers
│   ├── final_report.docx                 # Synchronized Word report
│   └── presentation_deck.pptx            # 12-slide presentation deck
│
└── results/
    ├── ablation_summary_table.csv        # Master 4-stage ablation results
    ├── crpc_bnss_generalization_results.json # Procedural generalization results
    ├── human_review_calibration.csv      # Double-blind human review (Cohen's kappa = 0.87)
    ├── phase7_tables/                    # 11 CSV/JSON metric tables
    └── phase7_figures/                   # 6 publication-ready charts
```

---

## 📜 8. Citation

```bibtex
@article{ipc2bns_verify_2026,
  title={IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions},
  author={Research Team},
  journal={Department of Computer Science & Engineering},
  year={2026}
}
```