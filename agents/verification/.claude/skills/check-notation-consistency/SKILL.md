---
name: check-notation-consistency
description: Read the proof's `## Notation` section, parse local variable declarations inside each lemma, and audit every symbol used across the proof at the appropriate strictness tier (global, local, standard). Flag undefined symbols, silently-renamed borrowings, symbols used with two meanings, and notation drift from cited papers. Mandatory step inserted after $verify-sequential-statements and before $check-referenced-statements.
---

# Check Notation Consistency

Notation drift is one of the most common ways a proof becomes wrong or unreadable. This skill audits every symbol used in the proof against the proof's declared notation dictionary (the `## Notation` section at the top of the markdown) and against the cited sources, applying a three-tier strictness model so that pragmatic local notation does not produce false-positive pressure.

## Three-tier audit model

Symbols are audited under one of three tiers; strictness differs by tier.

### Tier 1: Global Notation (strict)

Symbols used across multiple lemmas, imported from external sources, or persistent through the proof. Every Tier-1 symbol must appear in the proof's `## Notation` section with a recorded `source`. Borrowed notation must be verbatim with respect to its source, or accompanied by an explicit renaming declaration.

### Tier 2: Local Variables (medium)

Bound variables introduced inside a single lemma/proposition/theorem proof block (e.g. "let $x \in M$", "fix $\eta \in \Omega^1(M)$", "take $\epsilon > 0$"). These must be declared at the introduction site inside the lemma, but they do not need entries in the global `## Notation` section. They are scoped to their lemma and must not be reused with a different meaning later.

### Tier 3: Standard Constants (relaxed whitelist)

A small fixed whitelist of symbols whose meaning is universal in modern mathematical practice and need not be declared either globally or locally:

`\mathbb{N}, \mathbb{Z}, \mathbb{Q}, \mathbb{R}, \mathbb{C}, \emptyset, id, \in, \notin, \subset, \subseteq, \supset, \supseteq, \cup, \cap, \to, \mapsto, \forall, \exists, =, \neq, +, -, \cdot, \times, \le, \ge, <, >, |, \,`

Plus any symbols listed under a `# Standard Constants` heading in `data/{problem_id}.glossary.md`, which the problem author can use to extend the whitelist (e.g. for differential-geometry conventions like `d, \partial, \nabla, \Omega^k, T M, T^*M`).

If the problem uses any whitelisted symbol with a non-standard meaning, that symbol must be moved to Tier 1 with an explicit `## Notation` entry overriding the default.

## Input Contract

Read:

- the full proof markdown
- the `## Notation` section (Tier-1 declarations)
- local variable declarations inside each lemma/proposition/theorem (Tier 2)
- the standard-constants whitelist (Tier 3)
- cited source papers referenced by Tier-1 entries

## Procedure

### Step 1: Read the Tier-1 declarations

Locate the `## Notation` section. If it is missing, record a `critical_error` at location `Notation` with issue `"global Notation section absent; cannot audit notation consistency"`. Parse each bullet into `{symbol, meaning, source, scope: global}`. Acceptable `source` values:

- `glossary` — loaded from the per-problem glossary; authoritative.
- `paper_id (...), §/Def/Eq <ref>` — borrowed from an external source.
- `self, Definition X` / `self, Equation N` — defined locally in the proof but used across multiple lemmas.
- `self-renaming from paper_id, §/Eq <ref>` — locally renamed from a source.

### Step 2: Collect Tier-2 declarations

Walk each lemma/proposition/theorem proof block. Within each block, identify local variable declarations by their introduction sentences ("let", "fix", "take", "consider", "define" + binder). Build a per-block local symbol table mapping symbol → meaning → introduction location. Scope ends at the next major lemma/proposition/theorem heading.

### Step 3: Build the usage map

For each occurrence of a symbol in the proof, classify by lookup order:

1. Is the symbol declared in the current Tier-2 local table? → Tier 2 hit, record.
2. Is the symbol in Tier-1 `## Notation`? → Tier 1 hit, record.
3. Is the symbol in the Tier-3 standard whitelist (including glossary `# Standard Constants` extensions)? → Tier 3 hit, record (no audit needed).
4. Otherwise → **undefined symbol → critical_error** at the first location of use.

### Step 4: Audit per Tier-1 symbol

For each Tier-1 symbol, apply these checks (Tier-2 and Tier-3 entries are not subject to most of these):

1. **Multiple meanings.** The symbol appears with two distinct meanings in different parts of the proof. → `critical_error`.
2. **Silent renaming.** Symbol's source is an external paper, but the symbol the paper uses differs and no `self-renaming` declaration was made. → `critical_error`.
3. **Drift from source.** The meaning assigned in the proof differs from the source's definition after expanding the source's local context. → `critical_error`.
4. **Orphan entry.** Tier-1 symbol declared but never used. → **`warning`** (down from `gap`). Records the cleanup opportunity without blocking correctness.
5. **Source resolution.** For every paper-sourced entry, query `search_theorem_index` (and `WebSearch` as fallback) to confirm the source exists and contains the claimed definition. → `critical_error` if unresolved.

### Step 5: Audit per Tier-2 symbol

For each Tier-2 (local) symbol:

1. **Re-used outside scope.** The same local symbol is used in a later lemma/theorem proof block where it was not redeclared. → `critical_error` (with issue `"local symbol leaked outside its lemma scope; redeclare or promote to global"`).
2. **Conflicting redeclaration.** Two different lemma blocks redeclare the same symbol with materially different meanings without flagging the local rebinding. This is acceptable as long as the local declarations are independent, but if a Tier-1 entry exists for the symbol, the local rebinding must be flagged in-text. → `warning` if not flagged.

### Step 6: Persist

Append one record per audited symbol to `reference_checks` with sub-shape:

```json
{
  "record_subtype": "notation_consistency",
  "symbol": "...",
  "tier": "global|local|standard",
  "declared_meaning": "...",
  "declared_source": "...",
  "usage_locations": ["Lemma 2 statement", "Lemma 2 proof line 3", "Theorem proof line 7"],
  "checks": {
    "undefined": false,
    "multiple_meanings": false,
    "silent_renaming": false,
    "drift_from_source": false,
    "orphan": false,
    "source_resolves": true,
    "leaked_outside_scope": false,
    "conflicting_redeclaration": false
  },
  "critical_errors": [
    {"location": "Lemma 2 proof line 3", "issue": "...", "severity": "critical_error"}
  ],
  "gaps": [],
  "warnings": [
    {"location": "Notation entry for $\\omega$", "issue": "declared but never used", "severity": "warning"}
  ]
}
```

Append a summary `events` record with `event_type="notation_consistency_audit_complete"` listing the per-tier counts of audited symbols and the count of issues at each severity.

## Hard Invariants

1. Every symbol appearing in the proof must be classifiable into Tier 1, Tier 2, or Tier 3. Symbols matching none → `critical_error`.
2. Every Tier-1 external-source entry must resolve via `search_theorem_index` or `WebSearch`.
3. Silent renamings are `critical_error`, not `gap` or `warning`.
4. Tier-1 orphan entries are `warning` only — never block `verdict=correct`.
5. Local symbols leaking outside their lemma scope are `critical_error`.

## Output Contract

Persist every per-symbol audit record to `reference_checks` with `record_subtype="notation_consistency"`. Persist a summary `events` record. `$synthesize-verification-report` partitions findings by severity (`critical_error`, `gap`, `warning`) and applies the strict verdict rule (warnings do not block `correct`).

## Tools

- `search_theorem_index`
- Claude Code's built-in `WebSearch` tool
- `memory_append`
- `memory_query`
