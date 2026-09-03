"""
chunker.py — Section-Level Statutory Corpus Chunker

Chunks bare-act legal text at the statutory SECTION level (not arbitrary token/character splits).
In statutory law, a section with its sub-sections, illustrations, and explanations represents
the atomic semantic unit of law.

Each chunk produced includes:
- chunk_id: e.g. "IPC_SEC_302", "BNS_SEC_103"
- act: "IPC" or "BNS"
- act_full_name: "Indian Penal Code, 1860" or "Bharatiya Nyaya Sanhita, 2023"
- section_number: canonical section identifier (e.g. "302", "304A", "2(1)")
- section_title: title/marginal heading of the section
- section_text: full text of the statutory provision
- chapter: chapter number / name if available
- effective_date_range: e.g. {"start": "1860-10-06", "end": "2024-06-30"} for IPC
- token_estimate: rough token length
"""

import os
import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class StatutoryChunk:
    chunk_id: str
    act: str                              # "IPC" or "BNS"
    act_full_name: str
    section_number: str
    section_title: str
    section_text: str
    chapter: str = ""
    effective_start: str = ""
    effective_end: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_content(self) -> str:
        """Returns the formatted chunk representation used for embedding and context feeding."""
        header = f"[{self.act_full_name} §{self.section_number}: {self.section_title}]"
        return f"{header}\n{self.section_text.strip()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "act": self.act,
            "act_full_name": self.act_full_name,
            "section_number": self.section_number,
            "section_title": self.section_title,
            "section_text": self.section_text,
            "chapter": self.chapter,
            "effective_date_range": {
                "start": self.effective_start,
                "end": self.effective_end
            },
            "full_content": self.full_content,
            "token_estimate": len(self.full_content.split()) * 4 // 3,
            "metadata": self.metadata
        }


class StatutoryChunker:
    """
    Parser and chunker for Indian statutory bare-act corpora.
    """

    EFFECTIVE_DATES = {
        "IPC": {"start": "1860-10-06", "end": "2024-06-30"},
        "BNS": {"start": "2024-07-01", "end": "9999-12-31"},
    }

    ACT_FULL_NAMES = {
        "IPC": "Indian Penal Code, 1860",
        "BNS": "Bharatiya Nyaya Sanhita, 2023",
    }

    @classmethod
    def create_chunk(cls, act: str, section_number: str, section_title: str,
                     section_text: str, chapter: str = "", metadata: Optional[Dict[str, Any]] = None) -> StatutoryChunk:
        act_upper = act.upper().strip()
        sec_clean = str(section_number).strip().upper()
        chunk_id = f"{act_upper}_SEC_{sec_clean}"
        dates = cls.EFFECTIVE_DATES.get(act_upper, {"start": "", "end": ""})

        return StatutoryChunk(
            chunk_id=chunk_id,
            act=act_upper,
            act_full_name=cls.ACT_FULL_NAMES.get(act_upper, act_upper),
            section_number=sec_clean,
            section_title=section_title.strip(),
            section_text=section_text.strip(),
            chapter=chapter.strip(),
            effective_start=dates["start"],
            effective_end=dates["end"],
            metadata=metadata or {}
        )

    @classmethod
    def chunk_jsonl_corpus(cls, jsonl_path: str, act: str) -> List[StatutoryChunk]:
        """
        Loads cleaned section JSONL and turns each entry into a StatutoryChunk.
        """
        chunks = []
        if not os.path.exists(jsonl_path):
            return chunks

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    sec_num = str(data.get("section_number", "")).strip()
                    if not sec_num or sec_num in ("PLACEHOLDER", "-", ""):
                        continue

                    chunk = cls.create_chunk(
                        act=act,
                        section_number=sec_num,
                        section_title=data.get("section_title", ""),
                        section_text=data.get("section_text", ""),
                        chapter=data.get("chapter", ""),
                        metadata=data.get("metadata", {})
                    )
                    chunks.append(chunk)
                except json.JSONDecodeError:
                    continue
        return chunks


def load_all_chunks(cleaned_dir: str) -> Dict[str, List[StatutoryChunk]]:
    """
    Loads all statutory chunks from cleaned JSONL files.
    Returns: {"IPC": [...], "BNS": [...], "ALL": [...]}
    """
    ipc_file = os.path.join(cleaned_dir, "ipc_sections.jsonl")
    bns_file = os.path.join(cleaned_dir, "bns_sections.jsonl")

    ipc_chunks = StatutoryChunker.chunk_jsonl_corpus(ipc_file, "IPC")
    bns_chunks = StatutoryChunker.chunk_jsonl_corpus(bns_file, "BNS")

    return {
        "IPC": ipc_chunks,
        "BNS": bns_chunks,
        "ALL": ipc_chunks + bns_chunks
    }
