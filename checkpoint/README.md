# Checkpoint: Stage 2 Concordance Mapping & Pipeline Fixes

**Timestamp:** 2026-09-10T21:40:00+05:30  
**Purpose:** Snapshot of all bug fixes, ground-truth data corrections, query normalizer regex/lexicon enhancements, and verifier calibrations that resolved the Stage 2 Concordance Mapping failure.

---

## 1. Problem Summary
In the original pipeline, **Stage 2: Concordance Mapping (Exact Lookup)** was failing to map old IPC sections (and procedural CrPC sections) to new BNS (and BNSS) provisions due to:
1. **Concordance Table Data Corruption:** IPC §34 (Common Intention) was mistakenly mapped to BNS §2(36) ('Valuable security') instead of BNS §3(5), while IPC §30 was missing. Targets for Grievous Hurt, Rioting, Public Nuisance, and Perjury were pointing to wrong section IDs.
2. **Procedural Act Misrouting:** normalizer.py lacked patterns for CrPC and BNSS, causing CrPC §154 (FIR) and CrPC §438 (Anticipatory Bail) to be misclassified as IPC and returning NOT_FOUND.
3. **Section-First Syntax Blindspots:** Inputs like '302 IPC' or '154 CrPC' were returning None.
4. **Alphanumeric Code Destruction in UI:** app.py used str.isdigit which stripped letters, corrupting CrPC §265A to '265' and §176(3) to '1763'.
5. **Verifier Confidence Inversion:** When Layer 2/2.5 rejected an answer, the confidence score remained high (>= 0.80) and showed HIGH_CONFIDENCE_VERIFIED.

---

## 2. Changes Stored in this Checkpoint

### A. Ground-Truth Data (data/02_ground_truth/concordance_v1.csv)
- **Restored IPC §30:** Mapped to BNS §2(36) ('Valuable security').
- **Corrected IPC §34:** Mapped to BNS §3(5) ('Joint liability and common intention').
- **Corrected Misaligned Targets:**
  - IPC §320 (Grievous Hurt) -> BNS §116 (was 115)
  - IPC §146 / §147 (Rioting) -> BNS §191 (was 190 / 194)
  - IPC §268 (Public Nuisance) -> BNS §270 (was 271)
  - IPC §191 (Giving False Evidence / Perjury) -> BNS §227 (was 229)
- **Added Missing Core Sections:** IPC §121A, §122, §123, §149, §159, §160, §201, §212, §272, §273, §309, §313, §314, §315, §316, §325, §403, §404, §411, §416, §419, §464, §467.
- **Added New BNS Provisions:** BNS §103(2) (Mob Lynching), BNS §106(2) (Hit and Run), BNS §304 (Snatching).
- **Expanded Total Rows:** 154 -> 181 rows.

### B. Query Normalizer (code/src/mapping/normalizer.py)
- **Enhanced Regex:** Added support for section-first formats ('302 IPC', '154 CrPC', '173 BNSS') and explicit act boundaries (\bBNSS\b, \bBNS\b, \bCrPC\b, \bIPC\b).
- **Expanded Offence Lexicon:** Added modern offences ('snatching', 'organised crime', 'terrorist act', 'mob lynching', 'hit and run', 'deceitful means') and procedural concepts ('fir', 'anticipatory bail', 'remand', 'plea bargaining', 'common intention', 'attempted murder').

### C. Concordance Lookup Engine (code/src/mapping/lookup.py)
- **Dynamic BM25 Fallback:** If an unindexed IPC section is queried, the engine attempts dynamic resolution via the statutory BM25 retrieval index before failing.
- **Preserved Alphanumeric Keys:** Updated map_crpc_to_bnss and map_bnss_to_crpc to preserve parentheses and alphanumeric codes (e.g. 176(3) and 265A).

### D. Interactive UI (app.py)
- Replaced destructive digit filtering with safe cleaning (clean_section_key) so procedural sections route accurately.

### E. Verifier Pipeline (code/src/verifier/verifier_pipeline.py & entity_grounding.py)
- Added query intent legal synonyms ('fir', 'bail', 'remand', 'cheating', etc.).
- Penalized confidence score to <= 0.25 and updated grade to NON_RESPONSIVE_REJECTED or UNGROUNDED_CLAIM_REJECTED when Layer 2 or Layer 2.5 fails.

---

## 3. Files in this Directory
- app.py: Updated Streamlit interface.
- code/src/mapping/normalizer.py: Updated multi-tier query normalizer.
- code/src/mapping/lookup.py: Updated deterministic lookup engine with fallback.
- code/src/verifier/verifier_pipeline.py: Calibrated verifier confidence grading.
- code/src/verifier/entity_grounding.py: Intent synonym expansion.
- data/02_ground_truth/concordance_v1.csv: Patched and expanded ground-truth table.
- changes.patch: Full unified git diff of all modifications.

---

## 4. Verification Results
- **Validation Test Suite:** 37/37 assertions passed (0 failures).
- **Benchmark Evaluation:** Stage 2 mapping accuracy on benchmark_dev.csv jumped from 40.0% to 65.0%.
- **Sample Queries in app.py:** All 6 benchmark cases now route and verify cleanly.
