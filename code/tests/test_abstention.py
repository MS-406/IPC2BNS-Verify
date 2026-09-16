import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.temporal.abstention_engine import SelectivePredictionEngine, AbstentionCard

@pytest.fixture
def engine():
    return SelectivePredictionEngine(confidence_threshold=0.80)

def test_abstention_on_underspecified_date(engine):
    # Missing crucial dates for appeal
    query = "Which code applies to file an appeal against conviction in my trial?"
    card: AbstentionCard = engine.evaluate_query(query)
    assert card.should_abstain
    assert card.conflict_type == "UNDERSPECIFIED_DATE"
    assert len(card.required_clarifications) > 0
    assert "Section 531(2)(a)" in card.final_output

def test_abstention_on_unresolved_high_court_split(engine):
    # HC split on appeals without specifying state
    query = "The magistrate convicted the accused in May 2024. We want to file a criminal appeal in August 2024. Does CrPC or BNSS apply?"
    card: AbstentionCard = engine.evaluate_query(query)
    assert card.should_abstain
    assert card.conflict_type == "HIGH_COURT_SPLIT"
    assert "Kerala" in card.final_output
    assert "Punjab & Haryana" in card.final_output
    assert "STRUCTURED CONFLICT DISCLOSURE" in card.final_output

def test_direct_answer_when_jurisdiction_specified(engine):
    # When High Court jurisdiction is specified, engine resolves directly without abstaining
    query = "In Kerala High Court, filing an appeal in September 2024 against a conviction handed down in April 2024."
    card: AbstentionCard = engine.evaluate_query(query)
    assert not card.should_abstain
    assert card.confidence_score >= 0.80
    assert "BNSS" in card.final_output

def test_direct_answer_on_unambiguous_case(engine):
    query = "What is the section for murder under Section 302 IPC in the new BNS code?"
    card: AbstentionCard = engine.evaluate_query(query)
    assert not card.should_abstain
    assert card.confidence_score >= 0.90
    assert "103" in card.final_output
