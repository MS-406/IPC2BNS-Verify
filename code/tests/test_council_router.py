import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.council.router import QueryRouter, QueryTier
from src.council.model_council import ModelCouncil

@pytest.fixture
def router():
    return QueryRouter()

@pytest.fixture
def council():
    return ModelCouncil()

def test_tier1_direct_lookup(router):
    decision = router.classify_query("What is the punishment for murder under section 302 IPC?")
    assert decision.tier == QueryTier.TIER_1_DIRECT
    assert decision.complexity_score < 0.40

def test_tier2_substantive_split(router):
    decision = router.classify_query("Is sedition still an offence under the new Bharatiya Nyaya Sanhita?")
    assert decision.tier == QueryTier.TIER_2_SPLIT_MERGE
    assert 0.40 <= decision.complexity_score <= 0.75

def test_tier3_transitional_dual_regime(router):
    decision = router.classify_query("Incident took place on 10 June 2024, but the FIR was registered on 15 July 2024.")
    assert decision.tier == QueryTier.TIER_3_CONTESTED_COUNCIL
    assert decision.is_temporal_involved

def test_tier3_high_court_split(router):
    decision = router.classify_query("We want to file an appeal in August 2024 against a conviction handed down in April 2024.")
    assert decision.tier == QueryTier.TIER_3_CONTESTED_COUNCIL
    assert decision.is_contested_split
    assert decision.complexity_score >= 0.85

def test_council_execution_and_checkpoint_cache(council):
    query = "Offence committed on 20 May 2024. Anticipatory bail filed on 10 July 2024."
    # First execution (computes and caches)
    verdict1 = council.process_query(query, force_refresh=True)
    assert verdict1.routing_tier == QueryTier.TIER_3_CONTESTED_COUNCIL.value
    assert verdict1.consensus_reached
    assert not verdict1.from_cache

    # Second execution (must hit persistent disk checkpoint cache)
    verdict2 = council.process_query(query, force_refresh=False)
    assert verdict2.from_cache
    assert verdict2.synthesized_answer == verdict1.synthesized_answer
    assert verdict2.consensus_confidence == verdict1.consensus_confidence
