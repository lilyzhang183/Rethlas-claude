---
name: check-notation-consistency
description: Read the proof's `## Notation` section, build a per-symbol usage map across the entire proof, and flag undefined symbols, silently-renamed borrowings, symbols used with two different meanings, and notation drift from cited papers. Mandatory step inserted after $verify-sequential-statements and before $check-referenced-statements.
---

# Check Notation Consistency

Notation drift is one of the most common ways a proof becomes wrong or unreadable. This skill audits every symbol used in the proof against the proof's declared notation dictionary (the `## Notation` section at the top of the markdown) and against the cited sources.

## Input Contract

Read:

- the full proof markdown
- specifically, the `## Notation` section near the top of the document — this is the proof's declared notation dictionary, flushed from the generation agent's `notation_dictionary` memory channel
- the cited source papers referenced in the proof (via `search_arxiv_theorems` or the proof's reference list)

## Procedure

### Step 1: Read the declared notation

Locate the `## Notation` section. If it is missing, record a critical error at location `Notation` with issue `"declared notation section absent; cannot audit notation consistency"` and proceed with whatever symbols are implicitly defined inline.

Parse each bullet into `{symbol, meaning, source}`. The `source` field is one of:

- `glossary` — the symbol was loaded from a per-problem glossary file; treat as authoritative.
- `paper_id (...), §/Def/Eq <ref>` — borrowed from an external source.
- `self, Definition X` / `self, Equation N` — defined locally in the proof.
- `self-renaming from paper_id, §/Eq <ref>` — locally renamed from a source.

### Step 2: Build the usage map

For each symbol in the declared notation, scan the entire proof and collect every occurrence. For each occurrence, record the location and the meaning the proof seems to assign to it at that point (by reading the surrounding sentence).

Also collect every symbol that *appears* in the proof but is *not* in the declared notation. These are undefined symbols and must be flagged.

### Step 3: Audit per symbol

For each symbol, run the following checks:

1. **Undefined.** Symbol appears in the proof but not in `## Notation`. → critical error at the first location of use.
2. **Multiple meanings.** The same symbol appears with two or more distinct meanings in different parts of the proof, and the proof did not introduce a disambiguating subscript or scope. → critical error at the first conflicting location.
3. **Silent renaming.** Symbol's declared source is an external paper, but the symbol used in the proof differs from the symbol the paper actually uses, and no `self-renaming` declaration was made. → critical error at the citation location.
4. **Drift from source.** Symbol's declared source is an external paper, but the meaning attached to the symbol in the proof differs from the paper's definition (after expanding the paper's local context). → critical error.
5. **Orphan entry.** Symbol is declared in `## Notation` but never used in the proof. → gap (not a critical error, but recorded so the proof can be cleaned up).
6. **Source resolution.** For every entry whose source is a paper, query `search_arxiv_theorems` (and `WebSearch` as fallback) and confirm the source exists and contains the claimed definition. → critical error if the source does not exist or does not contain the definition.

### Step 4: Persist

Append one record per audited symbol to `reference_checks` with a sub-shape:

```json
{
  "record_subtype": "notation_consistency",
  "symbol": "...",
  "declared_meaning": "...",
  "declared_source": "...",
  "usage_locations": ["Lemma 2 statement", "Lemma 2 proof line 3", "Theorem proof line 7"],
  "checks": {
    "undefined": false,
    "multiple_meanings": false,
    "silent_renaming": false,
    "drift_from_source": false,
    "orphan": false,
    "source_resolves": true
  },
  "critical_errors": [
    {"location": "Lemma 2 proof line 3", "issue": "..."}
  ],
  "gaps": [
    {"location": "Notation entry for $\\omega$", "issue": "declared but never used"}
  ]
}
```

Append a summary `events` record with `event_type="notation_consistency_audit_complete"` listing the symbols checked and the count of issues found.

## Hard Invariants

1. Every symbol appearing in the proof must appear in the declared `## Notation` section. No exceptions for "standard" symbols — even $\mathbb{Z}$, $\mathbb{R}$, or category-theory shorthand must be declared if used.
2. Every external-source entry must resolve via `search_arxiv_theorems` or `WebSearch`.
3. Silent renamings are critical errors, not gaps.

## Output Contract

Persist every per-symbol audit record to `reference_checks` with `record_subtype="notation_consistency"`. Persist a summary `events` record. `$synthesize-verification-report` aggregates these into the final verdict.

## Tools

- `search_arxiv_theorems`
- Claude Code's built-in `WebSearch` tool
- `memory_append`
- `memory_query`
