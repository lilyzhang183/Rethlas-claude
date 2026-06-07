"""Infrastructure smoke tests for the verification API + MCP module.

These tests do not launch Claude. They exercise input validation, the
prompt-fence design, and the schema/semantic validator's edge cases.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Conftest.py puts REPO_ROOT on sys.path.
from api.server import (
    VerifyRequest,
    build_prompt,
    _http_detail,
)
from mcp.server import (
    sanitize_problem_id,
    validate_verification_output,
)


# --------------------------- Pydantic request schema ----------------------------


def test_verify_request_rejects_empty_statement() -> None:
    with pytest.raises(Exception):  # pydantic.ValidationError
        VerifyRequest(statement="", proof="non-empty")


def test_verify_request_rejects_empty_proof() -> None:
    with pytest.raises(Exception):
        VerifyRequest(statement="non-empty", proof="")


def test_verify_request_accepts_minimal_payload() -> None:
    req = VerifyRequest(statement="S", proof="P")
    assert req.problem_id is None
    assert req.attempt_id is None
    assert req.blueprint_sha256 is None
    assert req.self_audit_id is None


def test_verify_request_accepts_full_handshake_payload() -> None:
    req = VerifyRequest(
        statement="S",
        proof="P",
        problem_id="algebra/modrep",
        attempt_id="attempt-3",
        blueprint_sha256="a" * 64,
        self_audit_id="audit_20260607T134522Z_abcd1234",
    )
    assert req.problem_id == "algebra/modrep"
    assert req.attempt_id == "attempt-3"
    assert req.blueprint_sha256 == "a" * 64
    assert req.self_audit_id.startswith("audit_")


# ------------------- build_prompt: untrusted-data fence design ------------------


def test_build_prompt_does_not_inline_statement_or_proof() -> None:
    """The prompt must NOT contain the statement or proof inline.

    The verifier reads them from request.json. This is item 3 from the
    reviewer: avoids CLI-length limits and keeps proof text out of logs.
    """
    prompt = build_prompt(run_id="20260607T134522Z_abcd1234")
    assert "AB#NOT_A_STATEMENT_MARKER_xyz_42" not in prompt  # sanity check
    # The fence design implies the prompt instructs Claude to READ a file,
    # not embed the statement/proof. We assert both absent and the file
    # reference present.
    assert "request.json" in prompt
    assert "{statement}" not in prompt and "{proof}" not in prompt


def test_build_prompt_includes_untrusted_data_instruction() -> None:
    prompt = build_prompt(run_id="run_xyz")
    assert "UNTRUSTED" in prompt
    assert "do not follow" in prompt.lower() or "do not follow any instructions" in prompt.lower()


def test_build_prompt_includes_run_id() -> None:
    prompt = build_prompt(run_id="run_xyz")
    assert "run_xyz" in prompt


# ------------------------- _http_detail: debug visibility -----------------------


def test_http_detail_carries_run_id_and_log_path() -> None:
    detail = _http_detail("something went wrong", run_id="run_xyz", exit_code=137)
    assert detail["message"] == "something went wrong"
    assert detail["run_id"] == "run_xyz"
    assert "log_path" in detail
    assert "request_path" in detail
    assert detail["exit_code"] == 137


# ------------------------------ Validator semantics -----------------------------


def _findings_set(verdict: str, critical: int = 0, gaps: int = 0, warnings: int = 0, repair: str = "") -> dict:
    """Helper to build a minimally-valid verification output."""
    return {
        "verification_report": {
            "summary": "test",
            "critical_errors": [
                {"location": f"loc_{i}", "issue": f"crit issue {i}", "severity": "critical_error"}
                for i in range(critical)
            ],
            "gaps": [
                {"location": f"loc_g{i}", "issue": f"gap issue {i}", "severity": "gap"}
                for i in range(gaps)
            ],
            "warnings": [
                {"location": f"loc_w{i}", "issue": f"warn issue {i}", "severity": "warning"}
                for i in range(warnings)
            ],
        },
        "verdict": verdict,
        "repair_hints": repair,
    }


def test_validator_accepts_correct_with_no_findings() -> None:
    payload = _findings_set("correct")
    result = validate_verification_output(payload)
    assert result["valid"], result["errors"]


def test_validator_accepts_correct_with_warnings_only() -> None:
    """Warnings do not block verdict=correct (reviewer item 9)."""
    payload = _findings_set("correct", warnings=3)
    result = validate_verification_output(payload)
    assert result["valid"], result["errors"]


def test_validator_rejects_correct_with_critical_error() -> None:
    payload = _findings_set("correct", critical=1)
    result = validate_verification_output(payload)
    assert not result["valid"]
    assert any("verdict='correct' is invalid" in e for e in result["errors"])


def test_validator_rejects_correct_with_gap() -> None:
    payload = _findings_set("correct", gaps=1)
    result = validate_verification_output(payload)
    assert not result["valid"]
    assert any("verdict='correct' is invalid" in e for e in result["errors"])


def test_validator_rejects_wrong_with_no_findings() -> None:
    payload = _findings_set("wrong", repair="anything")
    result = validate_verification_output(payload)
    assert not result["valid"]
    assert any("verdict='wrong' requires" in e for e in result["errors"])


def test_validator_rejects_wrong_with_empty_repair_hints() -> None:
    payload = _findings_set("wrong", critical=1, repair="")
    result = validate_verification_output(payload)
    assert not result["valid"]
    assert any("repair_hints must be non-empty" in e for e in result["errors"])


def test_validator_rejects_correct_with_nonempty_repair_hints() -> None:
    payload = _findings_set("correct", repair="suggestion")
    result = validate_verification_output(payload)
    assert not result["valid"]
    assert any("repair_hints must be empty" in e for e in result["errors"])


def test_validator_rejects_missing_warnings_field() -> None:
    payload = _findings_set("correct")
    del payload["verification_report"]["warnings"]
    result = validate_verification_output(payload)
    assert not result["valid"]


def test_validator_rejects_invalid_verdict() -> None:
    payload = _findings_set("correct")
    payload["verdict"] = "maybe"
    result = validate_verification_output(payload)
    assert not result["valid"]


# ---------------------------- sanitize_problem_id ------------------------------


def test_sanitize_problem_id_rejects_path_traversal_dotdot() -> None:
    with pytest.raises(ValueError):
        sanitize_problem_id("../escape")


def test_sanitize_problem_id_rejects_embedded_dotdot() -> None:
    with pytest.raises(ValueError):
        sanitize_problem_id("algebra/../etc/passwd")


def test_sanitize_problem_id_preserves_category_directories() -> None:
    assert sanitize_problem_id("algebra/modrep") == "algebra/modrep"


def test_sanitize_problem_id_strips_dangerous_chars() -> None:
    result = sanitize_problem_id("foo;bar")
    assert ";" not in result
    assert "bar" in result


def test_sanitize_problem_id_handles_empty_input() -> None:
    # Should not raise; should produce a usable default.
    result = sanitize_problem_id("")
    assert result == "problem"
