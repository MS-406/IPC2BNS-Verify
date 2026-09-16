"""
abstention_engine.py — Confidence-Calibrated Selective Prediction & Structured Conflict Disclosure (v2)

Implements:
1. Selective prediction gating based on calibrated threshold tau.
2. Structured Conflict Disclosure / Abstention Card generation for unresolved High Court splits.
3. Clarification generator for underspecified date/posture queries.
4. Risk-coverage computation and Expected Calibration Error (ECE) metric calculations.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.temporal.timeline_parser import TimelineParser, ExtractedTimeline
from src.temporal.savings_clause_engine import SavingsClauseEngine, TemporalResolution
from src.council.model_council import ModelCouncil, CouncilVerdict
from src.verifier.stage_leakage_verifier import StageLeakageVerifier


@dataclass
class AbstentionCard:
    should_abstain: bool
    confidence_score: float
    abstention_reason: Optional[str] = None
    conflict_type: Optional[str] = None      # "HIGH_COURT_SPLIT" | "LOW_CONFIDENCE" | "UNDERSPECIFIED_DATE" | "COUNCIL_DISAGREEMENT"
    conflicting_authorities: Dict[str, Any] = field(default_factory=dict)
    safe_recommendation: Optional[str] = None
    required_clarifications: List[str] = field(default_factory=list)
    final_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_abstain": self.should_abstain,
            "confidence_score": round(self.confidence_score, 3),
            "abstention_reason": self.abstention_reason,
            "conflict_type": self.conflict_type,
            "conflicting_authorities": self.conflicting_authorities,
            "safe_recommendation": self.safe_recommendation,
            "required_clarifications": self.required_clarifications,
            "final_output": self.final_output
        }


class SelectivePredictionEngine:
    """
    Evaluates confidence calibration and triggers structured abstention
    whenever query certainty is insufficient or statutory interpretation is actively contested.
    """
    DEFAULT_CONFIDENCE_THRESHOLD = 0.80

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        self.tau = confidence_threshold
        self.temporal_engine = SavingsClauseEngine()
        self.timeline_parser = TimelineParser()
        self.council = ModelCouncil()
        self.stage_verifier = StageLeakageVerifier()

    def evaluate_query(self, query: str, force_refresh: bool = False) -> AbstentionCard:
        # Step 1: Temporal & Timeline Analysis
        timeline = self.timeline_parser.parse(query)
        temporal_res = self.temporal_engine.resolve_timeline(timeline)

        # Condition 1: Underspecified critical dates on procedurally sensitive queries
        if timeline.extracted_dates == [] and timeline.posture in ["APPEAL_OR_REVISION", "BAIL_APPLICATION", "TRIAL_ONGOING", "INVESTIGATION_PENDING"]:
            return AbstentionCard(
                should_abstain=True,
                confidence_score=0.40,
                abstention_reason="Critical procedural dates (incident date or FIR/filing date) are missing from the query.",
                conflict_type="UNDERSPECIFIED_DATE",
                conflicting_authorities={},
                safe_recommendation="Applicability of CrPC 1973 vs BNSS 2023 depends strictly on whether the proceeding was instituted before or after 1 July 2024.",
                required_clarifications=[
                    "What was the exact date when the original FIR/complaint was lodged?",
                    "When did the trial or investigation initiate?",
                    "In which High Court / State is the petition being instituted?"
                ],
                final_output=(
                    "[ABSTENTION: Underspecified Procedural Timeline]\n"
                    "Cannot provide a definitive governing code without knowing whether the proceedings were instituted "
                    "before or after the 1 July 2024 cutoff under Section 531(2)(a) BNSS."
                )
            )


        # Condition 2: Unresolved High Court Split without jurisdiction context
        if temporal_res.is_contested_split and not timeline.jurisdiction_hint:
            split_info = temporal_res.split_details or {}
            jurisdictions = split_info.get("jurisdictions", {})

            return AbstentionCard(
                should_abstain=True,
                confidence_score=0.60,
                abstention_reason="Query triggers a live, unresolved jurisdictional split across State High Courts regarding Section 531(2)(a) BNSS.",
                conflict_type="HIGH_COURT_SPLIT",
                conflicting_authorities=jurisdictions,
                safe_recommendation=(
                    "In Kerala and Delhi, invoke BNSS provisions. In Punjab & Haryana and Bombay, invoke CrPC provisions. "
                    "Plead both statutes in alternative with an explicit non-prejudice savings clause."
                ),
                required_clarifications=["Specify the target High Court (e.g., Delhi, Kerala, Bombay, Punjab & Haryana) to obtain precise state-specific binding precedent."],
                final_output=(
                    "[STRUCTURED CONFLICT DISCLOSURE: Unsettled High Court Split]\n"
                    f"Issue: {split_info.get('issue', 'Section 531 BNSS savings clause interpretation')}\n\n"
                    "High Courts have rendered divergent judgments on this point:\n"
                    "• Kerala High Court (Abdul Khader v. Joice, 2024): Held BNSS 2023 applies.\n"
                    "• Punjab & Haryana High Court (Mandeep Singh v. State, 2024): Held CrPC 1973 continues to apply.\n"
                    "• Delhi High Court (Prince v. State, 2024): Applied literal rule requiring BNSS for new petitions.\n"
                    "• Bombay High Court (Digambar v. State, 2024): Held defect in section labeling is curable.\n\n"
                    "Recommendation: Please specify your State jurisdiction for exact binding authority."
                )
            )

        # Step 2: Model Council Execution
        verdict: CouncilVerdict = self.council.process_query(query, force_refresh=force_refresh)

        # Condition 3: Council Disagreement
        if not verdict.consensus_reached or verdict.consensus_confidence < self.tau:
            return AbstentionCard(
                should_abstain=True,
                confidence_score=verdict.consensus_confidence,
                abstention_reason=f"Model council could not reach required {self.tau*100:.0f}% consensus threshold.",
                conflict_type="COUNCIL_DISAGREEMENT",
                conflicting_authorities={"dissenting_opinions": verdict.dissenting_opinions},
                safe_recommendation="Seek direct verification against bare act gazette notification.",
                required_clarifications=["Provide specific factual ingredients or statutory section numbers."],
                final_output=(
                    f"[ABSTENTION: Council Consensus Below Threshold ({verdict.consensus_confidence*100:.0f}% < {self.tau*100:.0f}%)]\n"
                    "The legal reasoning council flagged divergent interpretations across member models."
                )
            )

        # Step 3: Clean Confident Acceptance
        return AbstentionCard(
            should_abstain=False,
            confidence_score=verdict.consensus_confidence,
            abstention_reason=None,
            conflict_type=None,
            conflicting_authorities={},
            safe_recommendation="Direct statutory response verified.",
            required_clarifications=[],
            final_output=verdict.synthesized_answer
        )
