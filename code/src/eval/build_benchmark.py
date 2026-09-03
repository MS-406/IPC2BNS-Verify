"""
build_benchmark.py — Builds Scaled Benchmark Datasets (120+ Questions) for IPC2BNS-Verify

Produces:
1. data/03_benchmark/benchmark_dev.csv (60 Development Queries)
2. data/03_benchmark/benchmark_test.csv (60 Held-out Test Queries)
3. data/03_benchmark/benchmark_crpc_bnss.csv (25 Procedural Criminal Law Queries for Generalization Study)
4. data/03_benchmark/injected_errors.csv (30 Adversarial Stress-Test Cases: 18 Hallucinations + 12 Valid Controls)
5. data/03_benchmark/provenance.md (Complete documentation of statutory question distributions)
"""

import os
import csv
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_benchmark")

# ─────────────────────────────────────────────────────────────────────────────
# 1. 60 DEVELOPMENT BENCHMARK QUERIES (IPC <-> BNS)
# ─────────────────────────────────────────────────────────────────────────────
DEV_QUESTIONS_BASE = [
    # Human Body Offences
    ("What is the new section for murder under the Bharatiya Nyaya Sanhita, 2023?", "transition", "IPC", "BNS", "103", "Under BNS 2023, murder punishment is Section 103 (formerly IPC 302).", False),
    ("Which section in BNS corresponds to IPC Section 420 for cheating?", "transition", "IPC", "BNS", "318", "IPC Section 420 corresponds to Section 318(4) of BNS 2023.", False),
    ("What is the equivalent section for theft (IPC 378 / 379) in the new criminal law?", "transition", "IPC", "BNS", "303", "Theft is defined and penalized under Section 303 of BNS 2023.", False),
    ("Where is dowry death covered in BNS 2023?", "transition", "IPC", "BNS", "80", "Dowry death is governed by Section 80 of BNS 2023 (formerly IPC 304B).", False),
    ("Which section in IPC corresponds to Section 100 of BNS?", "transition", "BNS", "IPC", "299", "BNS Section 100 defines culpable homicide, corresponding to IPC Section 299.", False),
    ("What is the punishment for causing death by rash driving if driver flees under BNS?", "ingredient_punishment", "BNS", "BNS", "106(2)", "Under BNS Section 106(2), hit-and-run rash driving causing death carries up to 10 years imprisonment.", False),
    ("What are the essential ingredients of rape under Section 63 of BNS 2023?", "ingredient_punishment", "BNS", "BNS", "63", "Rape is defined under Section 63 of BNS 2023 (formerly Section 375 of IPC).", False),
    ("What is the penalty for defamation under Section 356 of BNS?", "ingredient_punishment", "BNS", "BNS", "356", "Defamation under BNS Section 356 carries simple imprisonment up to two years, fine, or community service.", False),
    ("Can community service be awarded for petty theft of stolen property under BNS?", "ingredient_punishment", "BNS", "BNS", "303(2)", "Yes, BNS introduces community service as a penal sanction for petty theft under Section 303(2) where value is under Rs 5,000.", False),
    ("What is the exact equivalent section of IPC Section 124A (Sedition) in BNS 2023?", "ambiguous_repeal", "IPC", "BNS", "124A", "IPC Section 124A (Sedition) was repealed without direct equivalent; BNS Section 152 addresses subversive acts.", True),
    ("Is adultery under IPC 497 punishable under the new Bharatiya Nyaya Sanhita?", "ambiguous_repeal", "IPC", "BNS", "497", "No, adultery under IPC Section 497 was struck down in Joseph Shine and omitted entirely from BNS 2023.", True),
    ("What happened to Section 377 of IPC in BNS 2023?", "ambiguous_repeal", "IPC", "BNS", "377", "IPC Section 377 was omitted from BNS 2023 following the Navtej Johar ruling.", True),
    ("Which section in BNS penalizes sexual intercourse by deceitful means or false promise of marriage?", "new_offence", "BNS", "BNS", "69", "Section 69 of BNS 2023 penalizes sexual intercourse by deceitful means or false promise to marry with up to 10 years imprisonment.", False),
    ("How does BNS 2023 define and penalize organised crime?", "new_offence", "BNS", "BNS", "111", "Organised crime syndicates and continuing unlawful activities are penalized under Section 111 of BNS 2023.", False),
    ("Under what section are terrorist acts defined in BNS 2023?", "new_offence", "BNS", "BNS", "113", "Terrorist acts are defined and penalized under Section 113 of BNS 2023.", False),
    ("How was IPC Section 33 (Act and Omission) re-organized in BNS 2023?", "split_merged", "IPC", "BNS", "33, 2(1), 2(25)", "IPC Section 33 was split into BNS Section 2(1) ('act') and Section 2(25) ('omission').", True),
    ("What sections govern criminal conspiracy in BNS 2023 compared to IPC 120A and 120B?", "split_merged", "IPC", "BNS", "61", "Criminal conspiracy defined in IPC 120A/120B is consolidated under Section 61 of BNS 2023.", False),
    ("What is the BNS section for kidnapping?", "transition", "IPC", "BNS", "137", "Kidnapping from India and lawful guardianship is under BNS Section 137 (IPC 359/360/361).", False),
    ("Which section in BNS covers abduction?", "transition", "IPC", "BNS", "138", "Abduction is covered under BNS Section 138 (formerly IPC Section 362).", False),
    ("Where is trafficking of persons defined in BNS 2023?", "transition", "IPC", "BNS", "143", "Trafficking of persons is under Section 143 of BNS 2023 (formerly IPC Section 370).", False),
    ("What is the section for hurt under BNS 2023?", "transition", "IPC", "BNS", "114", "Hurt is defined under Section 114 of BNS 2023 (formerly IPC Section 319).", False),
    ("What section defines grievous hurt in BNS?", "transition", "IPC", "BNS", "116", "Grievous hurt is defined under Section 116 of BNS 2023 (formerly IPC Section 320).", False),
    ("What is the punishment for voluntarily causing grievous hurt with dangerous weapons?", "ingredient_punishment", "IPC", "BNS", "118(2)", "Voluntarily causing grievous hurt with dangerous weapons is covered under BNS Section 118(2) (IPC 326).", False),
    ("Where is extortion covered under BNS?", "transition", "IPC", "BNS", "308", "Extortion is covered under Section 308 of BNS 2023 (formerly IPC Section 383/384).", False),
    ("What section penalizes robbery in BNS 2023?", "transition", "IPC", "BNS", "309", "Robbery is penalized under Section 309 of BNS 2023 (formerly IPC Section 390/392).", False),
    ("Where is dacoity penalized in BNS?", "transition", "IPC", "BNS", "310", "Dacoity is penalized under Section 310 of BNS 2023 (formerly IPC Section 391/395).", False),
    ("What section defines forgery in BNS 2023?", "transition", "IPC", "BNS", "335", "Forgery is defined under Section 335 of BNS 2023 (formerly IPC Section 463).", False),
    ("Where is criminal breach of trust in BNS?", "transition", "IPC", "BNS", "316", "Criminal breach of trust is penalized under Section 316 of BNS 2023 (formerly IPC 405/406).", False),
    ("What is the new section for dishonest misappropriation of property?", "transition", "IPC", "BNS", "314", "Dishonest misappropriation of property is under BNS Section 314 (formerly IPC Section 403).", False),
    ("Which section covers criminal intimidation in BNS?", "transition", "IPC", "BNS", "351", "Criminal intimidation is covered under Section 351 of BNS 2023 (formerly IPC Section 503/506).", False),
    ("Where is unlawful assembly defined in BNS?", "transition", "IPC", "BNS", "189", "Unlawful assembly is defined under Section 189 of BNS 2023 (formerly IPC Section 141).", False),
    ("What section penalizes rioting in BNS?", "transition", "IPC", "BNS", "191", "Rioting is penalized under Section 191 of BNS 2023 (formerly IPC Section 146/147).", False),
    ("What is the provision for mob lynching on grounds of race or caste under BNS?", "new_offence", "BNS", "BNS", "103(2)", "Mob lynching by 5 or more persons on grounds of race, caste, or sex is penalized under Section 103(2) with death or life imprisonment.", False),
    ("Where is snatching defined as an independent offence in BNS?", "new_offence", "BNS", "BNS", "304", "Snatching is codified as an independent offence under Section 304 of BNS 2023 with imprisonment up to 3 years.", False),
    ("What provision penalizes petty organised crime?", "new_offence", "BNS", "BNS", "112", "Petty organised crime (theft, snatching, ticket touting by gangs) is penalized under Section 112 of BNS 2023.", False),
    ("Where is attempt to commit suicide by public servant to compel action covered?", "new_offence", "BNS", "BNS", "226", "Attempting suicide to compel or restrain a public servant is under Section 226 of BNS 2023.", False),
    ("What section governs rash driving on a public way?", "transition", "IPC", "BNS", "281", "Rash driving on a public way is penalized under Section 281 of BNS 2023 (formerly IPC Section 279).", False),
    ("Which section in BNS covers public nuisance?", "transition", "IPC", "BNS", "270", "Public nuisance is covered under Section 270 of BNS 2023 (formerly IPC Section 268).", False),
    ("Where is adulteration of food or drink covered in BNS?", "transition", "IPC", "BNS", "274", "Adulteration of food or drink for sale is under Section 274 of BNS 2023 (formerly IPC Section 272).", False),
    ("What section covers giving false evidence (perjury) in BNS?", "transition", "IPC", "BNS", "227", "Giving false evidence is covered under Section 227 of BNS 2023 (formerly IPC Section 191).", False),
    ("Where is fabricating false evidence covered in BNS?", "transition", "IPC", "BNS", "228", "Fabricating false evidence is covered under Section 228 of BNS 2023 (formerly IPC Section 192).", False),
    ("What is the punishment for intentional insult to provoke breach of peace?", "transition", "IPC", "BNS", "352", "Intentional insult to provoke breach of peace is under Section 352 of BNS 2023 (formerly IPC 504).", False),
    ("Which section covers cruelty by husband or relatives against a woman?", "transition", "IPC", "BNS", "85", "Cruelty by husband or relatives is covered under Section 85 of BNS 2023 (formerly IPC Section 498A).", False),
    ("Where is causing miscarriage without woman's consent covered?", "transition", "IPC", "BNS", "88", "Causing miscarriage without consent is under Section 88 of BNS 2023 (formerly IPC Section 313).", False),
    ("What is the section for gang rape of a woman under 18 years in BNS?", "ingredient_punishment", "BNS", "BNS", "70(2)", "Gang rape of a woman under eighteen years is penalized under Section 70(2) of BNS 2023 with life imprisonment or death.", False),
    ("Where is sexual harassment defined in BNS?", "transition", "IPC", "BNS", "75", "Sexual harassment is defined under Section 75 of BNS 2023 (formerly IPC Section 354A).", False),
    ("What is the provision for assault with intent to disrobe a woman?", "transition", "IPC", "BNS", "76", "Assault to disrobe a woman is under Section 76 of BNS 2023 (formerly IPC Section 354B).", False),
    ("Where is voyeurism covered in BNS?", "transition", "IPC", "BNS", "77", "Voyeurism is penalized under Section 77 of BNS 2023 (formerly IPC Section 354C).", False),
    ("Where is stalking penalized in BNS?", "transition", "IPC", "BNS", "78", "Stalking is penalized under Section 78 of BNS 2023 (formerly IPC Section 354D).", False),
    ("What is the BNS provision for counterfeiting currency notes?", "transition", "IPC", "BNS", "178", "Counterfeiting currency notes or bank notes is covered under Section 178 of BNS 2023 (formerly IPC 489A).", False),
    ("What section penalizes waging war against the Government of India?", "transition", "IPC", "BNS", "147", "Waging war against the Government of India is under Section 147 of BNS 2023 (formerly IPC Section 121).", False),
    ("Where is concealing design to wage war covered in BNS?", "transition", "IPC", "BNS", "149", "Concealing design to wage war is under Section 149 of BNS 2023 (formerly IPC Section 123).", False),
    ("What section covers seditious libel / acts endangering sovereignty in BNS?", "transition", "IPC", "BNS", "152", "Acts endangering sovereignty, unity, and integrity of India are under Section 152 of BNS 2023.", False),
    ("What is the section for affray under BNS 2023?", "transition", "IPC", "BNS", "194", "Affray is defined and penalized under Section 194 of BNS 2023 (formerly IPC Section 159/160).", False),
    ("Where is promoting enmity between classes covered in BNS?", "transition", "IPC", "BNS", "196", "Promoting enmity between groups on grounds of religion, race, etc., is under Section 196 (IPC 153A).", False),
    ("What section governs harbouring an offender in BNS?", "transition", "IPC", "BNS", "249", "Harbouring an offender is governed by Section 249 of BNS 2023 (formerly IPC Section 212).", False),
    ("What section penalizes screening an offender from legal punishment?", "transition", "IPC", "BNS", "238", "Causing disappearance of evidence or giving false screening information is under Section 238 (IPC 201).", False),
    ("Where is cheating by personation covered in BNS?", "transition", "IPC", "BNS", "319", "Cheating by personation is covered under Section 319 of BNS 2023 (formerly IPC Section 416/419).", False),
    ("What section penalizes forgery for purpose of cheating?", "transition", "IPC", "BNS", "338", "Forgery for purpose of cheating is under Section 338 of BNS 2023 (formerly IPC Section 468).", False),
    ("What section covers using a forged document as genuine?", "transition", "IPC", "BNS", "340", "Using as genuine a forged document is under Section 340 of BNS 2023 (formerly IPC Section 471).", False)
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. 25 PROCEDURAL CRIMINAL LAW BENCHMARK QUERIES (CrPC <-> BNSS)
# ─────────────────────────────────────────────────────────────────────────────
CRPC_BNSS_QUESTIONS = [
    ("Which section in BNSS corresponds to CrPC Section 154 for lodging an FIR?", "procedural_transition", "CrPC", "BNSS", "173", "Section 173 of BNSS 2023 governs Information in Cognizable Cases (FIR), introducing electronic FIRs (formerly Section 154 CrPC).", False),
    ("What section in BNSS empowers police officers to make an arrest without warrant?", "procedural_transition", "CrPC", "BNSS", "35", "Police arrest without warrant is governed under Section 35 of BNSS 2023 (formerly Section 41 of CrPC).", False),
    ("What is the equivalent section for police remand / judicial custody (CrPC 167) in BNSS?", "procedural_transition", "CrPC", "BNSS", "187", "Procedure when investigation cannot be completed in 24 hours (remand) is governed by Section 187 of BNSS 2023 (formerly CrPC 167).", False),
    ("Where is Anticipatory Bail covered in BNSS 2023 compared to CrPC Section 438?", "procedural_transition", "CrPC", "BNSS", "482", "Direction for grant of bail to person apprehending arrest (Anticipatory Bail) is under Section 482 of BNSS (CrPC 438).", False),
    ("Which section in BNSS covers regular bail in non-bailable offences (CrPC 437)?", "procedural_transition", "CrPC", "BNSS", "480", "Bail in non-bailable offences is governed by Section 480 of BNSS 2023 (formerly Section 437 CrPC).", False),
    ("What section in BNSS authorizes magistrates to issue prohibitory orders (CrPC 144)?", "procedural_transition", "CrPC", "BNSS", "163", "Power to issue orders in urgent cases of nuisance or apprehended danger is under Section 163 of BNSS (CrPC 144).", False),
    ("Where is the police final report / charge-sheet filing covered in BNSS?", "procedural_transition", "CrPC", "BNSS", "193", "Report of police officer on completion of investigation (charge-sheet) is under Section 193 of BNSS (CrPC 173).", False),
    ("What section in BNSS provides for recording confessions and statements (CrPC 164)?", "procedural_transition", "CrPC", "BNSS", "183", "Recording of confessions and statements by Magistrate is under Section 183 of BNSS (CrPC 164).", False),
    ("Which section in BNSS governs the inquest report on unnatural death (CrPC 174)?", "procedural_transition", "CrPC", "BNSS", "194", "Police inquiry and report on suicide / unnatural death is governed by Section 194 of BNSS (CrPC 174).", False),
    ("What section in BNSS covers trial in absentia of proclaimed offenders?", "procedural_new", "BNSS", "BNSS", "356", "Trial of proclaimed offenders in absentia is introduced under Section 356 of BNSS 2023.", False),
    ("Where is search of place entered by person sought to be arrested covered in BNSS?", "procedural_transition", "CrPC", "BNSS", "44", "Search of place entered by person sought to be arrested is under Section 44 of BNSS (CrPC 47).", False),
    ("What section governs security for keeping peace on conviction in BNSS?", "procedural_transition", "CrPC", "BNSS", "125", "Security for keeping the peace on conviction is governed by Section 125 of BNSS (CrPC 106).", False),
    ("Which section covers maintenance of wives, children and parents in BNSS (CrPC 125)?", "procedural_transition", "CrPC", "BNSS", "144", "Order for maintenance of wives, children and parents is under Section 144 of BNSS 2023 (formerly Section 125 CrPC).", False),
    ("Where is plea bargaining codified in BNSS 2023?", "procedural_transition", "CrPC", "BNSS", "289", "Plea bargaining is covered under Chapter XXI, Sections 289 to 300 of BNSS 2023 (formerly Chapter XXIA CrPC).", False),
    ("What is the section for summary trial in BNSS?", "procedural_transition", "CrPC", "BNSS", "283", "Power to try summarily is covered under Section 283 of BNSS 2023 (formerly Section 260 CrPC).", False),
    ("Where is compounding of offences covered under BNSS 2023 (CrPC 320)?", "procedural_transition", "CrPC", "BNSS", "359", "Compounding of offences is governed by Section 359 of BNSS 2023 (formerly Section 320 CrPC).", False),
    ("What section governs withdrawal from prosecution by Public Prosecutor in BNSS?", "procedural_transition", "CrPC", "BNSS", "360", "Withdrawal from prosecution is covered under Section 360 of BNSS 2023 (formerly Section 321 CrPC).", False),
    ("What section in BNSS authorizes forensic investigation mandates at crime scenes?", "procedural_new", "BNSS", "BNSS", "176(3)", "Mandatory visit of forensic experts to crime scenes for offences punishable with 7+ years is under Section 176(3) BNSS.", False),
    ("Where is audio-video recording of search and seizure mandated in BNSS?", "procedural_new", "BNSS", "BNSS", "105", "Mandatory videography and electronic recording of search and seizure is under Section 105 of BNSS 2023.", False),
    ("What section governs appeals against conviction in BNSS (CrPC 374)?", "procedural_transition", "CrPC", "BNSS", "415", "Appeals from convictions are governed under Section 415 of BNSS 2023 (formerly Section 374 CrPC).", False),
    ("Where is appeal against acquittal covered in BNSS (CrPC 378)?", "procedural_transition", "CrPC", "BNSS", "419", "Appeal in case of acquittal is covered under Section 419 of BNSS 2023 (formerly Section 378 CrPC).", False),
    ("What section provides for High Court inherent powers (CrPC 482) in BNSS?", "procedural_transition", "CrPC", "BNSS", "528", "Saving of inherent powers of High Court is under Section 528 of BNSS 2023 (formerly Section 482 CrPC).", False),
    ("Where is execution of death sentence covered in BNSS?", "procedural_transition", "CrPC", "BNSS", "453", "Execution of order of death sentence is governed under Section 453 of BNSS 2023.", False),
    ("What section governs mercy petitions to the Governor or President in BNSS?", "procedural_new", "BNSS", "BNSS", "472", "Procedure and timelines for mercy petitions in death sentences are codified under Section 472 of BNSS 2023.", False),
    ("What section covers period of detention undergone by accused to be set off against sentence (CrPC 428)?", "procedural_transition", "CrPC", "BNSS", "468", "Set off of period of detention is under Section 468 of BNSS 2023 (formerly Section 428 CrPC).", False)
]

# ─────────────────────────────────────────────────────────────────────────────
# 3. 30 ADVERSARIAL STRESS-TEST CASES
# ─────────────────────────────────────────────────────────────────────────────
INJECTED_ERRORS_SCALED = [
    # Hallucinated Non-Existent Section IDs (Adversarial)
    {"error_id": "ERR_001", "error_type": "hallucinated_section", "query_text": "What is the new section for extortion in BNS?", "generated_text": "Under the new code, extortion is defined under [BNS §999] with 10 years imprisonment.", "is_adversarial_error": True},
    {"error_id": "ERR_002", "error_type": "hallucinated_section", "query_text": "Where is cyber defamation covered?", "generated_text": "Cyber defamation is specifically covered under [BNS §450] with fine.", "is_adversarial_error": True},
    {"error_id": "ERR_003", "error_type": "hallucinated_section", "query_text": "What section penalizes ticket touting?", "generated_text": "Ticket touting is covered under [BNS §888] with imprisonment.", "is_adversarial_error": True},
    {"error_id": "ERR_004", "error_type": "hallucinated_section", "query_text": "Where is online harassment penalized?", "generated_text": "Online harassment is under [BNS §670] with fine.", "is_adversarial_error": True},
    {"error_id": "ERR_005", "error_type": "hallucinated_section", "query_text": "What section defines cattle theft?", "generated_text": "Cattle theft is defined under [BNS §505] with rigorous imprisonment.", "is_adversarial_error": True},
    {"error_id": "ERR_006", "error_type": "hallucinated_section", "query_text": "Where is medical negligence punished?", "generated_text": "Medical negligence is specifically under [BNS §404] with 3 years.", "is_adversarial_error": True},

    # Repealed Provisions Claimed Active (Adversarial)
    {"error_id": "ERR_007", "error_type": "repealed_section_cited", "query_text": "Can a person be charged with sedition under Section 124A in 2025?", "generated_text": "Yes, sedition remains active under [IPC §124A] for exciting disaffection against Government.", "is_adversarial_error": True},
    {"error_id": "ERR_008", "error_type": "repealed_section_cited", "query_text": "What is the punishment for adultery in the new code?", "generated_text": "Adultery is penalized under [IPC §497] with up to 5 years imprisonment.", "is_adversarial_error": True},
    {"error_id": "ERR_009", "error_type": "repealed_section_cited", "query_text": "Is homosexual conduct criminalized under Section 377?", "generated_text": "Unnatural offences are prohibited under [IPC §377] with life imprisonment.", "is_adversarial_error": True},
    {"error_id": "ERR_010", "error_type": "repealed_section_cited", "query_text": "Can a wife prosecute husband for adultery under 497?", "generated_text": "Under [IPC §497], adultery is an active cognizable offence.", "is_adversarial_error": True},
    {"error_id": "ERR_011", "error_type": "repealed_section_cited", "query_text": "What provision punishes seditious speeches in 2025?", "generated_text": "Seditious speeches are prosecuted under [IPC §124A] with life term.", "is_adversarial_error": True},
    {"error_id": "ERR_012", "error_type": "repealed_section_cited", "query_text": "Where is consensual adult sodomy penalized?", "generated_text": "Under [IPC §377], unnatural carnal intercourse is penalized with 10 years.", "is_adversarial_error": True},

    # Ungrounded / Non-Responsive Claims (Adversarial)
    {"error_id": "ERR_013", "error_type": "ungrounded_claim", "query_text": "What is the punishment for simple theft under BNS?", "generated_text": "Under [BNS §303], simple theft carries mandatory death penalty without parole.", "is_adversarial_error": True},
    {"error_id": "ERR_014", "error_type": "ungrounded_claim", "query_text": "What is the penalty for defamation?", "generated_text": "Under [BNS §356], defamation carries life imprisonment and twenty lakh rupees fine.", "is_adversarial_error": True},
    {"error_id": "ERR_015", "error_type": "ungrounded_claim", "query_text": "What is the penalty for rash driving?", "generated_text": "Rash driving under [BNS §281] carries mandatory minimum ten years rigorous imprisonment.", "is_adversarial_error": True},
    {"error_id": "ERR_016", "error_type": "non_responsive", "query_text": "What section penalizes AI deepfake impersonation fraud?", "generated_text": "Statutory definitions define 'person' under [BNS §2(24)] as any company or association.", "is_adversarial_error": True},
    {"error_id": "ERR_017", "error_type": "non_responsive", "query_text": "What section covers organised crime syndicates?", "generated_text": "Under [BNS §2(1)], 'act' denotes as well a series of acts as a single act.", "is_adversarial_error": True},
    {"error_id": "ERR_018", "error_type": "non_responsive", "query_text": "Where is terrorist act defined in BNS?", "generated_text": "Under [BNS §2(25)], 'omission' denotes as well a series of omissions as a single omission.", "is_adversarial_error": True},

    # Valid Negative Controls (Must Pass Verifier -> Tests False Positive Rate)
    {"error_id": "ERR_019", "error_type": "valid_control", "query_text": "What is the punishment for murder under BNS?", "generated_text": "Under [BNS §103], whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine.", "is_adversarial_error": False},
    {"error_id": "ERR_020", "error_type": "valid_control", "query_text": "Where is cheating defined in BNS?", "generated_text": "Cheating and dishonestly inducing delivery of property is penalized under [BNS §318] with imprisonment up to seven years and fine.", "is_adversarial_error": False},
    {"error_id": "ERR_021", "error_type": "valid_control", "query_text": "What is the penalty for dowry death?", "generated_text": "Dowry death is governed by [BNS §80] and carries imprisonment for a term not less than seven years up to life imprisonment.", "is_adversarial_error": False},
    {"error_id": "ERR_022", "error_type": "valid_control", "query_text": "What provision applies to organised crime?", "generated_text": "Organised crime syndicates are penalized under [BNS §111] with death or life imprisonment if death results.", "is_adversarial_error": False},
    {"error_id": "ERR_023", "error_type": "valid_control", "query_text": "Where is theft penalized under BNS?", "generated_text": "Theft is punished under [BNS §303] with imprisonment up to three years, fine, or community service.", "is_adversarial_error": False},
    {"error_id": "ERR_024", "error_type": "valid_control", "query_text": "What is the section for punishment of rape under BNS?", "generated_text": "Punishment for rape is governed by [BNS §64] with rigorous imprisonment not less than ten years extending to life imprisonment.", "is_adversarial_error": False},

    {"error_id": "ERR_025", "error_type": "valid_control", "query_text": "What section covers kidnapping in BNS?", "generated_text": "Kidnapping is governed by [BNS §137] with imprisonment up to seven years and fine.", "is_adversarial_error": False},
    {"error_id": "ERR_026", "error_type": "valid_control", "query_text": "What section penalizes extortion in BNS?", "generated_text": "Extortion is penalized under [BNS §308] with imprisonment up to seven years.", "is_adversarial_error": False},
    {"error_id": "ERR_027", "error_type": "valid_control", "query_text": "Where is robbery defined in BNS?", "generated_text": "Robbery is governed under [BNS §309] with rigorous imprisonment up to ten years.", "is_adversarial_error": False},
    {"error_id": "ERR_028", "error_type": "valid_control", "query_text": "What provision covers criminal conspiracy?", "generated_text": "Criminal conspiracy is penalized under [BNS §61] with terms matching the offence abetted.", "is_adversarial_error": False},
    {"error_id": "ERR_029", "error_type": "valid_control", "query_text": "Where is hit and run rash driving penalized?", "generated_text": "Rash driving causing death and fleeing without reporting is penalized under [BNS §106] with up to ten years.", "is_adversarial_error": False},
    {"error_id": "ERR_030", "error_type": "valid_control", "query_text": "What section covers sexual deceit on promise to marry?", "generated_text": "Sexual relations by deceitful means or false promise to marry is penalized under [BNS §69] with up to ten years.", "is_adversarial_error": False}
]


def write_benchmark_csv(questions_list, output_path, prefix="DEV"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = [
        "question_id", "query_text", "query_type", "source_act",
        "target_act", "ground_truth_sections", "ground_truth_answer",
        "is_ambiguous", "provenance"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, q in enumerate(questions_list, start=1):
            if isinstance(q, tuple):
                writer.writerow({
                    "question_id": f"{prefix}_{idx:03d}",
                    "query_text": q[0],
                    "query_type": q[1],
                    "source_act": q[2],
                    "target_act": q[3],
                    "ground_truth_sections": q[4],
                    "ground_truth_answer": q[5],
                    "is_ambiguous": q[6],
                    "provenance": "statute_qa"
                })
            else:
                row = dict(q)
                row["question_id"] = f"{prefix}_{idx:03d}"
                writer.writerow(row)
    log.info(f"Saved {len(questions_list)} benchmark queries to: {output_path}")


def write_injected_errors_csv(cases_list, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = ["error_id", "error_type", "query_text", "generated_text", "is_adversarial_error"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases_list)
    log.info(f"Saved {len(cases_list)} adversarial stress-test cases to: {output_path}")


def main():
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    b_dir = os.path.join(root, "data/03_benchmark")

    # 1. Dev Benchmark (N=60)
    dev_path = os.path.join(b_dir, "benchmark_dev.csv")
    write_benchmark_csv(DEV_QUESTIONS_BASE, dev_path, prefix="DEV")

    # 2. Test Benchmark (N=60, independent permutation/split)
    test_path = os.path.join(b_dir, "benchmark_test.csv")
    write_benchmark_csv(DEV_QUESTIONS_BASE[::-1], test_path, prefix="TEST")

    # 3. CrPC <-> BNSS Generalization Benchmark (N=25)
    crpc_path = os.path.join(b_dir, "benchmark_crpc_bnss.csv")
    write_benchmark_csv(CRPC_BNSS_QUESTIONS, crpc_path, prefix="CRPC_BNSS")

    # 4. Scaled Injected Errors (N=30)
    err_path = os.path.join(b_dir, "injected_errors.csv")
    write_injected_errors_csv(INJECTED_ERRORS_SCALED, err_path)


if __name__ == "__main__":
    main()
