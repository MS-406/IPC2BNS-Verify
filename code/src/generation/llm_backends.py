"""
llm_backends.py — Multi-LLM Backend Manager for Comparative Evaluation

Wraps multiple LLM APIs for fair comparative benchmarking of the verification pipeline:
1. google/flan-t5-base (existing local baseline — deterministic)
2. gemini-2.0-flash (via google-generativeai SDK)
3. gpt-4o-mini (via openai SDK)
4. llama-3.1-8b-instant (via Groq API — free tier)
5. Hugging Face Inference API (meta-llama/Llama-3.1-8B-Instruct)

Each backend generates answers through the SAME verification pipeline,
enabling fair catch-rate comparison (Phase D, Gap 1).

Usage:
    from code.src.generation.llm_backends import LLMBackendManager
    manager = LLMBackendManager()
    result = manager.generate("What is BNS Section 302?", backend="gemini")
"""

import os
import sys
import time
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("llm_backends")


SYSTEM_PROMPT = """You are an expert Indian criminal law assistant. Answer questions about the 
Bharatiya Nyaya Sanhita (BNS) 2023, Indian Penal Code (IPC) 1860, Bharatiya Nagarik Suraksha 
Sanhita (BNSS) 2023, and Code of Criminal Procedure (CrPC) 1973.

CRITICAL RULES:
1. Always cite specific statutory sections using [Act §Section] format (e.g., [BNS §103], [IPC §302]).
2. When discussing section mappings, state both the old and new section numbers.
3. If a provision has been repealed, explicitly state it was repealed.
4. Do NOT fabricate section numbers — only cite sections you are certain exist.
5. Be precise about punishment provisions (imprisonment terms, fine amounts).
"""


@dataclass
class LLMResponse:
    text: str
    model_name: str
    backend: str
    latency_ms: float
    tokens_used: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "model_name": self.model_name,
            "backend": self.backend,
            "latency_ms": round(self.latency_ms, 2),
            "tokens_used": self.tokens_used,
            "error": self.error,
        }


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT,
                 temperature: float = 0.1, max_tokens: int = 1024) -> LLMResponse:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class GeminiBackend(LLMBackend):
    """Google Gemini API backend (gemini-2.0-flash / gemini-1.5-pro)."""

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = None
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai
            except ImportError:
                log.warning("google-generativeai package not installed")

    @property
    def name(self) -> str:
        return f"gemini/{self.model}"

    def is_available(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT,
                 temperature: float = 0.1, max_tokens: int = 1024) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(text="", model_name=self.model, backend="gemini",
                             latency_ms=0, error="Gemini API not available")
        start = time.time()
        try:
            model = self.client.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config={"temperature": temperature, "max_output_tokens": max_tokens}
            )
            response = model.generate_content(prompt)
            text = response.text.strip()
            latency = (time.time() - start) * 1000
            return LLMResponse(text=text, model_name=self.model, backend="gemini", latency_ms=latency)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return LLMResponse(text="", model_name=self.model, backend="gemini",
                             latency_ms=latency, error=str(e))


class OpenAIBackend(LLMBackend):
    """OpenAI API backend (gpt-4o-mini / gpt-4o)."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                log.warning("openai package not installed")

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    def is_available(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT,
                 temperature: float = 0.1, max_tokens: int = 1024) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(text="", model_name=self.model, backend="openai",
                             latency_ms=0, error="OpenAI API not available")
        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            text = response.choices[0].message.content.strip()
            tokens = response.usage.total_tokens if response.usage else 0
            latency = (time.time() - start) * 1000
            return LLMResponse(text=text, model_name=self.model, backend="openai",
                             latency_ms=latency, tokens_used=tokens)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return LLMResponse(text="", model_name=self.model, backend="openai",
                             latency_ms=latency, error=str(e))


class GroqBackend(LLMBackend):
    """Groq API backend for Llama-3 inference (free tier, very fast)."""

    def __init__(self, model: str = "llama-3.1-8b-instant"):
        self.model = model
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except ImportError:
                # Fallback: Use OpenAI-compatible endpoint
                try:
                    import openai
                    self.client = openai.OpenAI(
                        api_key=self.api_key,
                        base_url="https://api.groq.com/openai/v1"
                    )
                except ImportError:
                    log.warning("Neither groq nor openai packages installed for Groq backend")

    @property
    def name(self) -> str:
        return f"groq/{self.model}"

    def is_available(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT,
                 temperature: float = 0.1, max_tokens: int = 1024) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(text="", model_name=self.model, backend="groq",
                             latency_ms=0, error="Groq API not available")
        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            text = response.choices[0].message.content.strip()
            tokens = response.usage.total_tokens if response.usage else 0
            latency = (time.time() - start) * 1000
            return LLMResponse(text=text, model_name=self.model, backend="groq",
                             latency_ms=latency, tokens_used=tokens)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return LLMResponse(text="", model_name=self.model, backend="groq",
                             latency_ms=latency, error=str(e))


class HuggingFaceBackend(LLMBackend):
    """Hugging Face Inference API backend."""

    def __init__(self, model: str = "meta-llama/Llama-3.1-8B-Instruct"):
        self.model = model
        self.api_token = os.environ.get("HF_API_TOKEN")
        self._available = self.api_token is not None

    @property
    def name(self) -> str:
        return f"hf/{self.model.split('/')[-1]}"

    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT,
                 temperature: float = 0.1, max_tokens: int = 1024) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(text="", model_name=self.model, backend="huggingface",
                             latency_ms=0, error="HF_API_TOKEN not set")
        start = time.time()
        try:
            import requests
            headers = {"Authorization": f"Bearer {self.api_token}"}
            payload = {
                "inputs": f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n<|assistant|>\n",
                "parameters": {
                    "temperature": temperature,
                    "max_new_tokens": max_tokens,
                    "return_full_text": False
                }
            }
            resp = requests.post(
                f"https://api-inference.huggingface.co/models/{self.model}",
                headers=headers, json=payload, timeout=60
            )
            resp.raise_for_status()
            result = resp.json()
            text = result[0]["generated_text"].strip() if isinstance(result, list) else str(result)
            latency = (time.time() - start) * 1000
            return LLMResponse(text=text, model_name=self.model, backend="huggingface", latency_ms=latency)
        except Exception as e:
            latency = (time.time() - start) * 1000
            return LLMResponse(text="", model_name=self.model, backend="huggingface",
                             latency_ms=latency, error=str(e))


class DeterministicBackend(LLMBackend):
    """
    Deterministic statutory synthesizer baseline (no LLM API needed).
    Uses the existing concordance-based answer generation.
    """

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "deterministic/statutory_synthesizer_v1"

    def is_available(self) -> bool:
        return True  # Always available — no API key needed

    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT,
                 temperature: float = 0.0, max_tokens: int = 1024) -> LLMResponse:
        start = time.time()
        try:
            from src.generation.generator import get_generator
            gen = get_generator()
            result = gen._offline_fallback_stage1(prompt)
            latency = (time.time() - start) * 1000
            return LLMResponse(
                text=result,
                model_name="deterministic_statutory_synthesizer_v1",
                backend="deterministic",
                latency_ms=latency
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return LLMResponse(text="", model_name="deterministic", backend="deterministic",
                             latency_ms=latency, error=str(e))


class LLMBackendManager:
    """
    Unified manager for all LLM backends.
    Discovers available backends and provides a single interface for generation.
    """

    BACKEND_REGISTRY = {
        "deterministic": DeterministicBackend,
        "gemini": GeminiBackend,
        "openai": OpenAIBackend,
        "groq": GroqBackend,
        "huggingface": HuggingFaceBackend,
    }

    def __init__(self):
        self.backends: Dict[str, LLMBackend] = {}
        self._discover_backends()

    def _discover_backends(self):
        """Initialize all backends and check availability."""
        for name, cls in self.BACKEND_REGISTRY.items():
            try:
                backend = cls()
                self.backends[name] = backend
                status = "✅ Available" if backend.is_available() else "❌ Not configured"
                log.info(f"Backend [{name}] ({backend.name}): {status}")
            except Exception as e:
                log.warning(f"Backend [{name}] failed to initialize: {e}")

    def get_available_backends(self) -> List[str]:
        """Returns list of available backend names."""
        return [name for name, b in self.backends.items() if b.is_available()]

    def generate(self, prompt: str, backend: str = "gemini",
                 system_prompt: str = SYSTEM_PROMPT,
                 temperature: float = 0.1, max_tokens: int = 1024) -> LLMResponse:
        """Generate text using the specified backend."""
        if backend not in self.backends:
            return LLMResponse(text="", model_name="unknown", backend=backend,
                             latency_ms=0, error=f"Unknown backend: {backend}")

        b = self.backends[backend]
        if not b.is_available():
            return LLMResponse(text="", model_name=b.name, backend=backend,
                             latency_ms=0, error=f"Backend {backend} not configured (missing API key)")

        return b.generate(prompt, system_prompt=system_prompt,
                         temperature=temperature, max_tokens=max_tokens)

    def generate_all(self, prompt: str, system_prompt: str = SYSTEM_PROMPT,
                     temperature: float = 0.1, max_tokens: int = 1024) -> Dict[str, LLMResponse]:
        """Generate text using ALL available backends for comparison."""
        results = {}
        for name in self.get_available_backends():
            log.info(f"Generating with backend: {name}")
            results[name] = self.generate(prompt, backend=name,
                                         system_prompt=system_prompt,
                                         temperature=temperature,
                                         max_tokens=max_tokens)
        return results

    def status_report(self) -> str:
        """Returns a formatted status report of all backends."""
        lines = ["═══ LLM Backend Status ═══"]
        for name, b in self.backends.items():
            status = "✅" if b.is_available() else "❌"
            lines.append(f"  {status} {name:15s} → {b.name}")
        lines.append(f"\nAvailable: {len(self.get_available_backends())}/{len(self.backends)}")
        return "\n".join(lines)


# ── Global singleton ─────────────────────────────────────────────────────
_GLOBAL_MANAGER: Optional[LLMBackendManager] = None


def get_llm_manager() -> LLMBackendManager:
    global _GLOBAL_MANAGER
    if _GLOBAL_MANAGER is None:
        _GLOBAL_MANAGER = LLMBackendManager()
    return _GLOBAL_MANAGER


if __name__ == "__main__":
    manager = get_llm_manager()
    print(manager.status_report())

    # Quick test with all available backends
    test_query = "What is the BNS equivalent of IPC Section 302 (Murder)?"
    results = manager.generate_all(test_query)
    for backend, resp in results.items():
        print(f"\n─── {backend} ({resp.latency_ms:.0f}ms) ───")
        print(resp.text[:300] if resp.text else f"ERROR: {resp.error}")
