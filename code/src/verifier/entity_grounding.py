"""
entity_grounding.py — Layer 2 Entity Grounding & Query Relevance Gating Verifier

Verifies:
1. Penal & entity grounding: extracts legal terms, punishment durations, and offences
   from generated text and verifies they are strictly present in retrieved context.
2. Strict Penal Term Constraint: Un-grounded punishment durations (e.g. fabricating 10 years
   when the statute states 6 months) immediately trigger UNGROUNDED_CLAIM rejection.
3. Query-Intent Relevance Gating (Layer 2.5): Verifies that cited statutory chunks actually
   address the user's specific legal query (catching 'right section, wrong question' errors).
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Set, Optional


@dataclass
class EntityGroundingResult:
    is_grounded: bool
    overlap_score: float
    intent_aligned: bool
    grounded_entities: List[str]
    ungrounded_entities: List[str]
    intent_mismatches: List[str]
    context_tokens_count: int
    generated_tokens_count: int


class EntityGroundingVerifier:
    """
    Layer 2 Grounding Verifier checking entity overlap, strict penal duration constraints,
    and query-intent relevance.
    """

    PENAL_PUNISHMENT_TERMS = {
        "death", "imprisonment for life", "life imprisonment", "rigorous imprisonment",
        "simple imprisonment", "community service", "ten years", "seven years", "five years",
        "three years", "two years", "twenty years", "six months", "five thousand rupees",
        "ten lakh rupees", "one thousand rupees"
    }

    LEGAL_TERMS = PENAL_PUNISHMENT_TERMS | {
        "rash", "negligent", "driving", "medical practitioner",
        "snatching", "organised crime", "terrorist act", "deceitful means",
        "promise to marry", "consent", "minor", "caste", "race", "mob lynching",
        "sovereignty", "unity", "integrity", "armed rebellion", "dishonestly",
        "fraudulently", "forgery", "defamation", "extortion", "robbery",
        "dacoity", "cheating", "culpable homicide", "murder", "deepfake",
        "synthetic media", "voice cloning", "pollution", "effluent", "kidnapping"
    }

    STOPWORDS = {
        "what", "which", "where", "under", "section", "in", "the", "new", "bns",
        "ipc", "code", "act", "is", "for", "and", "or", "of", "to", "how", "can",
        "a", "an", "does", "penalize", "covered", "defined", "amended", "2023", "2025"
    }

    def __init__(self, min_overlap_threshold: float = 0.50):
        self.min_overlap_threshold = min_overlap_threshold

    @classmethod
    def normalize_penal_text(cls, text: str) -> str:
        """Normalizes common statutory penal synonyms."""
        t = text.lower()
        t = re.sub(r'\blife imprisonment\b', 'imprisonment for life', t)
        t = re.sub(r'\bdeath penalty\b', 'death', t)
        t = re.sub(r'\bcapital punishment\b', 'death', t)
        return t

    @classmethod
    def extract_legal_entities(cls, text: str) -> Set[str]:
        """Extracts recognizable legal terms and punishment durations from text."""
        norm_text = cls.normalize_penal_text(text)
        found = set()
        for term in cls.LEGAL_TERMS:
            if re.search(r'\b' + re.escape(term) + r'\b', norm_text):
                found.add(term)
        return found


    def extract_query_intent_keywords(self, query: str) -> Set[str]:
        """Extracts substantive content keywords representing query intent."""
        words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        return {w for w in words if w not in self.STOPWORDS}

    def verify_grounding(self, generated_text: str, retrieved_chunks: List[Dict[str, Any]],
                         query: str = "") -> EntityGroundingResult:
        """
        Verifies that legal entities mentioned in generated text are grounded in retrieved context
        AND that cited sections align with the user's query intent.
        """
        if not retrieved_chunks:
            return EntityGroundingResult(
                is_grounded=False,
                overlap_score=0.0,
                intent_aligned=False,
                grounded_entities=[],
                ungrounded_entities=list(self.extract_legal_entities(generated_text)),
                intent_mismatches=["No retrieved statutory chunks available for grounding."],
                context_tokens_count=0,
                generated_tokens_count=len(generated_text.split())
            )

        # Aggregate context text
        raw_context = " ".join([
            f"{c.get('section_title', '')} {c.get('section_text', '')}"
            for c in retrieved_chunks
        ])
        context_text = self.normalize_penal_text(raw_context)

        gen_entities = self.extract_legal_entities(generated_text)
        grounded = [e for e in gen_entities if e in context_text]
        ungrounded = [e for e in gen_entities if e not in context_text]


        # Strict Penal Duration Gating: If ungrounded contains critical penal punishment terms, reject
        has_ungrounded_penal_punishment = any(e in self.PENAL_PUNISHMENT_TERMS for e in ungrounded)

        overlap_score = len(grounded) / max(1, len(gen_entities)) if gen_entities else 1.0
        is_grounded = (overlap_score >= self.min_overlap_threshold) and (not has_ungrounded_penal_punishment)

        # Query Intent Alignment & Relevance Check (Layer 2.5)
        intent_aligned = True
        intent_mismatches = []

        if query:
            query_keywords = self.extract_query_intent_keywords(query)
            if query_keywords:
                matched_in_gen = any(k in generated_text.lower() for k in query_keywords)
                # Check if substantive keywords match context text or section titles
                matched_in_chunks = any(k in context_text for k in query_keywords)
                if not matched_in_gen or not matched_in_chunks:
                    intent_aligned = False
                    intent_mismatches.append(
                        f"Non-responsive answer / irrelevant citation: Query intent keywords not covered in context."
                    )


        return EntityGroundingResult(
            is_grounded=is_grounded,
            overlap_score=round(overlap_score, 4),
            intent_aligned=intent_aligned,
            grounded_entities=grounded,
            ungrounded_entities=ungrounded,
            intent_mismatches=intent_mismatches,
            context_tokens_count=len(context_text.split()),
            generated_tokens_count=len(generated_text.split())
        )


# ── Global singleton ──────────────────────────────────────────────────────
_GLOBAL_GROUNDING_VERIFIER = None


def get_grounding_verifier(min_overlap_threshold: float = 0.50) -> EntityGroundingVerifier:
    global _GLOBAL_GROUNDING_VERIFIER
    if _GLOBAL_GROUNDING_VERIFIER is None:
        _GLOBAL_GROUNDING_VERIFIER = EntityGroundingVerifier(min_overlap_threshold=min_overlap_threshold)
    return _GLOBAL_GROUNDING_VERIFIER
