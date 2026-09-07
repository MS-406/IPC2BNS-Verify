"""
patch_phase6.py — Cleanly updates Phase6_Full_Evaluation_Ablations.ipynb
"""

import os
import json

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
nb_path = os.path.join(root_dir, "Phase6_Full_Evaluation_Ablations.ipynb")

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for cell in nb.get("cells", []):
    if cell.get("cell_type") == "code":
        src = "".join(cell.get("source", []))
        if "MasterEvaluationHarness" in src:
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

with open(nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2, ensure_ascii=False)

print(f"Patched {nb_path} successfully.")
