# IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions

**Authors:** Research Team  
**Affiliation:** Department of Computer Science & Engineering  
**Date:** September 2026  
**Keywords:** Legal NLP, Retrieval-Augmented Generation, Neuro-Symbolic AI, Statutory Verification, Temporal Hallucination, Indian Criminal Law  

---

## Abstract
On July 1, 2024, India replaced its 164-year-old Indian Penal Code (IPC, 1860) and 50-year-old Code of Criminal Procedure (CrPC, 1973) with the Bharatiya Nyaya Sanhita (BNS, 2023) and Bharatiya Nagarik Suraksha Sanhita (BNSS, 2023). This major legislative shift poses a severe challenge for Large Language Models (LLMs), which exhibit persistent *historical inertia* by defaulting to obsolete section numbers (10.0% closed-book accuracy) or force-mapping repealed provisions (e.g., Sedition §124A, Adultery §497). We introduce **IPC2BNS-Verify**, a neuro-symbolic, constraint-verified RAG framework for statutory transitions. IPC2BNS-Verify pairs BM25 statutory retrieval with a deterministic verification boundary enforcing closed-vocabulary statutory gating, multi-citation cross-code consistency, penal duration bounding, and query-intent relevance alignment. On our expert-annotated benchmark ($N=60$ dev queries, $N=30$ adversarial stress cases, $N=30$ procedural questions), our framework elevates citation accuracy from a closed-book baseline of **10.0% (6/60)** [95% CI: 4.7%–20.1%] to **63.3% (38/60)** [95% CI: 50.7%–74.4%] under BM25 RAG (McNemar’s paired test: $\chi^2 = 28.26, p = 1.05 \times 10^{-7}$), while the two-layer verifier achieves a **100.0% (18/18)** hallucination catch rate with a **0.0% (0/12)** false positive rate. On procedural criminal law (CrPC $\leftrightarrow$ BNSS), our framework achieves **100.0% (30/30)** accuracy compared to a 23.3% baseline. We further demonstrate zero-downtime adaptivity on 2025 gazetted amendments in $<5\text{ ms}$ ($1/3 \rightarrow 3/3$). Double-blind human evaluation demonstrates near-perfect inter-annotator agreement (Cohen’s $\kappa = 0.93$).

---

## 1. Introduction & Background

The modernization of Indian criminal law on July 1, 2024, represents one of the largest statutory overhauls in modern legal history:
* **Substantive Criminal Law:** The *Bharatiya Nyaya Sanhita, 2023 (BNS)* repealed and replaced the *Indian Penal Code, 1860 (IPC)*.
* **Procedural Criminal Law:** The *Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)* replaced the *Code of Criminal Procedure, 1973 (CrPC)*.
* **Law of Evidence:** The *Bharatiya Sakshya Adhiniyam, 2023 (BSA)* replaced the *Indian Evidence Act, 1872 (IEA)*.

### 1.1 The NLP Challenge: Historical Inertia and Temporal Hallucination
Because foundation LLMs (such as GPT-4, LLaMA-3, and Gemini) are pre-trained on internet-scale text containing over a century of legal judgments, commentaries, and case filings, over 99% of Indian legal pre-training tokens reference historical IPC and CrPC numbers. When queried on current Indian law, LLMs suffer from four distinct failure modes:
1. **Historical Inertia:** Defaulting to obsolete sections (e.g., citing IPC §302 for Murder instead of BNS §103, or CrPC §154 for FIRs instead of BNSS §173).
2. **Repeal Force-Mapping:** Standard RAG pipelines frequently force-map struck-down offences (such as Sedition IPC §124A or Adultery IPC §497) to unrelated BNS provisions.
3. **Valid Citations on Non-Responsive Answers:** Models retrieve and cite valid sections that do not answer the specific legal question (e.g., citing the general definition of "Person" when asked about AI Deepfake Fraud).
4. **Cross-Statutory Inconsistency:** Generating answers that cite both an old section and a new section that do not correspond to the same offence (e.g., citing IPC §302 Murder alongside BNS §318 Cheating).

---

## 2. System Architecture

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

### 2.1 Multi-Tier Query Normalization
Queries are mapped to canonical statutory keys through a hierarchical normalizer:
* **Tier 1 (Regex):** Extracts direct section identifiers (e.g., *"Section 420 IPC"*, *"§124A"*) in $<0.1\text{ ms}$.
* **Tier 2 (Domain Lexicon):** Maps natural language offence terms (e.g., *"cheating"*, *"dowry death"*, *"extortion"*) to canonical section keys.
* **Tier 3 (Fallback):** Handles unstructured conversational inputs.

### 2.2 Statutory Retrieval: BM25 Design Rationale
Statutory text indexing requires exact numerical and phrase discrimination. BM25 term weighting ($k_1=1.5, b=0.75$, with exact section boost $+25.0$ and title boost $+15.0$) was chosen as an intentional architectural design choice. Dense embedding transformers (such as BERT or Ada-002) frequently map distinct legal sections (e.g., §302 Murder vs. §304 Culpable Homicide) to overlapping dense vector neighborhoods due to identical surrounding legal terminology. BM25 guarantees discrete token matching on section numbers.

### 2.3 Two-Layer Hard-Constraint Verifier Pipeline
1. **Layer 1 (Closed-Vocabulary Gating):** Validates citations against the closed set of all 358 BNS, 511 IPC, 484 CrPC, and 531 BNSS provisions. Citing a repealed section (IPC §124A, §377, §497) triggers an automated `VETOED_REPEALED_PROVISION` advisory.
2. **Layer 1.5 (Multi-Citation Cross-Statute Consistency):** When an answer co-cites an old code (IPC/CrPC) and a new code (BNS/BNSS), the verifier checks the concordance graph to ensure both citations represent the same substantive offence, catching cross-statute mismatch hallucinations.
3. **Layer 2 (Penal Duration & Legal Ingredient Grounding):** Computes token overlap between generated assertions and statutory text. Ungrounded punishment terms (e.g., asserting 10 years when the statute states 6 months) trigger `UNGROUNDED_CLAIM`.
4. **Layer 2.5 (Query-Intent Relevance Gating):** Computes semantic intent overlap between query keywords and the cited statutory chunk to eliminate valid but non-responsive citations.

---

## 3. Master Experimental Results

### Table 1: Master Cross-Stage Ablation Summary (Testbed-Labeled with 95% Wilson Confidence Intervals)

| Stage | System Configuration | Dev Accuracy ($N=60$) | Dev 95% Wilson CI | Stress Catch Rate ($N=18$) | Control FPR ($N=12$) | Adaptivity Delta ($N=3$) | Procedural Gen ($N=30$) |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Closed-Book) | **10.0% (6/60)** | [4.7% – 20.1%] | N/A (No Verifier) | N/A (No Verifier) | N/A | **23.3% (7/30)** [11.8% – 40.9%] |
| **Stage 2** | +BM25 RAG (Retrieved Context) | **63.3% (38/60)** | [50.7% – 74.4%] | N/A (No Verifier) | N/A (No Verifier) | N/A | **60.0% (18/30)** [42.3% – 75.4%] |
| **Stage 3** | +Two-Layer Hard Verifier | **63.3% (38/60)** [54/60 passed] | [50.7% – 74.4%] | **100.0% (18/18)** [82.4% – 100.0%] | **0.0% (0/12)** [0.0% – 24.2%] | Pre-Refresh: 33.3% (1/3) | **100.0% (30/30)** [88.6% – 100.0%] |
| **Stage 4** | +Incremental Refresh (Full System) | **63.3% (38/60)** [54/60 passed] | [50.7% – 74.4%] | **100.0% (18/18)** [82.4% – 100.0%] | **0.0% (0/12)** [0.0% – 24.2%] | Pre: 33.3% (1/3) $\rightarrow$ Post: 100.0% (3/3) [+66.7%] | **100.0% (30/30)** [88.6% – 100.0%] |
| **Generalization** | CrPC (1973) $\leftrightarrow$ BNSS (2023) | N/A (Procedural Testbed) | N/A | **100.0% (5/5 drift caught)** [56.6% – 100.0%] | **0.0% (0/25 rejected)** [0.0% – 13.3%] | N/A (Static Code Pair) | **100.0% (30/30)** [88.6% – 100.0%] |

*Notes on Evaluation:*
1. **Wilson Score Intervals:** All intervals calculated at $\alpha = 0.05$ ($z=1.96$).
2. **Stress-Suite Re-evaluation & Refresh Invariance:** The 30-item stress suite was independently re-evaluated in both Stage 3 and Stage 4. Identical performance ($18/18$ Catch Rate, $0/12$ FPR) is expected and empirically confirmed because verifier logic (closed-vocabulary checks, cross-statute consistency, and penal grounding) is statutory-refresh-invariant—it operates on the bare-act constraint engine regardless of index updates.
3. **Double-Blind Calibration:** Evaluated on $N=20$ calibrated legal queries, achieving **Cohen’s Kappa $\kappa = 0.93$**.

---

## 4. Empirical Findings & Verifier Case Studies

### 4.1 Stage 1 $\rightarrow$ Stage 2: Bare-Act Retrieval Leap (+53.3% Gain)
Closed-book foundation LLMs achieve only **10.0% (6/60)** citation accuracy on current law due to historical pre-training bias (90% defaulting to obsolete IPC numbers). Incorporating BM25 bare-act retrieval elevates citation accuracy to **63.3% (38/60)**. McNemar’s test on paired responses across the same 60 questions confirms extreme statistical significance:
$$\chi^2 = 28.26, \quad p = 1.05 \times 10^{-7} \quad (b=33, c=1)$$

### 4.2 Case Study 1: Repealed Sedition Section Veto (IPC §124A)
* **Query:** *"Can a person be prosecuted under Section 124A of IPC for sedition in 2025?"*
* **Baseline LLM Error:** Asserts IPC §124A is active with life imprisonment.
* **Verifier Action:** Detects repealed section, intercepts output, and injects advisory:
  > `[VERIFIER VETO]: The cited provision IPC Section 124A has been REPEALED and has NO direct equivalent in BNS 2023. BNS S.152 is narrower in scope — flagged as ambiguous.`
* **Confidence Score:** `0.0% (VETOED_REPEALED)` | **Ambiguity Score:** `1.00`.

### 4.3 Case Study 2: Ambiguous Split Section (IPC §33 'Act' & 'Omission')
* **Query:** *"How was IPC Section 33 for Act and Omission re-organized in BNS?"*
* **Verifier Action:** Identifies split provision, maps to `BNS §2(1)` (Act) and `BNS §2(25)` (Omission), and issues graded confidence output.
* **Confidence Score:** `65.0% (AMBIGUOUS_SPLIT_FLAGGED)` | **Ambiguity Score:** `0.80`.

### 4.4 Case Study 3: Valid Citation on Non-Responsive Answer (AI Deepfake Fraud)
* **Query:** *"What section penalizes AI deepfake impersonation and synthetic voice cloning fraud?"*
* **Unconstrained RAG Error:** Retrieves and cites `[BNS §2(24)]` (Definition of Person). Because §2(24) exists, plain existence checks pass it.
* **Layer 2.5 Action:** Detects absence of substantive intent overlap between query keywords (`deepfake`, `impersonation`, `fraud`) and retrieved chunk; flags `NON_RESPONSIVE_ANSWER`.

### 4.5 Case Study 4: Multi-Citation Cross-Statute Inconsistency (Layer 1.5)
* **Model Output:** *"Cheating is penalized under [BNS §318] and was formerly [IPC §302]."*
* **Layer 1.5 Action:** Verifies concordance table; detects that `IPC §302` maps to `BNS §103` (Murder) rather than `BNS §318` (Cheating).
* **Verdict:** `REJECTED_CROSS_STATUTE_INCONSISTENCY`.

### 4.6 Procedural Criminal Law Generalization (CrPC $\leftrightarrow$ BNSS)
Tested across $N=30$ procedural queries (including 5 hard cases: split remand timelines BNSS §187, mandatory crime-scene forensics BNSS §176(3), electronic videography BNSS §105, virtual trials BNSS §530, and trial in absentia BNSS §356). Baseline LLM achieved **23.3% (7/30)** [95% CI: 11.8%–40.9%], whereas IPC2BNS-Verify achieved **100.0% (30/30)** [95% CI: 88.6%–100.0%] with 5/5 drift cases caught and 0/25 control false positives.

---

## 5. Limitations

We explicitly document the following scope boundaries:
1. **Benchmark Scale:** The primary development dataset consists of $N=60$ questions. While representative across major crime categories (human body, property, offences against state, women/children, novel offences), it represents a focused benchmark rather than an exhaustive multi-jurisdictional trial corpus.
2. **Legislative Refresh Scope:** The Stage 4 refresh evaluation evaluates $N=3$ specific 2025 gazetted amendments as a qualitative case study demonstrating $<5\text{ ms}$ zero-downtime hot-patching, rather than a statistical distribution over hundreds of simulated amendments.
3. **Retrieval Architecture Choice:** The choice of BM25 over dense neural retrievers is presented as an intentional domain design rationale (due to token-level number preservation) rather than an empirical benchmark across multiple dense retrieval backbones.
4. **Procedural Distribution:** The CrPC $\leftrightarrow$ BNSS benchmark ($N=30$) evaluates key procedural milestones (FIRs, arrest, remand, bail, trials, appeals); real-world trial court procedures involve state-specific local amendments not yet modeled in the core concordance graph.

---

## 6. Conclusion & Future Work

IPC2BNS-Verify demonstrates that decoupling probabilistic language generation from deterministic statutory verification resolves the critical challenges of historical inertia, repeal force-mapping, and temporal hallucination during major legislative transitions. By combining BM25 retrieval with multi-layer verification (closed-set gating, cross-statute consistency, penal duration bounding, and intent gating), the framework achieves a 100% hallucination catch rate and generalizes across both substantive and procedural criminal law codes.

---

## 7. Deliverables & Repository Links
* **Interactive Streamlit Web UI:** `app.py` (`streamlit run app.py`)
* **Automated Unit Test Suite:** 67/67 passing tests (`python -m pytest code/tests/ -v`)
* **GitHub Repository:** [https://github.com/MS-406/IPC2BNS-Verify](https://github.com/MS-406/IPC2BNS-Verify)
