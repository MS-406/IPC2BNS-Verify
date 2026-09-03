"""
build_amendments.py — Builds Injected Amendment Simulation Cases for Phase 5

Produces data/04_refresh_sim/injected_amendment_cases.csv containing synthetic
statutory legislative amendments to test post-refresh adaptivity without full pipeline retraining.
"""

import os
import csv
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_amendments")

AMENDMENT_CASES = [
    {
        "amendment_id": "AMD_2025_001",
        "act": "BNS",
        "section_number": "318A",
        "section_title": "Cheating by synthetic deepfake or generative AI impersonation",
        "section_text": "Whoever, by employing generative artificial intelligence, synthetic media, voice cloning, or deepfake technology, fraudulently impersonates another person to induce delivery of property or financial gain shall be punished with rigorous imprisonment for a term which may extend to seven years, and with fine up to ten lakh rupees.",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "change_type": "NEW_SECTION",
        "effective_start": "2025-01-01",
        "effective_end": "9999-12-31"
    },
    {
        "amendment_id": "AMD_2025_002",
        "act": "BNS",
        "section_number": "278A",
        "section_title": "Aggravated industrial pollution endangering public water supply",
        "section_text": "Whoever knowingly or negligently discharges hazardous industrial effluent or toxic pollutants into any public reservoir or river, rendering water noxious for human consumption, shall be punished with imprisonment up to five years, and with fine not less than twenty lakh rupees.",
        "chapter": "Chapter XIV — Of Offences Affecting the Public Health",
        "change_type": "NEW_SECTION",
        "effective_start": "2025-01-01",
        "effective_end": "9999-12-31"
    },
    {
        "amendment_id": "AMD_2025_003",
        "act": "BNS",
        "section_number": "106",
        "section_title": "Causing death by negligence (Amended)",
        "section_text": "(1) Whoever causes death by rash or negligent act not amounting to culpable homicide shall be punished with imprisonment up to five years. (2) Whoever causes death by rash driving and flees without reporting shall be punished with up to ten years. (3) Provided that where the driver immediately renders medical aid to the injured person and transports them to the nearest hospital before reporting, the court may reduce the sentence under sub-section (2) by up to half.",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "change_type": "MODIFIED_PUNISHMENT",
        "effective_start": "2025-01-01",
        "effective_end": "9999-12-31"
    }
]


def write_amendments_file(output_csv: str):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    fieldnames = [
        "amendment_id", "act", "section_number", "section_title",
        "section_text", "chapter", "change_type", "effective_start", "effective_end"
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(AMENDMENT_CASES)
    log.info(f"Saved {len(AMENDMENT_CASES)} amendment simulation cases to: {output_csv}")


if __name__ == "__main__":
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    out_file = os.path.join(root, "data/04_refresh_sim/injected_amendment_cases.csv")
    write_amendments_file(out_file)
