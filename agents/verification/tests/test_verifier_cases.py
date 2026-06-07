"""Adversarial verifier-case integration tests.

For each fixture under `verifier_cases/`, POST to the running verification
service at http://127.0.0.1:8091/verify and assert the verdict + issue
substrings match expectations.

These tests **require the verification service to be running** and Claude
Code CLI to be installed. If `/health` is unreachable, the entire module
is skipped.

Run manually:

    cd agents/verification
    uvicorn api.server:app --host 0.0.0.0 --port 8091   # terminal 1
    pytest tests/test_verifier_cases.py -v               # terminal 2
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests


VERIFY_URL = os.getenv("VERIFY_URL", "http://127.0.0.1:8091/verify")
HEALTH_URL = os.getenv("HEALTH_URL", "http://127.0.0.1:8091/health")
PER_CASE_TIMEOUT = int(os.getenv("VERIFIER_CASE_TIMEOUT", "3600"))

CASES_DIR = Path(__file__).parent / "verifier_cases"


def _verifier_running() -> bool:
    try:
        response = requests.get(HEALTH_URL, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


pytestmark = pytest.mark.skipif(
    not _verifier_running(),
    reason=f"Verification service not reachable at {HEALTH_URL}. Start it with `uvicorn api.server:app --port 8091`.",
)


def _load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    if not CASES_DIR.exists():
        return cases
    for case_dir in sorted(CASES_DIR.iterdir()):
        if not case_dir.is_dir():
            continue
        case_file = case_dir / "case.json"
        if not case_file.exists():
            continue
        with case_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload.setdefault("name", case_dir.name)
        cases.append(payload)
    return cases


CASES = _load_cases()
CASE_IDS = [c["name"] for c in CASES]


def _collect_finding_text(report: Dict[str, Any], severity_keys: List[str]) -> str:
    blobs: List[str] = []
    for key in severity_keys:
        findings = report.get(key, []) or []
        for f in findings:
            issue = f.get("issue") if isinstance(f, dict) else None
            location = f.get("location") if isinstance(f, dict) else None
            if issue:
                blobs.append(str(issue))
            if location:
                blobs.append(str(location))
    return "\n".join(blobs)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_case(case: Dict[str, Any]) -> None:
    expected_verdict = case["expected_verdict"]
    expected_issue_subs: List[str] = case.get("expected_issue_substrings", [])
    expected_warn_subs: List[str] = case.get("expected_warning_substrings", [])

    payload = {
        "statement": case["statement"],
        "proof": case["proof"],
    }

    response = requests.post(VERIFY_URL, json=payload, timeout=PER_CASE_TIMEOUT)
    assert response.status_code == 200, f"non-200 response: {response.status_code} {response.text[:500]}"

    body = response.json()
    assert "verdict" in body and "verification_report" in body, f"unexpected response shape: {body!r}"

    actual_verdict = body["verdict"]
    report = body["verification_report"]

    assert actual_verdict == expected_verdict, (
        f"verdict mismatch (case={case['name']}): expected {expected_verdict!r}, "
        f"got {actual_verdict!r}. report={json.dumps(report, ensure_ascii=False)[:600]}"
    )

    if expected_verdict == "wrong":
        issue_text = _collect_finding_text(report, ["critical_errors", "gaps"])
        for substring in expected_issue_subs:
            assert substring.lower() in issue_text.lower(), (
                f"expected substring {substring!r} not found in issues for case {case['name']!r}. "
                f"Issues collected: {issue_text!r}"
            )
    else:  # expected_verdict == "correct"
        warn_text = _collect_finding_text(report, ["warnings"])
        for substring in expected_warn_subs:
            assert substring.lower() in warn_text.lower(), (
                f"expected warning substring {substring!r} not found in warnings for case {case['name']!r}. "
                f"Warnings collected: {warn_text!r}"
            )
