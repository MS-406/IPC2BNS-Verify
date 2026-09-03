#!/usr/bin/env python3
"""
build_notebook.py
Generates Step1_Setup.ipynb for Google Colab.
All paths target /content/drive/MyDrive/NLP_rspaper/
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
    nb["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": lines
    })

def code(lines):
    nb["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines
    })


# =====================================================================
# CELL 0 - Title
# =====================================================================
md([
    "# IPC2BNS-Verify — STEP 1: Project Setup\n",
    "\n",
    "**Run this notebook ONCE in your first Colab session.**  \n",
    "It will:\n",
    "1. Mount Google Drive\n",
    "2. Create the full project directory structure under `/content/drive/MyDrive/NLP_rspaper/`\n",
    "3. Copy all planning docs into `docs/`\n",
    "4. Write `check_progress.py` into the project root\n",
    "5. Create `checkpoints/progress_state.json` with initial state\n",
    "6. Verify the setup by running `check_progress.py`"
])

# =====================================================================
# CELL 1 - Mount header
# =====================================================================
md(["---\n", "## 1. Mount Google Drive"])

# =====================================================================
# CELL 2 - Mount code
# =====================================================================
code([
    "from google.colab import drive\n",
    "drive.mount('/content/drive')\n",
    "print('✅ Google Drive mounted successfully.')"
])

# =====================================================================
# CELL 3 - Dir structure header
# =====================================================================
md([
    "---\n",
    "## 2. Define Project Root & Create Directory Structure\n",
    "\n",
    "This matches the Data Management Plan exactly."
])

# =====================================================================
# CELL 4 - Create directories
# =====================================================================
code([
    "import os\n",
    "\n",
    "# ── Project root on Google Drive ──────────────────────────────────\n",
    "PROJECT_ROOT = '/content/drive/MyDrive/NLP_rspaper'\n",
    "\n",
    "# ── Full directory tree (from Data Management Plan) ───────────────\n",
    "DIRECTORIES = [\n",
    "    # code/\n",
    "    'code/src/mapping',\n",
    "    'code/src/ingestion',\n",
    "    'code/src/retrieval',\n",
    "    'code/src/generation',\n",
    "    'code/src/verifier',\n",
    "    'code/src/refresh',\n",
    "    'code/src/eval',\n",
    "    'code/tests',\n",
    "    'code/configs',\n",
    "    # data/\n",
    "    'data/00_raw/india_code',\n",
    "    'data/00_raw/concordance_source_pdfs',\n",
    "    'data/01_cleaned',\n",
    "    'data/02_ground_truth',\n",
    "    'data/03_benchmark',\n",
    "    'data/04_refresh_sim',\n",
    "    'data/05_embeddings_index',\n",
    "    # results/\n",
    "    'results/stage1',\n",
    "    'results/stage2',\n",
    "    'results/stage3',\n",
    "    'results/stage4',\n",
    "    # docs, report, checkpoints\n",
    "    'docs',\n",
    "    'report',\n",
    "    'checkpoints',\n",
    "]\n",
    "\n",
    "print(f'📁 Creating project structure under: {PROJECT_ROOT}')\n",
    "print()\n",
    "\n",
    "for d in DIRECTORIES:\n",
    "    full_path = os.path.join(PROJECT_ROOT, d)\n",
    "    os.makedirs(full_path, exist_ok=True)\n",
    "    print(f'  ✅ {d}/')\n",
    "\n",
    "print(f'\\n🎉 All {len(DIRECTORIES)} directories created successfully.')"
])

# =====================================================================
# CELL 5 - Docs header
# =====================================================================
md([
    "---\n",
    "## 3. Copy Planning Docs to `docs/`\n",
    "\n",
    "Searches for the docs in the Drive root or `required_doc_files/` subfolder.  \n",
    "If not found, use the upload widget in the next cell."
])

# =====================================================================
# CELL 6 - Copy docs
# =====================================================================
code([
    "import shutil\n",
    "\n",
    "PLANNING_DOCS = [\n",
    "    'IPC2BNS-Verify_Research_Proposal.md',\n",
    "    'IPC2BNS-Verify_Technical_Pipeline.md',\n",
    "    'IPC2BNS-Verify_Data_Management_Plan.md',\n",
    "    'IPC2BNS-Verify_Ground_Truth_Concordance_Runbook.md',\n",
    "    'IPC2BNS-Verify_Task_Board_WBS.md',\n",
    "    'IPC2BNS-Verify_Project_Management_Guide.md',\n",
    "]\n",
    "\n",
    "# Places to look for the docs\n",
    "SEARCH_DIRS = [\n",
    "    PROJECT_ROOT,\n",
    "    f'{PROJECT_ROOT}/required_doc_files',\n",
    "    '/content',\n",
    "]\n",
    "\n",
    "docs_dir = os.path.join(PROJECT_ROOT, 'docs')\n",
    "found_count = 0\n",
    "\n",
    "for doc_name in PLANNING_DOCS:\n",
    "    dest = os.path.join(docs_dir, doc_name)\n",
    "    if os.path.exists(dest):\n",
    "        print(f'  ⏭️  {doc_name} — already in docs/')\n",
    "        found_count += 1\n",
    "        continue\n",
    "\n",
    "    source = None\n",
    "    for search_dir in SEARCH_DIRS:\n",
    "        candidate = os.path.join(search_dir, doc_name)\n",
    "        if os.path.exists(candidate):\n",
    "            source = candidate\n",
    "            break\n",
    "\n",
    "    if source:\n",
    "        shutil.copy2(source, dest)\n",
    "        print(f'  ✅ {doc_name} — copied from {os.path.dirname(source)}')\n",
    "        found_count += 1\n",
    "    else:\n",
    "        print(f'  ❌ {doc_name} — NOT FOUND. Upload manually.')\n",
    "\n",
    "print(f'\\n📄 {found_count}/{len(PLANNING_DOCS)} planning docs in place.')\n",
    "\n",
    "if found_count < len(PLANNING_DOCS):\n",
    "    print('\\n⚠️  Missing docs — upload them via the next cell or to Drive directly.')"
])

# =====================================================================
# CELL 7 - Manual upload header
# =====================================================================
md(["### 3b. Manual upload (only if docs are missing above)"])

# =====================================================================
# CELL 8 - Manual upload (commented)
# =====================================================================
code([
    "# Uncomment and run this cell ONLY if docs were not found above.\n",
    "\n",
    "# from google.colab import files\n",
    "# uploaded = files.upload()  # select all 6 .md files\n",
    "#\n",
    "# docs_dir = os.path.join(PROJECT_ROOT, 'docs')\n",
    "# for filename, content in uploaded.items():\n",
    "#     dest = os.path.join(docs_dir, filename)\n",
    "#     with open(dest, 'wb') as f:\n",
    "#         f.write(content)\n",
    "#     print(f'  Uploaded → {dest}')\n",
    "#\n",
    "# print('Done. Re-run cell 3 to verify.')"
])

# =====================================================================
# CELL 9 - check_progress header
# =====================================================================
md(["---\n", "## 4. Write `check_progress.py` to Project Root"])

# =====================================================================
# CELL 10 - Write check_progress.py
# Read the actual file content and embed it
# =====================================================================
cp_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "check_progress.py"
)
with open(cp_path, "r", encoding="utf-8") as f:
    cp_content = f.read()

# We embed the check_progress.py content using a triple-quote string
code([
    "# Read check_progress.py content and write it to the project root\n",
    "\n",
    "check_progress_code = " + repr(cp_content) + "\n",
    "\n",
    "dest_path = os.path.join(PROJECT_ROOT, 'check_progress.py')\n",
    "with open(dest_path, 'w') as f:\n",
    "    f.write(check_progress_code)\n",
    "\n",
    "print(f'✅ check_progress.py written to {dest_path}')"
])

# =====================================================================
# CELL 11 - Checkpoint header
# =====================================================================
md(["---\n", "## 5. Create Initial Checkpoint (`progress_state.json`)"])

# =====================================================================
# CELL 12 - Create checkpoint
# =====================================================================
code([
    "import json\n",
    "from datetime import datetime\n",
    "\n",
    "checkpoint_path = os.path.join(PROJECT_ROOT, 'checkpoints', 'progress_state.json')\n",
    "\n",
    "initial_state = {\n",
    "    'current_phase': 0,\n",
    "    'completed_phases': [],\n",
    "    'last_updated': datetime.now().isoformat(timespec='seconds'),\n",
    "    'next_action': 'Begin Phase 0 setup',\n",
    "    'notes': 'Project initialized. Directory structure created. Planning docs copied to docs/.'\n",
    "}\n",
    "\n",
    "with open(checkpoint_path, 'w') as f:\n",
    "    json.dump(initial_state, f, indent=2)\n",
    "\n",
    "print(f'✅ Checkpoint initialized at: {checkpoint_path}')\n",
    "print()\n",
    "print(json.dumps(initial_state, indent=2))"
])

# =====================================================================
# CELL 13 - Run check header
# =====================================================================
md(["---\n", "## 6. Verify Setup — Run `check_progress.py`"])

# =====================================================================
# CELL 14 - Run check_progress
# =====================================================================
code([
    "import subprocess\n",
    "\n",
    "result = subprocess.run(\n",
    "    ['python', os.path.join(PROJECT_ROOT, 'check_progress.py'),\n",
    "     '--root', PROJECT_ROOT, '--write-report'],\n",
    "    capture_output=True, text=True\n",
    ")\n",
    "print(result.stdout)\n",
    "if result.stderr:\n",
    "    print('STDERR:', result.stderr)"
])

# =====================================================================
# CELL 15 - Tree header
# =====================================================================
md(["---\n", "## 7. Visual Directory Tree"])

# =====================================================================
# CELL 16 - Print tree
# =====================================================================
code([
    "def print_tree(root, prefix='', max_depth=3, current_depth=0):\n",
    "    \"\"\"Print directory tree up to max_depth.\"\"\"\n",
    "    if current_depth >= max_depth:\n",
    "        return\n",
    "    try:\n",
    "        entries = sorted(os.listdir(root))\n",
    "    except PermissionError:\n",
    "        return\n",
    "    dirs = [e for e in entries if os.path.isdir(os.path.join(root, e))]\n",
    "    files = [e for e in entries if os.path.isfile(os.path.join(root, e))]\n",
    "    for f in files:\n",
    "        print(f'{prefix}📄 {f}')\n",
    "    for i, d in enumerate(dirs):\n",
    "        is_last = (i == len(dirs) - 1)\n",
    "        connector = '└── ' if is_last else '├── '\n",
    "        print(f'{prefix}{connector}📁 {d}/')\n",
    "        extension = '    ' if is_last else '│   '\n",
    "        print_tree(os.path.join(root, d), prefix + extension, max_depth, current_depth + 1)\n",
    "\n",
    "print(f'📁 NLP_rspaper/')\n",
    "print_tree(PROJECT_ROOT, '  ')"
])

# =====================================================================
# CELL 17 - Done
# =====================================================================
md([
    "---\n",
    "## ✅ Setup Complete!\n",
    "\n",
    "**What was done:**\n",
    "1. ✅ Google Drive mounted\n",
    "2. ✅ Full directory structure created (matches Data Management Plan)\n",
    "3. ✅ Planning docs copied to `docs/`\n",
    "4. ✅ `check_progress.py` placed at project root\n",
    "5. ✅ `checkpoints/progress_state.json` initialized\n",
    "6. ✅ Progress report generated\n",
    "\n",
    "---\n",
    "\n",
    "### What's Next: Phase 0 — Environment & Ground Truth Setup\n",
    "\n",
    "Phase 0 will produce:\n",
    "- **Config system** → `code/configs/pipeline_config.yaml`\n",
    "- **India Code raw text** → `data/00_raw/india_code/` (IPC 1860 + BNS 2023 bare-act text)\n",
    "- **Concordance source PDFs** → `data/00_raw/concordance_source_pdfs/`\n",
    "- **Ground-truth concordance table** → `data/02_ground_truth/concordance_v1.csv`\n",
    "\n",
    "**⏳ Waiting for your confirmation before starting Phase 0.**"
])


# =====================================================================
# Write the notebook
# =====================================================================
out_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "Step1_Setup.ipynb"
)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)

print(f"[OK] Notebook written to: {out_path}")
print(f"     Total cells: {len(nb['cells'])}")
