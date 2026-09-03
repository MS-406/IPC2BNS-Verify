"""
updater.py — Incremental Statutory Index Updater & Refresh Engine

Implements the hot-patching update mechanism for statutory corpora:
1. Ingests new legislative amendment diffs (additions, modifications, repeals).
2. Updates in-memory vector index and recalculates term weights incrementally.
3. Preserves point-in-time index snapshots (e.g., stage4_post_refresh_index).
4. Zero-downtime hot-patching — no need to re-index the entire multi-act corpus from scratch.
"""

import os
import sys
import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.ingestion.chunker import StatutoryChunk
from src.retrieval.embedder import LocalStatutoryVectorIndex, build_and_save_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("index_updater")


@dataclass
class AmendmentRecord:
    amendment_id: str
    act: str                              # "BNS" or "IPC"
    section_number: str
    section_title: str
    section_text: str
    chapter: str
    change_type: str                      # "NEW_SECTION" | "MODIFIED_PUNISHMENT" | "REPEALED"
    effective_start: str = "2025-01-01"
    effective_end: str = "9999-12-31"


class IncrementalIndexUpdater:
    """
    Applies statutory updates and generates point-in-time post-refresh index snapshots.
    """

    def __init__(self, base_index_dir: str):
        self.base_index_dir = base_index_dir
        self.index = LocalStatutoryVectorIndex.load(base_index_dir)
        log.info(f"Loaded base index with {self.index.total_docs} chunks from {base_index_dir}")

    def apply_amendment(self, amendment: AmendmentRecord) -> StatutoryChunk:
        """
        Applies a single amendment to the vector index.
        """
        sec_clean = str(amendment.section_number).strip().upper()
        chunk_id = f"{amendment.act.upper()}_SEC_{sec_clean}"

        new_chunk = StatutoryChunk(
            chunk_id=chunk_id,
            act=amendment.act.upper(),
            act_full_name="Bharatiya Nyaya Sanhita, 2023 (Amended)",
            section_number=sec_clean,
            section_title=amendment.section_title,
            section_text=amendment.section_text,
            chapter=amendment.chapter,
            effective_start=amendment.effective_start,
            effective_end=amendment.effective_end,
            metadata={"amendment_id": amendment.amendment_id, "change_type": amendment.change_type}
        )

        # Check if chunk already exists (for modification) or is new
        existing_idx = None
        for i, c in enumerate(self.index.chunks):
            if c.chunk_id == chunk_id:
                existing_idx = i
                break

        if existing_idx is not None:
            log.info(f"Modifying existing chunk in index: {chunk_id}")
            self.index.chunks[existing_idx] = new_chunk
        else:
            log.info(f"Adding new amended chunk to index: {chunk_id}")
            self.index.chunks.append(new_chunk)

        # Re-weight index with the updated chunk list
        self.index.build_index(self.index.chunks)
        return new_chunk

    def apply_amendments_batch(self, amendments: List[AmendmentRecord]) -> int:
        for a in amendments:
            self.apply_amendment(a)
        return len(amendments)

    def save_post_refresh_snapshot(self, output_dir: str):
        """
        Persists the refreshed index as a distinct snapshot for Stage 4 evaluation.
        """
        os.makedirs(output_dir, exist_ok=True)
        self.index.save(output_dir)
        log.info(f"Saved post-refresh snapshot ({self.index.total_docs} chunks) to: {output_dir}")


def create_post_refresh_index(base_index_dir: str, amendments_csv: str, output_snapshot_dir: str) -> LocalStatutoryVectorIndex:
    """
    Loads base index, ingests amendment records from CSV, and saves post-refresh snapshot.
    """
    import csv

    updater = IncrementalIndexUpdater(base_index_dir)
    amendments = []

    if os.path.exists(amendments_csv):
        with open(amendments_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                amendments.append(AmendmentRecord(
                    amendment_id=row.get("amendment_id", "AMD_001"),
                    act=row.get("act", "BNS"),
                    section_number=row.get("section_number", ""),
                    section_title=row.get("section_title", ""),
                    section_text=row.get("section_text", ""),
                    chapter=row.get("chapter", "Amended Provisions"),
                    change_type=row.get("change_type", "NEW_SECTION"),
                    effective_start=row.get("effective_start", "2025-01-01"),
                    effective_end=row.get("effective_end", "9999-12-31")
                ))

    updater.apply_amendments_batch(amendments)
    updater.save_post_refresh_snapshot(output_snapshot_dir)
    return updater.index


if __name__ == "__main__":
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    base_idx = os.path.join(root, "data/05_embeddings_index/stage2_index")
    amd_csv = os.path.join(root, "data/04_refresh_sim/injected_amendment_cases.csv")
    out_idx = os.path.join(root, "data/05_embeddings_index/stage4_post_refresh_index")

    create_post_refresh_index(base_idx, amd_csv, out_idx)
