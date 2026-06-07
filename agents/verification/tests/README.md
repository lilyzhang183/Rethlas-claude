# Verification agent tests

Two test surfaces, runnable independently.

## 1. Infrastructure smoke tests (`test_infra_smoke.py`)

Unit tests that exercise the API server's input handling and the MCP module's
validator without launching Claude. Safe to run anywhere; no external services
required.

```bash
cd agents/verification
pytest tests/test_infra_smoke.py -v
```

Covers reviewer item 16: verifier-down behavior is documented in
`tests/test_runner_gate.py`; the rest live here:

- proof/statement empty → API rejects (Pydantic 422)
- malformed JSON in verifier output → 500 with structured detail
- `verdict=correct` with non-empty `critical_errors` or `gaps` → validator fails
- `verdict=wrong` with empty findings → validator fails
- missing `warnings` array → validator fails (schema enforcement)
- `repair_hints` non-empty when `verdict=correct` → validator fails
- `sanitize_problem_id` rejects path traversal (`../`)
- `build_prompt` does NOT inline the statement or proof (file-based handoff)
- `build_prompt` includes the untrusted-data instruction

## 2. Verifier adversarial cases (`test_verifier_cases.py`)

Integration tests that POST each fixture under `verifier_cases/` to the running
verification API and check the structured verdict matches expectations.
**Requires the verification service to be running** (and Claude Code CLI
installed); tests skip automatically if `http://127.0.0.1:8091/health` is
unreachable.

```bash
# Terminal 1
cd agents/verification
uvicorn api.server:app --host 0.0.0.0 --port 8091

# Terminal 2
cd agents/verification
pytest tests/test_verifier_cases.py -v
```

Each fixture is a directory under `verifier_cases/` containing `case.json` with:

```json
{
  "name": "...",
  "description": "...",
  "statement": "...",
  "proof": "...",
  "expected_verdict": "correct" | "wrong",
  "expected_issue_substrings": ["..."],
  "expected_warning_substrings": ["..."]
}
```

For `expected_verdict="wrong"`, each substring must appear in the issue text of
at least one `critical_error` or `gap` finding. For `expected_verdict="correct"`,
each warning substring must appear in some `warnings` entry; the verdict must
be exactly `"correct"` (warnings do not block).

## 3. Runner gate test (`test_runner_gate.py`)

Bash-level test that `run_example.sh` exits nonzero when
`REQUIRE_VERIFICATION=1` (the default) and the verifier health check fails.

```bash
pytest tests/test_runner_gate.py -v
```

## Adding a new adversarial case

```bash
mkdir tests/verifier_cases/my_new_case
$EDITOR tests/verifier_cases/my_new_case/case.json
pytest tests/test_verifier_cases.py::test_case[my_new_case] -v
```
