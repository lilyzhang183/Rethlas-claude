---
name: align-with-source-notation
description: Maintain verbatim notation alignment with cited sources by recording every borrowed symbol in the notation_dictionary and requiring an explicit renaming declaration whenever a local symbol differs from its source. Use whenever an external result is borrowed, a glossary is loaded, or a new symbol is introduced.
---

# Align with Source Notation

Notation drift is a leading cause of mistaken citations and unreadable proofs. This skill enforces the rule: **verbatim if borrowed**. Every borrowed symbol must be copied from its source verbatim and recorded in `notation_dictionary`. Every locally introduced symbol that is used across more than one lemma must also be recorded. Bound variables introduced inside a single lemma proof are *not* recorded globally — they live in the lemma scope.

## Three notation tiers

Each `notation_dictionary` entry carries a `scope` field with one of three values; the tier governs both how the entry is recorded and how the verifier audits it:

- **Tier 1 — `scope: "global"`.** Symbols used across multiple lemmas, imported from external sources, or carried throughout the proof. Flushed into the blueprint's `## Notation` section. Audited strictly by `$check-notation-consistency`.
- **Tier 2 — `scope: "local"`.** Bound variables introduced inside one lemma/proposition/theorem proof (e.g. "let $x \in M$", "fix $\eta \in \Omega^1(M)$"). Declared at the introduction site inside the lemma but **not** flushed to `## Notation`. Use the dictionary to record them for the parent agent's bookkeeping, especially when sub-agents are working in parallel; verification only checks that they are declared locally and do not leak outside their scope.
- **Tier 3 — `scope: "standard"`.** Universal mathematical constants and operators (`\mathbb{N}`, `\mathbb{Z}`, `\mathbb{Q}`, `\mathbb{R}`, `\mathbb{C}`, `\emptyset`, `id`, `\in`, `\subset`, etc.) plus any symbols declared under a `# Standard Constants` heading in `data/{problem_id}.glossary.md`. These need no `notation_dictionary` entry at all; the verifier resolves them from the whitelist. If a problem uses a whitelisted symbol with a non-standard meaning, promote it to Tier 1 with an explicit `## Notation` entry overriding the default.

## Input Contract

Read:

- the current target statement, subgoal, or proof step
- the cited paper or source (when borrowing a result)
- any `data/{problem_id}.glossary.md` file when starting a new problem
- the current contents of the `notation_dictionary` memory channel

## Procedure

### 1. Glossary seeding (run once at problem start)

If `data/{problem_id}.glossary.md` exists, read each heading and body. Glossary entries under regular headings are Tier-1; entries under a `# Standard Constants` heading are Tier-3 whitelist extensions and do not get appended (record them once in `events` for traceability). For each Tier-1 glossary entry, append one record to `notation_dictionary`:

```json
{
  "symbol": "the symbol or term as written in the glossary heading",
  "meaning": "the body of the glossary entry",
  "source": "glossary",
  "scope": "global",
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
  "scope": "global",
  "first_used_at": "blueprint location where first introduced"
}
```

3. If a local symbol collision is unavoidable (e.g. the source's $\omega$ collides with a $\omega$ already in use for a different object), write a one-sentence renaming declaration in the proof, and append a renaming entry:

```json
{
  "symbol": "local symbol used in the proof",
  "meaning": "same as <source symbol>",
  "source": "self-renaming from paper_id, §/Eq reference",
  "scope": "global",
  "renamed_from": "the source's original symbol",
  "first_used_at": "blueprint location of the renaming declaration"
}
```

The renaming declaration in the proof must read like: "We write $X$ for what [Author, Year] calls $Y$, throughout this section."

### 3. Introducing a new local symbol

When the proof introduces a symbol of its own (not borrowed), classify by intended use first:

- Will it be used across multiple lemmas, or carry through the proof? → Tier 1 (`scope: "global"`). Append to `notation_dictionary` and include in `## Notation`.
- Is it a bound variable scoped to one lemma proof (e.g. "let $\epsilon > 0$ in the proof of Lemma 4")? → Tier 2 (`scope: "local"`). Declare it inline at the introduction site, and append to `notation_dictionary` with the parent lemma's id under `scope_block` (do not flush to `## Notation`).
- Is it a Tier-3 standard constant being used with its standard meaning? → no append needed.

For Tier 1:

```json
{
  "symbol": "the global symbol",
  "meaning": "the local definition",
  "source": "self, Definition X.Y",
  "scope": "global",
  "first_used_at": "blueprint location"
}
```

For Tier 2:

```json
{
  "symbol": "the bound variable",
  "meaning": "what it ranges over, e.g. 'a smooth positive real'",
  "source": "self, Lemma 4 proof",
  "scope": "local",
  "scope_block": "lem:foo",
  "first_used_at": "Lemma 4 proof, line where 'let' appears"
}
```

### 4. Reusing an existing symbol

Before reusing any symbol elsewhere in the proof, query `notation_dictionary` and confirm the intended meaning matches the recorded entry. If a new context requires a different meaning, append a new entry with a disambiguating subscript or a renaming declaration; never overload silently.

### 5. Flushing the dictionary into the blueprint

When `blueprint.md` is being assembled or revised, render every Tier-1 (`scope: "global"`) entry from `notation_dictionary` as a bullet in a `## Notation` section at the very top of the document, after the title but before the lemmas. Tier-2 (`scope: "local"`) entries do not get flushed — their declarations remain inline inside the lemma where they were introduced. Tier-3 standard constants are not flushed either.

The same blueprint must also contain a `## Assumptions` block (alongside `## Notation`) listing every hypothesis from the problem statement with an explicit identifier (`H1`, `H2`, ...). Justification tags use `[hyp: H<i>]` referencing these identifiers; the bare `[hyp]` form is rejected. Example:

```markdown
## Assumptions

- H1: $M$ is a smooth manifold.
- H2: $\mathcal{F}$ is a singular foliation on $M$.
- H3: $p$ is a fixed point of every leaf-preserving symmetry.
```

Each Tier-1 `notation_dictionary` entry becomes one bullet in `## Notation`:

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
- `search_theorem_index` when the source is an arXiv paper and the symbol's meaning needs context expansion
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
