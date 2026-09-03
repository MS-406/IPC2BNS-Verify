"""
verifier_pipeline.py — Master Two-Layer Hard-Constraint Verifier with Graded Confidence & Ambiguity Scoring

Orchestrates:
1. Layer 1: Citation existence check against closed statute index + repeal vetoes
2. Layer 2: Entity & penal ingredient grounding check against retrieved chunks
3. Layer 2.5: Query-Intent Alignment (flags 'cites real sections, answers wrong question')
4. Continuous Confidence & Ambiguity Scoring (Graded output for 1:1, Split, Merged, and Repealed provisions)
5. Output Veto & Remediation
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
    verdict: str                        # "VERIFIED" | "REJECTED_HALLUCINATED_CITATION" | "VETOED_REPEALED_PROVISION" | "UNGROUNDED_CLAIM" | "NON_RESPONSIVE_ANSWER" | "AMBIGUOUS_SPLIT_CAUTION"
    layer1_result: CitationCheckResult
    layer2_result: EntityGroundingResult
    original_text: str
    verified_output_text: str
    confidence_score: float = 1.0       # 0.0 to 1.0 (Continuous reliability score)
    confidence_grade: str = "HIGH_CONFIDENCE_VERIFIED"  # "HIGH" | "MODERATE" | "AMBIGUOUS_SPLIT" | "VETOED" | "LOW"
    ambiguity_score: float = 0.0        # 0.0 = unambiguous 1:1; 1.0 = multi-branch split / repeal
    ambiguity_details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_verified": self.is_verified,
            "verdict": self.verdict,
            "confidence_score": round(self.confidence_score, 3),
            "confidence_grade": self.confidence_grade,
            "ambiguity_score": round(self.ambiguity_score, 3),
            "ambiguity_details": self.ambiguity_details,
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
    Master Verifier enforcing strict two-layer validation and continuous confidence / ambiguity grading.
    """

    def __init__(self, min_grounding_threshold: float = 0.35):
        self.citation_verifier = get_citation_verifier()
        self.grounding_verifier = get_grounding_verifier(min_overlap_threshold=min_grounding_threshold)

    def compute_confidence_and_ambiguity(
        self,
        l1_res: CitationCheckResult,
        l2_res: EntityGroundingResult,
        citations: List[Dict[str, str]],
        query: str = ""
    ) -> tuple:
        """
        Computes a continuous confidence score (0.0 to 1.0), confidence grade,
        and ambiguity score based on concordance certainty, grounding overlap, and query intent.
        """
        # Base mapping certainty
        mapping_certainty = 1.0
        ambiguity_score = 0.0
        ambiguity_details = {"status": "unambiguous_direct", "split_branches": []}

        for cit in citations:
            sec = cit.get("section", "")
            act = cit.get("act", "IPC").upper()
            if act == "IPC":
                map_res = map_ipc_to_bns(sec)
                if map_res.status == MappingStatus.REPEALED:
                    mapping_certainty = 0.0
                    ambiguity_score = 1.0
                    ambiguity_details = {"status": "repealed_provision", "notes": map_res.notes}
                elif map_res.status == MappingStatus.AMBIGUOUS_SPLIT:
                    mapping_certainty = 0.65
                    ambiguity_score = 0.80
                    ambiguity_details = {
                        "status": "ambiguous_split",
                        "split_branches": map_res.all_matched_sections,
                        "notes": map_res.notes
                    }
                elif map_res.status == MappingStatus.AMBIGUOUS_MERGED:
                    mapping_certainty = 0.75
                    ambiguity_score = 0.50
                    ambiguity_details = {"status": "ambiguous_merged", "notes": map_res.notes}
                elif map_res.status == MappingStatus.NOT_FOUND:
                    mapping_certainty = 0.40
                    ambiguity_score = 0.60

        # Grounding & Intent weight
        grounding_factor = 1.0 if l2_res.is_grounded else 0.40
        intent_factor = 1.0 if l2_res.intent_aligned else 0.30

        # Weighted calculation
        raw_conf = (mapping_certainty * 0.40) + (grounding_factor * 0.35) + (intent_factor * 0.25)
        raw_conf = max(0.0, min(1.0, raw_conf))

        if not l1_res.is_valid:
            if len(l1_res.repealed_citations) > 0:
                grade = "VETOED_REPEALED"
                raw_conf = 0.0
            else:
                grade = "LOW_CONFIDENCE_REJECTED"
                raw_conf = min(raw_conf, 0.20)
        elif ambiguity_score >= 0.70:
            grade = "AMBIGUOUS_SPLIT_FLAGGED"
            raw_conf = min(raw_conf, 0.65)
        elif raw_conf >= 0.80:
            grade = "HIGH_CONFIDENCE_VERIFIED"
        elif raw_conf >= 0.50:
            grade = "MODERATE_CONFIDENCE_WARNING"
        else:
            grade = "LOW_CONFIDENCE_REJECTED"

        return round(raw_conf, 3), grade, round(ambiguity_score, 3), ambiguity_details

    def verify_generation(self, generated_text: str, citations: List[Dict[str, str]],
                          retrieved_chunks: List[Dict[str, Any]], query: str = "") -> MasterVerificationResult:
        """
        Runs full two-layer verification pipeline on a model's generated answer with continuous confidence grading.
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

        # Step 3: Compute continuous confidence and ambiguity
        conf_score, conf_grade, amb_score, amb_details = self.compute_confidence_and_ambiguity(
            l1_res=l1_res,
            l2_res=l2_res,
            citations=citations,
            query=query
        )

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
            verified_text = f"[VERIFIER REJECTION]: Answer contains no formal statutory citations in [Act §Section] format."
            warnings.append("No statutory citations detected.")

        # Case D: Non-responsive citation / intent mismatch (Layer 2.5)
        elif not l2_res.intent_aligned:
            verdict = "NON_RESPONSIVE_ANSWER"
            is_verified = False
            verified_text = (
                f"[VERIFIER REJECTION - NON-RESPONSIVE]: The cited provisions do not substantively answer "
                f"the legal query intent. {l2_res.intent_mismatches[0] if l2_res.intent_mismatches else ''}"
            )
            warnings.extend(l2_res.intent_mismatches)

        # Case E: Ambiguous split section flagged
        elif amb_score >= 0.70:
            verdict = "AMBIGUOUS_SPLIT_CAUTION"
            is_verified = True
            warnings.append(
                f"Ambiguous Split Section: IPC provision split into multiple BNS sections: {amb_details.get('split_branches', [])}."
            )

        # Case F: Substantive ungrounded penal ingredient claims (Layer 2)
        elif not l2_res.is_grounded:
            verdict = "UNGROUNDED_CLAIM"
            is_verified = False
            verified_text = (
                f"[VERIFIER REJECTION]: Generation contains ungrounded legal assertions not supported "
                f"by authoritative statutory text. Ungrounded terms: {l2_res.ungrounded_entities}"
            )
            warnings.append(
                f"Low statutory grounding overlap score: {l2_res.overlap_score}. Ungrounded terms: {l2_res.ungrounded_entities}"
            )

        # Case G: Passed all verification layers
        else:
            verdict = "VERIFIED"
            is_verified = True

        # Append warnings for pre-transition references
        if len(l1_res.rejection_reasons) > 0 and verdict == "VERIFIED":
            warnings.extend(l1_res.rejection_reasons)


        return MasterVerificationResult(
            is_verified=is_verified,
            verdict=verdict,
            layer1_result=l1_res,
            layer2_result=l2_res,
            original_text=generated_text,
            verified_output_text=verified_text,
            confidence_score=conf_score,
            confidence_grade=conf_grade,
            ambiguity_score=amb_score,
            ambiguity_details=amb_details,
            warnings=warnings
        )


# ── Global singleton accessor ─────────────────────────────────────────────
_GLOBAL_MASTER_VERIFIER: Optional[HardConstraintVerifier] = None


def get_master_verifier() -> HardConstraintVerifier:
    global _GLOBAL_MASTER_VERIFIER
    if _GLOBAL_MASTER_VERIFIER is None:
        _GLOBAL_MASTER_VERIFIER = HardConstraintVerifier()
    return _GLOBAL_MASTER_VERIFIER
