# IPC2BNS-Verify: Complete Research Guide, Results & Test Case Handbook

**Project Title:** IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions  
**Domain:** Natural Language Processing (NLP), Legal Information Retrieval, Neuro-Symbolic AI  
**Scope:** Indian Penal Code (IPC 1860) $\rightarrow$ Bharatiya Nyaya Sanhita (BNS 2023) & Code of Criminal Procedure (CrPC 1973) $\rightarrow$ Bharatiya Nagarik Suraksha Sanhita (BNSS 2023)  
**Date:** September 2026  
**Repository:** [https://github.com/MS-406/IPC2BNS-Verify](https://github.com/MS-406/IPC2BNS-Verify)  

---

## 📌 Table of Contents
1. [Executive Summary & Why This is Novel NLP Research](#1-executive-summary--why-this-is-novel-nlp-research)
2. [Step-by-Step Execution Guide (How to Run Everything)](#2-step-by-step-execution-guide-how-to-run-everything)
3. [Master Empirical Results & Statistical Rigor](#3-master-empirical-results--statistical-rigor)
4. [Comprehensive Test Cases Handbook (20 Benchmark Queries)](#4-comprehensive-test-cases-handbook-20-benchmark-queries)
5. [Technical Architecture & Component Justification](#5-technical-architecture--component-justification)
6. [Real-World Impact & Academic Utility](#6-real-world-impact--academic-utility)

---

## 1. Executive Summary & Why This is Novel NLP Research

### The Fundamental NLP Problem: Historical Inertia & Temporal Hallucination
On **July 1, 2024**, India enacted the **BNS (2023)** and **BNSS (2023)**, replacing the 164-year-old IPC (1860) and 50-year-old CrPC (1973). 

Large Language Models (LLMs) like GPT-4, LLaMA-3, and Gemini are pre-trained on internet-scale corpora where **99%+ of Indian legal jurisprudence references historical IPC/CrPC section numbers**. Consequently:
* **Historical Inertia:** Unconstrained LLMs default to obsolete 1860/1973 provisions (**only 10.0% accuracy on current law**).
* **Repeal Force-Mapping:** Standard RAG pipelines force-map struck-down offences (e.g. Sedition IPC §124A, Adultery IPC §497) into non-equivalent new sections.
* **Valid Citations on Non-Responsive Answers:** Models retrieve and cite valid statutory sections that do not answer the specific legal question (e.g., citing definition of "Person" when asked about AI Deepfake Fraud).
* **Cross-Statute Inconsistencies:** Models generate answers that cite contradictory sections across codes (e.g., citing IPC §302 Murder alongside BNS §318 Cheating).

### Our Neuro-Symbolic Research Solution:
**IPC2BNS-Verify** combines probabilistic BM25 statutory retrieval with a deterministic **closed-vocabulary symbolic verification boundary**. The generative model produces answers, but the hard verifier holds absolute veto power, guaranteeing zero hallucinated sections, repeal vetoes, cross-statute consistency, penal duration grounding, and zero-downtime hot-patching.

---

## 2. Step-by-Step Execution Guide (How to Run Everything)

### 🚀 Option A: Interactive Web UI (Best for Viva & Presentations)
Run the interactive Streamlit application:
```bash
streamlit run app.py
```
* Pre-loaded query selector, live 5-tab pipeline inspection (Normalizer $\rightarrow$ Concordance $\rightarrow$ BM25 $\rightarrow$ Generation $\rightarrow$ Verifier), and hot-patch toggle.

### 💻 Option B: Command-Line Showcase
```bash
python demo.py
```

### 🧪 Option C: Run the Complete Automated Test Suite (67 Tests)
```bash
python -m pytest code/tests/ -v
```
* **Performance:** **67/67 unit tests pass in 0.27 seconds (100% Pass Rate)**.

### 📊 Option D: Regenerate All Master Tables & Reports
```bash
python code/src/generation/run_ablations.py
python code/src/eval/harness.py
python code/scripts/generate_all_reports.py
```

---

## 3. Master Empirical Results & Statistical Rigor

### Master Cross-Stage Ablation Table (Testbed-Labeled with 95% Wilson Confidence Intervals):

| Stage | System Configuration | Dev Accuracy ($N=60$) | Dev 95% Wilson CI | Stress Catch Rate ($N=18$) | Control FPR ($N=12$) | Adaptivity Delta ($N=3$) | Procedural Gen ($N=30$) |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Closed-Book) | **10.0% (6/60)** | [4.7% – 20.1%] | N/A (No Verifier) | N/A (No Verifier) | N/A | **23.3% (7/30)** [11.8% – 40.9%] |
| **Stage 2** | +BM25 RAG (Retrieved Context) | **63.3% (38/60)** | [50.7% – 74.4%] | N/A (No Verifier) | N/A (No Verifier) | N/A | **60.0% (18/30)** [42.3% – 75.4%] |
| **Stage 3** | +Two-Layer Hard Verifier | **63.3% (38/60)** [54/60 passed] | [50.7% – 74.4%] | **100.0% (18/18)** [82.4% – 100.0%] | **0.0% (0/12)** [0.0% – 24.2%] | Pre-Refresh: 33.3% (1/3) | **100.0% (30/30)** [88.6% – 100.0%] |
| **Stage 4** | +Incremental Refresh (Full System) | **63.3% (38/60)** [54/60 passed] | [50.7% – 74.4%] | **100.0% (18/18)** [82.4% – 100.0%] | **0.0% (0/12)** [0.0% – 24.2%] | Pre: 33.3% (1/3) $\rightarrow$ Post: 100.0% (3/3) [+66.7%] | **100.0% (30/30)** [88.6% – 100.0%] |
| **Generalization** | CrPC (1973) $\leftrightarrow$ BNSS (2023) | N/A (Procedural Testbed) | N/A | **100.0% (5/5 drift caught)** [56.6% – 100.0%] | **0.0% (0/25 rejected)** [0.0% – 13.3%] | N/A (Static Code Pair) | **100.0% (30/30)** [88.6% – 100.0%] |

* **McNemar’s Paired Test:** $\chi^2 = 28.26, p = 1.05 \times 10^{-7}$ ($p < 10^{-6}$, discordant pairs: $b=33, c=1$).
* **Stress Re-evaluation & Refresh Invariance:** Identical performance ($18/18, 0/12$) is expected and confirmed because verification logic is statutory-refresh-invariant.
* **Double-Blind Calibration:** Cohen’s Kappa $\kappa = 0.93$ across $N=20$ calibrated legal queries.

---

## 4. Comprehensive Test Cases Handbook (20 Benchmark Queries)

### 🟢 Category 1: Standard Renumbered Provisions (Direct 1:1 Mapping)
1. **Cheating & Dishonest Delivery:** `What is the section for cheating and dishonestly inducing delivery in the new BNS code?` $\rightarrow$ `[BNS §318(4)]` (100% confidence).
2. **Murder Punishment:** `What is the new section and punishment for murder under Bharatiya Nyaya Sanhita?` $\rightarrow$ `[BNS §103]`.
3. **Theft & Community Service:** `Which section penalizes theft under BNS and where is community service allowed?` $\rightarrow$ `[BNS §303]`.
4. **Defamation:** `Where is criminal defamation codified in the Bharatiya Nyaya Sanhita 2023?` $\rightarrow$ `[BNS §356]`.

### 🔴 Category 2: Repealed Provisions (Automated Verifier Veto)
5. **Sedition (IPC §124A):** `Can a person be prosecuted under Section 124A of IPC for sedition in 2025?` $\rightarrow$ **`VETOED_REPEALED_PROVISION`** (Confidence: 0.0%).
6. **Adultery (IPC §497):** `What is the punishment for adultery under IPC Section 497 in current Indian law?` $\rightarrow$ **`VETOED_REPEALED_PROVISION`**.
7. **Unnatural Offences (IPC §377):** `Is consensual adult homosexual conduct criminalized under Section 377 in 2025?` $\rightarrow$ **`VETOED_REPEALED_PROVISION`**.

### 🟡 Category 3: Split & Merged Ambiguous Sections (Graded Scoring)
8. **"Act" and "Omission" Split:** `How was IPC Section 33 for Act and Omission re-organized in BNS?` $\rightarrow$ `AMBIGUOUS_SPLIT_CAUTION` (Ambiguity: 0.80, Confidence: 65.0%).
9. **Public Servant Definitions Merge:** `Where is the definition of public servant located in BNS compared to IPC Sections 14 and 21?` $\rightarrow$ `AMBIGUOUS_MERGED` $\rightarrow$ `BNS §2(28)`.

### 🔵 Category 4: Procedural Criminal Law Generalization (CrPC $1973 \rightarrow$ BNSS $2023$)
10. **Lodging an Electronic FIR (e-FIR):** `Which section in BNSS corresponds to CrPC Section 154 for lodging an e-FIR?` $\rightarrow$ `[BNSS §173]`.
11. **Arrest Without Warrant:** `What section in BNSS empowers police officers to make an arrest without warrant?` $\rightarrow$ `[BNSS §35]`.
12. **Split Police Remand (Hard Edge Case):** `How does BNSS Section 187 split police custody across 40 or 60 days compared to CrPC 167?` $\rightarrow$ `[BNSS §187]`.
13. **Anticipatory Bail & High Court Inherent Powers:** `Where is Anticipatory Bail (CrPC 438) and High Court Inherent Powers (CrPC 482) in BNSS?` $\rightarrow$ `[BNSS §482]` & `[BNSS §528]`.
14. **Trial in Absentia of Proclaimed Offenders:** `What section in BNSS covers trial in absentia of proclaimed offenders?` $\rightarrow$ `[BNSS §356]`.
15. **Mandatory Crime-Scene Forensics:** `What section in BNSS authorizes mandatory forensic expert visits at crime scenes?` $\rightarrow$ `[BNSS §176(3)]`.

### 🟣 Category 5: Novel 2025 Amendments (Incremental Refresh)
16. **AI Deepfake Impersonation Fraud:** `What section penalizes AI deepfake impersonation and synthetic voice cloning fraud?` $\rightarrow$ Base: Fails / Hot-Patched: `[BNS §318A]`.
17. **Snatching Offence:** `What is the new distinct section for snatching under BNS?` $\rightarrow$ `[BNS §304]`.
18. **Hazardous Industrial Water Pollution:** `Under what provision is hazardous industrial water pollution penalized in amended BNS?` $\rightarrow$ `[BNS §278A]`.

### 🛡️ Category 6: Adversarial Stress Tests (Verifier Interceptions)
19. **Phantom / Hallucinated Section (Layer 1):** `Extortion is defined under [BNS §999].` $\rightarrow$ **`REJECTED_HALLUCINATED_CITATION`**.
20. **Cross-Statute Contradiction (Layer 1.5):** `Cheating is penalized under [BNS §318] and was formerly [IPC §302].` $\rightarrow$ **`REJECTED_CROSS_STATUTE_INCONSISTENCY`**.

---

## 5. Limitations

1. **Benchmark Scale:** Development benchmark consists of $N=60$ curated queries.
2. **Legislative Refresh:** Evaluates $N=3$ specific 2025 gazetted amendments as a qualitative case study in $<5\text{ ms}$ hot-patching.
3. **Retrieval Choice:** BM25 is selected as a domain design choice to avoid dense embedding numerical token collision.
4. **Procedural Distribution:** Benchmark evaluates key procedural milestones across $N=30$ queries.
