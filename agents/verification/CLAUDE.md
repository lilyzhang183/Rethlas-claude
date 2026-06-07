# Proof Verification Agent

This agent verifies the correctness of a mathematical proof provided in markdown format. It checks the logical flow, theorem applications, and external references to ensure the proof is valid. The agent produces a detailed verification report and a strict verdict on the proof's correctness.

## Objective

Given:

- `Run_id: <run_id>`
- `Statement: <informal theorem statement>`
- `Proof: <proof>`

verify whether the proof is correct and output:

- `results/{run_id}/verification.json`

with JSON fields:

- `verification_report`
- `verdict` (`"correct"` or `"wrong"`)
- `repair_hints`

## Input Contract

Assume `Proof` is markdown text written in normal mathematical order, like a paper proof with lemmas, propositions, claims, and a main theorem proof.

- Verify the statements and subproofs sequentially in the order they appear in the markdown.
- The main theorem conclusion is accepted only if the full markdown proof passes.

No code-level proof parser is required. Do not invent parser modules for subgoal extraction. Read the markdown in order and use its displayed structure.

## Required Skills

Use these skills in this order:

1. `$verify-sequential-statements`
2. `$check-notation-consistency`
3. `$check-computational-replay`
4. `$check-referenced-statements`
5. `$synthesize-verification-report`

`$check-notation-consistency` and `$check-computational-replay` are mandatory mid-pipeline audits added to catch notation drift and unstated computational steps respectively. See "Audit Dimensions" below for what each adds.


## Memory Policy

Initialize memory first:

- `memory_init(run_id, meta={"statement": ..., "input_shape": "proof_markdown_text"})`

Then persist artifacts in channels:

- `statement_checks`
- `reference_checks`
- `verification_reports`
- `failed_checks`
- `events`

Every detected issue must be persisted before final verdict.

## Verification Workflow

### Step 1: Initialize run context

1. Read `Run_id`, `Statement`, `Proof`.
2. Treat `Proof` as markdown text and read it in the order written.
3. Extract the assumptions and hypotheses stated in `Statement` before checking the proof.
4. If the proof text is empty or not usable as mathematical proof text, record a critical error at location `proof` and continue to final report with `verdict="wrong"`.

### Step 2: Sequential proof-item verification

For each statement/subproof in the markdown, in textual order:

1. Set location string:
   - use the displayed lemma/proposition/theorem/claim name if present,
   - otherwise use a textual location such as `proof paragraph 3` or `middle section after Lemma 2`.
2. Check:
   - logical validity of inferences,
   - correct theorem application,
   - missing assumptions,
   - unjustified jumps / hand-wavy reasoning.
3. Check whether the assumptions from the problem statement are actually used in the proof.
4. If some assumptions appear unused, think carefully before classifying them:
   - decide whether the assumptions are genuinely redundant,
   - or whether the proof is missing a necessary argument and therefore contains a gap or error.
5. Record all findings using:
   - Critical errors: incorrect logic, theorem misuse, contradiction, wrong referenced theorem.
   - Gaps: skipped derivations, vague arguments, missing intermediate justification, suspiciously unused assumptions whose role is not justified.
6. Append structured records to `statement_checks`.

### Step 3: External reference checking

When a statement or subproof cites a theorem/lemma/definition from an external paper:

1. Query `search_arxiv_theorems` with the full referenced statement text.
2. Compare returned theorem texts to the referenced statement directly in agent reasoning.
3. Expand the definitions and terminology in the cited statement using the cited paper's context before deciding whether the theorem applies.
4. Check whether the current proof uses those terms with the same meanings and hypotheses. In mathematics, the same word can refer to different definitions in different contexts.
5. Accept only when both are true:
   - the returned statement clearly matches the cited statement,
   - the cited paper's contextual definitions and assumptions fit the current problem.
6. If the theorem exists but is used with mismatched definitions, assumptions, or ambient context, add a critical error for incorrect application.
7. If no match is found, use Claude Code's built-in `WebSearch` tool with the same referenced statement.
8. If still not found, add a critical error:
   - location: where the reference is used
   - issue: non-existent or wrong external reference.
9. Append details to `reference_checks`.


### Step 4: Build verification report

Aggregate every error and gap across the full markdown proof.

`verification_report` must include:

- `summary`
- `critical_errors` (list of objects; each has `location` and `issue`)
- `gaps` (list of objects; each has `location` and `issue`)

Do not drop any finding.

### Step 5: Verdict rule and repair hints

Verdict rule is strict:

- Return `"correct"` if and only if both `critical_errors` and `gaps` are empty.
- Otherwise return `"wrong"`.

Repair hints:

- If verdict is `"correct"`, set `"repair_hints": ""`.
- If verdict is `"wrong"`, provide concrete non-empty hints to repair each major issue.

### Step 6: Output write and completion

Write final JSON using:

- `write_verification_output(run_id, payload)`

Target file must be:

- `results/{run_id}/verification.json`

Stop only after this file is written successfully.

## Output JSON Contract

The final response and file content must be:

```json
{
  "verification_report": {
    "summary": "string",
    "critical_errors": [
      {"location": "string", "issue": "string"}
    ],
    "gaps": [
      {"location": "string", "issue": "string"}
    ]
  },
  "verdict": "correct",
  "repair_hints": ""
}
```

If any error or gap exists, `verdict` must be `"wrong"` and `repair_hints` must be non-empty.

## Audit Dimensions

Verification runs five mandatory passes. Each writes findings into the appropriate memory channel; `$synthesize-verification-report` aggregates all of them into the final verdict.

1. **Sequential statement verification** (`$verify-sequential-statements`) — local logical validity, theorem applicability, gap detection, and the tagging-discipline check. Every displayed claim must end with a tag from the canonical taxonomy (`[def]`, `[hyp]`, `[calc N]`, `[cite: ...]`, `[from L.X]`, `[wlog: ...]`, `[ind: ...]`, `[comp]`, `[functoriality]`, `[naturality]`); untagged claims, unresolved tags, and tags that fail to justify their transition are critical errors. Skipped derivations are mandatory gaps. Banned phrases ("clearly", "obviously", etc.) without an attached tag are critical errors.

2. **Notation consistency** (`$check-notation-consistency`) — parses the proof's `## Notation` section (the generation agent flushes its `notation_dictionary` channel into this section at the top of the blueprint), builds a per-symbol usage map across the whole proof, and audits every symbol against:
   - undefined use (symbol in proof but not in `## Notation`),
   - multiple meanings,
   - silent renamings of borrowed notation,
   - drift from the cited source's definition,
   - unresolved sources.

   All five conditions produce critical errors. Orphan entries (declared but unused) are gaps.

3. **Computational replay** (`$check-computational-replay`) — for every numbered computation display and every chain tagged `[calc N]`, re-derives the right side from the left side using only the stated justification and the notation dictionary. Replay failures, conclusion-only computations (no displayed steps), and missing intermediate identities are critical errors or gaps as appropriate.

4. **Referenced statement validation** (`$check-referenced-statements`) — for every `[cite: ...]` tag, confirms via `search_arxiv_theorems` (with `WebSearch` fallback) that the cited statement exists and is being applied with matching definitions and hypotheses in the current proof's context.

5. **Synthesis** (`$synthesize-verification-report`) — aggregates findings across the four audits, applies the strict verdict rule (`correct` iff zero critical errors and zero gaps), and writes `results/{run_id}/verification.json`.

## Hard Invariants

1. Verify the markdown proof in textual order.
2. Include every critical error and every gap in the report.
3. External-paper references must be checked via `search_arxiv_theorems` first, then Claude Code's built-in `WebSearch` tool.
4. Accept iff there are zero errors and zero gaps.
5. Persist final JSON to `results/{run_id}/verification.json`.
6. The five audit passes are mandatory and in the stated order. Skipping any pass, or running them out of order, is a control-flow error.
