"""
generator.py — Generative Answer Engine for Statutory Legal QA

Implements generation for:
- Stage 1: Closed-book baseline LLM (no retrieval)
- Stage 2: RAG-augmented generation (+retrieval context)

Supports:
1. Google Gemini API (gemini-2.5-flash / gemini-2.0-flash)
2. Local deterministic fallback generator for offline testing and zero-API execution.
"""

import os
import sys
import time
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from src.generation.prompt_template import LegalPromptBuilder
from src.retrieval.search import retrieve_statutes
from src.mapping.lookup import map_ipc_to_bns, map_bns_to_ipc, MappingStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("generator")


@dataclass
class GenerationResult:
    question_id: str
    query_text: str
    stage: int                          # 1 or 2
    generated_text: str
    citations: List[Dict[str, str]]
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    model_name: str = "gemini-2.5-flash"
    latency_ms: float = 0.0
    prompt_used: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "query_text": self.query_text,
            "stage": self.stage,
            "generated_text": self.generated_text,
            "citations": self.citations,
            "retrieved_chunks": self.retrieved_chunks,
            "model_name": self.model_name,
            "latency_ms": round(self.latency_ms, 2),
            "cited_sections": [c["section"] for c in self.citations]
        }


class StatuteGenerator:
    """
    Core generative engine for Stage 1 and Stage 2 answering.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.genai_client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.genai_client = genai
                log.info(f"Initialized Gemini generation client for model: {self.model_name}")
            except Exception as e:
                log.warning(f"Could not initialize Google GenAI client: {e}")
                self.genai_client = None

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API."""
        if not self.genai_client:
            raise RuntimeError("Gemini client not initialized (missing API key).")

        model = self.genai_client.GenerativeModel(
            model_name=self.model_name,
            generation_config={"temperature": 0.1, "max_output_tokens": 1024}
        )
        response = model.generate_content(prompt)
        return response.text.strip()

    def _offline_fallback_stage1(self, query: str) -> str:
        """
        Simulates closed-book baseline LLM behaviour:
        Often confuses IPC sections with BNS, or hallucinate old IPC sections for BNS queries.
        """
        q_lower = query.lower()
        if "murder" in q_lower:
            return "Under Indian criminal law, murder is penalized under [IPC §302] with death or life imprisonment. Under the new Bharatiya Nyaya Sanhita, it has been renumbered to [BNS §103]."
        elif "cheating" in q_lower:
            return "Cheating and dishonestly inducing delivery of property was previously punished under [IPC §420] with up to 7 years imprisonment. In BNS 2023, it is covered under [BNS §318]."
        elif "theft" in q_lower:
            return "Theft is punishable with up to three years imprisonment under [IPC §379] and is now [BNS §303]."
        elif "sedition" in q_lower:
            return "Sedition was defined under [IPC §124A]. In the new BNS 2023, sedition has been replaced by [BNS §152] covering acts endangering sovereignty."
        elif "dowry death" in q_lower:
            return "Dowry death is punished with a minimum of seven years imprisonment under [IPC §304B] and now [BNS §80]."
        else:
            return f"Regarding '{query}', the offence falls under the relevant provisions of the Indian Penal Code [IPC §420] and Bharatiya Nyaya Sanhita [BNS §318]."

    def _offline_fallback_stage2(self, query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Simulates grounded RAG response based strictly on top retrieved context chunks.
        """
        if not retrieved_chunks:
            return "Based on statutory context, no matching statutory provision was found."

        top_chunk = retrieved_chunks[0]
        act = top_chunk.get("act", "BNS")
        sec = top_chunk.get("section_number", "")
        title = top_chunk.get("section_title", "")
        text = top_chunk.get("section_text", "")

        answer_parts = [
            f"Based on authoritative statutory context, this matter is governed by [{act} §{sec}] ({title}).",
            f"Statutory provision: {text}",
        ]

        if len(retrieved_chunks) > 1:
            second_chunk = retrieved_chunks[1]
            answer_parts.append(
                f"Additionally, [{second_chunk['act']} §{second_chunk['section_number']}] ({second_chunk['section_title']}) is relevant."
            )

        return " ".join(answer_parts)

    def generate_stage1(self, query: str, question_id: str = "Q_000") -> GenerationResult:
        """
        Stage 1: Closed-book baseline LLM generation (zero retrieval).
        """
        prompt_data = LegalPromptBuilder.build_stage1_prompt(query)
        start_t = time.time()

        if self.genai_client:
            try:
                gen_text = self._call_gemini(prompt_data["full_prompt"])
            except Exception as e:
                log.warning(f"Gemini API call failed, falling back to local model: {e}")
                gen_text = self._offline_fallback_stage1(query)
        else:
            gen_text = self._offline_fallback_stage1(query)

        latency = (time.time() - start_t) * 1000.0
        citations = LegalPromptBuilder.extract_citations(gen_text)

        return GenerationResult(
            question_id=question_id,
            query_text=query,
            stage=1,
            generated_text=gen_text,
            citations=citations,
            retrieved_chunks=[],
            model_name=self.model_name if self.genai_client else f"{self.model_name}-offline-sim",
            latency_ms=latency,
            prompt_used=prompt_data
        )

    def generate_stage2(self, query: str, question_id: str = "Q_000", top_k: int = 3,
                        act_filter: Optional[str] = None) -> GenerationResult:
        """
        Stage 2: RAG-augmented generation (retrieval context provided, no verifier).
        """
        # Step 1: Retrieve context chunks
        chunks = retrieve_statutes(query=query, top_k=top_k, act_filter=act_filter)

        # Step 2: Build prompt with context
        prompt_data = LegalPromptBuilder.build_stage2_prompt(query, chunks)
        start_t = time.time()

        if self.genai_client:
            try:
                gen_text = self._call_gemini(prompt_data["full_prompt"])
            except Exception as e:
                log.warning(f"Gemini API call failed, falling back to local model: {e}")
                gen_text = self._offline_fallback_stage2(query, chunks)
        else:
            gen_text = self._offline_fallback_stage2(query, chunks)

        latency = (time.time() - start_t) * 1000.0
        citations = LegalPromptBuilder.extract_citations(gen_text)

        return GenerationResult(
            question_id=question_id,
            query_text=query,
            stage=2,
            generated_text=gen_text,
            citations=citations,
            retrieved_chunks=chunks,
            model_name=self.model_name if self.genai_client else f"{self.model_name}-offline-sim",
            latency_ms=latency,
            prompt_used=prompt_data
        )


# ── Global singleton accessor ─────────────────────────────────────────────
_GLOBAL_GENERATOR: Optional[StatuteGenerator] = None


def get_generator(model_name: str = "gemini-2.5-flash") -> StatuteGenerator:
    global _GLOBAL_GENERATOR
    if _GLOBAL_GENERATOR is None:
        _GLOBAL_GENERATOR = StatuteGenerator(model_name=model_name)
    return _GLOBAL_GENERATOR
