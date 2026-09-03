#!/usr/bin/env python3
"""
build_phase4_notebook.py — Generates Phase4_Verifier_Layer.ipynb for Google Colab
"""

import json
import os

nb = {
    "cells": [],
    "metadata": {
        "colab": {"provenance": [], "toc_visible": True},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"}
    },
    "nbformat": 4,
    "nbformat_minor": 0
}

def md(lines):
    nb["cells"].append({"cell_type": "markdown", "metadata": {}, "source": lines})

def code(lines):
    nb["cells"].append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines})


# CELL 0: Title
md([
    "# IPC2BNS-Verify — Phase 4: Hard-Constraint Verifier Layer & Stage 3 Ablation\n",
    "\n",
    "This notebook demonstrates the core innovation of the research paper:\n",
    "1. **Layer 1: Hard Citation-Existence Gating** (`citation_check.py`) — Rejects phantom sections.\n",
    "2. **Layer 2: Semantic Entity Grounding** (`entity_grounding.py`) — Flags ungrounded penal claims.\n",
    "3. **Repeal Veto Engine**: Detects and overrides citations of repealed sections (§124A sedition, §497 adultery, §377).\n",
    "4. **Stage 3 Ablation (+Verifier)**: Benchmark run saving to `results/stage3/stage3_verifier_results.json`.\n",
    "5. **Stress-Test Evaluation**: Computes Hallucination Catch Rate and False Positive Rate on adversarial dataset.\n",
    "6. **Full Automated Test Suite**: Executes all 63 unit tests."
])

# CELL 1: Mount Drive
md(["---\n", "## 1. Mount Google Drive & Environment Setup"])
code([
    "from google.colab import drive\n",
    "drive.mount('/content/drive')\n",
    "\n",
    "import os, sys, json\n",
    "PROJECT_ROOT = '/content/drive/MyDrive/NLP_rspaper'\n",
    "os.environ['IPC2BNS_PROJECT_ROOT'] = PROJECT_ROOT\n",
    "\n",
    "if os.path.join(PROJECT_ROOT, 'code') not in sys.path:\n",
    "    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'code'))\n",
    "\n",
    "print('Project Root:', PROJECT_ROOT)\n",
    "print('Environment initialized.')"
])

# CELL 2: Install Pytest
md(["---\n", "## 2. Install Pytest"])
code([
    "!pip install -q pytest\n",
    "print('Pytest ready.')"
])

# CELL 3: Layer 1 Verification Demo
md(["---\n", "## 3. Layer 1 Verification Demo: Closed-Set Citation Gating"])
code([
    "from src.verifier.citation_check import get_citation_verifier\n",
    "\n",
    "verifier = get_citation_verifier()\n",
    "test_citations = [\n",
    "    [{'act': 'BNS', 'section': '103', 'raw': '[BNS §103]'}],       # Valid\n",
    "    [{'act': 'BNS', 'section': '999', 'raw': '[BNS §999]'}],       # Hallucinated\n",
    "    [{'act': 'IPC', 'section': '124A', 'raw': '[IPC §124A]'}],     # Repealed Sedition\n",
    "    [{'act': 'IPC', 'section': '497', 'raw': '[IPC §497]'}],       # Repealed Adultery\n",
    "]\n",
    "\n",
    "for c in test_citations:\n",
    "    res = verifier.verify_citations(c)\n",
    "    print(f'Citation: {c[0][\"raw\"]:12s} -> Valid: {res.is_valid}')\n",
    "    if res.rejection_reasons:\n",
    "        print(f'  Reasons: {res.rejection_reasons}')"
])

# CELL 4: Master Verifier & Repeal Veto Showcase
md(["---\n", "## 4. Master Verifier & Repeal Veto Showcase"])
code([
    "from src.verifier.verifier_pipeline import verify_answer\n",
    "from src.generation.prompt_template import LegalPromptBuilder\n",
    "\n",
    "cases = [\n",
    "    ('Valid Murder Answer', 'Under [BNS §103], whoever commits murder shall be punished with death or imprisonment for life and fine.'),\n",
    "    ('Hallucinated Section', 'Extortion is strictly governed under [BNS §999] with up to 10 years imprisonment.'),\n",
    "    ('Repealed Sedition Claim', 'Sedition remains an offence under [IPC §124A] for inciting disaffection against the Government.'),\n",
    "    ('Ungrounded Penalty', 'Under [BNS §303], simple theft carries mandatory death penalty without parole.')\n",
    "]\n",
    "\n",
    "mock_chunks = [{\n",
    "    'act': 'BNS', 'section_number': '103',\n",
    "    'section_title': 'Punishment for murder',\n",
    "    'section_text': 'Whoever commits murder shall be punished with death or imprisonment for life and fine.'\n",
    "}]\n",
    "\n",
    "for label, text in cases:\n",
    "    print('='*75)\n",
    "    print(f'CASE: {label}')\n",
    "    print('='*75)\n",
    "    cits = LegalPromptBuilder.extract_citations(text)\n",
    "    v_res = verify_answer(text, cits, mock_chunks)\n",
    "    print(f'Verdict       : {v_res.verdict}')\n",
    "    print(f'Is Verified   : {v_res.is_verified}')\n",
    "    print(f'Final Output  :\\n{v_res.verified_output_text}')\n",
    "    if v_res.warnings:\n",
    "        print(f'Warnings      : {v_res.warnings}')\n",
    "    print()"
])

# CELL 5: Run Stage 3 Ablation on Benchmark
md(["---\n", "## 5. Execute Stage 3 (+Verifier) Benchmark Run"])
code([
    "from src.generation.run_stage3 import run_stage3_benchmark, evaluate_verifier_stress_test\n",
    "\n",
    "benchmark_dev = os.path.join(PROJECT_ROOT, 'data/03_benchmark/benchmark_dev.csv')\n",
    "injected_errors = os.path.join(PROJECT_ROOT, 'data/03_benchmark/injected_errors.csv')\n",
    "stage3_out = os.path.join(PROJECT_ROOT, 'results/stage3/stage3_verifier_results.json')\n",
    "\n",
    "stage3_data = run_stage3_benchmark(benchmark_dev, stage3_out)\n",
    "stress_metrics = evaluate_verifier_stress_test(injected_errors)\n",
    "\n",
    "print('\\n' + '='*60)\n",
    "print('STAGE 3 VERIFIER STRESS-TEST METRICS')\n",
    "print('='*60)\n",
    "print(f'Hallucination Catch Rate : {stress_metrics[\"hallucination_catch_rate\"]*100:.1f}%')\n",
    "print(f'False Positive Rate (FPR): {stress_metrics[\"false_positive_rate\"]*100:.1f}%')"
])

# CELL 6: Run Full Automated Test Suite (63 Tests)
md(["---\n", "## 6. Run Full Test Suite (63 Unit Tests)"])
code([
    "test_dir = os.path.join(PROJECT_ROOT, 'code/tests')\n",
    "!python -m pytest \"{test_dir}\" -v --color=yes"
])

# CELL 7: Progress Check
md(["---\n", "## 7. Check WBS Progress"])
code([
    "!python \"{PROJECT_ROOT}/check_progress.py\" --root \"{PROJECT_ROOT}\" --write-report"
])

# Write out notebook
out_path = os.path.join(os.path.dirname(__file__), "Phase4_Verifier_Layer.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"[OK] Phase4 notebook generated at: {out_path}")
print(f"     Total cells: {len(nb['cells'])}")
