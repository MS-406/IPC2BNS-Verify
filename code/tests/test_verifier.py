"""
test_verifier.py — Unit Tests for Phase 4 Hard-Constraint Verifier Layer

Verifies:
1. Layer 1 rejects hallucinated non-existent section numbers (e.g. [BNS §999]).
2. Layer 1 vetoes citations of repealed provisions (e.g. [IPC §124A], [IPC §497]).
3. Layer 2 identifies ungrounded penal claims (e.g. death penalty for simple theft).
4. Master verifier correctly passes grounded, authoritative answers (0% False Positives).
5. Master verifier produces structured MasterVerificationResult with appropriate verdicts.
"""

import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.verifier.citation_check import get_citation_verifier
from src.verifier.entity_grounding import get_grounding_verifier
from src.verifier.verifier_pipeline import get_master_verifier, verify_answer
from src.generation.prompt_template import LegalPromptBuilder


# =========================================================================
# 1. Layer 1 Citation Check Tests
# =========================================================================

def test_layer1_accepts_valid_citations():
    verifier = get_citation_verifier()
    valid_cits = [{"act": "BNS", "section": "103", "raw": "[BNS §103]"}]
    res = verifier.verify_citations(valid_cits)
    assert res.is_valid is True
    assert len(res.invalid_citations) == 0


def test_layer1_rejects_hallucinated_bns_section():
    verifier = get_citation_verifier()
    fake_cits = [{"act": "BNS", "section": "999", "raw": "[BNS §999]"}]
    res = verifier.verify_citations(fake_cits)
    assert res.is_valid is False
    assert len(res.invalid_citations) == 1
    assert "999" in res.rejection_reasons[0]


def test_layer1_flags_repealed_ipc_sections():
    verifier = get_citation_verifier()
    repealed_cits = [{"act": "IPC", "section": "124A", "raw": "[IPC §124A]"}]
    res = verifier.verify_citations(repealed_cits)
    assert res.is_valid is False
    assert len(res.repealed_citations) == 1
    assert "repealed" in res.rejection_reasons[0].lower()


# =========================================================================
# 2. Layer 2 Entity Grounding Tests
# =========================================================================

def test_layer2_passes_grounded_text():
    grounder = get_grounding_verifier()
    mock_chunks = [{
        "section_title": "Punishment for murder",
        "section_text": "Whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine."
    }]
    gen_text = "Under [BNS §103], whoever commits murder shall be punished with death or imprisonment for life and fine."
    res = grounder.verify_grounding(gen_text, mock_chunks)
    assert res.is_grounded is True
    assert res.overlap_score >= 0.70


def test_layer2_fails_ungrounded_penal_claim():
    grounder = get_grounding_verifier()
    mock_chunks = [{
        "section_title": "Theft",
        "section_text": "Whoever commits theft shall be punished with imprisonment up to three years or with fine."
    }]
    # Hallucinates death penalty for theft
    gen_text = "Whoever commits theft under [BNS §303] shall be punished with mandatory death penalty or life imprisonment."
    res = grounder.verify_grounding(gen_text, mock_chunks)
    assert "death" in res.ungrounded_entities or "life imprisonment" in res.ungrounded_entities


# =========================================================================
# 3. Master Verifier End-to-End Tests
# =========================================================================

def test_master_verifier_sedition_veto():
    gen_text = "Sedition remains active under [IPC §124A] for exciting disaffection."
    cits = LegalPromptBuilder.extract_citations(gen_text)
    res = verify_answer(gen_text, cits, retrieved_chunks=[])

    assert res.is_verified is False
    assert res.verdict == "VETOED_REPEALED_PROVISION"
    assert "[VERIFIER VETO]" in res.verified_output_text


def test_master_verifier_hallucination_rejection():
    gen_text = "The new provision is [BNS §999]."
    cits = LegalPromptBuilder.extract_citations(gen_text)
    res = verify_answer(gen_text, cits, retrieved_chunks=[])

    assert res.is_verified is False
    assert res.verdict == "REJECTED_HALLUCINATED_CITATION"
    assert "[VERIFIER REJECTION]" in res.verified_output_text


def test_master_verifier_valid_answer_passed():
    mock_chunks = [{
        "act": "BNS",
        "section_number": "103",
        "section_title": "Punishment for murder",
        "section_text": "Whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine."
    }]
    gen_text = "Under [BNS §103], murder is punished with death or imprisonment for life and fine."
    cits = LegalPromptBuilder.extract_citations(gen_text)
    res = verify_answer(gen_text, cits, retrieved_chunks=mock_chunks)

    assert res.is_verified is True
    assert res.verdict == "VERIFIED"
    assert res.verified_output_text == gen_text


def test_layer1_5_multi_citation_consistency_passes():
    """Validates concordant cross-statute citations: IPC 420 <-> BNS 318 for Cheating."""
    verifier = get_citation_verifier()
    valid_multi_cits = [
        {"act": "BNS", "section": "318", "raw": "[BNS §318]"},
        {"act": "IPC", "section": "420", "raw": "[IPC §420]"}
    ]
    res = verifier.verify_citations(valid_multi_cits)
    assert res.is_cross_statute_consistent is True
    assert len(res.cross_statute_inconsistencies) == 0


def test_layer1_5_multi_citation_consistency_rejects_mismatch():
    """Catches contradictory cross-statute citations: IPC 302 (Murder) with BNS 318 (Cheating)."""
    verifier = get_citation_verifier()
    conflicting_cits = [
        {"act": "BNS", "section": "318", "raw": "[BNS §318]"},
        {"act": "IPC", "section": "302", "raw": "[IPC §302]"}
    ]
    res = verifier.verify_citations(conflicting_cits)
    assert res.is_cross_statute_consistent is False
    assert len(res.cross_statute_inconsistencies) > 0
    assert "Cross-statute citation mismatch" in res.cross_statute_inconsistencies[0]

