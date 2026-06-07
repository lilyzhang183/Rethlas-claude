---
name: verify-sequential-statements
description: Verify a markdown proof in the order it is written. Use when the task is to check local correctness, theorem applicability, and reasoning gaps statement by statement through a paper-style proof.
---

# Verify Sequential Statements

Check each statement and subproof in order and log all local issues.

## Input Contract

Assume:

- `Proof` is markdown text.
- The proof is written in good mathematical order.
- `Statement` contains the target theorem statement and its hypotheses.

Do not split the proof with utility code. Read the markdown in order and use its own structure.

## Procedure

1. Extract the assumptions and hypotheses from `Statement` before checking the proof.
2. Iterate through the statements/subproofs in the order they appear in the markdown.
3. For each item, determine a location key:
   - use the displayed theorem/lemma/claim heading if present,
   - otherwise use a local textual locator such as `proof paragraph 2`.
4. Check local reasoning:
   - Is the inference valid?
   - Are assumptions stated and sufficient?
   - Is each theorem application valid in context?
   - Are there skipped or hand-wavy steps?
5. Audit whether the assumptions from `Statement` are actually used in the proof.
6. If some assumptions seem unused, do not assume they are harmless. Reason carefully about whether:
   - the assumption is truly redundant, or
   - the proof is silently omitting a necessary use of it and therefore has a gap or error.
7. Classify findings:
   - `critical_error`: logical contradiction, invalid theorem use, false implication, **untagged claim** (see §"Tagging discipline" below), **banned-phrase transition** (see §"Banned phrases" below).
   - `gap`: missing derivation, vague justification, unsupported step, or suspiciously unused assumptions whose role is not justified. **Skipped derivations are mandatory gaps** — do not treat them as discretionary.
8. Persist each checked item to `statement_checks` using `memory_append`.

## Tagging discipline (mandatory check)

Every displayed claim in the proof must end with exactly one inline justification tag drawn from the canonical taxonomy. Acceptable tag labels:

`[def: name]`, `[hyp: H<i>]`, `[calc N]`, `[cite: paper_id, thm_id]`, `[from L.X]` / `[from L.X, Eq.Y]`, `[wlog: reason]`, `[ind: name]`, `[comp]`, `[functoriality]`, `[naturality]`.

Note: the hypothesis tag is **`[hyp: H<i>]`** with an explicit hypothesis identifier (e.g. `[hyp: H1]`, `[hyp: H2]`, `[hyp: local A]`). The bare `[hyp]` (no identifier) is no longer accepted — it produced uninformative "unused assumption" checks. The proof must list its hypotheses by name in a `## Assumptions` block (alongside `## Notation`), and every `[hyp: H<i>]` tag must resolve to one of those listed assumptions.

For each displayed claim:

1. **Untagged claim → critical error.** If a displayed claim has no inline tag from the taxonomy, record a critical error at that location with issue `"claim missing inline justification tag"`. This is not optional.
2. **Tag uses an unknown label → critical error.** If a tag uses a label not in the taxonomy above (including bare `[hyp]` without an identifier), record a critical error with issue `"unrecognized justification tag <label>"`.
3. **Tag fails to resolve → critical error.** `[from L.7]` when there is no Lemma 7; `[calc 3]` when there is no display (3); `[def: foo]` when `foo` is not in the proof's `## Notation` section or any prior definition; `[hyp: H3]` when `H3` is not listed in `## Assumptions`. → critical error with issue `"justification tag does not resolve"`.
4. **Tag does not justify the transition → critical error.** The cited lemma/definition/computation/hypothesis exists, but it does not actually entail the move from the previous line to this one. → critical error with issue `"tag resolves but does not justify the stated transition"`.

### Assumption-usage audit

Read the `## Assumptions` block. For each listed hypothesis `H<i>`:

- If at least one claim in the proof carries `[hyp: H<i>]` and that claim's transition genuinely depends on `H<i>` → assumption used. Pass.
- If no claim carries `[hyp: H<i>]` but the `## Notation` entry for `H<i>` is annotated `usage: "unused-by-design"` with a one-sentence reason → pass (recorded for the report as informational).
- Otherwise → `gap` at location `## Assumptions, H<i>` with issue `"assumption listed but never invoked in any [hyp: H<i>] tag"`.

If the problem statement names a hypothesis that is missing entirely from `## Assumptions`, record a `critical_error` at location `## Assumptions` with issue `"hypothesis from problem statement is not listed in ## Assumptions block"`.

## Banned phrases (always trigger a critical error)

The following phrases, appearing inside the proof text without an immediately-following resolved tag, are critical errors — they signal an unstated transition:

- "clearly", "obviously", "trivially"
- "it follows that", "it is easy to see that" (without an immediately-following `[from ...]` or `[cite: ...]` tag on the same line)
- "by symmetry" (without an immediately-following `[from ...]` tag naming the symmetry)
- "by a standard argument", "as usual"
- "we omit the details"

Record one critical error per occurrence with issue `"banned phrase <phrase> indicates unstated transition"`.

## Output Contract

Append records to `statement_checks` with structure like:

```json
{
  "location": "Lemma 3",
  "status": "checked",
  "critical_errors": [
    {"location": "Lemma 3", "issue": "Incorrect implication from A to B."}
  ],
  "gaps": [
    {"location": "Lemma 3", "issue": "Missing justification of boundedness."}
  ]
}
```

## MCP Tools

- `memory_append`
- `memory_query`
