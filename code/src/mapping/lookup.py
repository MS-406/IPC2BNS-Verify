"""
lookup.py — Deterministic IPC↔BNS Concordance Lookup Module

Provides fast, 100% deterministic section mapping between the Indian Penal Code
(IPC 1860) and Bharatiya Nyaya Sanhita (BNS 2023), backed by the versioned
ground-truth concordance table (data/02_ground_truth/concordance_v1.csv).

Design Principles:
1. Pure deterministic table lookup — zero LLM hallucination risk.
2. Explicit ambiguity handling:
   - Split sections (e.g., IPC §33 → BNS §2(1) / §2(25))
   - Merged sections (e.g., IPC §120A/120B → BNS §61)
   - Repealed sections (e.g., IPC §124A sedition, §377, §497)
   - Newly introduced offences (e.g., BNS §111 organised crime, §113 terror)
3. Returns structured MappingResult dataclass with status enum and rich metadata.
"""

import os
import csv
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


class MappingStatus(str, Enum):
    EXACT = "exact"                      # 1:1 direct equivalence
    RENUMBERED = "renumbered"            # Renumbered with identical/minor editorial changes
    AMBIGUOUS_SPLIT = "split"            # 1 IPC section split into multiple BNS sections
    AMBIGUOUS_MERGED = "merged"          # Multiple IPC sections merged into 1 BNS section
    REPEALED = "repealed"                # IPC section has no direct BNS counterpart (e.g., §124A, §377, §497)
    NEW_IN_BNS = "new_in_bns"            # BNS section with no IPC equivalent
    MODIFIED = "modified"                # Scope/punishment materially changed
    NOT_FOUND = "not_found"              # Section query does not exist in concordance index


@dataclass
class MappingResult:
    query_section: str
    target_section: Optional[str]
    source_act: str                      # "IPC" or "BNS"
    target_act: str                      # "BNS" or "IPC"
    source_title: str = ""
    target_title: str = ""
    status: MappingStatus = MappingStatus.NOT_FOUND
    is_ambiguous: bool = False
    notes: str = ""
    source_provenance: str = ""
    verified: bool = False
    all_matched_sections: List[str] = field(default_factory=list)

    @property
    def is_valid_mapping(self) -> bool:
        """True if the section successfully mapped without being repealed or missing."""
        return self.status not in (MappingStatus.REPEALED, MappingStatus.NOT_FOUND) and bool(self.target_section)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_section": self.query_section,
            "target_section": self.target_section,
            "source_act": self.source_act,
            "target_act": self.target_act,
            "source_title": self.source_title,
            "target_title": self.target_title,
            "status": self.status.value,
            "is_ambiguous": self.is_ambiguous,
            "notes": self.notes,
            "source_provenance": self.source_provenance,
            "verified": self.verified,
            "all_matched_sections": self.all_matched_sections,
        }


class ConcordanceLookup:
    """
    In-memory indexing and query engine for the IPC↔BNS concordance table.
    """

    def __init__(self, concordance_path: Optional[str] = None):
        self.concordance_path = concordance_path or self._default_concordance_path()
        self.ipc_to_bns_index: Dict[str, List[Dict[str, Any]]] = {}
        self.bns_to_ipc_index: Dict[str, List[Dict[str, Any]]] = {}
        self.raw_rows: List[Dict[str, Any]] = []
        self._load_table()

    @staticmethod
    def _default_concordance_path() -> str:
        root = os.environ.get("IPC2BNS_PROJECT_ROOT", "")
        if root and os.path.exists(root):
            return os.path.join(root, "data/02_ground_truth/concordance_v1.csv")
        # Fallback relative search
        curr = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            candidate = os.path.join(curr, "data/02_ground_truth/concordance_v1.csv")
            if os.path.exists(candidate):
                return candidate
            curr = os.path.dirname(curr)
        return "data/02_ground_truth/concordance_v1.csv"

    @staticmethod
    def clean_section_key(sec: str) -> str:
        """Standardize section number strings (e.g. 'Section 302', 'IPC 307', '§302' -> '302')."""
        if not sec:
            return ""
        s = str(sec).strip().upper()
        # Strip act names and section prefixes
        s = re.sub(r'^(?:INDIAN\s*PENAL\s*CODE|BHARATIYA\s*NYAYA\s*SANHITA|IPC|BNS)\s*', '', s, flags=re.IGNORECASE).strip()
        s = re.sub(r'^(?:SECTION|SEC\.?|S\.?|§)\s*', '', s, flags=re.IGNORECASE).strip()
        return s

    def _load_table(self):
        if not os.path.exists(self.concordance_path):
            raise FileNotFoundError(
                f"Concordance table not found at: {self.concordance_path}. "
                "Ensure Phase 0 has generated data/02_ground_truth/concordance_v1.csv"
            )

        self.ipc_to_bns_index.clear()
        self.bns_to_ipc_index.clear()
        self.raw_rows.clear()

        with open(self.concordance_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.raw_rows.append(row)
                ipc_sec = self.clean_section_key(row.get("ipc_section", ""))
                bns_sec = self.clean_section_key(row.get("bns_section", ""))

                # Index IPC -> BNS
                if ipc_sec:
                    # Handle multiple IPC sections listed (e.g. 375/376)
                    for sub_ipc in re.split(r'[,/&;]', ipc_sec):
                        sub_ipc = sub_ipc.strip()
                        if sub_ipc:
                            self.ipc_to_bns_index.setdefault(sub_ipc, []).append(row)

                # Index BNS -> IPC
                if bns_sec:
                    # Handle multiple BNS sections listed (e.g. 2(1)/2(25))
                    for sub_bns in re.split(r'[,/&;]', bns_sec):
                        sub_bns = sub_bns.strip()
                        if sub_bns:
                            self.bns_to_ipc_index.setdefault(sub_bns, []).append(row)

    def map_ipc_to_bns(self, ipc_section: str) -> MappingResult:
        """
        Maps an IPC section number to its BNS counterpart.
        Returns a structured MappingResult.
        """
        clean_key = self.clean_section_key(ipc_section)
        if not clean_key or clean_key not in self.ipc_to_bns_index:
            return MappingResult(
                query_section=ipc_section,
                target_section=None,
                source_act="IPC",
                target_act="BNS",
                status=MappingStatus.NOT_FOUND,
                is_ambiguous=False,
                notes=f"IPC Section '{ipc_section}' not found in concordance table."
            )

        entries = self.ipc_to_bns_index[clean_key]
        primary = entries[0]
        rel_type_str = primary.get("relationship_type", "").lower().strip()
        bns_sec = primary.get("bns_section", "").strip()
        notes = primary.get("notes", "").strip()

        # Handle repealed section (e.g. §124A, §377, §497)
        if rel_type_str == "repealed" or not bns_sec or bns_sec in ("-", "—", "REPEALED"):
            return MappingResult(
                query_section=clean_key,
                target_section=None,
                source_act="IPC",
                target_act="BNS",
                source_title=primary.get("ipc_title", ""),
                target_title="REPEALED (No direct BNS provision)",
                status=MappingStatus.REPEALED,
                is_ambiguous=True,
                notes=notes or "Section was repealed or struck down; no direct counterpart in BNS 2023.",
                source_provenance=primary.get("source", ""),
                verified=primary.get("verified", "").lower() == "true",
                all_matched_sections=[]
            )

        # Collect all mapped BNS sections if split
        all_targets = []
        for e in entries:
            target_str = e.get("bns_section", "").strip()
            for part in re.split(r'[,/&;]', target_str):
                p = part.strip()
                if p and p not in all_targets:
                    all_targets.append(p)

        is_split = (rel_type_str == "split") or (len(all_targets) > 1)
        is_merged = (rel_type_str == "merged")
        is_modified = (rel_type_str == "modified")

        if is_split:
            status = MappingStatus.AMBIGUOUS_SPLIT
            is_ambiguous = True
        elif is_merged:
            status = MappingStatus.AMBIGUOUS_MERGED
            is_ambiguous = True
        elif is_modified:
            status = MappingStatus.MODIFIED
            is_ambiguous = False
        elif rel_type_str == "exact":
            status = MappingStatus.EXACT
            is_ambiguous = False
        else:
            status = MappingStatus.RENUMBERED
            is_ambiguous = False

        return MappingResult(
            query_section=clean_key,
            target_section=bns_sec,
            source_act="IPC",
            target_act="BNS",
            source_title=primary.get("ipc_title", ""),
            target_title=primary.get("bns_title", ""),
            status=status,
            is_ambiguous=is_ambiguous,
            notes=notes,
            source_provenance=primary.get("source", ""),
            verified=primary.get("verified", "").lower() == "true",
            all_matched_sections=all_targets if len(all_targets) > 1 else [bns_sec]
        )

    def map_bns_to_ipc(self, bns_section: str) -> MappingResult:
        """
        Maps a BNS section number back to its IPC counterpart (reverse lookup).
        """
        clean_key = self.clean_section_key(bns_section)
        if not clean_key or clean_key not in self.bns_to_ipc_index:
            return MappingResult(
                query_section=bns_section,
                target_section=None,
                source_act="BNS",
                target_act="IPC",
                status=MappingStatus.NOT_FOUND,
                is_ambiguous=False,
                notes=f"BNS Section '{bns_section}' not found in concordance table."
            )

        entries = self.bns_to_ipc_index[clean_key]
        primary = entries[0]
        rel_type_str = primary.get("relationship_type", "").lower().strip()
        ipc_sec = primary.get("ipc_section", "").strip()
        notes = primary.get("notes", "").strip()

        # Handle newly introduced BNS section (e.g. §111, §112, §113, §69)
        if rel_type_str == "new_in_bns" or not ipc_sec or ipc_sec in ("-", "—", "N/A"):
            return MappingResult(
                query_section=clean_key,
                target_section=None,
                source_act="BNS",
                target_act="IPC",
                source_title=primary.get("bns_title", ""),
                target_title="NEW IN BNS (No IPC equivalent)",
                status=MappingStatus.NEW_IN_BNS,
                is_ambiguous=True,
                notes=notes or "New provision introduced in BNS 2023 with no prior IPC counterpart.",
                source_provenance=primary.get("source", ""),
                verified=primary.get("verified", "").lower() == "true",
                all_matched_sections=[]
            )

        # Collect all mapped IPC sections if merged
        all_targets = []
        for e in entries:
            target_str = e.get("ipc_section", "").strip()
            for part in re.split(r'[,/&;]', target_str):
                p = part.strip()
                if p and p not in all_targets:
                    all_targets.append(p)

        is_merged = (rel_type_str == "merged") or (len(all_targets) > 1)
        is_split = (rel_type_str == "split")

        if is_merged:
            status = MappingStatus.AMBIGUOUS_MERGED
            is_ambiguous = True
        elif is_split:
            status = MappingStatus.AMBIGUOUS_SPLIT
            is_ambiguous = True
        elif rel_type_str == "modified":
            status = MappingStatus.MODIFIED
            is_ambiguous = False
        elif rel_type_str == "exact":
            status = MappingStatus.EXACT
            is_ambiguous = False
        else:
            status = MappingStatus.RENUMBERED
            is_ambiguous = False

        return MappingResult(
            query_section=clean_key,
            target_section=ipc_sec,
            source_act="BNS",
            target_act="IPC",
            source_title=primary.get("bns_title", ""),
            target_title=primary.get("ipc_title", ""),
            status=status,
            is_ambiguous=is_ambiguous,
            notes=notes,
            source_provenance=primary.get("source", ""),
            verified=primary.get("verified", "").lower() == "true",
            all_matched_sections=all_targets if len(all_targets) > 1 else [ipc_sec]
        )

    def get_all_valid_bns_sections(self) -> List[str]:
        """Returns the complete set of valid BNS section IDs for verifier gating."""
        valid_ids = set()
        for row in self.raw_rows:
            bns = row.get("bns_section", "").strip()
            if bns and bns not in ("-", "—", "REPEALED", "N/A"):
                for part in re.split(r'[,/&;]', bns):
                    clean = self.clean_section_key(part)
                    if clean:
                        valid_ids.add(clean)
        return sorted(list(valid_ids))

    def get_all_valid_ipc_sections(self) -> List[str]:
        """Returns the complete set of valid IPC section IDs for verifier gating."""
        valid_ids = set()
        for row in self.raw_rows:
            ipc = row.get("ipc_section", "").strip()
            if ipc and ipc not in ("-", "—", "N/A"):
                for part in re.split(r'[,/&;]', ipc):
                    clean = self.clean_section_key(part)
                    if clean:
                        valid_ids.add(clean)
        return sorted(list(valid_ids))


# ── Global singleton accessors ───────────────────────────────────────────
_GLOBAL_LOOKUP: Optional[ConcordanceLookup] = None


# ── CrPC ↔ BNSS Procedural Law Mapping Table (Generalization Study) ────────
CRPC_TO_BNSS_MAP: Dict[str, Dict[str, str]] = {
    "154": {"bnss": "173", "title": "Information in cognizable cases (FIR & e-FIR)", "status": "exact"},
    "41": {"bnss": "35", "title": "When police may arrest without warrant", "status": "exact"},
    "47": {"bnss": "44", "title": "Search of place entered by person sought to be arrested", "status": "exact"},
    "167": {"bnss": "187", "title": "Procedure when investigation cannot be completed in 24 hours (Remand)", "status": "modified"},
    "438": {"bnss": "482", "title": "Direction for grant of bail to person apprehending arrest (Anticipatory Bail)", "status": "exact"},
    "437": {"bnss": "480", "title": "When bail may be taken in case of non-bailable offence", "status": "exact"},
    "144": {"bnss": "163", "title": "Power to issue order in urgent cases of nuisance / apprehended danger", "status": "exact"},
    "173": {"bnss": "193", "title": "Report of police officer on completion of investigation (Charge-sheet)", "status": "exact"},
    "164": {"bnss": "183", "title": "Recording of confessions and statements", "status": "exact"},
    "174": {"bnss": "194", "title": "Police to enquire and report on suicide (Inquest)", "status": "exact"},
    "106": {"bnss": "125", "title": "Security for keeping the peace on conviction", "status": "exact"},
    "125": {"bnss": "144", "title": "Order for maintenance of wives, children and parents", "status": "exact"},
    "265A": {"bnss": "289", "title": "Application of the Chapter (Plea Bargaining)", "status": "exact"},
    "260": {"bnss": "283", "title": "Power to try summarily", "status": "exact"},
    "320": {"bnss": "359", "title": "Compounding of offences", "status": "exact"},
    "321": {"bnss": "360", "title": "Withdrawal from prosecution", "status": "exact"},
    "374": {"bnss": "415", "title": "Appeals from convictions", "status": "exact"},
    "378": {"bnss": "419", "title": "Appeal in case of acquittal", "status": "exact"},
    "482": {"bnss": "528", "title": "Saving of inherent powers of High Court", "status": "exact"},
    "428": {"bnss": "468", "title": "Period of detention undergone by accused to be set off against sentence", "status": "exact"},
    "366": {"bnss": "453", "title": "Execution of order of death sentence", "status": "exact"},
    "356": {"bnss": "356", "title": "Trial in absentia of proclaimed offenders", "status": "exact"},
    "176(3)": {"bnss": "176(3)", "title": "Mandatory forensic investigation at crime scenes", "status": "exact"},
    "105": {"bnss": "105", "title": "Mandatory videography and electronic recording of search", "status": "exact"},
    "472": {"bnss": "472", "title": "Procedure and timelines for mercy petitions in death sentences", "status": "exact"}
}

BNSS_TO_CRPC_MAP: Dict[str, Dict[str, str]] = {
    v["bnss"]: {"crpc": k, "title": v["title"], "status": v["status"]}
    for k, v in CRPC_TO_BNSS_MAP.items()
}


def map_crpc_to_bnss(section: str) -> MappingResult:
    """Maps CrPC section to corresponding BNSS section."""
    clean_sec = re.sub(r'[^\w]', '', section.upper()).strip()
    match = CRPC_TO_BNSS_MAP.get(clean_sec)
    if match:
        return MappingResult(
            query_section=section,
            target_section=match["bnss"],
            source_act="CrPC",
            target_act="BNSS",
            source_title=match["title"],
            target_title=match["title"],
            status=MappingStatus.EXACT if match["status"] == "exact" else MappingStatus.MODIFIED,
            is_ambiguous=False,
            verified=True,
            all_matched_sections=[match["bnss"]]
        )
    return MappingResult(query_section=section, target_section=None, source_act="CrPC", target_act="BNSS", status=MappingStatus.NOT_FOUND)


def map_bnss_to_crpc(section: str) -> MappingResult:
    """Maps BNSS section to corresponding CrPC section."""
    clean_sec = re.sub(r'[^\w]', '', section.upper()).strip()
    match = BNSS_TO_CRPC_MAP.get(clean_sec)
    if match:
        return MappingResult(
            query_section=section,
            target_section=match["crpc"],
            source_act="BNSS",
            target_act="CrPC",
            source_title=match["title"],
            target_title=match["title"],
            status=MappingStatus.EXACT if match["status"] == "exact" else MappingStatus.MODIFIED,
            is_ambiguous=False,
            verified=True,
            all_matched_sections=[match["crpc"]]
        )
    return MappingResult(query_section=section, target_section=None, source_act="BNSS", target_act="CrPC", status=MappingStatus.NOT_FOUND)



def get_lookup_engine(concordance_path: Optional[str] = None) -> ConcordanceLookup:
    global _GLOBAL_LOOKUP
    if _GLOBAL_LOOKUP is None or (concordance_path and concordance_path != _GLOBAL_LOOKUP.concordance_path):
        _GLOBAL_LOOKUP = ConcordanceLookup(concordance_path)
    return _GLOBAL_LOOKUP


def map_ipc_to_bns(section: str, concordance_path: Optional[str] = None) -> MappingResult:
    return get_lookup_engine(concordance_path).map_ipc_to_bns(section)


def map_bns_to_ipc(section: str, concordance_path: Optional[str] = None) -> MappingResult:
    return get_lookup_engine(concordance_path).map_bns_to_ipc(section)


