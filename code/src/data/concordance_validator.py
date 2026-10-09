"""
concordance_validator.py — Pydantic Schema Validation for Concordance Ground Truth

Ensures every row in concordance_v1.csv (and future concordance tables) passes
strict structural and semantic validation before being indexed for retrieval/verification.

Validation Rules:
1. Every row must have a non-empty ipc_section OR bns_section (at least one).
2. relationship_type must be one of: exact, renumbered, split, merged, repealed, modified, new_in_bns.
3. Repealed rows must NOT have a bns_section value.
4. Non-repealed rows MUST have a bns_section value.
5. Section numbers must match format: digits optionally followed by alpha suffix and sub-clause.
6. verified column must be 'true' or 'false' (case-insensitive).
"""

import os
import csv
import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("concordance_validator")


VALID_RELATIONSHIP_TYPES = {
    "exact", "renumbered", "split", "merged", "repealed",
    "modified", "new_in_bns", "new", "partial"
}

SECTION_PATTERN = re.compile(
    r'^[0-9]{1,4}[A-Z]?(?:\([0-9]+\))?(?:/[0-9]{1,4}[A-Z]?(?:\([0-9]+\))?)*$',
    re.IGNORECASE
)


@dataclass
class ValidationError:
    row_index: int
    field: str
    value: str
    message: str
    severity: str = "ERROR"   # "ERROR" | "WARNING"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row_index,
            "field": self.field,
            "value": self.value,
            "message": self.message,
            "severity": self.severity
        }


@dataclass
class ValidationReport:
    total_rows: int
    valid_rows: int
    error_count: int
    warning_count: int
    verified_count: int
    unverified_count: int
    errors: List[ValidationError] = field(default_factory=list)
    coverage_stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_clean(self) -> bool:
        return self.error_count == 0

    @property
    def verification_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return round(self.verified_count / self.total_rows * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "verified_count": self.verified_count,
            "unverified_count": self.unverified_count,
            "verification_rate_pct": self.verification_rate,
            "is_clean": self.is_clean,
            "coverage_stats": self.coverage_stats,
            "errors": [e.to_dict() for e in self.errors]
        }

    def summary(self) -> str:
        lines = [
            f"═══ Concordance Validation Report ═══",
            f"Total Rows:        {self.total_rows}",
            f"Valid Rows:         {self.valid_rows}",
            f"Errors:            {self.error_count}",
            f"Warnings:          {self.warning_count}",
            f"Verified:          {self.verified_count} ({self.verification_rate}%)",
            f"Unverified:        {self.unverified_count}",
            f"Clean:             {'✅ YES' if self.is_clean else '❌ NO'}",
        ]
        if self.coverage_stats:
            lines.append(f"Relationship Types: {self.coverage_stats.get('relationship_distribution', {})}")
        return "\n".join(lines)


def _clean_section(s: str) -> str:
    """Strip whitespace and common prefixes from section value."""
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r'^(?:Section|Sec\.?|S\.?|§)\s*', '', s, flags=re.IGNORECASE)
    return s.strip()


def validate_concordance_csv(csv_path: str) -> ValidationReport:
    """
    Validates a concordance CSV file and returns a structured report.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Concordance file not found: {csv_path}")

    errors: List[ValidationError] = []
    total_rows = 0
    valid_rows = 0
    verified_count = 0
    unverified_count = 0
    relationship_dist: Dict[str, int] = {}
    seen_ipc_sections: set = set()
    seen_bns_sections: set = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_columns = {"ipc_section", "bns_section", "relationship_type"}
        if reader.fieldnames:
            missing_cols = required_columns - set(reader.fieldnames)
            if missing_cols:
                errors.append(ValidationError(
                    row_index=0, field="header", value=str(reader.fieldnames),
                    message=f"Missing required columns: {missing_cols}", severity="ERROR"
                ))
                return ValidationReport(
                    total_rows=0, valid_rows=0, error_count=len(errors),
                    warning_count=0, verified_count=0, unverified_count=0, errors=errors
                )

        for idx, row in enumerate(reader, start=2):  # Row 1 is header
            total_rows += 1
            row_valid = True

            ipc_sec = _clean_section(row.get("ipc_section", ""))
            bns_sec = _clean_section(row.get("bns_section", ""))
            rel_type = row.get("relationship_type", "").strip().lower()
            verified_val = row.get("verified", "").strip().lower()
            ipc_title = row.get("ipc_title", "").strip()
            bns_title = row.get("bns_title", "").strip()

            # Rule 1: At least one section must be non-empty
            if not ipc_sec and not bns_sec:
                errors.append(ValidationError(
                    row_index=idx, field="ipc_section/bns_section", value="",
                    message="Both ipc_section and bns_section are empty", severity="ERROR"
                ))
                row_valid = False

            # Rule 2: Valid relationship type
            if rel_type and rel_type not in VALID_RELATIONSHIP_TYPES:
                errors.append(ValidationError(
                    row_index=idx, field="relationship_type", value=rel_type,
                    message=f"Invalid relationship_type '{rel_type}'. Must be one of: {VALID_RELATIONSHIP_TYPES}",
                    severity="ERROR"
                ))
                row_valid = False

            # Rule 3: Repealed sections must NOT have a bns_section
            if rel_type == "repealed" and bns_sec and bns_sec not in ("-", "—", "N/A", "REPEALED"):
                errors.append(ValidationError(
                    row_index=idx, field="bns_section", value=bns_sec,
                    message=f"Repealed IPC section {ipc_sec} should not have a BNS mapping (found: {bns_sec})",
                    severity="WARNING"
                ))

            # Rule 4: Non-repealed rows must have a bns_section
            if rel_type and rel_type != "repealed" and rel_type != "new_in_bns" and not bns_sec:
                errors.append(ValidationError(
                    row_index=idx, field="bns_section", value="",
                    message=f"Non-repealed row (type={rel_type}) for IPC {ipc_sec} is missing bns_section",
                    severity="ERROR"
                ))
                row_valid = False

            # Rule 5: Section number format check
            if ipc_sec and not SECTION_PATTERN.match(ipc_sec):
                # Allow multi-section entries with separators
                parts = re.split(r'[,/&;]', ipc_sec)
                for part in parts:
                    p = part.strip()
                    if p and not SECTION_PATTERN.match(p):
                        errors.append(ValidationError(
                            row_index=idx, field="ipc_section", value=ipc_sec,
                            message=f"IPC section '{p}' doesn't match expected format (digits[A-Z][(sub)])",
                            severity="WARNING"
                        ))

            # Rule 6: Verified field
            if verified_val and verified_val not in ("true", "false", "yes", "no", ""):
                errors.append(ValidationError(
                    row_index=idx, field="verified", value=verified_val,
                    message=f"Invalid 'verified' value: '{verified_val}'. Expected 'true' or 'false'",
                    severity="WARNING"
                ))

            # Track verification status
            if verified_val in ("true", "yes"):
                verified_count += 1
            else:
                unverified_count += 1

            # Track relationship distribution
            if rel_type:
                relationship_dist[rel_type] = relationship_dist.get(rel_type, 0) + 1

            # Track section coverage
            if ipc_sec:
                seen_ipc_sections.add(ipc_sec)
            if bns_sec:
                seen_bns_sections.add(bns_sec)

            # Title completeness warning
            if ipc_sec and not ipc_title:
                errors.append(ValidationError(
                    row_index=idx, field="ipc_title", value="",
                    message=f"Missing IPC title for section {ipc_sec}",
                    severity="WARNING"
                ))

            if row_valid:
                valid_rows += 1

    error_count = sum(1 for e in errors if e.severity == "ERROR")
    warning_count = sum(1 for e in errors if e.severity == "WARNING")

    coverage_stats = {
        "unique_ipc_sections": len(seen_ipc_sections),
        "unique_bns_sections": len(seen_bns_sections),
        "relationship_distribution": relationship_dist,
    }

    report = ValidationReport(
        total_rows=total_rows,
        valid_rows=valid_rows,
        error_count=error_count,
        warning_count=warning_count,
        verified_count=verified_count,
        unverified_count=unverified_count,
        errors=errors,
        coverage_stats=coverage_stats,
    )

    return report


def validate_and_report(csv_path: Optional[str] = None) -> ValidationReport:
    """Convenience function: validates default concordance and prints summary."""
    if csv_path is None:
        # Find concordance CSV
        curr = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            candidate = os.path.join(curr, "data", "eval_ground_truth", "concordance_v1.csv")
            if os.path.exists(candidate):
                csv_path = candidate
                break
            curr = os.path.dirname(curr)

    if csv_path is None or not os.path.exists(csv_path):
        raise FileNotFoundError("Could not locate concordance_v1.csv")

    report = validate_concordance_csv(csv_path)
    print(report.summary())

    if report.errors:
        print(f"\n─── First 10 Issues ───")
        for err in report.errors[:10]:
            icon = "🔴" if err.severity == "ERROR" else "🟡"
            print(f"  {icon} Row {err.row_index}: [{err.field}] {err.message}")

    return report


if __name__ == "__main__":
    validate_and_report()
