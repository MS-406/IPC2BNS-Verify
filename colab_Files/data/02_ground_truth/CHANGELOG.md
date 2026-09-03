# Concordance Table CHANGELOG
# ─────────────────────────────────────────────────────────────────────────
# Every correction to the ground-truth concordance table is logged here
# with date and reason, per the Data Management Plan.
# ─────────────────────────────────────────────────────────────────────────

## v1 — Initial Seed (2025-01-01)

- Created initial concordance_v1.csv with 120+ known IPC→BNS mappings
- Sources: India Code bare-act text + publicly available concordance tables
- Key special cases documented:
  - IPC §124A (Sedition) → Repealed (BNS §152 is narrower, NOT a 1:1 map)
  - IPC §377 (Unnatural offences) → Repealed (per Navtej Singh Johar, 2018)
  - IPC §497 (Adultery) → Repealed (per Joseph Shine, 2018)
  - IPC §33 → Split into BNS §2(1) and §2(25)
  - New BNS provisions: §69, §111, §112, §113, §152, §303(2)
- All rows marked verified=false pending cross-validation against bare-act text
- Coverage: ~25% of IPC sections (120/511) — remaining sections need manual completion

### Known gaps (to be filled in subsequent versions):
- IPC sections 13-16, 18, 20, 22-23, 27-28, 30-32, 35-39, 41-43, 45-50
- IPC sections 53-75 (punishments chapter)
- IPC sections 85-86, 88-95, 98-99, 101-106, 110-113, 115-119
- Most of IPC sections 130-140, 149-152, 154-185
- Detailed sub-section level mappings for split/merged sections
