"""
test_concordance.py — Unit Tests for Phase 1 Mapping & Concordance Module

Verifies:
1. Ground-truth table structure & integrity (concordance_v1.csv)
2. Deterministic IPC → BNS mapping accuracy
3. Deterministic BNS → IPC reverse lookup accuracy
4. Explicit ambiguity handling (repeals, splits, merges, new BNS provisions)
5. Query normalizer regex & domain lexicon extraction accuracy
6. End-to-end integration: User Query → Normalizer → Concordance Lookup
7. Boundary conditions (invalid section IDs, whitespace, case insensitivity)
"""

import os
import sys
import pytest

# Ensure src is on path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.mapping.lookup import (
    ConcordanceLookup,
    MappingStatus,
    map_ipc_to_bns,
    map_bns_to_ipc,
    get_lookup_engine
)
from src.mapping.normalizer import (
    QueryNormalizer,
    normalize_query
)


@pytest.fixture
def lookup_engine():
    return get_lookup_engine()


@pytest.fixture
def normalizer():
    return QueryNormalizer(use_llm=False)


# =========================================================================
# 1. Ground Truth Integrity Tests
# =========================================================================

def test_concordance_table_loads_successfully(lookup_engine):
    """Verify that concordance_v1.csv is non-empty and loaded into memory."""
    assert len(lookup_engine.raw_rows) > 0
    assert len(lookup_engine.ipc_to_bns_index) > 0
    assert len(lookup_engine.bns_to_ipc_index) > 0


def test_concordance_schema_columns(lookup_engine):
    """Verify all expected columns exist in raw rows."""
    expected_cols = {
        "ipc_section", "ipc_title", "bns_section", "bns_title",
        "relationship_type", "notes", "source", "verified", "last_updated"
    }
    for row in lookup_engine.raw_rows[:10]:
        assert expected_cols.issubset(set(row.keys()))


# =========================================================================
# 2. Core Deterministic Mapping Tests (IPC -> BNS)
# =========================================================================

@pytest.mark.parametrize("ipc_sec, expected_bns", [
    ("302", "103"),     # Murder -> 103
    ("299", "100"),     # Culpable homicide -> 100
    ("304A", "106"),    # Death by negligence -> 106
    ("304B", "80"),     # Dowry death -> 80
    ("307", "109"),     # Attempt to murder -> 109
    ("378", "303"),     # Theft -> 303
    ("383", "308"),     # Extortion -> 308
    ("390", "309"),     # Robbery -> 309
    ("391", "310"),     # Dacoity -> 310
    ("415", "318"),     # Cheating -> 318
    ("420", "318"),     # Cheating & dishonestly inducing delivery -> 318
    ("463", "335"),     # Forgery -> 335
    ("499", "356"),     # Defamation -> 356
    ("503", "351"),     # Criminal intimidation -> 351
    ("511", "62"),      # Attempt -> 62
])
def test_deterministic_exact_mappings(ipc_sec, expected_bns):
    """Verify ground-truth accuracy on high-frequency statutory sections."""
    result = map_ipc_to_bns(ipc_sec)
    assert result.is_valid_mapping is True
    assert result.target_section == expected_bns
    assert result.source_act == "IPC"
    assert result.target_act == "BNS"


def test_case_and_whitespace_insensitivity():
    """Verify lookup normalizes messy input strings."""
    assert map_ipc_to_bns(" 302 ").target_section == "103"
    assert map_ipc_to_bns("section 302").target_section == "103"
    assert map_ipc_to_bns("sec. 420").target_section == "318"
    assert map_ipc_to_bns("IPC 307").target_section == "109"


# =========================================================================
# 3. Reverse Lookup Tests (BNS -> IPC)
# =========================================================================

@pytest.mark.parametrize("bns_sec, expected_ipc", [
    ("103", "302"),     # Murder
    ("100", "299"),     # Culpable homicide
    ("80", "304B"),     # Dowry death
    ("318", "415"),     # Cheating (or 420 in merged set)
    ("356", "499"),     # Defamation
])
def test_reverse_lookup_mappings(bns_sec, expected_ipc):
    """Verify BNS -> IPC reverse lookup works accurately."""
    result = map_bns_to_ipc(bns_sec)
    assert result.is_valid_mapping is True
    assert expected_ipc in result.all_matched_sections or result.target_section == expected_ipc


# =========================================================================
# 4. Critical Ambiguity Handling Tests (Novelty Verification)
# =========================================================================

def test_sedition_repeal_is_flagged_ambiguous():
    """
    CRITICAL TEST: IPC §124A (sedition) was repealed and NOT directly carried over.
    BNS §152 is narrower. System MUST reject auto-mapping and flag ambiguous.
    """
    result = map_ipc_to_bns("124A")
    assert result.status == MappingStatus.REPEALED
    assert result.is_ambiguous is True
    assert result.target_section is None
    assert "repealed" in result.notes.lower() or "sovereignty" in result.notes.lower()


def test_unnatural_offences_repeal():
    """IPC §377 struck down/repealed -> MUST return repealed."""
    result = map_ipc_to_bns("377")
    assert result.status == MappingStatus.REPEALED
    assert result.target_section is None


def test_adultery_repeal():
    """IPC §497 struck down/repealed -> MUST return repealed."""
    result = map_ipc_to_bns("497")
    assert result.status == MappingStatus.REPEALED
    assert result.target_section is None


def test_split_section_handling():
    """
    IPC §33 ('Act' and 'Omission') split into BNS §2(1) and §2(25).
    MUST return AMBIGUOUS_SPLIT with both target sub-clauses.
    """
    result = map_ipc_to_bns("33")
    assert result.status == MappingStatus.AMBIGUOUS_SPLIT
    assert result.is_ambiguous is True
    assert len(result.all_matched_sections) >= 2


def test_new_bns_provisions_flagged_correctly():
    """
    Reverse lookup for new BNS offences (e.g. §111 Organised Crime, §113 Terrorist Act)
    MUST return NEW_IN_BNS with target_section=None.
    """
    res_111 = map_bns_to_ipc("111")
    assert res_111.status == MappingStatus.NEW_IN_BNS
    assert res_111.is_ambiguous is True

    res_113 = map_bns_to_ipc("113")
    assert res_113.status == MappingStatus.NEW_IN_BNS
    assert res_113.is_ambiguous is True


def test_nonexistent_section_returns_not_found():
    """Querying an invalid section number must cleanly return NOT_FOUND."""
    result = map_ipc_to_bns("9999")
    assert result.status == MappingStatus.NOT_FOUND
    assert result.target_section is None
    assert result.is_valid_mapping is False


# =========================================================================
# 5. Query Normalizer Unit Tests
# =========================================================================

@pytest.mark.parametrize("query, expected_sec, expected_act", [
    ("What is section 302 in the new law?", "302", "IPC"),
    ("IPC Section 420 replacement", "420", "IPC"),
    ("What happened to sec 376 IPC?", "376", "IPC"),
    ("Under BNS Section 103 punishment", "103", "BNS"),
    ("§124A status", "124A", "IPC"),
    ("304A", "304A", "IPC"),
])
def test_normalizer_regex_extraction(normalizer, query, expected_sec, expected_act):
    norm = normalizer.normalize(query)
    assert norm.extracted_section == expected_sec
    assert norm.detected_act == expected_act
    assert norm.method == "regex"


@pytest.mark.parametrize("query, expected_sec", [
    ("what is the punishment for murder in the new law?", "302"),
    ("where is cheating defined now?", "420"),
    ("what section applies to dowry death?", "304B"),
    ("is sedition still a crime?", "124A"),
    ("new provision for extortion", "383"),
    ("defamation section in criminal code", "499"),
])
def test_normalizer_offence_lexicon(normalizer, query, expected_sec):
    norm = normalizer.normalize(query)
    assert norm.extracted_section == expected_sec
    assert norm.method == "offence_lexicon"


# =========================================================================
# 6. End-to-End Pipeline Integration Tests
# =========================================================================

def test_e2e_query_to_bns_mapping():
    """Verify raw user question -> normalizer -> deterministic lookup."""
    user_query = "What is the new section for cheating in BNS?"
    norm = normalize_query(user_query)
    assert norm.extracted_section == "420"

    mapping = map_ipc_to_bns(norm.extracted_section)
    assert mapping.target_section == "318"
    assert mapping.status in (MappingStatus.RENUMBERED, MappingStatus.EXACT, MappingStatus.AMBIGUOUS_MERGED)


def test_e2e_sedition_query_correctly_vetoed():
    """Verify sedition natural language query flags ambiguity end-to-end."""
    user_query = "What is the new section for sedition in BNS 2023?"
    norm = normalize_query(user_query)
    assert norm.extracted_section == "124A"

    mapping = map_ipc_to_bns(norm.extracted_section)
    assert mapping.status == MappingStatus.REPEALED
    assert mapping.is_ambiguous is True
    assert mapping.target_section is None


# =========================================================================
# 7. Valid Section ID Index Export for Verifier (Phase 4 Prerequisite)
# =========================================================================

def test_valid_bns_id_index_export(lookup_engine):
    """Verify valid BNS section IDs list is exported and non-empty."""
    valid_bns = lookup_engine.get_all_valid_bns_sections()
    assert len(valid_bns) > 50
    assert "103" in valid_bns
    assert "318" in valid_bns
    assert "100" in valid_bns
    # Ensure no garbage or repealed placeholders are in valid IDs
    assert "REPEALED" not in valid_bns
    assert "-" not in valid_bns
