import json
from pathlib import Path

PUBLIC_TEXT_FILES = [
    Path("README.md"),
    Path("CONTRIBUTING.md"),
    Path("CHANGELOG.md"),
    Path("SECURITY.md"),
    Path("action.yml"),
    Path("pyproject.toml"),
    *Path("docs").glob("*.md"),
    *Path(".github").glob("**/*.yml"),
    *Path(".github").glob("**/*.md"),
]


def test_open_source_maintenance_files_exist() -> None:
    for path in [
        Path("CONTRIBUTING.md"),
        Path("CHANGELOG.md"),
        Path("SECURITY.md"),
        Path("docs/release-checklist.md"),
        Path(".github/PULL_REQUEST_TEMPLATE.md"),
        Path(".github/ISSUE_TEMPLATE/bug_report.yml"),
        Path(".github/ISSUE_TEMPLATE/feature_request.yml"),
    ]:
        assert path.exists(), f"Missing maintenance file: {path}"


def test_service_health_demo_artifacts_exist_and_are_documented() -> None:
    for path in [
        Path("docs/demo-walkthrough.md"),
        Path("examples/service_health/service_health.py"),
        Path("examples/service_health/test_service_health.py"),
        Path("docs/sample-service-health-report.md"),
        Path("docs/sample-service-health-report.json"),
        Path("docs/sample-service-health-fixes.patch"),
    ]:
        assert path.exists(), f"Missing service health demo artifact: {path}"

    readme = Path("README.md").read_text(encoding="utf-8")
    project_brief = Path("docs/project-brief.md").read_text(encoding="utf-8")
    walkthrough = Path("docs/demo-walkthrough.md").read_text(encoding="utf-8")
    assert "10-Second Demo" in readme
    assert "docs/demo-walkthrough.md" in readme
    assert "examples/service_health" in readme
    assert "sample-service-health-report.md" in readme
    assert "examples/service_health" in project_brief
    for category in ["filesystem-boundary", "object-interface", "symbol-resolution"]:
        assert category in readme
        assert category in walkthrough


def test_service_health_sample_report_covers_realistic_failure_categories() -> None:
    report = json.loads(Path("docs/sample-service-health-report.json").read_text(encoding="utf-8"))
    categories = {diagnosis["category"] for diagnosis in report["diagnoses"]}
    targets = {proposal["target_file"] for proposal in report["patch_proposals"]}

    assert {"filesystem-boundary", "object-interface", "symbol-resolution"} <= categories
    assert targets == {"service_health.py"}
    assert len(report["fix_suggestions"]) == 3
    assert {suggestion["target_file"] for suggestion in report["fix_suggestions"]} == {"service_health.py"}


def test_public_text_avoids_application_specific_wording() -> None:
    forbidden = [
        "Track" + "03",
        "Agentic4" + "Systems",
        "Agent4" + "system",
        "agent4" + "system",
    ]

    for path in PUBLIC_TEXT_FILES:
        text = path.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in text, f"{term!r} found in {path}"


def test_project_metadata_exposes_public_repository_details() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    for expected in [
        'authors = [{ name = "Strangelight-Merser" }]',
        'Homepage = "https://github.com/Strangelight-Merser/agentic-testops"',
        '"Programming Language :: Python :: 3.10"',
        '"Programming Language :: Python :: 3.13"',
        '"Topic :: Software Development :: Testing"',
    ]:
        assert expected in text


def test_ci_runs_supported_python_matrix() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in text
    assert "python-version: ${{ matrix.python-version }}" in text


def test_github_actions_examples_use_current_node_runtime_actions() -> None:
    old_checkout = "actions/checkout@" + "v4"
    old_setup_python = "actions/setup-python@" + "v5"
    old_upload_artifact = "actions/upload-artifact@" + "v4"
    for path in [Path(".github/workflows/ci.yml"), Path("docs/github-action.md")]:
        text = path.read_text(encoding="utf-8")
        assert "actions/checkout@v6" in text
        assert "actions/setup-python@v6" in text
        assert "actions/upload-artifact@v7" in text
        assert old_checkout not in text
        assert old_setup_python not in text
        assert old_upload_artifact not in text
