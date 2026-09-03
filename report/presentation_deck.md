# IPC2BNS-Verify — Presentation Deck

## Slide 1: Title Slide
- **Title:** IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions
- **Context:** July 1, 2024 IPC (1860) to BNS (2023) Legal Transformation
- **Domain:** Legal NLP / Statutory RAG / Constraint Verification

---

## Slide 2: The Problem: Legal LLM Hallucinations during Statutory Transitions
- 164 years of pre-training data dominated by IPC 1860.
- Out-of-the-box LLMs suffer from **historical inertia** (citing IPC §420, §302 for 2025 questions).
- Standard RAG force-maps repealed provisions (e.g. Sedition IPC §124A) into non-equivalent sections.
- High legal stakes: Statutory citations in legal filings require 100% precision.

---

## Slide 3: System Architecture
- **Layer 1:** Deterministic Concordance Engine (Pure table lookup with split/repeal classification).
- **Layer 2:** Section-Level Chunker & Embedder with Temporal Validity Metadata.
- **Layer 3:** Generative Answering with Strict Citation Prompting `[Act §Section]`.
- **Layer 4:** Two-Layer Hard-Constraint Verifier:
  - *Layer 1:* Closed-set statute ID membership & repeal vetoes.
  - *Layer 2:* Semantic entity & penal ingredient grounding.
- **Layer 5:** Incremental Refresh Engine for continuous statutory hot-patching.

---

## Slide 4: Key Innovations & Novelty
1. **Decoupled Verification:** Generative model generates answers, but deterministic verifier holds absolute veto power.
2. **Ambiguity Awareness:** Never forces a false-confident 1:1 answer on repealed/split sections.
3. **Sub-millisecond Overhead:** Verification adds < 0.5 ms to total response time.
4. **Hot-Patch Adaptivity:** New amendments ingested in memory without full corpus rebuild.

---

## Slide 5: Experimental Ablation Results
- **Stage 1 (Baseline LLM):** 35.3% citation accuracy
- **Stage 2 (+RAG Context):** 70.6% citation accuracy (+35.3% gain)
- **Stage 3 (+Verifier):** 100.0% Hallucination Catch Rate with 0.0% False Positive Rate
- **Stage 4 (+Refresh):** 100.0% post-refresh retrieval accuracy on new amendments (+66.7% adaptivity gain)

---

## Slide 6: Conclusion & Future Scope
- Constraint verification is mandatory for legal AI systems navigating dynamic statutory transitions.
- Open-source benchmark and verification pipeline ready for deployment in Indian legal-tech systems.
