"""Flakiness detection for failing pytest node IDs.

A test that failed in the initial run is rerun several times in isolation.
If it passes at least once, the failure is unstable ("flaky"); if it fails in
every attempt, the failure is reproducible ("consistent"). This distinction
matters for repair automation: consistent failures are safe targets for patch
proposals, while flaky failures usually point at test order, timing, or shared
state instead of the production code the traceback blames.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .models import Failure, FlakeResult, TestRun
from .parser import parse_failures
from .runner import run_pytest

VERDICT_FLAKY = "flaky"
VERDICT_CONSISTENT = "consistent"

RunnerFunc = Callable[..., TestRun]


def detect_flaky_failures(
    project_path: Path,
    failures: list[Failure],
    attempts: int = 3,
    extra_args: list[str] | None = None,
    timeout: int = 120,
    runner: RunnerFunc | None = None,
) -> list[FlakeResult]:
    """Rerun every failing node ID ``attempts`` times and classify stability."""
    if runner is None:
        runner = run_pytest
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if not failures:
        return []

    nodeids = [failure.nodeid for failure in failures]
    failed_counts = {nodeid: 0 for nodeid in nodeids}
    completed_attempts = 0

    for _ in range(attempts):
        rerun_args = [*(extra_args or []), *nodeids]
        run = runner(project_path, extra_args=rerun_args, timeout=timeout)
        if run.timed_out:
            # A timed-out attempt gives no per-test signal; count every
            # tracked node as failed so a hung test is never reported flaky.
            for nodeid in nodeids:
                failed_counts[nodeid] += 1
            completed_attempts += 1
            continue
        rerun_failures = parse_failures(run)
        rerun_nodeids = [failure.nodeid for failure in rerun_failures]
        for nodeid in nodeids:
            if any(_nodeids_match(nodeid, rerun_nodeid) for rerun_nodeid in rerun_nodeids):
                failed_counts[nodeid] += 1
        completed_attempts += 1

    results = []
    for nodeid in nodeids:
        failed = failed_counts[nodeid]
        verdict = VERDICT_CONSISTENT if failed == completed_attempts else VERDICT_FLAKY
        results.append(
            FlakeResult(
                nodeid=nodeid,
                attempts=completed_attempts,
                failed_attempts=failed,
                verdict=verdict,
            )
        )
    return results


def _nodeids_match(left: str, right: str) -> bool:
    """Exact match, or one ID is a path-suffix of the other.

    Different parse sources may render the same test as
    ``tests/test_app.py::test_x`` or ``test_app.py::test_x``; treating a
    full ``::``-boundary suffix as equal keeps attempts comparable without
    conflating same-named tests in different files.
    """
    if left == right:
        return True
    longer, shorter = (left, right) if len(left) >= len(right) else (right, left)
    return longer.endswith(f"/{shorter}") or longer.endswith(f"::{shorter}")
