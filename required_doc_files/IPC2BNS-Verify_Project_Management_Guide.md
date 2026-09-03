# IPC2BNS-Verify: Project Management & Delivery Guide

A manager-facing companion to the research proposal and technical pipeline docs. This answers: what documents do you need to track, what tasks need doing, what's the overall shape of the project, how do you check for plagiarism, and how do you generalize the system beyond IPC/BNS.

---

## 1. Documents You Need (full list, in the order you'll create them)

| # | Document | Purpose | When |
|---|---|---|---|
| 1 | **Project Charter / Proposal** (you have this — `IPC2BNS-Verify_Research_Proposal.md`) | States the problem, gap, RQs, high-level plan. What you'd show an advisor to get sign-off. | Before starting |
| 2 | **Technical Design Doc** (you have this — `IPC2BNS-Verify_Technical_Pipeline.md`) | Architecture, phases, models/tools, metrics. What an engineer would build from. | Before coding |
| 3 | **Data Management Plan** | Where every dataset comes from, its license/usage terms, how it's stored/versioned, and how you'll cite it. Needed because this project pulls from India Code, IndianKanoon-derived academic corpora, and a scraped BNS dataset — each has different reuse terms. | Before ingestion (Phase 2) |
| 4 | **Ground-Truth Concordance Table** (`concordance_v1.csv`) | Your actual IPC↔BNS mapping data — the artifact everything else depends on. | Phase 0 |
| 5 | **Task Board / Work Breakdown Structure** | Every task, owner, dependency, status. (Section 2 below is your starting WBS.) | Ongoing, from day 1 |
| 6 | **Risk Register** | What could go wrong and your mitigation (see Section 5). | Before coding, updated weekly |
| 7 | **Benchmark / Test Set Document** | Your fixed question set, with dev/test split clearly marked, and provenance (which came from ILSI, which you wrote yourself). | Phase 2–4 |
| 8 | **Experiment Log** | One row per run: config used, model versions, date, results file path. This is what makes your results reproducible and defensible if someone asks "how did you get this number." | Ongoing from first experiment |
| 9 | **Results Tables (per ablation stage)** | Raw output of Phase 8 — the numbers before they're written into prose. | Phase 8 |
| 10 | **Error Analysis Notes** | Qualitative log of failure cases, especially ambiguous mapping cases and verifier false positives/negatives. | Phase 7–8 |
| 11 | **Final Report / Paper / Thesis** | The write-up per the structure in the proposal doc. | Phase 9 |
| 12 | **Presentation Deck** | Condensed version for defense/demo — architecture diagram, ablation table, 2–3 key findings, limitations slide. | End |
| 13 | **README + Reproducibility Instructions** | How to install, configure, and re-run every experiment from a clean checkout. | Continuous, finalized at end |
| 14 | **Plagiarism/Originality Report** | Output from your similarity check (Section 4) — keep this on file even if not formally required, as evidence of due diligence. | Before final submission |

**Minimum viable set if you're short on time:** #1, #2, #4, #7, #9, #11 are non-negotiable. #3, #5, #6, #8, #10 are what separates a rushed project from a well-run one — they cost little time if kept updated incrementally, and a lot of time if reconstructed retroactively.

---

## 2. Task Breakdown (Work Breakdown Structure)

Group by the phases from the technical doc; each task should have an owner and a done-condition even if you're a team of one.

**Setup**
- [ ] Scaffold repo structure, config system
- [ ] Download + clean India Code BNS/IPC text
- [ ] Digitize ground-truth concordance table; label all ambiguous cases
- [ ] Write Data Management Plan

**Mapping Module**
- [ ] Build deterministic lookup function + tests
- [ ] Build query normalizer
- [ ] Evaluate mapping accuracy on held-out queries

**Ingestion & Retrieval**
- [ ] Section-level chunker + metadata tagging
- [ ] Pull/adapt ILSI-style questions into a benchmark draft
- [ ] Embed corpus with primary + baseline embedder
- [ ] Evaluate retrieval precision@k / recall@k

**Generation**
- [ ] Build prompt template + citation format
- [ ] Run Stage 1 (baseline, no retrieval)
- [ ] Run Stage 2 (+RAG)

**Verifier**
- [ ] Build Layer 1 hard citation-existence check
- [ ] Build Layer 2 entity-grounding check
- [ ] Build injected-error test set for verifier evaluation
- [ ] Run Stage 3 (+Verifier)

**Adaptivity**
- [ ] Select 20–30 refresh cases
- [ ] Build pre/post-refresh index snapshots
- [ ] Run Stage 4 (+Verifier+Refresh); compute delta

**Evaluation & Write-up**
- [ ] Build evaluation harness + LLM-as-judge scoring
- [ ] Human-review calibration subsample
- [ ] Compile ablation results table
- [ ] Error analysis pass
- [ ] Draft report sections incrementally (don't leave writing to the end)
- [ ] Originality/plagiarism check
- [ ] Final review + submission package

---

## 3. Project Outline (top-level shape)

1. **Problem & Gap** — IPC→BNS transition creates a live citation-accuracy problem; no existing system combines mapping + verification + generation + adaptivity.
2. **Research Questions** — RQ1 (verifier effect), RQ2 (deterministic vs. LLM mapping), RQ3 (refresh delta).
3. **System** — four modules (Mapping, Retrieval, Generation, Verifier) + refresh simulator, wired through a single evaluation harness.
4. **Evaluation** — four-stage ablation on a fixed benchmark, with human-calibrated LLM-as-judge scoring.
5. **Results** — the ablation table + refresh delta + qualitative error analysis, especially ambiguous-mapping cases.
6. **Contribution** — the combined system and, more specifically, the measured marginal effect of each component (not any single piece in isolation, since each piece has some prior art).
7. **Limitations & Future Work** — small benchmark, simulated (not live) refresh, generalization to CrPC/BNSS and BSA left open.

This is the same skeleton as the earlier proposal doc — the outline above is what you'd put on one slide or in an abstract; the proposal doc is the expanded version.

---

## 4. How to Check for Plagiarism

You have two different plagiarism surfaces here — **written text** and **code** — and they need different tools.

### Written text (report/thesis/paper)
- **Institutional tool if available:** Turnitin or iThenticate — most universities provide access; use whichever your institution mandates, since that's the one that counts for submission.
- **Independent check before submission:** Grammarly's plagiarism checker or Copyscape for a second opinion, especially on sections you paraphrased heavily from source papers.
- **Practical discipline that prevents most issues in the first place:**
  - Never copy more than a short phrase directly from a paper's abstract/methodology without quotation marks and citation.
  - When summarizing prior work (as in your related-work table), write the comparison in your own words and structure — don't mirror a paper's abstract sentence-by-sentence.
  - Keep a citation manager (Zotero/Mendeley) from day one so every claim traces to a source, which makes both plagiarism-avoidance and your bibliography easier.
  - Run your own similarity check on a full draft, not just the final version — catching an accidental unattributed paraphrase in week 8 is far cheaper than in week 14.

### Code
- **MOSS (Measure of Software Similarity)** — Stanford's tool, the standard for detecting code similarity/plagiarism across submissions; free for academic use.
- **JPlag** — open-source alternative, supports multiple languages, easy to self-host.
- Even if no one requires this of you, running your own code through MOSS/JPlag against public reference implementations (e.g., popular LangChain RAG tutorials) is good practice if you adapted boilerplate — cite the tutorial/repo you learned from in your README rather than presenting adapted boilerplate as fully original engineering.

### A note on AI-generated text detectors
These are unreliable (high false-positive rates on non-native English writers and on technical/formulaic writing in particular) — don't rely on them to self-check, and don't be surprised if your legitimately-written methodology sections get flagged by one. If your institution requires disclosure of AI tool use in drafting or research assistance, follow that policy directly rather than trying to evade detection.

---

## 5. Risk Register (starter version)

| Risk | Likelihood | Mitigation |
|---|---|---|
| Ground-truth concordance table has errors | Medium | Cross-check against 2+ independent sources (India Code + Kerala Prisons table); spot-check with a law student/advisor if possible |
| Benchmark too small for statistically meaningful ablation deltas | Medium | Report confidence intervals or at minimum raw counts, not just percentages; be upfront about sample size in limitations |
| LLM-as-judge disagrees with human review | Medium | Always report the human-agreement calibration number alongside judge scores |
| API costs exceed budget | Medium | Cache all LLM calls; run baseline/ablation on a dev subset first, full benchmark only for final numbers |
| Scope creep (Phase 4b, generalization) eats core-pipeline time | High | Treat Phases 1–8 as the deliverable; treat generalization/extensions as stretch goals only after core ablation is done |

---

## 6. How to Add a New Feature: Generalization

The architecture generalizes cleanly because the four modules were built decoupled from IPC/BNS specifics. Here's the concrete path:

**Step 1 — Generalize the mapping module.**
The lookup-table pattern is code-agnostic: `map_old_to_new(section, code_pair)` instead of a hardcoded IPC↔BNS function. Add new concordance tables for:
- CrPC 1973 ↔ BNSS 2023 (procedure code)
- Indian Evidence Act 1872 ↔ Bharatiya Sakshya Adhiniyam (BSA) 2023 (evidence code)

Both replacements happened on the same date (1 July 2024) as part of the same legislative overhaul, so the ground-truth sourcing pattern (India Code + official concordance tables) carries over directly.

**Step 2 — Generalize the verifier's ID index.**
Your Layer 1 hard-constraint check just needs a versioned valid-section-ID set per code. Make this a config parameter (`code = "BNS" | "BNSS" | "BSA"`) rather than hardcoded, and the same string-matching logic works unchanged.

**Step 3 — Generalize retrieval and chunking.**
Section-level chunking with `(act, section_number, effective_date_range)` metadata already works for any Indian bare act — no architecture change needed, just re-run ingestion on the new source text.

**Step 4 — Re-run the same ablation methodology.**
This is actually a strength for your write-up: running the identical four-stage ablation on CrPC↔BNSS gives you a second data point proving the *framework* generalizes, not just that it happened to work once on IPC/BNS. If time allows, this is a higher-value addition than most other extensions, because it directly strengthens your core "this is a generalizable framework, not a one-off tool" claim.

**Step 5 (further/optional) — Generalize beyond India.**
The pattern (statute replaced/renumbered → deterministic mapping + verifier + RAG) isn't India-specific in principle. If you want a stretch goal for future work, note it explicitly in your limitations/future-work section rather than attempting it — scope discipline matters more than breadth at this project size.

---

## 7. Files You Need — Final Checklist

```
docs/
  01_project_charter.md              (= IPC2BNS-Verify_Research_Proposal.md)
  02_technical_design.md             (= IPC2BNS-Verify_Technical_Pipeline.md)
  03_data_management_plan.md
  04_risk_register.md
  05_final_report.md / .docx

data/
  concordance_v1.csv                 (IPC<->BNS ground truth)
  concordance_crpc_bnss.csv          (if generalizing — Step 1)
  concordance_iea_bsa.csv            (if generalizing — Step 1)
  benchmark_questions.csv            (dev + test split, provenance noted)
  refresh_sim_cases.csv

results/
  experiment_log.csv
  stage1_baseline_results.json
  stage2_rag_results.json
  stage3_verifier_results.json
  stage4_refresh_results.json
  ablation_summary_table.csv
  error_analysis_notes.md

report/
  final_report.docx / .pdf
  presentation_deck.pptx
  plagiarism_report.pdf

README.md                            (setup + reproduction instructions)
```
