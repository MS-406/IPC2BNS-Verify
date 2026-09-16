import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.temporal.timeline_parser import TimelineParser
from src.temporal.savings_clause_engine import SavingsClauseEngine


@pytest.fixture
def engine():
    return SavingsClauseEngine()

def test_pure_legacy_case(engine):
    query = "The theft incident occurred on 15 March 2024 and the FIR was registered on 20 March 2024. Which law applies for trial?"
    res = engine.resolve(query)
    assert res.substantive_code == "IPC_1860"
    assert res.procedural_code == "CRPC_1973"
    assert res.evidence_code == "IEA_1872"
    assert not res.is_contested_split
    assert any("Section 531(2)(a)" in c for c in res.statutory_citations)

def test_transitional_pre_incident_post_fir(engine):
    query = "The assault happened on 10 June 2024, but the police lodged the FIR on 15 July 2024. Which criminal codes govern?"
    res = engine.resolve(query)
    assert res.substantive_code == "IPC_1860"
    assert res.procedural_code == "BNSS_2023"
    assert res.evidence_code == "BSA_2023"
    assert not res.is_contested_split
    assert "Article 20(1)" in res.reasoning

def test_post_july_modern_case(engine):
    query = "An offence of cyber fraud took place on 25 August 2024 with FIR filed on 26 August 2024."
    res = engine.resolve(query)
    assert res.substantive_code == "BNS_2023"
    assert res.procedural_code == "BNSS_2023"
    assert res.evidence_code == "BSA_2023"
    assert not res.is_contested_split

def test_high_court_split_appeal(engine):
    query = "The magistrate convicted the accused in May 2024 under IPC. We want to file a criminal appeal on 20 August 2024. Does CrPC or BNSS apply?"
    res = engine.resolve(query)
    assert res.is_contested_split
    assert res.split_details["split_id"] == "SPLIT_APPEAL_POST_JULY_PRE_JULY_TRIAL"
    assert "Kerala_High_Court" in res.split_details["jurisdictions"]
    assert "Punjab_and_Haryana_High_Court" in res.split_details["jurisdictions"]

def test_high_court_split_with_jurisdiction_context(engine):
    query = "In Kerala High Court, filing an appeal in September 2024 against a conviction handed down in April 2024."
    res = engine.resolve(query)
    assert res.is_contested_split
    assert "BNSS_2023" in res.procedural_code
    assert "Abdul Khader" in res.actionable_guidance

def test_anticipatory_bail_split(engine):
    query = "An incident happened on May 12, 2024. Anticipatory bail application is being filed on July 10, 2024 in Bombay."
    res = engine.resolve(query)
    assert res.is_contested_split
    assert res.split_details["split_id"] == "SPLIT_BAIL_APPLICATION_POST_JULY_PRE_JULY_FIR"
