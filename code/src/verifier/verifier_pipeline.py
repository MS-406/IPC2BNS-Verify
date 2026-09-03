"""
verifier_pipeline.py — Master Two-Layer Hard-Constraint Verifier Pipeline

Orchestrates:
1. Layer 1: Citation existence check against closed statute index + repeal vetoes
2. Layer 2: Entity & penal ingredient grounding check against retrieved chunks
3. Layer 2.5: Query-Intent Alignment (flags 'cites real sections, answers wrong question')
4. Output Veto & Remediation
"""

import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.verifier.citation_check import get_citation_verifier, CitationCheckResult
from src.verifier.entity_grounding import get_grounding_verifier, EntityGroundingResult
from src.mapping.lookup import map_ipc_to_bns, MappingStatus


@dataclass
class MasterVerificationResult:
    is_verified: bool
    verdict: str                        # "VERIFIED" | "REJECTED_HALLUCINATED_CITATION" | "VETOED_REPEALED_PROVISION" | "UNGROUNDED_CLAIM" | "NON_RESPONSIVE_ANSWER"
    layer1_result: CitationCheckResult
    layer2_result: EntityGroundingResult
    original_text: str
    verified_output_text: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_verified": self.is_verified,
            "verdict": self.verdict,
            "layer1_valid": self.layer1_result.is_valid,
            "layer2_grounded": self.layer2_result.is_grounded,
            "layer2_intent_aligned": self.layer2_result.intent_aligned,
            "layer2_overlap_score": self.layer2_result.overlap_score,
            "original_text": self.original_text,
            "verified_output_text": self.verified_output_text,
            "warnings": self.warnings
        }


class HardConstraintVerifier:
    """
    Master Verifier enforcing strict two-layer validation.
    """

    def __init__(self, min_grounding_threshold: float = 0.35):
        self.citation_verifier = get_citation_verifier()
        self.grounding_verifier = get_grounding_verifier(min_overlap_threshold=min_grounding_threshold)

    def verify_generation(self, generated_text: str, citations: List[Dict[str, str]],
                          retrieved_chunks: List[Dict[str, Any]], query: str = "") -> MasterVerificationResult:
        """
        Runs full two-layer verification pipeline on a model's generated answer.
        """
        # Step 1: Layer 1 Citation Check
        l1_res = self.citation_verifier.verify_citations(citations)

        # Augment retrieved chunks with canonical chunks for cited valid sections
        all_chunks = list(retrieved_chunks)
        from src.retrieval.search import get_retriever
        retriever = get_retriever()
        if retriever and retriever.index and retriever.index.chunks:
            for cit in l1_res.valid_citations:
                act_tag = cit.get("act", "BNS").upper()
                sec_tag = cit.get("section", "").strip()
                for chunk in retriever.index.chunks:
                    if chunk.act.upper() == act_tag and chunk.section_number.strip() == sec_tag:
                        if not any(c.get("chunk_id") == chunk.chunk_id for c in all_chunks):
                            all_chunks.append(chunk.to_dict())


        # Step 2: Layer 2 Entity Grounding & Intent Alignment Check
        l2_res = self.grounding_verifier.verify_grounding(generated_text, all_chunks, query=query)



        warnings = []
        verified_text = generated_text
        is_verified = False
        verdict = "VERIFIED"

        # Case A: Repealed provision cited as active
        if len(l1_res.repealed_citations) > 0:
            repealed_sec = l1_res.repealed_citations[0]["section"]
            mapping = map_ipc_to_bns(repealed_sec)
            verdict = "VETOED_REPEALED_PROVISION"
            is_verified = False
            verified_text = (
                f"[VERIFIER VETO]: The cited provision IPC Section {repealed_sec} has been REPEALED / struck down "
                f"and has NO direct equivalent in BNS 2023. {mapping.notes}"
            )
            warnings.extend(l1_res.rejection_reasons)

        # Case B: Hallucinated / invalid section ID cited
        elif len(l1_res.invalid_citations) > 0:
            verdict = "REJECTED_HALLUCINATED_CITATION"
            is_verified = False
            invalid_secs = [c["section"] for c in l1_res.invalid_citations]
            verified_text = (
                f"[VERIFIER REJECTION]: Generation rejected due to hallucinated statutory section(s): {invalid_secs}. "
                f"These sections do not exist in the official statute."
            )
            warnings.extend(l1_res.rejection_reasons)

        # Case C: No citations present when required
        elif l1_res.total_citations == 0:
            verdict = "REJECTED_MISSING_CITATIONS"
            is_verified = False
            verified_text = "[VERIFIER REJECTION]: Answer rejected because no statutory citations [Act Section] were provided."
            warnings.append("No statutory citations detected.")

        # Case D: Non-responsive answer (answers wrong question)
        elif not l2_res.intent_aligned:
            verdict = "NON_RESPONSIVE_ANSWER"
            is_verified = False
            verified_text = f"[VERIFIER WARNING: NON-RESPONSIVE ANSWER]\n{generated_text}"
            warnings.extend(l2_res.intent_mismatches)

        # Case E: Layer 2 Grounding Failure (Ungrounded penal claims)
        elif not l2_res.is_grounded:
            verdict = "UNGROUNDED_CLAIM"
            is_verified = False
            verified_text = f"[VERIFIER WARNING: UNGROUNDED CLAIM]\n{generated_text}"
            warnings.append(f"Low statutory grounding overlap score: {l2_res.overlap_score}. Ungrounded terms: {l2_res.ungrounded_entities}")

        # Case F: Fully Verified
        else:
            verdict = "VERIFIED"
            is_verified = True
            verified_text = generated_text

        return MasterVerificationResult(
            is_verified=is_verified,
            verdict=verdict,
            layer1_result=l1_res,
            layer2_result=l2_res,
            original_text=generated_text,
            verified_output_text=verified_text,
            warnings=warnings
        )


# ── Global singleton ──────────────────────────────────────────────────────
_GLOBAL_MASTER_VERIFIER = None


def get_master_verifier() -> HardConstraintVerifier:
    global _GLOBAL_MASTER_VERIFIER
    if _GLOBAL_MASTER_VERIFIER is None:
        _GLOBAL_MASTER_VERIFIER = HardConstraintVerifier()
    return _GLOBAL_MASTER_VERIFIER


def verify_answer(generated_text: str, citations: List[Dict[str, str]],
                  retrieved_chunks: List[Dict[str, Any]], query: str = "") -> MasterVerificationResult:
    return get_master_verifier().verify_generation(generated_text, citations, retrieved_chunks, query)
