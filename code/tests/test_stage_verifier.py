import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.verifier.stage_leakage_verifier import StageLeakageVerifier

@pytest.fixture
def verifier():
    return StageLeakageVerifier()

def test_stage1_temporal_paradox_caught(verifier):
    query = "The incident happened on 20 August 2024, but the FIR was lodged on 10 July 2024."
    chunks = [{"text": "BNS Section 303 defines theft.", "statute": "BNS", "section": "303"}]
    candidate = "Under Section 303 BNS, theft is punishable."
    
    result = verifier.verify_pipeline(query, chunks, candidate)
    assert not result.is_verified
    assert result.failed_stage == "Stage1_Temporal"
    assert "TEMPORAL_PARADOX" in result.stage_reports["Stage1_Temporal"].error_type

def test_stage2_regime_leakage_caught(verifier):
    # Pure Legacy query (January 2024)
    query = "The theft occurred on 15 January 2024 with FIR on 16 January 2024."
    # Leakage: Only modern BNS chunks retrieved
    leaked_chunks = [{"text": "BNS Section 303 defines theft under Bharatiya Nyaya Sanhita.", "statute": "BNS", "section": "303"}]
    candidate = "The applicable provision is Section 303 of BNS 2023."
    
    result = verifier.verify_pipeline(query, leaked_chunks, candidate)
    assert not result.is_verified
    assert result.failed_stage == "Stage2_Retrieval"
    assert result.stage_reports["Stage2_Retrieval"].error_type == "REGIME_LEAKAGE_MODERN_INTO_LEGACY"

def test_stage3_hallucinated_citation_caught(verifier):
    query = "Offence committed on 10 August 2024."
    chunks = [{"text": "BNS Section 303 defines theft.", "statute": "BNS", "section": "303"}]
    # Hallucinated non-existent section 999
    candidate = "Under [BNS §999], the accused is sentenced to 5 years."
    
    result = verifier.verify_pipeline(query, chunks, candidate)
    assert not result.is_verified
    assert result.failed_stage == "Stage3_Concordance"

def test_stage3_repealed_section_on_modern_case_caught(verifier):
    query = "Offence of sedition committed on 15 August 2024."
    chunks = [{"text": "BNS Section 152 deals with acts endangering sovereignty.", "statute": "BNS", "section": "152"}]
    # Repealed IPC 124A cited on modern post-July case
    candidate = "The accused is charged under [IPC §124A] for sedition."
    
    result = verifier.verify_pipeline(query, chunks, candidate)
    assert not result.is_verified
    assert result.failed_stage == "Stage3_Concordance"
    assert result.stage_reports["Stage3_Concordance"].error_type == "ILLEGAL_REPEALED_CITATION"

def test_pipeline_clean_pass(verifier):
    query = "A theft offence was committed on 15 August 2024 with FIR lodged on 16 August 2024."
    chunks = [{"text": "BNS Section 303 defines theft and prescribes imprisonment up to three years or fine.", "statute": "BNS", "section": "303"}]
    candidate = "Under [BNS §303], theft is defined as dishonestly taking movable property, punishable with imprisonment up to three years or fine."
    
    result = verifier.verify_pipeline(query, chunks, candidate)
    assert result.is_verified
    assert result.failed_stage is None
    assert result.overall_confidence > 0.8
