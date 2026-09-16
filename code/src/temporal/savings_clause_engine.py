import json
from datetime import date
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .timeline_parser import TimelineParser, ExtractedTimeline
from .hc_split_resolver import HighCourtSplitResolver, SplitResolution

@dataclass
class TemporalResolution:
    raw_query: str
    timeline: ExtractedTimeline
    substantive_code: str          # "IPC_1860" or "BNS_2023"
    procedural_code: str           # "CRPC_1973", "BNSS_2023", or "CONTESTED_HIGH_COURT_SPLIT"
    evidence_code: str             # "IEA_1872", "BSA_2023", or "CONTESTED"
    is_contested_split: bool
    split_details: Optional[Dict[str, Any]] = None
    statutory_citations: List[str] = field(default_factory=list)
    reasoning: str = ""
    actionable_guidance: str = ""

class SavingsClauseEngine:
    """
    Core engine for Date-Conditioned Criminal Law Reasoning in India.
    Applies Section 531 BNSS, Section 358 BNS, Section 170 BSA, and Article 20(1).
    """
    CUTOFF_DATE = date(2024, 7, 1)

    def __init__(self, rules_path: Optional[str] = None, split_path: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        if rules_path is None:
            rules_path = base_dir / "data" / "01_temporal" / "statutory_savings_rules.json"
        
        self.rules_path = Path(rules_path)
        self.parser = TimelineParser()
        self.split_resolver = HighCourtSplitResolver(split_path)
        self.rules_data = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        if self.rules_path.exists():
            with open(self.rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def resolve(self, query: str) -> TemporalResolution:
        timeline = self.parser.parse(query)
        return self.resolve_timeline(timeline)

    def resolve_timeline(self, timeline: ExtractedTimeline) -> TemporalResolution:
        incident_d = timeline.incident_date
        fir_d = timeline.fir_date
        petition_d = timeline.petition_date
        appeal_d = timeline.appeal_date
        posture = timeline.posture
        jur = timeline.jurisdiction_hint

        # 1. Determine Substantive Law (Strictly governed by Date of Incident per Art 20(1) & Sec 358 BNS)
        if incident_d is not None and incident_d < self.CUTOFF_DATE:
            substantive_code = "IPC_1860"
            substantive_reason = (
                f"Incident occurred on {incident_d.strftime('%d-%m-%Y')} (prior to 1 July 2024). "
                "Governed by Indian Penal Code, 1860 pursuant to Article 20(1) of the Constitution "
                "(prohibition of ex-post facto laws) and Section 358(1) of BNS 2023."
            )
            substantive_citations = ["Article 20(1), Constitution of India", "Section 358, Bharatiya Nyaya Sanhita 2023", "Indian Penal Code 1860"]
        elif incident_d is not None and incident_d >= self.CUTOFF_DATE:
            substantive_code = "BNS_2023"
            substantive_reason = (
                f"Incident occurred on {incident_d.strftime('%d-%m-%Y')} (on or after 1 July 2024). "
                "Governed directly by Bharatiya Nyaya Sanhita, 2023."
            )
            substantive_citations = ["Bharatiya Nyaya Sanhita 2023"]
        else:
            # Fallback if no date is found
            substantive_code = "BNS_2023"
            substantive_reason = "No pre-July 2024 date identified; defaulting to currently active BNS 2023."
            substantive_citations = ["Bharatiya Nyaya Sanhita 2023"]

        # 2. Check for High Court Jurisdictional Splits on Procedural Law
        incident_pre_july = incident_d is not None and incident_d < self.CUTOFF_DATE
        filing_post_july = False
        if posture == "APPEAL_OR_REVISION":
            filing_post_july = appeal_d is None or appeal_d >= self.CUTOFF_DATE
        elif posture == "BAIL_APPLICATION":
            filing_post_july = petition_d is None or petition_d >= self.CUTOFF_DATE

        split_res: SplitResolution = self.split_resolver.check_split(posture, incident_pre_july, filing_post_july)

        citations = list(substantive_citations)
        split_details = None

        if split_res.is_split:
            procedural_code = "CONTESTED_HIGH_COURT_SPLIT"
            evidence_code = "CONTESTED"
            citations.append("Section 531(2)(a), Bharatiya Nagarik Suraksha Sanhita 2023")
            citations.append("Section 170, Bharatiya Sakshya Adhiniyam 2023")
            
            reasoning = (
                f"{substantive_reason}\n\n"
                f"PROCEDURAL LAW CONTESTED: {split_res.issue}\n"
                "Different High Courts have reached divergent conclusions regarding the interpretation of 'pending' under Section 531(2)(a) BNSS."
            )
            
            # If a specific jurisdiction was mentioned, customize guidance
            guidance = split_res.advisory
            if jur and split_res.jurisdiction_breakdown:
                matched_jur_data = None
                for k, v in split_res.jurisdiction_breakdown.items():
                    if jur.lower() in k.lower():
                        matched_jur_data = v
                        break
                if matched_jur_data:
                    guidance += f"\n\n[Jurisdiction Note ({matched_jur_data['bench']})]: '{matched_jur_data['held']}' ({matched_jur_data['case_citation']}). Governing standard: {matched_jur_data['governing_statute']}."
                    procedural_code = matched_jur_data['governing_statute']

            
            split_details = {
                "split_id": split_res.split_id,
                "issue": split_res.issue,
                "jurisdictions": split_res.jurisdiction_breakdown,
                "advisory": split_res.advisory
            }

        else:
            # 3. Standard Non-Contested Procedural Resolution
            if incident_pre_july:
                filing_effective_d = fir_d or petition_d
                # Did an investigation/proceeding start before July 1, 2024?
                if filing_effective_d is not None and filing_effective_d < self.CUTOFF_DATE:
                    # Proceeding pending prior to July 1
                    procedural_code = "CRPC_1973"
                    evidence_code = "IEA_1872"
                    citations.extend(["Section 531(2)(a), BNSS 2023", "Code of Criminal Procedure 1973", "Indian Evidence Act 1872"])
                    reasoning = (
                        f"{substantive_reason}\n\n"
                        f"PROCEDURAL LAW: Code of Criminal Procedure, 1973 applies because FIR/complaint/proceeding was initiated on "
                        f"{filing_effective_d.strftime('%d-%m-%Y')}, making it a 'pending' proceeding immediately before 1 July 2024 under Section 531(2)(a) of BNSS 2023."
                    )
                    actionable = "Charge-sheet, investigation, and trial must follow CrPC 1973 procedures and Indian Evidence Act 1872."
                elif filing_effective_d is not None and filing_effective_d >= self.CUTOFF_DATE:
                    # Incident pre-July, but FIR/complaint registered post-July
                    procedural_code = "BNSS_2023"
                    evidence_code = "BSA_2023"
                    citations.extend(["Section 531(2)(a), BNSS 2023 (Inapplicable - no pending investigation)", "Bharatiya Nagarik Suraksha Sanhita 2023", "Bharatiya Sakshya Adhiniyam 2023"])
                    reasoning = (
                        f"{substantive_reason}\n\n"
                        f"PROCEDURAL LAW: Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) applies because the FIR/complaint was instituted on "
                        f"{filing_effective_d.strftime('%d-%m-%Y')} (on/after 1 July 2024). Since no investigation/proceeding was pending as of 01-07-2024, Section 531(2)(a) savings do not apply to procedure, "
                        "even though substantive offence remains under IPC 1860."
                    )
                    actionable = "Register complaint and conduct investigation/inquiry under BNSS 2023 provisions; charge substantive offences under IPC 1860."

                else:
                    # Default for pre-July incident with unstated FIR date: check posture
                    if posture in ["TRIAL_ONGOING", "INVESTIGATION_PENDING", "CHARGE_SHEET_FILED"]:
                        procedural_code = "CRPC_1973"
                        evidence_code = "IEA_1872"
                        citations.extend(["Section 531(2)(a), BNSS 2023", "Code of Criminal Procedure 1973"])
                        reasoning = f"{substantive_reason}\n\nPROCEDURAL LAW: Pending proceeding under CrPC 1973 saved by Section 531(2)(a) BNSS."
                        actionable = "Continue trial/investigation under CrPC 1973."
                    else:
                        procedural_code = "CRPC_1973"
                        evidence_code = "IEA_1872"
                        citations.extend(["Section 531(2)(a), BNSS 2023", "Code of Criminal Procedure 1973"])
                        reasoning = f"{substantive_reason}\n\nPROCEDURAL LAW: CrPC 1973 applies under savings clause."
                        actionable = "Proceed under CrPC 1973."
            else:
                # Fully post-July 1, 2024
                procedural_code = "BNSS_2023"
                evidence_code = "BSA_2023"
                citations.extend(["Bharatiya Nagarik Suraksha Sanhita 2023", "Bharatiya Sakshya Adhiniyam 2023"])
                reasoning = (
                    f"{substantive_reason}\n\n"
                    "PROCEDURAL LAW: All proceedings, investigation, bail, and trial are governed by BNSS 2023 and BSA 2023."
                )
                actionable = "Apply BNS 2023 for substantive charges and BNSS 2023 for all procedural steps."

            guidance = actionable

        return TemporalResolution(
            raw_query=timeline.raw_query,
            timeline=timeline,
            substantive_code=substantive_code,
            procedural_code=procedural_code,
            evidence_code=evidence_code,
            is_contested_split=split_res.is_split,
            split_details=split_details,
            statutory_citations=citations,
            reasoning=reasoning,
            actionable_guidance=guidance
        )
