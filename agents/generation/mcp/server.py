from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - dependency should be installed via requirements
    FastMCP = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_ROOT = REPO_ROOT / "memory"

THEOREM_SEARCH_URL = os.getenv("THEOREM_SEARCH_URL", "https://leansearch.net/thm/search")
THEOREM_SEARCH_INDEX_NAME = os.getenv("THEOREM_SEARCH_INDEX_NAME", "leansearch")
THEOREM_SEARCH_TASK = (
    "Given a math statement, retrieve useful references, such as theorems, "
    "lemmas, and definitions, that are useful for solving the given problem."
)

VERIFY_PROOF_URL = "http://127.0.0.1:8091/verify"

CHANNEL_FILES: Dict[str, str] = {
    "immediate_conclusions": "immediate_conclusions.jsonl",
    "toy_examples": "toy_examples.jsonl",
    "counterexamples": "counterexamples.jsonl",
    "big_decisions": "big_decisions.jsonl",
    "subgoals": "subgoals.jsonl",
    "proof_steps": "proof_steps.jsonl",
    "failed_paths": "failed_paths.jsonl",
    "verification_reports": "verification_reports.jsonl",
    "branch_states": "branch_states.jsonl",
    "notation_dictionary": "notation_dictionary.jsonl",
    "events": "events.jsonl",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_problem_component(raw: str) -> str:
    cleaned = re.sub(r"\s+", "_", raw.strip())
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned


def sanitize_problem_id(raw: str) -> str:
    """Return a safe problem id while preserving relative path components."""
    normalized = raw.strip().replace("\\", "/")
    parts: List[str] = []
    for part in normalized.split("/"):
        stripped = part.strip()
        if stripped in {"", "."}:
            continue
        if stripped == "..":
            raise ValueError("problem_id must not contain '..' path components")
        cleaned = _sanitize_problem_component(stripped)
        if cleaned:
            parts.append(cleaned)
    return "/".join(parts) or "problem"

def build_problem_id(source: str, identifier: str) -> str:
    return sanitize_problem_id(f"{source}_{identifier}")


def _resolve_path(path_str: str) -> Path:
    candidate = Path(path_str)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _problem_dir(problem_id: str) -> Path:
    sanitized_problem_id = sanitize_problem_id(problem_id)
    problem_dir = (MEMORY_ROOT / sanitized_problem_id).resolve()
    memory_root = MEMORY_ROOT.resolve()
    if not problem_dir.is_relative_to(memory_root):
        raise ValueError("problem_id resolves outside memory root")
    return problem_dir


def _channel_path(problem_id: str, channel: str) -> Path:
    if channel not in CHANNEL_FILES:
        allowed = ", ".join(sorted(CHANNEL_FILES))
        raise ValueError(f"Unknown channel '{channel}'. Allowed channels: {allowed}")
    return _problem_dir(problem_id) / CHANNEL_FILES[channel]


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _tokenize_bm25(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _bm25_score_documents(
    query: str,
    documents: List[List[str]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> List[float]:
    query_tokens = _tokenize_bm25(query)
    if not query_tokens or not documents:
        return [0.0 for _ in documents]

    query_term_counts = Counter(query_tokens)
    document_frequencies: Counter[str] = Counter()
    document_term_counts = [Counter(document) for document in documents]
    document_lengths = [len(document) for document in documents]
    avg_doc_length = sum(document_lengths) / len(document_lengths) if document_lengths else 0.0
    total_documents = len(documents)

    for document in documents:
        for token in set(document):
            document_frequencies[token] += 1

    scores: List[float] = []
    for doc_counts, doc_length in zip(document_term_counts, document_lengths):
        score = 0.0
        norm = k1 * (1.0 - b + b * (doc_length / avg_doc_length)) if avg_doc_length > 0 else k1
        for token, query_tf in query_term_counts.items():
            term_frequency = doc_counts.get(token, 0)
            if term_frequency <= 0:
                continue
            document_frequency = document_frequencies.get(token, 0)
            idf = math.log(1.0 + ((total_documents - document_frequency + 0.5) / (document_frequency + 0.5)))
            numerator = term_frequency * (k1 + 1.0)
            denominator = term_frequency + norm
            score += query_tf * idf * (numerator / denominator)
        scores.append(score)

    return scores


def search_theorem_index(
    query: str,
    num_results: int = 10,
    endpoint: str = THEOREM_SEARCH_URL,
    index_name: str = THEOREM_SEARCH_INDEX_NAME,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """Query the configured theorem search index.

    Despite the legacy field name `arxiv_id` carried through from
    upstream, this is a theorem-search endpoint (Lean / Mathlib by
    default at leansearch.net), not arXiv full-text search. The
    returned payload tags each hit with the `index_name` it came
    from so the agent knows the source confidence and what fields
    are or are not authoritative.
    """
    if not query.strip():
        raise ValueError("query must be non-empty")
    if num_results <= 0:
        raise ValueError("num_results must be > 0")

    payload = {
        "query": query,
        "task": THEOREM_SEARCH_TASK,
        "num_results": num_results,
    }

    response = requests.post(endpoint, json=payload, timeout=timeout_seconds)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        raise ValueError("The theorem endpoint must return a JSON list")

    normalized: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        arxiv_id = str(item.get("arxiv_id", ""))
        paper_url = (
            f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id and arxiv_id != "None" else ""
        )
        normalized.append(
            {
                "title": str(item.get("title", "")),
                "statement_text": str(item.get("theorem", "")),
                "theorem": str(item.get("theorem", "")),
                "index_name": index_name,
                "arxiv_id": arxiv_id,
                "theorem_id": str(item.get("theorem_id", "")),
                "paper_url": paper_url,
                "source_confidence": "indexed_lean_statement",
                "context_text_path": "",
            }
        )

    return {
        "query": query,
        "count": len(normalized),
        "results": normalized,
        "endpoint": endpoint,
        "index_name": index_name,
    }


# Backwards-compatible alias. The legacy name leaked the misleading
# impression that this hits arXiv full text; the new name names what
# it actually does. Callers that still use the old name keep working.
def search_arxiv_theorems(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return search_theorem_index(*args, **kwargs)


def verify_proof_service(
    statement: str,
    proof: str,
    endpoint: str = VERIFY_PROOF_URL,
    timeout_seconds: int = 3600,
    problem_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    blueprint_sha256: Optional[str] = None,
    self_audit_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not statement.strip():
        raise ValueError("statement must be non-empty")
    if not isinstance(proof, str):
        raise ValueError("proof must be markdown text")
    if not proof.strip():
        raise ValueError("proof markdown must be non-empty")

    payload: Dict[str, Any] = {
        "statement": statement,
        "proof": proof,
    }
    if problem_id is not None:
        payload["problem_id"] = problem_id
    if attempt_id is not None:
        payload["attempt_id"] = attempt_id
    if blueprint_sha256 is not None:
        payload["blueprint_sha256"] = blueprint_sha256
    if self_audit_id is not None:
        payload["self_audit_id"] = self_audit_id

    response = requests.post(endpoint, json=payload, timeout=timeout_seconds)
    response.raise_for_status()

    try:
        body = response.json()
    except ValueError as exc:
        raise ValueError("verification service returned non-JSON response") from exc

    if not isinstance(body, dict):
        raise ValueError("verification service must return a JSON object")

    return {
        "statement": statement,
        "verification_report": body.get("verification_report", {}),
        "verdict": body.get("verdict"),
        "repair_hints": body.get("repair_hints"),
        "endpoint": endpoint,
        "run_id": body.get("run_id"),
        "log_path": body.get("log_path"),
        "request_path": body.get("request_path"),
        "verification_path": body.get("verification_path"),
        "metadata": body.get("metadata"),
    }


DEFAULT_BUDGET: Dict[str, Any] = {
    "max_wall_seconds": 28800,
    "max_recursive_rounds": 5,
    "max_verifier_calls": 8,
    "max_external_papers": 40,
    "on_budget_exhausted": "write_partial_progress_report",
}


def memory_init(
    problem_id: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sanitized_problem_id = sanitize_problem_id(problem_id)
    problem_dir = _problem_dir(sanitized_problem_id)
    problem_dir.mkdir(parents=True, exist_ok=True)

    created_files: Dict[str, str] = {}
    for channel, filename in CHANNEL_FILES.items():
        channel_path = problem_dir / filename
        channel_path.touch(exist_ok=True)
        created_files[channel] = str(channel_path)

    meta_path = problem_dir / "meta.json"
    existing_meta: Dict[str, Any] = {}
    if meta_path.exists() and meta_path.stat().st_size > 0:
        with meta_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            if isinstance(loaded, dict):
                existing_meta = loaded

    merged_meta: Dict[str, Any] = {
        "problem_id": sanitized_problem_id,
        "created_at_utc": existing_meta.get("created_at_utc", _utc_now()),
        "updated_at_utc": _utc_now(),
    }
    merged_meta.update(existing_meta)
    if meta:
        merged_meta.update(meta)

    incoming_budget = (meta or {}).get("budget") if meta else None
    existing_budget = existing_meta.get("budget")
    merged_budget = dict(DEFAULT_BUDGET)
    if isinstance(existing_budget, dict):
        merged_budget.update(existing_budget)
    if isinstance(incoming_budget, dict):
        merged_budget.update(incoming_budget)
    merged_meta["budget"] = merged_budget

    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(merged_meta, handle, indent=2, ensure_ascii=False)

    return {
        "problem_id": sanitized_problem_id,
        "memory_dir": str(problem_dir),
        "meta_path": str(meta_path),
        "channels": created_files,
        "budget": merged_budget,
    }


def memory_append(
    problem_id: str,
    channel: str,
    record: Dict[str, Any],
    agent_id: Optional[str] = None,
    parent_agent_id: Optional[str] = None,
    skill: Optional[str] = None,
    branch_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    blueprint_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")

    memory_init(problem_id)

    entry: Dict[str, Any] = {
        "timestamp_utc": _utc_now(),
        "channel": channel,
    }
    if agent_id is not None:
        entry["agent_id"] = agent_id
    if parent_agent_id is not None:
        entry["parent_agent_id"] = parent_agent_id
    if skill is not None:
        entry["skill"] = skill
    if branch_id is not None:
        entry["branch_id"] = branch_id
    if plan_id is not None:
        entry["plan_id"] = plan_id
    if attempt_id is not None:
        entry["attempt_id"] = attempt_id
    if blueprint_sha256 is not None:
        entry["blueprint_sha256"] = blueprint_sha256
    entry["record"] = record

    target = _channel_path(problem_id, channel)
    _append_jsonl(target, entry)

    if channel != "events":
        event_entry: Dict[str, Any] = {
            "timestamp_utc": _utc_now(),
            "event_type": "memory_append",
            "channel": channel,
        }
        if agent_id is not None:
            event_entry["agent_id"] = agent_id
        if branch_id is not None:
            event_entry["branch_id"] = branch_id
        if attempt_id is not None:
            event_entry["attempt_id"] = attempt_id
        _append_jsonl(_channel_path(problem_id, "events"), event_entry)

    return {
        "status": "ok",
        "channel": channel,
        "path": str(target),
        "entry": entry,
    }


def memory_query(
    problem_id: str,
    channel: str,
    filters: Optional[Dict[str, Any]] = None,
    contains: Optional[str] = None,
    limit: int = 100,
    reverse: bool = True,
) -> Dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be > 0")

    sanitized_problem_id = sanitize_problem_id(problem_id)
    path = _channel_path(sanitized_problem_id, channel)
    items = list(_iter_jsonl(path))

    if filters:
        filtered: List[Dict[str, Any]] = []
        for item in items:
            ok = True
            for key, value in filters.items():
                if item.get(key) != value and item.get("record", {}).get(key) != value:
                    ok = False
                    break
            if ok:
                filtered.append(item)
        items = filtered

    if contains:
        needle = contains.lower()
        items = [item for item in items if needle in json.dumps(item, ensure_ascii=False).lower()]

    if reverse:
        items = list(reversed(items))

    items = items[:limit]
    return {
        "problem_id": sanitized_problem_id,
        "channel": channel,
        "count": len(items),
        "items": items,
    }


def write_partial_progress_report(
    problem_id: str,
    summary_markdown: str,
    reason: str = "budget_exhausted",
    next_recommendations: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if not isinstance(summary_markdown, str) or not summary_markdown.strip():
        raise ValueError("summary_markdown must be a non-empty string")

    sanitized_problem_id = sanitize_problem_id(problem_id)
    results_dir = REPO_ROOT / "results" / sanitized_problem_id
    results_dir.mkdir(parents=True, exist_ok=True)
    report_path = results_dir / "partial_progress.md"

    timestamp = _utc_now()
    header = (
        f"# Partial progress report\n\n"
        f"- problem_id: `{sanitized_problem_id}`\n"
        f"- written_at_utc: `{timestamp}`\n"
        f"- reason: `{reason}`\n"
    )
    if next_recommendations:
        rec_body = "\n".join(f"- {rec}" for rec in next_recommendations)
        next_section = f"\n## Next recommended branches\n\n{rec_body}\n"
    else:
        next_section = ""

    body = f"{header}\n## Summary\n\n{summary_markdown.strip()}\n{next_section}"
    report_path.write_text(body, encoding="utf-8")

    memory_append(
        problem_id=sanitized_problem_id,
        channel="events",
        record={
            "event_type": "partial_progress_report_written",
            "reason": reason,
            "report_path": str(report_path),
            "has_next_recommendations": bool(next_recommendations),
        },
    )

    return {
        "status": "ok",
        "problem_id": sanitized_problem_id,
        "report_path": str(report_path),
        "written_at_utc": timestamp,
        "reason": reason,
    }


def memory_search(
    problem_id: str,
    query: str,
    channels: Optional[List[str]] = None,
    limit_per_channel: int = 10,
) -> Dict[str, Any]:
    if not query.strip():
        raise ValueError("query must be non-empty")
    if limit_per_channel <= 0:
        raise ValueError("limit_per_channel must be > 0")

    if channels is None:
        search_channels = [name for name in CHANNEL_FILES if name != "events"]
    else:
        search_channels = channels

    results_by_channel: Dict[str, Dict[str, Any]] = {}
    total_results = 0
    for channel in search_channels:
        path = _channel_path(problem_id, channel)
        items = list(_iter_jsonl(path))
        documents = [json.dumps(item, ensure_ascii=False) for item in items]
        tokenized_documents = [_tokenize_bm25(document) for document in documents]
        scores = _bm25_score_documents(query, tokenized_documents)

        ranked_results: List[Dict[str, Any]] = []
        for item, score in sorted(
            zip(items, scores),
            key=lambda pair: (
                -pair[1],
                pair[0].get("timestamp_utc", ""),
            ),
        ):
            if score <= 0:
                continue
            ranked_results.append(
                {
                    "score": score,
                    "item": item,
                }
            )
            if len(ranked_results) >= limit_per_channel:
                break

        results_by_channel[channel] = {
            "count": len(ranked_results),
            "results": ranked_results,
        }
        total_results += len(ranked_results)

    return {
        "problem_id": sanitize_problem_id(problem_id),
        "query": query,
        "channels": search_channels,
        "limit_per_channel": limit_per_channel,
        "count": total_results,
        "results_by_channel": results_by_channel,
    }


def branch_update(
    problem_id: str,
    branch_id: str,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    payload = {
        "branch_id": branch_id,
        "state": state,
    }
    return memory_append(problem_id, "branch_states", payload)


def build_mcp_app() -> Optional[Any]:
    if FastMCP is None:
        return None

    app = FastMCP("reasoning-agent")

    @app.tool(name="search_theorem_index")
    def _tool_search_theorem_index(
        query: str,
        num_results: int = 10,
    ) -> Dict[str, Any]:
        return search_theorem_index(query=query, num_results=num_results)

    @app.tool(name="search_arxiv_theorems")
    def _tool_search_arxiv_theorems_legacy(
        query: str,
        num_results: int = 10,
    ) -> Dict[str, Any]:
        # Legacy alias retained for backwards compatibility with any
        # external caller. Prefer `search_theorem_index` in new code
        # and in skill prompts.
        return search_theorem_index(query=query, num_results=num_results)

    @app.tool(name="verify_proof_service")
    def _tool_verify_proof_service(
        statement: str,
        proof: str,
        problem_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        blueprint_sha256: Optional[str] = None,
        self_audit_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return verify_proof_service(
            statement=statement,
            proof=proof,
            problem_id=problem_id,
            attempt_id=attempt_id,
            blueprint_sha256=blueprint_sha256,
            self_audit_id=self_audit_id,
        )

    @app.tool(name="memory_init")
    def _tool_memory_init(
        problem_id: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return memory_init(problem_id=problem_id, meta=meta)

    @app.tool(name="memory_append")
    def _tool_memory_append(
        problem_id: str,
        channel: str,
        record: Dict[str, Any],
        agent_id: Optional[str] = None,
        parent_agent_id: Optional[str] = None,
        skill: Optional[str] = None,
        branch_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        attempt_id: Optional[str] = None,
        blueprint_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        return memory_append(
            problem_id=problem_id,
            channel=channel,
            record=record,
            agent_id=agent_id,
            parent_agent_id=parent_agent_id,
            skill=skill,
            branch_id=branch_id,
            plan_id=plan_id,
            attempt_id=attempt_id,
            blueprint_sha256=blueprint_sha256,
        )

    @app.tool(name="memory_query")
    def _tool_memory_query(
        problem_id: str,
        channel: str,
        filters: Optional[Dict[str, Any]] = None,
        contains: Optional[str] = None,
        limit: int = 100,
        reverse: bool = True,
    ) -> Dict[str, Any]:
        return memory_query(
            problem_id=problem_id,
            channel=channel,
            filters=filters,
            contains=contains,
            limit=limit,
            reverse=reverse,
        )

    @app.tool(name="write_partial_progress_report")
    def _tool_write_partial_progress_report(
        problem_id: str,
        summary_markdown: str,
        reason: str = "budget_exhausted",
        next_recommendations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return write_partial_progress_report(
            problem_id=problem_id,
            summary_markdown=summary_markdown,
            reason=reason,
            next_recommendations=next_recommendations,
        )

    @app.tool(name="memory_search")
    def _tool_memory_search(
        problem_id: str,
        query: str,
        channels: Optional[List[str]] = None,
        limit_per_channel: int = 10,
    ) -> Dict[str, Any]:
        return memory_search(
            problem_id=problem_id,
            query=query,
            channels=channels,
            limit_per_channel=limit_per_channel,
        )

    @app.tool(name="branch_update")
    def _tool_branch_update(
        problem_id: str,
        branch_id: str,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        return branch_update(problem_id=problem_id, branch_id=branch_id, state=state)

    return app


APP = build_mcp_app()


def main() -> None:
    if APP is None:
        raise SystemExit(
            "fastmcp is not installed. Install requirements from mcp/requirements.txt first."
        )
    APP.run()


if __name__ == "__main__":
    main()
