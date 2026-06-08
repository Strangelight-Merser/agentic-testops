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
        '"Programming Language :: Python :: 3.9"',
        '"Programming Language :: Python :: 3.12"',
        '"Topic :: Software Development :: Testing"',
    ]:
        assert expected in text


def test_ci_runs_supported_python_matrix() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert 'python-version: ["3.9", "3.10", "3.11", "3.12"]' in text
    assert "python-version: ${{ matrix.python-version }}" in text
