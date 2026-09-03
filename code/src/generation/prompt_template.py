"""
prompt_template.py — Prompt Construction & Citation Formatting for Statute RAG

Defines structured prompt templates enforcing strict legal citation conventions:
1. Canonical citation format: [Act §Section], e.g. [BNS §103], [IPC §302], [BNS §106(2)].
2. Grounded answering instructions: rely exclusively on provided retrieved chunks.
3. Explicit ambiguity / repeal handling instructions.
"""

import re
from typing import List, Dict, Any, Optional

SYSTEM_PROMPT_STAGE1 = """You are an authoritative Indian legal assistant specializing in the transition from the Indian Penal Code (IPC 1860) to the Bharatiya Nyaya Sanhita (BNS 2023).

Instructions:
1. Answer the question accurately based on your knowledge of Indian statutory criminal law.
2. For EVERY legal statement, cite the specific statutory section in strict brackets format: [Act §SectionNumber], for example: [BNS §103] or [IPC §302].
3. If an IPC offence has been repealed or omitted in BNS without direct equivalent (e.g. sedition, adultery), explicitly state that it has been repealed and explain the change.
4. Keep answers concise, factual, and legally precise."""

SYSTEM_PROMPT_STAGE2 = """You are an authoritative Indian legal assistant specializing in the transition from the Indian Penal Code (IPC 1860) to the Bharatiya Nyaya Sanhita (BNS 2023).

Instructions:
1. You are provided with AUTHORITATIVE STATUTORY CONTEXT below retrieved from the official bare acts.
2. Answer the user's question relying STRICTLY and EXCLUSIVELY on the provided statutory context.
3. For EVERY substantive assertion, cite the exact provision from the context using the format: [Act §SectionNumber], for example: [BNS §103] or [IPC §302].
4. Do NOT cite any section number that is not explicitly present in the provided context.
5. If the provided context does not contain sufficient information or if a section was repealed, explicitly state: "Based on statutory context, this provision is repealed / not present."
6. Be concise, objective, and precise."""


class LegalPromptBuilder:
    """
    Constructs prompts for Stage 1 (closed-book baseline) and Stage 2 (+RAG).
    """

    CITATION_PATTERN = re.compile(
        r'\[(IPC|BNS|BHARATIYA NYAYA SANHITA|INDIAN PENAL CODE)\s*§?\s*(\d+[A-Z]?(?:\(\d+\))?)\]',
        re.IGNORECASE
    )

    @classmethod
    def format_statutory_context(cls, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Formats retrieved statutory chunks into clean markdown context blocks.
        """
        if not retrieved_chunks:
            return "No statutory context provided."

        context_blocks = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            act = chunk.get("act", "STATUTE")
            sec = chunk.get("section_number", "")
            title = chunk.get("section_title", "")
            text = chunk.get("section_text", "")
            chapter = chunk.get("chapter", "")

            block = (
                f"--- STATUTORY PROVISION #{i} ---\n"
                f"Act: {act}\n"
                f"Section: §{sec} - {title}\n"
                f"Chapter: {chapter}\n"
                f"Text:\n{text}\n"
            )
            context_blocks.append(block)

        return "\n".join(context_blocks)

    @classmethod
    def build_stage1_prompt(cls, query: str) -> Dict[str, str]:
        """
        Constructs prompt for Stage 1 (Base LLM, zero retrieval).
        """
        user_message = f"Question: {query.strip()}\n\nPlease provide your answer with statutory citations in [Act §Section] format:"
        return {
            "system_prompt": SYSTEM_PROMPT_STAGE1,
            "user_prompt": user_message,
            "full_prompt": f"{SYSTEM_PROMPT_STAGE1}\n\n{user_message}"
        }

    @classmethod
    def build_stage2_prompt(cls, query: str, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Constructs prompt for Stage 2 (+RAG retrieved context).
        """
        context_str = cls.format_statutory_context(retrieved_chunks)
        user_message = (
            f"=== STATUTORY CONTEXT ===\n"
            f"{context_str}\n\n"
            f"=== USER QUESTION ===\n"
            f"Question: {query.strip()}\n\n"
            f"Answer based exclusively on the context above with citations in [Act §Section] format:"
        )
        return {
            "system_prompt": SYSTEM_PROMPT_STAGE2,
            "context": context_str,
            "user_prompt": user_message,
            "full_prompt": f"{SYSTEM_PROMPT_STAGE2}\n\n{user_message}"
        }

    @classmethod
    def extract_citations(cls, text: str) -> List[Dict[str, str]]:
        """
        Extracts all statutory citations from generated text.
        Returns: [{"act": "BNS", "section": "103", "raw": "[BNS §103]"}, ...]
        """
        matches = cls.CITATION_PATTERN.findall(text)
        citations = []
        for act, sec in matches:
            act_norm = "BNS" if "BNS" in act.upper() or "BHARATIYA" in act.upper() else "IPC"
            citations.append({
                "act": act_norm,
                "section": sec.upper().strip(),
                "raw": f"[{act_norm} §{sec.upper().strip()}]"
            })
        return citations
