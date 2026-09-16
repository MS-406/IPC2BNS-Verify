"""
router.py — Query-Complexity Learned Router for Legal Architecture (v2)

Classifies legal queries into computational execution tiers:
- TIER_1_DIRECT: Direct 1:1 statutory mappings / settled temporal queries (single fast model/lookup).
- TIER_2_SPLIT_MERGE: Substantive 1:N split, merged offences, or partial penal shifts (dual-model verification).
- TIER_3_CONTESTED_COUNCIL: Section 531 BNSS savings clauses, multi-date transitional postures, High Court splits (full multi-model consensus council).
"""

import os
import sys
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.temporal.timeline_parser import TimelineParser
from src.temporal.savings_clause_engine import SavingsClauseEngine
from src.mapping.lookup import get_lookup_engine, MappingStatus


class QueryTier(Enum):
    TIER_1_DIRECT = "TIER_1_DIRECT"
    TIER_2_SPLIT_MERGE = "TIER_2_SPLIT_MERGE"
    TIER_3_CONTESTED_COUNCIL = "TIER_3_CONTESTED_COUNCIL"


@dataclass
class RoutingDecision:
    query: str
    tier: QueryTier
    reason: str
    target_models: List[str]
    complexity_score: float             # 0.0 (trivial) to 1.0 (highly contested)
    is_temporal_involved: bool
    is_contested_split: bool
    features: Dict[str, Any] = field(default_factory=dict)


class QueryRouter:
    """
    Intelligent router analyzing statutory ambiguity and temporal complexity
    to route queries to the most cost- and accuracy-optimal execution tier.
    """

    def __init__(self, concordance_path: Optional[str] = None):
        self.lookup = get_lookup_engine(concordance_path)
        self.temporal_engine = SavingsClauseEngine()
        self.timeline_parser = TimelineParser()

    def classify_query(self, query: str) -> RoutingDecision:
        # Step 1: Temporal analysis
        timeline = self.timeline_parser.parse(query)
        temporal_res = self.temporal_engine.resolve_timeline(timeline)

        is_temporal = len(timeline.extracted_dates) > 0 or timeline.incident_date is not None
        is_split = temporal_res.is_contested_split

        # Check for High Court split or Section 531 BNSS contested issue
        if is_split:
            return RoutingDecision(
                query=query,
                tier=QueryTier.TIER_3_CONTESTED_COUNCIL,
                reason="Contested High Court split / Section 531 BNSS transitional savings clause detected.",
                target_models=["LLaMA-3-Legal-70B", "Mistral-Large-Instruct", "Deterministic-Concordance-Oracle"],
                complexity_score=0.95,
                is_temporal_involved=True,
                is_contested_split=True,
                features={"split_id": temporal_res.split_details.get("split_id") if temporal_res.split_details else None}
            )

        # Check for multi-date transitional ambiguity (e.g. pre-July incident + post-July FIR)
        if is_temporal and temporal_res.substantive_code != "BNS_2023" and temporal_res.procedural_code == "BNSS_2023":
            return RoutingDecision(
                query=query,
                tier=QueryTier.TIER_3_CONTESTED_COUNCIL,
                reason="Transitional dual-regime query (Substantive IPC 1860 + Procedural BNSS 2023).",
                target_models=["LLaMA-3-Legal-70B", "Mistral-Large-Instruct", "Deterministic-Concordance-Oracle"],
                complexity_score=0.85,
                is_temporal_involved=True,
                is_contested_split=False,
                features={"substantive": temporal_res.substantive_code, "procedural": temporal_res.procedural_code}
            )

        # Step 2: Check statutory mapping complexity
        ipc_secs = re.findall(r'(?:ipc|section|sec\.?|§)\s*([0-9]+[a-z]?)', query.lower())
        bns_secs = re.findall(r'(?:bns)\s*(?:§|section|sec\.?)?\s*([0-9]+[a-z]?)', query.lower())

        is_substantive_split = False
        is_repealed = False
        matched_branches = []

        for sec in ipc_secs:
            map_res = self.lookup.map_ipc_to_bns(sec)
            if map_res.status == MappingStatus.AMBIGUOUS_SPLIT:
                is_substantive_split = True
                matched_branches.extend(map_res.all_matched_sections)
            elif map_res.status == MappingStatus.AMBIGUOUS_MERGED:
                is_substantive_split = True
            elif map_res.status == MappingStatus.REPEALED:
                is_repealed = True

        # Check keywords indicating split / repeal concepts
        query_lower = query.lower()
        if any(w in query_lower for w in [
            "sedition", "adultery", "unnatural", "repealed", "omitted",
            "split", "merged", "merge", "branches", "difference between",
            "counterpart", "organized crime", "mob lynching", "terrorist act", "new offence"
        ]):
            is_substantive_split = True


        if is_substantive_split or is_repealed:
            return RoutingDecision(
                query=query,
                tier=QueryTier.TIER_2_SPLIT_MERGE,
                reason="Substantive 1:N split, merged offences, or repealed statutory provision detected.",
                target_models=["LLaMA-3-Legal-8B", "Mistral-7B-Instruct"],
                complexity_score=0.60,
                is_temporal_involved=is_temporal,
                is_contested_split=False,
                features={"split_branches": matched_branches, "is_repealed": is_repealed}
            )

        # Step 3: Default Direct Settled Lookup
        return RoutingDecision(
            query=query,
            tier=QueryTier.TIER_1_DIRECT,
            reason="Direct 1:1 statutory mapping / settled modern penal query.",
            target_models=["Deterministic-Concordance-Oracle"],
            complexity_score=0.15,
            is_temporal_involved=is_temporal,
            is_contested_split=False,
            features={"direct_ipc_citations": ipc_secs, "direct_bns_citations": bns_secs}
        )
