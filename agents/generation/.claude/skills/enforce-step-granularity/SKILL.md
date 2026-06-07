---
name: enforce-step-granularity
description: Split every transition between displayed claims into atomic steps, each carrying exactly one inline justification tag. Use during direct-proving, recursive-proving, and any blueprint revision; required reading before invoking self-audit.
---

# Enforce Step Granularity

Proof jumps are the leading cause of verifier-detected gaps. This skill forces every transition between displayed claims to be **one** of a small fixed set of atomic moves, each tagged. Multi-step jumps are not allowed; they must be split.

## The Atomic Moves

A transition from one displayed claim to the next must be exactly one of:

1. **One named theorem/lemma application** — tagged `[cite: paper_id, thm_id]` for an external result or `[from: L<x>]` / `[from: L<x>.eq<y>]` / `[from: L<x>.claim<y>]` for a previously proved local lemma. The colon form is preferred; legacy `[from L.X]` is still accepted.
2. **One definitional unfolding** — tagged `[def: D<i>]` referencing a definition in the `## Definitions` block (e.g. `[def: D3]`). The bare `[def: name]` form is **not** accepted; every definition use must name an indexed definition so the proof-obligation graph can trace dependency precisely.
3. **One displayed computation** — tagged `[calc: E<n>]` referring to a numbered display environment labeled `(E<n>)`. Chained equalities $a = b = c = d$ are permitted *inside* one numbered display, but every `=` step carries its own inline tag.
4. **One hypothesis use** — tagged `[hyp: H<i>]` where `H<i>` is the identifier of the assumption listed in the proof's `## Assumptions` block (e.g. `[hyp: H1]`, `[hyp: H2]`, `[hyp: local A]`). The bare `[hyp]` form is not accepted; every hypothesis use must name *which* hypothesis is being invoked.
5. **One induction step** — tagged `[ind: name]`. The induction hypothesis must be named and previously stated.
6. **One composition / functoriality / naturality move** (category-style proofs) — tagged `[comp]`, `[functoriality]`, or `[naturality]`. The morphisms or functors involved must be named in the surrounding text.
7. **One without-loss-of-generality reduction** — tagged `[wlog: reason]`. The reason must be a one-clause justification.

Anything else — "it follows", "we then obtain", "by a standard argument", "by symmetry", "clearly" — is a multi-step jump and must be split.

## Input Contract

Read:

- the candidate proof step or transition under consideration
- the surrounding displayed claims
- the current `notation_dictionary`
- any prior `verification_reports` flagging gaps at this location

## Procedure

1. Identify the source claim and the target claim of the transition.
2. Ask: which atomic move from the list above carries this transition? If no single move suffices, the transition is compound — go to step 3. If exactly one move suffices, go to step 4.
3. **Splitting a compound transition.** Insert one or more intermediate displayed claims, each itself the result of one atomic move. Number the new intermediate claims and tag them. Re-check granularity for each new transition.
4. **Tagging the transition.** Append the appropriate inline tag at the end of the target claim line, using the canonical bracketed form. Examples:
   - `Therefore $\phi$ is injective. [from L.3, Eq.7]`
   - `Hence $H^*(M) \cong H^*(N)$. [cite: arXiv:2103.04567, Thm 1.2]`
   - `So $\eta = d\alpha$ on $U_i$. [def: closed form]`
   - `By chain rule, $df_p(v) = J_p \cdot v$. [calc 4]`
   - The diagram commutes. [naturality]
5. **Persist.** Append a record to `proof_steps`:

```json
{
  "step_id": "lem-X.Y.Z",
  "transition": "from <source> to <target>",
  "atomic_move": "cite|def|calc|hyp|ind|comp|functoriality|naturality|wlog",
  "tag": "[from L.3, Eq.7]",
  "split_from_compound": true,
  "intermediate_steps_added": ["step_id_a", "step_id_b"]
}
```

6. If the transition cannot be reduced to a chain of atomic moves, **the claim is not yet proved**. Append to `failed_paths` with `record_type="ungranular_transition"` and route the work back to `$direct-proving` or `$search-math-results` to find the missing intermediate lemma.

## Banned phrases (always require splitting)

- "clearly", "obviously", "trivially"
- "it follows that", "it is easy to see that"
- "by symmetry" without naming the symmetry as a `[from ...]` reference
- "by a standard argument", "as usual"
- "we omit the details"

These appearing in a candidate blueprint are a hard signal that the transition is unsplit. `self-audit` flags them as critical issues.

## Output Contract

Each transition in `blueprint.md` ends with exactly one inline justification tag drawn from the taxonomy above. Each tagged step has a corresponding `proof_steps` record.

## MCP Tools

- `memory_append` (channel: `proof_steps`, `failed_paths`, `events`)
- `memory_search` (to locate the lemma referenced by `[from L.X]`)

## Failure Logging

If splitting requires a lemma that does not exist yet, append a `subgoals` record proposing the missing lemma, then invoke `$direct-proving` on it before continuing the current chain.
