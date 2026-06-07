# Math Reasoning Agent

This agent solves research-level math problems by following a mathematician-style iterative process. The primary control logic lives in this file and in the skill `SKILL.md` files under `.claude/skills/`.

## Objective

Given the markdown filepath of a math problem, read that file and produce a verified markdown proof blueprint at:

- working draft: `results/{problem_id}/blueprint.md`
- verified proof: `results/{problem_id}/blueprint_verified.md`

Here `problem_id` is the markdown filepath relative to `data/`, without the trailing `.md`. It preserves any category directories. For example:

- `data/example.md` has `problem_id=example`
- `data/algebra/modrep.md` has `problem_id=algebra/modrep`

## Workspace Boundary

Do not read anything outside this working directory.

This is a hard constraint. Only inspect files, directories, inputs, logs, memory, results, skills, and scripts that are inside the current working directory. Do not read from parent directories, home-directory config, global skill directories, or any other external path.

## Input

The input is provided directly in the prompt and will include:

- the markdown filepath of the math problem
- the reference directory associated with the problem

Before any reasoning:

1. Resolve the provided filepath to a markdown file inside this workspace.
2. Read that markdown file carefully.
3. Set `problem_id` to the provided explicit problem id if the prompt includes one; otherwise set it to the problem filepath relative to `data/`, without the trailing `.md`.
4. If the prompt provides `reference_dir` and that directory exists, read supported reference files inside it before external search.
5. Use the markdown file contents as the authoritative local problem statement/context.

Do not flatten category directories out of `problem_id`. A problem in `data/algebra/modrep.md` must use `algebra/modrep`, not `modrep`.

Reference directories are problem-specific. For `data/algebra/modrep.md`, the associated reference directory is `data/algebra/modrep.refs/`. Supported direct reference files include `.md`, `.tex`, and `.txt`. PDF references are pre-extracted by the runner into `.txt` files under `reference_dir/.extracted/`; read those extracted text files instead of trying to inspect PDF binaries. These files are user-provided context, not verified facts; cite them in memory records and proof steps when they influence the proof.

A per-problem **glossary file** may exist at `data/{problem_id}.glossary.md` (e.g. `data/algebra/modrep.glossary.md` for the `algebra/modrep` problem). If it exists, read every entry on init and seed the `notation_dictionary` memory channel from it using `$align-with-source-notation` — each glossary entry becomes one dictionary record with `source: "glossary"`. Glossary entries are authoritative; never silently override them.


## Required Memory Policy

All intermediate reasoning artifacts must be persisted in `memory/{problem_id}/` using MCP tools (`memory_init`, `memory_append`, `memory_query`, `memory_search`, `branch_update`).

Initialize memory before any reasoning:

- call `memory_init(problem_id=problem_id, meta=...)`

`memory_init` allocates the channel JSONL files, seeds (or merges) `meta.json`, and ensures a `budget` object is present in `meta.json`. The default budget is:

```json
{
  "max_wall_seconds": 28800,
  "max_recursive_rounds": 5,
  "max_verifier_calls": 8,
  "max_external_papers": 40,
  "on_budget_exhausted": "write_partial_progress_report"
}
```

Override any field by passing `meta={"budget": {"max_wall_seconds": ...}}` when initializing. When any budget dimension is exhausted, follow `on_budget_exhausted`: invoke the MCP tool `write_partial_progress_report(problem_id, summary_markdown, reason, next_recommendations)` with a structured summary of progress, failed paths, and the next branches you would try. Budget exhaustion is **not** the same as failure — partial progress reports record where you got and what to try next; never claim the proof failed simply because the budget ran out.

For MCP memory tools, use the same data-relative `problem_id`.

Use append-only channels (except `meta.json`):

- `immediate_conclusions`
- `toy_examples`
- `counterexamples`
- `big_decisions`
- `subgoals`
- `proof_steps`
- `failed_paths`
- `verification_reports`
- `branch_states`
- `notation_dictionary`
- `events`

## Adaptive Control Loop

The agent should repeatedly assess the current state and choose the most appropriate skill(s) for the situation.

### Step 1: Assess state (every iteration)

Think about the following questions:

- What is the current main problem to tackle?
- Have we already searched extensively, and if so, what can we now do by deep independent reasoning rather than further retrieval?
- Have we gathered enough information to propose multiple subgoal decomposition plans?
- What decomposition plans have already been tried, and what stuck points did they reveal?
- Do we have any fresh constructions / counterexamples?
- What common failure patterns have already been identified?
- What grounding references from arXiv might help next?



Prefer the skill `$search-math-results` as the default retrieval workflow when the agent needs external mathematical results or background.
Prefer the skill `$query-memory` when the needed information may already exist in local memory.
External search is a support tool, not a substitute for deep thinking. Besides searching extensively for relevant theorems and background, the agent should also reason deeply about the problem on its own. If extensive search does not produce useful information, the agent should stop leaning on `$search-math-results` and instead push the problem forward with the other available skills.

### Step 2: Choose the next skill(s)

You can choose to invoke any skill at any time based on the current state and needs.
Do not decide a fixed order of skill usage before tackling the problem. Choose skills adaptively in response to the current proof state, new evidence, verifier feedback, stuck points, and newly discovered opportunities.

- Use `$obtain-immediate-conclusions` when:
  - starting a new problem/branch/subgoal
  - you need cheap progress or a cleaner reformulation
- Use `$search-math-results` when:
  - you need relevant theorems, constructions, examples, counterexamples, or background
  - you are starting a new problem and need context
  - you are constructing examples/counterexamples or proving subgoals and need supporting references
- Use `$query-memory` when:
  - you want to check whether earlier conclusions, examples, counterexamples, failed paths, or brach states can bring insight to the current question, claim, subgoal, or branch decision
  - you want to test a claim against previously saved counterexamples.
- Use `$construct-toy-examples` when:
  - you are stuck in reasoning and need simpler examples to regain traction
  - you need simpler examples that satisfy both assumptions and conclusion
  - you want to see where the assumptions take effect and gain intuition
- Use `$construct-counterexamples` when:
  - you are stuck in reasoning and want to see where the assumptions take effect and gain intuition
  - a proposed conjecture/claim feels fragile or unproved
  - you want to test whether the assumptions can hold while the claimed conclusion fails
- Use `$propose-subgoal-decomposition-plans` when:
  - you have gathered enough information from examples, counterexamples, search results, and previous failures to propose multiple decomposition plans
  - you need several materially different ways to break the theorem into subgoals
- Use `$direct-proving` when:
  - one or more decomposition plans are created.
- Use `$enforce-step-granularity` when:
  - you are writing or revising any proof step that displays a claim
  - `$direct-proving` or `$recursive-proving` is about to commit a transition between displayed claims to `blueprint.md`
  - you are repairing a gap, banned-phrase warning, or untagged claim flagged by the verifier or by `$self-audit`
- Use `$align-with-source-notation` when:
  - a `data/{problem_id}.glossary.md` file exists and needs to be seeded into `notation_dictionary` on init
  - you are about to invoke an external result and need to copy its notation verbatim into the proof
  - you are introducing a new local symbol or making a local renaming declaration
  - `$check-notation-consistency` (verifier-side) flagged drift, undefined symbols, or silent renamings
- Use `$recursive-proving` when:
  - all current decomposition plans have been attempted with `$direct-proving`
  - none of them fully solved the problem
  - you have identified key stuck points for each plan and want one sub-agent to work on each plan in parallel
- Use `$identify-key-failures` when:
  - recursive attempts on the current decomposition plans all failed
- Use `$self-audit` when:
  - a full candidate proof of the entire problem has been assembled in `blueprint.md`
  - you are about to call `$verify-proof` (`$self-audit` must pass first; this is a hard gate)
  - you have edited `blueprint.md` since the last passing self-audit (the audit is invalidated and must be re-run)
- Use `$verify-proof` when:
  - `$self-audit` has returned `audit_pass=true` for the current `blueprint.md` state and you want the canonical verification service to check it



### Step 3: Act and persist

After invoking any skill:

1. Persist produced artifacts to the correct channel(s) with `memory_append` using `problem_id=problem_id`. **Always pass `agent_id` (your own identifier), `skill` (the name of the skill you are currently executing), and `branch_id` / `plan_id` / `attempt_id` whenever these are known.** When running as a sub-agent invoked via `$recursive-proving`, also pass `parent_agent_id`. These stamps are essential for reconstructing which sub-agent produced which fragment when the parent assembles the final blueprint.
2. Update branch state with `branch_update` when a choice is made or backtracking happens.
3. **Prefer `memory_query` over `memory_search` for control-flow decisions.** `memory_query` accepts exact `filters` (e.g. `{"record.audit_pass": true, "blueprint_sha256": "..."}`), `contains` substring matching, `limit`, and `reverse=true`. Use it for: most recent self_audit, most recent verifier_response, all failed_paths for a `plan_id`, all notation_dictionary entries for a symbol, branch state by `branch_id`. Reserve `memory_search` (BM25 over JSONL) for fuzzy *discovery*, not for control-flow gates.
3. When a branch dies, append to `failed_paths` with a concrete reason and evidence.
4. When you propose decomposition plans or identify stuck points, persist them clearly so later skills and sub-agents can reuse them.
5. If a proof step uses an external result from search tools, record the complete statement and its source identifiers in the proof step itself:
   - paper id
   - arXiv id if applicable
   - theorem id if available
6. Before using an external result from a paper, expand the definitions and concepts appearing in that statement using the surrounding context of the paper, and check carefully that the result is genuinely applicable in the current setting. Do not assume that the same words mean the same thing across different mathematical contexts.


### Verification repair loop

If an informal blueprint or candidate proof does not pass verification:

1. Revise it using the verification report.
2. Resolve critical errors first.
3. Do not assume the fix is purely local; if needed, change strategy, backtrack, or choose a different direction.
4. After critical errors are addressed, resolve all remaining errors and gaps.
5. Invoke the appropriate skills based on the current state before re-running verification.

If the problem appears difficult, actively explore different directions and proof strategies instead of forcing one narrow path. In such cases, it is acceptable and encouraged to write long, detailed proof blueprints when they help organize the strategy and preserve partial progress.
If the current problem appears to be an open conjecture or open problem, that is not a reason to stop. This agent is meant to tackle hard open problems. Keep trying serious approaches, keep refining decomposition plans, and preserve partial progress carefully instead of giving up.
If extensive searching fails to uncover useful information, do not stall on further retrieval. Switch to deep self-driven exploration of the problem using the non-search skills, and continue trying to make progress without external support.
If a family of decomposition plans repeatedly fails, use `$identify-key-failures` to summarize the common stuck points, store them in `failed_paths`, and then propose a new generation of decomposition plans.


### Step 4: Stopping rules — four terminal states

A run ends in exactly one of four explicit terminal states. Only the first publishes a verified proof; the other three publish stable companion files so the run's outcome is honest at the filesystem level.

- **`verified_correct`** — Verifier returned `verdict=correct` with empty `critical_errors` and `gaps`; the `verified_blueprint_sha256` returned by the service matches `sha256(blueprint.md)`. Action: call `publish_terminal_blueprint(problem_id, "verified_correct")`, which writes `results/{problem_id}/blueprint_verified.md`. This is the only path to a verified proof.

- **`unverified_blocked`** — A gap survived three repair rounds (see Gap Ledger below) without progress, or a structural constraint of the proof-obligation graph cannot be satisfied with current evidence, or a fragile claim's counterexample search produced an obstruction. Action: call `publish_terminal_blueprint(problem_id, "unverified_blocked", summary_markdown=...)`, which writes `results/{problem_id}/blueprint_blocked.md`. The summary names the surviving blocking gap, the strategies tried, and the missing lemma or hypothesis that would unblock progress.

- **`unverified_budget_exhausted`** — A budget dimension in `meta.json` (`max_wall_seconds`, `max_recursive_rounds`, `max_verifier_calls`, `max_external_papers`) was exhausted before a verified verdict was obtained. Action: call `publish_terminal_blueprint(problem_id, "unverified_budget_exhausted", summary_markdown=...)`, which writes `results/{problem_id}/blueprint_partial.md`. Budget exhaustion is **not** failure — record progress and next recommended branches via `write_partial_progress_report`.

- **`unverified_partial_progress`** — The agent voluntarily yields with progress recorded but no verdict (e.g. when handing back to the user for an external decision). Action: call `publish_terminal_blueprint(problem_id, "unverified_partial_progress", summary_markdown=...)`.

Never claim the proof is correct in any state other than `verified_correct`. Never overwrite `blueprint.md` with a terminal companion file — `publish_terminal_blueprint` writes a new file alongside it.

## Proof Writing Discipline

This section governs how every proof step is written into `blueprint.md`. It is mandatory; `$self-audit` enforces it before `$verify-proof` is allowed to call the verification service, and the verifier independently re-checks every rule.

### Justification tag taxonomy

Every displayed claim in the proof must end with exactly one inline justification tag from this fixed set:

- `[def: D<i>]` — by a definition listed in the `## Definitions` block (e.g. `[def: D1]`, `[def: D7]`). The bare `[def: name]` form is **not** accepted; every definition use must name an indexed definition. Locally introduced definitions inside a single lemma are stated in that lemma's `## Context` block and tagged `[def: local <i>]`.
- `[hyp: H<i>]` — by a named hypothesis from the `## Assumptions` block (e.g. `[hyp: H1]`, `[hyp: H2]`, `[hyp: local A]`). The bare `[hyp]` form (no identifier) is **not** accepted; every hypothesis use must name which hypothesis is being invoked.
- `[calc: E<n>]` — by a numbered computation display labeled `(E<n>)` above this line (e.g. `[calc: E7]`). The bare `[calc N]` form without the `E` prefix is accepted as a legacy form but new code should use `[calc: E<n>]`.
- `[cite: paper_id, thm_id]` — by an external result. The full statement and source identifiers (paper_id, theorem_id, arXiv id) must appear nearby in the proof, AND a complete theorem-application table must accompany the citation (see `$align-with-source-notation`).
- `[from: L<x>]` or `[from: L<x>.eq<y>]` or `[from: L<x>.claim<y>]` — by a previously proved local lemma/proposition X (optionally a specific equation `eq<y>` or claim `claim<y>` inside it). Use the colon form `[from: L4]` consistently. The legacy form `[from L.4]` is still accepted but disambiguates more poorly inside the proof-obligation graph.
- `[wlog: reason]` — without loss of generality, with a one-clause reason.
- `[ind: name]` — by the named induction hypothesis.
- `[comp]` — by composition.
- `[functoriality]` — by functoriality of a named functor.
- `[naturality]` — by naturality of a named transformation.

No other tag labels are accepted. No claim may be untagged. Tags must resolve.

### Step granularity rule

Every transition between displayed claims must be exactly one atomic move from the taxonomy above. Compound transitions (more than one atomic move chained together) must be split into multiple displayed intermediate claims, each with its own tag. `$enforce-step-granularity` is the operational version of this rule and must be invoked whenever a transition is being committed.

Chained equalities $a = b = c = d$ are allowed *inside* a single numbered computation display, but each `=` step carries its own inline tag.

### Banned phrases

The following phrases, appearing in `blueprint.md` without an immediately-following resolved tag, are critical errors — they always signal an unstated transition:

- "clearly", "obviously", "trivially"
- "it follows that" (without an immediately-following `[from: ...]` or `[cite: ...]`)
- "by symmetry" (without an immediately-following `[from: ...]`)
- "by a standard argument", "by a standard X argument" (for any X)
- "as usual"
- "we omit the details", "the proof is standard"
- "it is easy to see that" (without an immediately-following tag)
- "an analogous argument shows" (without an immediately-following `[from: ...]` to the analogous lemma)

If "by a standard X argument" appears, the fix is not to add a tag — it is to **create a named local lemma with prefix `Lstd`** (see the Standard-lemma library section), prove it, and then cite it via `[from: Lstd<n>]`. The verifier's `$check-proof-obligation-graph` will trace the dependency through the standard lemma's own node.

If any other banned phrase appears, the transition must be split and tagged using `$enforce-step-granularity`.

### Three-tier notation rule

Notation discipline applies at three strictness tiers; `$align-with-source-notation` is the operational version of this rule.

- **Tier 1 — Global Notation.** Symbols used across multiple lemmas, imported from external sources, or persistent through the proof. Each Tier-1 symbol must have a `notation_dictionary` entry with `scope: "global"` and must appear as a bullet in the blueprint's `## Notation` section. When a result is cited from a source paper, the proof must use the source's **exact** symbols and names; if a local rename is unavoidable, an explicit one-sentence renaming declaration must appear in the proof and a corresponding `notation_dictionary` entry must record `source: "self-renaming from paper_id, ..."`. Silent renamings are critical errors.
- **Tier 2 — Local Variables.** Bound variables introduced inside a single lemma proof (e.g. "let $\eta \in \Omega^1(M)$", "fix $\epsilon > 0$"). These are declared at the introduction site inside the lemma. Append to `notation_dictionary` with `scope: "local"` and `scope_block: "<lemma_id>"` for parent-agent bookkeeping, but **do not** flush them to `## Notation`. They must not be reused with a different meaning outside their lemma; leaking a local symbol out of scope is a critical error.
- **Tier 3 — Standard Constants.** A small whitelist of universal symbols (`\mathbb{N}`, `\mathbb{Z}`, `\mathbb{Q}`, `\mathbb{R}`, `\mathbb{C}`, `\emptyset`, `id`, `\in`, `\subset`, etc.) plus any symbols declared under a `# Standard Constants` heading in `data/{problem_id}.glossary.md`. No `notation_dictionary` entry needed; the verifier resolves from the whitelist. If a problem uses a whitelisted symbol with a non-standard meaning, promote it to Tier 1 with an explicit `## Notation` entry overriding the default.

### Notation section in the blueprint

The blueprint must contain a `## Notation` section near the top (after the title, before the first lemma) listing every Tier-1 entry from `notation_dictionary`. Tier-2 declarations live inline inside their lemmas; Tier-3 constants need no declaration. The verifier reads `## Notation` to perform `$check-notation-consistency`; if it is missing or stale relative to the Tier-1 entries, the audit fails.

### Assumptions section in the blueprint

The blueprint must contain a `## Assumptions` block (alongside `## Notation`) listing every hypothesis from the problem statement with an explicit identifier:

```markdown
## Assumptions
- H1: $M$ is a smooth manifold.
- H2: $\mathcal{F}$ is a singular foliation on $M$.
- H3: $p$ is a fixed point of every leaf-preserving symmetry.
```

Justification tags use `[hyp: H<i>]` referencing these identifiers. Every assumption must be either invoked by at least one `[hyp: H<i>]` tag in the proof body or annotated `usage: "unused-by-design"` in `notation_dictionary` with a one-sentence reason.

### Definitions section in the blueprint

The blueprint must contain a `## Definitions` block (alongside `## Notation` and `## Assumptions`) listing every locally-introduced definition with an explicit identifier:

```markdown
## Definitions
- D1: A morphism $f$ is **proper at $x$** iff every neighborhood of $x$ has a saturated preimage.
- D2: The **leaf closure** of $x$ is $\overline{L_x}$, the closure of the leaf through $x$ in $M$.
- D3: A foliation is **regular at $x$** iff its dimension is locally constant on a neighborhood of $x$.
```

Justification tags use `[def: D<i>]` referencing these identifiers. The bare `[def: name]` form is rejected — every definition use must name a numbered definition, so the proof-obligation graph can trace dependency precisely.

### Local Context blocks per lemma

Every lemma, proposition, and theorem must begin with a `## Context` block listing the active assumptions, definitions, notation entries, and local variables in scope at that proof:

```markdown
# Lemma L4: ...

## Context
- Active assumptions: H1, H2, H5.
- Active definitions: D1, D2, D7.
- Active notation: N1, N3, N9.
- Local variables:
  - $x \in M$.
  - $U$ is an open neighborhood of $x$.
  - $\pi: E \to B$ is the bundle map from D7.

## Statement
...

## Proof
...
```

The verifier (`$check-notation-consistency`, `$check-proof-obligation-graph`) uses these context blocks to detect **scope drift** — the failure mode where a proof starts with one neighborhood, later uses a smaller neighborhood, and silently forgets which properties survive shrinking. Every symbol used inside the lemma must be reachable through `## Notation`, the lemma's `## Context` local variables, or the Tier-3 standard whitelist.

### Display every nontrivial computation (aligned form)

Every nontrivial computation must be displayed in an *aligned* environment with one tag per step. Conclusion-only computations (e.g., "Thus $T(\eta) = 0$" without a displayed derivation) are critical errors caught by the verifier's `$check-computational-replay`.

Required form for any multi-step computation:

```markdown
\[
\begin{aligned}
A
&= B && [def: D3] \\
&= C && [from: L2.eq1] \\
&= 0 && [hyp: H4].
\end{aligned}
\tag{E7}
\]

Therefore $A = 0$. [calc: E7]
```

Rules:

- Every equality/inequality/congruence step in a displayed computation gets its own inline tag in the second column of the aligned environment.
- The display is numbered with a `\tag{E<n>}` and referenced in prose by `[calc: E<n>]`.
- A prose sentence may cite the whole computation only with `[calc: E<n>]`; it may not chain multiple steps inline.
- No "therefore $A = 0$" unless the display labeled `(E<n>)` actually ends in $A = 0$ (or a cited lemma gives it).
- Single-step "computations" (one displayed equality with one tag) may use the simpler form $A = B \quad [\text{tag}]$ without the aligned environment.

### Standard-lemma library (replace "by a standard argument")

The phrase "by a standard argument" is banned. If the agent wants to use a standard argument, it must create a named lemma in the blueprint with id prefix `Lstd`. For example:

```markdown
# Lemma Lstd1: Shrinking preserves saturated-neighborhood containment

## Context
- Active assumptions: H1.
- Active definitions: D1, D4.
- Local variables: $U \supset V$ open subsets of $M$.

## Statement
If $U \supset V$ are open and $U$ is saturated for $\mathcal{F}$, then so is $V \cap U$.

## Proof
...
```

Then any later proof step that would have said "by a standard saturation argument" instead writes:

```markdown
We use Lemma Lstd1, whose proof is included above. [from: Lstd1]
```

Standard lemmas may be collected in a per-problem file `results/{problem_id}/standard_lemmas.md` for re-use across attempts on the same problem, but each one used in the final proof must still be cited via a `[from: Lstd<n>]` tag and must appear (either inline or as a transcluded reference) before its first use. There is no privileged status: a `Lstd` lemma is audited identically to any other local lemma — it has a proof-obligation node, must be in `## Context` of any lemma that uses it, and must be acyclic with the rest of the graph.

### Self-audit gate (multi-hash-anchored)

`$verify-proof` may not call `verify_proof_service` until `$self-audit` returns `audit_pass=true` for the current rigor-mode artifact state. "Current state" is defined by **three** hashes: `blueprint_sha256 = sha256(blueprint.md)`, `proof_obligations_sha256 = sha256(proof_obligations.json)`, and `notation_dictionary_sha256 = sha256(notation_dictionary.jsonl)`. All three must match the corresponding fields on the most recent passing `self_audit` record. Any edit to any of those three files invalidates the audit; re-run `$self-audit` before re-invoking `$verify-proof`.

When `$verify-proof` invokes `verify_proof_service`, it must pass `problem_id`, `attempt_id`, `blueprint_sha256`, `proof_obligations_sha256`, `notation_dictionary_sha256`, `self_audit_id`, and the literal content of `proof_obligations.json` so the verification service can run `$check-proof-obligation-graph` over the structural DAG. The verifier writes all three hashes back into `results/{run_id}/metadata.json` and includes `verified_blueprint_sha256` in the response, closing the round-trip.

## Accuracy Modes (sequential progression)

The agent self-declares its current mode in `memory/{problem_id}/meta.json` under the key `mode`. The four modes progress in order; each transition is recorded in `events` as `event_type="mode_transition"`. Skipping a mode (e.g. jumping from `exploration` straight to `verification`) is a critical error caught by `$self-audit`.

- **`exploration`** — sketches, searches, examples, counterexamples, fragile-claim hunting. **May not write `blueprint.md` content other than the title, `## Notation`, `## Assumptions`, `## Definitions`, and exploratory drafts marked `<!-- mode: exploration -->`.** May not call `verify_proof_service`.

- **`assembly`** — writes the candidate blueprint with every claim tagged. Every nontrivial assertion gets a `proof_obligations.json` node (`status: "stub"` is acceptable in this mode). May not call `verify_proof_service`. Transition criterion: every assertion the agent intends to prove has a node and a `proof_location`.

- **`rigor`** — every claim must be in `proof_obligations.json` with `status` in `{proved_in_blueprint, external_citation}` (no `stub` reachable from `MainThm`); every citation has a theorem-application table; every computation is in aligned form; every notation entry is Tier-1/2/3-classified. The DAG is acyclic. `$self-audit` will return `audit_pass=true` only in rigor mode (or later). Transition criterion: `$self-audit` returns `audit_pass=true`.

- **`verification`** — no editing the blueprint except through repair tickets in the `gap_ledger`. `$verify-proof` may be invoked. Transition criterion: a passing `$self-audit` exists for the current triple-hash.

- **`blocked`** — only the `unverified_blocked` terminal path may be taken from here. Set when monotone-repair convergence fails (see Gap Ledger). The agent records the blocking gap and calls `publish_terminal_blueprint(..., "unverified_blocked", ...)`.

Mode order is `exploration → assembly → rigor → verification → (verified_correct | blocked)`. Each transition writes:

```json
{"event_type": "mode_transition", "from": "<prev>", "to": "<next>", "blueprint_sha256": "..."}
```

## Gap Ledger (monotone-repair rule)

Every verifier `gap` and every blocking finding from `$self-audit` becomes a repair ticket in the `gap_ledger` memory channel:

```json
{
  "gap_id": "GAP-004",
  "location": "Lemma L5 proof, paragraph 3",
  "issue": "The proof uses compactness of the orbit but only properness at x was assumed.",
  "required_fix": "Either prove compactness from H<i> or weaken the step.",
  "status": "open|addressed|rejected|blocked",
  "round": 1,
  "blocking_reason": null
}
```

A **repair round** is one cycle of: edit the blueprint → re-run `$self-audit` (if it had failed) → call `verify_proof_service` (if self-audit passes) → read the verifier response → update the ledger.

**Monotone-repair rule.** A repair round is valid only if it closes at least one `open` ticket (`addressed`), or it adds a brand-new subgoal lemma, or it explicitly changes the proof strategy (recorded as a `big_decisions` entry referencing the surviving ticket).

If the same `gap_id` survives three rounds in `status="open"` without progress, mark its `status="blocked"` and set `blocking_reason`. Switch the agent's mode to `blocked` and proceed to `unverified_blocked`. Do not keep rewriting the same lemma locally — record the missing lemma as a new subgoal in `subgoals` or a `failed_path`, and try a different proof strategy on a future run.

## Rigor Mode: Proof Obligation Discipline

The final blueprint is not only prose. Every nontrivial assertion in `blueprint.md` must have a corresponding node in `results/{problem_id}/proof_obligations.json`.

A proof obligation node records:

- unique `node_id` (`L<n>`, `D<n>`, `H<n>`, `N<n>`, `<parent>.eq<n>`, `E<n>`, `MainThm`);
- `type` (`lemma`, `proposition`, `theorem`, `claim`, `equation`, `computation`, `definition`);
- exact `statement`;
- local `context` (active assumptions, definitions, notation entries in scope at the node site);
- `depends_on` (node_ids of earlier obligations the node uses, plus `Source.*` for external citations);
- `proof_location` (a stable markdown anchor inside `blueprint.md`);
- `status` (`proved_in_blueprint`, `axiom`, `external_citation`, `stub`, `blocked`);
- `verification_status` (`unchecked`, `verified`, `failed`);
- `blueprint_sha256` (the hash at the time the obligation was last updated).

Before writing any theorem, lemma, claim, or computation into the final blueprint:

1. Create or update its proof-obligation node.
2. Ensure all dependencies point backward (earlier `proof_location`), or are external `Source.*` citations.
3. Ensure no dependency chain returns to the current node or to `MainThm` (no node may transitively depend on the theorem it is helping to prove).
4. Ensure every symbol used in the node's `statement` is declared in `## Notation`, in the parent lemma's `## Context`, or in the Tier-3 standard-constants whitelist.
5. Ensure every external `Source.*` dependency has a corresponding theorem-application table in the markdown (see `$align-with-source-notation`).

A proof is acceptable only if:

- the proof-obligation graph is acyclic;
- every obligation reachable from `MainThm` (via reverse-`depends_on`) is `proved_in_blueprint` or `external_citation` — no `stub` or `blocked` nodes in that subgraph;
- every displayed assertion has an exact inline tag whose target appears in the node's `depends_on`;
- every computation is displayed and replayable;
- every external theorem has a theorem-application table;
- the verifier returns `verdict=correct` for the exact current triple `(blueprint_sha256, proof_obligations_sha256, notation_dictionary_sha256)`.

This turns "no circular reasoning" and "no missing dependencies" from prose discipline into a data invariant. The verifier's `$check-proof-obligation-graph` pass is structural; the markdown-level audits cannot catch what only the DAG can.

### Warning severity (verifier output)

The verifier returns three severity levels in its `verification_report`:

- `critical_error` — proof is mathematically invalid or applies a nonexistent / misused theorem. **Blocks `verdict=correct`.**
- `gap` — proof may be true but is missing a needed argument, justification, or computation. **Blocks `verdict=correct`.**
- `warning` — style, cleanup, orphan notation entries, redundant declarations, verbosity. **Does NOT block `verdict=correct`.** Record for cleanup in a follow-up revision, but the proof is accepted.

## Hard Invariants

1. Every intermediate artifact must be written to memory.
2. Failed paths are mandatory memory artifacts and must remain queryable.
3. Decomposition plans and key failures are dynamic: keep proposing new plans, but preserve the failure information from previous plans.
4. Verification must pass before final output.
5. Any verifier `wrong` verdict, any critical error, or any gap counts as verification failure.
6. Supporting definitions, lemmas, and propositions should appear before later statements that rely on them, and the main theorem must appear last.
7. External results used in proofs must be cited with their complete statement and source identifiers when available.
8. The final markdown proof text must also include the complete statement, `paper_id`, `theorem_id`, and `arXiv id` when applicable for any cited external result.
9. External paper results must not be used as black boxes without context-checking: expand the paper's local definitions, disambiguate terminology, and verify applicability before relying on the statement.
10. Do not read anything outside the current working directory under any circumstance.
11. For difficult problems, prefer broader exploration of multiple proof strategies and allow long proof blueprints when they help track the argument.
12. For the final target theorem section, the `## statement` text must be the original complete informal statement from the input markdown problem file, not a shortened or paraphrased version.
13. If the problem appears to be an open conjecture or open problem, do not treat that as a stopping condition. Keep trying to tackle it seriously, but never claim success unless the proof has actually passed verification.
14. Extensive search is not enough by itself. The agent must also think deeply and explore the problem on its own, and if retrieval stops being useful, it must continue with the non-search skills rather than waiting for external support.



Use these tools when relevant:

- `search_theorem_index`
- `memory_init`
- `memory_append` (stamp `agent_id`, `skill`, `branch_id`, `plan_id`, `attempt_id`, `parent_agent_id` whenever known)
- `memory_query` (exact filters; use for control-flow gates)
- `memory_search` (BM25; use for fuzzy discovery)
- `branch_update`
- `verify_proof_service`
- `write_partial_progress_report` (when any budget dimension in `meta.json` is exhausted)

Always call `search_theorem_index` for nontrivial subgoals and key claims to ground reasoning in related literature.
Use Claude Code's built-in `WebSearch` tool early to gather background (terminology, standard lemmas, common techniques) and throughout when constructing examples/counterexamples or proving subgoals.
Prefer `$search-math-results` to orchestrate this retrieval flow: use `search_theorem_index` first, then fall back to the `WebSearch` tool when the theorem search is not useful.
If `$search-math-results` identifies a useful paper, download it inside the current working directory, extract its text, and read the extracted text before using the paper in reasoning or proof writing.
If `$search-math-results` identifies a useful theorem, read the proof of that theorem as well and extract any techniques or ideas that may help with the current statement.
When considering an external theorem from a paper, expand the definitions and concepts in that theorem using the paper's own context and terminology, and check carefully that the theorem is actually applicable to the current situation.
If extensive retrieval still does not yield useful support, stop relying on search and continue the proof attempt through deep independent reasoning and the other provided skills.
Use `verify_proof_service` for proof verification instead of relying on model-only checking.
Only call `verify_proof_service` when a full proof of the whole problem has been assembled in `blueprint.md`. Do not call it on partial proofs, incomplete branches, isolated lemmas, or drafts that have made no real progress on the full theorem.
When calling `verify_proof_service`, always use a large timeout of `3600` seconds.

## Output Contract

Write the proof in markdown in `results/{problem_id}/blueprint.md`, in a paper-like format such as:

```markdown
# lemma lem:xxx

## statement
put the statement here

## proof
put the proof of this statement here
```

The main theorem should be written at the end. After the proof passes verification, rename the file to `results/{problem_id}/blueprint_verified.md`.

For the final target theorem section, `## statement` must be the original complete statement from the input markdown problem file written in full.

If `## proof` cites an external result, include in the proof text:

- the complete cited statement
- `paper_id`
- `theorem_id`
- `arXiv id` when applicable
