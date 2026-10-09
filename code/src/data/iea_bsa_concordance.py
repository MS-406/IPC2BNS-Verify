"""
iea_bsa_concordance.py — Indian Evidence Act 1872 ↔ Bharatiya Sakshya Adhiniyam 2023 Concordance

Provides deterministic section mapping between IEA 1872 and BSA 2023,
extending the IPC↔BNS concordance framework to cover the Evidence Act transition.

Coverage: 45+ key provisions covering:
- Relevancy of facts (IEA §1–55 → BSA §1–55)
- Oral evidence, documentary evidence, burden of proof
- Witness competency, examination, impeaching credit
- Electronic evidence (new BSA provisions)
- Expert opinion evidence
- Presumptions (including digital record presumptions)

Source: India Code gazette, Kerala HC comparative tables, CAPT reference.
"""

import os
import csv
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class IEABSAMapping:
    iea_section: str
    bsa_section: Optional[str]
    iea_title: str
    bsa_title: str
    relationship_type: str   # "exact", "renumbered", "modified", "repealed", "new_in_bsa", "split"
    notes: str = ""
    verified: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iea_section": self.iea_section,
            "bsa_section": self.bsa_section,
            "iea_title": self.iea_title,
            "bsa_title": self.bsa_title,
            "relationship_type": self.relationship_type,
            "notes": self.notes,
            "verified": self.verified,
        }


# ── Core IEA → BSA Concordance Table ─────────────────────────────────────
# Based on official India Code gazette and comparative analyses
IEA_TO_BSA_TABLE: List[IEABSAMapping] = [
    # Part I — Relevancy of Facts
    IEABSAMapping("1", "1", "Short title, extent and commencement", "Short title, extent and commencement", "exact"),
    IEABSAMapping("2", "2", "Repeal of enactments", "Definitions", "modified", "BSA §2 consolidates definitions"),
    IEABSAMapping("3", "2", "Interpretation clause / Definitions", "Definitions", "renumbered"),
    IEABSAMapping("4", "3", "May presume", "May presume", "exact"),
    IEABSAMapping("5", "4", "Relevancy of facts forming part of same transaction (Res Gestae)", "Relevancy of facts forming part of same transaction", "exact"),
    IEABSAMapping("6", "4", "Relevancy of facts forming part of same transaction", "Relevancy of facts forming part of same transaction", "exact", "IEA §5 and §6 both map to BSA §4"),
    IEABSAMapping("7", "5", "Facts which are the occasion, cause or effect of facts in issue", "Facts which are the occasion, cause or effect of relevant facts", "exact"),
    IEABSAMapping("8", "6", "Motive, preparation and previous or subsequent conduct", "Motive, preparation and previous or subsequent conduct", "exact"),
    IEABSAMapping("9", "7", "Facts necessary to explain or introduce relevant facts", "Facts necessary to explain or introduce relevant facts", "exact"),
    IEABSAMapping("14", "12", "Facts showing existence of state of mind", "Facts showing existence of state of mind", "exact"),
    IEABSAMapping("15", "13", "Facts bearing on question whether act was accidental or intentional", "Facts bearing on question whether act was accidental or intentional", "exact"),
    IEABSAMapping("17", "14", "Admission defined", "Admission defined", "exact"),
    IEABSAMapping("21", "18", "Proof of admissions against persons making them", "Proof of admissions against persons making them", "exact"),
    IEABSAMapping("24", "20", "Confession caused by inducement, threat or promise when irrelevant", "Confession caused by inducement, threat or promise when irrelevant", "exact"),
    IEABSAMapping("25", "21", "Confession to police officer not to be proved", "Confession to police officer not to be proved", "exact"),
    IEABSAMapping("26", "22", "Confession by accused while in custody of police not to be proved", "Confession by accused while in custody of police not to be proved", "exact"),
    IEABSAMapping("27", "23", "How much of information received from accused may be proved", "How much of information received from accused may be proved", "exact"),
    IEABSAMapping("32", "27", "Cases in which statement of relevant fact by person who is dead or cannot be found", "Statement of relevant fact by person who is dead or cannot be found", "exact"),
    IEABSAMapping("45", "39", "Opinions of experts", "Opinions of experts", "exact"),
    IEABSAMapping("47", "41", "Opinion as to handwriting when relevant", "Opinion as to handwriting when relevant", "exact"),

    # Part II — Documentary Evidence
    IEABSAMapping("59", "47", "Proof of facts by oral evidence", "Proof of facts by oral evidence", "exact"),
    IEABSAMapping("61", "48", "Proof of contents of documents", "Proof of contents of documents", "exact"),
    IEABSAMapping("62", "49", "Primary evidence", "Primary evidence", "exact"),
    IEABSAMapping("63", "50", "Secondary evidence", "Secondary evidence", "modified", "BSA §50 broadened to include electronic copies"),
    IEABSAMapping("65A", "51", "Special provisions as to evidence relating to electronic record", "Special provisions as to evidence relating to electronic record", "modified", "BSA §51 strengthened electronic record admissibility"),
    IEABSAMapping("65B", "63", "Admissibility of electronic records", "Admissibility of electronic records", "modified", "BSA §63 overhauls digital evidence admissibility with certificate requirements"),
    IEABSAMapping("73A", "67", "Proof as to electronic signature", "Proof as to electronic signature", "exact"),
    IEABSAMapping("76", "70", "Certified copies of public documents", "Certified copies of public documents", "exact"),
    IEABSAMapping("78", "72", "Proof of other official documents", "Proof of other official documents", "exact"),
    IEABSAMapping("79", "73", "Presumption as to genuineness of certified copies", "Presumption as to genuineness of certified copies", "exact"),
    IEABSAMapping("85A", "79", "Presumption as to electronic agreements", "Presumption as to electronic agreements", "exact"),
    IEABSAMapping("85B", "80", "Presumption as to electronic records and electronic signatures", "Presumption as to electronic records and electronic signatures", "exact"),
    IEABSAMapping("85C", "81", "Presumption as to Digital Signature Certificates", "Presumption as to Digital Signature Certificates", "exact"),
    IEABSAMapping("88A", "84", "Presumption as to electronic messages", "Presumption as to electronic messages", "exact"),
    IEABSAMapping("90A", "86", "Presumption as to electronic records five years old", "Presumption as to electronic records five years old", "exact"),

    # Part III — Burden of Proof, Witness, Examination
    IEABSAMapping("101", "104", "Burden of proof", "Burden of proof", "exact"),
    IEABSAMapping("102", "105", "On whom burden of proof lies", "On whom burden of proof lies", "exact"),
    IEABSAMapping("103", "106", "Burden of proof as to particular fact", "Burden of proof as to particular fact", "exact"),
    IEABSAMapping("105", "108", "Burden of proving that case of accused comes within exceptions", "Burden of proving that case of accused comes within exceptions", "exact"),
    IEABSAMapping("106", "109", "Burden of proving fact especially within knowledge", "Burden of proving fact especially within knowledge", "exact"),
    IEABSAMapping("112", "115", "Birth during marriage conclusive proof of legitimacy", "Birth during marriage conclusive proof of legitimacy", "exact"),
    IEABSAMapping("113A", "116", "Presumption as to abetment of suicide by married woman", "Presumption as to abetment of suicide by married woman", "exact"),
    IEABSAMapping("113B", "117", "Presumption as to dowry death", "Presumption as to dowry death", "exact"),
    IEABSAMapping("114A", "118", "Presumption as to absence of consent in certain prosecution for rape", "Presumption as to absence of consent in certain prosecution for rape", "exact"),
    IEABSAMapping("118", "120", "Who may testify", "Who may testify", "exact"),
    IEABSAMapping("122", "124", "Communications during marriage", "Communications during marriage", "exact"),
    IEABSAMapping("126", "128", "Professional communications (legal privilege)", "Professional communications (legal privilege)", "exact"),
    IEABSAMapping("132", "134", "Witness not excused from answering on ground that answer will criminate", "Witness not excused from answering on ground that answer will criminate", "exact"),
    IEABSAMapping("135", "137", "Order of examinations — Chief, Cross, Re-examination", "Order of examinations — Chief, Cross, Re-examination", "exact"),
    IEABSAMapping("137", "139", "Cross-examination of person called to produce a document", "Cross-examination of person called to produce a document", "exact"),
    IEABSAMapping("145", "147", "Cross-examination as to previous statements in writing", "Cross-examination as to previous statements in writing", "exact"),
    IEABSAMapping("155", "153", "Impeaching credit of witness", "Impeaching credit of witness", "modified", "BSA §153 tightens impeachment procedures"),
    IEABSAMapping("165", "160", "Judge's power to put questions or order production", "Judge's power to put questions or order production", "exact"),
    IEABSAMapping("167", "162", "No new trial for improper admission or rejection of evidence", "No new trial for improper admission or rejection of evidence", "exact"),
]


# ── Index Maps ────────────────────────────────────────────────────────────
_IEA_TO_BSA_INDEX: Dict[str, IEABSAMapping] = {}
_BSA_TO_IEA_INDEX: Dict[str, IEABSAMapping] = {}

def _build_indexes():
    global _IEA_TO_BSA_INDEX, _BSA_TO_IEA_INDEX
    for m in IEA_TO_BSA_TABLE:
        _IEA_TO_BSA_INDEX[m.iea_section] = m
        if m.bsa_section:
            _BSA_TO_IEA_INDEX[m.bsa_section] = m

_build_indexes()


def map_iea_to_bsa(section: str) -> Optional[IEABSAMapping]:
    """Maps an IEA 1872 section to its BSA 2023 counterpart."""
    clean = re.sub(r'^(?:Section|Sec\.?|S\.?|§)\s*', '', section.strip(), flags=re.IGNORECASE).strip()
    return _IEA_TO_BSA_INDEX.get(clean)


def map_bsa_to_iea(section: str) -> Optional[IEABSAMapping]:
    """Maps a BSA 2023 section back to its IEA 1872 counterpart."""
    clean = re.sub(r'^(?:Section|Sec\.?|S\.?|§)\s*', '', section.strip(), flags=re.IGNORECASE).strip()
    return _BSA_TO_IEA_INDEX.get(clean)


def export_iea_bsa_csv(output_path: str):
    """Exports the IEA→BSA concordance table to CSV for ground truth."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "iea_section", "bsa_section", "iea_title", "bsa_title",
            "relationship_type", "notes", "verified"
        ])
        writer.writeheader()
        for m in IEA_TO_BSA_TABLE:
            writer.writerow(m.to_dict())
    print(f"Exported {len(IEA_TO_BSA_TABLE)} IEA→BSA concordance rows to {output_path}")


if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        root = os.path.dirname(root)
    out = os.path.join(root, "data", "eval_ground_truth", "iea_to_bsa_concordance.csv")
    export_iea_bsa_csv(out)
