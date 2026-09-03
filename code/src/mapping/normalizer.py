"""
normalizer.py — Query Normalization Layer

Converts natural language, conversational, or dirty queries into canonical
statutory section numbers before feeding them to the deterministic lookup module.

Architecture:
1. Tier 1: Regex & Pattern Normalizer (Fast path, ~0ms latency)
   - Handles "section 302", "sec 420 ipc", "ipc 376", "§124A", "what is 304A in BNS", etc.
2. Tier 2: Canonical Offence Vocabulary Matcher (Rule-based domain ontology)
   - Matches keywords like "murder", "cheating", "sedition", "rape", "theft", "dowry death",
     "snatching", "organised crime", "terrorist act" to their canonical sections.
3. Tier 3: LLM Normalizer (Optional / Configurable)
   - Calls small instruction model (e.g. Gemini 2.0 Flash) when free-text query has no regex match.
   - Note: The LLM only extracts canonical section strings — it NEVER generates the mapping itself.
"""

import os
import re
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

log = logging.getLogger("query_normalizer")

# Canonical common Indian criminal law offence keywords -> IPC sections
COMMON_OFFENCE_MAP: Dict[str, str] = {
    "murder": "302",
    "culpable homicide": "299",
    "death by negligence": "304A",
    "rash driving": "279",
    "dowry death": "304B",
    "abetment of suicide": "306",
    "attempt to murder": "307",
    "rape": "375",
    "gang rape": "376D",
    "sexual harassment": "354A",
    "disrobe": "354B",
    "voyeurism": "354C",
    "stalking": "354D",
    "outrage modesty": "354",
    "unnatural offences": "377",
    "sodomy": "377",
    "adultery": "497",
    "cruelty by husband": "498A",
    "theft": "378",
    "extortion": "383",
    "robbery": "390",
    "dacoity": "391",
    "cheating": "420",
    "criminal breach of trust": "405",
    "dishonest misappropriation": "403",
    "forgery": "463",
    "counterfeiting currency": "489A",
    "defamation": "499",
    "criminal intimidation": "503",
    "sedition": "124A",
    "unlawful assembly": "141",
    "rioting": "146",
    "bribery": "171B",
    "kidnapping": "359",
    "abduction": "362",
    "trafficking": "370",
    "criminal conspiracy": "120A",
    "grievous hurt": "320",
    "hurt": "319",
    "public nuisance": "268",
    "giving false evidence": "191",
    "perjury": "191",
}


@dataclass
class NormalizedQuery:
    original_query: str
    extracted_section: Optional[str]
    detected_act: str                   # "IPC", "BNS", or "UNKNOWN"
    method: str                         # "regex", "offence_lexicon", "llm", "raw_fallback"
    confidence: float                   # 0.0 to 1.0
    offence_name: Optional[str] = None


class QueryNormalizer:
    """
    Multi-tier query normalizer for Indian statutory questions.
    """

    def __init__(self, use_llm: bool = False, gemini_api_key: Optional[str] = None):
        self.use_llm = use_llm
        self.api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")

    ACT_YEARS = {"1860", "2023", "2024", "1973", "1872"}

    @classmethod
    def extract_via_regex(cls, query: str) -> Optional[Tuple[str, str]]:
        """
        Extract section number and act from query text using regex patterns.
        Returns: (section_number, act_name) or None.
        """
        q = query.strip()

        # Clean act year noise (e.g. "BNS 2023", "IPC 1860", "BNS, 2023")
        q_cleaned = re.sub(r'\b(BNS|IPC|BNSS|BSA)[,\s]+(1860|2023|2024|1973|1872)\b', r'\1', q, flags=re.IGNORECASE)

        # Patterns for Section X of Act Y
        patterns = [
            # "IPC 302", "IPC section 302", "IPC §302"
            (r'\bIPC\s*(?:SECTION|SEC\.?|S\.?|§)?\s*(\d+[A-Z]?(?:\(\d+\))?)\b', "IPC"),
            # "BNS 103", "BNS section 103", "BNS §103"
            (r'\bBNS\s*(?:SECTION|SEC\.?|S\.?|§)?\s*(\d+[A-Z]?(?:\(\d+\))?)\b', "BNS"),
            # "Section 302 of IPC", "section 302 ipc"
            (r'(?:(?:\b(?:SECTION|SEC\.?|S\.?))|§)\s*(\d+[A-Z]?(?:\(\d+\))?)\s*(?:OF\s*)?(?:THE\s*)?IPC\b', "IPC"),
            # "Section 103 of BNS", "section 103 bns"
            (r'(?:(?:\b(?:SECTION|SEC\.?|S\.?))|§)\s*(\d+[A-Z]?(?:\(\d+\))?)\s*(?:OF\s*)?(?:THE\s*)?BNS\b', "BNS"),
            # "Section 302", "sec. 302", "§302", "§ 124A"
            (r'(?:(?:\b(?:SECTION|SEC\.?|S\.?))|§)\s*(\d+[A-Z]?(?:\(\d+\))?)\b', "IPC"),
            # Just a bare section number in short query like "302" or "420"
            (r'^\s*(\d+[A-Z]?(?:\(\d+\))?)\s*$', "IPC"),
        ]

        for pat, act in patterns:
            match = re.search(pat, q_cleaned, re.IGNORECASE)
            if match:
                sec = match.group(1).upper().strip()
                if sec not in cls.ACT_YEARS:
                    return sec, act

        return None

    @staticmethod
    def extract_via_offence_lexicon(query: str) -> Optional[Tuple[str, str, str]]:
        """
        Match query text against common offence names.
        Returns: (section_number, act, offence_name) or None.
        """
        q_lower = query.lower()
        # Sort by length descending to match multi-word phrases first (e.g. "dowry death" before "death")
        for offence, sec in sorted(COMMON_OFFENCE_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r'\b' + re.escape(offence) + r'\b', q_lower):
                return sec, "IPC", offence
        return None

    def extract_via_llm(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Extract canonical section number from query via lightweight LLM call.
        """
        if not self.use_llm or not self.api_key:
            return None

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = (
                "You are an Indian statutory legal assistant. Your ONLY job is to extract the relevant "
                "Indian Penal Code (IPC) or Bharatiya Nyaya Sanhita (BNS) section number from the user query.\n"
                "Return a JSON object with keys 'section' (string) and 'act' ('IPC' or 'BNS'). "
                "If no section is mentioned or inferred, return {'section': null, 'act': null}.\n\n"
                f"Query: {query}\n"
                "JSON:"
            )

            resp = model.generate_content(prompt)
            text = resp.text.strip()
            # Clean markdown fences
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            data = json.loads(text)
            sec = data.get("section")
            act = data.get("act", "IPC")
            if sec:
                return str(sec).strip().upper(), str(act).upper()
        except Exception as e:
            log.warning(f"LLM normalization fallback failed: {e}")

        return None

    def normalize(self, query: str) -> NormalizedQuery:
        """
        Normalizes a free-text user query into a canonical section and act.
        """
        clean_q = query.strip()

        # Tier 1: Regex
        regex_match = self.extract_via_regex(clean_q)
        if regex_match:
            sec, act = regex_match
            return NormalizedQuery(
                original_query=clean_q,
                extracted_section=sec,
                detected_act=act,
                method="regex",
                confidence=1.0
            )

        # Tier 2: Offence Lexicon
        lex_match = self.extract_via_offence_lexicon(clean_q)
        if lex_match:
            sec, act, offence = lex_match
            return NormalizedQuery(
                original_query=clean_q,
                extracted_section=sec,
                detected_act=act,
                method="offence_lexicon",
                confidence=0.9,
                offence_name=offence
            )

        # Tier 3: LLM Extraction
        llm_match = self.extract_via_llm(clean_q)
        if llm_match:
            sec, act = llm_match
            return NormalizedQuery(
                original_query=clean_q,
                extracted_section=sec,
                detected_act=act,
                method="llm",
                confidence=0.8
            )

        # Fallback
        return NormalizedQuery(
            original_query=clean_q,
            extracted_section=None,
            detected_act="UNKNOWN",
            method="raw_fallback",
            confidence=0.0
        )


# ── Global singleton accessors ───────────────────────────────────────────
_GLOBAL_NORMALIZER: Optional[QueryNormalizer] = None


def get_query_normalizer(use_llm: bool = False) -> QueryNormalizer:
    global _GLOBAL_NORMALIZER
    if _GLOBAL_NORMALIZER is None:
        _GLOBAL_NORMALIZER = QueryNormalizer(use_llm=use_llm)
    return _GLOBAL_NORMALIZER


def normalize_query(query: str, use_llm: bool = False) -> NormalizedQuery:
    return get_query_normalizer(use_llm=use_llm).normalize(query)
