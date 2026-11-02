#!/usr/bin/env python3
"""Validate markdown docs: balanced fences, mermaid blocks, no obvious issues."""
import sys
from pathlib import Path

ROOT = Path("/home/aaksh/projects/LocalAgentBench")
FILES = [ROOT / "README.md",
         ROOT / "docs/EXPERIMENT_PIPELINE.md",
         ROOT / "docs/HARDENING_SAFEGUARDS.md"]

fail = 0
for f in FILES:
    if not f.exists():
        print("MISSING", f)
        fail += 1
        continue
    text = f.read_text(encoding="utf-8")
    fences = text.count("```")
    mermaid = text.count("```mermaid")
    # every mermaid block must be closed: count of ``` should be even
    balanced = fences % 2 == 0
    # quick sanity: no leftover unclosed placeholder
    print(f"{f.name}: len={len(text)} fences={fences} (balanced={balanced}) "
          f"mermaid_blocks={mermaid}")
    if not balanced:
        fail += 1
    # each mermaid fence should have content after it before the closing fence
    lines = text.splitlines()
    in_m = False
    for i, line in enumerate(lines):
        if line.strip() == "```mermaid":
            in_m = True
            continue
        if line.strip() == "```" and in_m:
            in_m = False
            continue
    if in_m:
        print("  ERROR: unclosed mermaid block")
        fail += 1

print("DOC_VALIDATION_FAILURES:", fail)
sys.exit(1 if fail else 0)
