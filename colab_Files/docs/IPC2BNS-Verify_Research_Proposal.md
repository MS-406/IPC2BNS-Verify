# IPC2BNS-Verify: A Lightweight, Verifier-Guarded RAG Framework for Adaptive Statutory Question Answering in the Indian Criminal Law Transition

*(Short title: "Verified and Adaptive: A RAG Framework for IPC-to-BNS Statutory Question Answering")*

---

## Abstract

On 1 July 2024, the Bharatiya Nyaya Sanhita (BNS) 2023 replaced the 163-year-old Indian Penal Code (IPC) 1860, reorganizing 511 sections into 358 with no one-to-one number carryover. This creates a live, high-stakes retrieval problem: legal professionals, police, and citizens must now determine which code applies (IPC for pre-transition conduct, BNS for post-transition conduct), what a given IPC section now maps to, and whether an AI-generated citation is real. Existing work addresses pieces of this problem in isolation — hard-constraint citation verification (Falkor-IRAC), temporal-validity filtering for statute retrieval (TaxFlow), and IPC/BNS-specific baseline LLM comparison (LegalEase) — but no published system combines (1) a deterministic IPC↔BNS section mapping layer, (2) a hard-constraint hallucinated-citation verifier, (3) end-to-end generative RAG evaluation, and (4) a measured before/after accuracy delta across a simulated corpus refresh, evaluated together as an ablation. This proposal describes IPC2BNS-Verify, a system and evaluation framework that fills this gap and quantifies, component by component, how much each addition (retrieval, verification, refresh-awareness) reduces citation error on a fixed statutory question-answering benchmark.

---

## 1. Research Gap and Motivation

- The IPC→BNS transition is not a simple renumbering: sections were merged, split, renamed, or newly introduced (e.g., IPC §124A "sedition" has no direct BNS counterpart and is instead addressed, narrower in scope, by BNS §152). A lookup-only tool cannot flag this kind of ambiguous case; a generative system without verification can confidently fabricate an answer.
- Independent empirical work already shows two separate risks this project must guard against:
  - Even commercial RAG-grounded legal research tools are not hallucination-free — a peer-reviewed study found leading tools hallucinate materially often despite RAG grounding.
  - Generic semantic-similarity-based hallucination checks tolerate entity substitutions that preserve meaning but introduce material legal errors — motivating a **hard, set-membership verifier** over a closed, versioned list of valid section IDs, rather than a soft/semantic check.
- The IPC↔BNS mapping space today is served entirely by static, non-generative lookup tools (converter apps and websites). None of them are wired into a generative RAG pipeline, and none report hallucination or accuracy metrics. This is the concrete, checkable gap this project fills.

**Research Questions**
- **RQ1:** Does a hard-constraint citation verifier measurably reduce fabricated-section-citation rate compared to RAG-only generation?
- **RQ2:** Does a deterministic table-lookup mapping module outperform LLM-generated IPC↔BNS mapping in accuracy and consistency?
- **RQ3:** How much does end-to-end answer accuracy change after a simulated corpus refresh (e.g., a correction or amendment), before vs. after the verifier and retrieval index are updated?

---

## 2. What Should Be Done (Methodology / System Architecture)

### 2.1 Deterministic IPC↔BNS Concordance Module
- Build a hand-curated, versioned lookup table (IPC section → BNS section, and reverse) sourced from official/near-official concordance tables (see Data Sources).
- Use a small LLM or rule-based normalizer only to convert free-text queries ("what's the new section for cheating?") into canonical section numbers before table lookup — the mapping itself should **not** be LLM-generated, to avoid inheriting hallucination risk in the one component that should be ground-truth-exact.
- Explicitly flag non-1:1 cases (splits, merges, repeals like §124A) as "ambiguous — requires legal review" rather than forcing a false-confident single answer. This is your most defensible novelty point.

### 2.2 Retrieval Layer
- Chunk BNS/IPC bare-act text at the section (not paragraph) level, since statute retrieval is a structured, not prose, retrieval problem.
- Use a legal-domain or multilingual embedding model (see Section 3) to reduce Document-Level Retrieval Mismatch, a documented failure mode in long, structured Indian legal texts.

### 2.3 Generation Layer
- Prompt a strong general-purpose LLM (see Section 3) to answer statutory questions using only retrieved chunks, with citations required in a fixed format (Act, Section, chunk ID).

### 2.4 Verifier Module (hallucination gate)
- Hard veto: any generated citation must exist in the closed, versioned section-ID index; if not, the answer is rejected/flagged rather than returned.
- Optional secondary check inspired by knowledge-graph alignment methods: verify that entities in the answer (section numbers, offence names, punishment terms) actually appear in the retrieved source, catching entity-substitution errors that a citation-existence check alone would miss.

### 2.5 Adaptivity / Refresh Handler
- Tag each retrieved chunk with an effective-date range (borrowing the "temporal validity filtering" concept from tax-law RAG work).
- Simulate a corpus refresh by deliberately injecting a small number (e.g., 20–30) of known section amendments/corrections into the index, then re-running the fixed question set to measure the accuracy delta before vs. after refresh. This is more tractable for a student timeline than a live longitudinal deployment.

### 2.6 Evaluation Design (the ablation table — this is your core contribution)
Run the same fixed question set through four progressively richer configurations and report citation-existence accuracy, end-to-end answer correctness, retrieval precision/recall, and (for stage 4) the refresh delta:

| Stage | Configuration |
|---|---|
| 1 | Baseline LLM, no retrieval |
| 2 | + RAG (retrieval only, no verifier) |
| 3 | + Hard-constraint verifier |
| 4 | + Verifier + simulated corpus refresh |

---

## 3. What to Use (Tools, Models, Stack)

| Component | Recommended choice | Why |
|---|---|---|
| Mapping module | Rule-based/regex table lookup (no LLM for the core mapping) | Ground-truth exactness; matches how existing production tools already do this reliably |
| Query normalizer | Small/cheap LLM (e.g., a lightweight instruction-tuned model) | Only needed to convert free text into a canonical section number |
| Embedding model | A legal-domain or multilingual embedding model, evaluated against a general-purpose embedder as a baseline | Retrieval quality sets the ceiling on RAG accuracy; embedder choice has the single largest measured impact in prior legal RAG benchmarking |
| Generator LLM | A frontier general-purpose model (Claude, GPT-4/5-class, or Gemini) | Weak retrieval + weak generation compounds error; a strong general LLM paired with a domain embedder is the realistic top-tier stack for a project this scoped |
| Verifier | Deterministic set-membership check against your versioned section-ID index, with an optional lightweight entity-grounding check | Hard constraints are cheaper and more precise than agentic or semantic-similarity verification for a bounded, finite-label domain like BNS (358 sections) |
| Evaluation | LLM-as-a-judge (calibrated against a human-reviewed subsample), plus exact-match citation-existence scoring | Matches the methodology used in the closest prior India-specific work, enabling direct comparison |
| Infrastructure | Any standard RAG stack (vector DB + orchestration); a knowledge-graph store (e.g., Neo4j/FalkorDB) only if you extend to multi-hop precedent reasoning beyond section lookup | Graph stores add value mainly for citation-path verification across cases, not for flat statute lookup |

---

## 4. Data Sources

### Statute text (ground truth for mapping and retrieval)
- **India Code** (indiacode.nic.in) — the Government of India's official repository of central acts, the authoritative source for BNS 2023 and IPC 1860 full text.
- **Official/near-official concordance tables** — e.g., the BNS-to-IPC correspondence table prepared for police training academies (Kerala Prisons Dept. publication by A. K. Yadav, IPS) gives section-by-section mapping with a "summary of comparison" column distinguishing exact matches, renumbered sections, and genuinely new provisions — a strong seed for your ground-truth table and for labeling ambiguous (non-1:1) cases.
- **Structured BNS dataset (CSV)** — a web-scraped BNS dataset (IEEE DataPort, chapter/section_title/section_content columns) usable as a ready-made structured source for chunking, though it should be cross-checked against India Code for accuracy before use as ground truth.

### Case law / citation-grounding corpora (for the generative RAG and verification legs)
- **IndianKanoon** (indiankanoon.org) — the primary public search engine for Indian judgments, sourced originally from indiacode.nic.in and judis.nic.in; used as the scraping source for nearly every academic Indian-legal-NLP dataset below.
- **IL-PCSR** (Indian Legal corpus for Prior Case and Statute Retrieval) — 936 statutes/sections from 92 central acts plus 3,183 Supreme Court cases, purpose-built as a joint statute-and-precedent retrieval testbed; closest existing academic dataset structurally to what your statute-retrieval evaluation needs.
- **IL-PCR** (Indian Legal Prior Case Retrieval corpus) — 7,070 case texts with ~8,000 citation links, usable for citation-accuracy benchmarking methodology.
- **ILSI dataset** (from the LeSICiN paper) — ~66,000 fact excerpts labeled with the 100 most frequently cited IPC sections; a ready-made source of realistic IPC-citing query text you can adapt into BNS-era questions.

### Hallucination/verification benchmarking methodology (adapt, don't reuse directly — none are India-specific)
- **LePhantomCite** — a benchmark of real court-filing excerpts with injected citation errors, useful as a template for how to construct your own "known error injection" test set for the verifier module.
- **HalluGraph** methodology (entity grounding / relation preservation metrics) — adapt as your secondary, finer-grained verification metric beyond simple citation-existence.

### Practical/commercial reference (not for ground truth, but for cross-checking and scope calibration)
- Public IPC↔BNS converter tools (e.g., ipc2bns.in, Vakeel Saathi, LawCentral, Vakeel360) — all static lookup tools; useful to sanity-check your own mapping table against, and to cite as evidence that no existing public tool combines mapping with generative verification.

---

## 5. Suggested Timeline (semester-scale project)

1. **Weeks 1–3:** Build deterministic mapping module + ground-truth table (cross-check India Code against the Kerala Prisons concordance table); flag all non-1:1 cases.
2. **Weeks 4–6:** Build retrieval + baseline RAG pipeline; construct fixed question set (adapt from ILSI-style fact excerpts, updated to BNS-era phrasing).
3. **Weeks 7–9:** Implement hard-constraint verifier; run Stage 1–3 ablation; collect citation-existence and answer-correctness metrics.
4. **Weeks 10–12:** Design and inject simulated corpus refresh; run Stage 4; compute before/after delta.
5. **Weeks 13–14:** Human-reviewed subsample for LLM-as-judge calibration; write up results, limitations, and discussion (especially the ambiguous-mapping cases as a qualitative finding).

---

## 6. Limitations to State Up Front

- Benchmark size will be small (hundreds, not thousands, of Q&A pairs) — frame results as a controlled proof-of-concept, consistent with how Falkor-IRAC scoped its own 51-case evaluation.
- LLM-as-judge introduces its own bias; a human-reviewed subsample is necessary for credibility.
- The simulated refresh is a controlled substitute for a real, live corpus update — state this explicitly rather than implying longitudinal deployment testing.
