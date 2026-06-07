---
name: self-audit
description: Read your own assembled blueprint against a hard checklist (tagged claims, displayed computations, notation dictionary coverage, full citations, original statement verbatim, banned phrases) before calling the verification service. Hard-fail — must pass before $verify-proof is allowed.
---

# Self-Audit

Run this skill on the assembled `results/{problem_id}/blueprint.md` *before* invoking `$verify-proof`. The audit catches the issues that would otherwise round-trip through the verifier and waste a verification call. **Hard-fail mode**: any unchecked item blocks verification; revise the blueprint until the audit passes.

## Input Contract

Read:

- `results/{problem_id}/blueprint.md` in full as plain markdown text
- the original problem markdown at `data/{problem_id}.md`
- the current contents of `notation_dictionary`
- the most recent `verification_reports` entry, if any, to ensure earlier issues have not regressed

## Audit Checklist

The audit consists of nine checks. Each is binary (pass / fail). All nine must pass.

### Check 1: Notation section present and synchronized

The blueprint must contain a `## Notation` section near the top (after the title, before the first lemma). Every entry in `notation_dictionary` must appear as a bullet in this section. Every symbol used elsewhere in the blueprint must appear in `notation_dictionary` and in the `## Notation` section.

**Fail conditions:** missing `## Notation` section; symbol used in the proof but absent from the dictionary; entry in the dictionary that contradicts a symbol's usage in the proof.

### Check 2: Every claim carries a justification tag

Every displayed claim (statement-line ending in a period or equation) must end with exactly one bracketed tag from the taxonomy:

`[def: name]`, `[hyp]`, `[calc N]`, `[cite: paper_id, thm_id]`, `[from L.X]` / `[from L.X, Eq.Y]`, `[wlog: reason]`, `[ind: name]`, `[comp]`, `[functoriality]`, `[naturality]`.

**Fail conditions:** any displayed claim without a tag; any tag using a label not in the taxonomy; any tag whose reference does not resolve (e.g. `[from L.7]` when there is no Lemma 7).

### Check 3: Every numbered computation display has at least one referring `[calc N]`

If display `(N)` exists but no claim in the proof tags `[calc N]`, the display is orphaned — either delete it or use it.

### Check 4: Every cited external result has paper_id, thm_id, and arXiv id (when applicable)

For every `[cite: ...]` tag, the proof body must include nearby the complete cited statement, the `paper_id`, the `theorem_id`, and the arXiv id when applicable. Missing source identifiers fail this check.

### Check 5: Original problem statement reproduced verbatim

The final theorem section's `## statement` must contain the original problem statement from `data/{problem_id}.md` byte-for-byte. Paraphrases, shortened forms, or notational adjustments are failures (notational adjustments belong in `## Notation`, not in the statement).

### Check 6: Every hypothesis from the problem statement is either used or annotated

Read the problem statement's hypotheses. For each hypothesis, either some claim in the proof must carry `[hyp]` referencing it, or `notation_dictionary` must record it with `usage: "unused-by-design"` and a one-sentence reason. Silently unused hypotheses fail.

### Check 7: No banned phrases

Search the blueprint for: "clearly", "obviously", "trivially", "it is easy to see", "it follows that" (without a `[from ...]` tag immediately after), "by symmetry" (without a `[from ...]` tag), "by a standard argument", "as usual", "we omit the details". Any match is a fail; rewrite using `$enforce-step-granularity`.

### Check 8: Numbered objects appear before being cited

A `[from L.3]` tag must follow Lemma 3, not precede it. Likewise for `[calc N]`, `[def: name]`, and `[ind: name]`. Forward references are a fail.

### Check 9: Supporting lemmas precede the main theorem

The main theorem section must be the last `# theorem` heading in the blueprint, and every `[cite]` / `[from L.X]` tag in its proof must point either backward in the blueprint or to an external result with full identifiers.

## Procedure

1. Read the blueprint and the original problem markdown.
2. Run Check 1 through Check 9 in order. For each check, list every line in the blueprint that fails.
3. If **any** check fails, the audit fails. Do not call `$verify-proof`. Instead, append an audit report:

```json
{
  "audit_pass": false,
  "checks_failed": ["check_2", "check_7"],
  "findings": [
    {"check": "check_2", "location": "Lemma 4 proof, line ending '\\therefore \\phi is injective'", "issue": "missing justification tag"},
    {"check": "check_7", "location": "Lemma 2 proof, paragraph 1", "issue": "banned phrase 'clearly'"}
  ]
}
```

to `verification_reports` with `record_type="self_audit"`, then revise the blueprint to address every finding using the relevant generation skills (`enforce-step-granularity`, `align-with-source-notation`, `direct-proving`, etc.), and re-run `self-audit`.

4. If **all** checks pass, append:

```json
{"audit_pass": true, "checks_passed": ["check_1","check_2",...,"check_9"]}
```

to `verification_reports` with `record_type="self_audit"`, then proceed to `$verify-proof`.

## Hard-Fail Invariant

`$verify-proof` must refuse to invoke `verify_proof_service` unless the most recent `self_audit` record for this blueprint has `audit_pass=true` and references the current blueprint state. If you make any change to `blueprint.md` after a passing self-audit, the audit is invalidated and must be re-run before verification.

## Output Contract

One JSON record per self-audit run in `verification_reports` (channel) tagged `record_type="self_audit"`, as shown above.

## MCP Tools

- `memory_append` (channel: `verification_reports`, `events`)
- `memory_search` (to consult prior self-audit findings and the notation dictionary)

## Failure Logging

If the same check fails repeatedly across multiple audit rounds (e.g. step granularity cannot be achieved without a missing lemma), append to `failed_paths` and route the work to `$identify-key-failures`.
