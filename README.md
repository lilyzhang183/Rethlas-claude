# Rethlas-claude

A Claude-native port of [frenzymath/Rethlas](https://github.com/frenzymath/Rethlas) — a natural-language reasoning system for mathematics built around two agents:

- The **generation agent** reads a math problem from a markdown file and writes an informal proof blueprint.
- The **verification agent** checks that proof blueprint, produces a structured verdict, and serves as the generation agent's verifier.

Upstream Rethlas runs on the OpenAI Codex CLI. This fork runs the same architecture on the Claude Code CLI: the `AGENTS.md` instruction files become `CLAUDE.md`, the skill folder moves from `.agents/skills/` to `.claude/skills/`, the Codex multi-agent config becomes a Claude Code subagent definition, and the FastAPI verification service spawns `claude -p` instead of `codex exec`. The mathematical skill content (~10 generation skills, 3 verification skills, the proof-and-repair loop, the verdict schema) is unchanged.

The intended deployment order is:

1. Start the verification agent as a local HTTP service.
2. Run the generation agent through Claude Code.
3. Let the generation agent call the verification service during its proof-and-repair loop.

## Repository Layout

- `agents/generation`: the proof-generation agent (CLAUDE.md, skills, subagent, MCP server, data, site)
- `agents/verification`: the proof-verification agent (CLAUDE.md, skills, FastAPI server, MCP server, schemas)

In particular,
- Original problems are put in `agents/generation/data/`, e.g. unclassified problem `agents/generation/data/example.md`, or classified problem `agents/generation/data/modrep/modrep.md`, `agents/generation/data/example/example1.md`.
- Zola project to render the results in a static website is in `agents/generation/site/`.

## 1. Install Claude Code

Install the Claude Code CLI per the [official quickstart](https://code.claude.com/docs/en/quickstart.md). On macOS:

```bash
claude install stable
```

Sign in once with `claude login`. Confirm the CLI works:

```bash
claude --version
```

## 2. Clone the Repository

```bash
git clone https://github.com/lilyzhang183/Rethlas-claude.git
cd Rethlas-claude
```

## 3. Start the Verification Service

```bash
cd agents/verification
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.server:app --host 0.0.0.0 --port 8091
```

Using uv:

```bash
cd agents/verification
uv venv
uv pip install -r requirements.txt
uv run uvicorn api.server:app --host 0.0.0.0 --port 8091
```

The verification service is configured via environment variables:

- `CLAUDE_BIN` (default: `claude`)
- `CLAUDE_MODEL` (default: `claude-opus-4-8`)
- `CLAUDE_EFFORT` (default: `xhigh`)
- `CLAUDE_TIMEOUT_SECONDS` (default: unbounded)

## 4. Run the Generation Agent on the Included Example

In a separate terminal:

```bash
cd agents/generation
python3 -m venv .venv
source .venv/bin/activate
pip install -r mcp/requirements.txt
./tests/run_example.sh
```

This script:

- reads `agents/generation/data/example.md`
- runs `claude -p` inside `agents/generation`
- writes the run log to `agents/generation/logs/example/example.md`
- writes memory artifacts to `agents/generation/memory/example/`
- writes the draft proof to `agents/generation/results/example/blueprint.md`
- writes the verified proof to `agents/generation/results/example/blueprint_verified.md` if verification succeeds

Override the model or reasoning effort:

```bash
MODEL=claude-sonnet-4-6 EFFORT=high ./tests/run_example.sh
```

Run a different problem:

```bash
PROBLEM_FILE=data/modrep/modrep.md ./tests/run_example.sh
```

## How the Port Differs from Upstream

| Upstream (Codex)                              | This fork (Claude)                                        |
| --------------------------------------------- | --------------------------------------------------------- |
| `codex exec` subprocess                       | `claude -p` subprocess                                    |
| `AGENTS.md`                                   | `CLAUDE.md`                                               |
| `.agents/skills/<name>/SKILL.md`              | `.claude/skills/<name>/SKILL.md` (same frontmatter)       |
| `.codex/agents/<name>.toml`                   | `.claude/agents/<name>.md`                                |
| `.codex/config.toml` `[mcp_servers.*]`        | `.mcp.json` at project root                               |
| `--config model_reasoning_effort=xhigh`       | `--effort xhigh`                                          |
| `--dangerously-bypass-approvals-and-sandbox`  | `--dangerously-skip-permissions`                          |
| Codex built-in web search                     | Claude Code's built-in `WebSearch` tool                   |
| Codex `spawn_agent` / `wait_agent` primitives | Claude Code `Agent` tool with `subagent_type=subgoal-prover` |

What did **not** change:
- The MCP servers under `agents/*/mcp/server.py` are byte-identical to upstream.
- The verdict JSON schema and the FastAPI surface (`GET /health`, `POST /verify`) are unchanged.
- The memory channel layout and the BM25 search behavior are unchanged.
- All ten generation skills and all three verification skills retain their mathematical procedures, output contracts, and stopping rules.

## License and Attribution

Inherits the Apache License 2.0 from upstream Rethlas. See [LICENSE](LICENSE) and [NOTICE](NOTICE) for required attribution.
