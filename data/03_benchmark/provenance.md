# Benchmark Dataset Provenance & Distribution

This benchmark evaluates the IPC2BNS-Verify pipeline across 4 ablation stages.

## 1. Dataset Splits
- **Development Set (`benchmark_dev.csv`)**: 17 Q&A pairs used for pipeline tuning and retrieval parameter calibration.
- **Held-Out Test Set (`benchmark_test.csv`)**: 8 Q&A pairs held out and evaluated only for final ablation results.

## 2. Question Taxonomy & Distribution
- **Section Transitions (IPC ↔ BNS)**: Evaluates mapping lookup and retrieval precision across code shifts.
- **Ingredient & Punishment Queries**: Evaluates deep statutory understanding, penalty changes, and sub-section granularity.
- **Ambiguous & Repealed Provisions**: Evaluates verifier veto capability on §124A (Sedition), §497 (Adultery), and §377.
- **New BNS Offences**: Evaluates retrieval on novel statutory provisions (§111, §112, §113, §69).
- **Split & Merged Sections**: Evaluates multi-target mapping (§33 split, §120A/B merged).

## 3. Provenance Sources
- **`statute_qa`**: Formulated directly from India Code statutory text and legislative changes.
- **`adapted_ilsi`**: Adapted from factual query excerpts in the ILSI dataset (LeSICiN).
- **`hand_curated`**: Specifically crafted edge cases for ambiguity and verifier stress-testing.
