---
name: check-terminology-consistency
description: Audit every key mathematical term used in the proof against its source definition. Notation handles symbols; this handles WORDS and CONCEPTS — "proper at x", "leaf closure", "Morita equivalence", "regular vs singular", "linearized vs saturated linearization". Catches the failure mode where the proof says the right word but means a stronger or weaker thing than the source. Mandatory pass inserted between $check-notation-consistency and $check-computational-replay.
---

# Check Terminology Consistency

In research-level mathematics — especially differential geometry, NCG, Poisson and foliation theory — many proof errors are not symbol-level (notation) but word-level (terminology). The proof says "proper" where the source says "s-proper"; calls something "the leaf" when the source means "the leaf closure"; treats "Morita equivalent" as "literally isomorphic"; uses "linearization" in the local sense while applying a result that needs the saturated sense. These are the failures the symbol-level notation audit cannot catch.

## Input Contract

Read:

- the full proof markdown, with particular attention to:
  - `## Notation` (definitions of terms whose meaning is source-locked)
  - `## Definitions` (locally-numbered definitions)
  - the theorem-application tables associated with each `[cite: ...]` tag
- cited source papers (via `search_theorem_index` and `WebSearch`)

## Procedure

### Step 1: Extract key terms

Walk the proof and identify every **key term**: a noun or noun phrase used in a statement or proof step whose meaning is not literally fixed by symbol substitution. Examples:

- adjectives applied to maps and morphisms (`proper`, `s-proper`, `étale`, `submersive`, `regular`)
- relations between spaces (`Morita equivalent`, `isomorphic`, `homotopy equivalent`)
- subsets of an ambient space (`leaf`, `leaf closure`, `orbit`, `orbit closure`)
- modifiers on linearization (`local`, `saturated`, `formal`, `analytic`)
- structural words (`smooth`, `analytic`, `algebraic`, `formal`)

Skip purely structural symbols handled by `$check-notation-consistency`.

### Step 2: Build the terminology table

For each key term, populate one record:

```json
{
  "term": "proper at x",
  "appearances": ["Lemma 2 statement", "Theorem proof line 4"],
  "source": "CS2013.Def1.1" | "local Definition D3" | "self, standard",
  "verbatim_source_definition": "...",
  "local_definition": "...",
  "compatible": true,
  "notes": "Source uses pointwise properness at the unit; this proof uses the same definition. Not the same as global properness or s-properness."
}
```

If a term appears with no traceable source — i.e. used as if standard but not in `## Notation`, `## Definitions`, or the Tier-3 whitelist of standard terms — record a `gap` at the first appearance.

### Step 3: Audit per key term

For each term, run these checks:

1. **Same term, two meanings.** The term is used in two parts of the proof with materially different meanings (e.g. "proper" in one lemma means "the underlying map of topological spaces is proper" and in another means "s-proper as a Lie groupoid"), without an explicit disambiguating phrase. → `critical_error` at the conflicting locations.
2. **Source-stronger.** The cited source defines the term to require strictly more than what the proof's context assumes (e.g. cited theorem requires "s-proper", proof's hypothesis is only "proper"). → `critical_error` with the precise mismatch.
3. **Source-weaker.** The cited source defines the term more weakly than the proof assumes (e.g. proof uses a property the source's "proper" does not guarantee). → `critical_error`.
4. **Silent terminology drift.** The proof uses a term that is named identically to a source term but means something different in the proof's local context, without a clarifying definition. → `critical_error`.
5. **Unexpanded application term.** A `[cite: paper_id, thm_id]` invokes an external theorem whose statement uses term `T`, but the proof's theorem-application table (per `$check-referenced-statements`) does not include `T` in its terminology rows. → `gap` at the citation.
6. **Domain-trap pairs (high-priority watch list).** The following pairs are flagged at first appearance unless explicitly disambiguated in `## Definitions`:
   - `proper` vs `s-proper`
   - `orbit` vs `leaf` vs `leaf closure`
   - `linearized foliation` vs `local linearization` vs `saturated linearization`
   - `regular` vs `singular` (with respect to which structure?)
   - `Morita equivalent` vs `isomorphic`
   - `Riemannian foliation` vs `transnormal system`
   - `smooth quotient` vs `set-theoretic quotient`
   - `formal` vs `analytic` vs `smooth`

   Any pair from the watch list appearing in the same proof without a disambiguation sentence is a `gap` (not yet a critical_error, because the proof may well be correct; but it must be explicit).

### Step 4: Persist

Append one record per audited term to `reference_checks` with sub-shape:

```json
{
  "record_subtype": "terminology_consistency",
  "term": "proper at x",
  "source": "CS2013.Def1.1",
  "verbatim_source_definition": "...",
  "local_definition": "...",
  "compatible": true,
  "appearances": ["Lemma 2", "Theorem proof line 4"],
  "checks": {
    "two_meanings": false,
    "source_stronger": false,
    "source_weaker": false,
    "silent_drift": false,
    "unexpanded_application": false,
    "domain_trap_disambiguated": true
  },
  "critical_errors": [],
  "gaps": [],
  "warnings": []
}
```

Append an `events` record `event_type="terminology_consistency_audit_complete"`.

## Hard Invariants

1. Every key term must trace to a source (external citation, local definition, or standard usage).
2. Domain-trap pairs require an explicit disambiguation sentence in `## Definitions` or in the term's first introduction.
3. Source-stronger / source-weaker mismatches are `critical_error`, never `warning`.

## Output Contract

Per-term audit records appended to `reference_checks` with `record_subtype="terminology_consistency"`. Summary `events` record. `$synthesize-verification-report` aggregates at the standard severities.

## Tools

- `search_theorem_index`
- Claude Code's built-in `WebSearch` tool
- `memory_append`
- `memory_query`
