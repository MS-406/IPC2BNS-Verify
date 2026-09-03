"""
build_benchmark.py — Builds Benchmark Datasets for IPC2BNS-Verify

Produces:
1. data/03_benchmark/benchmark_dev.csv (Development set for tuning)
2. data/03_benchmark/benchmark_test.csv (Held-out test set for final reporting)
3. data/03_benchmark/provenance.md (Documentation of question sources and distribution)

Schema for benchmark CSVs:
- question_id: unique ID (e.g. "DEV_001", "TEST_001")
- query_text: natural language question
- query_type: "transition" | "ingredient_punishment" | "ambiguous_repeal" | "new_offence" | "split_merged"
- source_act: "IPC" | "BNS" | "MIXED"
- target_act: "BNS" | "IPC"
- ground_truth_sections: comma-separated canonical section numbers (e.g. "103", "106(2)", "124A")
- ground_truth_answer: canonical authoritative answer
- is_ambiguous: boolean
- provenance: "hand_curated" | "adapted_ilsi" | "statute_qa"
"""

import os
import csv
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_benchmark")

DEV_QUESTIONS = [
    # 1. Direct Transition
    {
        "query_text": "What is the new section for murder under the Bharatiya Nyaya Sanhita, 2023?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "103",
        "ground_truth_answer": "Under BNS 2023, punishment for murder is governed by Section 103 (previously Section 302 of IPC 1860).",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "Which section in BNS corresponds to IPC Section 420 for cheating?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "318",
        "ground_truth_answer": "IPC Section 420 (cheating and dishonestly inducing delivery of property) corresponds to Section 318(4) of BNS 2023.",
        "is_ambiguous": False, "provenance": "adapted_ilsi"
    },
    {
        "query_text": "What is the equivalent section for theft (IPC 378 / 379) in the new criminal law?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "303",
        "ground_truth_answer": "Theft is defined and penalized under Section 303 of BNS 2023 (formerly Sections 378 and 379 of IPC).",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "Where is dowry death covered in BNS 2023?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "80",
        "ground_truth_answer": "Dowry death is governed by Section 80 of BNS 2023 (previously Section 304B of IPC).",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "Which section in IPC corresponds to Section 100 of BNS?",
        "query_type": "transition", "source_act": "BNS", "target_act": "IPC",
        "ground_truth_sections": "299",
        "ground_truth_answer": "Section 100 of BNS corresponds to Section 299 of IPC 1860 (culpable homicide).",
        "is_ambiguous": False, "provenance": "statute_qa"
    },

    # 2. Ingredient & Punishment
    {
        "query_text": "What is the punishment for causing death by rash or negligent driving if the driver flees the scene without reporting under BNS?",
        "query_type": "ingredient_punishment", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "106(2)",
        "ground_truth_answer": "Under Section 106(2) of BNS 2023, causing death by rash and negligent driving and escaping without reporting to police or a Magistrate carries imprisonment up to ten years and fine.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "What are the essential ingredients of rape under Section 63 of BNS 2023?",
        "query_type": "ingredient_punishment", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "63",
        "ground_truth_answer": "Section 63 of BNS 2023 defines rape as non-consensual penetration of penis, insertion of objects, manipulation of body parts to cause penetration, or applying mouth to genital/anal orifices.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "What is the penalty for defamation under Section 356 of BNS?",
        "query_type": "ingredient_punishment", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "356",
        "ground_truth_answer": "Under Section 356 of BNS 2023, defamation is punishable with simple imprisonment up to two years, fine, or community service.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "Can community service be awarded for petty theft of stolen property under BNS?",
        "query_type": "ingredient_punishment", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "303(2)",
        "ground_truth_answer": "Yes, under the proviso to Section 303(2) of BNS 2023, if the stolen property value is less than 5,000 rupees and the offender is a first-time offender, community service may be awarded.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },

    # 3. Ambiguity & Repeals
    {
        "query_text": "What is the exact equivalent section of IPC Section 124A (Sedition) in BNS 2023?",
        "query_type": "ambiguous_repeal", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "124A",
        "ground_truth_answer": "IPC Section 124A (Sedition) has been repealed and has NO direct 1:1 equivalent in BNS 2023. Section 152 of BNS addresses acts endangering the sovereignty, unity, and integrity of India with a narrower, distinct legal scope.",
        "is_ambiguous": True, "provenance": "hand_curated"
    },
    {
        "query_text": "Is adultery under IPC 497 punishable under the new Bharatiya Nyaya Sanhita?",
        "query_type": "ambiguous_repeal", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "497",
        "ground_truth_answer": "No. IPC Section 497 was struck down as unconstitutional by the Supreme Court in Joseph Shine v. Union of India (2018) and was omitted completely from BNS 2023.",
        "is_ambiguous": True, "provenance": "hand_curated"
    },
    {
        "query_text": "What happened to Section 377 of IPC in BNS 2023?",
        "query_type": "ambiguous_repeal", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "377",
        "ground_truth_answer": "IPC Section 377 (unnatural offences) was decriminalized in part by Navtej Singh Johar v. Union of India (2018) and has not been carried forward as an offence in BNS 2023.",
        "is_ambiguous": True, "provenance": "hand_curated"
    },

    # 4. New Offences in BNS
    {
        "query_text": "Which section in BNS 2023 penalizes sexual intercourse by deceitful means or false promise of marriage?",
        "query_type": "new_offence", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "69",
        "ground_truth_answer": "Section 69 of BNS 2023 is a new provision that penalizes sexual intercourse by employing deceitful means or false promise to marry with imprisonment up to ten years and fine.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "How does BNS 2023 define and penalize organised crime?",
        "query_type": "new_offence", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "111",
        "ground_truth_answer": "Section 111 of BNS 2023 introduces a comprehensive definition for organised crime syndicates, prescribing death or life imprisonment if death results, and minimum 5 years otherwise.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "Under what section are terrorist acts defined in BNS 2023?",
        "query_type": "new_offence", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "113",
        "ground_truth_answer": "Terrorist acts are defined and penalized under Section 113 of BNS 2023.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },

    # 5. Splits and Mergers
    {
        "query_text": "How was IPC Section 33 (Act and Omission) re-organized in BNS 2023?",
        "query_type": "split_merged", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "33, 2(1), 2(25)",
        "ground_truth_answer": "IPC Section 33 defined 'act' and 'omission' together. In BNS 2023, it is split into two separate sub-clauses under Section 2: Section 2(1) for 'act' and Section 2(25) for 'omission'.",
        "is_ambiguous": True, "provenance": "hand_curated"
    },
    {
        "query_text": "What sections govern criminal conspiracy in BNS 2023 compared to IPC 120A and 120B?",
        "query_type": "split_merged", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "120A, 120B, 61",
        "ground_truth_answer": "IPC Sections 120A (definition) and 120B (punishment) for criminal conspiracy have been merged into a single Section 61 in BNS 2023.",
        "is_ambiguous": True, "provenance": "hand_curated"
    }
]

TEST_QUESTIONS = [
    # Held-out evaluation questions (untouched during dev)
    {
        "query_text": "What is the BNS provision for culpable homicide not amounting to murder?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "105",
        "ground_truth_answer": "Culpable homicide not amounting to murder is covered under Section 105 of BNS 2023 (formerly Section 304 of IPC).",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "What is the section for criminal breach of trust under BNS 2023?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "316",
        "ground_truth_answer": "Criminal breach of trust is governed by Section 316 of BNS 2023 (formerly Section 405/406 of IPC).",
        "is_ambiguous": False, "provenance": "adapted_ilsi"
    },
    {
        "query_text": "Under what section is forgery defined and penalized in BNS 2023?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "335, 336",
        "ground_truth_answer": "Forgery is defined under Section 335 and punished under Section 336 of BNS 2023 (formerly IPC Sections 463 and 465).",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "What is the punishment for mob lynching on grounds of caste or race under Section 103(2) of BNS?",
        "query_type": "ingredient_punishment", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "103(2)",
        "ground_truth_answer": "Under Section 103(2) of BNS 2023, murder committed by a group of five or more persons on grounds of race, caste, sex, or community is punishable with death or life imprisonment, and fine.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "Does BNS 2023 introduce a specific offence for petty organised crime?",
        "query_type": "new_offence", "source_act": "BNS", "target_act": "BNS",
        "ground_truth_sections": "112",
        "ground_truth_answer": "Yes, Section 112 of BNS 2023 introduces a specific offence for petty organised crime including gang-based snatching, ticket scalping, and unauthorized betting.",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "What is the legal status of sedition (IPC 124A) in post-July 2024 Indian criminal law?",
        "query_type": "ambiguous_repeal", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "124A, 152",
        "ground_truth_answer": "IPC Section 124A (Sedition) was repealed. In BNS 2023, Section 152 penalizes acts endangering sovereignty, unity, and integrity of India, requiring subversive/armed rebellion elements rather than mere disaffection.",
        "is_ambiguous": True, "provenance": "hand_curated"
    },
    {
        "query_text": "Where are gang rape provisions located in BNS 2023?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "70",
        "ground_truth_answer": "Gang rape is penalized under Section 70 of BNS 2023 (formerly IPC Section 376D).",
        "is_ambiguous": False, "provenance": "statute_qa"
    },
    {
        "query_text": "Which section penalizes rash driving under BNS 2023?",
        "query_type": "transition", "source_act": "IPC", "target_act": "BNS",
        "ground_truth_sections": "281",
        "ground_truth_answer": "Rash driving on a public way is penalized under Section 281 of BNS 2023 (formerly Section 279 of IPC).",
        "is_ambiguous": False, "provenance": "statute_qa"
    }
]


def write_benchmark_csv(data: list, path: str, prefix: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "question_id", "query_text", "query_type", "source_act",
        "target_act", "ground_truth_sections", "ground_truth_answer",
        "is_ambiguous", "provenance"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(data, start=1):
            row_copy = row.copy()
            row_copy["question_id"] = f"{prefix}_{idx:03d}"
            writer.writerow(row_copy)
    log.info(f"Saved {len(data)} questions to {path}")


def write_provenance_md(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = """# Benchmark Dataset Provenance & Distribution

This benchmark evaluates the IPC2BNS-Verify pipeline across 4 ablation stages.

## 1. Dataset Splits
- **Development Set (`benchmark_dev.csv`)**: 17 Q&A pairs used for pipeline tuning and retrieval parameter calibration.
- **Held-Out Test Set (`benchmark_test.csv`)**: 8 Q&A pairs held out and evaluated only for final ablation results.

## 2. Question Taxonomy & Distribution
- **Section Transitions (IPC ↔ BNS)**: Evaluates mapping lookup and retrieval precision across code shifts.
- **Ingredient & Punishment Queries**: Evaluates deep statutory understanding, penalty changes, and sub-section granularity.
- **Ambiguous & Repealed Provisions**: Evaluates verifier veto capability on §124A (Sedition), §497 (Adultery), and §377.
- **New BNS Offences**: Evaluates retrieval on novel statutory provisions (§111, §112, §113, §69).
- **Split & Merged Sections**: Evaluates multi-target mapping (§33 split, §120A/B merged).

## 3. Provenance Sources
- **`statute_qa`**: Formulated directly from India Code statutory text and legislative changes.
- **`adapted_ilsi`**: Adapted from factual query excerpts in the ILSI dataset (LeSICiN).
- **`hand_curated`**: Specifically crafted edge cases for ambiguity and verifier stress-testing.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    log.info(f"Saved provenance documentation to {path}")


def main():
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    dev_path = os.path.join(root, "data/03_benchmark/benchmark_dev.csv")
    test_path = os.path.join(root, "data/03_benchmark/benchmark_test.csv")
    prov_path = os.path.join(root, "data/03_benchmark/provenance.md")

    write_benchmark_csv(DEV_QUESTIONS, dev_path, "DEV")
    write_benchmark_csv(TEST_QUESTIONS, test_path, "TEST")
    write_provenance_md(prov_path)


if __name__ == "__main__":
    main()
