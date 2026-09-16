"""
stage_leakage_verifier.py — Multi-Stage Leakage & Mutation Verifier (v2)

Implements stage-level verification across:
- Stage 1: Temporal Consistency & Timeline Paradox Verifier
- Stage 2: Temporal-Statutory Regime Retrieval Verifier (Prevents cross-regime leakage)
- Stage 3: Statutory Concordance & Repeal Veto Verifier
- Stage 4: Cross-Stage Confidence Propagation & Mutation Leakage Detector
"""

import os
import sys
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Any, Optional, Tuple


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.temporal.timeline_parser import TimelineParser, ExtractedTimeline
from src.temporal.savings_clause_engine import SavingsClauseEngine, TemporalResolution
from src.verifier.citation_check import get_citation_verifier
from src.verifier.entity_grounding import get_grounding_verifier


@dataclass
class StageVerificationReport:
    stage_name: str
    is_passed: bool
    confidence: float
    error_type: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class MultiStageVerificationResult:
    is_verified: bool
    overall_confidence: float
    failed_stage: Optional[str]
    stage_reports: Dict[str, StageVerificationReport]
    remediation_suggestion: Optional[str] = None
    sanitized_output: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_verified": self.is_verified,
            "overall_confidence": round(self.overall_confidence, 3),
            "failed_stage": self.failed_stage,
            "remediation_suggestion": self.remediation_suggestion,
            "stages": {k: {
                "passed": v.is_passed,
                "confidence": round(v.confidence, 3),
                "error_type": v.error_type,
                "details": v.details,
                "warnings": v.warnings
            } for k, v in self.stage_reports.items()}
        }


class StageLeakageVerifier:
    """
    Multi-stage verifier that halts cascading hallucinations and leakage
    at every discrete transition point in the RAG pipeline.
    """
    CUTOFF_DATE = date(2024, 7, 1)

    def __init__(self):
        self.temporal_engine = SavingsClauseEngine()
        self.citation_verifier = get_citation_verifier()
        self.grounding_verifier = get_grounding_verifier()

    # -------------------------------------------------------------------------
    # STAGE 1: Temporal Consistency & Timeline Paradox Verifier
    # -------------------------------------------------------------------------
    def verify_stage1_temporal(self, timeline: ExtractedTimeline) -> StageVerificationReport:
        """
        Validates timeline consistency and detects temporal paradoxes.
        """
        inc = timeline.incident_date
        fir = timeline.fir_date
        pet = timeline.petition_date
        app = timeline.appeal_date

        warnings = []

        # Check 1: FIR date before incident date
        if inc and fir and fir < inc:
            return StageVerificationReport(
                stage_name="Stage1_Temporal",
                is_passed=False,
                confidence=0.0,
                error_type="TEMPORAL_PARADOX_FIR_BEFORE_INCIDENT",
                details={"incident_date": str(inc), "fir_date": str(fir)},
                warnings=["FIR date cannot precede incident date."]
            )

        # Check 2: Appeal date before incident date
        if inc and app and app < inc:
            return StageVerificationReport(
                stage_name="Stage1_Temporal",
                is_passed=False,
                confidence=0.0,
                error_type="TEMPORAL_PARADOX_APPEAL_BEFORE_INCIDENT",
                details={"incident_date": str(inc), "appeal_date": str(app)},
                warnings=["Appeal date cannot precede incident date."]
            )

        # Check 3: Future date beyond plausible horizon (e.g. year > 2030)
        for d_item in timeline.extracted_dates:
            if d_item["date"].year > 2030:
                warnings.append(f"Distant future date detected: {d_item['date']}")

        return StageVerificationReport(
            stage_name="Stage1_Temporal",
            is_passed=True,
            confidence=1.0 if not warnings else 0.85,
            error_type=None,
            details={"posture": timeline.posture, "jurisdiction": timeline.jurisdiction_hint},
            warnings=warnings
        )

    # -------------------------------------------------------------------------
    # STAGE 2: Retrieval Scope & Regime Leakage Verifier
    # -------------------------------------------------------------------------
    def verify_stage2_retrieval(
        self,
        temporal_res: TemporalResolution,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> StageVerificationReport:
        """
        Ensures retrieved statutory chunks align with the required legal regime
        (prevents BNS-only chunks on legacy queries or IPC-only chunks on modern queries).
        """
        if not retrieved_chunks:
            return StageVerificationReport(
                stage_name="Stage2_Retrieval",
                is_passed=False,
                confidence=0.0,
                error_type="EMPTY_RETRIEVAL",
                details={},
                warnings=["No statutory chunks retrieved."]
            )

        expected_substantive = temporal_res.substantive_code
        expected_procedural = temporal_res.procedural_code

        chunk_codes = []
        for ch in retrieved_chunks:
            text = (ch.get("text", "") + " " + ch.get("statute", "") + " " + ch.get("section", "")).upper()
            if "BNS" in text or "BHARATIYA NYAYA" in text:
                chunk_codes.append("BNS")
            if "IPC" in text or "INDIAN PENAL CODE" in text:
                chunk_codes.append("IPC")
            if "CRPC" in text or "CODE OF CRIMINAL PROCEDURE" in text:
                chunk_codes.append("CRPC")
            if "BNSS" in text or "BHARATIYA NAGARIK" in text:
                chunk_codes.append("BNSS")

        has_bns = "BNS" in chunk_codes
        has_ipc = "IPC" in chunk_codes
        has_crpc = "CRPC" in chunk_codes
        has_bnss = "BNSS" in chunk_codes

        # Check for Regime Leakage: Pure Legacy query where only BNS was retrieved without IPC
        if expected_substantive == "IPC_1860" and has_bns and not has_ipc:
            return StageVerificationReport(
                stage_name="Stage2_Retrieval",
                is_passed=False,
                confidence=0.2,
                error_type="REGIME_LEAKAGE_MODERN_INTO_LEGACY",
                details={"expected": "IPC_1860", "retrieved_statutes": list(set(chunk_codes))},
                warnings=["Legacy case query retrieved solely BNS 2023 chunks without IPC 1860 provisions."]
            )

        # Check for Regime Leakage: Pure Modern query where only IPC was retrieved without BNS
        if expected_substantive == "BNS_2023" and has_ipc and not has_bns:
            return StageVerificationReport(
                stage_name="Stage2_Retrieval",
                is_passed=False,
                confidence=0.2,
                error_type="REGIME_LEAKAGE_LEGACY_INTO_MODERN",
                details={"expected": "BNS_2023", "retrieved_statutes": list(set(chunk_codes))},
                warnings=["Modern post-July query retrieved solely repealed IPC 1860 chunks without BNS 2023."]
            )

        return StageVerificationReport(
            stage_name="Stage2_Retrieval",
            is_passed=True,
            confidence=0.95,
            error_type=None,
            details={"retrieved_statutes": list(set(chunk_codes)), "num_chunks": len(retrieved_chunks)},
            warnings=[]
        )

    # -------------------------------------------------------------------------
    # STAGE 3: Statutory Concordance & Repeal Veto Verifier
    # -------------------------------------------------------------------------
    CITATION_PATTERN = re.compile(
        r'\[?(IPC|BNS|CRPC|BNSS|BHARATIYA NYAYA SANHITA|INDIAN PENAL CODE)\s*(?:§|Section|Sec\.?|S\.)?\s*([0-9]+[A-Z]?(?:\([0-9]+\))?)\]?',
        re.IGNORECASE
    )

    def extract_citations_from_text(self, text: str) -> List[Dict[str, str]]:
        citations = []
        for match in self.CITATION_PATTERN.finditer(text):
            act = match.group(1).upper()
            if "BHARATIYA" in act:
                act = "BNS"
            elif "INDIAN" in act:
                act = "IPC"
            sec = match.group(2).strip()
            citations.append({"act": act, "section": sec})
        return citations

    def verify_stage3_concordance(
        self,
        candidate_text: str,
        temporal_res: TemporalResolution
    ) -> StageVerificationReport:
        """
        Validates citation existence, repeal vetoes, and savings clause legality.
        """
        citations = self.extract_citations_from_text(candidate_text)
        if not citations:
            return StageVerificationReport(
                stage_name="Stage3_Concordance",
                is_passed=True,
                confidence=0.8,
                error_type=None,
                details={"valid_citations": []},
                warnings=["No explicit statute citations found in response."]
            )

        cit_res = self.citation_verifier.verify_citations(citations)
        # Check if hallucinated non-existent section numbers were cited
        if not cit_res.is_valid:
            error_type = "INVALID_CITATION_HALLUCINATION"
            if cit_res.repealed_citations:
                error_type = "ILLEGAL_REPEALED_CITATION"
            elif not cit_res.is_cross_statute_consistent:
                error_type = "CROSS_STATUTE_INCONSISTENCY"

            return StageVerificationReport(
                stage_name="Stage3_Concordance",
                is_passed=False,
                confidence=0.0,
                error_type=error_type,
                details={
                    "invalid_citations": cit_res.invalid_citations,
                    "repealed_citations": cit_res.repealed_citations,
                    "cross_statute_inconsistencies": cit_res.cross_statute_inconsistencies
                },
                warnings=cit_res.rejection_reasons
            )

        # Check if repealed sections were cited inappropriately
        if cit_res.repealed_citations:
            # If query is NOT a legacy case governed by IPC, citing repealed provisions without saving is illegal
            if temporal_res.substantive_code != "IPC_1860":
                return StageVerificationReport(
                    stage_name="Stage3_Concordance",
                    is_passed=False,
                    confidence=0.0,
                    error_type="ILLEGAL_REPEALED_CITATION",
                    details={"repealed_citations": cit_res.repealed_citations},
                    warnings=["Repealed provision cited for post-July 2024 offence without savings authority."]
                )

        return StageVerificationReport(
            stage_name="Stage3_Concordance",
            is_passed=True,
            confidence=1.0,
            error_type=None,
            details={"valid_citations": cit_res.valid_citations},
            warnings=cit_res.rejection_reasons
        )


    # -------------------------------------------------------------------------
    # STAGE 4: Cross-Stage Confidence Propagation & Mutation Leakage Detector
    # -------------------------------------------------------------------------
    def verify_pipeline(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        candidate_response: str
    ) -> MultiStageVerificationResult:
        """
        Executes end-to-end multi-stage verification with stage gating and
        cross-stage confidence propagation.
        """
        # Step 1: Parse timeline and verify Stage 1
        temporal_res = self.temporal_engine.resolve(query)
        s1_report = self.verify_stage1_temporal(temporal_res.timeline)

        if not s1_report.is_passed:
            return MultiStageVerificationResult(
                is_verified=False,
                overall_confidence=0.0,
                failed_stage="Stage1_Temporal",
                stage_reports={"Stage1_Temporal": s1_report},
                remediation_suggestion=f"Temporal timeline paradox: {s1_report.warnings[0] if s1_report.warnings else 'Invalid date order'}",
                sanitized_output="[VERIFICATION FAILED: Query contains an unresolvable temporal paradox.]"
            )

        # Step 2: Verify Stage 2 (Retrieval Regime Leakage)
        s2_report = self.verify_stage2_retrieval(temporal_res, retrieved_chunks)
        if not s2_report.is_passed:
            return MultiStageVerificationResult(
                is_verified=False,
                overall_confidence=s1_report.confidence * s2_report.confidence,
                failed_stage="Stage2_Retrieval",
                stage_reports={"Stage1_Temporal": s1_report, "Stage2_Retrieval": s2_report},
                remediation_suggestion=f"Regime Leakage: Retrieved chunks do not match applicable regime ({temporal_res.substantive_code}). Re-retrieve with correct statute index.",
                sanitized_output=f"[VERIFICATION FAILED: Statutory regime leakage detected ({s2_report.error_type}).]"
            )

        # Step 3: Verify Stage 3 (Concordance & Repeals)
        s3_report = self.verify_stage3_concordance(candidate_response, temporal_res)
        if not s3_report.is_passed:
            return MultiStageVerificationResult(
                is_verified=False,
                overall_confidence=s1_report.confidence * s2_report.confidence * s3_report.confidence,
                failed_stage="Stage3_Concordance",
                stage_reports={
                    "Stage1_Temporal": s1_report,
                    "Stage2_Retrieval": s2_report,
                    "Stage3_Concordance": s3_report
                },
                remediation_suggestion=f"Concordance/Citation Failure: {s3_report.error_type}. Veto candidate output.",
                sanitized_output=f"[VERIFICATION FAILED: Citation invalid or repealed provision cited ({s3_report.error_type}).]"
            )

        # Step 4: Grounding check
        normalized_chunks = []
        for ch in retrieved_chunks:
            if isinstance(ch, dict):
                normalized_chunks.append({
                    "section_title": ch.get("section_title", ch.get("statute", "")),
                    "section_text": ch.get("section_text", ch.get("text", ""))
                })
            else:
                normalized_chunks.append({
                    "section_title": "",
                    "section_text": str(ch)
                })

        grounding_res = self.grounding_verifier.verify_grounding(
            generated_text=candidate_response,
            retrieved_chunks=normalized_chunks,
            query=query
        )

        s4_confidence = 1.0 if grounding_res.is_grounded else 0.4
        s4_report = StageVerificationReport(
            stage_name="Stage4_Grounding",
            is_passed=grounding_res.is_grounded,
            confidence=s4_confidence,
            error_type=None if grounding_res.is_grounded else "UNGROUNDED_PENAL_CLAIM",
            details={
                "overlap_score": grounding_res.overlap_score,
                "intent_aligned": grounding_res.intent_aligned,
                "grounded_entities": grounding_res.grounded_entities,
                "ungrounded_entities": grounding_res.ungrounded_entities
            },
            warnings=grounding_res.intent_mismatches
        )



        overall_conf = s1_report.confidence * s2_report.confidence * s3_report.confidence * s4_report.confidence

        is_all_passed = s1_report.is_passed and s2_report.is_passed and s3_report.is_passed and s4_report.is_passed

        return MultiStageVerificationResult(
            is_verified=is_all_passed,
            overall_confidence=overall_conf,
            failed_stage=None if is_all_passed else "Stage4_Grounding",
            stage_reports={
                "Stage1_Temporal": s1_report,
                "Stage2_Retrieval": s2_report,
                "Stage3_Concordance": s3_report,
                "Stage4_Grounding": s4_report
            },
            remediation_suggestion=None if is_all_passed else "Ungrounded penal ingredient or low factual overlap with statute text.",
            sanitized_output=candidate_response if is_all_passed else "[VERIFICATION CAUTION: Output partially ungrounded.]"
        )

    # -------------------------------------------------------------------------
    # CONVENIENCE HELPERS FOR CELL-BY-CELL TESTING
    # -------------------------------------------------------------------------
    def verify_stage1_timeline(self, timeline_input: Any) -> Dict[str, Any]:
        """Convenience method for Stage 1 testing accepting dict or ExtractedTimeline."""
        if isinstance(timeline_input, ExtractedTimeline):
            rep = self.verify_stage1_temporal(timeline_input)
        elif isinstance(timeline_input, dict):
            # Parse dates if string
            inc = timeline_input.get("incident_date")
            fir = timeline_input.get("fir_date")
            if isinstance(inc, str):
                parts = [int(p) for p in inc.split("-")]
                inc = date(parts[0], parts[1], parts[2])
            if isinstance(fir, str):
                parts = [int(p) for p in fir.split("-")]
                fir = date(parts[0], parts[1], parts[2])
            tl = ExtractedTimeline(raw_query="", incident_date=inc, fir_date=fir)
            rep = self.verify_stage1_temporal(tl)
        else:
            rep = StageVerificationReport(stage_name="Stage1", is_passed=False, confidence=0.0)

        return {
            "passed": rep.is_passed,
            "confidence": rep.confidence,
            "error_type": rep.error_type,
            "reason": rep.warnings[0] if rep.warnings else None,
            "report": rep
        }

    def verify_stage2_retrieval_scope(self, target_regime: str, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convenience method for Stage 2 testing."""
        is_legacy = "legacy" in target_regime.lower() or "ipc" in target_regime.lower()
        sub_code = "IPC_1860" if is_legacy else "BNS_2023"
        proc_code = "CRPC_1973" if is_legacy else "BNSS_2023"
        
        dummy_tl = ExtractedTimeline(raw_query="")
        dummy_res = TemporalResolution(
            raw_query="",
            timeline=dummy_tl,
            substantive_code=sub_code,
            procedural_code=proc_code,
            evidence_code="IEA_1872" if is_legacy else "BSA_2023",
            is_contested_split=False
        )
        rep = self.verify_stage2_retrieval(dummy_res, retrieved_chunks)
        return {
            "passed": rep.is_passed,
            "confidence": rep.confidence,
            "error_type": rep.error_type,
            "reason": rep.warnings[0] if rep.warnings else None,
            "report": rep
        }

    def verify_stage3_citations(self, citations: Any, is_post_july_offence: bool = True) -> Dict[str, Any]:
        """Convenience method for Stage 3 testing."""
        dummy_tl = ExtractedTimeline(raw_query="")
        sub_code = "BNS_2023" if is_post_july_offence else "IPC_1860"
        dummy_res = TemporalResolution(
            raw_query="",
            timeline=dummy_tl,
            substantive_code=sub_code,
            procedural_code="BNSS_2023" if is_post_july_offence else "CRPC_1973",
            evidence_code="BSA_2023" if is_post_july_offence else "IEA_1872",
            is_contested_split=False
        )
        if isinstance(citations, list):
            text_rep = " ".join(str(c) for c in citations)
        else:
            text_rep = str(citations)

        rep = self.verify_stage3_concordance(text_rep, dummy_res)
        return {
            "passed": rep.is_passed,
            "confidence": rep.confidence,
            "error_type": rep.error_type,
            "reason": rep.warnings[0] if rep.warnings else None,
            "report": rep
        }

    def verify_stage4_grounding_claim(self, generated_claim: str, statutory_text: str) -> Dict[str, Any]:
        """Convenience method for Stage 4 testing with direct text."""
        chunks = [{"section_title": "Statute", "section_text": statutory_text}]
        res = self.grounding_verifier.verify_grounding(
            generated_text=generated_claim,
            retrieved_chunks=chunks,
            query=""
        )
        return {
            "passed": res.is_grounded,
            "overlap_score": res.overlap_score,
            "intent_aligned": res.intent_aligned,
            "reason": res.intent_mismatches[0] if res.intent_mismatches else ("Low overlap" if not res.is_grounded else None)
        }
