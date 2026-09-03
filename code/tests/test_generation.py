"""
test_generation.py — Unit Tests for Phase 3 Generation Layer

Verifies:
1. LegalPromptBuilder constructs valid prompts with expected bracket formats.
2. Citation extraction regex parses [Act §Section] correctly.
3. Stage 1 generator generates responses with citations.
4. Stage 2 generator injects retrieved statutory context into responses.
5. Generated responses contain non-empty citation metadata.
"""

import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.generation.prompt_template import LegalPromptBuilder
from src.generation.generator import StatuteGenerator, get_generator


def test_prompt_builder_stage1():
    query = "What is the section for murder in BNS?"
    prompt = LegalPromptBuilder.build_stage1_prompt(query)
    assert "system_prompt" in prompt
    assert "user_prompt" in prompt
    assert query in prompt["user_prompt"]
    assert "[Act §SectionNumber]" in prompt["system_prompt"]


def test_prompt_builder_stage2():
    query = "What is the penalty for murder?"
    mock_chunks = [{
        "act": "BNS",
        "section_number": "103",
        "section_title": "Punishment for murder",
        "section_text": "Whoever commits murder shall be punished with death or life imprisonment.",
        "chapter": "Chapter VI"
    }]
    prompt = LegalPromptBuilder.build_stage2_prompt(query, mock_chunks)
    assert "BNS" in prompt["context"]
    assert "§103" in prompt["context"]
    assert query in prompt["user_prompt"]


def test_citation_extraction_regex():
    sample_text = (
        "Under [BNS §103], punishment for murder is death or life imprisonment. "
        "Previously, under [IPC §302], it was identical. Also see [BNS §106(2)] for hit and run."
    )
    citations = LegalPromptBuilder.extract_citations(sample_text)
    assert len(citations) == 3

    c_acts = [c["act"] for c in citations]
    c_secs = [c["section"] for c in citations]

    assert "BNS" in c_acts and "IPC" in c_acts
    assert "103" in c_secs and "302" in c_secs and "106(2)" in c_secs


def test_stage1_generation_execution():
    gen = get_generator()
    res = gen.generate_stage1("What is the punishment for cheating in BNS?")
    assert res.stage == 1
    assert len(res.generated_text) > 0
    assert len(res.citations) > 0
    assert res.retrieved_chunks == []


def test_stage2_generation_execution():
    gen = get_generator()
    res = gen.generate_stage2("Where is dowry death covered in BNS 2023?", top_k=2)
    assert res.stage == 2
    assert len(res.generated_text) > 0
    assert len(res.citations) > 0
    assert len(res.retrieved_chunks) > 0
    assert res.retrieved_chunks[0]["act"] in ("IPC", "BNS")
