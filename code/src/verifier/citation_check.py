"""
citation_check.py — Layer 1 Hard-Constraint Citation Existence Verifier

Deterministic Layer 1 gating:
1. Validates all extracted citations against the closed set of valid BNS 2023 / IPC 1860 section IDs.
2. Rejects phantom/hallucinated section numbers (e.g. [BNS §999], [BNS §450]).
3. Flags and vetoes citations of repealed provisions (e.g. IPC §124A sedition, §377, §497).
4. Supports dynamic section registration for post-refresh gazetted amendments.
"""

import os
import sys
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Tuple, Optional

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.mapping.lookup import get_lookup_engine, MappingStatus


@dataclass
class CitationCheckResult:
    is_valid: bool
    total_citations: int
    valid_citations: List[Dict[str, str]] = field(default_factory=list)
    invalid_citations: List[Dict[str, str]] = field(default_factory=list)
    repealed_citations: List[Dict[str, str]] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)


class CitationExistenceVerifier:
    """
    Layer 1 Hard-Constraint Verifier using closed-vocabulary statute validation.
    """

    REPEALED_IPC_SECTIONS = {"124A", "377", "497"}

    def __init__(self, concordance_path: Optional[str] = None):
        self.lookup = get_lookup_engine(concordance_path)
        self.valid_bns_ids: Set[str] = set(self.lookup.get_all_valid_bns_sections())
        self.valid_ipc_ids: Set[str] = set(self.lookup.get_all_valid_ipc_sections())

    def register_dynamic_sections(self, sections: List[str], act: str = "BNS"):
        """Registers newly gazetted amendment section IDs after a corpus refresh."""
        for s in sections:
            clean_s = self.lookup.clean_section_key(s)
            if act.upper() == "BNS":
                self.valid_bns_ids.add(clean_s)
            elif act.upper() == "IPC":
                self.valid_ipc_ids.add(clean_s)

    def verify_citations(self, citations: List[Dict[str, str]], require_bns: bool = True) -> CitationCheckResult:
        """
        Validates citations extracted from a model's generated text.
        """
        valid = []
        invalid = []
        repealed = []
        reasons = []

        for cit in citations:
            act = cit.get("act", "BNS").upper()
            sec_raw = cit.get("section", "").upper().strip()
            sec_clean = self.lookup.clean_section_key(sec_raw)
            base_sec = re.sub(r'\(.*?\)', '', sec_clean).strip()

            if act == "BNS":
                if sec_clean in self.valid_bns_ids or base_sec in self.valid_bns_ids:
                    valid.append(cit)
                else:
                    invalid.append(cit)
                    reasons.append(f"Invalid BNS Section ID: '{sec_raw}' does not exist in BNS 2023 statute.")

            elif act == "IPC":
                if sec_clean in self.REPEALED_IPC_SECTIONS or base_sec in self.REPEALED_IPC_SECTIONS:
                    repealed.append(cit)
                    reasons.append(f"Repealed Provision Cited: IPC Section {sec_raw} was repealed/struck down and has no direct BNS equivalent.")
                elif sec_clean in self.valid_ipc_ids or base_sec in self.valid_ipc_ids:
                    if require_bns:
                        reasons.append(f"Pre-transition Citation: IPC Section {sec_raw} cited for current law query.")
                    valid.append(cit)
                else:
                    invalid.append(cit)
                    reasons.append(f"Invalid IPC Section ID: '{sec_raw}' does not exist in IPC 1860 statute.")

        is_overall_valid = (len(invalid) == 0 and len(repealed) == 0 and len(valid) > 0)

        return CitationCheckResult(
            is_valid=is_overall_valid,
            total_citations=len(citations),
            valid_citations=valid,
            invalid_citations=invalid,
            repealed_citations=repealed,
            rejection_reasons=reasons
        )


# ── Global singleton ──────────────────────────────────────────────────────
_GLOBAL_CITATION_VERIFIER: Optional[CitationExistenceVerifier] = None


def get_citation_verifier() -> CitationExistenceVerifier:
    global _GLOBAL_CITATION_VERIFIER
    if _GLOBAL_CITATION_VERIFIER is None:
        _GLOBAL_CITATION_VERIFIER = CitationExistenceVerifier()
    return _GLOBAL_CITATION_VERIFIER
