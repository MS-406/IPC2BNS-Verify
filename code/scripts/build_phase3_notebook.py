#!/usr/bin/env python3
"""
build_phase3_notebook.py — Generates Phase3_Generation_Layer.ipynb for Google Colab
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
    "# IPC2BNS-Verify — Phase 3: Generation Layer & Stage 1 / Stage 2 Ablation\n",
    "\n",
    "This notebook demonstrates and evaluates the generative answering layer:\n",
    "1. **Legal Prompt Builder** (`prompt_template.py`): Enforces canonical statutory citations `[Act §Section]`.\n",
    "2. **Stage 1 (Baseline LLM, Closed-Book)**: Evaluates baseline generative model without retrieval augmentation.\n",
    "3. **Stage 2 (+RAG Context)**: Evaluates generative model augmented with top-k retrieved bare-act chunks.\n",
    "4. **Citation Extraction & Comparison**: Compares hallucinations in Stage 1 vs. statutory grounding in Stage 2.\n",
    "5. **Automated Unit Tests**: Runs the 55-test pytest suite."
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
    "print('Environment configured.')"
])

# CELL 2: Install Pytest
md(["---\n", "## 2. Install Pytest"])
code([
    "!pip install -q pytest\n",
    "print('Pytest ready.')"
])

# CELL 3: Prompt Construction Showcase
md(["---\n", "## 3. Prompt Construction & Citation Format Demo"])
code([
    "from src.generation.prompt_template import LegalPromptBuilder\n",
    "from src.retrieval.search import retrieve_statutes\n",
    "\n",
    "query = 'What is the punishment for cheating under BNS 2023?'\n",
    "chunks = retrieve_statutes(query, top_k=2, act_filter='BNS')\n",
    "\n",
    "stage2_prompt = LegalPromptBuilder.build_stage2_prompt(query, chunks)\n",
    "print('=== CONSTRUCTED STAGE 2 SYSTEM PROMPT ===')\n",
    "print(stage2_prompt['system_prompt'])\n",
    "print('\\n=== CONSTRUCTED STATUTORY CONTEXT & USER PROMPT ===')\n",
    "print(stage2_prompt['user_prompt'][:500] + '...')"
])

# CELL 4: Run Stage 1 & Stage 2 Comparison
md(["---\n", "## 4. Compare Stage 1 (Baseline) vs Stage 2 (+RAG)"])
code([
    "from src.generation.generator import get_generator\n",
    "\n",
    "generator = get_generator()\n",
    "test_queries = [\n",
    "    'What is the punishment for murder under BNS?',\n",
    "    'Where is dowry death covered in the new law?',\n",
    "    'What happened to sedition under Section 124A IPC in BNS 2023?',\n",
    "]\n",
    "\n",
    "for q in test_queries:\n",
    "    print('='*75)\n",
    "    print(f'QUESTION: {q}')\n",
    "    print('='*75)\n",
    "    \n",
    "    res1 = generator.generate_stage1(q)\n",
    "    print(f'\\n[STAGE 1 — Baseline LLM (No Context)]')\n",
    "    print(f'Answer   : {res1.generated_text}')\n",
    "    print(f'Citations: {[c[\"raw\"] for c in res1.citations]}')\n",
    "    \n",
    "    res2 = generator.generate_stage2(q, top_k=2)\n",
    "    print(f'\\n[STAGE 2 — +RAG (Retrieved Statutory Context)]')\n",
    "    print(f'Answer   : {res2.generated_text}')\n",
    "    print(f'Citations: {[c[\"raw\"] for c in res2.citations]}')\n",
    "    print()"
])

# CELL 5: Run Full Benchmark Ablations
md(["---\n", "## 5. Execute Full Benchmark Ablations (Stage 1 & Stage 2)"])
code([
    "from src.generation.run_ablations import run_stage1_ablation, run_stage2_ablation\n",
    "\n",
    "benchmark_dev = os.path.join(PROJECT_ROOT, 'data/03_benchmark/benchmark_dev.csv')\n",
    "stage1_out = os.path.join(PROJECT_ROOT, 'results/stage1/stage1_baseline_results.json')\n",
    "stage2_out = os.path.join(PROJECT_ROOT, 'results/stage2/stage2_rag_results.json')\n",
    "\n",
    "run_stage1_ablation(benchmark_dev, stage1_out)\n",
    "run_stage2_ablation(benchmark_dev, stage2_out)\n",
    "\n",
    "print('\\nBoth Stage 1 and Stage 2 ablation results generated successfully.')"
])

# CELL 6: Inspect Ablation Results
md(["---\n", "## 6. Inspect Results Summary"])
code([
    "with open(stage1_out, 'r') as f:\n",
    "    s1_data = json.load(f)\n",
    "with open(stage2_out, 'r') as f:\n",
    "    s2_data = json.load(f)\n",
    "\n",
    "print(f'Stage 1 queries completed: {len(s1_data[\"results\"])}')\n",
    "print(f'Stage 2 queries completed: {len(s2_data[\"results\"])}')\n",
    "\n",
    "# Sample output comparison\n",
    "s1_sample = s1_data['results'][0]\n",
    "s2_sample = s2_data['results'][0]\n",
    "print('\\n--- Sample Query Comparison ---')\n",
    "print(f'Query        : {s1_sample[\"query_text\"]}')\n",
    "print(f'Ground Truth : {s1_sample[\"ground_truth_sections\"]} - {s1_sample[\"ground_truth_answer\"][:80]}...')\n",
    "print(f'Stage 1 Cited: {s1_sample[\"cited_sections\"]}')\n",
    "print(f'Stage 2 Cited: {s2_sample[\"cited_sections\"]}')"
])

# CELL 7: Run Unit Tests
md(["---\n", "## 7. Run Full Automated Test Suite (55 Tests)"])
code([
    "test_dir = os.path.join(PROJECT_ROOT, 'code/tests')\n",
    "!python -m pytest \"{test_dir}\" -v --color=yes"
])

# CELL 8: WBS Progress Check
md(["---\n", "## 8. Check Progress against WBS"])
code([
    "!python \"{PROJECT_ROOT}/check_progress.py\" --root \"{PROJECT_ROOT}\" --write-report"
])

# Write out notebook
out_path = os.path.join(os.path.dirname(__file__), "Phase3_Generation_Layer.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"[OK] Phase3 notebook generated at: {out_path}")
print(f"     Total cells: {len(nb['cells'])}")
