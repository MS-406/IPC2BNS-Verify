# IPC2BNS-Verify — Presentation Deck Notes

## Slide 1: Title & Overview
- **Title:** IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions
- **Context:** July 1, 2024 IPC (1860) $\rightarrow$ BNS (2023) & CrPC (1973) $\rightarrow$ BNSS (2023) Legal Overhaul
- **Domain:** Natural Language Processing (NLP), Legal IR, Neuro-Symbolic Verification

---

## Slide 2: The Problem: Legal LLM Hallucinations during Statutory Transitions
- 164 years of pre-training data dominated by historical IPC 1860 & CrPC 1973 texts.
- **Historical Inertia:** Out-of-the-box LLMs default to obsolete sections (**10.0% accuracy** on current law).
- **Repeal Force-Mapping:** Standard RAG force-maps repealed provisions (Sedition §124A, Adultery §497) into non-equivalent sections.
- **Valid Citations on Non-Responsive Answers:** Models retrieve valid sections that fail to answer the specific query.
- **Cross-Statute Inconsistencies:** Hallucinated co-citations across codes (e.g. IPC §302 Murder paired with BNS §318 Cheating).

---

## Slide 3: System Architecture
1. **Multi-Tier Query Normalizer:** Hierarchical regex ($<0.1\text{ ms}$) + domain offence ontology.
2. **Deterministic Concordance Graph:** Key-value hash lookup encoding exact, split, merged, and repealed mappings.
3. **BM25 Statutory Retrieval (Design Rationale):** Discretely indexes section numbers, avoiding dense vector collisions.
4. **Generative Answering:** Strict `[Act §Section]` citation extraction grammar.
5. **Two-Layer Hard-Constraint Verifier:**
   - *Layer 1:* Closed-vocabulary statutory ID gating & repeal veto directives.
   - *Layer 1.5:* Multi-citation cross-statute concordance consistency check.
   - *Layer 2:* Penal duration & legal ingredient grounding bounding.
   - *Layer 2.5:* Query-intent semantic relevance gating.
6. **Zero-Downtime Hot-Patch Refresh:** Dynamically updates indexes for newly gazetted amendments in $<5\text{ ms}$.

---

## Slide 4: Master Experimental Ablation Results (Testbed-Labeled)
- **Dev Set Accuracy ($N=60$):**
  - Stage 1 (Baseline LLM): 10.0% (6/60) [95% CI: 4.7%–20.1%]
  - Stage 2 (+BM25 RAG Context): 63.3% (38/60) [95% CI: 50.7%–74.4%] (McNemar’s paired test: $\chi^2 = 28.26, p = 1.05 \times 10^{-7}$)
  - Stage 3 (+Two-Layer Hard Verifier): 63.3% (38/60) [54/60 passed]
- **Injected-Errors Stress Suite ($N=30$):**
  - Adversarial Catch Rate ($N=18$): **100.0% (18/18)** [95% CI: 82.4%–100.0%]
  - Control False Positive Rate ($N=12$): **0.0% (0/12)** [95% CI: 0.0%–24.2%]
  - *Refresh Invariance:* Re-evaluated across Stage 3 and 4 with identical results.
- **Incremental Refresh Adaptivity ($N=3$):** Pre: 33.3% (1/3) $\rightarrow$ Post: 100.0% (3/3) in $<5\text{ ms}$.
- **Double-Blind Calibration:** Cohen’s Kappa $\kappa = 0.87$ across $N=20$ calibrated legal test queries (95.0% concordance).
- **Scale Evaluation (Phase 7, $N=1,140$):** 94.4% adversarial catch rate across 10 categories; revealed BM25 retrieval bottleneck on procedural queries (Recall@5: 30.4%).

---

## Slide 5: Live Interactive Streamlit Showcase (`app.py`) for Viva
- **Live 5-Step Pipeline Inspection:** Normalizer $\rightarrow$ Concordance $\rightarrow$ BM25 Retrieval $\rightarrow$ Generation $\rightarrow$ Verifier.
- **Sedition Repeal Interception (IPC §124A):** Live demonstration of automated verifier veto.
- **Split Section Ambiguity Breakdown:** Graded confidence outputs on IPC §33 $\rightarrow$ BNS §2(1) & §2(25).
- **Zero-Downtime Amendment Toggle:** Real-time hot-patch demonstration.
- **Automated Verification:** 67/67 unit tests passing in $0.27\text{s}$.
