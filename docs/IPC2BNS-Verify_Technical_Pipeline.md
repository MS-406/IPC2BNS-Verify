# IPC2BNS-Verify: Full Technical Implementation Document

This document is the engineering companion to the research proposal. It breaks the system into codeable phases, specifies exact models/libraries per phase, defines what "done" looks like at each stage, and explains how to turn the output into a defensible research write-up.

---

## 0. System Overview

```
                        ┌─────────────────────────┐
   User query  ───────▶ │  Query Normalizer (LLM)  │
                        └────────────┬─────────────┘
                                     │  canonical section no. / free-text query
                    ┌────────────────┼─────────────────┐
                    ▼                                   ▼
        ┌───────────────────────┐            ┌───────────────────────┐
        │ Deterministic Mapping │            │   Retrieval Layer      │
        │ Module (IPC ⇄ BNS)    │            │ (embeddings + vector DB)│
        └───────────┬───────────┘            └───────────┬────────────┘
                    │                                     │
                    ▼                                     ▼
        ┌───────────────────────────────────────────────────────────┐
        │              Generator LLM (answers from retrieved chunks) │
        └───────────────────────────┬───────────────────────────────┘
                                    ▼
                        ┌───────────────────────┐
                        │   Verifier / Hallu-    │
                        │  cination Gate         │
                        └───────────┬───────────┘
                                    │  pass / reject / flag-ambiguous
                                    ▼
                        ┌───────────────────────┐
                        │   Final Answer + Cited │
                        │   Section(s) + Status  │
                        └───────────────────────┘

        (Offline, parallel) Corpus Refresh Simulator ──▶ re-indexes + re-runs eval
```

Four independently testable modules (Mapping, Retrieval, Generation, Verifier) plus one evaluation harness that runs all four in the ablation configurations. Build and unit-test each module in isolation before wiring them together — this is what makes your later ablation table credible (you can prove each component in isolation works before measuring its marginal contribution).

---

## 1. Repository Structure (suggested)

```
ipc2bns-verify/
├── data/
│   ├── raw/                  # scraped/downloaded source text (India Code, IndianKanoon)
│   ├── concordance/          # ground-truth IPC<->BNS mapping table (CSV/JSON)
│   ├── benchmark/            # your fixed Q&A test set
│   └── refresh_sim/          # injected "amendment" cases for adaptivity test
├── src/
│   ├── mapping/               # Phase 1
│   ├── ingestion/              # Phase 2
│   ├── retrieval/              # Phase 3
│   ├── generation/             # Phase 4
│   ├── verifier/                # Phase 5
│   ├── refresh/                  # Phase 6
│   └── eval/                      # Phase 7-8
├── notebooks/                # exploratory analysis, error analysis
├── configs/                  # model/pipeline configs per ablation stage
├── results/                  # raw outputs + metrics per stage, per run
└── report/                   # write-up, tables, figures
```

---

## 2. Coding Phases

### Phase 0 — Environment & Ground Truth Setup (Week 1)
**Build:**
- Project scaffolding, config system (so you can swap models/stages via a YAML/JSON config, not code edits).
- Download and clean BNS + IPC bare-act text from India Code (indiacode.nic.in).
- Digitize the ground-truth concordance table (e.g., the Kerala Prisons/CAPT Bhopal correspondence table) into a structured CSV: `ipc_section, bns_section, relationship_type (exact | renumbered | split | merged | repealed | new), notes`.

**Output:** a versioned `concordance_v1.csv` — this is your single most important artifact; almost everything else depends on it being right.

**Done when:** every IPC section 1–511 has a row, and every ambiguous case (splits, merges, repeals like §124A) is explicitly labeled, not silently mapped.

---

### Phase 1 — Deterministic Mapping Module (Week 2)
**Build:**
- A pure lookup function: `map_ipc_to_bns(section: str) -> MappingResult` and reverse, reading from `concordance_v1.csv`. No LLM involved here.
- A query normalizer: small LLM call that extracts a section number or offence keyword from free text ("what happened to the old cheating section?") and calls the lookup function.

**Models to use:** any cheap/fast instruction model for normalization only (this doesn't need a frontier model — it's a simple extraction task). Do **not** let an LLM generate the mapping itself.

**Metric to report:** mapping accuracy = exact match against ground truth on a held-out sample of section queries. **Target:** should be ~99–100% since it's deterministic — if it's not hitting that, the bug is in your normalizer, not the mapping.

---

### Phase 2 — Corpus Ingestion & Chunking (Weeks 2–3)
**Build:**
- Section-level chunker for BNS/IPC bare-act text (chunk boundary = statutory section, not paragraph or fixed token count — this matters more for statutes than for prose).
- Metadata tagging per chunk: `act (IPC/BNS), section_number, chapter, effective_date_range`.
- Ingestion script for case-law corpora if you're extending beyond pure statute lookup into judgment-grounded QA (optional, see Phase 4b).

**Data sources to pull from:**
- India Code (bare act text)
- IL-PCSR / IL-PCR (if using case law for judgment-grounded questions)
- ILSI dataset (as a source of realistic fact-pattern queries to convert into your benchmark)

**Done when:** every chunk has an unambiguous `section_number` you can check citations against later — this is what your verifier will use as its ground-truth ID set.

---

### Phase 3 — Retrieval Layer (Week 3–4)
**Build:**
- Embed all chunks with your chosen embedding model; store in a vector DB.
- Retrieval function returning top-k chunks per query.

**Models/tools to use:**
- **Vector DB:** FAISS (simplest, local, free) or Chroma if you want persistence + metadata filtering out of the box. Pinecone/Weaviate only if you need managed hosting.
- **Embedding model:** run at least two for comparison — a strong general-purpose embedder (e.g., OpenAI text-embedding-3-large, or Voyage AI's legal/general embedder) as your primary, and a general open-source embedder (e.g., BGE-large or E5-large) as a cheaper baseline. If you can get access, a legal-domain embedder (Isaacus Kanon 2) is worth benchmarking since it's shown the largest measured impact in prior legal RAG evaluation — but a strong general embedder is a perfectly defensible fallback if access/cost is a constraint.
- **Orchestration:** LangChain or LlamaIndex will save you boilerplate for chunking + retrieval wiring, but a hand-rolled retrieval loop is equally fine and easier to debug for a project this scoped — don't over-invest in framework plumbing.

**Metric to report:** retrieval precision@k and recall@k against your fixed question set (does the correct section appear in the top-k retrieved chunks?). **Target to beat:** prior India-specific work reports ~95% retrieval accuracy on IPC/BNS text with a fine-tuned pipeline — treat that as your ceiling to compare against, not a guaranteed floor.

---

### Phase 4 — Generation Layer (Week 4–5)
**Build:**
- Prompt template that forces the model to answer only from retrieved chunks, with a strict citation format: `[Act §Section]`.
- Fallback behavior when retrieval returns nothing relevant ("I cannot find a matching provision" rather than guessing).

**Models to use:** a frontier general-purpose LLM — Claude, GPT-4/5-class, or Gemini. Run your **baseline** (Stage 1: no retrieval, model answering from parametric knowledge alone) with the same model so the ablation isolates the effect of retrieval, not a model swap.

**Done when:** you have raw generation output for every question in your benchmark, for Stage 1 and Stage 2 configurations, saved with full prompt + response logs (you'll need these for error analysis and for the verifier).

#### Phase 4b (optional extension) — Judgment-grounded generation
If you want the "generative end-to-end" leg to go beyond flat section lookup into judgment reasoning, add a retrieval branch over case law (IL-PCSR/IL-PCR) and extend the prompt to synthesize statute + precedent. This is a real scope expansion — only take it on if Phases 1–3 are solid and you have time left.

---

### Phase 5 — Verifier / Hallucination Gate (Weeks 5–6) — the core novel feature
This is the component your whole framing rests on. Build it in two layers:

**Layer 1 — Hard citation-existence check (mandatory, build first):**
- After generation, extract every cited section from the model's output (regex on your fixed citation format is fine here since you control the prompt).
- Check each citation against your closed, versioned section-ID index from Phase 2.
- If a citation doesn't exist in the index → reject the answer or flag it `UNVERIFIED`, don't silently pass it through.
- This mirrors Falkor-IRAC's "Verifier Agent" pattern — a hard veto rather than a soft nudge.

**Layer 2 — Entity-grounding check (optional, stronger signal):**
- For each citation that *does* exist, check whether the specific claim made about it (offence name, punishment, ingredients) actually appears in the retrieved chunk text — catching the subtler error of citing a real section but misdescribing it.
- Adapt the entity-grounding / relation-preservation idea from knowledge-graph-alignment hallucination-detection work: extract key entities (section number, offence term, punishment figure) from both the retrieved chunk and the generated answer, and score overlap. This can be done without a full KG — simple entity extraction + set comparison is enough for a project at this scale.

**Models/tools:** Layer 1 needs no model at all (pure string/set matching — deliberately cheap and fast). Layer 2 can use a small LLM call or a NER library (spaCy) for entity extraction — avoid an expensive agentic multi-step verifier; prior benchmarking shows agentic verification is accurate but resource-heavy (15+ steps per check in published results), which isn't worth it for a bounded 358-section domain.

**Metric to report:** hallucination catch rate = % of deliberately injected fake/wrong citations correctly flagged (see Phase 8 for how to construct this test set), plus false-positive rate (real, correct citations wrongly flagged).

**Target:** your hard-constraint Layer 1 should approach ~100% catch rate for citations that reference a section number outside the valid set (that's a solved string-matching problem). The harder, more interesting number is Layer 2's catch rate for "cites a real section but says something wrong about it" — expect this to be meaningfully lower and to be a genuine result worth reporting, not something you need to force above a target.

---

### Phase 6 — Adaptivity / Refresh Simulation (Week 7)
**Build:**
- Pick 20–30 known section changes (use ambiguous/edge cases from your concordance table — merges, splits, the §124A→§152 case).
- Create a "pre-refresh" index snapshot with old/incomplete mapping data, and a "post-refresh" snapshot with corrected data.
- Re-run your full fixed question set (or the subset touching these sections) through the pipeline on both snapshots.

**Metric to report:** the refresh delta — accuracy and hallucination-catch-rate before vs. after refresh, on the affected question subset. This is your most novel empirical result; report it as a paired comparison (same questions, two index states), not just two separate numbers.

---

### Phase 7 — Evaluation Harness (Weeks 6–8, built alongside Phases 4–6)
**Build:**
- A single script that runs the full fixed benchmark through any of the four ablation configurations (set via config file) and outputs a standardized results table.
- Metrics computed per stage: citation-existence accuracy, end-to-end answer correctness, retrieval precision/recall, hallucination catch rate (stage 3+), refresh delta (stage 4).

**Judging method:**
- **LLM-as-judge:** use a strong model (can be the same generator model or a different one to avoid self-preference bias) to score answer correctness against a reference answer, on a rubric (correct / partially correct / incorrect / hallucinated).
- **Human calibration:** manually review a random 10–15% subsample yourself (or with a peer) and compute agreement with the LLM judge. Report this agreement rate — it's what makes your LLM-as-judge numbers credible rather than circular.

---

### Phase 8 — Ablation Experiments & Error Injection (Week 8–9)
**Build:**
- Run all four stages on the full benchmark; log everything to `results/`.
- Construct a small injected-error test set specifically for the verifier: take real questions, deliberately swap in wrong/fake section numbers or plausible-but-wrong offence descriptions, and confirm the verifier catches them (adapt the injected-error methodology from citation-hallucination benchmarking work — you don't need their exact dataset, just their method of deliberately corrupting known-correct examples).

**Output:** your core results table —

| Stage | Citation-Existence Acc. | Answer Correctness | Retrieval P@k / R@k | Hallucination Catch Rate | Notes |
|---|---|---|---|---|---|
| 1. Baseline LLM | | | n/a | n/a | |
| 2. +RAG | | | | n/a | |
| 3. +Verifier | | | | | |
| 4. +Verifier+Refresh | | | | | refresh delta reported separately |

---

### Phase 9 — Write-Up (Weeks 9–10)
- Structure per the outline in the earlier research proposal document (Intro → Related Work → RQs → Architecture → Dataset → Experiments → Results → Discussion → Limitations → Conclusion).
- Lead with the ablation table as your central figure.
- Discuss failure cases qualitatively — especially the ambiguous mapping cases (§124A→§152, merges/splits) — these make for a strong discussion section because they show where a purely mechanical system *should* defer to human judgment rather than force an answer.

---

## 3. How to Make This Proper Research (not just an engineering project)

1. **State falsifiable hypotheses up front** (RQ1–RQ3 from the proposal doc) and design each phase to answer one of them — don't just build the system and retrofit questions afterward.
2. **Always compare against a baseline you also ran yourself**, not just against numbers quoted from other papers — your Stage 1 (no-retrieval LLM) baseline, run on your own benchmark, is what makes your Stage 2–4 improvements credible.
3. **Report negative/null results honestly.** If the verifier's false-positive rate is higher than expected, or the refresh delta is smaller than hoped, report it — that's still a real finding and reviewers/evaluators respect it far more than an artificially clean table.
4. **Use a held-out test split.** Don't tune your prompts or verifier thresholds on the same questions you report final numbers on — split your benchmark into a dev set (for iteration) and a test set (reported once, at the end).
5. **Make it reproducible.** Fixed random seeds, versioned config files per experiment, and a `results/` folder that maps 1:1 to your results table rows.
6. **Cite your closest prior work precisely and compare numbers where possible** (Falkor-IRAC's verifier pattern, the Domain-Partitioned Hybrid RAG paper's 70% vs 37.5% pass-rate result, the offline RAFT paper's ~95% retrieval accuracy) — direct numerical comparison, even if not perfectly apples-to-apples, is what turns "I built a system" into "I built a system that measurably improves on X."

---

## 4. How to Improve It Further (once the core pipeline works)

- **Add multi-hop reasoning** (Phase 4b) — statute + precedent grounded answers, not just flat section lookup, using IL-PCSR.
- **Expand the verifier to CrPC↔BNSS and Evidence Act↔BSA** — the same architecture generalizes to India's other two 2023 code replacements, which would meaningfully broaden the contribution.
- **Add a confidence/ambiguity score** to the verifier output instead of a binary pass/reject — for cases like split/merged sections, a graded "high confidence / needs review / ambiguous" output is more legally honest than forcing binary accept/reject.
- **Run a small user study** (even 5–10 law students) comparing task completion accuracy with vs. without the verifier — this adds a human-in-the-loop result on top of your automated metrics, which strengthens the "this matters practically" argument considerably.

---

## 5. Quick Model/Tool Reference Sheet

| Need | Recommended | Budget alternative |
|---|---|---|
| Generator LLM | Claude / GPT-4/5-class / Gemini (frontier) | Any capable open model (Llama-3-70B class) if compute-constrained |
| Embedding model | Domain/legal embedder if accessible, else strong general embedder (text-embedding-3-large, Voyage) | BGE-large / E5-large (open-source) |
| Vector DB | Chroma (local, metadata filtering) | FAISS (simplest, no server) |
| Query normalizer | Small/cheap LLM | Rule-based regex if query phrasing is constrained enough |
| Verifier Layer 1 | Pure Python set-membership check | — (already free) |
| Verifier Layer 2 | Small LLM call for entity extraction | spaCy NER (fully local, no API cost) |
| Orchestration | LangChain / LlamaIndex | Hand-rolled Python (more debuggable at this scale) |
| Evaluation judge | Strong LLM-as-judge + human-reviewed subsample | Human-only scoring if budget-constrained (smaller benchmark) |
