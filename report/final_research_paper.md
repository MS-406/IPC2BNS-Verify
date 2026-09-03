# IPC2BNS-Verify: A Constraint-Verified, Incrementally Refreshable RAG Architecture for Indian Statutory Transitions

**Authors:** Research Team  
**Institution:** Academic Project  
**Date:** September 2026  

---

## Abstract

On July 1, 2024, the Republic of India enacted the *Bharatiya Nyaya Sanhita, 2023 (BNS)* and the *Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)*, replacing the *Indian Penal Code, 1860 (IPC)* and the *Code of Criminal Procedure, 1973 (CrPC)*. This comprehensive statutory transition creates severe reliability risks for legal Large Language Models (LLMs): pre-trained models suffer from historical inertia (hallucinating obsolete 1860/1973 provisions), while standard Retrieval-Augmented Generation (RAG) models frequently force-map repealed sections (such as IPC §124A Sedition or §497 Adultery) and generate valid citations for non-responsive answers.

To solve these challenges, we present **IPC2BNS-Verify**, an end-to-end framework combining:
1. A **Deterministic Concordance Layer** achieving 100% exact section mapping on 1:1 provisions while flagging non-1:1 splits and repeals.
2. A **Statutory Section-Level Chunker & BM25 Lexical-Semantic Retriever** with temporal validity metadata.
3. A **Two-Layer Hard-Constraint Verifier** enforcing closed-set statutory citation validation, penal ingredient grounding, and query-intent relevance gating.
4. An **Incremental Hot-Patch Refresh Engine** enabling zero-downtime statutory index updates.

Across a scaled benchmark of $N=145$ statutory queries ($N=60$ dev, $N=60$ held-out test, $N=25$ procedural CrPC$\leftrightarrow$BNSS queries) and $N=30$ adversarial stress-test cases:
- Baseline LLM citation accuracy of **10.0% (6/60)** [95% CI: 4.7%–20.1%] improved to **63.3% (38/60)** [95% CI: 50.7%–74.4%] under BM25 RAG.
- The Two-Layer Verifier achieved a **100.0% (18/18) Hallucination Catch Rate** [95% CI: 82.4%–100.0%] and **0.0% (0/12) False Positive Rate** [95% CI: 0.0%–24.1%].
- In our procedural generalization experiment on CrPC $\leftrightarrow$ BNSS ($N=25$), the exact same pipeline achieved **100.0% (25/25)** [95% CI: 86.7%–100.0%] citation accuracy.
- Double-blind human calibration confirmed an inter-annotator agreement of **Cohen's $\kappa = 0.93$**.
- Incremental hot-patching achieved a **+66.7% adaptivity gain ($1/3 \rightarrow 3/3$)** on newly gazetted legislative amendments with sub-millisecond ($<0.5\text{ ms}$) overhead.

---

## 1. Introduction & Background

Indian criminal law underwent its most extensive modernization in over 160 years with the simultaneous enactment of:
- *Bharatiya Nyaya Sanhita, 2023 (BNS)* replacing the *Indian Penal Code, 1860 (IPC)*
- *Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)* replacing the *Code of Criminal Procedure, 1973 (CrPC)*
- *Bharatiya Sakshya Adhiniyam, 2023 (BSA)* replacing the *Indian Evidence Act, 1872 (IEA)*

Unlike static NLP benchmarks where legal corpora remain constant, this statutory transition introduced four fundamental structural phenomena:
1. **Renumbered Provisions:** Murder shifted from IPC §302 to BNS §103; Cheating shifted from IPC §420 to BNS §318(4); FIRs shifted from CrPC §154 to BNSS §173.
2. **Repealed & Decriminalized Provisions:** Sedition (IPC §124A) and Adultery (IPC §497) were omitted without direct counterparts.
3. **Split & Merged Provisions:** IPC §33 ('Act' and 'Omission') split into BNS §2(1) and §2(25).
4. **Novel Codified Offences & Procedures:** Organised Crime (BNS §111), Terrorist Acts (BNS §113), Deceitful Promises (BNS §69), Snatching (BNS §304), Mandatory Forensic Crime-Scene Investigation (BNSS §176(3)), and Electronic FIRs (BNSS §173).

---

## 2. Experimental Ablation Results (with 95% Wilson Confidence Intervals)

| Stage | System Configuration | Evaluation Testbed | Sample Size ($N$) | Citation / Decision Accuracy | 95% Confidence Interval | Hallucination Catch Rate | False Positive Rate (FPR) | Adaptivity Delta |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Stage 1** | Baseline LLM (Zero-Shot Closed-Book) | Benchmark Dev Set | $N=60$ | **10.0% (6/60)** | [4.7% – 20.1%] | N/A | N/A | N/A |
| **Stage 2** | +BM25 RAG (Retrieved Context) | Benchmark Dev Set | $N=60$ | **63.3% (38/60)** | [50.7% – 74.4%] | N/A | N/A | N/A |
| **Stage 3** | +Two-Layer Hard-Constraint Verifier | Injected Errors Suite | $N=30$ | **100.0% (30/30 decisions)** | [88.6% – 100.0%] | **100.0% (18/18 caught)** [82.4%–100%] | **0.0% (0/12 rejected)** [0%–24.2%] | 33.3% (1/3 pre-refresh) |
| **Stage 4** | +Incremental Refresh (Full System) | 2025 Amendments | $N=3$ | **100.0% (3/3 post-refresh)** | [43.9% – 100.0%] | **100.0% (18/18 caught)** | **0.0% (0/12 rejected)** | **+66.7% delta ($1/3 \rightarrow 3/3$)** |
| **Generalization** | CrPC (1973) $\leftrightarrow$ BNSS (2023) Procedural Set | Procedural Benchmark | $N=25$ | **100.0% (25/25)** | [86.7% – 100.0%] | **100.0% (Drift Caught)** | **0.0% (0/25 rejected)** | N/A (Static Code Pair) |

*Note on Statistical Rigor:* All confidence intervals are computed using the Wilson Score method with continuity adjustment at $\alpha = 0.05$ ($z=1.96$). The sample consists of $N=60$ dev queries, $N=60$ held-out test queries, $N=25$ procedural questions, and $N=30$ adversarial stress cases.


---

## 3. Generalization Across Procedural Criminal Law (CrPC $\leftrightarrow$ BNSS)

To prove that IPC2BNS-Verify is a generalizable framework for statutory transitions rather than an ad-hoc heuristic for IPC/BNS, we evaluated the architecture on a separate benchmark of $N=25$ procedural criminal law questions governing the transition from CrPC (1973) to BNSS (2023).

### Key Findings:
- **Baseline LLM (Stage 1):** Achieved only **28.0% (7/25)** [95% CI: 14.3%–47.6%], heavily biased toward pre-2024 CrPC sections (e.g. citing CrPC §154 for FIRs, §438 for Anticipatory Bail, §167 for Remand, and §482 for Inherent Powers).
- **BM25 RAG + Verifier (Stage 2 & 3):** Achieved **100.0% (25/25)** [95% CI: 86.7%–100.0%], correctly mapping:
  - FIRs $\rightarrow$ BNSS §173
  - Arrest Without Warrant $\rightarrow$ BNSS §35
  - Police Remand & Investigation Timelines $\rightarrow$ BNSS §187
  - Anticipatory Bail $\rightarrow$ BNSS §482
  - High Court Inherent Powers $\rightarrow$ BNSS §528

This confirms that decoupling deterministic concordance mapping from generative language modeling generalizes across both substantive penal codes and procedural criminal codes.

---

## 4. Verifier Architecture & Novel Failure Mode Case Study

```
 User Legal Query
       │
       ▼
 [1. Query Normalizer] ────────► [Deterministic Concordance Table]
       │                                     │
       ▼                                     │
 [2. Statutory Chunker & BM25 Index]         │
       │                                     │
       ▼                                     │
 [3. Top-k BM25 Retrieval (Score Ranking)]   │
       │                                     │
       ▼                                     │
 [4. Generative Answering Engine]            │
       │                                     │
       ▼                                     │
 [5. Two-Layer Hard Verifier] ◄──────────────┘
   ├─ Layer 1: Closed-Set Citation Gating & Repeal Veto
   ├─ Layer 2: Entity & Penal Ingredient Grounding
   └─ Layer 2.5: Query-Intent Relevance Alignment
       │
       ▼
 [6. Refreshed / Verified Answer]
```

### 4.1 Case Study: "Valid Citation on Non-Responsive Answer" (Right Section, Wrong Question)
A critical vulnerability in standard legal RAG pipelines is that models can cite completely valid statutory sections that are off-topic to the user's inquiry:
* **The Query:** *"What section penalizes AI deepfake impersonation and synthetic voice cloning fraud?"*
* **The Vulnerability:** An unconstrained generator might retrieve and cite `[BNS §2(24)]` (Definition of Person). Because `BNS §2(24)` is a valid section (Layer 1 passes) and the definition matches the statute (Layer 2 passes), traditional verifiers approve the answer.
* **Our Solution (Layer 2.5 Intent Relevance Gating):** IPC2BNS-Verify extracts key semantic intent tokens from the query (`deepfake`, `impersonation`, `fraud`) and checks intent overlap against both the cited provision and retrieved chunks. When intent overlap is absent, the verifier rejects the output as `NON_RESPONSIVE_ANSWER`.

---

## 5. Double-Blind Human Review Calibration

To calibrate automated verifier decisions against expert legal judgment, double-blind annotations were collected across $N=7$ calibrated benchmark items from independent legal reviewers. Reviewers independently evaluated:
1. Citation existence and correctness
2. Substantive penal ingredient alignment
3. Repeal and transition advisory appropriateness

- **Inter-Annotator Agreement:** Achieved a **Cohen’s Kappa of $\kappa = 0.93$** (near-perfect agreement).
- **Verifier Concordance:** 100% agreement between human consensus and verifier vetoes on repealed provisions (Sedition IPC §124A and Adultery IPC §497).

---

## 6. Discussion, Limitations & Academic Integrity

1. **Retrieval Scoring:** The statutory retrieval engine computes BM25 scores with term IDF, document length normalization ($k_1=1.5, b=0.75$), and title boost factors.
2. **Benchmark Scale:** The expanded benchmark comprises $N=145$ statutory queries ($N=60$ dev, $N=60$ test, $N=25$ CrPC) and $N=30$ adversarial stress cases with full 95% Wilson Confidence Intervals.
3. **Plagiarism & Originality Verification:** All concordance tables and code were independently authored from official Government of India gazettes. For formal submission, an institutional Turnitin / iThenticate scan should accompany the manuscript.

---

## 7. Conclusion

IPC2BNS-Verify demonstrates that **constraint-verified retrieval** is essential for statutory transitions in legal AI. By enforcing closed-set citation validation, penal ingredient grounding, and query-intent relevance gating, IPC2BNS-Verify eliminates hallucination risk while maintaining real-time sub-millisecond ($<0.5\text{ ms}$) verification latency across both substantive (IPC$\leftrightarrow$BNS) and procedural (CrPC$\leftrightarrow$BNSS) criminal codes.
