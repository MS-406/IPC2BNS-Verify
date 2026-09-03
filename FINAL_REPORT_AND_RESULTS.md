# IPC2BNS-Verify: Final Comprehensive Research Report & Experimental Results

**Project Title:** IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions  
**Domain:** Natural Language Processing (NLP), Legal Information Retrieval, Neuro-Symbolic AI  
**Focus Laws:** Indian Penal Code, 1860 (IPC) $\rightarrow$ Bharatiya Nyaya Sanhita, 2023 (BNS) & Code of Criminal Procedure, 1973 (CrPC) $\rightarrow$ Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)  
**Date:** September 2026  

---

## 1. Executive Summary & Core Research Motivation

On **July 1, 2024**, the Republic of India enacted the **Bharatiya Nyaya Sanhita, 2023 (BNS)** and the **Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)**, repealing and replacing the 164-year-old Indian Penal Code (IPC 1860) and the Code of Criminal Procedure (CrPC 1973). 

### The Fundamental NLP Problem: Historical Inertia & Temporal Hallucination
Pre-trained Large Language Models (LLMs) are trained on massive historical corpora where 99%+ of Indian legal jurisprudence references old IPC and CrPC section numbers. Consequently:
1. **Historical Inertia:** When asked legal questions about current law, LLMs default to obsolete provisions (e.g. citing IPC §302 for Murder or CrPC §154 for FIRs).
2. **Force-Mapping Repealed Provisions:** Standard Retrieval-Augmented Generation (RAG) pipelines force-map struck-down/repealed offences (e.g., Sedition IPC §124A or Adultery IPC §497) into non-equivalent new sections.
3. **Subtle Non-Responsive Citations:** Generative models cite real sections that exist in the statute but completely fail to answer the user's specific legal query (e.g., citing definition of "Person" when asked about AI Deepfake Fraud).
4. **Cross-Statutory Inconsistencies:** Models cite mixed provisions that contradict each other across codes (e.g., citing IPC §302 Murder alongside BNS §318 Cheating).

### Our Core NLP Contribution:
**IPC2BNS-Verify** is a **Neuro-Symbolic Legal RAG Architecture** that combines probabilistic retrieval with strict deterministic statutory verification guardrails. It establishes a verifiable boundary that guarantees zero hallucinated section numbers, active repeal vetoes, cross-statute concordance consistency, and zero-downtime hot-patching for new amendments.

---

## 2. Technical Architecture & Component Justification

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

---

## 3. Master Experimental Results & Stage-by-Stage Ablation

### Master Ablation Summary Table (Testbed-Labeled with 95% Wilson Confidence Intervals):

| Stage | System Configuration | Dev Accuracy ($N=60$) | Dev 95% Wilson CI | Stress Catch Rate ($N=18$) | Control FPR ($N=12$) | Adaptivity Delta ($N=3$) | Procedural Gen ($N=30$) |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Closed-Book) | **10.0% (6/60)** | [4.7% – 20.1%] | N/A (No Verifier) | N/A (No Verifier) | N/A | **23.3% (7/30)** [11.8% – 40.9%] |
| **Stage 2** | +BM25 RAG (Retrieved Context) | **63.3% (38/60)** | [50.7% – 74.4%] | N/A (No Verifier) | N/A (No Verifier) | N/A | **60.0% (18/30)** [42.3% – 75.4%] |
| **Stage 3** | +Two-Layer Hard Verifier | **63.3% (38/60)** [54/60 passed] | [50.7% – 74.4%] | **100.0% (18/18)** [82.4% – 100.0%] | **0.0% (0/12)** [0.0% – 24.2%] | Pre-Refresh: 33.3% (1/3) | **100.0% (30/30)** [88.6% – 100.0%] |
| **Stage 4** | +Incremental Refresh (Full System) | **63.3% (38/60)** [54/60 passed] | [50.7% – 74.4%] | **100.0% (18/18)** [82.4% – 100.0%] | **0.0% (0/12)** [0.0% – 24.2%] | Pre: 33.3% (1/3) $\rightarrow$ Post: 100.0% (3/3) [+66.7%] | **100.0% (30/30)** [88.6% – 100.0%] |
| **Generalization** | CrPC (1973) $\leftrightarrow$ BNSS (2023) | N/A (Procedural Testbed) | N/A | **100.0% (5/5 drift caught)** [56.6% – 100.0%] | **0.0% (0/25 rejected)** [0.0% – 13.3%] | N/A (Static Code Pair) | **100.0% (30/30)** [88.6% – 100.0%] |

*Notes:*
1. **McNemar’s Paired Test:** Stage 1 vs Stage 2 yields $\chi^2 = 28.26, p = 1.05 \times 10^{-7}$ ($p < 10^{-6}$, discordant pairs $b=33, c=1$), establishing statistical significance.
2. **Stress-Suite Re-evaluation & Refresh Invariance:** Stress suite ($N=30$) was independently re-evaluated across stages; identical performance ($18/18, 0/12$) is expected and confirmed because verification logic is refresh-invariant.
3. **Double-Blind Calibration:** Evaluated on $N=20$ calibrated legal queries, achieving **Cohen’s Kappa $\kappa = 0.93$**.

---

## 4. Key Verifier Case Studies

### 4.1 Case Study 1: Repealed Sedition Section Veto (IPC §124A)
* **User Query:** *"Can a person be prosecuted under Section 124A of IPC for sedition in 2025?"*
* **Verifier Remediation:** Detects repealed section, intercepts output, and injects authoritative advisory:
  > `[VERIFIER VETO]: The cited provision IPC Section 124A has been REPEALED and has NO direct equivalent in BNS 2023. BNS S.152 is narrower in scope — flagged as ambiguous.`
* **Confidence Score:** `0.0% (VETOED_REPEALED)` | **Ambiguity Score:** `1.00`.

### 4.2 Case Study 2: Ambiguous Split Section (IPC §33 'Act' & 'Omission')
* **User Query:** *"How was IPC Section 33 for Act and Omission re-organized in BNS?"*
* **Verifier Remediation:** Detects split provision, maps to `BNS §2(1)` (Act) and `BNS §2(25)` (Omission), and issues graded confidence output.
* **Confidence Score:** `65.0% (AMBIGUOUS_SPLIT_FLAGGED)` | **Ambiguity Score:** `0.80`.

### 4.3 Case Study 3: Valid Citation on Non-Responsive Answer (AI Deepfake Fraud)
* **User Query:** *"What section penalizes AI deepfake impersonation and synthetic voice cloning fraud?"*
* **Layer 2.5 Remediation:** Detects query keywords (`deepfake`, `impersonation`, `fraud`) missing in cited chunk; flags `NON_RESPONSIVE_ANSWER`.

### 4.4 Case Study 4: Cross-Statute Citation Contradiction (Layer 1.5)
* **Model Output:** *"Cheating is penalized under [BNS §318] and was formerly [IPC §302]."*
* **Layer 1.5 Remediation:** Verifies concordance table; detects that `IPC §302` maps to `BNS §103` (Murder) rather than `BNS §318` (Cheating).
* **Verdict:** `REJECTED_CROSS_STATUTE_INCONSISTENCY`.

---

## 5. Limitations

1. **Benchmark Scale:** Development benchmark consists of $N=60$ curated queries.
2. **Legislative Refresh:** Evaluates $N=3$ specific 2025 gazetted amendments as a qualitative case study in $<5\text{ ms}$ hot-patching.
3. **Retrieval Choice:** BM25 is selected as a domain design choice to avoid dense embedding numerical token collision.
4. **Procedural Distribution:** Benchmark evaluates key procedural milestones across $N=30$ queries.

---

## 6. Deliverables & Verification Suite

1. 🖥️ **Interactive Web Application:** [`app.py`](file:///d:/college%204th%20year/research%20paper/NLP_rs/app.py) (`streamlit run app.py`)
2. 💻 **CLI Showcase Script:** [`demo.py`](file:///d:/college%204th%20year/research%20paper/NLP_rs/demo.py) (`python demo.py`)
3. 📄 **Academic Research Paper (Markdown):** [`report/final_research_paper.md`](file:///d:/college%204th%20year/research%20paper/NLP_rs/report/final_research_paper.md)
4. 📄 **Academic Research Paper (Word):** [`report/final_report.docx`](file:///d:/college%204th%20year/research%20paper/NLP_rs/report/final_report.docx)
5. 📊 **Master Ablation CSV:** [`results/ablation_summary_table.csv`](file:///d:/college%204th%20year/research%20paper/NLP_rs/results/ablation_summary_table.csv)
6. 🧪 **Automated Unit Tests:** **67/67 passing tests** in [`code/tests/`](file:///d:/college%204th%20year/research%20paper/NLP_rs/code/tests) in $0.27\text{s}$.
7. 🌐 **GitHub Repository (Main Branch):** **[https://github.com/MS-406/IPC2BNS-Verify](https://github.com/MS-406/IPC2BNS-Verify)**
