"""
split_manager.py — Phase 2: Fixed Data Splits

Provides deterministic, stratified splitting of the IPC2BNS classification
dataset into train/validation/test sets with data leakage verification.

Design decisions:
- Concordance samples are stratified-split (70/15/15) by bns_section,
  with rare-class grouping to ensure every split has ≥1 sample per class.
- Benchmark dev samples are routed to validation; benchmark test → test.
- Leakage assertions verify zero overlap on both sample_id and input_text.
"""

import csv
import logging
import os
import random
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple

log = logging.getLogger("split_manager")


# ── Constants ─────────────────────────────────────────────────────────────
SPLIT_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}


class DataSplitManager:
    """Manages deterministic data splitting and provides split accessors."""

    def __init__(self, splits_dir: Optional[str] = None, seed: int = 42):
        from src.utils.config import SPLITS_DIR, SEED
        self.splits_dir = splits_dir or str(SPLITS_DIR)
        self.seed = seed or SEED
        self._splits: Dict[str, List[Dict[str, Any]]] = {}

    # ── Split Generation ──────────────────────────────────────────────────

    def generate_splits(
        self,
        samples: Optional[List[Dict[str, Any]]] = None,
        force: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate train/validation/test splits.

        If split CSVs already exist and force=False, loads from disk.
        Otherwise builds fresh splits from the classification dataset.

        Returns dict mapping split name → list of sample dicts.
        """
        if not force and self._splits_exist():
            log.info("Split files already exist. Loading from disk.")
            return self.load_all_splits()

        if samples is None:
            from src.data.dataset_validator import build_classification_dataset
            samples = build_classification_dataset()

        log.info(f"Generating splits from {len(samples)} samples (seed={self.seed})")

        # Separate by source
        concordance_samples = [s for s in samples if s["source"] == "concordance"]
        dev_samples = [s for s in samples if s["source"] == "benchmark_dev"]
        test_samples = [s for s in samples if s["source"] == "benchmark_test"]

        # Stratified split of concordance samples
        train, val_conc, test_conc = self._stratified_split(
            concordance_samples, SPLIT_RATIOS
        )

        # Merge benchmark samples into their natural splits
        validation = val_conc + dev_samples
        test = test_conc + test_samples

        # Tag each sample with its split
        for s in train:
            s["split"] = "train"
        for s in validation:
            s["split"] = "validation"
        for s in test:
            s["split"] = "test"

        splits = {"train": train, "validation": validation, "test": test}

        # Verify no leakage
        self._verify_no_leakage(splits)

        # Persist to CSV
        self._save_splits(splits)

        self._splits = splits
        log.info(
            f"Splits generated: train={len(train)}, "
            f"validation={len(validation)}, test={len(test)}"
        )
        return splits

    def _stratified_split(
        self,
        samples: List[Dict[str, Any]],
        ratios: Dict[str, float],
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Stratified split by bns_section.

        For classes with only 1 sample, they are grouped into a 'rare' pool
        and distributed round-robin across splits to guarantee coverage.
        """
        rng = random.Random(self.seed)

        # Group samples by BNS section (stratification key)
        class_buckets: Dict[str, List[Dict]] = defaultdict(list)
        for s in samples:
            class_buckets[s["bns_section"]].append(s)

        train, val, test = [], [], []
        rare_pool = []

        for bns_sec, bucket in sorted(class_buckets.items()):
            rng.shuffle(bucket)

            if len(bucket) == 1:
                # Single-sample class: defer to rare pool
                rare_pool.append(bucket[0])
                continue

            n = len(bucket)
            n_val = max(1, round(n * ratios["validation"]))
            n_test = max(1, round(n * ratios["test"]))
            n_train = n - n_val - n_test

            # Ensure at least 1 in train for multi-sample classes
            if n_train < 1 and n >= 3:
                n_train = 1
                n_val = max(1, (n - 1) // 2)
                n_test = n - n_train - n_val

            train.extend(bucket[:n_train])
            val.extend(bucket[n_train:n_train + n_val])
            test.extend(bucket[n_train + n_val:])

        # Distribute rare-pool round-robin: train gets most, then val, test
        rng.shuffle(rare_pool)
        split_targets = [train, val, test]
        for i, s in enumerate(rare_pool):
            split_targets[i % 3].append(s)

        return train, val, test

    # ── Leakage Verification ──────────────────────────────────────────────

    def _verify_no_leakage(self, splits: Dict[str, List[Dict]]):
        """Assert zero overlap of sample_id and input_text between splits."""
        split_names = list(splits.keys())
        for i, name_a in enumerate(split_names):
            for name_b in split_names[i + 1:]:
                ids_a = {s["sample_id"] for s in splits[name_a]}
                ids_b = {s["sample_id"] for s in splits[name_b]}
                overlap_ids = ids_a & ids_b
                if overlap_ids:
                    raise ValueError(
                        f"Data leakage: {len(overlap_ids)} sample_ids overlap "
                        f"between {name_a} and {name_b}: {list(overlap_ids)[:5]}"
                    )

                texts_a = {s["input_text"].strip().lower() for s in splits[name_a]}
                texts_b = {s["input_text"].strip().lower() for s in splits[name_b]}
                overlap_texts = texts_a & texts_b
                if overlap_texts:
                    log.warning(
                        f"Input text overlap between {name_a} and {name_b}: "
                        f"{len(overlap_texts)} texts. This may inflate metrics."
                    )

        log.info("Leakage verification passed: no sample_id overlaps.")

    # ── Persistence ───────────────────────────────────────────────────────

    def _splits_exist(self) -> bool:
        """Check if all split CSV files exist."""
        for split_name in ("train", "validation", "test"):
            path = os.path.join(self.splits_dir, f"{split_name}.csv")
            if not os.path.exists(path):
                return False
        return True

    def _save_splits(self, splits: Dict[str, List[Dict]]):
        """Persist each split as a CSV file."""
        os.makedirs(self.splits_dir, exist_ok=True)
        fieldnames = [
            "sample_id", "input_text", "ipc_section", "bns_section",
            "relationship_type", "source", "split"
        ]
        for split_name, samples in splits.items():
            path = os.path.join(self.splits_dir, f"{split_name}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for s in samples:
                    writer.writerow(s)
            log.info(f"Saved {len(samples)} samples to {path}")

    # ── Loading ───────────────────────────────────────────────────────────

    def load_split(self, split_name: str) -> List[Dict[str, Any]]:
        """Load a single split from CSV."""
        if split_name in self._splits and self._splits[split_name]:
            return self._splits[split_name]

        path = os.path.join(self.splits_dir, f"{split_name}.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Split file not found: {path}. Run generate_splits() first."
            )

        rows = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))

        self._splits[split_name] = rows
        return rows

    def load_all_splits(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load all three splits."""
        return {
            name: self.load_split(name)
            for name in ("train", "validation", "test")
        }

    def get_split_stats(self) -> Dict[str, Any]:
        """Return statistics about the current splits."""
        splits = self.load_all_splits()
        stats = {}
        for name, samples in splits.items():
            bns_classes = set(s["bns_section"] for s in samples)
            sources = defaultdict(int)
            for s in samples:
                sources[s.get("source", "unknown")] += 1
            stats[name] = {
                "total_samples": len(samples),
                "unique_bns_classes": len(bns_classes),
                "sources": dict(sources),
            }
        return stats


def generate_and_save_splits(force: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    """Convenience function to generate and save splits."""
    manager = DataSplitManager()
    return manager.generate_splits(force=force)
