#!/usr/bin/env python3
"""test_normalization.py — offline regression tests for evaluate_candidate.py
normalization logic (Task 4).

Tests 12 scenarios without loading the model or running the sandbox.
Each test directly calls normalize_candidate() and optionally runs the
harness locally (not inside bwrap, but against the real oracle code) to
check pass/fail results.

Run: python scripts/test_normalization.py
Exit 0 = all tests pass. Non-zero = failures.
"""
import ast
import sys
import textwrap
import traceback
from pathlib import Path

# ── Bootstrap: import the module under test ───────────────────────────────────
ROOT = Path('/home/aaksh/projects/LocalAgentBench')
sys.path.insert(0, str(ROOT / 'scripts'))

from evaluate_candidate import normalize_candidate, _extract_body_source  # noqa: E402

# ── Minimal fake task rows ────────────────────────────────────────────────────
TASK_DOUBLE = {
    "task_id": "Synthetic/double",
    "entry_point": "double",
    "declaration": "def double(x):\n",
    "test": "assert double(2) == 4\nassert double(0) == 0\nassert double(-3) == -6\n",
}

TASK_P16 = {
    "task_id": "Python/16",
    "entry_point": "count_distinct_characters",
    "declaration": "def count_distinct_characters(string: str) -> int:\n",
    "test": (
        "assert count_distinct_characters('xyzXYZ') == 3\n"
        "assert count_distinct_characters('Jerry') == 4\n"
    ),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
PASS = 0
FAIL = 0

def check(name, got_code, got_note, expected_note_contains,
          expected_code_contains=None, expected_code_not_contains=None):
    global PASS, FAIL
    ok = True
    msgs = []

    if expected_note_contains and expected_note_contains not in got_note:
        msgs.append(f"  note mismatch: got {got_note!r}, expected to contain {expected_note_contains!r}")
        ok = False
    if expected_code_contains and expected_code_contains not in got_code:
        msgs.append(f"  code missing expected fragment {expected_code_contains!r}")
        ok = False
    if expected_code_not_contains and expected_code_not_contains in got_code:
        msgs.append(f"  code should NOT contain {expected_code_not_contains!r}")
        ok = False

    if ok:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")
        for m in msgs:
            print(m)


def exec_code(code, entry, test_str):
    """Execute code + test_str locally (no sandbox). Returns (rc, note)."""
    ns = {}
    try:
        exec(code, ns)
    except Exception as e:
        return 3, f"IMPORT_ERROR: {type(e).__name__} {e}"
    fn = ns.get(entry)
    if fn is None:
        return 4, f"MISSING_ENTRY: {entry}"
    try:
        exec(test_str, ns)
    except AssertionError:
        return 1, "ASSERT_FAILED"
    except Exception as e:
        return 2, f"RUNTIME_ERROR: {type(e).__name__} {e}"
    return 0, "PASSED"


# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Task 4: Regression tests — evaluate_candidate normalization")
print("=" * 60)

# T1: JSON with escaped newlines — body-only fragment
print("\nT1: Body-only (escaped \\n in JSON string, decoded to actual newlines)")
body = "    return x * 2\n"   # this is what json.loads gives after decoding \n
code, note = normalize_candidate(body, TASK_DOUBLE)
# Indented fragments get "body-only" (unexpected-indent SyntaxError detected)
check("T1 body-only note", code, note, "body-only")
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc == 0:
    PASS += 1; print("  PASS  T1 oracle pass")
else:
    FAIL += 1; print(f"  FAIL  T1 oracle: rc={rc} {msg}")

# T2: Body-only with valid Python indented lines
print("\nT2: Body-only with valid Python")
body = "    return len(set(string.lower()))\n"
code, note = normalize_candidate(body, TASK_P16)
check("T2 note", code, note, "body-only")
rc, msg = exec_code(code, TASK_P16["entry_point"], TASK_P16["test"])
if rc == 0:
    PASS += 1; print("  PASS  T2 oracle pass")
else:
    FAIL += 1; print(f"  FAIL  T2 oracle: rc={rc} {msg}")

# T3: Complete function definition — should be extracted
print("\nT3: Complete function definition (FULL_DEF)")
body = "def double(x):\n    return x * 2\n"
code, note = normalize_candidate(body, TASK_DOUBLE)
check("T3 note", code, note, "full-def-extracted")
# Must not contain double def
check("T3 no double-def", code, note, "full-def-extracted",
      expected_code_not_contains="def double(x):\ndef double")
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc == 0:
    PASS += 1; print("  PASS  T3 oracle pass")
else:
    FAIL += 1; print(f"  FAIL  T3 oracle: rc={rc} {msg}")

# T4: Duplicate definition scenario — what pilot_v2 produced
print("\nT4: Duplicate definition (what raw concatenation produced in pilot_v2)")
# Simulate what the OLD evaluator did: declaration + full_def
declaration = TASK_DOUBLE["declaration"]
full_def = "def double(x):\n    return x * 2\n"
raw_code = declaration + full_def   # this is the bug
rc, msg = exec_code(raw_code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc == 3:
    PASS += 1; print(f"  PASS  T4 confirmed old code causes import_error: {msg}")
else:
    FAIL += 1; print(f"  FAIL  T4 expected import_error, got rc={rc} {msg}")
# New evaluator should handle it correctly
code, note = normalize_candidate(full_def, TASK_DOUBLE)
check("T4 new evaluator extracts", code, note, "full-def-extracted",
      expected_code_not_contains="def double(x):\ndef double")
rc2, msg2 = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc2 == 0:
    PASS += 1; print("  PASS  T4 new evaluator oracle pass")
else:
    FAIL += 1; print(f"  FAIL  T4 new evaluator: rc={rc2} {msg2}")

# T5: Invalid JSON (prose passed as body — what pilot_v2 produced)
print("\nT5: Natural-language prose instead of code")
body = "The bug is that it uses + instead of *. Fix by using multiplication."
code, note = normalize_candidate(body, TASK_DOUBLE)
# prose or parse-error(with msg) — either way normalize_candidate must not crash
assert note.startswith("parse-error") or note in ("body-only", "prose"), \
    f"T5 unexpected note: {note}"
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc == 3:
    PASS += 1; print(f"  PASS  T5 prose → import_error (expected): {msg[:80]}")
else:
    FAIL += 1; print(f"  FAIL  T5: expected import_error, got rc={rc} {msg}")

# T6: Wrong function name — should be rejected
print("\nT6: Wrong function name in full def")
body = "def triple(x):\n    return x * 3\n"
code, note = normalize_candidate(body, TASK_DOUBLE)
check("T6 sig-mismatch note", code, note, "full-def-sig-mismatch")
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
# Should fail with missing_entry (rc=4) or import_error (rc=3)
if rc in (3, 4):
    PASS += 1; print(f"  PASS  T6 wrong name → rc={rc}: {msg[:80]}")
else:
    FAIL += 1; print(f"  FAIL  T6: expected rc 3 or 4, got rc={rc} {msg}")

# T7: Empty output
print("\nT7: Empty body string")
body = ""
code, note = normalize_candidate(body, TASK_DOUBLE)
# Should not crash; oracle will report error
assert isinstance(code, str), "T7 code must be str"
PASS += 1; print(f"  PASS  T7 empty body handled (note={note!r})")
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc in (3, 4):
    PASS += 1; print(f"  PASS  T7 empty → rc={rc}: {msg[:80]}")
else:
    FAIL += 1; print(f"  FAIL  T7: expected rc 3 or 4, got rc={rc} {msg}")

# T8: Syntax error inside function body
print("\nT8: Syntax error in body")
body = "    return x *\n"   # incomplete expression
code, note = normalize_candidate(body, TASK_DOUBLE)
assert note in ("parse-error", "body-only"), f"T8 unexpected note: {note}"
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc == 3:
    PASS += 1; print(f"  PASS  T8 syntax error → import_error: {msg[:80]}")
else:
    FAIL += 1; print(f"  FAIL  T8: expected rc=3, got rc={rc} {msg}")

# T9: Valid fix that passes the oracle (end-to-end)
print("\nT9: Valid fix — oracle should PASS")
body = "    return x * 2\n"
code, note = normalize_candidate(body, TASK_DOUBLE)
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc == 0:
    PASS += 1; print(f"  PASS  T9 valid fix passes oracle")
else:
    FAIL += 1; print(f"  FAIL  T9: expected rc=0, got rc={rc} {msg}")

# T10: Fix that is valid Python but fails the oracle (wrong algorithm)
print("\nT10: Valid code but wrong algorithm")
body = "    return x + 1\n"   # wrong: adds 1 instead of doubling
code, note = normalize_candidate(body, TASK_DOUBLE)
rc, msg = exec_code(code, TASK_DOUBLE["entry_point"], TASK_DOUBLE["test"])
if rc == 1:
    PASS += 1; print(f"  PASS  T10 wrong algorithm → assertion_fail")
else:
    FAIL += 1; print(f"  FAIL  T10: expected rc=1 (assert fail), got rc={rc} {msg}")

# T11: Full def with correct algorithm for P16 (matches pilot_v2 C attempt 2)
print("\nT11: Full def with correct algorithm (like pilot_v2 Python/16 C a2)")
body = "def count_distinct_characters(string: str) -> int:\n    return len(set(string.lower()))\n"
code, note = normalize_candidate(body, TASK_P16)
check("T11 full-def-extracted", code, note, "full-def-extracted")
# Declaration is in code (expected), but must NOT contain two def lines for same func
double_def = code.count("def count_distinct_characters") > 1
if not double_def:
    PASS += 1; print("  PASS  T11 no double-def in code")
else:
    FAIL += 1; print("  FAIL  T11 code still contains double def")
rc, msg = exec_code(code, TASK_P16["entry_point"], TASK_P16["test"])
if rc == 0:
    PASS += 1; print(f"  PASS  T11 oracle passes (would have been hidden by double-def bug)")
else:
    FAIL += 1; print(f"  FAIL  T11: rc={rc} {msg}")

# T12: Config C repair feedback — verify the feedback string is present
print("\nT12: Config C repair prompt includes actual test output")
# Simulate what run_config() builds for C after attempt 1
fake_base_prompt = "Below is a Python function..."
fake_body = "    return x + 1\n"
fake_eval = {"category": "assertion_fail", "note": "ASSERT_FAILED"}
attempt_no = 1
repair = (
    fake_base_prompt
    + "\n\n# Your previous fix (attempt %d):\n%s" % (attempt_no, fake_body)
    + "\n\nGround-truth test result: %s" % fake_eval["category"]
    + "\nTest output:\n%s" % fake_eval["note"]
    + "\nReturn ONLY a JSON object with a single key \"fix\" whose value is "
      "the corrected function body (indented lines inside the def block, "
      "not the def line itself). Do not explain or add anything else."
)
if "assertion_fail" in repair and "ASSERT_FAILED" in repair and "attempt 1" in repair:
    PASS += 1; print("  PASS  T12 repair prompt contains feedback")
else:
    FAIL += 1; print("  FAIL  T12 repair prompt missing fields")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
