from pathlib import Path


def test_action_metadata_exposes_core_inputs() -> None:
    text = Path("action.yml").read_text(encoding="utf-8")

    for expected in [
        "using: composite",
        "project:",
        "json-output:",
        "fix-output:",
        "rerun-failures:",
        "suggest-fixes:",
        "apply-and-verify:",
        "fail-on-test-failure:",
        "job-summary:",
        "summary-written:",
        "GITHUB_STEP_SUMMARY",
        "agentic-testops audit",
    ]:
        assert expected in text
