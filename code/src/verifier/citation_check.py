"""
citation_check.py — Layer 1 Hard-Constraint Citation Existence & Cross-Statute Consistency Verifier

Deterministic Layer 1 & Layer 1.5 gating:
1. Validates all extracted citations against the closed set of valid BNS 2023 / IPC 1860 / CrPC / BNSS section IDs.
2. Rejects phantom/hallucinated section numbers (e.g. [BNS §999], [BNS §450]).
3. Flags and vetoes citations of repealed provisions (e.g. IPC §124A sedition, §377, §497).
4. Layer 1.5 Multi-Citation Cross-Statute Consistency Check:
   When an answer cites both an IPC and a BNS section (or CrPC and BNSS), verifies they are
   statutorily concordant (same substantive provision), catching cross-code mismatch hallucinations.
"""

import os
import sys
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Tuple, Optional

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.mapping.lookup import get_lookup_engine, map_ipc_to_bns, map_bns_to_ipc, map_crpc_to_bnss, map_bnss_to_crpc, MappingStatus


@dataclass
class CitationCheckResult:
    is_valid: bool
    total_citations: int
    valid_citations: List[Dict[str, str]] = field(default_factory=list)
    invalid_citations: List[Dict[str, str]] = field(default_factory=list)
    repealed_citations: List[Dict[str, str]] = field(default_factory=list)
    is_cross_statute_consistent: bool = True
    cross_statute_inconsistencies: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)


class CitationExistenceVerifier:
    """
    Layer 1 Hard-Constraint Verifier using closed-vocabulary statute validation
    and Layer 1.5 Multi-Citation Cross-Statute Consistency Verification.
    """

    REPEALED_IPC_SECTIONS = {"124A", "377", "497"}

    def __init__(self, concordance_path: Optional[str] = None):
        self.lookup = get_lookup_engine(concordance_path)
        self.valid_bns_ids: Set[str] = set(self.lookup.get_all_valid_bns_sections())
        self.valid_ipc_ids: Set[str] = set(self.lookup.get_all_valid_ipc_sections())
        # Procedural valid IDs
        self.valid_crpc_ids: Set[str] = {"154", "41", "47", "83", "167", "438", "437", "144", "173", "164", "174", "106", "125", "260", "320", "321", "374", "378", "482", "428", "366"}
        self.valid_bnss_ids: Set[str] = {"173", "35", "44", "86", "187", "482", "480", "163", "193", "183", "194", "125", "144", "283", "359", "360", "415", "419", "528", "468", "453", "356", "105", "176", "472", "530"}


    def register_dynamic_sections(self, sections: List[str], act: str = "BNS"):
        """Registers newly gazetted amendment section IDs after a corpus refresh."""
        for s in sections:
            clean_s = self.lookup.clean_section_key(s)
            if act.upper() == "BNS":
                self.valid_bns_ids.add(clean_s)
            elif act.upper() == "IPC":
                self.valid_ipc_ids.add(clean_s)

    def verify_cross_statute_consistency(self, citations: List[Dict[str, str]]) -> Tuple[bool, List[str]]:
        """
        Layer 1.5: Verifies that when both pre-transition (IPC/CrPC) and post-transition (BNS/BNSS)
        citations are present in the same output, they are concordant to the same substantive provision.
        """
        inconsistencies = []

        ipc_secs = [self.lookup.clean_section_key(c["section"]) for c in citations if c.get("act", "").upper() == "IPC"]
        bns_secs = [self.lookup.clean_section_key(c["section"]) for c in citations if c.get("act", "").upper() == "BNS"]
        crpc_secs = [self.lookup.clean_section_key(c["section"]) for c in citations if c.get("act", "").upper() == "CRPC"]
        bnss_secs = [self.lookup.clean_section_key(c["section"]) for c in citations if c.get("act", "").upper() == "BNSS"]

        # 1. Substantive IPC <-> BNS Consistency Check
        if ipc_secs and bns_secs:
            for ipc_s in ipc_secs:
                # Skip general definitions or cross-references if single citation
                if ipc_s in ("11", "21", "22", "23"):
                    continue
                map_res = map_ipc_to_bns(ipc_s)
                if map_res.status not in (MappingStatus.REPEALED, MappingStatus.NOT_FOUND) and map_res.target_section:
                    expected_bns = [self.lookup.clean_section_key(s) for s in map_res.all_matched_sections]
                    # Check if any cited BNS section is concordant with this IPC section
                    has_concordance = any(
                        b_s in expected_bns or any(b_s.startswith(exp) for exp in expected_bns)
                        for b_s in bns_secs
                    )
                    if not has_concordance:
                        inconsistencies.append(
                            f"Cross-statute citation mismatch: Cited [IPC §{ipc_s}] maps to BNS §{map_res.target_section}, "
                            f"which conflicts with cited [BNS §{', '.join(bns_secs)}]."
                        )

        # 2. Procedural CrPC <-> BNSS Consistency Check
        if crpc_secs and bnss_secs:
            for crpc_s in crpc_secs:
                map_res = map_crpc_to_bnss(crpc_s)
                if map_res.is_valid_mapping:
                    expected_bnss = [self.lookup.clean_section_key(s) for s in map_res.all_matched_sections]
                    has_concordance = any(
                        bn_s in expected_bnss or any(bn_s.startswith(exp) for exp in expected_bnss)
                        for bn_s in bnss_secs
                    )
                    if not has_concordance:
                        inconsistencies.append(
                            f"Cross-statute citation mismatch: Cited [CrPC §{crpc_s}] maps to BNSS §{map_res.target_section}, "
                            f"which conflicts with cited [BNSS §{', '.join(bnss_secs)}]."
                        )

        is_consistent = len(inconsistencies) == 0
        return is_consistent, inconsistencies

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
                    reasons.append(f"Invalid BNS Section Cited: Section {sec_raw} does not exist in BNS 2023.")

            elif act == "IPC":
                if sec_clean in self.REPEALED_IPC_SECTIONS:
                    repealed.append(cit)
                    reasons.append(f"Repealed Provision Cited: IPC Section {sec_raw} was repealed/struck down and has no direct BNS equivalent.")
                elif sec_clean in self.valid_ipc_ids or base_sec in self.valid_ipc_ids:
                    valid.append(cit)
                    reasons.append(f"Pre-transition Citation: IPC Section {sec_raw} cited for current law query.")
                else:
                    invalid.append(cit)
                    reasons.append(f"Invalid IPC Section Cited: Section {sec_raw} is not a recognized IPC provision.")

            elif act == "CRPC":
                if sec_clean in self.valid_crpc_ids or base_sec in self.valid_crpc_ids:
                    valid.append(cit)
                    reasons.append(f"Pre-transition Citation: CrPC Section {sec_raw} cited.")
                else:
                    invalid.append(cit)
                    reasons.append(f"Invalid CrPC Section Cited: Section {sec_raw} not recognized.")

            elif act == "BNSS":
                if sec_clean in self.valid_bnss_ids or base_sec in self.valid_bnss_ids:
                    valid.append(cit)
                else:
                    invalid.append(cit)
                    reasons.append(f"Invalid BNSS Section Cited: Section {sec_raw} not recognized.")

            else:
                invalid.append(cit)
                reasons.append(f"Unrecognized Act: '{act}' is not a supported statutory code.")

        is_valid = len(invalid) == 0 and len(repealed) == 0 and len(valid) > 0

        # Run Layer 1.5 Multi-Citation Cross-Statute Consistency Check
        is_cross_consistent, cross_inconsistencies = self.verify_cross_statute_consistency(valid)
        if not is_cross_consistent:
            is_valid = False
            reasons.extend(cross_inconsistencies)

        return CitationCheckResult(
            is_valid=is_valid,
            total_citations=len(citations),
            valid_citations=valid,
            invalid_citations=invalid,
            repealed_citations=repealed,
            is_cross_statute_consistent=is_cross_consistent,
            cross_statute_inconsistencies=cross_inconsistencies,
            rejection_reasons=reasons
        )


# ── Global singleton accessor ─────────────────────────────────────────────
_GLOBAL_CITATION_VERIFIER = None


def get_citation_verifier(concordance_path: Optional[str] = None) -> CitationExistenceVerifier:
    global _GLOBAL_CITATION_VERIFIER
    if _GLOBAL_CITATION_VERIFIER is None:
        _GLOBAL_CITATION_VERIFIER = CitationExistenceVerifier(concordance_path)
    return _GLOBAL_CITATION_VERIFIER
