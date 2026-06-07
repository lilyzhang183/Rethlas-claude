"""Runner-gate test: confirm run_example.sh fails fast when the
verification service is down and REQUIRE_VERIFICATION=1 (the default).

This is reviewer item 1 — the most important runtime gate. It must be
mechanically testable so a regression in the gate logic cannot land
silently.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import requests


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = REPO_ROOT / "agents" / "generation" / "tests" / "run_example.sh"


def _verifier_unreachable() -> bool:
    """Confirm the verification service is NOT running on its default port,
    so this test exercises the failure path of REQUIRE_VERIFICATION=1."""
    try:
        response = requests.get("http://127.0.0.1:8091/health", timeout=2)
        return response.status_code != 200
    except requests.RequestException:
        return True


@pytest.mark.skipif(not RUNNER.exists(), reason="run_example.sh not present at expected path")
@pytest.mark.skipif(
    not _verifier_unreachable(),
    reason="Verification service IS running on :8091; this test exercises the failure path.",
)
def test_runner_exits_nonzero_when_verifier_down_and_required() -> None:
    """REQUIRE_VERIFICATION=1 (default) + verifier unreachable → runner fails fast."""
    env = os.environ.copy()
    env.setdefault("REQUIRE_VERIFICATION", "1")
    # Point at a port we know nothing is listening on.
    env["VERIFY_URL"] = "http://127.0.0.1:8091/health"

    completed = subprocess.run(
        ["bash", str(RUNNER)],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode != 0, (
        f"runner exited 0 when verifier was down and REQUIRE_VERIFICATION=1; "
        f"stdout={completed.stdout[:500]!r} stderr={completed.stderr[:500]!r}"
    )
    assert (
        "verification service not reachable" in completed.stderr.lower()
        or "verification service not reachable" in completed.stdout.lower()
    ), f"runner exited nonzero but did not print the expected reason; stderr={completed.stderr[:500]!r}"


@pytest.mark.skipif(not RUNNER.exists(), reason="run_example.sh not present at expected path")
@pytest.mark.skipif(
    not _verifier_unreachable(),
    reason="Verification service IS running on :8091; can't exercise exploratory-mode path.",
)
def test_runner_warns_but_does_not_fail_when_verifier_down_and_exploratory() -> None:
    """REQUIRE_VERIFICATION=0 with verifier unreachable → runner continues (mode=exploratory).

    We cannot fully run claude in this test environment, so we accept either
    success (the gate passed and claude was attempted) or any nonzero exit
    that is NOT the gate failure. The key is: the gate-failure stderr line
    must NOT appear.
    """
    env = os.environ.copy()
    env["REQUIRE_VERIFICATION"] = "0"
    env["VERIFY_URL"] = "http://127.0.0.1:8091/health"

    # Use a problem file that exists in data/.
    env.setdefault("PROBLEM_FILE", "data/example.md")

    completed = subprocess.run(
        ["bash", str(RUNNER)],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    # The gate-failure ERROR line must not appear in exploratory mode.
    assert (
        "ERROR: verification service not reachable" not in completed.stderr
    ), f"runner emitted the hard-gate failure in exploratory mode; stderr={completed.stderr[:500]!r}"
