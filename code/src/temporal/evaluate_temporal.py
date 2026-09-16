import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.temporal.savings_clause_engine import SavingsClauseEngine

TEST_SUITE: List[Dict[str, Any]] = [
    # 1. Pure Legacy (Pre-July 2024 Incident + Pre-July 2024 FIR/Trial)
    {
        "id": "T01",
        "category": "pure_legacy",
        "query": "The theft took place on 12 January 2024 and the FIR was lodged on 14 January 2024. What penal section and procedure apply?",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CRPC_1973",
        "expected_split": False
    },
    {
        "id": "T02",
        "category": "pure_legacy",
        "query": "A riot occurred on 20 February 2024 with trial ongoing since March 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CRPC_1973",
        "expected_split": False
    },
    {
        "id": "T03",
        "category": "pure_legacy",
        "query": "Cheating under Section 420 committed on 15 May 2024, chargesheet submitted on 25 June 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CRPC_1973",
        "expected_split": False
    },
    {
        "id": "T04",
        "category": "pure_legacy",
        "query": "Murder case where incident happened on 10 October 2023, FIR filed on 11 October 2023.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CRPC_1973",
        "expected_split": False
    },
    {
        "id": "T05",
        "category": "pure_legacy",
        "query": "Criminal trespass committed in December 2023 and police inquiry initiated in January 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CRPC_1973",
        "expected_split": False
    },

    # 2. Transitional (Pre-July 2024 Incident + Post-July 2024 FIR)
    {
        "id": "T06",
        "category": "transitional_delayed_fir",
        "query": "A dowry harassment incident occurred on 15 May 2024, but the victim filed the police FIR on 20 July 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T07",
        "category": "transitional_delayed_fir",
        "query": "Financial fraud committed in April 2024, complaint lodged on 10 August 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T08",
        "category": "transitional_delayed_fir",
        "query": "Assault on 28 June 2024, FIR registered on 5 July 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T09",
        "category": "transitional_delayed_fir",
        "query": "Land grab crime committed on 1 January 2024, private complaint filed on 15 September 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T10",
        "category": "transitional_delayed_fir",
        "query": "Medical negligence offence committed on 10 March 2024, FIR registered on 1 August 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },

    # 3. Pure Modern (Post-July 2024 Incident)
    {
        "id": "T11",
        "category": "pure_modern",
        "query": "A robbery was committed on 15 July 2024 and FIR was registered on 16 July 2024.",
        "expected_substantive": "BNS_2023",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T12",
        "category": "pure_modern",
        "query": "Organized crime incident occurred on 10 August 2024.",
        "expected_substantive": "BNS_2023",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T13",
        "category": "pure_modern",
        "query": "Snatching and assault committed on 5 September 2024, FIR registered on 6 September 2024.",
        "expected_substantive": "BNS_2023",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T14",
        "category": "pure_modern",
        "query": "Cyber fraud committed on 1 December 2024.",
        "expected_substantive": "BNS_2023",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },
    {
        "id": "T15",
        "category": "pure_modern",
        "query": "Hit and run offence occurring on 20 October 2024 with chargesheet filed on 10 November 2024.",
        "expected_substantive": "BNS_2023",
        "expected_procedural": "BNSS_2023",
        "expected_split": False
    },

    # 4. High Court Split: Post-July Appeals for Pre-July Convictions
    {
        "id": "T16",
        "category": "hc_split_appeal",
        "query": "Trial court convicted the accused in April 2024. Filing a criminal appeal in August 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CONTESTED_HIGH_COURT_SPLIT",
        "expected_split": True
    },
    {
        "id": "T17",
        "category": "hc_split_appeal",
        "query": "In Kerala High Court, filing an appeal in September 2024 against an order passed in March 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": True
    },
    {
        "id": "T18",
        "category": "hc_split_appeal",
        "query": "In Punjab and Haryana High Court, filing an appeal in October 2024 against a conviction rendered in February 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CrPC_1973",
        "expected_split": True
    },
    {
        "id": "T19",
        "category": "hc_split_appeal",
        "query": "In Delhi High Court, petition filed in November 2024 challenging a trial judgment from May 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": True
    },
    {
        "id": "T20",
        "category": "hc_split_appeal",
        "query": "Revision petition filed on 15 July 2024 against an interlocutory order passed on 10 June 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CONTESTED_HIGH_COURT_SPLIT",
        "expected_split": True
    },

    # 5. High Court Split: Anticipatory Bail Post-July for Pre-July Offence
    {
        "id": "T21",
        "category": "hc_split_bail",
        "query": "Offence committed on 20 May 2024. Anticipatory bail application filed on 10 July 2024 under Section 438 or 482?",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CONTESTED_HIGH_COURT_SPLIT",
        "expected_split": True
    },
    {
        "id": "T22",
        "category": "hc_split_bail",
        "query": "In Rajasthan High Court, anticipatory bail filed on 15 August 2024 for an incident occurring on 10 June 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "BNSS_2023",
        "expected_split": True
    },
    {
        "id": "T23",
        "category": "hc_split_bail",
        "query": "In Bombay High Court, regular bail application filed in August 2024 where FIR was lodged on 15 March 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CrPC_1973_OR_BNSS_2023 (Defect Curable)",
        "expected_split": True
    },
    {
        "id": "T24",
        "category": "hc_split_bail",
        "query": "Bail application moved on 25 July 2024 for offence that took place on 28 June 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CONTESTED_HIGH_COURT_SPLIT",
        "expected_split": True
    },
    {
        "id": "T25",
        "category": "hc_split_bail",
        "query": "Anticipatory bail petition filed on 1 August 2024 for an alleged cheque bounce crime committed in April 2024.",
        "expected_substantive": "IPC_1860",
        "expected_procedural": "CONTESTED_HIGH_COURT_SPLIT",
        "expected_split": True
    }
]

def run_evaluation():
    engine = SavingsClauseEngine()
    results = []
    correct_substantive = 0
    correct_procedural = 0
    correct_split = 0
    total = len(TEST_SUITE)

    for item in TEST_SUITE:
        res = engine.resolve(item["query"])
        
        # Check substantive
        sub_match = res.substantive_code.upper() == item["expected_substantive"].upper()
        if sub_match:
            correct_substantive += 1

        # Check procedural
        proc_match = False
        if res.procedural_code.upper() == item["expected_procedural"].upper():
            proc_match = True
        elif item["expected_procedural"].upper() in res.procedural_code.upper():
            proc_match = True
        if proc_match:
            correct_procedural += 1

        # Check split detection
        split_match = res.is_contested_split == item["expected_split"]
        if split_match:
            correct_split += 1

        results.append({
            "id": item["id"],
            "category": item["category"],
            "query": item["query"],
            "substantive": {
                "pred": res.substantive_code,
                "expected": item["expected_substantive"],
                "match": sub_match
            },
            "procedural": {
                "pred": res.procedural_code,
                "expected": item["expected_procedural"],
                "match": proc_match
            },
            "split": {
                "pred_is_split": res.is_contested_split,
                "expected_is_split": item["expected_split"],
                "match": split_match
            }
        })

    metrics = {
        "total_test_cases": total,
        "substantive_accuracy": correct_substantive / total,
        "procedural_accuracy": correct_procedural / total,
        "split_detection_accuracy": correct_split / total,
        "overall_perfect_accuracy": sum(1 for r in results if r["substantive"]["match"] and r["procedural"]["match"] and r["split"]["match"]) / total,
        "results": results
    }

    out_dir = ROOT_DIR.parent / "results" / "v2_temporal_eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "phase1_temporal_accuracy.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"=== Phase 1 Temporal Evaluation Completed ===")
    print(f"Total Cases: {total}")
    print(f"Substantive Accuracy: {metrics['substantive_accuracy'] * 100:.1f}%")
    print(f"Procedural Accuracy:  {metrics['procedural_accuracy'] * 100:.1f}%")
    print(f"Split Detection:      {metrics['split_detection_accuracy'] * 100:.1f}%")
    print(f"Overall Accuracy:     {metrics['overall_perfect_accuracy'] * 100:.1f}%")
    print(f"Metrics saved to: {out_file}")

if __name__ == "__main__":
    run_evaluation()
