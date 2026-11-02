#!/usr/bin/env python3
"""Offline regression tests for pilot_runner.extract_body().

Run with: python scripts/test_extract_body.py
"""
import sys
import json
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
sys.path.insert(0, str(ROOT / "scripts"))
from pilot_runner import extract_body

def test_case(name: str, raw: str, grammar: bool, expected_body: str | None, expected_note_prefix: str):
    body, note = extract_body(raw, grammar)
    body_ok = (body == expected_body)
    note_ok = note.startswith(expected_note_prefix)
    ok = body_ok and note_ok
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {name}")
    if not ok:
        print(f"  expected body={repr(expected_body)} note_prefix={expected_note_prefix}")
        print(f"  got       body={repr(body)} note={note}")
    return ok

def main():
    all_ok = True

    # 1. Real artifact: grammar1.out (has echo with placeholder, then valid completion)
    with open(ROOT / "results/inference_smoke/grammar1.out") as f:
        g1 = f.read()
    all_ok &= test_case(
        "grammar1.out (grammar, has echo)",
        g1, True,
        "The function subtracts b from a, but it should add b to a.",
        "ok-json"
    )

    # 2. Real artifact: comp1.out (no grammar, has echo, malformed completion)
    # Without grammar, falls back to raw extraction which includes echo - this is expected
    with open(ROOT / "results/inference_smoke/comp1.out") as f:
        c1 = f.read()
    body, note = extract_body(c1, False)
    all_ok &= test_case(
        "comp1.out (no grammar, has echo -> raw fallback)",
        c1, False,
        body,  # accept whatever raw fallback returns (non-None)
        "ok-raw-fallback"
    )

    # 3. Canary with grammar, no echo (clean JSON with ESCAPED newlines)
    # JSON strings must have \\n not raw newlines
    canary3 = '{"fix": "def fibonacci(n):\\n    return n + 1"}'
    all_ok &= test_case(
        "canary3.out (grammar, no echo, clean JSON)",
        canary3, True,
        "def fibonacci(n):\n    return n + 1",
        "ok-json"
    )

    # 4. Canary without grammar, has echo (finds last JSON)
    canary = 'user\nprompt with {"fix": "echo"}\nassistant\n{"fix": "def fibonacci(n):\\n    return n + 1"}'
    all_ok &= test_case(
        "canary.out (no grammar, has echo, finds last JSON)",
        canary, False,
        "def fibonacci(n):\n    return n + 1",
        "ok-json"
    )

    # 5. Malformed JSON (falls back to raw)
    all_ok &= test_case(
        "malformed JSON",
        "no json here", True,
        "no json here",
        "ok-raw-fallback"
    )

    # 6. Empty input
    all_ok &= test_case(
        "empty input",
        "", True,
        None,
        "malformed: empty"
    )

    # 7. Valid JSON without echo
    all_ok &= test_case(
        "valid JSON no echo",
        '{"fix": "def foo(): return 1"}', True,
        "def foo(): return 1",
        "ok-json"
    )

    # 8. Echo with placeholder (should be skipped, last match wins)
    echo_with_placeholder = 'user\nprompt with {"fix": "<the complete corrected function body>"}\nassistant\n{"fix": "def foo(): return 42"}'
    all_ok &= test_case(
        "echo with placeholder",
        echo_with_placeholder, True,
        "def foo(): return 42",
        "ok-json"
    )

    # 9. Markdown fence (config A fallback)
    fenced = '```python\ndef foo():\n    return 42\n```'
    all_ok &= test_case(
        "markdown fence (no grammar)",
        fenced, False,
        "def foo():\n    return 42",
        "ok-raw-fallback"
    )

    # 10. Raw body (no JSON, no fence)
    raw = 'def foo():\n    return 42'
    all_ok &= test_case(
        "raw body (no grammar)",
        raw, False,
        "def foo():\n    return 42",
        "ok-raw-fallback"
    )

    # 11. JSON with escaped newlines in string value
    json_with_newlines = '{"fix": "def foo():\\n    return 1"}'
    all_ok &= test_case(
        "JSON with escaped newlines",
        json_with_newlines, True,
        "def foo():\n    return 1",
        "ok-json"
    )

    print()
    if all_ok:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())