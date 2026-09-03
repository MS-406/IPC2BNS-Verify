# 📖 Plain-English Research Guide: IPC2BNS-Verify

**Paper Title:** IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions  
**Field:** Artificial Intelligence / Natural Language Processing (NLP) & Legal Technology  
**Core Law Transition:** Indian Penal Code (IPC 1860) $\rightarrow$ Bharatiya Nyaya Sanhita (BNS 2023) & CrPC (1973) $\rightarrow$ BNSS (2023)  

---

## 🌟 1. The Big Picture (What is this project about?)

On **July 1, 2024**, India underwent its biggest legal overhaul in over 160 years:
* The 1860 British-era **Indian Penal Code (IPC)** was replaced by the **Bharatiya Nyaya Sanhita (BNS)**.
* The 1973 **Code of Criminal Procedure (CrPC)** was replaced by the **Bharatiya Nagarik Suraksha Sanhita (BNSS)**.

Because of this, section numbers that everyone used for decades changed completely:
* *Murder* moved from **IPC Section 302** $\rightarrow$ **BNS Section 103**.
* *Cheating* moved from **IPC Section 420** $\rightarrow$ **BNS Section 318**.
* *Filing an FIR* moved from **CrPC Section 154** $\rightarrow$ **BNSS Section 173**.
* *Sedition (IPC 124A)* and *Adultery (IPC 497)* were **completely repealed/struck down**.

---

## ⚠️ 2. The Problem with AI Models (Why Standard AI Fails)

If you ask ChatGPT, GPT-4, LLaMA, or Gemini a legal question today about Indian law, they fail badly because:

1. **Historical Inertia (Living in the Past):**
   * These AI models were trained on millions of internet legal documents written between 1860 and 2023. Over **99% of their knowledge has old IPC sections**.
   * When asked a 2025 question, unassisted AI models default to old IPC numbers **90% of the time** (only **10.0% accuracy** on new law).
2. **Force-Mapping Repealed Laws (Inventing Fake Equivalents):**
   * If asked *"What is the BNS section for Sedition?"*, standard RAG tools force-map Sedition to an unrelated new section, even though Sedition was deliberately repealed!
3. **Right Section, Wrong Question:**
   * Models sometimes cite a real section (like the general definition of a "Person") when you actually asked about "AI Deepfake Fraud".
4. **Cross-Code Contradictions:**
   * AI models mix and match contradictory citations (e.g. claiming *"Cheating is under BNS 318 and was formerly IPC 302 (Murder)"*).

---

## 🛡️ 3. Our Solution: IPC2BNS-Verify (How it Works)

Instead of trusting the AI model blindly, **IPC2BNS-Verify** builds a **Neuro-Symbolic Verification Safety Net** around the AI:

```
           [User Asks a Legal Question]
                       │
                       ▼
         [Step 1: Multi-Tier Normalizer]
         (Cleans query, identifies section or offence in <0.1ms)
                       │
                       ▼
      [Step 2: BM25 Exact Statutory Search]
      (Pulls authoritative bare-act statutory text)
                       │
                       ▼
       [Step 3: AI Generates Answer Draft]
       (Strict format: [Act §Section])
                       │
                       ▼
   ┌──────────────────────────────────────────────┐
   │    Step 4: TWO-LAYER HARD VERIFIER           │
   │    (Holds absolute veto power over the AI)   │
   │                                              │
   │ 1. Closed-Vocabulary Gating:                 │
   │    Rejects fake sections like [BNS §999].    │
   │ 2. Repeal Veto Directives:                   │
   │    Intercepts Sedition/Adultery and injects  │
   │    official legal warning.                   │
   │ 3. Cross-Statute Consistency:                │
   │    Catches conflicting co-citations.         │
   │ 4. Penal Grounding:                          │
   │    Prevents fake punishments (e.g. death     │
   │    penalty for simple theft).                │
   │ 5. Intent Gating:                            │
   │    Rejects off-topic citations.              │
   └──────────────────────┬───────────────────────┘
                          │
                          ▼
            [Verified, Safe Legal Answer]
          (+ Continuous Reliability Score 0-100%)
```

---

## 📊 4. The Experimental Results (Testbed-Labeled)

| Stage | System Configuration | Dev Accuracy ($N=60$) | Stress Catch Rate ($N=18$) | Control FPR ($N=12$) | Adaptivity Delta ($N=3$) | Procedural Gen ($N=30$) |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Closed-Book) | **10.0% (6/60)** | N/A | N/A | N/A | **23.3% (7/30)** |
| **Stage 2** | +BM25 RAG (Retrieved Context) | **63.3% (38/60)** | N/A | N/A | N/A | **60.0% (18/30)** |
| **Stage 3** | +Two-Layer Hard Verifier | **63.3% (38/60)** | **100.0% (18/18)** | **0.0% (0/12)** | Pre: 33.3% (1/3) | **100.0% (30/30)** |
| **Stage 4** | +Incremental Refresh (Full System) | **63.3% (38/60)** | **100.0% (18/18)** | **0.0% (0/12)** | Post: 100.0% (3/3) | **100.0% (30/30)** |
| **Generalization** | CrPC $\leftrightarrow$ BNSS Procedural Law | N/A | **100.0% (5/5 drift)** | **0.0% (0/25)** | N/A | **100.0% (30/30)** |

* **Statistical Proof:** McNemar’s paired test shows the Stage 1 $\rightarrow$ 2 jump is significant ($p = 1.05 \times 10^{-7}$).
* **Human Expert Agreement:** Double-blind legal review scored **$\kappa = 0.93$**.

---

## 🎯 5. Top 4 Live Case Studies (Great for Presentations)

### Case 1: The Sedition Veto (IPC §124A)
* **Question:** *"Can a person be prosecuted under Section 124A of IPC for sedition in 2025?"*
* **Standard AI Mistake:** Says yes with life imprisonment.
* **Our Verifier Action:** **VETOED!** Injects legal advisory explaining IPC §124A was struck down and omitted in BNS.

### Case 2: Split Provision (IPC §33 'Act' & 'Omission')
* **Question:** *"How was IPC Section 33 re-organized in BNS?"*
* **Our Verifier Action:** Identifies that IPC §33 split into two sections (`BNS §2(1)` for Act and `BNS §2(25)` for Omission) and issues a graded confidence alert.

### Case 3: Novel 2025 AI Deepfake Amendment (BNS §318A)
* **Question:** *"What section penalizes AI voice cloning and deepfake impersonation fraud?"*
* **Our Verifier Action:** Hot-patches in $<5\text{ ms}$ and accurately retrieves newly gazetted `BNS §318A` with up to 7 years imprisonment.

### Case 4: Cross-Statute Contradiction Interception
* **AI Output:** *"Cheating is penalized under [BNS §318] and was formerly [IPC §302]."*
* **Our Verifier Action:** Catches the mistake! Flags that IPC §302 is Murder, not Cheating (`REJECTED_CROSS_STATUTE_INCONSISTENCY`).

---

## 🚀 6. How to Test the Project Yourself

### 1. Launch the Web UI (Interactive Visual Interface):
```bash
streamlit run app.py
```

### 2. Run the Command-Line Showcase:
```bash
python demo.py
```

### 3. Run the Automated Test Suite (67 Tests):
```bash
python -m pytest code/tests/ -v
```
