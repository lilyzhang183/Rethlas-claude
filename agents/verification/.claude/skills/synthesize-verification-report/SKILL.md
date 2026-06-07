---
name: synthesize-verification-report
description: Aggregate all detected critical errors, gaps, and warnings into the final verification report, apply the strict accept/reject rule (warnings do not block correctness), and produce repair hints when rejected.
---

# Synthesize Verification Report

Produce the final verification output JSON and verdict.

## Input Contract

Read all findings from:

- `statement_checks` (sequential audit + tag/banned-phrase discipline + computational replay sub-records)
- `reference_checks` (notation consistency + external reference resolution)

Each finding records `location`, `issue`, and a `severity` of `critical_error`, `gap`, or `warning`. If a recorded finding lacks an explicit `severity`, infer it from the originating skill's classification rules; default to `gap` when ambiguous.

## Severity semantics

The three-level severity ladder decides what blocks `verdict=correct`:

- **`critical_error`** — the proof is mathematically invalid, applies a nonexistent or misused theorem, contradicts itself, or uses untagged claims / banned phrases / silent notation renamings. Blocks correctness.
- **`gap`** — the proof may be true but is missing a needed intermediate argument, justification, or computation. Blocks correctness.
- **`warning`** — style, cleanup, orphan notation entries, redundant declarations, stale memory, verbosity. **Does not block correctness.**

## Procedure

1. Collect every finding across `statement_checks` and `reference_checks`. Partition each into `critical_errors`, `gaps`, or `warnings` by severity.
2. Build a complete `verification_report` object with `summary`, `critical_errors`, `gaps`, and `warnings`. The four fields are all required; `warnings=[]` is acceptable, but the key must be present.
3. Apply the strict verdict rule:
   - `verdict = "correct"` iff `critical_errors=[]` **and** `gaps=[]`. Warnings are not counted.
   - Otherwise `verdict = "wrong"`.
4. If `verdict="wrong"`, produce non-empty `repair_hints` that explicitly address each critical error and each gap. Warnings may be referenced for completeness but are never the sole reason for failure.
5. If `verdict="correct"`, set `repair_hints=""`. The warnings list (if non-empty) is informational only; do not move warnings into `repair_hints`.
6. Validate the output via `validate_verification_output`. The schema requires the `warnings` field to be present.
7. Persist output via `write_verification_output`.

## Output Contract

Final output JSON shape:

```json
{
  "verification_report": {
    "summary": "string",
    "critical_errors": [
      {"location": "string", "issue": "string", "severity": "critical_error"}
    ],
    "gaps": [
      {"location": "string", "issue": "string", "severity": "gap"}
    ],
    "warnings": [
      {"location": "string", "issue": "string", "severity": "warning"}
    ]
  },
  "verdict": "correct",
  "repair_hints": ""
}
```

When the proof passes:

```json
{
  "verification_report": {
    "summary": "All audits passed; warnings recorded for cleanup but do not block correctness.",
    "critical_errors": [],
    "gaps": [],
    "warnings": [
      {"location": "Notation entry for $\\omega$", "issue": "declared but never used", "severity": "warning"}
    ]
  },
  "verdict": "correct",
  "repair_hints": ""
}
```

When the proof fails:

```json
{
  "verification_report": {
    "summary": "Two critical errors and one gap detected.",
    "critical_errors": [
      {"location": "Lemma 3 proof, line 2", "issue": "...", "severity": "critical_error"}
    ],
    "gaps": [
      {"location": "Lemma 5 proof, paragraph 1", "issue": "...", "severity": "gap"}
    ],
    "warnings": []
  },
  "verdict": "wrong",
  "repair_hints": "..."
}
```

## MCP Tools

- `memory_query`
- `memory_append`
- `validate_verification_output`
- `write_verification_output`
