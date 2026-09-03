"""
build_injected_errors.py — Generates Injected-Error Test Benchmark for Verifier Stress Testing

Produces data/03_benchmark/injected_errors.csv containing synthetic adversarial examples:
1. Hallucinated Section Numbers ([BNS §999], [BNS §450])
2. Repealed Statute Claims ([IPC §124A], [IPC §497], [IPC §377])
3. Ungrounded Penal Claims (claims death penalty for simple theft)
4. Valid Negative Controls (clean valid answers) to compute False Positive Rate (FPR)
"""

import os
import csv
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_injected_errors")

INJECTED_ERRORS = [
    # 1. Hallucinated Section Numbers
    {
        "error_id": "ERR_001",
        "error_type": "hallucinated_section",
        "query_text": "What is the new section for extortion in BNS?",
        "generated_text": "Under the new Bharatiya Nyaya Sanhita, extortion is defined and penalized under [BNS §999] with up to 10 years imprisonment.",
        "cited_sections": "[BNS §999]",
        "expected_verdict": "REJECTED_HALLUCINATED_CITATION",
        "is_adversarial_error": True
    },
    {
        "error_id": "ERR_002",
        "error_type": "hallucinated_section",
        "query_text": "Where is cyber defamation covered?",
        "generated_text": "Cyber defamation is specifically covered under [BNS §450] with fine and community service.",
        "cited_sections": "[BNS §450]",
        "expected_verdict": "REJECTED_HALLUCINATED_CITATION",
        "is_adversarial_error": True
    },

    # 2. Repealed Section Hallucinations
    {
        "error_id": "ERR_003",
        "error_type": "repealed_section_cited",
        "query_text": "Can a person be charged with sedition under Section 124A in 2025?",
        "generated_text": "Yes, sedition remains an active offence under [IPC §124A] for exciting disaffection against the Government.",
        "cited_sections": "[IPC §124A]",
        "expected_verdict": "VETOED_REPEALED_PROVISION",
        "is_adversarial_error": True
    },
    {
        "error_id": "ERR_004",
        "error_type": "repealed_section_cited",
        "query_text": "What is the punishment for adultery in the new code?",
        "generated_text": "Adultery is penalized with up to 5 years imprisonment under [IPC §497].",
        "cited_sections": "[IPC §497]",
        "expected_verdict": "VETOED_REPEALED_PROVISION",
        "is_adversarial_error": True
    },
    {
        "error_id": "ERR_005",
        "error_type": "repealed_section_cited",
        "query_text": "Is homosexual conduct criminalized under Section 377?",
        "generated_text": "Unnatural offences are strictly prohibited under [IPC §377] with life imprisonment.",
        "cited_sections": "[IPC §377]",
        "expected_verdict": "VETOED_REPEALED_PROVISION",
        "is_adversarial_error": True
    },

    # 3. Ungrounded Penal Claims
    {
        "error_id": "ERR_006",
        "error_type": "ungrounded_claim",
        "query_text": "What is the punishment for simple theft under BNS?",
        "generated_text": "Under [BNS §303], simple theft carries mandatory death penalty or life imprisonment without parole.",
        "cited_sections": "[BNS §303]",
        "expected_verdict": "UNGROUNDED_CLAIM",
        "is_adversarial_error": True
    },

    # 4. Valid Controls (Must Pass Verifier -> Tests False Positive Rate)
    {
        "error_id": "ERR_007",
        "error_type": "valid_control",
        "query_text": "What is the punishment for murder under BNS?",
        "generated_text": "Under [BNS §103], whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine.",
        "cited_sections": "[BNS §103]",
        "expected_verdict": "VERIFIED",
        "is_adversarial_error": False
    },
    {
        "error_id": "ERR_008",
        "error_type": "valid_control",
        "query_text": "Where is cheating defined in BNS?",
        "generated_text": "Cheating and dishonestly inducing delivery of property is penalized under [BNS §318] with imprisonment up to seven years and fine.",
        "cited_sections": "[BNS §318]",
        "expected_verdict": "VERIFIED",
        "is_adversarial_error": False
    },
    {
        "error_id": "ERR_009",
        "error_type": "valid_control",
        "query_text": "What is the penalty for dowry death?",
        "generated_text": "Dowry death is governed by [BNS §80] and carries imprisonment for a term not less than seven years up to life imprisonment.",
        "cited_sections": "[BNS §80]",
        "expected_verdict": "VERIFIED",
        "is_adversarial_error": False
    },
    {
        "error_id": "ERR_010",
        "error_type": "valid_control",
        "query_text": "What provision applies to organised crime?",
        "generated_text": "Organised crime syndicates and continuing unlawful activities are penalized under [BNS §111] with death or life imprisonment if death results.",
        "cited_sections": "[BNS §111]",
        "expected_verdict": "VERIFIED",
        "is_adversarial_error": False
    }
]


def build_injected_errors_file(output_csv: str):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    fieldnames = [
        "error_id", "error_type", "query_text", "generated_text",
        "cited_sections", "expected_verdict", "is_adversarial_error"
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(INJECTED_ERRORS)
    log.info(f"Saved {len(INJECTED_ERRORS)} injected-error stress test cases to {output_csv}")


if __name__ == "__main__":
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    out_file = os.path.join(root, "data/03_benchmark/injected_errors.csv")
    build_injected_errors_file(out_file)
