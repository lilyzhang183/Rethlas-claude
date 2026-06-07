---
name: check-referenced-statements
description: Validate externally referenced theorems by querying arXiv theorem search first and Claude Code's built-in WebSearch second. Use when a markdown proof cites statements from external papers.
---

# Check Referenced Statements

Validate every external-paper reference used in the proof.

## Input Contract

For each cited external theorem/lemma/definition:

- location where it is used,
- the full referenced statement text.

## Procedure

1. Query `search_theorem_index` using the full referenced statement as `query`.
2. Inspect returned results and compare theorem text directly to the referenced statement in reasoning.
3. **Require a theorem-application table beside every `[cite: ...]` in the proof markdown.** The table must include three subsections — verbatim source statement, source terminology, and an application-map + hypotheses-checklist. Schema:

   ```markdown
   ### Source theorem used: <paper_id>, <Thm>

   **Verbatim source statement.** "<copy from source>"

   **Source terminology.**
   - "<source term>" means <expanded definition in source's context>

   **Application map.**
   | Source symbol | Meaning in source | Local symbol | Local meaning | Verified match |
   |---|---|---|---|---|
   | ... | ... | ... | ... | yes |

   **Hypotheses checklist.**
   | Source hypothesis | Where proved/assumed locally |
   |---|---|
   | ... | H<i> / Lemma L<j> / Definition D<k> |
   ```

   A `[cite: ...]` tag is **invalid** unless a complete theorem-application table appears nearby (in the same lemma/proof body). Missing or incomplete table → `critical_error` with issue `"citation lacks theorem-application table; cannot verify applicability"`. The verifier never accepts a citation on "vibe" — every row of every table must be either explicitly checked or flagged.

4. Expand the definitions and terminology appearing in the cited statement using the cited paper's context before deciding whether the theorem applies. The application-map rows are where this expansion lives in the markdown.
5. Check whether the same words in the current proof mean the same thing as they do in the cited paper. In mathematics, identical words can carry different definitions in different contexts. `$check-terminology-consistency` runs this audit at the word level; `$check-referenced-statements` checks that the application table claims terms match, and that those claims are sound.
6. Accept as matched and applicable only when all three are true:
   - the source statement matches the cited statement in the table;
   - every application-map row's "Verified match" is `yes`;
   - every hypothesis-checklist row points to a real local hypothesis, lemma, or definition.
7. If the theorem exists but the current proof uses different definitions, hypotheses, or ambient objects (any "no" in the application map), record a `critical_error` for incorrect application with the specific row.
8. If no source match is found, use Claude Code's built-in `WebSearch` tool with the same statement text.
9. If still not found, emit a `critical_error`:
   - location: where the citation is used,
   - issue: referenced theorem appears non-existent or incorrectly cited.
10. Persist each reference check in `reference_checks`.

Do not rely on dedicated comparison utility code; perform comparison through careful reasoning.

## Output Contract

Append records to `reference_checks` like:

```json
{
  "location": "Lemma 2",
  "referenced_statement": "Exact statement text",
  "context_expansion": "In the cited paper, 'regular' means regular with respect to the valuation topology.",
  "arxiv_match_found": false,
  "web_match_found": false,
  "critical_error": {
    "location": "Lemma 2",
    "issue": "Referenced external theorem was not found in arXiv search or Claude Code built-in WebSearch."
  }
}
```

## Tools

- `search_theorem_index`
- `memory_append`
- Claude Code's built-in `WebSearch` tool
