#!/usr/bin/env python3
"""
build_phase6_notebook.py — Generates Phase6_Full_Evaluation_Ablations.ipynb for Google Colab
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
    "# IPC2BNS-Verify — Phase 6: Master Evaluation, Ablation Summary & Final Report\n",
    "\n",
    "This master notebook runs the complete end-to-end evaluation harness across all 4 stages:\n",
    "1. **Stage 1 (Baseline LLM, Closed-Book)**\n",
    "2. **Stage 2 (+RAG Statutory Context)**\n",
    "3. **Stage 3 (+Two-Layer Hard-Constraint Verifier)**\n",
    "4. **Stage 4 (+Verifier + Incremental Refresh)**\n",
    "5. **Master Ablation Summary Table Generation** (`ablation_summary_table.csv`)\n",
    "6. **Full 65-Test Automated Pytest Suite Execution**"
])

# CELL 1: Mount Drive & Fast Local Workspace Sync
md(["---\n", "## 1. Mount Google Drive & Environment Setup"])
code([
    "from google.colab import drive\n",
    "import os, sys, shutil\n",
    "\n",
    "# Mount Drive cleanly\n",
    "drive.mount('/content/drive', force_remount=False)\n",
    "\n",
    "DRIVE_ROOT = '/content/drive/MyDrive/NLP_rspaper'\n",
    "LOCAL_ROOT = '/content/IPC2BNS-Verify'\n",
    "\n",
    "# Copy to Colab local SSD for lightning-fast disk I/O & zero network timeouts\n",
    "if os.path.exists(DRIVE_ROOT):\n",
    "    if os.path.exists(LOCAL_ROOT):\n",
    "        shutil.rmtree(LOCAL_ROOT)\n",
    "    shutil.copytree(DRIVE_ROOT, LOCAL_ROOT, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '.git'))\n",
    "    PROJECT_ROOT = LOCAL_ROOT\n",
    "    print('✅ Synced project from Drive to Colab local SSD:', PROJECT_ROOT)\n",
    "else:\n",
    "    PROJECT_ROOT = DRIVE_ROOT\n",
    "\n",
    "os.environ['IPC2BNS_PROJECT_ROOT'] = PROJECT_ROOT\n",
    "if os.path.join(PROJECT_ROOT, 'code') not in sys.path:\n",
    "    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'code'))\n",
    "\n",
    "print('Environment initialized.')"
])

# CELL 2: Install Dependencies
md(["---\n", "## 2. Dependencies"])
code([
    "!pip install -q pytest pandas tabulate\n",
    "print('Dependencies ready.')"
])

# CELL 3: Run Master Evaluation Harness
md(["---\n", "## 3. Run Master Evaluation Harness Across All 4 Stages"])
code([
    "from src.eval.harness import MasterEvaluationHarness, generate_full_ablation_report\n",
    "\n",
    "results_dir = os.path.join(PROJECT_ROOT, 'results')\n",
    "out_csv = os.path.join(results_dir, 'ablation_summary_table.csv')\n",
    "\n",
    "harness = MasterEvaluationHarness(results_dir)\n",
    "ablation_rows = harness.export_ablation_summary_csv(out_csv)\n",
    "\n",
    "import pandas as pd\n",
    "df = pd.DataFrame(ablation_rows)\n",
    "print('\\n' + '='*85)\n",
    "print('MASTER ABLATION SUMMARY TABLE')\n",
    "print('='*85)\n",
    "display(df)"
])

# CELL 4: Human Review Calibration
md(["---\n", "## 4. Human Expert Calibration Inspection"])
code([
    "human_cal_file = os.path.join(PROJECT_ROOT, 'results/human_review_calibration.csv')\n",
    "cal_df = pd.read_csv(human_cal_file)\n",
    "print('=== DOUBLE-BLIND LEGAL EXPERT CALIBRATION (SAMPLE) ===')\n",
    "display(cal_df[['question_id', 'consensus_verdict', 'inter_annotator_agreement_cohen_kappa', 'verifier_alignment_status']])"
])

# CELL 5: Error Analysis Summary
md(["---\n", "## 5. Qualitative Error Analysis Notes"])
code([
    "error_notes_file = os.path.join(PROJECT_ROOT, 'results/error_analysis_notes.md')\n",
    "with open(error_notes_file, 'r', encoding='utf-8') as f:\n",
    "    print(f.read())"
])

# CELL 6: Run Full Automated Test Suite (65 Unit Tests)
md(["---\n", "## 6. Run Complete Automated Pytest Suite (All 65 Tests)"])
code([
    "test_dir = os.path.join(PROJECT_ROOT, 'code/tests')\n",
    "!python -m pytest \"{test_dir}\" -v --color=yes"
])

# CELL 7: Final WBS Progress Verification (100% Target)
md(["---\n", "## 7. Check Final WBS Project Completion"])
code([
    "!python \"{PROJECT_ROOT}/check_progress.py\" --root \"{PROJECT_ROOT}\" --write-report"
])

# CELL 8: Sync Any Results Back to Google Drive
md(["---\n", "## 8. Sync Results Back to Google Drive"])
code([
    "if PROJECT_ROOT == LOCAL_ROOT:\n",
    "    import shutil\n",
    "    shutil.copy2(os.path.join(PROJECT_ROOT, 'results/ablation_summary_table.csv'), os.path.join(DRIVE_ROOT, 'results/ablation_summary_table.csv'))\n",
    "    shutil.copy2(os.path.join(PROJECT_ROOT, 'results/progress_report.md'), os.path.join(DRIVE_ROOT, 'results/progress_report.md'))\n",
    "    print('✅ Saved latest results to Google Drive successfully.')"
])

# Write out notebook
out_path = os.path.join(os.path.dirname(__file__), "Phase6_Full_Evaluation_Ablations.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"[OK] Updated Phase6 notebook at: {out_path}")
print(f"     Total cells: {len(nb['cells'])}")
