"""
flan_t5_generator.py — Phase 7 Flan-T5 Generator (Open-Source Replacement)

Replaces the Gemini/offline-simulator with Google Flan-T5-base.
This is a fully open-source, locally-running model with NO external API calls.

Citation:
    Chung et al. (2022). Scaling Instruction-Finetuned Language Models.
    arXiv:2210.11416. https://huggingface.co/google/flan-t5-base

Model: google/flan-t5-base (~300MB, Apache 2.0 license, runs on CPU)

This module is ISOLATED to phase7/ and does NOT modify any existing file.

Usage (from project root):
    python phase7/generators/flan_t5_generator.py --test
"""

import os
import sys
import json
import time
import logging
import re
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PHASE7_ROOT = os.path.join(PROJECT_ROOT, "phase7")
CODE_DIR = os.path.join(PROJECT_ROOT, "code")

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("flan_t5_generator")

MODEL_NAME = "google/flan-t5-base"
MODEL_LABEL = "flan-t5-base"  # What goes in result files — NO Gemini mention


# ─── Model singleton ──────────────────────────────────────────────────────────

_tokenizer = None
_model = None

def _load_model():
    """Load Flan-T5-base. Model weights are cached locally."""
    global _tokenizer, _model
    if _model is not None and _tokenizer is not None:
        return _tokenizer, _model
    
    try:
        from transformers import T5ForConditionalGeneration, T5Tokenizer
        log.info(f"Loading {MODEL_NAME} from local cache...")
        t0 = time.time()
        _tokenizer = T5Tokenizer.from_pretrained(MODEL_NAME)
        _model = T5ForConditionalGeneration.from_pretrained(MODEL_NAME)
        _model.eval()
        log.info(f"Flan-T5-base loaded in {time.time()-t0:.1f}s")
        return _tokenizer, _model
    except Exception as e:
        log.error(f"Failed to load Flan-T5: {e}")
        raise


def run_flan_t5_inference(prompt: str, max_new_tokens: int = 128) -> str:
    """Run deterministic greedy inference using Flan-T5-base."""
    tokenizer, model = _load_model()
    import torch
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


# ─── Prompt templates ─────────────────────────────────────────────────────────

SYSTEM_CONTEXT = """You are a legal expert on Indian criminal law transitions.
The Indian Penal Code (IPC) 1860 was replaced by the Bharatiya Nyaya Sanhita (BNS) 2023,
effective 1 July 2024. The Code of Criminal Procedure (CrPC) 1973 was replaced by the
Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023 on the same date.
Answer the following question accurately, citing the specific section number."""


def build_stage1_prompt(query: str) -> str:
    """Closed-book prompt — no retrieved context."""
    return f"""{SYSTEM_CONTEXT}

Question: {query}

Answer with the specific BNS or BNSS section number that applies:"""


def build_stage2_prompt(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """RAG-augmented prompt with retrieved statutory context."""
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks[:5], 1):
        act = chunk.get("act", "")
        sec = chunk.get("section_number", "")
        title = chunk.get("section_title", "")
        text = chunk.get("section_text", "")[:300]  # Truncate for T5 context window
        context_parts.append(f"[{i}] {act} Section {sec} — {title}: {text}")
    
    context = "\n".join(context_parts) if context_parts else "No statutory context retrieved."
    
    return f"""{SYSTEM_CONTEXT}

Statutory context:
{context}

Question: {query}

Based on the above statutory context, answer with the specific section number:"""


# ─── Citation extraction ───────────────────────────────────────────────────────

def extract_citations(text: str) -> List[str]:
    """Extract section citations from generated text."""
    # Patterns: BNS §103, BNS Section 103, Section 103, §103, [BNS §103]
    patterns = [
        r'\[?(?:BNS|IPC|BNSS|CrPC)\s*[§S](?:ection\s*)?\s*(\w+(?:\.\w+)?(?:\([^)]+\))?)\]?',
        r'[§S]ection\s+(\d+[A-Z]?(?:\.\d+)?(?:\([^)]+\))?)',
        r'\b(\d{1,3}[A-Z]?)\b(?=\s*(?:BNS|IPC|BNSS|of the))',
    ]
    found = []
    for p in patterns:
        matches = re.findall(p, text, re.IGNORECASE)
        found.extend(matches)
    
    # Deduplicate, keep order
    seen = set()
    result = []
    for s in found:
        s_clean = s.strip().rstrip(".")
        if s_clean and s_clean not in seen:
            seen.add(s_clean)
            result.append(s_clean)
    return result


# ─── Generation result dataclass ──────────────────────────────────────────────

class FlanT5Result:
    def __init__(self, question_id, query_text, stage, generated_text,
                 citations, retrieved_chunks, model_name, latency_ms, prompt_used):
        self.question_id = question_id
        self.query_text = query_text
        self.stage = stage
        self.generated_text = generated_text
        self.cited_sections = extract_citations(generated_text)
        self.citations = citations
        self.retrieved_chunks = retrieved_chunks
        self.model_name = model_name
        self.latency_ms = latency_ms
        self.prompt_used = prompt_used
    
    def to_dict(self):
        return {
            "question_id": self.question_id,
            "query_text": self.query_text,
            "stage": self.stage,
            "generated_text": self.generated_text,
            "cited_sections": self.cited_sections,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
        }


# ─── Main generator class ─────────────────────────────────────────────────────

class FlanT5StatuteGenerator:
    """
    Drop-in replacement for the existing StatuteGenerator.
    Uses Flan-T5-base (Apache 2.0 license, ~300MB, CPU-compatible).
    Citable as: Chung et al. (2022), arXiv:2210.11416.
    """

    def __init__(self):
        self.model_name = MODEL_LABEL
        self._pipe = None
        log.info("FlanT5StatuteGenerator initialized (model will load on first call).")

    def _get_pipe(self):
        if self._pipe is None:
            self._pipe = _load_model()
        return self._pipe

    def generate_stage1(self, query: str, question_id: str = "UNK") -> FlanT5Result:
        """Closed-book generation (no retrieval context)."""
        prompt = build_stage1_prompt(query)
        t0 = time.time()
        
        try:
            output = run_flan_t5_inference(prompt, max_new_tokens=150)
        except Exception as e:
            log.warning(f"Flan-T5 generation failed: {e}")
            output = f"Section not identified. Query: {query}"
        
        latency = (time.time() - t0) * 1000
        cited = extract_citations(output)
        
        return FlanT5Result(
            question_id=question_id,
            query_text=query,
            stage=1,
            generated_text=output,
            citations=[{"section": s, "act": "BNS", "raw": s} for s in cited],
            retrieved_chunks=[],
            model_name=self.model_name,
            latency_ms=round(latency, 2),
            prompt_used=prompt,
        )

    def generate_stage2(self, query: str, question_id: str = "UNK",
                        top_k: int = 5, retrieved_chunks: Optional[List[Dict]] = None) -> FlanT5Result:
        """RAG-augmented generation with retrieved statutory context."""
        chunks = retrieved_chunks or []
        
        # Attempt retrieval if chunks not provided
        if not chunks:
            try:
                from src.retrieval.search import retrieve_statutes
                chunks = retrieve_statutes(query=query, top_k=top_k)
            except Exception as e:
                log.warning(f"Retrieval failed: {e}")
        
        prompt = build_stage2_prompt(query, chunks)
        t0 = time.time()
        
        try:
            output = run_flan_t5_inference(prompt, max_new_tokens=150)
        except Exception as e:
            log.warning(f"Flan-T5 generation failed: {e}")
            output = f"Unable to generate answer for: {query}"
        
        latency = (time.time() - t0) * 1000
        cited = extract_citations(output)
        
        return FlanT5Result(
            question_id=question_id,
            query_text=query,
            stage=2,
            generated_text=output,
            citations=[{"section": s, "act": "BNS", "raw": s} for s in cited],
            retrieved_chunks=chunks[:top_k],
            model_name=self.model_name,
            latency_ms=round(latency, 2),
            prompt_used=prompt,
        )


# ─── Singleton accessor ───────────────────────────────────────────────────────

_generator_instance = None

def get_flan_t5_generator() -> FlanT5StatuteGenerator:
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = FlanT5StatuteGenerator()
    return _generator_instance


# ─── Quick test ───────────────────────────────────────────────────────────────

def run_test():
    print("=" * 60)
    print("Flan-T5-base Generator Test")
    print("=" * 60)
    
    gen = get_flan_t5_generator()
    
    test_queries = [
        "Which BNS section replaced IPC Section 302 for murder?",
        "What is the BNSS equivalent of CrPC Section 154 for FIR?",
        "IPC Section 420 on cheating — what is the BNS equivalent?",
        "What happened to sedition under IPC Section 124A in BNS 2023?",
    ]
    
    for q in test_queries:
        print(f"\nQ: {q}")
        result = gen.generate_stage1(q, question_id="TEST")
        print(f"A: {result.generated_text}")
        print(f"   Cited sections: {result.cited_sections}")
        print(f"   Latency: {result.latency_ms:.0f}ms | Model: {result.model_name}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        run_test()
