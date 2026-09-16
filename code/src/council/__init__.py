"""
Multi-Model Council & Learned Complexity Router (v2)
Orchestrates:
- Tier 1: Fast deterministic lookup for unambiguous queries
- Tier 2: Dual-model verification for substantive splits & merges
- Tier 3: Multi-model consensus council for contested savings clauses & High Court splits
- Persistent inference checkpointing and disk caching
"""

from .router import QueryRouter, QueryTier, RoutingDecision
from .model_council import ModelCouncil, CouncilVerdict, ModelMember

__all__ = [
    "QueryRouter",
    "QueryTier",
    "RoutingDecision",
    "ModelCouncil",
    "CouncilVerdict",
    "ModelMember"
]
