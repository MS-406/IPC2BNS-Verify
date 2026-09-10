"""
query_expander.py — Concordance-Assisted Query Expansion Engine

Enriches user legal queries by:
1. Extracting explicit historical IPC/CrPC sections via regex.
2. Mapping extracted sections to canonical BNS/BNSS provisions via the Concordance table.
3. Expanding colloquial/domain offence terms (e.g. "cheating", "rash driving", "dowry death")
   with official statutory titles and modern section keywords.
4. Outputting an enriched query that boosts lexical and semantic retrieval recall.
"""

import os
import sys
import re
from typing import Optional, Dict, Any, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from src.mapping.lookup import ConcordanceLookup


class ConcordanceQueryExpander:
    """
    Deterministically expands legal queries using the statutory concordance table.
    """

    # Domain legal synonym mappings for high-frequency offences
    OFFENCE_LEXICON = {
        "murder": "Section 103 BNS Murder culpable homicide",
        "culpable homicide": "Section 100 BNS Culpable homicide not amounting to murder",
        "cheating": "Section 318 BNS Cheating dishonestly inducing delivery of property",
        "fraud": "Section 318 BNS Cheating fraud dishonestly inducing",
        "dowry death": "Section 80 BNS Dowry death cruelty husband relatives",
        "rash driving": "Section 281 BNS Rash driving riding public way danger",
        "negligent driving": "Section 281 BNS Section 106 BNS Rash negligent act death",
        "hit and run": "Section 106 BNS Rash negligent act death escape police",
        "theft": "Section 303 BNS Theft dishonestly taking movable property",
        "extortion": "Section 308 BNS Extortion putting person fear injury",
        "robbery": "Section 309 BNS Robbery theft extortion death grievous hurt",
        "dacoity": "Section 310 BNS Dacoity gang robbery five or more persons",
        "stolen property": "Section 317 BNS Dishonestly receiving stolen property",
        "forgery": "Section 335 BNS Section 336 BNS Forgery false document electronic record",
        "criminal breach of trust": "Section 316 BNS Criminal breach of trust misappropriation",
        "misappropriation": "Section 314 BNS Dishonest misappropriation property",
        "defamation": "Section 356 BNS Defamation imputations reputation",
        "criminal intimidation": "Section 351 BNS Criminal intimidation threat injury",
        "rape": "Section 63 BNS Section 64 BNS Rape sexual assault",
        "gang rape": "Section 70 BNS Gang rape common intention",
        "outrage modesty": "Section 74 BNS Assault criminal force woman modesty",
        "sexual harassment": "Section 75 BNS Sexual harassment unwelcome physical contact",
        "stalking": "Section 78 BNS Stalking following woman disinterest",
        "voyeurism": "Section 77 BNS Voyeurism capturing publishing private act",
        "kidnapping": "Section 137 BNS Kidnapping lawful guardianship abduction",
        "abduction": "Section 138 BNS Abduction kidnapping murder grievous hurt",
        "human trafficking": "Section 143 BNS Trafficking of person exploitation",
        "sedition": "Section 152 BNS Act endangering sovereignty unity integrity",
        "public nuisance": "Section 270 BNS Public nuisance common injury danger annoyance",
        "trespass": "Section 329 BNS Section 331 BNS Criminal trespass house breaking",
        "house trespass": "Section 331 BNS Lurking house trespass house breaking",
        "mischief": "Section 324 BNS Section 326 BNS Mischief damage property explosive fire",
        "false evidence": "Section 227 BNS Giving fabricating false evidence judicial proceeding",
        "perjury": "Section 227 BNS False evidence under oath judicial",
        "disappearance of evidence": "Section 238 BNS Causing disappearance of evidence screen offender",
        "screen offender": "Section 238 BNS Giving false information screen offender",
        "harboring offender": "Section 249 BNS Harbouring offender arrest ordered",
        "disobedience": "Section 223 BNS Disobedience order public servant",
        "acid attack": "Section 124 BNS Voluntarily causing grievous hurt acid"
    }

    def __init__(self, concordance_lookup: Optional[ConcordanceLookup] = None):
        self.concordance = concordance_lookup or ConcordanceLookup()

    def extract_ipc_section(self, query: str) -> Optional[str]:
        """Extracts any explicit IPC section number from query."""
        patterns = [
            r'(?:IPC|Indian\s*Penal\s*Code)\s*(?:Section|Sec\.?|S\.?|§)?\s*([0-9]+[A-Z]?)',
            r'(?:Section|Sec\.?|S\.?|§)\s*([0-9]+[A-Z]?)\s*(?:of\s*(?:the\s*)?IPC|IPC)',
            r'\bSection\s*([0-9]+[A-Z]?)\b',
            r'§\s*([0-9]+[A-Z]?)'
        ]
        for pat in patterns:
            match = re.search(pat, query, re.IGNORECASE)
            if match:
                return match.group(1).upper().strip()
        return None

    def expand_query(self, query: str) -> str:
        """
        Enriches user query with concordance mappings and domain synonyms.
        """
        expansion_terms = []
        q_lower = query.lower()

        # 1. Check for explicit IPC section references
        extracted_ipc = self.extract_ipc_section(query)
        if extracted_ipc:
            mapping = self.concordance.map_ipc_to_bns(extracted_ipc)
            if mapping and mapping.target_section:
                bns_sec = mapping.target_section
                title = mapping.target_title or mapping.source_title
                expansion_terms.append(f"Section {bns_sec} BNS")
                if title:
                    expansion_terms.append(title)
            elif mapping and mapping.status.value == "repealed":
                expansion_terms.append("REPEALED Section 152 BNS sovereignty")

        # 2. Check for domain offence keywords
        for offence_term, expansion in self.OFFENCE_LEXICON.items():
            if re.search(r'\b' + re.escape(offence_term) + r'\b', q_lower):
                expansion_terms.append(expansion)

        if not expansion_terms:
            return query

        # Combine original query with unique expansion terms
        unique_terms = list(dict.fromkeys(expansion_terms))
        expanded_query = f"{query} {' '.join(unique_terms)}".strip()
        return expanded_query


_GLOBAL_EXPANDER: Optional[ConcordanceQueryExpander] = None


def get_query_expander() -> ConcordanceQueryExpander:
    global _GLOBAL_EXPANDER
    if _GLOBAL_EXPANDER is None:
        _GLOBAL_EXPANDER = ConcordanceQueryExpander()
    return _GLOBAL_EXPANDER
