---
name: verify-proof
description: Verify candidate proofs with the local proof verification MCP service. Use only when a full candidate proof of the entire problem has been assembled in markdown, and before publishing the final verified blueprint.
---

# Verify Proof

Use the local proof verification service as the canonical verifier before accepting a solution.
Do not use this skill for partial proofs, isolated subgoals, or branches that have not yet produced a full proof draft of the whole problem.

## Input Contract

Read:

- target theorem statement
- assembled proof blueprint candidate from `results/{problem_id}/blueprint.md` as pure markdown text
- relevant prior failure reports and branch context

## Procedure

1. Read the current `results/{problem_id}/blueprint.md` draft as pure text.
2. First check that `blueprint.md` contains a full proof draft of the entire target theorem rather than a partial proof, fragment, or exploratory notes. If it does not, do not call the verifier yet.
3. **Confirm a passing self-audit for the current triple-hash state.** Compute three current hashes:
   - `current_blueprint_sha256 = sha256(blueprint.md as bytes)`
   - `current_obligations_sha256 = sha256(results/{problem_id}/proof_obligations.json as bytes)`
   - `current_notation_sha256 = sha256(memory/{problem_id}/notation_dictionary.jsonl as bytes)`

   Query `verification_reports` for the most recent record with `record_type="self_audit"`. If no such record exists, or `audit_pass=false`, or any of the recorded hashes (`blueprint_sha256`, `proof_obligations_sha256`, `notation_dictionary_sha256`) does not equal the corresponding current hash, **do not call the verifier**. Instead, invoke `$self-audit` and address every finding it reports. Re-run `$self-audit` until it returns `audit_pass=true` for the current triple. Only after a matching passing audit exists may you proceed to step 4.
4. Allocate an `attempt_id` for this verification call (e.g. `attempt_{n}` where `n` is the number of prior verify_proof_service calls for this `problem_id`).
5. Read the literal content of `results/{problem_id}/proof_obligations.json` into memory as the string `proof_obligations_content`. Call MCP tool `verify_proof_service` with:
   - `statement`: target informal statement
   - `proof`: the raw markdown text from `blueprint.md`
   - `problem_id`: the current `problem_id`
   - `attempt_id`: the `attempt_id` from the previous step
   - `blueprint_sha256`: `current_blueprint_sha256`
   - `proof_obligations_sha256`: `current_obligations_sha256`
   - `notation_dictionary_sha256`: `current_notation_sha256`
   - `proof_obligations_json`: `proof_obligations_content` (the literal JSON string; the verifier reads it to run `$check-proof-obligation-graph`)
   - `self_audit_id`: the `audit_id` field of the matching `audit_pass=true` self_audit record
6. Read `verification_report.summary`, `critical_errors`, `gaps`, `warnings`, `verdict`, and `repair_hints`. Also record `run_id`, `log_path`, and `metadata` returned by the service for the run log.
7. Return and persist exactly what the verification service returns. Do not rename keys, add keys, or change the JSON structure. Persist the full response to `verification_reports` with `record_type="verifier_response"` and `attempt_id` so future skills can correlate it with the `self_audit` record.
8. Treat the proof as failed if any of the following hold:
   - `verdict` is `"wrong"`
   - `verification_report.critical_errors` is non-empty
   - `verification_report.gaps` is non-empty
9. Warnings in `verification_report.warnings` do **not** cause failure. Record them for cleanup in a subsequent revision pass, but do not block acceptance over warnings alone.
10. Only treat the proof as passed when none of the failure conditions above hold.
11. If the proof passes, rename `results/{problem_id}/blueprint.md` to `results/{problem_id}/blueprint_verified.md`.

## Hard Invariants

1. **No verification call without a passing self-audit for the exact current triple-hash state.** Step 3 is enforced absolutely. Calling `verify_proof_service` without a fresh passing audit, or with a hash mismatch on any of the three artifacts (`blueprint.md`, `proof_obligations.json`, `notation_dictionary.jsonl`), is a control-flow error.
2. Any edit to any of the three artifacts after a passing self-audit changes the corresponding hash and invalidates that audit; `$self-audit` must be re-run before the next verification call.
3. After a passing verification, also verify that the response's `verified_blueprint_sha256` equals the current `sha256(blueprint.md)` before renaming to `blueprint_verified.md`. A mismatch means the blueprint was edited mid-call and must not be accepted.

## Output Contract

Append to `verification_reports`:

```json
{
  "verification_report": {
    "summary": "string",
    "critical_errors": [
      {"location": "", "issue": "detailed description of the issue"}
    ],
    "gaps": [
      {"location": "", "issue": "detailed description of the gap"}
    ]
  },
  "verdict": "string",
  "repair_hints": "string"
}
```

Persist the verification service response exactly as returned.

If verification fails, revise `blueprint.md` directly and append to `failed_paths` when a branch is invalidated.

## MCP Tools

- `verify_proof_service`
- `memory_append`
- `memory_search`
- `branch_update`
- Claude Code's built-in `WebSearch` tool and `search_theorem_index` when the verifier identifies a missing lemma or gap

## Failure Logging

Always persist verification output, including successful checks.
