---
name: check-computational-replay
description: For each numbered computation display in the proof, re-derive it line by line from previously displayed steps, cited identities, and the notation dictionary; flag any equality that cannot be reconstructed and any computation that exists only as a conclusion. Mandatory step inserted after $check-notation-consistency and before $check-referenced-statements.
---

# Check Computational Replay

Missing computational steps and unstated intermediate manipulations are a major source of hidden errors. This skill re-derives every numbered computation in the proof to confirm that the displayed steps actually compose into the claimed result.

## Input Contract

Read:

- the full proof markdown
- the `## Notation` section (already parsed by `$check-notation-consistency`)
- each numbered display environment in the proof — typically marked as $(1), (2), \ldots$ or `eq:foo`, etc. — and any inline chain $a = b = c = d$ that the proof tags with `[calc N]`
- cited identities, lemmas, and definitions referenced from each computation step

## What counts as a computation step

A computation step is any single use of `=`, `\le`, `\ge`, `<`, `>`, `\equiv`, `\sim`, `\cong`, `\to`, `\mapsto`, or any other binary relation that produces a new expression from a previous one. Each step has:

- a **left side** (the prior expression),
- a **right side** (the new expression),
- a **justification** (the inline tag immediately attached: `[def: name]`, `[from L.X, Eq.Y]`, `[cite: paper_id, thm_id]`, `[hyp]`, `[ind: name]`, `[comp]`, `[functoriality]`, `[naturality]`, etc.).

A display containing $a = b = c = d$ is parsed as three steps:
$(a = b)$, $(b = c)$, $(c = d)$, each with its own tag.

## Procedure

### Step 1: Locate every computation

Identify every numbered display environment in the proof, and every inline chain tagged `[calc N]`. Each display is treated as a sequence of computation steps.

### Step 2: Replay each step

For each computation step, attempt to reconstruct the right side from the left side using **only** the justification cited in the tag, the notation dictionary, and previously verified steps. The reconstruction must:

1. Identify the rewrite rule the justification provides:
   - `[def: name]` — the definition is in `## Notation` or stated in a numbered display above; substitution should produce the right side directly.
   - `[from L.X, Eq.Y]` — the lemma L.X provides an identity (or a specific equation Y inside L.X) that rewrites the left side to the right side.
   - `[cite: paper_id, thm_id]` — the cited theorem provides an identity; the verifier must inspect the cited statement to confirm the rewrite is valid.
   - `[hyp]` — a hypothesis from the problem statement provides the rewrite.
   - `[ind: name]` — the induction hypothesis named provides the rewrite.
   - `[comp]` / `[functoriality]` / `[naturality]` — the rewrite is a categorical move; the verifier checks that the morphisms/functors involved are named and that the move applies.
2. Apply the rewrite mechanically and compare the result against the displayed right side. If they match (up to notational normalization defined in `## Notation`), the step replays.
3. If they do not match, the step is a **replay failure**.

If the justification cites an external theorem the verifier has not yet inspected, query `search_arxiv_theorems` (and `WebSearch` as fallback) to retrieve the statement before attempting replay.

### Step 3: Flag failures

- **Replay failure.** The step's right side cannot be obtained from its left side using only its stated justification. → critical error at the step's location with issue `"computation step cannot be replayed from its stated justification"`.
- **Untagged step.** The step has no inline justification tag. → critical error (also caught by `$verify-sequential-statements`, but record here too for the computational audit).
- **Conclusion-only computation.** A claim asserts a computational result (e.g., "Thus $T(\eta) = 0$") but no numbered display was given and no `[calc N]` tag was attached. → critical error at the claim location with issue `"computation stated as conclusion without displayed steps"`.
- **Missing intermediate.** The displayed steps are too coarse — going from one line to the next would require an unstated intermediate identity. → gap at the step location with issue `"intermediate identity needed; please display"`.

### Step 4: Persist

Append one record per audited computation to `statement_checks` with sub-shape:

```json
{
  "record_subtype": "computational_replay",
  "computation_label": "(3)" | "eq:cocycle" | "calc 4",
  "location": "Lemma 5 proof, display (3)",
  "steps": [
    {
      "step_index": 1,
      "left": "$d\\omega + [\\eta,\\omega]$",
      "right": "$d\\omega - [\\omega,\\eta]$",
      "justification_tag": "[from L.2, Eq.4]",
      "replay_status": "ok|failure|missing_intermediate"
    }
  ],
  "critical_errors": [{"location": "...", "issue": "..."}],
  "gaps": [{"location": "...", "issue": "..."}]
}
```

Append an `events` record `event_type="computational_replay_audit_complete"` summarizing total steps, replay successes, replay failures.

## Hard Invariants

1. Every numbered computation display in the proof must have every `=` (or other relation) tagged and replayable.
2. Computations stated only as conclusions are critical errors. The proof must display the work.
3. Cited external identities must be inspected via `search_arxiv_theorems` before being accepted as the justification for a rewrite.

## Output Contract

Per-computation audit records appended to `statement_checks` with `record_subtype="computational_replay"`. Summary `events` record. `$synthesize-verification-report` aggregates these.

## Tools

- `search_arxiv_theorems`
- Claude Code's built-in `WebSearch` tool
- `memory_append`
- `memory_query`
