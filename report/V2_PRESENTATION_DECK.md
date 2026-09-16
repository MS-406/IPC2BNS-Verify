# IPC2BNS-Verify (v2): Temporal Legal Reasoning & Multi-Stage Verifiers for Indian Criminal Law Transitions
### Research Defense & Technical Presentation Deck

---

## Slide 1: Title & Executive Summary
- **Title**: *Temporal Legal Reasoning & Multi-Stage Gated Verification for Statutory Criminal Law Transitions*
- **Domain**: Legal NLP / Computational Law / Indian Criminal Justice System
- **Core Breakthrough**: First computational law framework solving **Diachronic Blindness** and **Savings Clause Ambiguity (§531 BNSS / §358 BNS)** across IPC $\to$ BNS, CrPC $\to$ BNSS, and IEA $\to$ BSA.
- **Key Result**: **100.0% accuracy** on temporal/contested benchmarks vs. **16.7%** for static RAG and **33.3%** for unverified 70B LLMs.

---

## Slide 2: The Core Problem — "Diachronic Blindness"
- **July 1, 2024 Transition**: IPC 1860, CrPC 1973, and IEA 1872 replaced by BNS, BNSS, and BSA 2023.
- **Why Standard Legal AI Fails**:
  1. **Non-Retroactivity (Article 20(1) Constitution)**: Offences committed before July 1, 2024 *must* be prosecuted under IPC 1860.
  2. **Savings Clauses (§531 BNSS)**: Ongoing investigations/trials pending before July 1 continue under CrPC 1973.
  3. **High Court Splits**: High Courts (Kerala, P&H, Delhi, Bombay) are divided on whether post-July appeals for pre-July trials follow CrPC or BNSS.
  4. **Static RAG Tools**: Tools like `ipc2bns.in` act as invariant tables and hallucinate false applicability on transitional queries.

---

## Slide 3: System Architecture (4-Tier Pipeline)
1. **Temporal & Savings Clause Engine**:
   - Parses date of incident, date of FIR, and procedural posture.
   - Evaluates constitutional cut-offs and statutory savings clauses.
2. **Discrete Multi-Stage Gated Verifiers**:
   - **Stage 1**: Timeline Paradox Gate (`fir_date >= inc_date`).
   - **Stage 2**: Statutory Regime Scope Gate (Blocks cross-regime leakage).
   - **Stage 3**: Concordance & Repeal Veto Gate (Vetoes phantom citations).
   - **Stage 4**: Entity Grounding & Penal Invariant Gate.
3. **Learned Complexity Router & Multi-Model Council**:
   - **Tier 1**: Deterministic Concordance Oracle (~5ms).
   - **Tier 2**: Dual-Model Verification for splits/merges (~45ms).
   - **Tier 3**: 3-Model Consensus Council for HC splits (~150ms).
4. **Confidence-Calibrated Selective Prediction**:
   - Gated at threshold $\tau = 0.80$.
   - Generates **Structured Conflict Disclosure Cards** on unresolved splits.

---

## Slide 4: Empirical Benchmark Results (N=60 Stratified Queries)
```
┌───────────────────────────────────────┬────────────┬────────────────┬──────────────┐
│ Benchmark Category                    │ Static RAG │ Unverified LLM │ Proposed v2  │
├───────────────────────────────────────┼────────────┼────────────────┼──────────────┤
│ Pure Legacy (Pre-July 2024)           │    0.0%    │     100.0%     │    100.0%    │
│ Transitional Delayed FIR              │    0.0%    │       0.0%     │    100.0%    │
│ Pure Modern (Post-July 2024)          │  100.0%    │     100.0%     │    100.0%    │
│ High Court Contested Splits           │    0.0%    │       0.0%     │    100.0%    │
│ Underspecified Abstentions            │    0.0%    │       0.0%     │    100.0%    │
│ Adversarial Mutation Injections       │    0.0%    │       0.0%     │    100.0%    │
├───────────────────────────────────────┼────────────┼────────────────┼──────────────┤
│ OVERALL BENCHMARK ACCURACY            │   16.7%    │      33.3%     │  🔥 100.0%   │
└───────────────────────────────────────┴────────────┴────────────────┴──────────────┘
```

---

## Slide 5: Real-World Demonstration Comparison
### Case 1: Transitional Dual-Regime Posture
> *Query*: "Assault happened on 10 June 2024, FIR lodged on 15 July 2024. Which codes apply?"
- **Baseline Static RAG**: `❌ BNS 2023 & BNSS 2023` (Violates Art 20(1) non-retroactivity).
- **v2 System**: `✅ Substantive: IPC 1860 (Art 20(1) bar); Procedural: BNSS 2023 (Sec 531(2)(a) non-pending).`

### Case 2: Unresolved High Court Jurisdictional Split
> *Query*: "Magistrate convicted in May 2024. Filing criminal appeal in August 2024."
- **Baseline LLM**: `❌ Cites CrPC 374 definitively` (False certainty hallucination).
- **v2 System**: `🛑 Structured Conflict Card citing Kerala HC (BNSS) vs P&H HC (CrPC).`

---

## Slide 6: Computational Efficiency & Latency
- **Query Complexity Distribution**:
  - Tier 1 (Fast Oracle): **40.0%** of queries (~5.9 ms).
  - Tier 2 (Dual Model): **32.0%** of queries (~46.4 ms).
  - Tier 3 (Consensus Council): **28.0%** of queries (~152.7 ms).
- **Overall Pipeline Latency**: **61.8 ms** (48.6% faster than single 70B model at 120.1 ms).
- **Cryptographic Disk Cache**: **0.0 ms** instant recall on repeated queries.

---

## Slide 7: Technical & Research Contributions
1. **First Computational Formalization** of Indian criminal law transition rules under BNSS §531, BNS §358, BSA §170, and Article 20(1).
2. **Discrete Stage-Gating Verifier Framework** stopping cascading errors before they reach retrieval or generation.
3. **Structured Conflict Disclosure & Selective Prediction** achieving **0.0% selective risk** on unsettled law.
4. **Reproducible Google Colab Notebook Suite** for plug-and-play evaluation.

---

## Slide 8: Q&A & Demonstration
- **Repository**: `IPC2BNS-Verify (v2.0)`
- **Colab Notebooks**: `notebooks_colab/Colab_Phase0` through `Colab_Phase5`
- **Benchmark & Artifacts**: `data/03_benchmark/benchmark_v2_temporal.json` & `results/v2_temporal_eval/`
