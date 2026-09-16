import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class SplitResolution:
    is_split: bool
    split_id: Optional[str] = None
    issue: Optional[str] = None
    jurisdiction_breakdown: Optional[Dict[str, Any]] = None
    advisory: Optional[str] = None

class HighCourtSplitResolver:
    """
    Detects and resolves High Court disagreements concerning the interpretation
    of Section 531 BNSS savings clause.
    """
    def __init__(self, split_db_path: Optional[str] = None):
        if split_db_path is None:
            # Look relative to repository root
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            split_db_path = base_dir / "data" / "01_temporal" / "high_court_split_cases.json"
        
        self.split_db_path = Path(split_db_path)
        self.splits_data = self._load_splits()

    def _load_splits(self) -> List[Dict[str, Any]]:
        if self.split_db_path.exists():
            with open(self.split_db_path, "r", encoding="utf-8") as f:
                return json.load(f).get("splits", [])
        return []

    def check_split(self, posture: str, incident_date_pre_july: bool, filing_date_post_july: bool) -> SplitResolution:
        """
        Determines if the factual matrix falls into a known High Court divergence.
        """
        # Scenario 1: Appeal/Revision filed post-July for pre-July trial/conviction
        if posture == "APPEAL_OR_REVISION" and filing_date_post_july and incident_date_pre_july:
            for s in self.splits_data:
                if s["split_id"] == "SPLIT_APPEAL_POST_JULY_PRE_JULY_TRIAL":
                    return SplitResolution(
                        is_split=True,
                        split_id=s["split_id"],
                        issue=s["issue"],
                        jurisdiction_breakdown=s["jurisdictions"],
                        advisory=s["advisory"]
                    )

        # Scenario 2: Bail Application filed post-July for pre-July offence/FIR
        if posture == "BAIL_APPLICATION" and filing_date_post_july and incident_date_pre_july:
            for s in self.splits_data:
                if s["split_id"] == "SPLIT_BAIL_APPLICATION_POST_JULY_PRE_JULY_FIR":
                    return SplitResolution(
                        is_split=True,
                        split_id=s["split_id"],
                        issue=s["issue"],
                        jurisdiction_breakdown=s["jurisdictions"],
                        advisory=s["advisory"]
                    )

        return SplitResolution(is_split=False)
