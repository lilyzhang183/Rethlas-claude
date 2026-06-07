---
name: check-computational-replay
description: For each numbered computation display in the proof, re-derive it line by line from prior steps, the notation dictionary, and cited identities. Classify each step into a four-level replay status (mechanically_ok, human_math_ok, needs_intermediate, failure) and emit findings at the matching severity. Mandatory step inserted after $check-notation-consistency and before $check-referenced-statements.
---

# Check Computational Replay

Missing computational steps and unstated intermediate manipulations are a major source of hidden errors. This skill re-derives every numbered computation in the proof to confirm that the displayed steps actually compose into the claimed result, and grades each step on a four-level scale instead of a binary pass/fail — research-level math frequently uses compressed but standard manipulations that should be tolerated, not rejected outright.

## Input Contract

Read:

- the full proof markdown
- the `## Notation` section (already parsed by `$check-notation-consistency`)
- the per-lemma local variable declarations
- each numbered display environment in the proof (typically labeled $(1), (2), \ldots$ or `eq:foo`) and any inline chain that the proof tags with `[calc N]`
- cited identities, lemmas, and definitions referenced from each computation step

## What counts as a computation step

A computation step is any single use of `=`, `\le`, `\ge`, `<`, `>`, `\equiv`, `\sim`, `\cong`, `\to`, `\mapsto`, or any other binary relation that produces a new expression from a previous one. Each step has:

- a **left side** (the prior expression),
- a **right side** (the new expression),
- a **justification** (the inline tag immediately attached: `[def: D<i>]`, `[from: L<x>.eq<y>]`, `[cite: paper_id, thm_id]`, `[hyp: H<i>]`, `[ind: name]`, `[comp]`, `[functoriality]`, `[naturality]`, etc.).

A display containing $a = b = c = d$ is parsed as three steps:
$(a = b)$, $(b = c)$, $(c = d)$, each with its own tag.

## Expected aligned form

Multi-step displayed computations are expected in the aligned-equation form, with one tag per step in the second column of the aligned environment:

```latex
\begin{aligned}
A
&= B && [def: D3] \\
&= C && [from: L2.eq1] \\
&= 0 && [hyp: H4].
\end{aligned}
\tag{E7}
```

The replay pass parses each aligned row as one step. If the display is *not* in aligned form (e.g. a single long line `$A = B = C = 0$ [from: L2]` with a single tag covering all transitions), classify every implicit step as `needs_intermediate` (`gap`) for the steps the tag does not actually justify. Generation should rewrite into aligned form; verifier should not silently accept compressed multi-step chains.

Single-step displayed equalities (one `=`) without an `aligned` environment are accepted as long as they carry one inline tag.

## Replay-status taxonomy

For each computation step, classify the replay attempt into one of four statuses:

| Status                | Meaning                                                                                                                                                                                                       | Severity                |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `mechanically_ok`     | Direct syntactic rewrite. The right side falls out of the left side by applying the stated justification verbatim (substitution, named theorem, exact identity from a cited equation).                       | none                    |
| `human_math_ok`       | The step is valid by a common algebraic manipulation that a mathematician in the field would accept on sight (e.g. expanding a bracket, reindexing a sum, applying a standard inequality named in the tag). | none (or `warning` if untagged) |
| `needs_intermediate`  | The step is likely valid but is too compressed — going from left to right requires an unstated intermediate identity that should be displayed.                                                                | `gap`                   |
| `failure`             | The step is actually wrong or its stated justification does not support it.                                                                                                                                  | `critical_error`        |

`human_math_ok` is the *anti-false-positive* status: research math routinely compresses two or three algebraic moves into one displayed step. This skill records the move but does not flag it as a gap, *as long as the tag accurately names the manipulation type*. If the tag is missing or wrong, the same step becomes `needs_intermediate` or `failure`.

## Procedure

### Step 1: Locate every computation

Identify every numbered display environment in the proof, and every inline chain tagged `[calc N]`. Each display is treated as a sequence of computation steps.

### Step 2: Replay each step

For each computation step:

1. Identify the rewrite rule the justification provides:
   - `[def: name]` — substitution from the definition; should be `mechanically_ok`.
   - `[from L.X, Eq.Y]` — apply identity from a previously proved lemma; usually `mechanically_ok`, sometimes `human_math_ok` if combined with reindexing.
   - `[cite: paper_id, thm_id]` — apply external identity; inspect the cited statement first.
   - `[hyp: H1]` — apply a named hypothesis.
   - `[ind: name]` — apply the named induction hypothesis.
   - `[comp]` / `[functoriality]` / `[naturality]` — categorical move; check that the morphisms/functors involved are named and the move applies.
2. Attempt to reconstruct the right side from the left side using only that rewrite rule + the notation dictionary + previously verified steps.
3. Decide replay status:
   - exact match after one rewrite → `mechanically_ok`.
   - match after one rewrite plus a single common algebraic move (bracket expansion, sign flip, reindexing) that is consistent with the stated tag → `human_math_ok`.
   - cannot reconstruct without an unstated intermediate identity, even with charitable algebraic reading → `needs_intermediate`.
   - reconstruction produces a different result, or the stated justification does not entail the rewrite at all → `failure`.

If the justification cites an external theorem that has not yet been inspected, query `search_theorem_index` (and `WebSearch` as fallback) to retrieve the statement before classifying.

### Step 3: Emit findings at the matching severity

- `mechanically_ok` → no finding.
- `human_math_ok` → no finding, unless the step is untagged or tagged incorrectly, in which case emit a `warning`.
- `needs_intermediate` → emit a `gap` at the step location with issue `"intermediate identity needed; please display"`.
- `failure` → emit a `critical_error` at the step location with issue `"computation step cannot be replayed from its stated justification"` plus the attempted reconstruction.

Additionally:

- **Untagged step.** No inline justification tag at all. → `critical_error` (also caught by `$verify-sequential-statements`).
- **Conclusion-only computation.** A claim asserts a computational result (e.g., "Thus $T(\eta) = 0$") but no numbered display or `[calc N]` tag accompanies it. → `critical_error` at the claim location with issue `"computation stated as conclusion without displayed steps"`.

### Step 4: Persist

Append one record per audited computation to `statement_checks` with sub-shape:

```json
{
  "record_subtype": "computational_replay",
  "computation_label": "(3)",
  "location": "Lemma 5 proof, display (3)",
  "steps": [
    {
      "step_index": 1,
      "left": "$d\\omega + [\\eta,\\omega]$",
      "right": "$d\\omega - [\\omega,\\eta]$",
      "justification_tag": "[from L.2, Eq.4]",
      "replay_status": "mechanically_ok"
    },
    {
      "step_index": 2,
      "left": "$d\\omega - [\\omega,\\eta]$",
      "right": "$-[\\omega, d\\eta]$",
      "justification_tag": "[from L.3]",
      "replay_status": "needs_intermediate",
      "missing_intermediate": "expansion using cocycle identity (cite L.3 step explicitly)"
    }
  ],
  "critical_errors": [],
  "gaps": [{"location": "Lemma 5 proof, display (3), step 2", "issue": "intermediate identity needed; please display", "severity": "gap"}],
  "warnings": []
}
```

Append an `events` record `event_type="computational_replay_audit_complete"` summarizing total steps and the count at each replay status.

## Hard Invariants

1. Every numbered computation display in the proof must have every step tagged.
2. Computations stated only as conclusions are `critical_error`. The proof must display the work or cite a single justification on the same line.
3. Cited external identities must be inspected via `search_theorem_index` before being accepted as a rewrite source.
4. The four-status taxonomy is mandatory; do not collapse `human_math_ok` into `mechanically_ok` (which would hide which steps depend on domain convention) or into `needs_intermediate` (which would inflate gap counts on valid proofs).

## Output Contract

Per-computation audit records appended to `statement_checks` with `record_subtype="computational_replay"`. Summary `events` record. `$synthesize-verification-report` partitions per severity and applies the verdict rule.

## Tools

- `search_theorem_index`
- Claude Code's built-in `WebSearch` tool
- `memory_append`
- `memory_query`
