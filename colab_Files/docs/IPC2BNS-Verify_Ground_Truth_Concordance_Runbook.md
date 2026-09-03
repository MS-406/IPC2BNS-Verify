# Ground-Truth Concordance Table — End-to-End Build Runbook

This is the single most important artifact in the whole project (`data/02_ground_truth/concordance_v1.csv` from the Data Management Plan). Everything downstream — mapping module, verifier's valid-ID index, retrieval ground truth — depends on this being right. This document walks through building it end to end: what to run, where to run it, and how to validate it before you trust it.

---

## 1. Target Schema

Decide this before writing any code — every step below produces or refines rows in this shape.

| Column | Type | Example |
|---|---|---|
| `ipc_section` | string | `"302"` |
| `ipc_title` | string | `"Punishment for murder"` |
| `bns_section` | string (nullable) | `"103"` |
| `bns_title` | string | `"Punishment for murder"` |
| `relationship_type` | enum | `exact` \| `renumbered` \| `split` \| `merged` \| `repealed` \| `new_in_bns` |
| `notes` | string | free text — e.g. "harsher punishment added for caste/race-based murder" |
| `source` | string | which source(s) this row came from, e.g. `"india_code + kerala_prisons_table"` |
| `verified` | boolean | true only after Step 5 cross-check |
| `last_updated` | date | ISO date |

Save the empty schema first as `data/02_ground_truth/concordance_v1.csv` with just the header row — this is your Step 0 output.

**Where to run this:** anywhere — it's just a CSV header. Create it locally in your `data/02_ground_truth/` folder (see Data Management Plan for the folder layout) and commit the header to git even though the data itself isn't versioned in git.

---

## 2. Step-by-Step Build Process

### Step 1 — Pull primary source text (India Code)
**What:** Download/scrape the official BNS 2023 and IPC 1860 bare-act text.
**Script:** `code/src/ingestion/fetch_india_code.py`
**Run:**
```bash
cd code/
python src/ingestion/fetch_india_code.py \
    --acts "IPC-1860,BNS-2023" \
    --out ../data/00_raw/india_code/
```
**Where to run:** your local machine or a Colab notebook — no GPU needed, this is just HTTP requests + HTML/PDF parsing. If India Code serves PDFs, use `pdfplumber` or `PyMuPDF`; if HTML, `BeautifulSoup`.
**Output:** `data/00_raw/india_code/ipc_1860_raw.pdf`, `bns_2023_raw.pdf` (or `.html`).

### Step 2 — Pull the reference concordance table
**What:** Download the correspondence table PDF (e.g., the Kerala Prisons/CAPT Bhopal publication) that already maps BNS→IPC section by section with a comparison summary.
**Run:** manual download (it's a single PDF) into `data/00_raw/concordance_source_pdfs/`. No script needed for a one-time download; if you find multiple such tables, save each with a clear filename (`concordance_source_A.pdf`, `concordance_source_B.pdf`) so Step 5's cross-check has more than one reference.

### Step 3 — Extract raw table rows from the PDF
**What:** Turn the correspondence PDF's table into structured rows.
**Script:** `code/src/mapping/extract_concordance_pdf.py`
**Run:**
```bash
python src/mapping/extract_concordance_pdf.py \
    --pdf ../data/00_raw/concordance_source_pdfs/concordance_source_A.pdf \
    --out ../data/01_cleaned/concordance_extracted_raw.csv
```
**Tooling:** `camelot-py` or `tabula-py` for table extraction from PDF; expect to hand-fix a meaningful fraction of rows — legal PDFs rarely extract perfectly clean, especially where a single BNS section maps to multiple IPC sections in one cell.
**Where to run:** local machine (table-extraction libraries can be finicky with system dependencies like Ghostscript — easier to debug locally than in a notebook environment).

### Step 4 — Normalize into target schema
**What:** Map extracted raw columns onto the schema from Section 1; infer `relationship_type` from the "summary of comparison" text (e.g., "no change" → `exact`; "new addition" → `new_in_bns`; a BNS row with multiple IPC section numbers listed → `split`; multiple BNS rows pointing to the same IPC section → `merged`).
**Script:** `code/src/mapping/normalize_concordance.py`
**Run:**
```bash
python src/mapping/normalize_concordance.py \
    --input ../data/01_cleaned/concordance_extracted_raw.csv \
    --output ../data/02_ground_truth/concordance_v1_draft.csv
```
**Where to run:** local — this is pure data transformation, no external calls needed.

### Step 5 — Cross-validate against India Code + a second source
**What:** For every row, confirm the section number and title actually appear in the Step 1 bare-act text, and — where you have a second concordance source from Step 2 — confirm agreement between sources. Flag any mismatch for manual review rather than auto-resolving it.
**Script:** `code/src/mapping/cross_validate.py`
**Run:**
```bash
python src/mapping/cross_validate.py \
    --draft ../data/02_ground_truth/concordance_v1_draft.csv \
    --bare_act_ipc ../data/01_cleaned/ipc_sections.jsonl \
    --bare_act_bns ../data/01_cleaned/bns_sections.jsonl \
    --report ../data/02_ground_truth/validation_report.csv
```
**Output:** `validation_report.csv` — a list of every row that passed automatically vs. every row flagged for manual review (mismatched titles, section not found, disagreement between two concordance sources).
**Where to run:** local — fast, no external API calls.

### Step 6 — Manual review pass
**What:** Open `validation_report.csv`, go through every flagged row by hand against the actual India Code bare-act text side by side. This is the step that cannot be scripted — budget real time for it (expect this to take longer than any of the coding steps for a table of ~500+ IPC sections).
**Where to run:** any spreadsheet tool (Google Sheets is fine — put a working copy of `concordance_v1_draft.csv` there for this pass specifically, then export back to CSV when done). Log every correction with a reason in a `CHANGELOG.md` next to the file, per the Data Management Plan.
**Special attention:** every `split`, `merged`, `repealed`, and `new_in_bns` row — these are exactly the cases your verifier needs to handle as "flag as ambiguous" rather than force a confident single answer (e.g., IPC §124A sedition → no direct BNS counterpart, replaced in narrower scope by BNS §152).

### Step 7 — Finalize and lock the version
**What:** Once manual review is complete, save the finished table as the real `concordance_v1.csv`, mark every row `verified = true`, and do not edit it further without bumping the version (`concordance_v2.csv`) and logging why in `CHANGELOG.md`.
**Run:**
```bash
python src/mapping/finalize_concordance.py \
    --input ../data/02_ground_truth/concordance_v1_draft.csv \
    --output ../data/02_ground_truth/concordance_v1.csv
```
**Where to run:** local. This is also the point to commit a copy to your backup location per the Data Management Plan — this file is hand-curated and not re-derivable by re-running scripts alone (Steps 3–4 are automatable, Step 6 is not).

### Step 8 — Unit tests against the finished table
**What:** Write tests that the mapping module (Phase 1 of the technical pipeline) will run against on every change.
**Script:** `code/tests/test_concordance.py`
**Run:**
```bash
cd code/
pytest tests/test_concordance.py -v
```
**What to test:**
- Every IPC section 1–511 has a row (no silent gaps).
- Every row with `relationship_type != exact` has a non-empty `notes` field.
- No `bns_section` value appears that isn't actually present in `data/01_cleaned/bns_sections.jsonl`.
**Where to run:** locally, and again in CI (GitHub Actions) on every push if you set one up — cheap to add and catches silent corruption of this file later in the project.

---

## 3. End-to-End Command Summary (copy-paste order)

```bash
# from the code/ directory
python src/ingestion/fetch_india_code.py --acts "IPC-1860,BNS-2023" --out ../data/00_raw/india_code/
# (manual) download concordance source PDF(s) into ../data/00_raw/concordance_source_pdfs/
python src/mapping/extract_concordance_pdf.py --pdf ../data/00_raw/concordance_source_pdfs/concordance_source_A.pdf --out ../data/01_cleaned/concordance_extracted_raw.csv
python src/mapping/normalize_concordance.py --input ../data/01_cleaned/concordance_extracted_raw.csv --output ../data/02_ground_truth/concordance_v1_draft.csv
python src/mapping/cross_validate.py --draft ../data/02_ground_truth/concordance_v1_draft.csv --bare_act_ipc ../data/01_cleaned/ipc_sections.jsonl --bare_act_bns ../data/01_cleaned/bns_sections.jsonl --report ../data/02_ground_truth/validation_report.csv
# (manual) review validation_report.csv in Sheets, fix flagged rows, log changes in CHANGELOG.md
python src/mapping/finalize_concordance.py --input ../data/02_ground_truth/concordance_v1_draft.csv --output ../data/02_ground_truth/concordance_v1.csv
pytest tests/test_concordance.py -v
```

---

## 4. Example Rows (illustrative — verify against India Code before using)

| ipc_section | ipc_title | bns_section | bns_title | relationship_type | notes |
|---|---|---|---|---|---|
| 302 | Punishment for murder | 103 | Punishment for murder | renumbered | BNS adds harsher punishment for murder on grounds of race/caste, etc. |
| 299 | Culpable homicide | 100 | Culpable homicide | renumbered | Similar definition; BNS provides more detailed explanations |
| 375/376 | Rape / Punishment for rape | 63/64 | Rape / Punishment for rape | renumbered | Definition expanded to include digital penetration and other non-consensual acts; BNS increases minimum punishment |
| 124A | Sedition | — | — | repealed | No direct counterpart; replaced in narrower scope by BNS §152 (acts endangering sovereignty/unity/integrity) — flag as ambiguous, do not auto-map |
| 33 | "Act"/"Omission" (combined) | 2(1) / 2(25) | "Act" / "Omission" (separate definitions) | split | IPC §33 covered both terms in one section; BNS defines them as two separate sub-clauses |
| — | — | 2(3) | Definition of "child" | new_in_bns | No IPC counterpart; entirely new definition |

---

## 5. Where Each Piece Lives (tie-back to the Data Management Plan)

- Raw sources → `data/00_raw/india_code/`, `data/00_raw/concordance_source_pdfs/`
- Intermediate extraction → `data/01_cleaned/concordance_extracted_raw.csv`
- Working draft + validation report → `data/02_ground_truth/concordance_v1_draft.csv`, `validation_report.csv`
- Final, locked artifact → `data/02_ground_truth/concordance_v1.csv` + `CHANGELOG.md`
- Scripts that produce all of the above → `code/src/ingestion/`, `code/src/mapping/`
- Tests → `code/tests/test_concordance.py`
