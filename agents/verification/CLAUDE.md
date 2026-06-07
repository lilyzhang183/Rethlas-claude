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
2. `$check-proof-obligation-graph`
3. `$check-notation-consistency`
4. `$check-computational-replay`
5. `$check-referenced-statements`
6. `$synthesize-verification-report`

`$check-proof-obligation-graph` is the structural rigor backbone. It loads `proof_obligations.json` (supplied alongside the proof in the verification request) and validates the DAG: no cycles, no forward references, no self-dependence, no hidden dependencies missing from `depends_on`, and every node reachable from `MainThm` is proved or externally cited. If the graph is missing, unparseable, or violates any of these properties, the verdict is `wrong`.

`$check-notation-consistency` and `$check-computational-replay` are the per-symbol and per-step audits described under "Audit Dimensions" below.


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

1. Query `search_theorem_index` with the full referenced statement text.
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

The four fields `summary`, `critical_errors`, `gaps`, and `warnings` are all required; empty arrays are acceptable but the keys must be present.

If any `critical_error` or `gap` exists, `verdict` must be `"wrong"` and `repair_hints` must be non-empty. Warnings do **not** block correctness; orphan notation, redundant declarations, and style issues are recorded as warnings and do not move `verdict` from `correct` to `wrong`.

## Audit Dimensions

Verification runs five mandatory passes. Each writes findings into the appropriate memory channel; `$synthesize-verification-report` aggregates all of them into the final verdict.

### Severity ladder

All findings carry one of three severities. The verdict rule depends only on the first two:

- `critical_error` — proof is mathematically invalid or applies a nonexistent / misused theorem. **Blocks `verdict=correct`.**
- `gap` — proof may be true but missing a needed argument, justification, or computation. **Blocks `verdict=correct`.**
- `warning` — style, cleanup, orphan notation entries, redundant declarations, stale memory. **Does NOT block `verdict=correct`.**

### Pass-by-pass

0. **Proof-obligation graph** (`$check-proof-obligation-graph`) — loads `proof_obligations.json` and validates it as a DAG. Flags cycles, forward references, missing nodes, self-dependence, hidden dependencies (tags whose target is not declared in `depends_on`), unreached main-theorem subgraph, and any stub/blocked obligation reachable from the main theorem. Turns "no circular reasoning" into a data invariant that markdown-only audits cannot catch.

1. **Sequential statement verification** (`$verify-sequential-statements`) — local logical validity, theorem applicability, gap detection, and the tagging-discipline check. Every displayed claim must end with a tag from the canonical taxonomy (`[def: name]`, `[hyp: H<i>]`, `[calc N]`, `[cite: ...]`, `[from L.X]`, `[wlog: ...]`, `[ind: ...]`, `[comp]`, `[functoriality]`, `[naturality]`); the bare `[hyp]` form (no identifier) is no longer accepted. Untagged claims, unresolved tags, and tags that fail to justify their transition are critical errors. Skipped derivations are mandatory gaps. Banned phrases ("clearly", "obviously", etc.) without an attached tag are critical errors. The pass also audits the proof's `## Assumptions` block: hypotheses listed but never invoked via `[hyp: H<i>]` are gaps; hypotheses from the problem statement missing from `## Assumptions` are critical errors.

2. **Notation consistency** (`$check-notation-consistency`) — parses the proof's `## Notation` section (the generation agent flushes Tier-1 entries from its `notation_dictionary` into this section) plus per-lemma local variable declarations, and audits every symbol used in the proof under a three-tier strictness model:
   - **Tier 1 (global)** — declared in `## Notation`. Audited strictly: undefined use, multiple meanings, silent renamings, drift from cited source, unresolved sources are all critical errors. Tier-1 entries declared but never used are **warnings** (down from gaps — they do not block correctness).
   - **Tier 2 (local)** — bound variables declared at their introduction site inside a single lemma proof. Audited for scope leakage (critical error if a local symbol is re-used outside its lemma) and conflicting redeclaration.
   - **Tier 3 (standard)** — whitelist of universal symbols (`\mathbb{N}`, `\mathbb{R}`, `id`, `\emptyset`, etc.) plus glossary `# Standard Constants` extensions. No audit; the verifier resolves from the whitelist.

3. **Computational replay** (`$check-computational-replay`) — for every numbered computation display and every chain tagged `[calc N]`, re-derives the right side from the left side using only the stated justification, the notation dictionary, and previously verified steps. Classifies each step into a four-level taxonomy:
   - `mechanically_ok` — direct syntactic rewrite. No finding.
   - `human_math_ok` — valid by a standard algebraic manipulation consistent with the stated tag. No finding (warning if the tag is missing or misclassifies the manipulation).
   - `needs_intermediate` — likely valid but too compressed; missing intermediate identity. Gap.
   - `failure` — actually wrong or unsupported by the stated justification. Critical error.

   Conclusion-only computations (assertions of computational results without any displayed steps or `[calc N]`) are critical errors regardless of replay outcome.

4. **Referenced statement validation** (`$check-referenced-statements`) — for every `[cite: ...]` tag, confirms via `search_theorem_index` (with `WebSearch` fallback) that the cited statement exists and is being applied with matching definitions and hypotheses in the current proof's context.

5. **Synthesis** (`$synthesize-verification-report`) — aggregates findings across the four audits, partitions by severity, applies the strict verdict rule (`correct` iff zero critical_errors AND zero gaps; warnings do not block), and writes `results/{run_id}/verification.json` with all three severity arrays populated.

## Hard Invariants

1. Verify the markdown proof in textual order.
2. Include every critical error and every gap in the report.
3. External-paper references must be checked via `search_theorem_index` first, then Claude Code's built-in `WebSearch` tool.
4. Accept iff there are zero errors and zero gaps.
5. Persist final JSON to `results/{run_id}/verification.json`.
6. The six audit passes are mandatory and in the stated order (sequential → graph → notation → replay → references → synthesis). Skipping any pass, or running them out of order, is a control-flow error.
