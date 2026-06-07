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
3. **Confirm a passing self-audit for the current blueprint state.** Query `verification_reports` for the most recent record with `record_type="self_audit"`. If no such record exists, or if `audit_pass` is `false`, or if the blueprint has been modified since the recorded audit, **do not call the verifier**. Instead, invoke `$self-audit` and address every finding it reports. Re-run `$self-audit` until it returns `audit_pass=true` for the current blueprint state. Only after the audit passes may you proceed to step 4.
4. Call MCP tool `verify_proof_service` with:
   - `statement`: target informal statement
   - `proof`: the raw markdown text from `blueprint.md`
5. Read `verification_report.summary`, `critical_errors`, `gaps`, `verdict`, and `repair_hints`.
6. Return and persist exactly what the verification service returns. Do not rename keys, add keys, or change the JSON structure.
7. Treat the proof as failed if any of the following hold:
   - `verdict` is `"wrong"`
   - `verification_report.critical_errors` is non-empty
   - `verification_report.gaps` is non-empty
8. Only treat the proof as passed when none of the failure conditions above hold.
9. If the proof passes, rename `results/{problem_id}/blueprint.md` to `results/{problem_id}/blueprint_verified.md`.

## Hard Invariants

1. **No verification call without a passing self-audit for the exact current blueprint state.** Step 3 is enforced absolutely. Calling `verify_proof_service` without a fresh passing audit is a control-flow error.
2. Any edit to `blueprint.md` after a passing self-audit invalidates that audit; `$self-audit` must be re-run before the next verification call.

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
- Claude Code's built-in `WebSearch` tool and `search_arxiv_theorems` when the verifier identifies a missing lemma or gap

## Failure Logging

Always persist verification output, including successful checks.
