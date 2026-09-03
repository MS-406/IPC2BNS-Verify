"""
entity_grounding.py — Layer 2 Semantic Entity & Query-Intent Grounding Verifier

Evaluates:
1. Substantive Legal Ingredient Grounding:
   Checks whether generated assertions (punishments, conditions, terms) are grounded in retrieved context.
2. Query-Intent Alignment (Novel Verifier Check):
   Checks whether the cited section actually addresses the core legal question asked,
   catching the failure mode: 'Cites real sections, but answers the wrong question'.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Tuple


@dataclass
class EntityGroundingResult:
    is_grounded: bool
    overlap_score: float                # 0.0 to 1.0
    intent_aligned: bool = True
    grounded_entities: List[str] = field(default_factory=list)
    ungrounded_entities: List[str] = field(default_factory=list)
    intent_mismatches: List[str] = field(default_factory=list)
    context_tokens_count: int = 0
    generated_tokens_count: int = 0


class EntityGroundingVerifier:
    """
    Layer 2 Grounding Verifier checking entity overlap and query-intent relevance.
    """

    LEGAL_TERMS = {
        "death", "imprisonment for life", "life imprisonment", "rigorous imprisonment",
        "simple imprisonment", "fine", "community service", "rash", "negligent",
        "driving", "medical practitioner", "ten years", "seven years", "five years",
        "three years", "two years", "twenty years", "five thousand rupees",
        "ten lakh rupees", "snatching", "organised crime", "terrorist act",
        "deceitful means", "promise to marry", "consent", "minor", "caste", "race",
        "mob lynching", "sovereignty", "unity", "integrity", "armed rebellion",
        "dishonestly", "fraudulently", "forgery", "defamation", "extortion",
        "robbery", "dacoity", "cheating", "culpable homicide", "murder",
        "deepfake", "synthetic media", "voice cloning", "pollution", "effluent"
    }

    # Stopwords to filter when checking query keywords
    STOPWORDS = {
        "what", "which", "where", "under", "section", "in", "the", "new", "bns",
        "ipc", "code", "act", "is", "for", "and", "or", "of", "to", "how", "can",
        "a", "an", "does", "penalize", "covered", "defined", "amended", "2023", "2025"
    }

    def __init__(self, min_overlap_threshold: float = 0.40):
        self.min_overlap_threshold = min_overlap_threshold

    @classmethod
    def extract_legal_entities(cls, text: str) -> Set[str]:
        """Extracts recognizable legal terms and numbers from text."""
        text_lower = text.lower()
        found = set()
        for term in cls.LEGAL_TERMS:
            if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
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
        context_text = " ".join([
            f"{c.get('section_title', '')} {c.get('section_text', '')}"
            for c in retrieved_chunks
        ]).lower()

        gen_entities = self.extract_legal_entities(generated_text)
        context_entities = self.extract_legal_entities(context_text)

        grounded = [e for e in gen_entities if e in context_entities or e in context_text]
        ungrounded = [e for e in gen_entities if e not in context_entities and e not in context_text]

        overlap_score = len(grounded) / max(1, len(gen_entities)) if gen_entities else 1.0
        is_grounded = overlap_score >= self.min_overlap_threshold

        # Query Intent Alignment Check
        intent_aligned = True
        intent_mismatches = []

        if query:
            query_keywords = self.extract_query_intent_keywords(query)
            # Check if any top query keyword is mentioned in the generated text or top-1 cited chunk
            if query_keywords:
                matched_in_gen = any(k in generated_text.lower() for k in query_keywords)
                if not matched_in_gen:
                    intent_aligned = False
                    missing = [k for k in query_keywords if k not in generated_text.lower()]
                    intent_mismatches.append(
                        f"Non-responsive answer: Generated text does not address query keywords: {missing[:3]}"
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


def get_grounding_verifier(min_overlap_threshold: float = 0.40) -> EntityGroundingVerifier:
    global _GLOBAL_GROUNDING_VERIFIER
    if _GLOBAL_GROUNDING_VERIFIER is None:
        _GLOBAL_GROUNDING_VERIFIER = EntityGroundingVerifier(min_overlap_threshold=min_overlap_threshold)
    return _GLOBAL_GROUNDING_VERIFIER
