---
name: self-audit
description: Read your own assembled blueprint against an eleven-check hard checklist before calling the verification service. Emits findings at three severities (critical_error, gap, warning); audit passes iff zero critical_errors AND zero gaps. Records the blueprint sha256 and a self_audit_id so the generation/verification handshake can prove the verifier approved the exact byte state that was audited. Hard-fail — must pass before $verify-proof is allowed.
---

# Self-Audit

Run this skill on the assembled `results/{problem_id}/blueprint.md` *before* invoking `$verify-proof`. The audit catches the issues that would otherwise round-trip through the verifier and waste a verification call. **Hard-fail mode**: any `critical_error` or `gap` blocks verification. Warnings record cleanup opportunities but do not block.

## Input Contract

Read:

- `results/{problem_id}/blueprint.md` in full as plain markdown text
- the original problem markdown at `data/{problem_id}.md`
- the current contents of `notation_dictionary`
- the most recent `verification_reports` entry, if any, to ensure earlier issues have not regressed

## Audit Checklist

The audit consists of twelve checks. Each check emits findings at the appropriate severity. The overall audit passes iff zero critical_errors **and** zero gaps; warnings do not block.

### Check 1: Three-tier notation coverage

The blueprint must contain a `## Notation` section near the top (after the title, before the first lemma) listing every **Tier-1 (global)** entry from `notation_dictionary`. Tier-2 (local) variables are declared at their introduction site inside each lemma; Tier-3 (standard constants whitelist + glossary `# Standard Constants`) need no declaration.

For each symbol used anywhere in the blueprint, classify by lookup order: Tier-2 local table, then Tier-1 `## Notation`, then Tier-3 whitelist.

**Severity:**
- Symbol classifiable into none of the three tiers → `critical_error` at first use.
- Tier-1 entry declared in `## Notation` but never used → `warning` (cleanup, not a block).
- Tier-1 entry contradicted by usage in the proof → `critical_error`.
- Local symbol leaking outside its lemma scope → `critical_error`.

### Check 2: Assumptions block present and complete

The blueprint must contain a `## Assumptions` block (alongside `## Notation`) listing every hypothesis from the problem statement with an explicit identifier:

```markdown
## Assumptions
- H1: $M$ is a smooth manifold.
- H2: $\mathcal{F}$ is a singular foliation on $M$.
- H3: $p$ is a fixed point of every leaf-preserving symmetry.
```

**Severity:**
- `## Assumptions` block missing → `critical_error`.
- A hypothesis from the problem statement is missing from the block → `critical_error`.
- A hypothesis is listed but never invoked via a `[hyp: H<i>]` tag and not annotated `usage: "unused-by-design"` in `notation_dictionary` → `gap`.

### Check 3: Every claim carries a justification tag

Every displayed claim must end with exactly one tag from the canonical taxonomy:

`[def: name]`, `[hyp: H<i>]`, `[calc N]`, `[cite: paper_id, thm_id]`, `[from L.X]` / `[from L.X, Eq.Y]`, `[wlog: reason]`, `[ind: name]`, `[comp]`, `[functoriality]`, `[naturality]`.

The bare `[hyp]` form (no identifier) is **not** accepted; replace with `[hyp: H<i>]` referencing the `## Assumptions` block.

**Severity:**
- Untagged displayed claim → `critical_error`.
- Tag uses unknown label (including bare `[hyp]`) → `critical_error`.
- Tag fails to resolve (`[from L.7]` with no L.7, `[hyp: H4]` with no H4, etc.) → `critical_error`.

### Check 4: Numbered computation displays are referenced

If display `(N)` exists but no claim tags `[calc N]`, the display is orphaned. **Severity:** `warning` (delete the orphan or use it; not a correctness block).

### Check 5: Every cited external result has complete source identifiers

For every `[cite: ...]` tag, the proof body must include nearby the complete cited statement, the `paper_id`, the `theorem_id`, and the arXiv id when applicable.

**Severity:** Missing `paper_id` or `theorem_id` → `critical_error`. Missing arXiv id when one exists → `gap`. Cited statement not reproduced near the citation → `gap`.

### Check 6: Original problem statement reproduced verbatim

The final theorem section's `## statement` must contain the original problem statement from `data/{problem_id}.md` byte-for-byte.

**Severity:** Any paraphrase, shortened form, or notational adjustment in `## statement` → `critical_error`. Notational adjustments belong in `## Notation`, not in the statement.

### Check 7: No banned phrases

Search the blueprint for: "clearly", "obviously", "trivially", "it is easy to see", "it follows that" (without an immediately-following `[from ...]` or `[cite: ...]` tag), "by symmetry" (without an immediately-following `[from ...]` tag), "by a standard argument", "as usual", "we omit the details".

**Severity:** Any match → `critical_error`. Rewrite using `$enforce-step-granularity`.

### Check 8: Numbered objects appear before they are cited

`[from L.3]` must follow Lemma 3 in textual order. Likewise for `[calc N]`, `[def: name]`, `[ind: name]`. **Severity:** Forward reference → `critical_error`.

### Check 9: Supporting lemmas precede the main theorem

The main theorem section must be the last `# theorem` heading in the blueprint, and every `[cite]` / `[from L.X]` tag inside its proof must point either backward in the blueprint or to an external result with full identifiers. **Severity:** Violation → `critical_error`.

### Check 10: Rigor-mode triple-hash is current and recorded

Compute three hashes for the rigor-mode artifact triple:

- `blueprint_sha256 = sha256(blueprint.md as bytes)`
- `proof_obligations_sha256 = sha256(results/{problem_id}/proof_obligations.json as bytes)`
- `notation_dictionary_sha256 = sha256(memory/{problem_id}/notation_dictionary.jsonl as bytes)`

Record all three in the audit output. The `$verify-proof` skill will pass them to `verify_proof_service` so the verifier can confirm it audited the exact byte state being verified. Any edit to any of the three files invalidates the audit and requires a fresh `$self-audit` run.

**Severity:** This check is a record-keeping operation. If `proof_obligations.json` is missing in rigor mode, this becomes a `critical_error` with issue `"proof_obligations.json absent; rigor mode requires the structural DAG to be present"`.

### Check 11: Notation_dictionary <-> Notation section consistency

Every Tier-1 (`scope=global`) entry in `notation_dictionary` must appear as a bullet in `## Notation`, and vice versa. Tier-2 (`scope=local`) entries appear in the dictionary for the parent agent's bookkeeping but are not flushed to `## Notation`. Tier-3 (`scope=standard`) entries from the glossary `# Standard Constants` extend the whitelist and may be silently omitted from `## Notation`.

**Severity:** Tier-1 entry in dictionary missing from `## Notation`, or vice versa → `critical_error`.

### Check 12: Proof-obligation graph is structurally valid

Read `results/{problem_id}/proof_obligations.json` and audit:

1. Every nontrivial assertion in `blueprint.md` (every lemma, proposition, theorem, claim, numbered equation, and tagged computation) has a corresponding node.
2. The DAG is acyclic.
3. No node depends on itself directly or transitively.
4. `MainThm` does not appear in the dependency chain of any of its dependencies.
5. Every `MainThm`-reachable node has `status` in `{proved_in_blueprint, external_citation}` (no `stub` or `blocked`).
6. Every inline justification tag in `blueprint.md` corresponds to an entry in the appropriate node's `depends_on`.

**Severity:** Any of 1–6 violated → `critical_error`. This pre-empts the verifier's structural check; if `$check-proof-obligation-graph` would reject the blueprint, `$self-audit` rejects it first so no verification call is wasted.

## Procedure

1. Read the blueprint and the original problem markdown.
2. Run Check 1 through Check 11 in order, classifying each finding at its severity.
3. Compute `blueprint_sha256` (Check 10).
4. Allocate a fresh `audit_id` (e.g. `audit_{timestamp}_{short_hash}`).
5. If any `critical_error` or `gap` was emitted, the audit **fails**. Append the audit record (see below) with `audit_pass=false`. Do not call `$verify-proof`. Revise the blueprint to address every finding using `$enforce-step-granularity`, `$align-with-source-notation`, `$direct-proving`, etc. Re-run `$self-audit`; a new `audit_id` is allocated each run.
6. If only `warning`s (or no findings) were emitted, the audit **passes**. Append the audit record with `audit_pass=true`. Proceed to `$verify-proof` with `blueprint_sha256` and `audit_id` passed through.

## Audit record shape

Append a single JSON record per audit run to `verification_reports` with `record_type="self_audit"`:

```json
{
  "record_type": "self_audit",
  "audit_id": "audit_20260607T134522Z_a4f29b1c",
  "blueprint_sha256": "9f3c8b6d...e1a7",
  "proof_obligations_sha256": "2c4e1a7b...8d3f",
  "notation_dictionary_sha256": "6a90b5f1...c2e8",
  "audit_pass": true,
  "checks_run": ["check_1", ..., "check_12"],
  "critical_errors": [],
  "gaps": [],
  "warnings": [
    {"check": "check_4", "location": "display (7) in Lemma 3", "issue": "orphan numbered display; either delete or reference via [calc 7]", "severity": "warning"}
  ]
}
```

## Hard-Fail Invariant

`$verify-proof` must refuse to invoke `verify_proof_service` unless:

1. the most recent `self_audit` record has `audit_pass=true`, AND
2. the current `sha256(blueprint.md)` equals the recorded `blueprint_sha256`, AND
3. the current `sha256(proof_obligations.json)` equals the recorded `proof_obligations_sha256`, AND
4. the current `sha256(notation_dictionary.jsonl)` equals the recorded `notation_dictionary_sha256`.

Any edit to any of the three files after a passing audit changes its sha256 and invalidates that audit; `$self-audit` must be re-run before the next verification call.

## Output Contract

One JSON record per `$self-audit` run, written to `verification_reports` with `record_type="self_audit"` and the shape above. The `audit_id` and `blueprint_sha256` are forwarded to `verify_proof_service` by `$verify-proof`.

## MCP Tools

- `memory_append` (channel: `verification_reports`, `events`)
- `memory_query` (preferred over BM25 search for finding the most recent self_audit by `blueprint_sha256`)
- `memory_search` (for fuzzy lookup of past audit findings)

## Failure Logging

If the same check fails repeatedly across multiple audit rounds (e.g. step granularity cannot be achieved without a missing lemma), append to `failed_paths` and route the work to `$identify-key-failures`.
