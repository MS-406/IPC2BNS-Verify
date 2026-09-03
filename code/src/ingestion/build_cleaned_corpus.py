"""
build_cleaned_corpus.py — Generates Cleaned Section Corpora (JSONL)

Populates data/01_cleaned/ipc_sections.jsonl and data/01_cleaned/bns_sections.jsonl
with structured statutory section records containing:
- section_number
- section_title
- section_text (complete statutory definition & punishment ingredients)
- chapter
- effective_date_range
"""

import os
import csv
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_cleaned_corpus")

# Key statutory definitions text repository for primary Indian criminal law provisions
IPC_DETAILED_PROVISIONS = {
    "302": {
        "title": "Punishment for murder",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine."
    },
    "300": {
        "title": "Murder",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "Except in the cases hereinafter excepted, culpable homicide is murder, if the act by which the death is caused is done with the intention of causing death, or with the intention of causing such bodily injury as the offender knows to be likely to cause the death of the person to whom the harm is caused, or with the intention of causing bodily injury to any person and the bodily injury intended to be inflicted is sufficient in the ordinary course of nature to cause death, or if the person committing the act knows that it is so imminently dangerous that it must, in all probability, cause death or such bodily injury as is likely to cause death, and commits such act without any excuse for incurring the risk of causing death or such injury as aforesaid."
    },
    "299": {
        "title": "Culpable homicide",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "Whoever causes death by doing an act with the intention of causing death, or with the intention of causing such bodily injury as is likely to cause death, or with the knowledge that he is likely by such act to cause death, commits the offence of culpable homicide."
    },
    "304A": {
        "title": "Causing death by negligence",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "Whoever causes the death of any person by doing any rash or negligent act not amounting to culpable homicide, shall be punished with imprisonment of either description for a term which may extend to two years, or with fine, or with both."
    },
    "304B": {
        "title": "Dowry death",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "(1) Where the death of a woman is caused by any burns or bodily injury or occurs otherwise than under normal circumstances within seven years of her marriage and it is shown that soon before her death she was subjected to cruelty or harassment by her husband or any relative of her husband for, or in connection with, any demand for dowry, such death shall be called 'dowry death', and such husband or relative shall be deemed to have caused her death. (2) Whoever commits dowry death shall be punished with imprisonment for a term which shall not be less than seven years but which may extend to imprisonment for life."
    },
    "307": {
        "title": "Attempt to murder",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "Whoever does any act with such intention or knowledge, and under such circumstances that, if he by that act caused death, he would be guilty of murder, shall be punished with imprisonment of either description for a term which may extend to ten years, and shall also be liable to fine; and if hurt is caused to any person by such act, the offender shall be liable either to imprisonment for life, or to such punishment as is hereinbefore mentioned."
    },
    "375": {
        "title": "Rape",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "A man is said to commit 'rape' if he penetrates his penis into the vagina, mouth, urethra or anus of a woman, or inserts any object or part of the body to any extent into the vagina, urethra or anus of a woman, or manipulates any part of the body of a woman so as to cause penetration into the vagina, urethra, anus or any part of body of such woman, or applies his mouth to the vagina, anus, urethra of a woman, against her will, without her consent, or with her consent when her consent has been obtained by putting her or any person in whom she is interested, in fear of death or of hurt."
    },
    "376": {
        "title": "Punishment for rape",
        "chapter": "Chapter XVI — Of Offences Affecting the Human Body",
        "text": "Whoever commits rape shall be punished with rigorous imprisonment of either description for a term which shall not be less than ten years, but which may extend to imprisonment for life, and shall also be liable to fine."
    },
    "378": {
        "title": "Theft",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "Whoever, intending to take dishonestly any moveable property out of the possession of any person without that person's consent, moves that property in order to such taking, is said to commit theft."
    },
    "379": {
        "title": "Punishment for theft",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "Whoever commits theft shall be punished with imprisonment of either description for a term which may extend to three years, or with fine, or with both."
    },
    "383": {
        "title": "Extortion",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "Whoever intentionally puts any person in fear of any injury to that person, or to any other, and thereby dishonestly induces the person so put in fear to deliver to any person any property or valuable security, or anything signed or sealed which may be converted into a valuable security, commits 'extortion'."
    },
    "390": {
        "title": "Robbery",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "In all robbery there is either theft or extortion. Theft is robbery if, in order to the committing of the theft, or in committing the theft, or in carrying away or attempting to carry away property obtained by the theft, the offender, for that end, voluntarily causes or attempts to cause to any person death or hurt or wrongful restraint, or fear of instant death or of instant hurt, or of instant wrongful restraint."
    },
    "391": {
        "title": "Dacoity",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "When five or more persons conjointly commit or attempt to commit a robbery, or where the whole number of persons conjointly committing or attempting to commit a robbery, and persons present and aiding such commission or attempt, amount to five or more, every person so committing, attempting or aiding, is said to commit 'dacoity'."
    },
    "415": {
        "title": "Cheating",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "Whoever, by deceiving any person, fraudulently or dishonestly induces the person so deceived to deliver any property to any person, or to consent that any person shall retain any property, or intentionally induces the person so deceived to do or omit to do anything which he would not do or omit if he were not so deceived, and which act or omission causes or is likely to cause damage or harm to that person in body, mind, reputation or property, is said to 'cheat'."
    },
    "420": {
        "title": "Cheating and dishonestly inducing delivery of property",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person, or to make, alter or destroy the whole or any part of a valuable security, or anything which is signed or sealed, and which is capable of being converted into a valuable security, shall be punished with imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine."
    },
    "463": {
        "title": "Forgery",
        "chapter": "Chapter XVIII — Of Offences Relating to Documents",
        "text": "Whoever makes any false documents or false electronic record or part of a document or electronic record, with intent to cause damage or injury, to the public or to any person, or to support any claim or title, or to cause any person to part with property, or to enter into any express or implied contract, or with intent to commit fraud or that fraud may be committed, commits forgery."
    },
    "499": {
        "title": "Defamation",
        "chapter": "Chapter XXI — Of Defamation",
        "text": "Whoever, by words either spoken or intended to be read, or by signs or by visible representations, makes or publishes any imputation concerning any person intending to harm, or knowing or having reason to believe that such imputation will harm, the reputation of such person, is said, except in the cases hereinafter expected, to defame that person."
    },
    "503": {
        "title": "Criminal intimidation",
        "chapter": "Chapter XXII — Of Criminal Intimidation, Insult and Annoyance",
        "text": "Whoever threatens another with any injury to his person, reputation or property, or to the person or reputation of any one in whom that person is interested, with intent to cause alarm to that person, or to cause that person to do any act which he is not legally bound to do, or to omit to do any act which that person is legally entitled to do, as the means of avoiding the execution of such threat, commits criminal intimidation."
    },
    "124A": {
        "title": "Sedition",
        "chapter": "Chapter VI — Of Offences Against the State",
        "text": "Whoever by words, either spoken or written, or by signs, or by visible representation, or otherwise, brings or attempts to bring into hatred or contempt, or excites or attempts to excite disaffection towards the Government established by law in India, shall be punished with imprisonment for life, to which fine may be added, or with imprisonment which may extend to three years, to which fine may be added, or with fine."
    },
    "33": {
        "title": "Act, Omission",
        "chapter": "Chapter II — General Explanations",
        "text": "The word 'act' denotes as well a series of acts as a single act: the word 'omission' denotes as well a series of omissions as a single omission."
    }
}

BNS_DETAILED_PROVISIONS = {
    "103": {
        "title": "Punishment for murder",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "text": "(1) Whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine. (2) When a group of five or more persons acting in concert commits murder on the ground of race, caste or community, sex, place of birth, language, personal belief or any other similar ground, each member of such group shall be punished with death or with imprisonment for life, and shall also be liable to fine."
    },
    "100": {
        "title": "Culpable homicide",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "text": "Whoever causes death by doing an act with the intention of causing death, or with the intention of causing such bodily injury as is likely to cause death, or with the knowledge that he is likely by such act to cause death, commits the offence of culpable homicide."
    },
    "106": {
        "title": "Causing death by negligence",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "text": "(1) Whoever causes the death of any person by doing any rash or negligent act not amounting to culpable homicide, shall be punished with imprisonment of either description for a term which may extend to five years, and shall also be liable to fine; and if such act is committed by a registered medical practitioner, he shall be punished with imprisonment up to two years. (2) Whoever causes the death of any person by rash and negligent driving of vehicle not amounting to culpable homicide, and escapes without reporting it to a police officer or Magistrate soon after the incident, shall be punished with imprisonment of either description for a term which may extend to ten years, and shall also be liable to fine."
    },
    "80": {
        "title": "Dowry death",
        "chapter": "Chapter V — Of Offences Against Women and Children",
        "text": "(1) Where the death of a woman is caused by any burns or bodily injury or occurs otherwise than under normal circumstances within seven years of her marriage and it is shown that soon before her death she was subjected to cruelty or harassment by her husband or any relative of her husband for, or in connection with, any demand for dowry, such death shall be called 'dowry death', and such husband or relative shall be deemed to have caused her death. (2) Whoever commits dowry death shall be punished with imprisonment for a term which shall not be less than seven years but which may extend to imprisonment for life."
    },
    "109": {
        "title": "Attempt to murder",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "text": "Whoever does any act with such intention or knowledge, and under such circumstances that, if he by that act caused death, he would be guilty of murder, shall be punished with imprisonment of either description for a term which may extend to ten years, and shall also be liable to fine; and if hurt is caused to any person by such act, the offender shall be liable either to imprisonment for life, or to such punishment as is hereinbefore mentioned."
    },
    "63": {
        "title": "Rape",
        "chapter": "Chapter V — Of Offences Against Women and Children",
        "text": "A man is said to commit 'rape' if he penetrates his penis into the vagina, mouth, urethra or anus of a woman; or inserts any object or part of body to any extent into the vagina, urethra or anus of a woman; or manipulates any part of the body of a woman so as to cause penetration; or applies his mouth to the vagina, anus, urethra of a woman, against her will or without her consent."
    },
    "64": {
        "title": "Punishment for rape",
        "chapter": "Chapter V — Of Offences Against Women and Children",
        "text": "(1) Whoever commits rape shall be punished with rigorous imprisonment of either description for a term which shall not be less than ten years, but which may extend to imprisonment for life, and shall also be liable to fine. (2) Whoever commits rape on a woman below twelve years of age shall be punished with rigorous imprisonment for a term which shall not be less than twenty years, but which may extend to imprisonment for life, or with death."
    },
    "69": {
        "title": "Sexual intercourse by employing deceitful means etc.",
        "chapter": "Chapter V — Of Offences Against Women and Children",
        "text": "Whoever, by deceitful means or making by promise to marry to a woman without any intention of fulfilling the same, and has sexual intercourse with her, such sexual intercourse not amounting to the offence of rape, shall be punished with imprisonment of either description for a term which may extend to ten years and shall also be liable to fine. Explanation.—'deceitful means' shall include the false promise of employment or promotion, or inducement or marrying after suppressing identity."
    },
    "303": {
        "title": "Theft",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "(1) Whoever, intending to take dishonestly any moveable property out of the possession of any person without that person's consent, moves that property in order to such taking, is said to commit theft. (2) Whoever commits theft shall be punished with imprisonment of either description for a term which may extend to three years, or with fine, or with both; and in case of second or subsequent conviction, with rigorous imprisonment for a term which shall not be less than one year but which may extend to five years, and with fine. Provided that where the value of stolen property is less than five thousand rupees, and the person has not been previously convicted, he may be punished with community service."
    },
    "308": {
        "title": "Extortion",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "(1) Whoever intentionally puts any person in fear of any injury to that person, or to any other, and thereby dishonestly induces the person so put in fear to deliver to any person any property or valuable security, commits 'extortion'. (2) Whoever commits extortion shall be punished with imprisonment of either description for a term which may extend to seven years, or with fine, or with both."
    },
    "309": {
        "title": "Robbery",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "In all robbery there is either theft or extortion. (4) Whoever commits robbery shall be punished with rigorous imprisonment for a term which may extend to ten years, and shall also be liable to fine; and, if the robbery be committed on the highway between sunset and sunrise, the imprisonment may be extended to fourteen years."
    },
    "310": {
        "title": "Dacoity",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "(1) When five or more persons conjointly commit or attempt to commit a robbery, every person so committing, attempting or aiding, is said to commit 'dacoity'. (2) Whoever commits dacoity shall be punished with imprisonment for life, or with rigorous imprisonment for a term which may extend to ten years, and shall also be liable to fine."
    },
    "318": {
        "title": "Cheating",
        "chapter": "Chapter XVII — Of Offences Against Property",
        "text": "(1) Whoever, by deceiving any person, fraudulently or dishonestly induces the person so deceived to deliver any property, is said to 'cheat'. (4) Whoever cheats and thereby dishonestly induces the person deceived to deliver any property, shall be punished with imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine."
    },
    "335": {
        "title": "Forgery",
        "chapter": "Chapter XVIII — Of Offences Relating to Documents",
        "text": "Whoever makes any false document or false electronic record with intent to cause damage or injury, to the public or to any person, commits forgery."
    },
    "356": {
        "title": "Defamation",
        "chapter": "Chapter XXI — Of Defamation",
        "text": "(1) Whoever, by words spoken or intended to be read, or by signs or visible representations, makes or publishes any imputation concerning any person intending to harm the reputation of such person, is said to defame that person. (2) Whoever defames another shall be punished with simple imprisonment for a term which may extend to two years, or with fine, or with both or with community service."
    },
    "351": {
        "title": "Criminal intimidation",
        "chapter": "Chapter XXII — Of Criminal Intimidation",
        "text": "(1) Whoever threatens another with any injury to his person, reputation or property with intent to cause alarm, commits criminal intimidation. (2) Whoever commits criminal intimidation shall be punished with imprisonment of either description for a term which may extend to two years, or with fine, or with both."
    },
    "111": {
        "title": "Organised crime",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "text": "(1) Any continuing unlawful activity including kidnapping, robbery, vehicle theft, extortion, land grabbing, contract killing, economic offence, cybercrimes, trafficking of persons or drugs by a group acting individually or jointly as a member of an organised crime syndicate shall constitute organised crime. (2) Whoever commits organised crime resulting in the death of any person shall be punished with death or imprisonment for life, and fine not less than ten lakh rupees."
    },
    "112": {
        "title": "Petty organised crime",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "text": "(1) Whoever, being a member of a group or gang, commits theft, snatching, cheating, unauthorized selling of tickets, betting or gambling shall be punished with imprisonment for a term which shall not be less than one year but which may extend to seven years, and with fine."
    },
    "113": {
        "title": "Terrorist act",
        "chapter": "Chapter VI — Of Offences Affecting the Human Body",
        "text": "(1) Whoever does any act with the intent to threaten or likely to threaten the unity, integrity, sovereignty, security, or economic security of India or with the intent to strike terror in the people shall be guilty of committing a terrorist act. (2) Whoever commits a terrorist act resulting in death shall be punished with death or imprisonment for life."
    },
    "152": {
        "title": "Act endangering sovereignty unity and integrity of India",
        "chapter": "Chapter VII — Of Offences Against the State",
        "text": "Whoever, purposely or knowingly, by words, either spoken or written, or by signs, or by visible representation, or by electronic communication or by use of financial mean, or otherwise, excites or attempts to excite, secession or armed rebellion or subversive activities, or encourages feelings of separatist activities or endangers sovereignty or unity and integrity of India; or indulges in or commits any such act shall be punished with imprisonment for life or with imprisonment which may extend to seven years, and shall also be liable to fine."
    },
    "2(1)": {
        "title": "Definition of 'act'",
        "chapter": "Chapter I — Preliminary",
        "text": "'act' denotes as well a series of acts as a single act."
    },
    "2(25)": {
        "title": "Definition of 'omission'",
        "chapter": "Chapter I — Preliminary",
        "text": "'omission' denotes as well a series of omissions as a single omission."
    }
}


def build_corpora(concordance_path: str, output_cleaned_dir: str):
    """
    Builds both ipc_sections.jsonl and bns_sections.jsonl from concordance entries
    and detailed statutory text.
    """
    os.makedirs(output_cleaned_dir, exist_ok=True)
    ipc_file = os.path.join(output_cleaned_dir, "ipc_sections.jsonl")
    bns_file = os.path.join(output_cleaned_dir, "bns_sections.jsonl")

    # Read concordance table
    ipc_records = {}
    bns_records = {}

    with open(concordance_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ipc_sec = row.get("ipc_section", "").strip()
            ipc_title = row.get("ipc_title", "").strip()
            bns_sec = row.get("bns_section", "").strip()
            bns_title = row.get("bns_title", "").strip()
            notes = row.get("notes", "").strip()
            rel_type = row.get("relationship_type", "").strip()

            if ipc_sec and ipc_sec not in ("-", "—", "N/A"):
                text_detail = IPC_DETAILED_PROVISIONS.get(ipc_sec, {})
                ipc_records[ipc_sec] = {
                    "act": "Indian Penal Code, 1860",
                    "section_number": ipc_sec,
                    "section_title": ipc_title or text_detail.get("title", f"Section {ipc_sec}"),
                    "chapter": text_detail.get("chapter", "Indian Penal Code Provisions"),
                    "section_text": text_detail.get("text", f"Statutory provision for IPC Section {ipc_sec}: {ipc_title}. {notes}".strip()),
                    "effective_date_range": {"start": "1860-10-06", "end": "2024-06-30"},
                    "relationship_type": rel_type,
                    "mapped_to_bns": bns_sec,
                    "notes": notes,
                    "created_at": datetime.now().isoformat()
                }

            if bns_sec and bns_sec not in ("-", "—", "REPEALED", "N/A"):
                text_detail = BNS_DETAILED_PROVISIONS.get(bns_sec, {})
                bns_records[bns_sec] = {
                    "act": "Bharatiya Nyaya Sanhita, 2023",
                    "section_number": bns_sec,
                    "section_title": bns_title or text_detail.get("title", f"Section {bns_sec}"),
                    "chapter": text_detail.get("chapter", "Bharatiya Nyaya Sanhita Provisions"),
                    "section_text": text_detail.get("text", f"Statutory provision for BNS Section {bns_sec}: {bns_title}. {notes}".strip()),
                    "effective_date_range": {"start": "2024-07-01", "end": "9999-12-31"},
                    "relationship_type": rel_type,
                    "mapped_from_ipc": ipc_sec,
                    "notes": notes,
                    "created_at": datetime.now().isoformat()
                }

    # Write IPC JSONL
    with open(ipc_file, "w", encoding="utf-8") as f:
        for sec, record in sorted(ipc_records.items()):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info(f"Written {len(ipc_records)} sections to {ipc_file}")

    # Write BNS JSONL
    with open(bns_file, "w", encoding="utf-8") as f:
        for sec, record in sorted(bns_records.items()):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info(f"Written {len(bns_records)} sections to {bns_file}")

    return len(ipc_records), len(bns_records)


if __name__ == "__main__":
    root = os.environ.get("IPC2BNS_PROJECT_ROOT", "D:/college 4th year/research paper/NLP_rs")
    concordance = os.path.join(root, "data/02_ground_truth/concordance_v1.csv")
    cleaned_dir = os.path.join(root, "data/01_cleaned")
    build_corpora(concordance, cleaned_dir)
