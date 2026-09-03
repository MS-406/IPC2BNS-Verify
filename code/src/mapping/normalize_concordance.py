"""
normalize_concordance.py

Takes the raw extracted concordance data (from extract_concordance_pdf.py
or a manually created CSV) and normalizes it into the target schema for
data/02_ground_truth/concordance_v1.csv.

Target schema (from the Concordance Runbook):
    ipc_section, ipc_title, bns_section, bns_title,
    relationship_type, notes, source, verified, last_updated

Usage:
    python code/src/mapping/normalize_concordance.py \
        --input data/01_cleaned/concordance_extracted_raw.csv \
        --output data/02_ground_truth/concordance_v1_draft.csv

Colab:
    %run code/src/mapping/normalize_concordance.py ...
"""

import os
import sys
import csv
import re
import argparse
import logging
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("normalize_concordance")


# ─────────────────────────────────────────────────────────────────────────
# Relationship type inference
# ─────────────────────────────────────────────────────────────────────────

# Keywords → relationship_type mapping
RELATIONSHIP_KEYWORDS = {
    "exact": [
        "no change", "same", "identical", "unchanged", "no modification",
        "reproduced", "verbatim"
    ],
    "renumbered": [
        "renumber", "re-number", "minor change", "minor modification",
        "slight", "marginal", "cosmetic", "editorial", "wording change"
    ],
    "split": [
        "split", "divided", "separated", "bifurcated",
        "broken into", "sub-divided"
    ],
    "merged": [
        "merged", "combined", "consolidated", "clubbed",
        "brought together", "amalgamated"
    ],
    "repealed": [
        "repealed", "omitted", "deleted", "removed", "dropped",
        "no counterpart", "no equivalent", "abolished", "struck down"
    ],
    "new_in_bns": [
        "new provision", "new section", "newly introduced", "new addition",
        "newly added", "fresh provision", "no ipc equivalent",
        "introduced for the first time"
    ],
    "modified": [
        "modified", "changed", "amended", "enhanced", "expanded",
        "increased", "reduced", "altered", "revised", "updated",
        "harsher", "stricter", "lenient", "broader", "narrower"
    ],
}


def infer_relationship_type(notes_text, ipc_section, bns_section):
    """
    Infer the relationship type from the comparison notes and section numbers.

    Priority:
    1. Explicit keywords in notes
    2. Structural clues (missing sections, multiple mappings)
    3. Default to 'renumbered' if section numbers differ
    """
    if not notes_text:
        notes_text = ""
    notes_lower = notes_text.lower().strip()

    # Check for no IPC section → new_in_bns
    if not ipc_section or ipc_section.strip() in ("", "-", "—", "N/A", "nil", "none"):
        return "new_in_bns"

    # Check for no BNS section → repealed
    if not bns_section or bns_section.strip() in ("", "-", "—", "N/A", "nil", "none"):
        return "repealed"

    # Check for multiple section numbers (split or merged)
    ipc_parts = re.split(r'[,/&;]', str(ipc_section))
    bns_parts = re.split(r'[,/&;]', str(bns_section))

    if len(ipc_parts) == 1 and len(bns_parts) > 1:
        return "split"
    if len(ipc_parts) > 1 and len(bns_parts) == 1:
        return "merged"

    # Check keywords in notes
    for rel_type, keywords in RELATIONSHIP_KEYWORDS.items():
        for kw in keywords:
            if kw in notes_lower:
                return rel_type

    # Default: if section numbers are different, it's renumbered
    if str(ipc_section).strip() != str(bns_section).strip():
        return "renumbered"

    return "exact"


# ─────────────────────────────────────────────────────────────────────────
# Column mapping heuristics
# ─────────────────────────────────────────────────────────────────────────

def detect_column_mapping(headers):
    """
    Try to map raw CSV column names to our target fields.
    Returns a dict: {target_field: source_column_name}
    """
    mapping = {}
    headers_lower = {h: h.lower().strip() for h in headers}

    patterns = {
        "ipc_section": r"ipc.*sec|old.*sec|sec.*ipc|ipc.*no|sl.*ipc",
        "ipc_title": r"ipc.*title|ipc.*desc|old.*title|ipc.*provision|offence.*ipc",
        "bns_section": r"bns.*sec|new.*sec|sec.*bns|bns.*no|sl.*bns|bharatiya",
        "bns_title": r"bns.*title|bns.*desc|new.*title|bns.*provision|offence.*bns",
        "notes": r"comparison|note|remark|comment|change|summary|observation",
    }

    for target, pattern in patterns.items():
        for orig, lower in headers_lower.items():
            if re.search(pattern, lower):
                mapping[target] = orig
                break

    # If we couldn't map any, try by column position
    if not mapping and len(headers) >= 3:
        log.warning("Could not auto-detect column mapping. Using positional fallback.")
        if len(headers) >= 5:
            mapping = {
                "bns_section": headers[0],
                "bns_title": headers[1],
                "ipc_section": headers[2],
                "ipc_title": headers[3],
                "notes": headers[4] if len(headers) > 4 else None,
            }
        elif len(headers) >= 3:
            mapping = {
                "ipc_section": headers[0],
                "bns_section": headers[1],
                "notes": headers[2],
            }

    return mapping


# ─────────────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────────────

def clean_section_number(raw):
    """Extract clean section number(s) from raw text."""
    if not raw:
        return ""
    raw = str(raw).strip()
    # Remove "Section" prefix
    raw = re.sub(r'^section\s+', '', raw, flags=re.I)
    # Remove surrounding whitespace and quotes
    raw = raw.strip().strip('"').strip("'").strip()
    return raw


def normalize_row(row, col_map, source_name):
    """
    Normalize a single raw row into the target concordance schema.
    """
    ipc_sec = clean_section_number(row.get(col_map.get("ipc_section", ""), ""))
    ipc_title = str(row.get(col_map.get("ipc_title", ""), "")).strip()
    bns_sec = clean_section_number(row.get(col_map.get("bns_section", ""), ""))
    bns_title = str(row.get(col_map.get("bns_title", ""), "")).strip()
    notes = str(row.get(col_map.get("notes", ""), "")).strip()

    # Clean up "None" and "nan" strings
    for val in [ipc_sec, ipc_title, bns_sec, bns_title, notes]:
        if val.lower() in ("none", "nan", "null"):
            val = ""

    rel_type = infer_relationship_type(notes, ipc_sec, bns_sec)

    return {
        "ipc_section": ipc_sec,
        "ipc_title": ipc_title,
        "bns_section": bns_sec,
        "bns_title": bns_title,
        "relationship_type": rel_type,
        "notes": notes,
        "source": source_name,
        "verified": "false",
        "last_updated": date.today().isoformat(),
    }


def normalize_concordance(input_path, output_path, source_name="concordance_pdf"):
    """
    Main normalization pipeline:
    1. Read raw extracted CSV
    2. Detect column mapping
    3. Normalize each row
    4. Write to target schema CSV
    """
    if not os.path.exists(input_path):
        log.error(f"Input file not found: {input_path}")
        return False

    log.info(f"Reading raw data from: {input_path}")

    # Read input
    rows = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    if not rows:
        log.error("No data rows found in input file.")
        return False

    log.info(f"  Raw rows: {len(rows)}")
    log.info(f"  Columns: {headers}")

    # Detect column mapping
    col_map = detect_column_mapping(headers)
    log.info(f"  Column mapping: {col_map}")

    if not col_map:
        log.error("Could not detect column mapping. Please check the input CSV format.")
        return False

    # Normalize
    normalized = []
    skipped = 0
    for row in rows:
        try:
            norm = normalize_row(row, col_map, source_name)
            # Skip rows where both IPC and BNS sections are empty
            if not norm["ipc_section"] and not norm["bns_section"]:
                skipped += 1
                continue
            normalized.append(norm)
        except Exception as e:
            log.warning(f"Error normalizing row: {e}")
            skipped += 1

    log.info(f"  Normalized: {len(normalized)} rows ({skipped} skipped)")

    # Relationship type distribution
    type_counts = {}
    for row in normalized:
        rt = row["relationship_type"]
        type_counts[rt] = type_counts.get(rt, 0) + 1
    log.info(f"  Relationship types: {type_counts}")

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = [
        "ipc_section", "ipc_title", "bns_section", "bns_title",
        "relationship_type", "notes", "source", "verified", "last_updated"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(normalized)

    log.info(f"\nNormalized concordance written to: {output_path}")
    log.info(f"Next step: Run cross_validate.py to verify against bare-act text.")

    return True


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Normalize extracted concordance data into target schema"
    )
    parser.add_argument("--input", required=True, help="Path to raw extracted CSV")
    parser.add_argument("--output", required=True, help="Output path for normalized CSV")
    parser.add_argument("--source", default="concordance_pdf",
                        help="Source name for provenance tracking")
    if argv is None and any("ipykernel" in a or "-f" in a or a.endswith(".json") for a in sys.argv):
        args, _ = parser.parse_known_args([])
    else:
        args = parser.parse_args(argv)

    normalize_concordance(args.input, args.output, args.source)


if __name__ == "__main__":
    main()
