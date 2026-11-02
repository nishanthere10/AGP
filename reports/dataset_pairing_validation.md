# Dataset Pairing Validation — HumanEvalPack Python (164 tasks)

**Date:** 2026-11-01
**Status:** ✅ PASS
**Canonical location:** `~/projects/LocalAgentBench` (WSL)
**Artifacts:**
- Oracle run: `scripts/validate_dataset.py` → `results/dataset_validation.json`
- Pairing validator: `scripts/validate_pairing_164.py` → `results/dataset_pairing_validation.json`

---

## 1. Purpose

For the quantization × synthesis-vs-repair study, every task must exist in two
modes derived from the **same underlying problem**:

- **Synthesis:** natural-language specification + function signature → complete function.
- **Repair:** same specification + same signature + buggy implementation → corrected function.

Both modes must be scored by the **same hidden test**. This report confirms all
164 tasks satisfy the pairing and integrity requirements before the experiment is
prepared.

---

## 2. Results

| Check | Target | Result |
|---|---|---|
| Task count | 164 | ✅ 164 |
| Unique task IDs | 164 | ✅ 164 (0 duplicates) |
| Canonical solution passes oracle | 164/164 | ✅ 164/164 |
| Buggy solution fails oracle | 164/164 | ✅ 164/164 |
| Hidden-test leakage into prompts | 0 | ✅ 0 |
| Canonical-solution leakage outside buggy block | 0 | ✅ 0 |
| Prompt pairs buildable (synthesis + repair) | 164/164 | ✅ 164/164 |

**Overall status: PASS.**

---

## 3. Leak check methodology (important nuance)

A naive substring search for the canonical solution inside the repair prompt flags
7 tasks (Python/2, 23, 53, 67, 97, 120, 138). Inspection showed these are
**false positives**: the injected bug type is "excess logic" (or similar), where
the buggy body is the canonical body **plus extra trailing code**. The canonical
body is therefore a legitimately embedded *prefix* of the buggy body.

This is inherent to the task (the model must delete the extra code), **not**
leakage of the hidden test or of the answer. The refined validator therefore
checks:

- hidden test appears in **neither** prompt (strict);
- canonical solution appears in the **synthesis** prompt (strict, zero);
- canonical solution appears in the repair prompt **outside the buggy block**
  (strict, zero).

After this correction: **0 true leaks.**

### Impact on task difficulty
The 7 prefix-embedded tasks make repair *easier* in one sense (delete trailing
lines). This is a property of the dataset to **report as a covariate**, not hide:
`bug_type` and `edit_distance_buggy_canonical` are recorded per task in
`results/dataset_pairing_validation.json`, so subgroup analysis can control for it.
No tasks are removed.

---

## 4. Per-task recorded fields

Each of the 164 records in `results/dataset_pairing_validation.json` includes:

- `task_id`
- `synthesis_prompt_chars`, `repair_prompt_chars`
- `entry_point`
- `bug_type` (e.g. excess logic, value misuse, missing logic, off-by-one, …)
- `failure_symptoms`
- `has_import`, `has_test_setup`
- `edit_distance_buggy_canonical` (Levenshtein)
- `canonical_passes`, `buggy_fails`
- `leak_flags` (empty for all tasks)

---

## 5. Commands to reproduce

```bash
cd ~/projects/LocalAgentBench
.venv/bin/python scripts/validate_dataset.py            # oracle: results/dataset_validation.json
.venv/bin/python scripts/validate_pairing_164.py       # pairing: results/dataset_pairing_validation.json
```
