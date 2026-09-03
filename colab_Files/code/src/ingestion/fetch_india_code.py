"""
fetch_india_code.py

Downloads and parses IPC 1860 and BNS 2023 bare-act text from India Code
(indiacode.nic.in). Outputs section-level JSONL files to data/00_raw/india_code/.

If India Code scraping fails (common — the site uses dynamic rendering),
falls back to:
  1. Attempting an alternative source (legislative.gov.in)
  2. Using the IEEE DataPort BNS CSV if available
  3. Prompting for manual upload

Usage (from project root):
    python code/src/ingestion/fetch_india_code.py

Colab usage:
    %run code/src/ingestion/fetch_india_code.py
"""

import os
import sys
import json
import time
import re
import logging
from datetime import datetime
from pathlib import Path

# ── Ensure project root is on path ──────────────────────────────────────
def get_project_root():
    """Find the project root (contains code/, data/, etc.)."""
    # Check environment variable first (set by Colab notebook)
    env_root = os.environ.get("IPC2BNS_PROJECT_ROOT")
    if env_root and os.path.isdir(env_root):
        return env_root
    # Default Colab path
    default = "/content/drive/MyDrive/NLP_rspaper"
    if os.path.isdir(default):
        return default
    # Fallback: walk up from this file
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "data").is_dir() and (current / "code").is_dir():
            return str(current)
        current = current.parent
    return os.getcwd()

PROJECT_ROOT = get_project_root()

# ── Setup logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("fetch_india_code")


# ─────────────────────────────────────────────────────────────────────────
# Section 1: HTTP helpers
# ─────────────────────────────────────────────────────────────────────────

def safe_request(url, max_retries=3, delay=2, timeout=30):
    """Make an HTTP GET request with retries and exponential backoff."""
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            wait = delay * (2 ** attempt)
            log.warning(f"Request failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                log.info(f"Retrying in {wait}s...")
                time.sleep(wait)
    return None


# ─────────────────────────────────────────────────────────────────────────
# Section 2: India Code scraper
# ─────────────────────────────────────────────────────────────────────────

def scrape_india_code_act(act_name, act_id, output_dir):
    """
    Attempt to scrape bare-act text from indiacode.nic.in.

    India Code uses DSpace with dynamic JS rendering, so direct scraping
    often fails. This function tries the main site and falls back to
    legislative.gov.in (which sometimes has static HTML versions).

    Returns: list of section dicts, or empty list if scraping fails.
    """
    from bs4 import BeautifulSoup

    log.info(f"Attempting to scrape {act_name} from India Code...")

    # India Code search URL pattern
    urls_to_try = [
        f"https://www.indiacode.nic.in/handle/123456789/{act_id}",
        f"https://www.indiacode.nic.in/show-data?actid={act_id}",
        f"https://legislative.gov.in/actsofparliamentfromtheyear/{act_id}",
    ]

    sections = []
    for url in urls_to_try:
        log.info(f"  Trying: {url}")
        resp = safe_request(url)
        if resp is None:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Try to find section-level content
        # India Code typically renders sections in divs or tables
        section_elements = soup.find_all(
            ["div", "section", "tr"],
            class_=re.compile(r"section|provision|act-section", re.I)
        )

        if not section_elements:
            # Try finding by text pattern (Section 1., Section 2., etc.)
            all_text = soup.get_text()
            section_pattern = re.compile(
                r'(?:Section\s+(\d+[A-Z]?))\s*[\.\-—]\s*(.+?)(?=Section\s+\d+|$)',
                re.DOTALL | re.IGNORECASE
            )
            matches = section_pattern.findall(all_text)
            if matches:
                for sec_num, sec_text in matches:
                    # Extract title (first line/sentence)
                    lines = sec_text.strip().split('\n')
                    title = lines[0].strip().rstrip('.').strip() if lines else ""
                    body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else sec_text.strip()
                    sections.append({
                        "act": act_name,
                        "section_number": sec_num.strip(),
                        "section_title": title[:200],
                        "section_text": body[:5000],
                        "source_url": url,
                        "scraped_at": datetime.now().isoformat()
                    })

        if sections:
            log.info(f"  Found {len(sections)} sections from {url}")
            break
        else:
            log.warning(f"  No sections found at {url}")

    return sections


def parse_act_from_text(text_content, act_name):
    """
    Parse bare-act text (from a manually downloaded or uploaded file)
    into section-level records.

    Handles common formats:
    - "1. Title of Act.—" followed by section text
    - "Section 1." followed by section text
    """
    sections = []

    # Pattern: section number followed by title and content
    # Handles: "302. Punishment for murder.—", "Section 302.", etc.
    patterns = [
        # "302. Title.—content..."
        re.compile(
            r'^(\d+[A-Z]?)\.\s*(.+?)[\.\-—]+\s*(.*?)(?=^\d+[A-Z]?\.\s|\Z)',
            re.MULTILINE | re.DOTALL
        ),
        # "Section 302. Title..." 
        re.compile(
            r'Section\s+(\d+[A-Z]?)\.\s*(.+?)(?=Section\s+\d+[A-Z]?\.\s|\Z)',
            re.DOTALL | re.IGNORECASE
        ),
    ]

    for pattern in patterns:
        matches = pattern.findall(text_content)
        if matches:
            for match in matches:
                if len(match) >= 2:
                    sec_num = match[0].strip()
                    title = match[1].strip().split('\n')[0].strip().rstrip('.')
                    body = match[2].strip() if len(match) > 2 else match[1].strip()
                    sections.append({
                        "act": act_name,
                        "section_number": sec_num,
                        "section_title": title[:200],
                        "section_text": body[:5000],
                        "source": "manual_text_parse",
                        "parsed_at": datetime.now().isoformat()
                    })
            break  # Use first matching pattern

    return sections


# ─────────────────────────────────────────────────────────────────────────
# Section 3: Fallback — IEEE DataPort BNS CSV
# ─────────────────────────────────────────────────────────────────────────

def load_ieee_dataport_csv(csv_path):
    """
    Load the IEEE DataPort BNS structured dataset (CSV).
    Expected columns: chapter, section_title, section_content
    """
    import csv

    sections = []
    if not os.path.exists(csv_path):
        log.warning(f"IEEE DataPort CSV not found at {csv_path}")
        return sections

    log.info(f"Loading IEEE DataPort BNS CSV from {csv_path}...")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Extract section number from section_title if possible
            title = row.get("section_title", "")
            sec_match = re.match(r'Section\s+(\d+[A-Z]?)', title, re.I)
            sec_num = sec_match.group(1) if sec_match else ""

            sections.append({
                "act": "Bharatiya Nyaya Sanhita, 2023",
                "section_number": sec_num,
                "chapter": row.get("chapter", ""),
                "section_title": title,
                "section_text": row.get("section_content", ""),
                "source": "ieee_dataport_csv",
                "parsed_at": datetime.now().isoformat()
            })

    log.info(f"Loaded {len(sections)} sections from IEEE DataPort CSV")
    return sections


# ─────────────────────────────────────────────────────────────────────────
# Section 4: Manual fallback — create placeholder with instructions
# ─────────────────────────────────────────────────────────────────────────

def create_placeholder_with_instructions(act_name, output_path):
    """
    When scraping fails, create a placeholder file with instructions
    for manual data collection.
    """
    instructions = {
        "status": "PLACEHOLDER — manual download needed",
        "act": act_name,
        "instructions": [
            f"1. Go to https://www.indiacode.nic.in",
            f"2. Search for '{act_name}'",
            f"3. Download or copy the full bare-act text",
            f"4. Save the text to this location: {output_path}",
            f"5. Re-run this script to parse the text into sections",
            "",
            "Alternative sources:",
            "  - legislative.gov.in",
            "  - Google 'BNS 2023 bare act text PDF'",
            "  - IEEE DataPort BNS dataset (CSV format)",
        ],
        "created_at": datetime.now().isoformat()
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(instructions, f, indent=2, ensure_ascii=False)

    log.info(f"Created placeholder with instructions at {output_path}")


# ─────────────────────────────────────────────────────────────────────────
# Section 5: Save output
# ─────────────────────────────────────────────────────────────────────────

def save_sections_jsonl(sections, output_path):
    """Save section list as JSONL (one JSON object per line)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for sec in sections:
            f.write(json.dumps(sec, ensure_ascii=False) + "\n")
    log.info(f"Saved {len(sections)} sections to {output_path}")


def save_raw_html(html_content, output_path):
    """Save raw HTML for archival/debugging."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


# ─────────────────────────────────────────────────────────────────────────
# Section 6: Main pipeline
# ─────────────────────────────────────────────────────────────────────────

def fetch_act(act_key, act_config, raw_dir, cleaned_dir):
    """
    Full pipeline for one act:
    1. Try scraping from India Code
    2. If that fails, try parsing manually uploaded text
    3. If that fails, try IEEE DataPort CSV (BNS only)
    4. If all fail, create placeholder with instructions
    """
    act_name = act_config["name"]
    act_id = act_config["act_id"]

    log.info(f"\n{'='*60}")
    log.info(f"Processing: {act_name}")
    log.info(f"{'='*60}")

    raw_out_dir = os.path.join(raw_dir, "india_code")
    os.makedirs(raw_out_dir, exist_ok=True)

    cleaned_file = os.path.join(
        cleaned_dir,
        f"{act_key}_sections.jsonl"
    )

    # Check if already done
    if os.path.exists(cleaned_file) and os.path.getsize(cleaned_file) > 100:
        log.info(f"Already exists: {cleaned_file}")
        with open(cleaned_file, "r") as f:
            count = sum(1 for _ in f)
        log.info(f"  Contains {count} sections. Skipping.")
        return count

    sections = []

    # Strategy 1: Try scraping
    try:
        sections = scrape_india_code_act(act_name, act_id, raw_out_dir)
    except Exception as e:
        log.warning(f"Scraping failed: {e}")

    # Strategy 2: Try parsing a manually uploaded text file
    if not sections:
        manual_files = [
            os.path.join(raw_out_dir, f"{act_key}_raw.txt"),
            os.path.join(raw_out_dir, f"{act_key}_raw.html"),
            os.path.join(raw_out_dir, f"{act_key}.txt"),
        ]
        for mf in manual_files:
            if os.path.exists(mf):
                log.info(f"Found manual file: {mf}")
                with open(mf, "r", encoding="utf-8") as f:
                    text = f.read()
                sections = parse_act_from_text(text, act_name)
                if sections:
                    break

    # Strategy 3: IEEE DataPort CSV (BNS only)
    if not sections and act_key == "bns":
        csv_candidates = [
            os.path.join(raw_dir, "bns_ieee_dataport", "bns_dataset.csv"),
            os.path.join(raw_dir, "bns_ieee_dataport.csv"),
        ]
        for csv_path in csv_candidates:
            if os.path.exists(csv_path):
                sections = load_ieee_dataport_csv(csv_path)
                if sections:
                    break

    # Strategy 4: Create placeholder
    if not sections:
        log.warning(f"All sources failed for {act_name}")
        placeholder_path = os.path.join(raw_out_dir, f"{act_key}_DOWNLOAD_NEEDED.json")
        create_placeholder_with_instructions(act_name, placeholder_path)

        # Create minimal stub so downstream code doesn't break
        stub_sections = [{
            "act": act_name,
            "section_number": "PLACEHOLDER",
            "section_title": "DATA NOT YET DOWNLOADED",
            "section_text": "This is a placeholder. See instructions in: " + placeholder_path,
            "source": "placeholder",
            "created_at": datetime.now().isoformat()
        }]
        save_sections_jsonl(stub_sections, cleaned_file)
        return 0

    # Save successfully parsed sections
    save_sections_jsonl(sections, cleaned_file)
    return len(sections)


def main():
    """Main entry point."""
    log.info("=" * 60)
    log.info("IPC2BNS-Verify: India Code Fetcher")
    log.info("=" * 60)

    raw_dir = os.path.join(PROJECT_ROOT, "data", "00_raw")
    cleaned_dir = os.path.join(PROJECT_ROOT, "data", "01_cleaned")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(cleaned_dir, exist_ok=True)

    # Acts to fetch (from config)
    acts = {
        "ipc": {
            "name": "Indian Penal Code, 1860",
            "act_id": "1860_45",
        },
        "bns": {
            "name": "Bharatiya Nyaya Sanhita, 2023",
            "act_id": "2023_45",
        },
    }

    results = {}
    for key, config in acts.items():
        try:
            count = fetch_act(key, config, raw_dir, cleaned_dir)
            results[key] = count
        except Exception as e:
            log.error(f"Error processing {key}: {e}")
            results[key] = 0

    # Summary
    log.info("\n" + "=" * 60)
    log.info("FETCH SUMMARY")
    log.info("=" * 60)
    for key, count in results.items():
        status = f"{count} sections" if count > 0 else "⚠️ NEEDS MANUAL DOWNLOAD"
        log.info(f"  {key.upper()}: {status}")

    total = sum(results.values())
    if total == 0:
        log.warning(
            "\n⚠️  No sections were scraped. This is expected — India Code "
            "uses dynamic rendering that blocks automated scraping.\n"
            "  Next steps:\n"
            "  1. Manually download IPC and BNS text from indiacode.nic.in\n"
            "  2. Save as .txt files in data/00_raw/india_code/\n"
            "  3. Re-run this script to parse them\n"
            "  See data/00_raw/india_code/*_DOWNLOAD_NEEDED.json for details."
        )

    return results


if __name__ == "__main__":
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        log.error("Missing dependencies. Install with:")
        log.error("  pip install requests beautifulsoup4")
        sys.exit(1)

    main()
