"""
extract_concordance_pdf.py

Extracts the IPC↔BNS correspondence table from a PDF source
(e.g., Kerala Prisons Dept. / CAPT Bhopal concordance table).

Uses camelot-py (preferred) or tabula-py for table extraction.
Outputs raw extracted rows to data/01_cleaned/concordance_extracted_raw.csv.

Usage:
    python code/src/mapping/extract_concordance_pdf.py \
        --pdf data/00_raw/concordance_source_pdfs/concordance_source_A.pdf \
        --out data/01_cleaned/concordance_extracted_raw.csv

Colab:
    %run code/src/mapping/extract_concordance_pdf.py \
        --pdf "$PROJECT_ROOT/data/00_raw/concordance_source_pdfs/concordance_source_A.pdf" \
        --out "$PROJECT_ROOT/data/01_cleaned/concordance_extracted_raw.csv"
"""

import os
import sys
import csv
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("extract_concordance_pdf")


# ─────────────────────────────────────────────────────────────────────────
# Table extraction strategies
# ─────────────────────────────────────────────────────────────────────────

def extract_with_camelot(pdf_path):
    """
    Extract tables using camelot-py (Ghostscript-based).
    Best for bordered/ruled tables common in government PDFs.
    """
    try:
        import camelot
    except ImportError:
        log.warning("camelot-py not installed. Install with: pip install camelot-py[cv] ghostscript")
        return None

    log.info("Attempting extraction with camelot-py (lattice mode)...")
    try:
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
        if not tables or len(tables) == 0:
            log.info("No lattice tables found, trying stream mode...")
            tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")

        if tables and len(tables) > 0:
            log.info(f"Found {len(tables)} table(s)")
            # Merge all tables into one DataFrame
            import pandas as pd
            all_rows = []
            for t in tables:
                df = t.df
                all_rows.append(df)
            merged = pd.concat(all_rows, ignore_index=True)
            return merged
    except Exception as e:
        log.warning(f"camelot extraction failed: {e}")

    return None


def extract_with_tabula(pdf_path):
    """
    Extract tables using tabula-py (Java-based).
    Fallback for when camelot fails.
    """
    try:
        import tabula
    except ImportError:
        log.warning("tabula-py not installed. Install with: pip install tabula-py")
        return None

    log.info("Attempting extraction with tabula-py...")
    try:
        import pandas as pd
        tables = tabula.read_pdf(pdf_path, pages="all", multiple_tables=True)
        if tables and len(tables) > 0:
            log.info(f"Found {len(tables)} table(s)")
            merged = pd.concat(tables, ignore_index=True)
            return merged
    except Exception as e:
        log.warning(f"tabula extraction failed: {e}")

    return None


def extract_with_pdfplumber(pdf_path):
    """
    Extract tables using pdfplumber (pure Python, no Java/Ghostscript).
    Most reliable in Colab environments.
    """
    try:
        import pdfplumber
    except ImportError:
        log.warning("pdfplumber not installed. Install with: pip install pdfplumber")
        return None

    log.info("Attempting extraction with pdfplumber...")
    try:
        import pandas as pd
        all_rows = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row and any(cell for cell in row if cell):
                            all_rows.append(row)
                if (i + 1) % 10 == 0:
                    log.info(f"  Processed page {i+1}/{len(pdf.pages)}")

        if all_rows:
            # Use first row as header if it looks like one
            max_cols = max(len(r) for r in all_rows)
            # Pad rows to same length
            padded = [r + [None] * (max_cols - len(r)) for r in all_rows]
            df = pd.DataFrame(padded)
            log.info(f"Extracted {len(df)} rows with {max_cols} columns")
            return df
    except Exception as e:
        log.warning(f"pdfplumber extraction failed: {e}")

    return None


# ─────────────────────────────────────────────────────────────────────────
# Post-processing
# ─────────────────────────────────────────────────────────────────────────

def clean_extracted_table(df):
    """
    Clean and normalize the extracted table.
    Tries to identify which columns map to:
    - BNS section number
    - BNS section title/description
    - IPC section number
    - IPC equivalent description
    - Comparison/notes
    """
    import pandas as pd

    log.info("Cleaning extracted table...")

    # Drop completely empty rows
    df = df.dropna(how="all").reset_index(drop=True)

    # Drop rows where all cells are empty strings
    df = df[df.apply(lambda row: any(str(cell).strip() for cell in row if cell), axis=1)]
    df = df.reset_index(drop=True)

    # Try to detect header row
    # Look for rows containing keywords like "Section", "BNS", "IPC", "Sl.No"
    header_keywords = ["section", "bns", "ipc", "sl", "no", "description",
                        "comparison", "equivalent", "provision", "offence"]

    header_idx = None
    for idx in range(min(5, len(df))):
        row_text = " ".join(str(v).lower() for v in df.iloc[idx] if v)
        matches = sum(1 for kw in header_keywords if kw in row_text)
        if matches >= 3:
            header_idx = idx
            break

    if header_idx is not None:
        # Use detected row as header
        new_header = [str(v).strip() if v else f"col_{i}"
                      for i, v in enumerate(df.iloc[header_idx])]
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
        df.columns = new_header[:len(df.columns)]
        log.info(f"Detected header at row {header_idx}: {list(df.columns)}")
    else:
        # Use generic column names
        df.columns = [f"col_{i}" for i in range(len(df.columns))]
        log.info("No header detected, using generic column names")

    # Strip whitespace from all cells
    for col in df.columns:
        df[col] = df[col].apply(lambda x: str(x).strip() if x and str(x).strip() != "None" else "")

    log.info(f"Cleaned table: {len(df)} rows, {len(df.columns)} columns")
    return df


def save_raw_csv(df, output_path):
    """Save the raw extracted (and cleaned) table as CSV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    log.info(f"Saved raw extraction to {output_path}")


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def extract_concordance(pdf_path, output_path):
    """
    Main extraction pipeline:
    1. Try pdfplumber (most reliable in Colab)
    2. Try camelot
    3. Try tabula
    4. Report failure
    """
    if not os.path.exists(pdf_path):
        log.error(f"PDF not found: {pdf_path}")
        log.info("Download the concordance PDF and place it at:")
        log.info(f"  {pdf_path}")
        return False

    log.info(f"Extracting tables from: {pdf_path}")

    # Try each extraction method
    df = None
    for extractor in [extract_with_pdfplumber, extract_with_camelot, extract_with_tabula]:
        df = extractor(pdf_path)
        if df is not None and len(df) > 0:
            break

    if df is None or len(df) == 0:
        log.error(
            "All extraction methods failed.\n"
            "Options:\n"
            "  1. Install dependencies: pip install pdfplumber camelot-py tabula-py\n"
            "  2. Manually transcribe the PDF table into CSV format\n"
            "  3. Try a different PDF source"
        )
        return False

    # Clean and save
    df = clean_extracted_table(df)
    save_raw_csv(df, output_path)

    log.info(f"\nExtraction complete!")
    log.info(f"  Rows: {len(df)}")
    log.info(f"  Columns: {list(df.columns)}")
    log.info(f"  Output: {output_path}")
    log.info(f"\nNext step: Run normalize_concordance.py to map these into the target schema.")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Extract concordance table from PDF"
    )
    parser.add_argument(
        "--pdf",
        default=None,
        help="Path to concordance source PDF"
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for raw extracted CSV"
    )
    args = parser.parse_args()

    # Defaults
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "/content/drive/MyDrive/NLP_rspaper")
    pdf_path = args.pdf or os.path.join(
        root, "data/00_raw/concordance_source_pdfs/concordance_source_A.pdf"
    )
    out_path = args.out or os.path.join(
        root, "data/01_cleaned/concordance_extracted_raw.csv"
    )

    extract_concordance(pdf_path, out_path)


if __name__ == "__main__":
    main()
