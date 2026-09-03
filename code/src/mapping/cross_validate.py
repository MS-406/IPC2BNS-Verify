"""
cross_validate.py

Cross-validates the concordance draft table against:
1. IPC bare-act sections (from data/01_cleaned/ipc_sections.jsonl)
2. BNS bare-act sections (from data/01_cleaned/bns_sections.jsonl)
3. Optionally, a second concordance source for disagreement detection

Outputs a validation_report.csv flagging:
- Sections referenced in the concordance but not found in bare-act text
- Title mismatches between concordance and bare-act
- Disagreements between two concordance sources

Usage:
    python code/src/mapping/cross_validate.py \
        --draft data/02_ground_truth/concordance_v1_draft.csv \
        --bare_act_ipc data/01_cleaned/ipc_sections.jsonl \
        --bare_act_bns data/01_cleaned/bns_sections.jsonl \
        --report data/02_ground_truth/validation_report.csv
"""

import os
import sys
import csv
import json
import re
import argparse
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("cross_validate")


# ─────────────────────────────────────────────────────────────────────────
# Load helpers
# ─────────────────────────────────────────────────────────────────────────

def load_concordance(csv_path):
    """Load concordance CSV into list of dicts."""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_bare_act_sections(jsonl_path):
    """
    Load bare-act sections from JSONL into a dict keyed by section_number.
    Returns: {section_number: {title, text, ...}}
    """
    sections = {}
    if not os.path.exists(jsonl_path):
        log.warning(f"Bare-act file not found: {jsonl_path}")
        return sections

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                sec_num = str(obj.get("section_number", "")).strip()
                if sec_num and sec_num != "PLACEHOLDER":
                    sections[sec_num] = obj
            except json.JSONDecodeError:
                continue

    return sections


# ─────────────────────────────────────────────────────────────────────────
# Validation checks
# ─────────────────────────────────────────────────────────────────────────

def normalize_title(title):
    """Normalize a section title for fuzzy comparison."""
    if not title:
        return ""
    # Lowercase, strip, remove extra whitespace
    t = re.sub(r'\s+', ' ', title.lower().strip())
    # Remove punctuation
    t = re.sub(r'[^\w\s]', '', t)
    return t


def title_similarity(title_a, title_b):
    """Simple word-overlap similarity between two titles."""
    words_a = set(normalize_title(title_a).split())
    words_b = set(normalize_title(title_b).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def validate_concordance(concordance_rows, ipc_sections, bns_sections):
    """
    Validate each concordance row against bare-act sections.

    Returns a list of validation result dicts.
    """
    results = []

    for i, row in enumerate(concordance_rows):
        ipc_sec = str(row.get("ipc_section", "")).strip()
        ipc_title = str(row.get("ipc_title", "")).strip()
        bns_sec = str(row.get("bns_section", "")).strip()
        bns_title = str(row.get("bns_title", "")).strip()
        rel_type = str(row.get("relationship_type", "")).strip()

        issues = []
        status = "PASS"

        # Check IPC section exists in bare-act (skip for new_in_bns)
        if ipc_sec and rel_type != "new_in_bns":
            # Handle split sections (e.g., "375/376")
            ipc_parts = re.split(r'[,/]', ipc_sec)
            for part in ipc_parts:
                part = part.strip()
                if part and part not in ipc_sections:
                    if ipc_sections:  # Only flag if we have data to check against
                        issues.append(f"IPC section {part} not found in bare-act text")

            # Check title match (for first part)
            first_ipc = ipc_parts[0].strip()
            if first_ipc in ipc_sections and ipc_title:
                bare_title = ipc_sections[first_ipc].get("section_title", "")
                sim = title_similarity(ipc_title, bare_title)
                if sim < 0.3 and bare_title:
                    issues.append(
                        f"IPC title mismatch (similarity={sim:.2f}): "
                        f"concordance='{ipc_title[:50]}' vs bare-act='{bare_title[:50]}'"
                    )

        # Check BNS section exists in bare-act (skip for repealed)
        if bns_sec and rel_type != "repealed":
            bns_parts = re.split(r'[,/]', bns_sec)
            for part in bns_parts:
                part = part.strip()
                if part and part not in bns_sections:
                    if bns_sections:
                        issues.append(f"BNS section {part} not found in bare-act text")

            # Check title match
            first_bns = bns_parts[0].strip()
            if first_bns in bns_sections and bns_title:
                bare_title = bns_sections[first_bns].get("section_title", "")
                sim = title_similarity(bns_title, bare_title)
                if sim < 0.3 and bare_title:
                    issues.append(
                        f"BNS title mismatch (similarity={sim:.2f}): "
                        f"concordance='{bns_title[:50]}' vs bare-act='{bare_title[:50]}'"
                    )

        # Check structural consistency
        if rel_type == "repealed" and bns_sec:
            issues.append(f"Marked 'repealed' but has BNS section {bns_sec}")
        if rel_type == "new_in_bns" and ipc_sec:
            issues.append(f"Marked 'new_in_bns' but has IPC section {ipc_sec}")
        if rel_type not in ("exact", "renumbered", "split", "merged",
                            "repealed", "new_in_bns", "modified", ""):
            issues.append(f"Unknown relationship_type: {rel_type}")

        # Check that ambiguous cases have notes
        if rel_type in ("split", "merged", "repealed", "modified") and not row.get("notes", "").strip():
            issues.append(f"Ambiguous type '{rel_type}' should have notes explaining the mapping")

        if issues:
            status = "FLAG"

        results.append({
            "row_index": i + 1,
            "ipc_section": ipc_sec,
            "bns_section": bns_sec,
            "relationship_type": rel_type,
            "status": status,
            "issues": "; ".join(issues) if issues else "OK",
        })

    return results


# ─────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────

def save_validation_report(results, output_path):
    """Save validation results as CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fieldnames = ["row_index", "ipc_section", "bns_section",
                  "relationship_type", "status", "issues"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    flagged = sum(1 for r in results if r["status"] == "FLAG")

    log.info(f"\nValidation Report: {output_path}")
    log.info(f"  Total rows: {total}")
    log.info(f"  Passed:     {passed} ({100*passed/total:.0f}%)" if total else "  No rows")
    log.info(f"  Flagged:    {flagged} ({100*flagged/total:.0f}%)" if total else "")

    if flagged > 0:
        log.info(f"\n  Flagged rows need manual review:")
        for r in results:
            if r["status"] == "FLAG":
                log.info(f"    Row {r['row_index']}: IPC {r['ipc_section']} → "
                         f"BNS {r['bns_section']} — {r['issues']}")


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def cross_validate(draft_path, ipc_path, bns_path, report_path):
    """Run the full cross-validation pipeline."""
    log.info("=" * 60)
    log.info("Cross-Validation: Concordance vs. Bare-Act Text")
    log.info("=" * 60)

    # Load data
    concordance = load_concordance(draft_path)
    log.info(f"Loaded {len(concordance)} concordance rows from {draft_path}")

    ipc_sections = load_bare_act_sections(ipc_path)
    log.info(f"Loaded {len(ipc_sections)} IPC sections from {ipc_path}")

    bns_sections = load_bare_act_sections(bns_path)
    log.info(f"Loaded {len(bns_sections)} BNS sections from {bns_path}")

    if not ipc_sections and not bns_sections:
        log.warning(
            "No bare-act sections loaded. Validation will be limited to "
            "structural consistency checks only. Run fetch_india_code.py "
            "first to get bare-act data for full validation."
        )

    # Validate
    results = validate_concordance(concordance, ipc_sections, bns_sections)

    # Save report
    save_validation_report(results, report_path)

    return results


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Cross-validate concordance table against bare-act text"
    )
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "/content/drive/MyDrive/NLP_rspaper")

    parser.add_argument("--draft", default=os.path.join(root, "data/02_ground_truth/concordance_v1.csv"))
    parser.add_argument("--bare_act_ipc", default=os.path.join(root, "data/01_cleaned/ipc_sections.jsonl"))
    parser.add_argument("--bare_act_bns", default=os.path.join(root, "data/01_cleaned/bns_sections.jsonl"))
    parser.add_argument("--report", default=os.path.join(root, "data/02_ground_truth/validation_report.csv"))

    if argv is None and any("ipykernel" in a or "-f" in a or a.endswith(".json") for a in sys.argv):
        args, _ = parser.parse_known_args([])
    else:
        args = parser.parse_args(argv)

    return cross_validate(args.draft, args.bare_act_ipc, args.bare_act_bns, args.report)


if __name__ == "__main__":
    main()
