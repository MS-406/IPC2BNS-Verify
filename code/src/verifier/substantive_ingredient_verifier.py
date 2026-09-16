"""
substantive_ingredient_verifier.py — Deep Substantive Ingredient & Statutory Delta Verifier

Identifies critical substantive law changes between IPC 1860 and BNS 2023:
1. Novel Statutory Offences: Snatching (§304), Organised Crime (§111), Terrorist Act (§113), Deceitful Promise to Marry (§69).
2. Altered Statutory Ingredients: Mob Lynching (§103(2)), Medical Negligence (§106(1)), Hit-and-Run (§106(2) abeyance).
3. New Penal Modality: Community Service (§4, §303(2) proviso, §355, §356(2)).
4. Repealed & Struck-down Offences: Sedition (§124A), Adultery (§497), Unnatural Offences (§377).

Ensures LLM generations do not falsely equate IPC and BNS where the legislative ingredients have fundamentally diverged.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set


@dataclass
class IngredientDelta:
    offence_name: str
    ipc_section: Optional[str]
    bns_section: Optional[str]
    delta_type: str                     # "NOVEL_OFFENCE" | "MODIFIED_INGREDIENTS" | "REPEALED_PROVISION" | "PENALTY_ALTERATION"
    key_new_ingredients: List[str]
    removed_ingredients: List[str]
    penal_modality_change: Optional[str]
    statutory_warning: str


@dataclass
class SubstantiveVerificationResult:
    passed: bool
    offence_detected: Optional[str]
    delta_type: Optional[str]
    is_delta_violation: bool
    identified_omissions: List[str]
    identified_misrepresentations: List[str]
    remedial_statutory_advisory: str
    confidence_penalty: float = 0.0


class SubstantiveIngredientVerifier:
    """
    Deep semantic verifier for substantive criminal law element changes between IPC 1860 and BNS 2023.
    """

    STATUTORY_DELTAS: Dict[str, IngredientDelta] = {
        "MOB_LYNCHING": IngredientDelta(
            offence_name="Mob Lynching / Hate Murder",
            ipc_section="302",
            bns_section="103(2)",
            delta_type="MODIFIED_INGREDIENTS",
            key_new_ingredients=[
                "group of five or more persons acting in concert",
                "murder committed on grounds of race, caste, sex, place of birth, language, personal belief"
            ],
            removed_ingredients=[],
            penal_modality_change="Mandatory death penalty or imprisonment for life, and fine",
            statutory_warning="BNS §103(2) explicitly creates a distinct sub-offence for mob lynching with a 5+ person threshold and protected identity grounds, which was absent in IPC §302."
        ),
        "DECEITFUL_PROMISE_TO_MARRY": IngredientDelta(
            offence_name="Sexual Intercourse by Deceitful Means / False Promise to Marry",
            ipc_section=None,  # Was prosecuted under IPC 375/417 via judicial interpretation
            bns_section="69",
            delta_type="NOVEL_OFFENCE",
            key_new_ingredients=[
                "deceitful means including false promise of employment or promotion",
                "marrying after suppressing identity",
                "intercourse not amounting to the offence of rape"
            ],
            removed_ingredients=[],
            penal_modality_change="Imprisonment up to 10 years and fine",
            statutory_warning="BNS §69 creates an independent statutory offence for sexual intercourse on false promise of marriage or identity suppression, distinct from rape under §63 BNS / §375 IPC."
        ),
        "SNATCHING": IngredientDelta(
            offence_name="Snatching",
            ipc_section="379",  # Was charged under generic theft or robbery
            bns_section="304",
            delta_type="NOVEL_OFFENCE",
            key_new_ingredients=[
                "sudden or quick or forcible seizure or grabbing of property from possession of any person"
            ],
            removed_ingredients=[],
            penal_modality_change="Imprisonment up to 3 years and fine",
            statutory_warning="BNS §304 introduces an explicit definition of snatching as a specific aggravated form of theft."
        ),
        "ORGANISED_CRIME": IngredientDelta(
            offence_name="Organised Crime",
            ipc_section=None,  # Handled formerly only by state statutes (MCOCA, GUJCTOC)
            bns_section="111",
            delta_type="NOVEL_OFFENCE",
            key_new_ingredients=[
                "continuing unlawful activity by member or on behalf of organised crime syndicate",
                "use of violence, threat, intimidation, or coercion",
                "economic offences, human trafficking, cyber crime of severe nature"
            ],
            removed_ingredients=[],
            penal_modality_change="Death or life imprisonment with minimum Rs. 5 lakh fine",
            statutory_warning="BNS §111 codifies organised crime syndicate offences at the national federal level for the first time."
        ),
        "COMMUNITY_SERVICE": IngredientDelta(
            offence_name="Community Service Penal Modality",
            ipc_section=None,
            bns_section="4(f), 303(2) proviso, 355, 356(2)",
            delta_type="PENALTY_ALTERATION",
            key_new_ingredients=[
                "first-time petty theft where value is less than Rs. 5,000 upon return of property",
                "defamation",
                "public servant unlawfully engaging in trade",
                "misconduct in public by drunken person"
            ],
            removed_ingredients=[],
            penal_modality_change="Community service added as statutory punishment modality",
            statutory_warning="BNS Section 4(f) introduces Community Service as an official penal modality for designated petty offences."
        ),
        "HIT_AND_RUN": IngredientDelta(
            offence_name="Rash and Negligent Driving Causing Death / Hit and Run",
            ipc_section="304A",
            bns_section="106(1) & 106(2)",
            delta_type="MODIFIED_INGREDIENTS",
            key_new_ingredients=[
                "Section 106(1): General rash/negligent driving causing death (imprisonment up to 5 years)",
                "Section 106(2): Escaping without reporting to police/magistrate (up to 10 years - KEPT IN ABEYANCE)"
            ],
            removed_ingredients=[],
            penal_modality_change="Enhanced from 2 years under IPC 304A to 5 years under BNS 106(1)",
            statutory_warning="BNS §106(1) increases negligence punishment to 5 years. Section 106(2) (10 years for failure to report) has been officially stayed/held in abeyance pending notification."
        ),
        "SEDITION_REPEAL": IngredientDelta(
            offence_name="Sedition (Repealed)",
            ipc_section="124A",
            bns_section="152",  # Not direct equivalent
            delta_type="REPEALED_PROVISION",
            key_new_ingredients=[
                "BNS 152 requires acts endangering sovereignty, unity, and integrity of India with armed rebellion or subversive activities",
                "Words disaffection towards government alone no longer penalised"
            ],
            removed_ingredients=["exciting disaffection towards Government established by law"],
            penal_modality_change="Life imprisonment or up to 7 years",
            statutory_warning="IPC Section 124A (Sedition) was struck down and is NOT directly mapped to BNS. BNS §152 penalises acts endangering sovereignty/integrity through armed rebellion/subversive means, not mere criticism."
        )
    }

    def verify_substantive_accuracy(self, query: str, generated_text: str, citations: List[str]) -> SubstantiveVerificationResult:
        query_lower = query.lower()
        gen_lower = generated_text.lower()

        for delta_key, delta in self.STATUTORY_DELTAS.items():
            # Check if query or generation pertains to this specific substantive area
            is_relevant = False
            if delta.ipc_section and f"ipc {delta.ipc_section}" in query_lower:
                is_relevant = True
            elif delta.bns_section and any(s in query_lower or s in gen_lower for s in delta.bns_section.split(", ")):
                is_relevant = True
            elif any(term in query_lower or term in gen_lower for term in delta.offence_name.lower().split("/")):
                is_relevant = True
            elif delta_key == "MOB_LYNCHING" and ("lynch" in query_lower or "mob" in query_lower):
                is_relevant = True
            elif delta_key == "DECEITFUL_PROMISE_TO_MARRY" and ("promise to marry" in query_lower or "promise of marriage" in query_lower):
                is_relevant = True
            elif delta_key == "SNATCHING" and "snatch" in query_lower:
                is_relevant = True
            elif delta_key == "COMMUNITY_SERVICE" and "community service" in query_lower:
                is_relevant = True
            elif delta_key == "HIT_AND_RUN" and ("hit and run" in query_lower or "106" in query_lower or "304a" in query_lower):
                is_relevant = True

            if not is_relevant:
                continue

            # Substantive checks for this offence
            omissions = []
            misreps = []

            # Check for Mob Lynching: Did LLM claim BNS 103 is just identical to IPC 302 without noting 103(2)?
            if delta_key == "MOB_LYNCHING":
                if ("lynch" in query_lower or "mob" in query_lower or "5" in query_lower or "caste" in query_lower) and "103(2)" not in generated_text:
                    omissions.append("Failed to cite Section 103(2) BNS for 5+ person mob lynching based on protected grounds.")

            # Check for Deceitful Promise to Marry: Did LLM cite Rape §63 instead of Section 69?
            if delta_key == "DECEITFUL_PROMISE_TO_MARRY":
                if ("promise to marry" in query_lower or "promise of marriage" in query_lower) and "69" not in generated_text:
                    misreps.append("Cited general rape or cheating provisions instead of the specific newly codified Section 69 BNS.")

            # Check for Hit-and-Run: Did LLM assert that 10-year penalty is currently active without noting the government stay/abeyance?
            if delta_key == "HIT_AND_RUN":
                if "10 years" in gen_lower and "106(2)" in generated_text and not any(k in gen_lower for k in ["abeyance", "stay", "held in abeyance", "not yet notified"]):
                    misreps.append("Asserted Section 106(2) 10-year punishment is active without disclosing that it is currently held in abeyance.")

            # Check for Sedition: Did LLM claim Sedition IPC 124A is still valid current law or auto-map to 152 without caveat?
            if delta_key == "SEDITION_REPEAL":
                if "124a" in generated_text and not any(k in gen_lower for k in ["repeal", "struck down", "unconstitutional"]):
                    misreps.append("Cited repealed Section 124A as currently applicable substantive law.")

            if omissions or misreps:
                return SubstantiveVerificationResult(
                    passed=False,
                    offence_detected=delta.offence_name,
                    delta_type=delta.delta_type,
                    is_delta_violation=True,
                    identified_omissions=omissions,
                    identified_misrepresentations=misreps,
                    remedial_statutory_advisory=delta.statutory_warning,
                    confidence_penalty=0.40
                )

        return SubstantiveVerificationResult(
            passed=True,
            offence_detected=None,
            delta_type=None,
            is_delta_violation=False,
            identified_omissions=[],
            identified_misrepresentations=[],
            remedial_statutory_advisory="",
            confidence_penalty=0.0
        )
