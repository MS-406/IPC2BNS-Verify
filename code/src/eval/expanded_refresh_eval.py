"""
expanded_refresh_eval.py — N=50 Refresh Simulation Evaluation (Phase E, Gap 5)

Expands the Stage 4 refresh evaluation from N=3 to N=50 realistic amendment scenarios
covering three categories:
1. NEW_SECTION: Entirely new offence provisions (e.g., deepfake fraud, cyberterrorism)
2. MODIFIED_PUNISHMENT: Changes to existing punishment terms or scope
3. REPEALED: Removal of obsolete provisions

Outputs:
- data/phase5_refresh_sim/expanded_amendment_cases.csv — 50 amendment records
- results/refresh_eval/expanded_refresh_results.json — Hot-patch evaluation metrics

Metrics Reported:
- Hot-patch success rate (% of amendments correctly applied)
- Average hot-patch latency (ms per amendment)
- Index integrity (pre vs post chunk count delta)
- Retrieval accuracy post-refresh (can the updated section be found?)
"""

import os
import sys
import csv
import json
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("expanded_refresh_eval")


# ── 50 Realistic Amendment Scenarios ─────────────────────────────────────
EXPANDED_AMENDMENTS = [
    # NEW_SECTION: 20 new offences
    {"amendment_id": "AMD_E01", "act": "BNS", "section_number": "318A", "section_title": "Cheating by deepfake or AI impersonation", "section_text": "Whoever employs generative AI, deepfake technology, or voice cloning to fraudulently impersonate another person for monetary gain shall be punished with rigorous imprisonment up to seven years and fine up to ten lakh rupees.", "chapter": "XVII — Offences Against Property", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E02", "act": "BNS", "section_number": "278A", "section_title": "Industrial pollution endangering water supply", "section_text": "Whoever knowingly discharges hazardous effluent into public water sources shall be punished with imprisonment up to five years and fine not less than twenty lakh rupees.", "chapter": "XIV — Public Health", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E03", "act": "BNS", "section_number": "111A", "section_title": "Cyber-enabled organised crime", "section_text": "Whoever as part of an organised crime syndicate uses electronic systems for commission of scheduled offences shall be punished with imprisonment not less than five years extendable to life.", "chapter": "V — Criminal Conspiracy", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E04", "act": "BNS", "section_number": "113A", "section_title": "Cyberterrorism", "section_text": "Whoever commits or attempts to commit an act of terrorism through electronic means, including disruption of critical information infrastructure, shall be punished with imprisonment for life.", "chapter": "V — Criminal Conspiracy", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E05", "act": "BNS", "section_number": "69A", "section_title": "Aggravated mob violence causing death", "section_text": "Where mob violence as defined under Section 69 results in the death of the victim, each member of the mob shall be punished with imprisonment for life or death.", "chapter": "III — Offences Against Body", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E06", "act": "BNS", "section_number": "303A", "section_title": "Trafficking using digital platforms", "section_text": "Whoever uses online platforms, social media, or encrypted messaging for human trafficking shall be punished with rigorous imprisonment not less than ten years.", "chapter": "XVI — Offences Affecting Human Body", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E07", "act": "BNS", "section_number": "120", "section_title": "Stalking using electronic surveillance", "section_text": "Whoever monitors, tracks, or surveils another person through electronic means including GPS trackers, spyware, or social media without consent shall be punished with imprisonment up to three years.", "chapter": "VIII — Offences Against Women", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E08", "act": "BNS", "section_number": "332A", "section_title": "Cryptocurrency fraud and digital asset theft", "section_text": "Whoever dishonestly misappropriates or converts to own use any digital asset, cryptocurrency, or blockchain-based token shall be punished with imprisonment up to seven years and fine.", "chapter": "XVII — Offences Against Property", "change_type": "NEW_SECTION", "effective_start": "2025-06-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E09", "act": "BNS", "section_number": "200A", "section_title": "False information endangering sovereignty", "section_text": "Whoever publishes or circulates information known to be false and likely to endanger sovereignty or territorial integrity shall be punished with imprisonment up to five years.", "chapter": "X — Offences Against State", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E10", "act": "BNS", "section_number": "85A", "section_title": "Offence of sextortion", "section_text": "Whoever threatens to publish or transmit intimate images of another person to extort money, sexual favours, or other consideration shall be punished with imprisonment up to five years and fine.", "chapter": "VIII — Offences Against Women", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E11", "act": "BNS", "section_number": "256A", "section_title": "Counterfeiting digital identity documents", "section_text": "Whoever counterfeits or tampers with Aadhaar, digital driving licence, or any government-issued digital identity document shall be punished with imprisonment up to seven years.", "chapter": "XII — Offences Relating to Documents", "change_type": "NEW_SECTION", "effective_start": "2025-03-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E12", "act": "BNS", "section_number": "150A", "section_title": "Endangering passenger safety in public transport", "section_text": "Whoever by any rash or negligent act endangers the safety of passengers in public transport including railways and aviation shall be punished with imprisonment up to three years.", "chapter": "IX — Public Tranquility", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E13", "act": "BNS", "section_number": "279A", "section_title": "Contamination of food supply chain", "section_text": "Whoever adulterates or contaminates food products in the supply chain with substances dangerous to health shall be punished with imprisonment up to ten years and fine.", "chapter": "XIV — Public Health", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E14", "act": "BNS", "section_number": "355A", "section_title": "Assault on healthcare workers", "section_text": "Whoever assaults or uses criminal force against a healthcare worker during discharge of duty shall be punished with imprisonment up to five years and fine up to five lakh rupees.", "chapter": "XVI — Offences Against Body", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E15", "act": "BNS", "section_number": "270A", "section_title": "Negligent spread of epidemic disease", "section_text": "Whoever negligently or maliciously spreads or abets the spread of a notified epidemic disease shall be punished with imprisonment up to two years or fine or both.", "chapter": "XIV — Public Health", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E16", "act": "BNS", "section_number": "336A", "section_title": "Illegal drone operation endangering public safety", "section_text": "Whoever operates an unmanned aerial system in prohibited airspace or in a manner endangering public safety shall be punished with imprisonment up to two years and fine.", "chapter": "XIV — Public Nuisance", "change_type": "NEW_SECTION", "effective_start": "2025-06-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E17", "act": "BNS", "section_number": "319A", "section_title": "Phishing and credential theft", "section_text": "Whoever creates fraudulent electronic communications to deceive persons into revealing passwords, financial credentials, or personal information shall be punished with imprisonment up to three years and fine.", "chapter": "XVII — Offences Against Property", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E18", "act": "BNS", "section_number": "114A", "section_title": "Financing of terrorism through hawala", "section_text": "Whoever provides or collects funds through informal value transfer (hawala) for terrorist activities shall be punished with imprisonment for life and forfeiture of property.", "chapter": "V — Criminal Conspiracy", "change_type": "NEW_SECTION", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E19", "act": "BNS", "section_number": "145A", "section_title": "Hate speech on digital platforms", "section_text": "Whoever publishes or circulates on electronic platforms statements promoting enmity between groups on grounds of religion, race, or caste shall be punished with imprisonment up to three years and fine.", "chapter": "IX — Public Tranquility", "change_type": "NEW_SECTION", "effective_start": "2025-03-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E20", "act": "BNS", "section_number": "220A", "section_title": "Bribery of foreign public officials", "section_text": "Whoever gives or agrees to give gratification to a foreign public official to obtain business advantage shall be punished with imprisonment up to seven years and fine.", "chapter": "XI — Offences by Public Servants", "change_type": "NEW_SECTION", "effective_start": "2025-06-01", "effective_end": "9999-12-31"},

    # MODIFIED_PUNISHMENT: 15 changes to existing provisions
    {"amendment_id": "AMD_E21", "act": "BNS", "section_number": "106", "section_title": "Death by negligence (Amended 2025)", "section_text": "(1) Causing death by rash or negligent act: up to 5 years. (2) Causing death by rash driving and fleeing: up to 10 years. (3) Proviso: rendering immediate medical aid may reduce sentence by half.", "chapter": "VI — Offences Against Body", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E22", "act": "BNS", "section_number": "303", "section_title": "Trafficking (Enhanced punishment)", "section_text": "Punishment enhanced from minimum 7 years to minimum 10 years rigorous imprisonment for trafficking of minors.", "chapter": "XVI — Offences Against Body", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E23", "act": "BNS", "section_number": "316", "section_title": "Criminal breach of trust (Enhanced fine)", "section_text": "Fine enhanced to not less than twice the value of property misappropriated, in addition to imprisonment.", "chapter": "XVII — Offences Against Property", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E24", "act": "BNS", "section_number": "74", "section_title": "Assault on woman (Enhanced)", "section_text": "Minimum imprisonment enhanced from 1 year to 2 years. Mandatory compensation to victim added.", "chapter": "VIII — Offences Against Women", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-03-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E25", "act": "BNS", "section_number": "308", "section_title": "Extortion (Enhanced)", "section_text": "Maximum imprisonment enhanced from 3 years to 5 years. Fine not less than twice the extorted amount.", "chapter": "XVII — Offences Against Property", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E26", "act": "BNS", "section_number": "103", "section_title": "Murder (Mandatory minimum)", "section_text": "Clarification: mandatory minimum life imprisonment means imprisonment for remainder of natural life in heinous cases.", "chapter": "VI — Offences Against Body", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E27", "act": "BNS", "section_number": "309", "section_title": "Robbery (Enhanced)", "section_text": "Punishment for robbery with use of firearms: minimum 7 years, maximum 14 years rigorous imprisonment.", "chapter": "XVII — Offences Against Property", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E28", "act": "BNS", "section_number": "318", "section_title": "Cheating (Digital commerce)", "section_text": "Cheating through e-commerce platforms: enhanced punishment of up to 7 years and fine equal to amount cheated.", "chapter": "XVII — Offences Against Property", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-06-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E29", "act": "BNS", "section_number": "329", "section_title": "Criminal misappropriation (Digital assets)", "section_text": "Extended to cover misappropriation of digital assets, NFTs, and virtual property. Same punishment as physical property.", "chapter": "XVII — Offences Against Property", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E30", "act": "BNS", "section_number": "351", "section_title": "Criminal intimidation (Online)", "section_text": "Criminal intimidation through electronic means: enhanced punishment up to 3 years (previously 2 years).", "chapter": "XIX — Criminal Intimidation", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E31", "act": "BNS", "section_number": "78", "section_title": "Voyeurism (Enhanced)", "section_text": "First offence: 1-3 years. Second or subsequent: 3-7 years. Non-compoundable.", "chapter": "VIII — Offences Against Women", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E32", "act": "BNS", "section_number": "336", "section_title": "Forgery of electronic records (Enhanced)", "section_text": "Forgery of electronic records: enhanced from 2 years to 5 years imprisonment.", "chapter": "XII — Offences Relating to Documents", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-03-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E33", "act": "BNS", "section_number": "296", "section_title": "Obscenity in electronic form (Enhanced)", "section_text": "Publishing obscene material in electronic form: punishment enhanced to 5 years and fine up to ten lakh rupees.", "chapter": "XIII — Offences Against Public Morals", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E34", "act": "BNS", "section_number": "256", "section_title": "Counterfeiting stamps (Enhanced)", "section_text": "Enhanced punishment for counterfeiting government stamps used for revenue: up to 10 years.", "chapter": "XII — Offences Relating to Documents", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-01-01", "effective_end": "9999-12-31"},
    {"amendment_id": "AMD_E35", "act": "BNS", "section_number": "299", "section_title": "Defamation (Amended)", "section_text": "Clarification: online defamation treated at par with print media defamation. Enhanced fine provisions.", "chapter": "XIX — Defamation", "change_type": "MODIFIED_PUNISHMENT", "effective_start": "2025-06-01", "effective_end": "9999-12-31"},

    # REPEALED: 15 provisions removed or struck down
    {"amendment_id": "AMD_E36", "act": "BNS", "section_number": "152", "section_title": "Wantonly giving provocation to cause riot (Repealed)", "section_text": "REPEALED — Subsumed into enhanced provisions of BNS §196.", "chapter": "IX — Public Tranquility", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E37", "act": "BNS", "section_number": "214", "section_title": "Taking gift to help recover stolen property (Repealed)", "section_text": "REPEALED — Redundant with enhanced anti-fencing provisions.", "chapter": "XI — Public Servants", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E38", "act": "BNS", "section_number": "215", "section_title": "Taking gift to screen offender from punishment (Repealed)", "section_text": "REPEALED — Consolidated into BNS §218 (Public servant framing incorrect record).", "chapter": "XI — Public Servants", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E39", "act": "BNS", "section_number": "286", "section_title": "Negligent conduct with respect to animal (Repealed)", "section_text": "REPEALED — Transferred to separate Animal Welfare Act provisions.", "chapter": "XIV — Public Safety", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E40", "act": "BNS", "section_number": "292", "section_title": "Sale of obscene books (Repealed)", "section_text": "REPEALED — Subsumed into digital obscenity provisions of enhanced BNS §296.", "chapter": "XIII — Public Morals", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E41", "act": "BNS", "section_number": "293", "section_title": "Sale of obscene objects to young person (Repealed)", "section_text": "REPEALED — Merged into POCSO Act provisions and BNS §296.", "chapter": "XIII — Public Morals", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E42", "act": "BNS", "section_number": "157", "section_title": "Harbouring persons hired for unlawful assembly (Repealed)", "section_text": "REPEALED — Consolidated into general harbouring provisions.", "chapter": "IX — Public Tranquility", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E43", "act": "BNS", "section_number": "160", "section_title": "Committing affray (Repealed)", "section_text": "REPEALED — Subsumed into broader public disturbance provisions.", "chapter": "IX — Public Tranquility", "change_type": "REPEALED", "effective_start": "2025-03-01", "effective_end": "2025-03-01"},
    {"amendment_id": "AMD_E44", "act": "BNS", "section_number": "283", "section_title": "Danger or obstruction in public way (Repealed)", "section_text": "REPEALED — Transferred to municipal corporation bye-laws and traffic regulations.", "chapter": "XIV — Public Nuisance", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E45", "act": "BNS", "section_number": "284", "section_title": "Negligent conduct with respect to poisonous substance (Repealed)", "section_text": "REPEALED — Covered under Hazardous Substances Management Act.", "chapter": "XIV — Public Safety", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E46", "act": "BNS", "section_number": "287", "section_title": "Negligent conduct with machinery (Repealed)", "section_text": "REPEALED — Covered under Factories Act and occupational safety regulations.", "chapter": "XIV — Public Safety", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E47", "act": "BNS", "section_number": "288", "section_title": "Negligent conduct with fire (Repealed)", "section_text": "REPEALED — Covered under National Fire Safety Code and state fire services acts.", "chapter": "XIV — Public Safety", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E48", "act": "BNS", "section_number": "289", "section_title": "Negligent conduct with explosive substance (Repealed)", "section_text": "REPEALED — Covered under Explosives Act 1884 and Explosive Substances Act 1908.", "chapter": "XIV — Public Safety", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
    {"amendment_id": "AMD_E49", "act": "BNS", "section_number": "167", "section_title": "Public servant framing incorrect document with intent to save (Repealed)", "section_text": "REPEALED — Merged into consolidated anti-corruption provisions.", "chapter": "XI — Public Servants", "change_type": "REPEALED", "effective_start": "2025-06-01", "effective_end": "2025-06-01"},
    {"amendment_id": "AMD_E50", "act": "BNS", "section_number": "168", "section_title": "Public servant unlawfully engaging in trade (Repealed)", "section_text": "REPEALED — Now governed by service conduct rules and Prevention of Corruption Act.", "chapter": "XI — Public Servants", "change_type": "REPEALED", "effective_start": "2025-01-01", "effective_end": "2025-01-01"},
]


def export_expanded_amendments(output_csv: str):
    """Export all 50 amendment scenarios to CSV."""
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    fieldnames = [
        "amendment_id", "act", "section_number", "section_title",
        "section_text", "chapter", "change_type", "effective_start", "effective_end"
    ]
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for a in EXPANDED_AMENDMENTS:
            writer.writerow(a)
    log.info(f"Exported {len(EXPANDED_AMENDMENTS)} amendments to {output_csv}")


def run_expanded_refresh_eval(
    base_index_dir: Optional[str] = None,
    output_dir: str = "results/refresh_eval"
):
    """
    Runs the N=50 refresh evaluation: applies each amendment, measures
    hot-patch latency, checks index integrity, and tests retrieval accuracy.
    """
    from src.refresh.updater import IncrementalIndexUpdater, AmendmentRecord
    from src.retrieval.search import get_retriever

    # Find base index
    if base_index_dir is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        base_index_dir = os.path.join(root, "data", "phase3_embeddings", "stage2_index")
        if not os.path.exists(os.path.join(base_index_dir, "index.pkl")):
            # Try alternate paths
            for alt in ["data/05_embeddings_index/stage2_index", "data/phase3_embeddings/stage2_index"]:
                candidate = os.path.join(root, alt)
                if os.path.exists(os.path.join(candidate, "index.pkl")):
                    base_index_dir = candidate
                    break

    os.makedirs(output_dir, exist_ok=True)

    results = {
        "total_amendments": len(EXPANDED_AMENDMENTS),
        "by_type": {"NEW_SECTION": [], "MODIFIED_PUNISHMENT": [], "REPEALED": []},
        "success_count": 0,
        "failure_count": 0,
        "total_latency_ms": 0,
        "per_amendment": [],
    }

    try:
        updater = IncrementalIndexUpdater(base_index_dir)
        pre_count = updater.index.total_docs
        log.info(f"Base index has {pre_count} chunks")
    except Exception as e:
        log.error(f"Could not load base index from {base_index_dir}: {e}")
        log.info("Generating results based on amendment structure analysis...")

        # Generate analysis-based results even without index
        for a in EXPANDED_AMENDMENTS:
            result = {
                "amendment_id": a["amendment_id"],
                "change_type": a["change_type"],
                "section": f"{a['act']} §{a['section_number']}",
                "title": a["section_title"],
                "status": "PENDING_INDEX",
                "latency_ms": 0,
                "notes": "Base index not found — amendment prepared for application"
            }
            results["per_amendment"].append(result)
            results["by_type"][a["change_type"]].append(result)

        with open(os.path.join(output_dir, "expanded_refresh_results.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        log.info(f"Results (pending) saved to {output_dir}")
        return results

    for a in EXPANDED_AMENDMENTS:
        amendment = AmendmentRecord(
            amendment_id=a["amendment_id"],
            act=a["act"],
            section_number=a["section_number"],
            section_title=a["section_title"],
            section_text=a["section_text"],
            chapter=a["chapter"],
            change_type=a["change_type"],
            effective_start=a["effective_start"],
            effective_end=a["effective_end"]
        )

        start_t = time.time()
        try:
            chunk = updater.apply_amendment(amendment)
            latency = (time.time() - start_t) * 1000
            success = True

            # Test retrieval: Can we find the amended section?
            retrieval_test = updater.index.search(
                f"{a['act']} Section {a['section_number']} {a['section_title']}", top_k=3
            )
            found = any(
                c.section_number.strip() == a["section_number"].strip()
                for c, _ in retrieval_test
            )

            result = {
                "amendment_id": a["amendment_id"],
                "change_type": a["change_type"],
                "section": f"{a['act']} §{a['section_number']}",
                "title": a["section_title"],
                "status": "SUCCESS",
                "latency_ms": round(latency, 2),
                "retrieval_found": found,
                "post_chunk_count": updater.index.total_docs,
            }
            results["success_count"] += 1

        except Exception as e:
            latency = (time.time() - start_t) * 1000
            result = {
                "amendment_id": a["amendment_id"],
                "change_type": a["change_type"],
                "section": f"{a['act']} §{a['section_number']}",
                "title": a["section_title"],
                "status": "FAILED",
                "latency_ms": round(latency, 2),
                "error": str(e),
            }
            results["failure_count"] += 1

        results["total_latency_ms"] += latency
        results["per_amendment"].append(result)
        results["by_type"][a["change_type"]].append(result)

    # Compute aggregate metrics
    post_count = updater.index.total_docs
    results["pre_index_chunks"] = pre_count
    results["post_index_chunks"] = post_count
    results["success_rate"] = round(results["success_count"] / len(EXPANDED_AMENDMENTS) * 100, 1)
    results["avg_latency_ms"] = round(results["total_latency_ms"] / len(EXPANDED_AMENDMENTS), 2)
    results["retrieval_accuracy"] = round(
        sum(1 for r in results["per_amendment"] if r.get("retrieval_found", False)) / len(EXPANDED_AMENDMENTS) * 100, 1
    )

    # Save snapshot
    snapshot_dir = os.path.join(os.path.dirname(base_index_dir), "stage4_expanded_refresh_index")
    try:
        updater.save_post_refresh_snapshot(snapshot_dir)
    except Exception as e:
        log.warning(f"Could not save snapshot: {e}")

    # Save results
    with open(os.path.join(output_dir, "expanded_refresh_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n═══ Expanded Refresh Evaluation (N=50) ═══")
    print(f"Success Rate:       {results['success_rate']}%")
    print(f"Avg Latency:        {results['avg_latency_ms']}ms per amendment")
    print(f"Index Growth:       {pre_count} → {post_count} chunks")
    print(f"Retrieval Accuracy: {results['retrieval_accuracy']}%")
    print(f"\nBy Type:")
    for t, items in results["by_type"].items():
        ok = sum(1 for r in items if r.get("status") == "SUCCESS")
        print(f"  {t}: {ok}/{len(items)} successful")

    log.info(f"Results saved to {output_dir}")
    return results


if __name__ == "__main__":
    # First export the CSV
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    csv_path = os.path.join(root, "data", "phase5_refresh_sim", "expanded_amendment_cases.csv")
    export_expanded_amendments(csv_path)

    # Then run evaluation
    run_expanded_refresh_eval(output_dir=os.path.join(root, "results", "refresh_eval"))
