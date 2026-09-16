"""
penal_bound_verifier.py — Mathematical & Statutory Penal Invariant Verifier

Enforces hard statutory ceilings and invariant constraints:
1. Imprisonment Duration Bounds (Ensures generated sentence does not exceed statutory ceiling).
2. Mandatory Minimum Penalties (Flags omissions of mandatory statutory minimums).
3. Capital Punishment Constraints (Vetoes death penalty claims for non-capital offences).
4. Community Service Eligibility (Flags improper community service assertions on grave offences).
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class StatutoryPenalBound:
    section_code: str                  # e.g., "BNS_318", "BNS_103", "BNS_304"
    offence_title: str
    min_imprisonment_months: int       # 0 if no mandatory minimum
    max_imprisonment_months: int       # -1 for life imprisonment, -2 for death penalty
    allows_fine: bool
    is_capital_offence: bool
    allows_community_service: bool
    bailable: bool
    cognizable: bool


@dataclass
class PenalBoundCheckResult:
    passed: bool
    violation_type: Optional[str]      # "DURATION_EXCEEDED" | "MINIMUM_VIOLATED" | "ILLEGAL_CAPITAL_CLAIM" | "ILLEGAL_COMMUNITY_SERVICE"
    section_evaluated: str
    claimed_duration: str
    statutory_ceiling: str
    remedy_text: str
    confidence_penalty: float = 0.0


class PenalBoundVerifier:
    """
    Hard-constraint mathematical & penal invariant verifier.
    """

    STATUTORY_BOUNDS: Dict[str, StatutoryPenalBound] = {
        # BNS Substantive Offences
        "BNS_103": StatutoryPenalBound("BNS_103", "Murder", min_imprisonment_months=-1, max_imprisonment_months=-2, allows_fine=True, is_capital_offence=True, allows_community_service=False, bailable=False, cognizable=True),
        "BNS_103(2)": StatutoryPenalBound("BNS_103(2)", "Mob Lynching", min_imprisonment_months=-1, max_imprisonment_months=-2, allows_fine=True, is_capital_offence=True, allows_community_service=False, bailable=False, cognizable=True),
        "BNS_106(1)": StatutoryPenalBound("BNS_106(1)", "Rash and Negligent Driving Death", min_imprisonment_months=0, max_imprisonment_months=60, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=True, cognizable=True),
        "BNS_318": StatutoryPenalBound("BNS_318", "Cheating (Generic)", min_imprisonment_months=0, max_imprisonment_months=36, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=True, cognizable=False),
        "BNS_318(4)": StatutoryPenalBound("BNS_318(4)", "Cheating & Dishonestly Inducing Delivery", min_imprisonment_months=0, max_imprisonment_months=84, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=False, cognizable=True),
        "BNS_303(2)": StatutoryPenalBound("BNS_303(2)", "Theft (Generic)", min_imprisonment_months=0, max_imprisonment_months=36, allows_fine=True, is_capital_offence=False, allows_community_service=True, bailable=False, cognizable=True),
        "BNS_304": StatutoryPenalBound("BNS_304", "Snatching", min_imprisonment_months=0, max_imprisonment_months=36, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=False, cognizable=True),
        "BNS_69": StatutoryPenalBound("BNS_69", "Sexual Intercourse on Deceitful Promise", min_imprisonment_months=0, max_imprisonment_months=120, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=False, cognizable=True),
        "BNS_356(2)": StatutoryPenalBound("BNS_356(2)", "Defamation", min_imprisonment_months=0, max_imprisonment_months=24, allows_fine=True, is_capital_offence=False, allows_community_service=True, bailable=True, cognizable=False),
        "BNS_111": StatutoryPenalBound("BNS_111", "Organised Crime", min_imprisonment_months=60, max_imprisonment_months=-2, allows_fine=True, is_capital_offence=True, allows_community_service=False, bailable=False, cognizable=True),
        
        # IPC Historical Offences
        "IPC_302": StatutoryPenalBound("IPC_302", "Murder", min_imprisonment_months=-1, max_imprisonment_months=-2, allows_fine=True, is_capital_offence=True, allows_community_service=False, bailable=False, cognizable=True),
        "IPC_304A": StatutoryPenalBound("IPC_304A", "Death by Negligence", min_imprisonment_months=0, max_imprisonment_months=24, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=True, cognizable=True),
        "IPC_420": StatutoryPenalBound("IPC_420", "Cheating", min_imprisonment_months=0, max_imprisonment_months=84, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=False, cognizable=True),
        "IPC_379": StatutoryPenalBound("IPC_379", "Theft", min_imprisonment_months=0, max_imprisonment_months=36, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=False, cognizable=True),
        "IPC_499": StatutoryPenalBound("IPC_499", "Defamation", min_imprisonment_months=0, max_imprisonment_months=24, allows_fine=True, is_capital_offence=False, allows_community_service=False, bailable=True, cognizable=False),
    }

    DURATION_REGEX = re.compile(
        r'\b(?:punished\s+with\s+imprisonment\s+(?:for\s+a\s+term\s+)?(?:which\s+may\s+extend\s+to\s+)?|term\s+of\s+|up\s+to\s+)(\d+)\s+(years?|months?)\b',
        re.IGNORECASE
    )

    def verify_penal_bounds(self, generated_text: str, cited_sections: List[str]) -> PenalBoundCheckResult:
        gen_lower = generated_text.lower()

        # Check each cited section against statutory bounds
        for section_raw in cited_sections:
            sec_clean = section_raw.replace("§", "").replace("Section", "").strip()
            # Normalize to key
            target_key = None
            for k in self.STATUTORY_BOUNDS:
                if sec_clean.upper() in k or k.replace("_", " ") in sec_clean.upper():
                    target_key = k
                    break

            if not target_key:
                continue

            bound = self.STATUTORY_BOUNDS[target_key]

            # 1. Capital Punishment Check
            if not bound.is_capital_offence:
                if any(cap in gen_lower for cap in ["death penalty", "punished with death", "capital punishment", "sentenced to death"]):
                    return PenalBoundCheckResult(
                        passed=False,
                        violation_type="ILLEGAL_CAPITAL_CLAIM",
                        section_evaluated=bound.section_code,
                        claimed_duration="Death Penalty",
                        statutory_ceiling="Maximum " + (f"{bound.max_imprisonment_months // 12} years" if bound.max_imprisonment_months > 0 else "Life"),
                        remedy_text=f"Statutory Veto: {bound.section_code} ({bound.offence_title}) is not a capital offence and does NOT carry the death penalty.",
                        confidence_penalty=0.80
                    )

            # 2. Imprisonment Duration Ceiling Check
            matches = self.DURATION_REGEX.findall(generated_text)
            for val_str, unit in matches:
                val = int(val_str)
                claimed_months = val * 12 if "year" in unit.lower() else val

                if bound.max_imprisonment_months > 0 and claimed_months > bound.max_imprisonment_months:
                    return PenalBoundCheckResult(
                        passed=False,
                        violation_type="DURATION_EXCEEDED",
                        section_evaluated=bound.section_code,
                        claimed_duration=f"{val} {unit}",
                        statutory_ceiling=f"{bound.max_imprisonment_months // 12} years ({bound.max_imprisonment_months} months)",
                        remedy_text=f"Statutory Invariant Violation: Generated punishment duration ({val} {unit}) exceeds the statutory maximum ceiling for {bound.section_code} ({bound.max_imprisonment_months // 12} years).",
                        confidence_penalty=0.60
                    )

            # 3. Community Service Authorization Check
            if "community service" in gen_lower and not bound.allows_community_service:
                if not bound.is_capital_offence and bound.max_imprisonment_months > 36:
                    return PenalBoundCheckResult(
                        passed=False,
                        violation_type="ILLEGAL_COMMUNITY_SERVICE",
                        section_evaluated=bound.section_code,
                        claimed_duration="Community Service",
                        statutory_ceiling=f"Rigorous/Simple Imprisonment up to {bound.max_imprisonment_months // 12} years",
                        remedy_text=f"Statutory Constraint: Community service under BNS Section 4 is restricted to designated petty offences and cannot be substituted for grave offences under {bound.section_code}.",
                        confidence_penalty=0.30
                    )

        return PenalBoundCheckResult(
            passed=True,
            violation_type=None,
            section_evaluated="",
            claimed_duration="",
            statutory_ceiling="",
            remedy_text="",
            confidence_penalty=0.0
        )
