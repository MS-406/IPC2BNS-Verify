"""
build_phase7_notebook.py — Programmatic generator for Phase7_Large_Scale_Evaluation.ipynb
"""

import json
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NOTEBOOK_PATH = os.path.join(PROJECT_ROOT, "Phase7_Large_Scale_Evaluation.ipynb")

cells = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# IPC2BNS-Verify — Phase 7: Large-Scale Benchmark Expansion & Re-Evaluation\n",
            "\n",
            "> **A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions**\n",
            "\n",
            "This notebook provides the complete, interactive evaluation pipeline for **Phase 7**:\n",
            "- **Large-Scale Benchmark**: 1,140 source-grounded questions across 10 statutory categories.\n",
            "- **Open-Source Local Generation**: Powered by Google Flan-T5-base (citable as Chung et al., 2022; no proprietary API requirement).\n",
            "- **Rigorous Constraint Verification**: Closed-set statutory ID validation + substantive penal ingredient grounding + query intent alignment.\n",
            "- **Statistical Significance**: N=60 vs N=1,140 comparison demonstrating 4.5x tighter Wilson 95% confidence intervals.\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 1. Mount Google Drive & Environment Setup\n",
            "Sets up the execution path both for Google Colab and local Python environments."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import os, sys, shutil\n",
            "\n",
            "# Check if running in Google Colab\n",
            "try:\n",
            "    from google.colab import drive\n",
            "    drive.mount('/content/drive', force_remount=False)\n",
            "    DRIVE_ROOT = '/content/drive/MyDrive/NLP_rspaper'\n",
            "    LOCAL_ROOT = '/content/IPC2BNS-Verify'\n",
            "    if os.path.exists(DRIVE_ROOT):\n",
            "        if os.path.exists(LOCAL_ROOT):\n",
            "            shutil.rmtree(LOCAL_ROOT)\n",
            "        shutil.copytree(DRIVE_ROOT, LOCAL_ROOT, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '.git'))\n",
            "        PROJECT_ROOT = LOCAL_ROOT\n",
            "        print('✅ Synced project from Drive to Colab local SSD:', PROJECT_ROOT)\n",
            "    else:\n",
            "        PROJECT_ROOT = DRIVE_ROOT\n",
            "except ImportError:\n",
            "    # Local execution\n",
            "    PROJECT_ROOT = os.path.abspath('.')\n",
            "    DRIVE_ROOT = PROJECT_ROOT\n",
            "    print('✅ Running in local environment:', PROJECT_ROOT)\n",
            "\n",
            "os.environ['IPC2BNS_PROJECT_ROOT'] = PROJECT_ROOT\n",
            "for path in [os.path.join(PROJECT_ROOT, 'code'), PROJECT_ROOT]:\n",
            "    if path not in sys.path:\n",
            "        sys.path.insert(0, path)\n",
            "\n",
            "print('Environment initialized successfully.')\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 2. Dependencies & Open-Source LLM Setup\n",
            "Installs Hugging Face transformers and evaluation tools for the Google Flan-T5 model."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Install dependencies\n",
            "!pip install -q transformers sentencepiece accelerate pandas tabulate matplotlib\n",
            "print('Dependencies verified.')\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 3. Load and Inspect the 1,140-Question Benchmark\n",
            "Inspects category distribution, source ground-truth provenance, and question formulations."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import pandas as pd\n",
            "\n",
            "benchmark_path = os.path.join(PROJECT_ROOT, 'phase7', 'benchmark', 'master_benchmark.csv')\n",
            "df_bench = pd.read_csv(benchmark_path)\n",
            "print(f'Total Benchmark Records: {len(df_bench)}')\n",
            "\n",
            "# Category distribution\n",
            "cat_counts = df_bench['category'].value_counts().reset_index()\n",
            "cat_counts.columns = ['Category', 'Count']\n",
            "cat_counts['Share (%)'] = (cat_counts['Count'] / len(df_bench) * 100).round(1)\n",
            "print('\\n--- Benchmark Category Composition ---')\n",
            "print(cat_counts.to_string(index=False))\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 4. Run Large-Scale Benchmark Evaluation\n",
            "Executes the frozen pipeline over the Phase 7 testbed, measuring retrieval, generation, and verification."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# Run quick evaluation test on sample or full test split\n",
            "import subprocess\n",
            "\n",
            "driver_script = os.path.join(PROJECT_ROOT, 'phase7', 'evaluation', 'run_large_benchmark.py')\n",
            "print('Executing Phase 7 evaluation driver on test split...')\n",
            "ret = subprocess.run([sys.executable, driver_script, '--split', 'test', '--max-questions', '20'], capture_output=True, text=True)\n",
            "print(ret.stdout[-500:] if ret.stdout else ret.stderr)\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 5. Master Retrieval & Generation Results\n",
            "Displays the calculated performance metrics across all 1,140 questions."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "retrieval_table = os.path.join(PROJECT_ROOT, 'phase7', 'results', 'tables', 'retrieval_metrics.csv')\n",
            "if os.path.exists(retrieval_table):\n",
            "    print('--- Retrieval Metrics ---')\n",
            "    print(pd.read_csv(retrieval_table).to_string(index=False))\n",
            "\n",
            "verifier_table = os.path.join(PROJECT_ROOT, 'phase7', 'results', 'tables', 'verifier_metrics.csv')\n",
            "if os.path.exists(verifier_table):\n",
            "    print('\\n--- Verifier Confusion Matrix and Metrics ---')\n",
            "    print(pd.read_csv(verifier_table).to_string(index=False))\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 6. Statistical Significance: Baseline (N=60) vs Large-Scale (N=1,140)\n",
            "Empirically confirms the reduction in confidence interval width (23.7% -> 5.3%)."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "comparison_table = os.path.join(PROJECT_ROOT, 'phase7', 'results', 'tables', 'original_vs_large_scale.csv')\n",
            "if os.path.exists(comparison_table):\n",
            "    print('--- Sample Size Scaling and Wilson 95% Confidence Intervals ---')\n",
            "    print(pd.read_csv(comparison_table).to_string(index=False))\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 7. Publication Visualizations\n",
            "Displays publication-ready figures generated for the research paper."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import matplotlib.pyplot as plt\n",
            "import matplotlib.image as mpimg\n",
            "\n",
            "figures = [\n",
            "    ('fig1_benchmark_composition.png', 'Benchmark Category Composition'),\n",
            "    ('fig2_retrieval_recall_at_k.png', 'Retrieval Recall@K Curve'),\n",
            "    ('fig5_original_vs_largescale.png', 'N=60 vs N=1,140 Confidence Intervals'),\n",
            "]\n",
            "\n",
            "fig_dir = os.path.join(PROJECT_ROOT, 'phase7', 'results', 'figures')\n",
            "for f_name, f_title in figures:\n",
            "    f_path = os.path.join(fig_dir, f_name)\n",
            "    if os.path.exists(f_path):\n",
            "        img = mpimg.imread(f_path)\n",
            "        plt.figure(figsize=(10, 5))\n",
            "        plt.imshow(img)\n",
            "        plt.axis('off')\n",
            "        plt.title(f_title, fontsize=14, pad=10)\n",
            "        plt.show()\n"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "## 8. Synchronize Results Back to Google Drive\n",
            "Persists newly generated tables and reports to `/content/drive/MyDrive/NLP_rspaper`."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "if 'LOCAL_ROOT' in locals() and PROJECT_ROOT == LOCAL_ROOT:\n",
            "    dest_phase7 = os.path.join(DRIVE_ROOT, 'phase7')\n",
            "    if os.path.exists(dest_phase7):\n",
            "        shutil.rmtree(dest_phase7)\n",
            "    shutil.copytree(os.path.join(PROJECT_ROOT, 'phase7'), dest_phase7)\n",
            "    \n",
            "    dest_report = os.path.join(DRIVE_ROOT, 'report')\n",
            "    if os.path.exists(dest_report):\n",
            "        for item in os.listdir(os.path.join(PROJECT_ROOT, 'report')):\n",
            "            s = os.path.join(PROJECT_ROOT, 'report', item)\n",
            "            d = os.path.join(dest_report, item)\n",
            "            if os.path.isfile(s):\n",
            "                shutil.copy2(s, d)\n",
            "    print('✅ Successfully synced all Phase 7 artifacts back to Google Drive.')\n",
            "else:\n",
            "    print('Local run complete. No Drive sync required.')\n"
        ]
    }
]

notebook = {
    "cells": cells,
    "metadata": {
        "language_info": {
            "name": "python",
            "version": "3.11"
        },
        "kernelspec": {
            "name": "python3",
            "display_name": "Python 3"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=2, ensure_ascii=False)

print(f"Generated {NOTEBOOK_PATH} successfully!")
