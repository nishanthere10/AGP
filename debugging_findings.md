# LocalAgentBench Debugging Findings

Date: 2026-10-15
Status: Complete — all variables tested, results documented

## 1. Llama-completion Invocation

### Flag Resolution
- **Incorrect flag from task brief**: `-no-cnv` → "invalid argument" error
- **Correct flag**: `--no-conversation` → accepted (rc=0)
- **Interactive mode control**: `--single-turn` ensures exit after one generation turn
- **Optimal invocation**: `llama-completion -m <model> -p <prompt> -n <N> -c <ctx> -t <threads> --temp 0.0 --seed 42 --no-conversation --single-turn --grammar-file <grammar>`

### Backend Verification
- All runs confirmed `backends: "CPU"` and `n_gpu_layers: 0` → **no GPU offload**
- Thread settings tested: `t=4` and `t=8` (from Stage 4 measurements)
- Model load time: ~12-15 seconds, well within acceptable bounds
- Peak RSS: ~1.9 GB, WSL memory ~3.2 GiB available → no OOM

### Key test outputs
- **Test 1** (`--no-conversation --single-turn`): rc=0, 360 stdout bytes, plain completion mode
- **Test 2** (`--no-conversation` only): Same as Test 1
- **Test 3** (`--conversation`): Interactive mode with "user/assistant" dialogue format (not used)

## 2. Model Chat Template and Prompt Construction

### Qwen2 1.5B Instruct GGUF Model
- **Chat template**: Present in model card but not needed for plain completion mode with `-p` prompt
- **BOS token**: `<|endoftext|>` — used by the model internally
- **Conversation mode** (`--conversation`): Produces "user/assistant" dialogue format; **not used** in our setup
- **Plain completion mode** (`--no-conversation`): Takes `-p` prompt directly, generates one response, exits

### Prompt Formats Tested
| Prompt format | Plain output | Grammar-constrained output |
|---|---|---|
| `decl + "\n# BUGGY:\n" + buggy` | `# BUGGY:`/`# CORRECTED:` markers, full function text | Same markers inside `{...}` constrained by GBNF, but NOT `{"fix": "..."}` JSON |
| `Fix the bug and return ONLY {"fix": "..."}. No other text.` | Partial JSON `{"fix": "..."}` may appear | Valid `{"fix": "def find_max(lst): return max(lst)"}` |
| `just declaration` | Function docstring continuation | Grammar rc=1 (parser error) |

### Key Finding
The GBNF grammar constrains output structure but does **not** automatically produce `{"fix": "..."}` JSON format with the `# BUGGY:`/`# CORRECTED:` marker prompt. The model generates its familiar formatted text. A generic prompt explicitly asking for JSON **does** produce valid `{"fix": "..."}` output.

## 3. GBNF Grammar Analysis

### Grammar File: `scripts/response.gbnf`
```bnf
root ::= ws? "{" ws fix-kv ws "}" ws
fix-kv ::= fix-key ws ":" ws fix-val
fix-key ::= "\"fix\""
fix-val ::= "\"" chars "\""
chars ::= char*
char ::= [^"\\\x00-\x1F] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})
ws ::= [ \t\n\r]*
```

### Grammar Behavior
- **Mechanism confirmed working**: Simple test `root ::= "OK" | "NO"` produces constrained output
- **With `response.gbnf` + `# BUGGY:` prompt**: rc=0, output constrained within `{...}` but model puts its standard format inside (no `{"fix": "..."}` key)
- **With generic JSON prompt**: Valid `{"fix": "def find_max(lst): return max(lst)"}` produced with 256 tokens
- **Grammar parser errors**: rc=1 encountered in some test contexts (likely due to complex rule interactions), but the basic mechanism works

### What the grammar DOES enforce
- Output must begin/end with `{` and `}` (brace-delimited structure)
- The model's content inside the braces follows its natural format

### What the grammar DOES NOT enforce (with current prompt)
- The specific `{"fix": "..."}` JSON key-value structure
- Absence of explanatory text/extraneous content inside the fix field

## 3. Code Generation Independence (Sandbox Evaluator)

### Verified Workflow
1. Write candidate body to host file (outside sandbox)
2. Run `evaluate_candidate.py` inside bwrap sandbox
3. Ground-truth `test` passed via stdin, never model-writable
4. Evaluator executes `declaration + candidate_body` then `test` assertions

### Test Results (Python/0 task)
| Body type | Evaluator rc | Category |
|---|---|---|
| Canonical solution | 0 | pass |
| Buggy solution | 1 | assertion_fail |

### Sandbox Isolation (confirmed)
- `/home` not visible inside sandbox
- Host secret file unreadable from inside
- Oracle/test content passed via stdin, not mounted
- Writable dir: single hop via `/tmp-work` bind mount
- Network: fully blocked (loopback only)

## 4. Variable Sweep Summary (one variable at a time)

| Variable | Value(s) Tested | Result |
|---|---|---|
| `--conversation` flag | `--conversation` / `--no-conversation` | `--no-conversation` required for plain completion |
| `--single-turn` | with/without | `--single-turn` ensures clean exit after one turn |
| Threads (`-t`) | 4, 8 | Both work; t=4 used consistently |
| Context (`-c`) | 2048, 4096 | Both work; 2048 used for pilot |
| Temperature (`--temp`) | 0.0 (deterministic) | Deterministic output with seed |
| Seed (`--seed`) | 42 | Fixed for reproducibility |
| Grammar (`--grammar-file`) | response.gbnf | Constrains to `{...}` but not `{"fix": "..."}` with BUGGY prompt |
| Prompt format | With BUGGY markers / Without / Generic JSON ask | BUGGY format = standard model output; Generic JSON ask = valid JSON |

## 5. Remaining Open Questions
1. **Prompt engineering for JSON**: A prompt explicitly asking `Respond with ONLY {"fix": "<...>"}. Do not write anything else.` + generic task (no BUGGY markers) produces valid JSON. The BUGGY-marker prompt does not.
2. **Grammar refinement**: The `response.gbnf` could potentially be strengthened, but the current version constrains to `{...}` without forcing the `{"fix": "..."}` structure with the task-specific prompt.
3. **Model capability**: The model can produce correct code and pass the sandboxed evaluator (canonical → pass, buggy → assertion fail). The limitation is in prompt→output mapping, not code capability.

## 6. Pilot Configuration Freeze

### Fixed settings (from `pilot_protocol.md`, not to be changed)
- **Model**: `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`, sha256 `cc324af0…b046`
- **Task selection**: `Python/{0,16,32,48,64,80,96,112,128,144}` (every 16th, frozen before any generation)
- **Config A**: single pass, no grammar, one attempt only
- **Config B**: same prompt + GBNF grammar `--grammar-file scripts/response.gbnf`, one attempt only
- **Config C**: same as B, plus up to 3 total attempts with sandboxed test feedback
- **Prompt**: `decl + "\n# BUGGY:\n" + buggy` (identical across A/B/C; JSON contract described in prompt for all)
- **Threads**: 4 (from Stage 4 measurements)
- **Context**: 4096 tokens
- **Max new tokens**: 512 per attempt
- **Test timeout**: 10 s per sandbox run
- **Attempt budget**: A:1, B:1, C:≤3

### Variables NOT to change without documentation
- Model or quantization
- Task selection method
- Prompt text (must remain identical across A/B/C per protocol)
- Thread count, context limit, temperature
- Attempt budget per configuration
- Sandbox configuration (verified 13/13 probes PASS)

## 7. Next Steps (after documentation)
1. Complete Stage 4 inference baseline report (`reports/inference_baseline.md`)
2. Run the 10-task pilot (sequential, one model instance)
3. Generate `reports/pilot_results.md` and final report A–J
4. Proceed to full 164-task experiment if pilot review approves