# Phase 7 — Audit of Existing IPC2BNS-Verify System

**Audit Date:** 2026-09-04  
**Auditor:** Phase 7 Evaluation Layer  
**Git HEAD:** `24d9744876b6e35e457c7eb42cfa0179dae8a5cc`  
**Purpose:** Document all existing interfaces for the Phase 7 evaluation adapter. Nothing in this document modifies or suggests modification of any existing component.

---

## 1. Question Representation

**File:** `data/03_benchmark/benchmark_dev.csv`  
**Format:** CSV  
**Fields:**

| Field | Type | Description |
|---|---|---|
| `question_id` | str | Unique ID (e.g., `DEV_001`, `CRPC_BNSS_001`) |
| `query_text` | str | Natural-language question |
| `query_type` | str | `transition`, `ingredient_punishment`, `ambiguous_repeal`, `new_offence`, `split_merged`, `stress`, `procedural_transition` |
| `source_act` | str | `IPC`, `BNS`, or `CrPC` |
| `target_act` | str | `BNS`, `IPC`, or `BNSS` |
| `ground_truth_sections` | str | Comma-separated expected section numbers |
| `ground_truth_answer` | str | Reference answer text |
| `is_ambiguous` | bool str | `True`/`False` string |
| `provenance` | str | `statute_qa`, `adapted_ilsi`, `hand_curated` |

---

## 2. Expected Answer Representation

Expected answers come in two forms:
1. **Structured section reference** — `ground_truth_sections` field (e.g., `"103"`, `"318"`, `"80"`)
2. **Natural text** — `ground_truth_answer` field (prose explanation)

Correctness is evaluated in `harness.py` (line 62) as:
```python
any(c.strip().upper() in r.get("ground_truth_sections","").upper() for c in r.get("cited_sections",[]))
```
i.e., **any cited section** appearing in the `ground_truth_sections` string counts as a hit.

---

## 3. IPC→BNS Mapping Representation

**File:** `data/02_ground_truth/concordance_v1.csv`  
**Size:** 155 rows, ~150 mapped IPC sections + 5 `new_in_bns` rows

**Fields:** `ipc_section, ipc_title, bns_section, bns_title, relationship_type, notes, source, verified, last_updated`

**Relationship types:** `exact`, `renumbered`, `split`, `merged`, `repealed`, `new_in_bns`, `modified`

**Loading:** `code/src/mapping/lookup.py` — `ConcordanceLookup._load_table()`  
**Query API:** `map_ipc_to_bns(section)` / `map_bns_to_ipc(section)` → `MappingResult` dataclass

**MappingResult fields:**
- `query_section`, `target_section`, `source_act`, `target_act`
- `source_title`, `target_title`
- `status: MappingStatus` (enum: EXACT, RENUMBERED, AMBIGUOUS_SPLIT, AMBIGUOUS_MERGED, REPEALED, NEW_IN_BNS, MODIFIED, NOT_FOUND)
- `is_ambiguous: bool`
- `notes: str`
- `source_provenance: str`
- `verified: bool`
- `all_matched_sections: List[str]`

**Repealed sections in concordance:** IPC §124A (sedition), §377, §497

---

## 4. CrPC→BNSS Mapping Representation

**File:** `code/src/mapping/lookup.py` (lines 341–375)  
**Type:** Hard-coded Python dict `CRPC_TO_BNSS_MAP`  
**Size:** 26 key-value pairs

**Entry format:**
```python
"154": {"bnss": "173", "title": "Information in cognizable cases (FIR & e-FIR)", "status": "exact"}
```

**Query API:** `map_crpc_to_bnss(section)` / `map_bnss_to_crpc(section)` → `MappingResult`

**Mapped CrPC sections:** 154, 41, 47, 167, 438, 437, 144, 173, 164, 174, 106, 125, 265A, 260, 320, 321, 374, 378, 482, 428, 366, 356, 176(3), 105, 472, 83, 530

---

## 5. Retrieval Execution

**Implementation:** `code/src/retrieval/embedder.py` — `LocalStatutoryVectorIndex`  
**Algorithm:** BM25/TF-IDF with cosine similarity + section-ID exact-match boost  
**Offline:** Yes — zero external API dependency  
**Parameters:**  
- `top_k = 5` (configurable)  
- `k1 = 1.5`, `b = 0.75` (BM25 parameters, set in embedder)  
- Section number match boost applied  
- Act filter available (`act_filter: Optional[str]`)

**Query API:**
```python
from src.retrieval.search import retrieve_statutes
chunks = retrieve_statutes(query=query, top_k=5, act_filter=None)
```

**Return type:** `List[Dict]` with fields:
`chunk_id, act, section_number, section_title, section_text, full_content, similarity_score, score, chapter, effective_date_range`

**Temporal filtering:** Available via `target_date` parameter on `StatutoryRetriever.retrieve()`

---

## 6. Generated Answer Obtainment

**Implementation:** `code/src/generation/generator.py` — `StatuteGenerator`

**Two modes:**
1. **Gemini API mode** (when `GEMINI_API_KEY` set): calls `google.generativeai` → `GenerativeModel.generate_content()`
2. **Offline simulation mode** (no API key): deterministic `_offline_fallback_stage1()` / `_offline_fallback_stage2()` based on keyword matching

**Confirmed from existing results:** `model_name = "gemini-2.0-flash-offline-sim"` → system ran in **offline mode**.

**Stage 1:** Closed-book (no retrieval) — `generate_stage1(query)`  
**Stage 2:** RAG-augmented — `generate_stage2(query, top_k=3, retrieved_chunks=...)` 

**Query API:**
```python
from src.generation.generator import get_generator
gen = get_generator()
result = gen.generate_stage1(query=q, question_id=qid)
result = gen.generate_stage2(query=q, question_id=qid, top_k=5)
```

**GenerationResult fields:**
`question_id, query_text, stage, generated_text, citations (List[Dict]), retrieved_chunks, model_name, latency_ms, prompt_used`

---

## 7. Verifier Decision Obtainment

**Implementation:** `code/src/verifier/verifier_pipeline.py` — `HardConstraintVerifier`

**Query API:**
```python
from src.verifier.verifier_pipeline import verify_answer
result = verify_answer(generated_text, citations, retrieved_chunks, query)
```

**Returns:** `MasterVerificationResult` with fields:
- `is_verified: bool`
- `verdict: str` — one of: `VERIFIED`, `REJECTED_HALLUCINATED_CITATION`, `VETOED_REPEALED_PROVISION`, `UNGROUNDED_CLAIM`, `NON_RESPONSIVE_ANSWER`, `AMBIGUOUS_SPLIT_CAUTION`, `REJECTED_CROSS_STATUTE_INCONSISTENCY`, `REJECTED_MISSING_CITATIONS`
- `confidence_score: float` (0.0–1.0)
- `confidence_grade: str` — `HIGH_CONFIDENCE_VERIFIED`, `MODERATE_CONFIDENCE_WARNING`, `AMBIGUOUS_SPLIT_FLAGGED`, `LOW_CONFIDENCE_REJECTED`, `VETOED_REPEALED`
- `ambiguity_score: float` (0.0–1.0)
- `layer1_result: CitationCheckResult`
- `layer2_result: EntityGroundingResult`

**Layer 1 checks (citation_check.py):**
- Section must exist in closed BNS/IPC statute index
- Repealed sections trigger veto
- Cross-statute inconsistency detection

**Layer 2 checks (entity_grounding.py):**
- Entity overlap between generated text and retrieved chunks
- `min_overlap_threshold = 0.35` (constructor default)
- Intent alignment (Layer 2.5)

---

## 8. Existing Results Storage

| File | Description |
|---|---|
| `results/stage1/stage1_baseline_results.json` | `{"stage":1, "total_queries":60, "results":[...]}` |
| `results/stage2/stage2_rag_results.json` | Stage 2 RAG results |
| `results/stage2/retrieval_metrics.json` | BM25 retrieval evaluation metrics |
| `results/stage3/stage3_verifier_results.json` | Stage 3 + stress suite results (includes `stress_suite` key) |
| `results/stage4/stage4_refresh_results.json` | N=3 amendment adaptivity |
| `results/ablation_summary_table.csv` | Master ablation table (Wilson CIs) |
| `results/crpc_bnss_generalization_results.json` | CrPC/BNSS generalization |
| `results/human_review_calibration.csv` | Double-blind calibration (Cohen's κ=0.93) |

**Per-result record schema (stage 2 example):**
```json
{
  "question_id": "DEV_001",
  "query_text": "...",
  "stage": 2,
  "generated_text": "...",
  "cited_sections": ["103"],
  "raw_citations": ["[BNS §103]"],
  "retrieved_chunk_ids": ["BNS_103_001"],
  "model_name": "gemini-2.0-flash-offline-sim",
  "latency_ms": 0.0,
  "ground_truth_sections": "103",
  "ground_truth_answer": "...",
  "is_ambiguous": false
}
```

---

## 9. eval/harness.py Interface

**Class:** `MasterEvaluationHarness`  
**Key method:** `compile_ablation_metrics()` → `List[Dict]`  
**Input:** Reads existing stage JSON files from `results/stage{n}/`  
**Output:** 5 rows (Stage 1–4 + Generalization) with Wilson CIs  
**Correctness metric:** Citation hit — any `cited_section` appears in `ground_truth_sections` string (case-insensitive)

**Wilson CI helper:** `wilson_score_interval(successes, total, confidence=0.95)` — available for reuse in Phase 7 via import.

---

## 10. generation/run_ablations.py Interface

**Functions:**
- `load_benchmark(benchmark_csv)` → `List[Dict]`
- `run_stage1_ablation(benchmark_csv, output_path)` — saves JSON to `output_path`
- `run_stage2_ablation(benchmark_csv, output_path)` — saves JSON
- `run_stage3_ablation(benchmark_csv, output_path)` — saves JSON (includes stress suite)
- `run_stage4_ablation(benchmark_csv, output_path)` — saves JSON (runs refresh)

**Phase 7 will NOT call these functions** (to avoid any risk of overwriting). Instead it will use the lower-level API (`get_generator()`, `retrieve_statutes()`, `verify_answer()`) directly.

---

## 11. scripts/generate_all_reports.py Interface

**Purpose:** Generates consolidated markdown reports from existing result files.  
**File:** `code/scripts/generate_all_reports.py`  
**Phase 7 does not call this.** Phase 7 has its own report generation pipeline.

---

## 12. Generation Model — Exact Identification

| Parameter | Value |
|---|---|
| **Default model name** | `gemini-2.0-flash` |
| **Config generator model** | `gemini-2.5-flash` (pipeline_config.yaml L71) |
| **Config query normalizer** | `gemini-2.0-flash` (pipeline_config.yaml L64) |
| **Provider** | Google (google-generativeai Python SDK) |
| **API key env var** | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| **Temperature** | 0.1 (generator), 0.0 (normalizer) |
| **Max output tokens** | 1024 |
| **Offline fallback** | `gemini-2.0-flash-offline-sim` (keyword-based deterministic simulator) |
| **Mode confirmed by results** | **OFFLINE** — all existing results used offline simulator |

**Evidence:** `results/stage1/stage1_baseline_results.json` L21: `"model_name": "gemini-2.0-flash-offline-sim"`

Phase 7 evaluation will run in the **same offline mode** for reproducibility, unless `GEMINI_API_KEY` is explicitly set in the environment.

---

## Interface Summary for Phase 7 Adapter

The Phase 7 adapter will import these frozen functions (read-only):

```python
# Retrieval
from src.retrieval.search import retrieve_statutes, get_retriever

# Generation
from src.generation.generator import get_generator

# Mapping
from src.mapping.lookup import map_ipc_to_bns, map_bns_to_ipc, map_crpc_to_bnss, map_bnss_to_crpc, ConcordanceLookup

# Verifier
from src.verifier.verifier_pipeline import verify_answer, get_master_verifier

# Evaluation utilities
from src.eval.harness import wilson_score_interval
```

No existing file will be modified. No existing class will be subclassed to change behaviour.
