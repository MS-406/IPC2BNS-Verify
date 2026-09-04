# Phase 7 — Large-Scale Benchmark Expansion

This directory contains **all Phase 7 work** for IPC2BNS-Verify. It is a fully isolated evaluation layer that wraps the existing frozen pipeline without modifying any original file.

## Quick Results

| Metric | Value |
|---|---|
| **Benchmark size** | **1,140 questions** |
| **Citation hit rate** | **28.9% (329/1,140)** |
| **Wilson 95% CI** | [26.3%–31.6%] |
| **Retrieval Recall@5** | 30.4% |
| **Retrieval MRR** | 0.267 |
| **Adversarial catch rate** | 94.4% (17/18) |
| **Existing tests** | 67/67 ✓ |
| **Original files modified** | 0 ✓ |

See the full report: [`results/reports/PHASE7_LARGE_SCALE_EVALUATION.md`](results/reports/PHASE7_LARGE_SCALE_EVALUATION.md)

## Directory Structure

```
phase7/
├── AUDIT_EXISTING_SYSTEM.md          # Audit of all existing interfaces
├── original_experiment_manifest.json # Original experiment metadata
├── original_artifact_manifest.json   # SHA-256 integrity manifest
├── NOT_USED_AND_WHY.md               # Excluded datasets + reasons
│
├── sources/
│   └── source_registry.json          # All datasets considered
│
├── scripts/
│   ├── build_phase7_benchmark.py     # Master benchmark builder
│   ├── verify_integrity.py           # Integrity checker
│   ├── collect_sources.py            # Dataset discovery
│   ├── filter_relevant_questions.py  # Relevance filter
│   ├── deduplicate.py                # Deduplication
│   ├── assign_ground_truth.py        # Ground truth assignment
│   └── verify_ground_truth.py        # Ground truth audit
│
├── benchmark/
│   ├── master_benchmark.jsonl        # Full 1,140-question benchmark
│   ├── master_benchmark.csv          # CSV version
│   ├── natural_benchmark.jsonl       # Natural only (N=1,122)
│   ├── adversarial_benchmark.jsonl   # Adversarial only (N=18)
│   ├── train.jsonl                   # Train split (N=647)
│   ├── dev.jsonl                     # Dev split (N=251)
│   ├── test.jsonl                    # Test split (N=242)
│   └── ground_truth_audit.csv        # Per-question GT verification
│
├── data/
│   ├── intermediate/                 # Build intermediates
│   ├── filtered/                     # Filtered candidates
│   ├── verified/                     # Verified records
│   └── final/
│       └── benchmark_stats.json      # Build statistics
│
├── evaluation/
│   ├── run_large_benchmark.py        # Main evaluation driver
│   ├── evaluate_retrieval.py         # Retrieval metrics
│   ├── evaluate_generation.py        # Generation + verifier metrics
│   └── generate_figures.py           # Publication figures
│
└── results/
    ├── raw/                          # Raw evaluation JSON output
    ├── tables/                       # CSV + JSON tables
    └── reports/
        └── PHASE7_LARGE_SCALE_EVALUATION.md  # Full report
```

## Reproduce

```bash
cd "d:\college 4th year\research paper\NLP_rs"

# 1. Build benchmark
python phase7/scripts/build_phase7_benchmark.py

# 2. Run evaluation (offline mode — consistent with original experiments)
python phase7/evaluation/run_large_benchmark.py --split all

# 3. Compute all metrics
python phase7/evaluation/evaluate_retrieval.py
python phase7/evaluation/evaluate_generation.py

# 4. Generate figures
python phase7/evaluation/generate_figures.py

# 5. Verify integrity (all original files must be unmodified)
python phase7/scripts/verify_integrity.py

# 6. Regression test (must show 67 passed)
python -m pytest code/tests/ -v
```

## Benchmark Categories

| Category | Name | N | Source |
|---|---|---|---|
| A | IPC→BNS Direct | 952 | concordance_v1.csv |
| B | CrPC→BNSS Direct | 108 | CRPC_TO_BNSS_MAP |
| C | Natural Scenarios | 25 | Hand-curated |
| D | Repealed Provisions | 6 | concordance + SC judgments |
| E | Split Provisions | 5 | concordance_v1.csv |
| F | Merged Provisions | 5 | concordance_v1.csv |
| G | Changed Scope | 6 | concordance + india_code |
| H | Adversarial | 18 | Hand-constructed |
| I | Temporal/Current Law | 10 | concordance + dates |
| J | Incremental Refresh | 5 | concordance + india_code |

## Ground Truth Authority

1. `data/02_ground_truth/concordance_v1.csv` — IPC→BNS (155 rows)
2. `code/src/mapping/lookup.py::CRPC_TO_BNSS_MAP` — CrPC→BNSS (26 pairs)
3. India Code official statutory text
4. Supreme Court judgments (sedition repeal, adultery repeal)

## Key Guarantee

**All 17 original critical files verified unmodified** (SHA-256 checksums in `original_artifact_manifest.json`). No existing file was touched during Phase 7 construction or evaluation.
