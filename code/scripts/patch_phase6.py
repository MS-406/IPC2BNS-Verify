"""
patch_phase6.py — Comprehensive patch for Phase6_Full_Evaluation_Ablations.ipynb
"""

import os
import json

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
nb_path = os.path.join(root_dir, "Phase6_Full_Evaluation_Ablations.ipynb")

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for i, cell in enumerate(nb.get("cells", [])):
    if cell.get("cell_type") == "code":
        src = "".join(cell.get("source", []))
        
        # Cell 2: Setup
        if "drive.mount" in src:
            cell["source"] = [
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
                "code_dir = os.path.join(PROJECT_ROOT, 'code')\n",
                "if code_dir not in sys.path:\n",
                "    sys.path.insert(0, code_dir)\n",
                "\n",
                "print('Environment initialized.')\n"
            ]

        # Cell 6 (Code cell 3): Master Evaluation Harness
        elif "MasterEvaluationHarness" in src:
            cell["source"] = [
                "import os, sys, importlib\n",
                "importlib.invalidate_caches()\n",
                "\n",
                "# Ensure code directory is at top of sys.path\n",
                "code_dir = os.path.join(PROJECT_ROOT, 'code')\n",
                "if code_dir not in sys.path:\n",
                "    sys.path.insert(0, code_dir)\n",
                "\n",
                "# Force fresh reload if already loaded in this runtime session\n",
                "for mod in ['src.eval.harness', 'src.eval', 'src']:\n",
                "    if mod in sys.modules:\n",
                "        try:\n",
                "            importlib.reload(sys.modules[mod])\n",
                "        except Exception:\n",
                "            pass\n",
                "\n",
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
                "display(df)\n"
            ]

        # Cell 8 (Code cell 4): Human Expert Calibration
        elif "human_review_calibration.csv" in src:
            cell["source"] = [
                "import os\n",
                "import pandas as pd\n",
                "\n",
                "human_cal_file = os.path.join(PROJECT_ROOT, 'results/human_review_calibration.csv')\n",
                "cal_df = pd.read_csv(human_cal_file)\n",
                "print('=== DOUBLE-BLIND LEGAL EXPERT CALIBRATION (SAMPLE) ===')\n",
                "# Select relevant calibration columns present in the dataset\n",
                "desired_cols = ['question_id', 'legal_expert_1_score', 'legal_expert_1_verdict', 'legal_expert_2_score', 'legal_expert_2_verdict', 'consensus_verdict', 'verifier_alignment_status']\n",
                "display_cols = [c for c in desired_cols if c in cal_df.columns]\n",
                "display(cal_df[display_cols].head(10))\n"
            ]

        # Cell 12 (Code cell 6): Pytest execution
        elif "pytest" in src and "code/tests" in src:
            cell["source"] = [
                "import os\n",
                "test_dir = os.path.join(PROJECT_ROOT, 'code/tests')\n",
                "code_dir = os.path.join(PROJECT_ROOT, 'code')\n",
                "# Run pytest with code directory in PYTHONPATH\n",
                "!PYTHONPATH=\"{code_dir}\" python -m pytest \"{test_dir}\" -v --color=yes\n"
            ]

        # Cell 16 (Code cell 8): Sync back to drive
        elif "Saved latest results to Google Drive" in src:
            cell["source"] = [
                "if PROJECT_ROOT == LOCAL_ROOT:\n",
                "    import shutil, os\n",
                "    os.makedirs(os.path.join(DRIVE_ROOT, 'results'), exist_ok=True)\n",
                "    for f in ['ablation_summary_table.csv', 'progress_report.md']:\n",
                "        src_f = os.path.join(PROJECT_ROOT, 'results', f)\n",
                "        if os.path.exists(src_f):\n",
                "            shutil.copy2(src_f, os.path.join(DRIVE_ROOT, 'results', f))\n",
                "    print('✅ Saved latest results to Google Drive successfully.')\n"
            ]

with open(nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2, ensure_ascii=False)

print(f"Patched {nb_path} successfully.")
