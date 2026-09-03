# IPC2BNS-Verify: Data Management Plan (Open-Source Sources Only)

This plan lists **only sources that are freely accessible without a paid license**, gives an honest access/reuse status for each (don't assume "publicly viewable" means "freely reusable" — I've flagged the difference below), defines where everything lives in your Drive/project folder alongside code, and covers what to check before you rely on any source for the generalized (CrPC/BNSS, Evidence Act/BSA) version of the project.

---

## 1. Open-Source Data Sources (verified access status)

| Source | What it gives you | Access | Reuse status | Action needed |
|---|---|---|---|---|
| **India Code** (indiacode.nic.in) | Official bare-act text: IPC 1860, BNS 2023, and (for generalization) CrPC 1973, BNSS 2023, Evidence Act 1872, BSA 2023 | Free, no login, Government of India portal | Government-published statute text — the authoritative source, safe to use and cite directly | Download/scrape once, store raw HTML/PDF, re-parse locally |
| **Correspondence/concordance table** (e.g., Kerala Prisons Dept. / CAPT Bhopal publication) | Section-by-section IPC→BNS mapping with change-type annotations | Free PDF, publicly hosted by a government training institute | Public government training material; treat as a reference to cross-check against, cite the author/publisher | Digitize into your own CSV; do **not** treat as infallible — cross-check against India Code text directly for any section you use in the benchmark |
| **IL-PCSR** (Paul, Ghumare, Goyal, Ghosh, Modi — IIT Kharagpur/Kanpur, arXiv 2511.00268) | 936 statutes from 92 central acts + 3,183 Supreme Court cases, joint statute+precedent retrieval testbed | Released alongside an academic paper (arXiv) | Standard practice for these corpora is a research-use license attached to the paper's repo — **verify the exact license file in their release** before using in any output you publish, even though the paper itself is open | Check the release repo/appendix for license terms; cite the paper regardless |
| **IL-PCR** (Joshi et al., 2023, used in arXiv 2508.00679) | 7,070 case texts, ~8,000 citation links | Released with the paper | Same as above — verify license in the actual data release, not just the paper | Same |
| **ILSI dataset** (from LeSICiN, arXiv 2112.14731) | ~66,000 fact excerpts labeled with the 100 most-cited IPC sections — useful seed for realistic query phrasing | Released with the paper | Same as above — check for an explicit license (research-use is typical) | Same; adapt phrasing to BNS-era terms rather than reusing verbatim |
| **BNS structured dataset (CSV)** (IEEE DataPort, chapter/section_title/section_content) | Pre-chunked BNS text | Free download, requires a (free) IEEE DataPort account | Check the specific dataset's license tag on its DataPort page (varies by submitter — often CC BY) before redistributing; safe for internal research use regardless | Cross-validate against India Code before treating as ground truth — it's a third-party scrape, not primary source |

**Deliberately excluded from this list:** IndianKanoon's own API is a **paid, authenticated service** (public-private key access, usage billed) — not open-source, so it doesn't belong in an open-source-only data plan. Where academic papers above sourced case text "via IndianKanoon," that refers to a one-time scrape those researchers did for their own published corpus (IL-PCSR/IL-PCR/ILSI) — you are not reusing IndianKanoon directly, you're reusing *their* released dataset, which is the correct approach for staying open-source-only. Do not scrape IndianKanoon.org directly yourself; it sits outside this plan's open-source scope and outside what this conversation should help engineer around.

---

## 2. Storage Structure (Drive / Project Folder, parallel to code)

Keep data physically separate from code but structurally mirrored, so any team member can find the data for a given pipeline stage next to the code that consumes it.

```
IPC2BNS-Verify/                        ← root project folder (Drive or local, synced to git)
│
├── code/                              ← git repo lives here
│   ├── src/
│   │   ├── mapping/
│   │   ├── ingestion/
│   │   ├── retrieval/
│   │   ├── generation/
│   │   ├── verifier/
│   │   ├── refresh/
│   │   └── eval/
│   ├── configs/
│   └── notebooks/
│
├── data/                              ← NOT in git (too large / avoid committing scraped text); sync via Drive instead
│   ├── 00_raw/
│   │   ├── india_code/                ← raw IPC, BNS, (CrPC, BNSS, IEA, BSA if generalizing) bare-act text
│   │   ├── concordance_source_pdfs/   ← original correspondence table PDFs, unmodified
│   │   ├── il_pcsr/
│   │   ├── il_pcr/
│   │   ├── ilsi/
│   │   └── bns_ieee_dataport/
│   │
│   ├── 01_cleaned/                    ← parsed, deduplicated, encoding-fixed versions of the above
│   │   ├── ipc_sections.jsonl
│   │   ├── bns_sections.jsonl
│   │   └── ...
│   │
│   ├── 02_ground_truth/               ← your own curated artifacts — the most important folder
│   │   ├── concordance_v1.csv
│   │   ├── concordance_crpc_bnss.csv       (generalization)
│   │   ├── concordance_iea_bsa.csv         (generalization)
│   │   └── CHANGELOG.md               ← every correction to ground truth logged with date+reason
│   │
│   ├── 03_benchmark/
│   │   ├── benchmark_dev.csv
│   │   ├── benchmark_test.csv         ← held out, touched only for final numbers
│   │   └── provenance.md              ← which questions came from ILSI vs. hand-written
│   │
│   ├── 04_refresh_sim/
│   │   └── injected_amendment_cases.csv
│   │
│   └── 05_embeddings_index/           ← vector DB files/snapshots (can be large — consider .gitignore + Drive only)
│       ├── stage2_index/
│       └── stage4_post_refresh_index/
│
├── results/                           ← outputs of running code against data — keep alongside data, not inside code/
│   ├── experiment_log.csv
│   ├── stage1/ stage2/ stage3/ stage4/
│   └── ablation_summary_table.csv
│
├── docs/                              ← all your planning docs (proposal, technical design, this DMP, PM guide)
│
└── report/
```

**Practical rules:**
- `code/` is the only folder under version control (git). `data/`, `results/` are synced via Drive (or DVC/Git LFS if you want data versioning inside git without bloating the repo).
- Never edit `00_raw/` files in place — all cleaning happens in code that outputs to `01_cleaned/`, so you can always re-derive everything from the untouched originals.
- `02_ground_truth/` is the one folder that should be backed up with extra care (it's hand-curated, not re-derivable by re-running a script) — keep a dated copy in a separate backup location, not just Drive's version history.

---

## 3. Availability Check for Generalization

Before extending to CrPC↔BNSS or Evidence Act↔BSA, confirm each of these — don't assume the IPC/BNS pattern holds automatically:

| Check | IPC↔BNS (done) | CrPC↔BNSS | IEA↔BSA |
|---|---|---|---|
| Bare-act text available on India Code | Yes | Verify — should be present, same portal, same 1 July 2024 commencement | Verify — same portal |
| Official/near-official concordance table exists publicly | Yes (Kerala Prisons/CAPT Bhopal) | Search for an equivalent — police/judicial academy training material is the most likely free source, same pattern as the BNS one | Same — check state judicial academies |
| Academic retrieval corpus exists for cross-validation | Yes (IL-PCSR covers statutes broadly, not IPC-specific — check if it includes CrPC/Evidence Act sections too, since it spans 92 central acts) | Check IL-PCSR's 92-act list directly — it may already include CrPC provisions | Same check |
| Section count / mapping complexity known | 511→358, well documented | BNSS restructured procedural sections — get exact counts before assuming 1:1 style parity with the IPC/BNS case | Same |

**Do this check before writing any generalization code** — if a good concordance source doesn't exist for one of these codes, that's worth knowing before you budget time for it, and it becomes a valid "left for future work due to source-data availability" line in your limitations section rather than a silent gap.

---

## 4. Getting Proper Accuracy Out of These Sources

- **Never treat a single source as ground truth in isolation.** Cross-check every concordance-table entry you actually use in your benchmark against the India Code bare-act text directly — the concordance table is a convenience layer, the bare act is the legal authority.
- **Version everything.** Statute text can be amended; tag every cleaned file with the date you pulled it and the India Code URL/version it came from, so a later correction doesn't silently invalidate your benchmark without you noticing.
- **Sample-audit third-party datasets before trusting them at scale.** For IL-PCSR/IL-PCR/ILSI and the IEEE DataPort CSV, manually check a random 20–30 entries against the primary source before using the full dataset — third-party scrapes accumulate small errors (OCR issues, missed amendments) that compound if unnoticed.
- **Keep your test set completely untouched until final evaluation.** Accuracy numbers lose credibility the moment there's any chance the test set influenced earlier tuning — this is a data-management discipline issue as much as a modeling one.
