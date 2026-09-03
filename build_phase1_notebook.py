#!/usr/bin/env python3
"""
build_phase1_notebook.py — Generates Phase1_Mapping_Module.ipynb for Google Colab
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
    "# IPC2BNS-Verify — Phase 1: Deterministic Mapping & Query Normalization\n",
    "\n",
    "This notebook demonstrates and verifies the Phase 1 components:\n",
    "1. **Deterministic Concordance Lookup** (`lookup.py`): 100% exact, non-hallucinatory IPC ↔ BNS mapping.\n",
    "2. **Ambiguity Handling Engine**: Explicit handling of repeals (§124A, §377, §497), splits (§33), and new offences (§111-113).\n",
    "3. **Query Normalizer** (`normalizer.py`): Multi-tier extraction (Regex → Offence Ontology → LLM fallback).\n",
    "4. **Unit Test Suite** (`test_concordance.py`): Full automated pytest verification."
])

# CELL 1: Mount Drive
md(["---\n", "## 1. Mount Google Drive & Environment Setup"])
code([
    "from google.colab import drive\n",
    "drive.mount('/content/drive')\n",
    "\n",
    "import os, sys\n",
    "PROJECT_ROOT = '/content/drive/MyDrive/NLP_rspaper'\n",
    "os.environ['IPC2BNS_PROJECT_ROOT'] = PROJECT_ROOT\n",
    "\n",
    "if os.path.join(PROJECT_ROOT, 'code') not in sys.path:\n",
    "    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'code'))\n",
    "\n",
    "print('Project root:', PROJECT_ROOT)\n",
    "print('Environment configured successfully.')"
])

# CELL 2: Install pytest
md(["---\n", "## 2. Install Test Runner"])
code([
    "!pip install -q pytest\n",
    "print('Pytest ready.')"
])

# CELL 3: Initialize Lookup Engine
md(["---\n", "## 3. Initialize Deterministic Lookup Engine"])
code([
    "from src.mapping.lookup import (\n",
    "    get_lookup_engine,\n",
    "    map_ipc_to_bns,\n",
    "    map_bns_to_ipc,\n",
    "    MappingStatus\n",
    ")\n",
    "\n",
    "engine = get_lookup_engine()\n",
    "print(f'Concordance index loaded successfully from: {engine.concordance_path}')\n",
    "print(f'Total indexed IPC sections: {len(engine.ipc_to_bns_index)}')\n",
    "print(f'Total indexed BNS sections: {len(engine.bns_to_ipc_index)}')\n",
    "print(f'Total valid BNS IDs: {len(engine.get_all_valid_bns_sections())}')"
])

# CELL 4: Forward & Reverse Lookup Demo
md(["---\n", "## 4. Interactive Lookup Demonstration (IPC ↔ BNS)"])
code([
    "test_cases = ['302', '420', '375', '304B', '499', '503']\n",
    "\n",
    "print('--- IPC -> BNS (Forward Lookup) ---')\n",
    "for sec in test_cases:\n",
    "    res = map_ipc_to_bns(sec)\n",
    "    print(f'IPC §{res.query_section:4s} ({res.source_title[:28]:28s}) -> BNS §{res.target_section} [{res.status.value}]')\n",
    "\n",
    "print('\\n--- BNS -> IPC (Reverse Lookup) ---')\n",
    "for sec in ['103', '318', '63', '80', '356', '351']:\n",
    "    res = map_bns_to_ipc(sec)\n",
    "    print(f'BNS §{res.query_section:4s} ({res.source_title[:28]:28s}) -> IPC §{res.target_section} [{res.status.value}]')"
])

# CELL 5: Ambiguity Handling Showcase
md([
    "---\n",
    "## 5. Critical Ambiguity & Edge Case Verification\n",
    "\n",
    "Demonstrating the core novelty: **Ambiguous and non-1:1 provisions are NEVER hallucinated or silently force-mapped.**"
])
code([
    "edge_cases = [\n",
    "    ('124A', 'Sedition (Repealed in BNS, narrower scope in §152)'),\n",
    "    ('377',  'Unnatural Offences (Decriminalized / Struck down)'),\n",
    "    ('497',  'Adultery (Struck down in Joseph Shine v UOI)'),\n",
    "    ('33',   'Act / Omission (Split into BNS §2(1) and §2(25))'),\n",
    "]\n",
    "\n",
    "print('='*75)\n",
    "print('AMBIGUITY & REPEAL VETO DEMONSTRATION')\n",
    "print('='*75)\n",
    "\n",
    "for sec, desc in edge_cases:\n",
    "    res = map_ipc_to_bns(sec)\n",
    "    print(f'\\nQuery: IPC §{sec} ({desc})')\n",
    "    print(f'  Target Section : {res.target_section}')\n",
    "    print(f'  Status         : {res.status.value}')\n",
    "    print(f'  Is Ambiguous   : {res.is_ambiguous}')\n",
    "    print(f'  Matched List   : {res.all_matched_sections}')\n",
    "    print(f'  Legal Notes    : {res.notes}')"
])

# CELL 6: Query Normalizer
md(["---\n", "## 6. Query Normalization Layer (Free-Text → Canonical Section)"])
code([
    "from src.mapping.normalizer import normalize_query\n",
    "\n",
    "natural_queries = [\n",
    "    'What is the new section for cheating in BNS 2023?',\n",
    "    'punishment for murder under the new criminal code',\n",
    "    'What happened to sedition under Section 124A of IPC?',\n",
    "    'Where is dowry death penalized now?',\n",
    "    'BNS section 103 provisions',\n",
    "    'What is the law for defamation?',\n",
    "]\n",
    "\n",
    "print('='*75)\n",
    "print('END-TO-END QUERY NORMALIZATION & LOOKUP PIPELINE')\n",
    "print('='*75)\n",
    "\n",
    "for q in natural_queries:\n",
    "    norm = normalize_query(q)\n",
    "    if norm.extracted_section:\n",
    "        if norm.detected_act == 'BNS':\n",
    "            mapping = map_bns_to_ipc(norm.extracted_section)\n",
    "            dest_label = f'IPC §{mapping.target_section}'\n",
    "        else:\n",
    "            mapping = map_ipc_to_bns(norm.extracted_section)\n",
    "            dest_label = f'BNS §{mapping.target_section}' if mapping.target_section else 'REPEALED / NO DIRECT 1:1 MAP'\n",
    "        print(f'Query: \"{q}\"')\n",
    "        print(f'  -> Extracted: {norm.detected_act} §{norm.extracted_section} (via {norm.method})')\n",
    "        print(f'  -> Mapped To: {dest_label} [{mapping.status.value}]')\n",
    "        print()\n",
    "    else:\n",
    "        print(f'Query: \"{q}\" -> Could not extract canonical section.')"
])

# CELL 7: Run Unit Tests
md(["---\n", "## 7. Run Full Automated Unit Test Suite (`test_concordance.py`)"])
code([
    "test_file = os.path.join(PROJECT_ROOT, 'code/tests/test_concordance.py')\n",
    "!python -m pytest \"{test_file}\" -v --color=yes"
])

# CELL 8: Update Progress
md(["---\n", "## 8. Check Progress against WBS"])
code([
    "!python \"{PROJECT_ROOT}/check_progress.py\" --root \"{PROJECT_ROOT}\" --write-report"
])

# Write out the notebook
out_path = os.path.join(os.path.dirname(__file__), "Phase1_Mapping_Module.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"[OK] Phase1 notebook generated at: {out_path}")
print(f"     Total cells: {len(nb['cells'])}")
