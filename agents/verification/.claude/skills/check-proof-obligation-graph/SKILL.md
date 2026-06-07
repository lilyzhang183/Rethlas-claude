---
name: check-proof-obligation-graph
description: Parse the proof_obligations.json artifact and validate it as a directed acyclic graph (DAG). Flag cycles, forward references, missing nodes, self-dependence, hidden dependencies, and any obligation needed by the main theorem that is not proved or externally cited. Mandatory pass 1.5 inserted between $verify-sequential-statements and $check-notation-consistency.
---

# Check Proof-Obligation Graph

The proof-obligation graph is the structural backbone of rigor: every nontrivial assertion in the blueprint has a node, every dependency is explicit, and the graph must be acyclic with the main theorem as the unique sink. This pass turns rigor into a data invariant — circular reasoning cannot hide in prose because the graph would no longer be a DAG.

## Input Contract

Read:

- the proof markdown
- `proof_obligations.json` content (passed alongside `proof` in the verification request payload as untrusted data — read from `results/{run_id}/request.json`)
- the proof's `## Notation`, `## Definitions`, and `## Assumptions` blocks (already parsed by `$verify-sequential-statements`)
- the proof's local `## Context` blocks per lemma

## Node shape

Each node in `proof_obligations.json` has the following keys:

```json
{
  "node_id": "L3.claim2",
  "type": "lemma|proposition|theorem|claim|equation|computation|definition",
  "statement": "For every x in U, ...",
  "context": ["H1", "H2", "D4", "N7"],
  "depends_on": ["L1", "L2.eq3", "Source.CS2013.Thm1"],
  "proof_location": "blueprint.md#lemma-L3-proof",
  "status": "proved_in_blueprint|axiom|external_citation|stub|blocked",
  "verification_status": "unchecked|verified|failed",
  "blueprint_sha256": "..."
}
```

Conventions:

- `node_id` is a stable identifier. Lemmas use `L<n>`. Definitions use `D<n>`. Hypotheses use `H<n>`. Notation entries use `N<n>`. Numbered equations use `<parent>.eq<n>` (e.g. `L3.eq2`). Computations use `E<n>`. The main theorem uses `MainThm`.
- `context` lists the active assumptions, definitions, and notation entries required at the node site.
- `depends_on` lists the node_ids of earlier obligations the node uses. External citations use the prefix `Source.` (e.g. `Source.CS2013.Thm1`).
- `proof_location` is a stable markdown anchor inside `blueprint.md`.
- `blueprint_sha256` is the hash of `blueprint.md` at the time the obligation was last updated.

## Procedure

### Step 1: Parse the graph

Load `proof_obligations.json` from the request payload. Build a directed graph with edges from each node to every node listed in its `depends_on`. External-citation dependencies (prefix `Source.`) are sinks and require a corresponding theorem-application table in the markdown (`$check-terminology-consistency` and `$check-referenced-statements` validate those).

If `proof_obligations.json` is missing or unparseable, record a `critical_error` at location `proof_obligations` with issue `"proof obligation graph missing or unparseable; rigor mode requires the graph to be present"` and stop the pass.

### Step 2: Acyclicity

Run a topological sort. If a cycle is detected, record a `critical_error` at each node in the cycle with issue `"node participates in a dependency cycle; proof obligation graph must be acyclic: <cycle node_ids>"`. Cycles are the central failure mode this pass catches; they indicate circular proof structure that the markdown surface would hide.

### Step 3: Self-dependence

For each node `n`, check that `n` does not appear (directly or transitively) in its own `depends_on`. Direct self-dependence is a `critical_error` with issue `"node depends on itself directly"`. Transitive self-dependence is caught by the acyclicity check.

### Step 4: Forward reference

For each `(node, dep)` pair where `dep` is not an external citation: confirm that `dep`'s `proof_location` appears *before* `node`'s `proof_location` in textual order through the blueprint markdown. Forward references (`node` cites `dep`, but `dep` appears later in the markdown) are `critical_error`s with issue `"node references <dep> which appears later in the blueprint"`.

### Step 5: Missing dependency nodes

For each `dep` referenced from any `depends_on` list, confirm a node with that id exists in the graph (or is an external citation). Missing `dep` → `critical_error` at the citing node with issue `"depends_on references missing node <dep>"`.

### Step 6: Main-theorem reachability and self-isolation

Confirm that:

1. There is a node with `node_id = "MainThm"` and `type = "theorem"`.
2. Every obligation needed to prove the main theorem (the set of nodes reachable from `MainThm` through reverse-`depends_on`) has `status` in `{proved_in_blueprint, external_citation}`. Any reachable node with `status` in `{stub, blocked, axiom}` is a `critical_error` (an `axiom` outside an explicitly declared `## Axioms` block is unacceptable in rigor mode).
3. `MainThm` does not appear in the dependency chain of any lemma used to prove it. This is the strongest form of "no circular proof": even transitively, no lemma may rely on the theorem it is helping to prove. → `critical_error` if violated.

### Step 7: Hidden dependencies

For every node, cross-check the `depends_on` list against the blueprint markdown content at `proof_location`. Identify the inline justification tags (`[def: D<i>]`, `[from: L4.eq1]`, `[hyp: H<i>]`, `[cite: paper_id, thm_id]`, `[calc: E<n>]`, `[ind: ...]`) and confirm each referenced node_id appears in `depends_on`. Tags that point to node_ids not declared in `depends_on` are **hidden dependencies** → `critical_error` with issue `"node uses <tag_target> at <proof_location> but does not declare it in depends_on; hidden dependency"`.

Symmetrically, declared `depends_on` entries that are never actually used at the node's `proof_location` are **orphan declarations** → `warning` with issue `"depends_on declares <dep> but no inline tag at proof_location references it"`.

### Step 8: Context coverage

For every node, confirm that:

- every node_id in `context` matches a Hypothesis/Definition/Notation entry that is in scope at the `proof_location` (per the lemma's `## Context` block); and
- every symbol used in `statement` is declared (via Tier-1 `## Notation`, Tier-2 local declaration in the parent lemma's `## Context`, or Tier-3 standard-constants whitelist).

Symbols used in a node's statement but absent from both the notation dictionary and the parent lemma's context → `critical_error`.

### Step 9: Persist

Append one record per audited node to `statement_checks` (sub-shape `record_subtype="proof_obligation_node"`) plus a single summary record:

```json
{
  "record_subtype": "proof_obligation_graph_summary",
  "node_count": 47,
  "edges": 112,
  "max_depth": 9,
  "acyclic": true,
  "main_theorem_reachable_count": 23,
  "external_citations": 8,
  "stub_or_blocked_in_main_chain": 0,
  "critical_errors": [...],
  "gaps": [],
  "warnings": [...]
}
```

Append an `events` record `event_type="proof_obligation_graph_audit_complete"`.

## Hard Invariants

1. The graph must be present, parseable, and acyclic. None of the three is optional in rigor mode.
2. The main theorem may not appear in any of its own dependencies' dependency chains.
3. Every inline justification tag in the blueprint must correspond to a `depends_on` entry on the appropriate node.
4. Every node reachable from the main theorem (via reverse-`depends_on`) must be proved or externally cited; `stub` or `blocked` status in that subgraph is a hard fail.

## Output Contract

Per-node records appended to `statement_checks` with `record_subtype="proof_obligation_node"`. One summary record. One `events` record. `$synthesize-verification-report` aggregates the findings into the final verdict at the standard severities (`critical_error`, `gap`, `warning`).

## Tools

- `memory_append`
- `memory_query`
- `search_theorem_index` (when resolving `Source.*` external citations)
- Claude Code's built-in `WebSearch` tool
