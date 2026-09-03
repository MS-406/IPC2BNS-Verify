"""
entity_grounding.py — Layer 2 Semantic Entity & Ingredient Grounding Verifier

Evaluates whether substantive legal assertions in the model's generated text
(punishments, offence ingredients, conditions) are grounded in the retrieved statutory text.

Calculates:
1. Legal Entity & Term Overlap Score (0.0 to 1.0)
2. Ungrounded Legal Claims detection (e.g. hallucinating death penalty where statute says 3 years)
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set


@dataclass
class EntityGroundingResult:
    is_grounded: bool
    overlap_score: float                # 0.0 to 1.0
    grounded_entities: List[str] = field(default_factory=list)
    ungrounded_entities: List[str] = field(default_factory=list)
    context_tokens_count: int = 0
    generated_tokens_count: int = 0


class EntityGroundingVerifier:
    """
    Layer 2 Grounding Verifier checking entity overlap against retrieved statute chunks.
    """

    # Key substantive legal ingredient terms
    LEGAL_TERMS = {
        "death", "imprisonment for life", "life imprisonment", "rigorous imprisonment",
        "simple imprisonment", "fine", "community service", "rash", "negligent",
        "driving", "medical practitioner", "ten years", "seven years", "five years",
        "three years", "two years", "twenty years", "five thousand rupees",
        "ten lakh rupees", "snatching", "organised crime", "terrorist act",
        "deceitful means", "promise to marry", "consent", "minor", "caste", "race",
        "mob lynching", "sovereignty", "unity", "integrity", "armed rebellion",
        "dishonestly", "fraudulently", "forgery", "defamation", "extortion",
        "robbery", "dacoity", "cheating", "culpable homicide", "murder"
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

    def verify_grounding(self, generated_text: str, retrieved_chunks: List[Dict[str, Any]]) -> EntityGroundingResult:
        """
        Verifies that legal entities mentioned in generated text are grounded in retrieved context.
        """
        if not retrieved_chunks:
            # No context provided -> cannot be grounded
            return EntityGroundingResult(
                is_grounded=False,
                overlap_score=0.0,
                grounded_entities=[],
                ungrounded_entities=list(self.extract_legal_entities(generated_text)),
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

        if not gen_entities:
            # Generic response without specific legal entities -> pass
            return EntityGroundingResult(
                is_grounded=True,
                overlap_score=1.0,
                grounded_entities=[],
                ungrounded_entities=[],
                context_tokens_count=len(context_text.split()),
                generated_tokens_count=len(generated_text.split())
            )

        grounded = [e for e in gen_entities if e in context_entities or e in context_text]
        ungrounded = [e for e in gen_entities if e not in context_entities and e not in context_text]

        overlap_score = len(grounded) / max(1, len(gen_entities))
        is_grounded = overlap_score >= self.min_overlap_threshold

        return EntityGroundingResult(
            is_grounded=is_grounded,
            overlap_score=round(overlap_score, 4),
            grounded_entities=grounded,
            ungrounded_entities=ungrounded,
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
