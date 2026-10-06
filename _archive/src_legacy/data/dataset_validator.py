"""
dataset_validator.py — Phase 1: Dataset Validation & Audit

Validates the IPC2BNS dataset by analyzing:
- Input format and schema
- IPC/BNS section distributions
- Class balance
- Duplicates and missing values
- Conflicting mappings
- Potential data leakage between splits
"""

import os
import csv
import json
import logging
from collections import Counter, defaultdict
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

log = logging.getLogger("dataset_validator")


def load_concordance(path: str) -> List[Dict[str, str]]:
    """Load concordance CSV into list of dicts."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load JSONL file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_benchmark_csv(path: str) -> List[Dict[str, str]]:
    """Load benchmark CSV."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def validate_dataset(
    concordance_path: Optional[str] = None,
    ipc_path: Optional[str] = None,
    bns_path: Optional[str] = None,
    dev_path: Optional[str] = None,
    test_path: Optional[str] = None,
    output_json: Optional[str] = None,
    output_csv: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run complete dataset validation and generate reports.

    Returns a comprehensive report dict.
    """
    from src.utils.config import (
        CONCORDANCE_PATH, IPC_SECTIONS_PATH, BNS_SECTIONS_PATH,
        BENCHMARK_DEV_PATH, BENCHMARK_TEST_PATH, REPORTS_DIR
    )

    concordance_path = concordance_path or str(CONCORDANCE_PATH)
    ipc_path = ipc_path or str(IPC_SECTIONS_PATH)
    bns_path = bns_path or str(BNS_SECTIONS_PATH)
    dev_path = dev_path or str(BENCHMARK_DEV_PATH)
    test_path = test_path or str(BENCHMARK_TEST_PATH)
    output_json = output_json or str(REPORTS_DIR / "dataset_report.json")
    output_csv = output_csv or str(REPORTS_DIR / "dataset_report.csv")

    report = {"status": "success", "errors": [], "warnings": []}

    # ── 1. Load all data ──────────────────────────────────────────────────
    log.info("Loading datasets...")
    concordance = load_concordance(concordance_path)
    ipc_sections = load_jsonl(ipc_path)
    bns_sections = load_jsonl(bns_path)
    dev_data = load_benchmark_csv(dev_path)
    test_data = load_benchmark_csv(test_path)

    report["files"] = {
        "concordance": {"path": concordance_path, "rows": len(concordance)},
        "ipc_sections": {"path": ipc_path, "rows": len(ipc_sections)},
        "bns_sections": {"path": bns_path, "rows": len(bns_sections)},
        "benchmark_dev": {"path": dev_path, "rows": len(dev_data)},
        "benchmark_test": {"path": test_path, "rows": len(test_data)},
    }

    # ── 2. Concordance Analysis ───────────────────────────────────────────
    log.info("Analyzing concordance table...")
    ipc_sections_in_concordance = set()
    bns_sections_in_concordance = set()
    relationship_types = Counter()
    duplicate_mappings = []
    missing_values = {"ipc_missing": 0, "bns_missing": 0, "both_missing": 0}
    verified_count = 0

    ipc_to_bns_map = defaultdict(list)
    bns_to_ipc_map = defaultdict(list)

    for row in concordance:
        ipc_sec = row.get("ipc_section", "").strip()
        bns_sec = row.get("bns_section", "").strip()
        rel_type = row.get("relationship_type", "").strip()
        verified = row.get("verified", "").lower() == "true"

        if verified:
            verified_count += 1

        relationship_types[rel_type] += 1

        if not ipc_sec and not bns_sec:
            missing_values["both_missing"] += 1
        elif not ipc_sec:
            missing_values["ipc_missing"] += 1
        elif not bns_sec:
            missing_values["bns_missing"] += 1

        if ipc_sec:
            ipc_sections_in_concordance.add(ipc_sec)
            ipc_to_bns_map[ipc_sec].append(bns_sec)
        if bns_sec:
            bns_sections_in_concordance.add(bns_sec)
            bns_to_ipc_map[bns_sec].append(ipc_sec)

    # Check for duplicate IPC→BNS mappings
    for ipc_sec, bns_list in ipc_to_bns_map.items():
        if len(bns_list) > 1:
            duplicate_mappings.append({
                "ipc_section": ipc_sec,
                "mapped_bns_sections": bns_list,
                "count": len(bns_list)
            })

    # Check for conflicting mappings (same IPC → different BNS with different relationships)
    conflicting = []
    for ipc_sec, bns_list in ipc_to_bns_map.items():
        unique_bns = set(bns_list)
        if len(unique_bns) > 1:
            conflicting.append({"ipc_section": ipc_sec, "bns_targets": list(unique_bns)})

    # ── 3. Class Distribution ─────────────────────────────────────────────
    log.info("Computing class distributions...")
    bns_class_dist = Counter()
    for row in concordance:
        bns_sec = row.get("bns_section", "").strip()
        if bns_sec:
            bns_class_dist[bns_sec] += 1

    class_counts = sorted(bns_class_dist.values())
    single_sample_classes = sum(1 for c in class_counts if c == 1)

    # ── 4. Benchmark Analysis ─────────────────────────────────────────────
    log.info("Analyzing benchmark sets...")

    dev_query_types = Counter(row.get("query_type", "") for row in dev_data)
    test_query_types = Counter(row.get("query_type", "") for row in test_data)
    dev_ambiguous = sum(1 for row in dev_data if row.get("is_ambiguous", "").lower() == "true")
    test_ambiguous = sum(1 for row in test_data if row.get("is_ambiguous", "").lower() == "true")

    # ── 5. Data Leakage Check ─────────────────────────────────────────────
    log.info("Checking for data leakage...")
    dev_gt_sections = set()
    test_gt_sections = set()
    dev_queries = set()
    test_queries = set()

    for row in dev_data:
        dev_gt_sections.add(row.get("ground_truth_sections", "").strip())
        dev_queries.add(row.get("query_text", "").strip().lower())
    for row in test_data:
        test_gt_sections.add(row.get("ground_truth_sections", "").strip())
        test_queries.add(row.get("query_text", "").strip().lower())

    overlapping_sections = dev_gt_sections & test_gt_sections
    overlapping_queries = dev_queries & test_queries

    leakage_report = {
        "overlapping_ground_truth_sections": len(overlapping_sections),
        "overlapping_sections_list": sorted(list(overlapping_sections))[:20],
        "overlapping_query_texts": len(overlapping_queries),
        "warning": "Section overlap between dev/test may inflate metrics" if overlapping_sections else "No exact section overlap detected"
    }

    if overlapping_sections:
        report["warnings"].append(
            f"Data leakage risk: {len(overlapping_sections)} ground-truth sections appear in both dev and test sets."
        )

    # ── 6. Compile Report ─────────────────────────────────────────────────
    report["concordance"] = {
        "total_rows": len(concordance),
        "unique_ipc_sections": len(ipc_sections_in_concordance),
        "unique_bns_sections": len(bns_sections_in_concordance),
        "relationship_type_distribution": dict(relationship_types),
        "verified_count": verified_count,
        "unverified_count": len(concordance) - verified_count,
        "missing_values": missing_values,
        "split_mappings": len([m for m in duplicate_mappings if len(m["mapped_bns_sections"]) > 1]),
        "conflicting_mappings": len(conflicting),
        "conflicting_details": conflicting[:10],
    }

    report["class_distribution"] = {
        "num_classes": len(bns_class_dist),
        "single_sample_classes": single_sample_classes,
        "multi_sample_classes": len(bns_class_dist) - single_sample_classes,
        "min_samples_per_class": min(class_counts) if class_counts else 0,
        "max_samples_per_class": max(class_counts) if class_counts else 0,
        "mean_samples_per_class": round(sum(class_counts) / max(1, len(class_counts)), 2),
        "class_imbalance_ratio": round(
            max(class_counts) / max(1, min(class_counts)), 2
        ) if class_counts else 0,
    }

    report["corpus"] = {
        "ipc_sections_count": len(ipc_sections),
        "bns_sections_count": len(bns_sections),
    }

    report["benchmark"] = {
        "dev_samples": len(dev_data),
        "test_samples": len(test_data),
        "total_samples": len(dev_data) + len(test_data),
        "dev_query_types": dict(dev_query_types),
        "test_query_types": dict(test_query_types),
        "dev_ambiguous": dev_ambiguous,
        "test_ambiguous": test_ambiguous,
    }

    report["leakage"] = leakage_report

    # ── 7. Save Reports ──────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Dataset report saved to {output_json}")

    # CSV summary
    csv_rows = [
        {"metric": "concordance_rows", "value": len(concordance)},
        {"metric": "unique_ipc_sections", "value": len(ipc_sections_in_concordance)},
        {"metric": "unique_bns_sections", "value": len(bns_sections_in_concordance)},
        {"metric": "num_classes", "value": len(bns_class_dist)},
        {"metric": "single_sample_classes", "value": single_sample_classes},
        {"metric": "ipc_corpus_sections", "value": len(ipc_sections)},
        {"metric": "bns_corpus_sections", "value": len(bns_sections)},
        {"metric": "dev_samples", "value": len(dev_data)},
        {"metric": "test_samples", "value": len(test_data)},
        {"metric": "verified_mappings", "value": verified_count},
        {"metric": "conflicting_mappings", "value": len(conflicting)},
        {"metric": "leakage_overlapping_sections", "value": len(overlapping_sections)},
    ]
    for rel_type, count in relationship_types.items():
        csv_rows.append({"metric": f"relationship_{rel_type}", "value": count})

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(csv_rows)
    log.info(f"Dataset CSV summary saved to {output_csv}")

    return report


def build_classification_dataset(
    concordance_path: Optional[str] = None,
    ipc_path: Optional[str] = None,
    bns_path: Optional[str] = None,
    dev_path: Optional[str] = None,
    test_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Build a unified classification dataset from all available data sources.

    Each sample has:
    - sample_id: unique identifier
    - input_text: the query or IPC section text
    - ipc_section: IPC section number
    - bns_section: target BNS section (label)
    - relationship_type: concordance relationship type
    - source: where this sample came from
    """
    from src.utils.config import (
        CONCORDANCE_PATH, IPC_SECTIONS_PATH, BNS_SECTIONS_PATH,
        BENCHMARK_DEV_PATH, BENCHMARK_TEST_PATH
    )

    concordance_path = concordance_path or str(CONCORDANCE_PATH)
    ipc_path = ipc_path or str(IPC_SECTIONS_PATH)
    dev_path = dev_path or str(BENCHMARK_DEV_PATH)
    test_path = test_path or str(BENCHMARK_TEST_PATH)

    samples = []
    sample_id = 0

    # Source 1: Concordance table — each IPC→BNS mapping is a sample
    concordance = load_concordance(concordance_path)
    ipc_data = {r["section_number"]: r for r in load_jsonl(ipc_path)}

    for row in concordance:
        ipc_sec = row.get("ipc_section", "").strip()
        bns_sec = row.get("bns_section", "").strip()
        rel_type = row.get("relationship_type", "").strip()

        if not bns_sec or bns_sec in ("-", "—", "REPEALED"):
            continue  # Skip repealed / new_in_bns without IPC source

        ipc_title = row.get("ipc_title", "")
        ipc_text = ""
        if ipc_sec and ipc_sec in ipc_data:
            ipc_text = ipc_data[ipc_sec].get("section_text", "")

        input_text = f"IPC Section {ipc_sec}: {ipc_title}"
        if ipc_text:
            input_text += f". {ipc_text}"

        samples.append({
            "sample_id": f"CONC_{sample_id:04d}",
            "input_text": input_text,
            "ipc_section": ipc_sec,
            "bns_section": bns_sec,
            "relationship_type": rel_type,
            "source": "concordance",
        })
        sample_id += 1

    # Source 2: Benchmark dev queries
    dev_data = load_benchmark_csv(dev_path)
    for row in dev_data:
        gt_sections = row.get("ground_truth_sections", "").strip()
        if not gt_sections:
            continue
        samples.append({
            "sample_id": row.get("question_id", f"DEV_{sample_id:04d}"),
            "input_text": row.get("query_text", ""),
            "ipc_section": "",
            "bns_section": gt_sections.split(",")[0].strip(),
            "relationship_type": row.get("query_type", "transition"),
            "source": "benchmark_dev",
        })
        sample_id += 1

    # Source 3: Benchmark test queries
    test_data = load_benchmark_csv(test_path)
    for row in test_data:
        gt_sections = row.get("ground_truth_sections", "").strip()
        if not gt_sections:
            continue
        samples.append({
            "sample_id": row.get("question_id", f"TEST_{sample_id:04d}"),
            "input_text": row.get("query_text", ""),
            "ipc_section": "",
            "bns_section": gt_sections.split(",")[0].strip(),
            "relationship_type": row.get("query_type", "transition"),
            "source": "benchmark_test",
        })
        sample_id += 1

    log.info(f"Built classification dataset with {len(samples)} samples")
    return samples
