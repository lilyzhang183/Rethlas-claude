---
name: align-with-source-notation
description: Maintain verbatim notation alignment with cited sources by recording every borrowed symbol in the notation_dictionary and requiring an explicit renaming declaration whenever a local symbol differs from its source. Use whenever an external result is borrowed, a glossary is loaded, or a new symbol is introduced.
---

# Align with Source Notation

Notation drift is a leading cause of mistaken citations and unreadable proofs. This skill enforces the rule: **verbatim if borrowed**. When a result is taken from an external paper, the proof must use that paper's exact symbols and names, and every symbol used anywhere in the proof must be traceable to a definition or a citation.

## Input Contract

Read:

- the current target statement, subgoal, or proof step
- the cited paper or source (when borrowing a result)
- any `data/{problem_id}.glossary.md` file when starting a new problem
- the current contents of the `notation_dictionary` memory channel

## Procedure

### 1. Glossary seeding (run once at problem start)

If `data/{problem_id}.glossary.md` exists, read each heading and body and append one entry per term to `notation_dictionary` with:

```json
{
  "symbol": "the symbol or term as written in the glossary heading",
  "meaning": "the body of the glossary entry",
  "source": "glossary",
  "first_used_at": "init"
}
```

Treat glossary entries as authoritative throughout the proof. Do not silently override them.

### 2. Borrowing a result from a paper

When citing a theorem, lemma, or definition from a source paper:

1. Copy the source's notation verbatim into the proof — exact symbols, exact subscripts, exact names.
2. For every symbol appearing in the borrowed statement that was not already in `notation_dictionary`, append:

```json
{
  "symbol": "as written in the source",
  "meaning": "what it denotes, expanded using the source's context",
  "source": "paper_id (and arXiv id), §/Def/Eq reference",
  "first_used_at": "blueprint location where first introduced"
}
```

3. If a local symbol collision is unavoidable (e.g. the source's $\omega$ collides with a $\omega$ already in use for a different object), write a one-sentence renaming declaration in the proof, and append a renaming entry:

```json
{
  "symbol": "local symbol used in the proof",
  "meaning": "same as <source symbol>",
  "source": "self-renaming from paper_id, §/Eq reference",
  "renamed_from": "the source's original symbol",
  "first_used_at": "blueprint location of the renaming declaration"
}
```

The renaming declaration in the proof must read like: "We write $X$ for what [Author, Year] calls $Y$, throughout this section."

### 3. Introducing a new local symbol

When the proof introduces a symbol of its own (not borrowed), append:

```json
{
  "symbol": "the local symbol",
  "meaning": "the local definition",
  "source": "self, Definition X.Y" | "self, Equation N",
  "first_used_at": "blueprint location"
}
```

### 4. Reusing an existing symbol

Before reusing any symbol elsewhere in the proof, query `notation_dictionary` and confirm the intended meaning matches the recorded entry. If a new context requires a different meaning, append a new entry with a disambiguating subscript or a renaming declaration; never overload silently.

### 5. Flushing the dictionary into the blueprint

When `blueprint.md` is being assembled or revised, render the contents of `notation_dictionary` as a `## Notation` section at the very top of the document, after the title but before the lemmas. Each entry becomes one bullet:

```markdown
## Notation

- $X$ — meaning, source: paper_id (arXiv:2401.xxxxx), Def 2.1.
- $\omega$ — symplectic form, source: glossary.
- $\tilde\omega$ — same as the $\omega$ of [Author, 2024], source: self-renaming from arXiv:1234.5678, §3.
```

The verifier reads this section to perform `check-notation-consistency`. The section must be present in the blueprint *before* `verify-proof` is invoked.

## Output Contract

Each `notation_dictionary` append is a single JSON record as shown above. The flushed `## Notation` section in `blueprint.md` must list every symbol used elsewhere in the proof; the `self-audit` skill enforces this.

## MCP Tools

- `memory_append` (channel: `notation_dictionary`)
- `memory_search` (channel: `notation_dictionary`)
- `search_arxiv_theorems` when the source is an arXiv paper and the symbol's meaning needs context expansion
- Claude Code's built-in `WebSearch` tool when the source is not on arXiv

## Failure Logging

If a borrowed symbol cannot be traced to a definition in the source paper (e.g. the symbol is used without being defined), append to `failed_paths`:

```json
{
  "record_type": "untraceable_borrowed_symbol",
  "symbol": "...",
  "source_attempted": "...",
  "implications": "borrowed result cannot be safely applied; reconsider citation or expand definitions"
}
```

and append an `events` record `event_type="notation_alignment_blocked"` so `$identify-key-failures` can act on it.
