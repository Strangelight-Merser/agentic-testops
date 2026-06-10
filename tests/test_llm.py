import json
from dataclasses import replace
from pathlib import Path

import pytest

from agentic_testops import cli
from agentic_testops.llm import (
    LlmRequestError,
    MissingApiKeyError,
    explain_failures,
)
from agentic_testops.models import AuditReport, Diagnosis, Failure, LlmExplanation, TestRun


def _report() -> AuditReport:
    failure = Failure(
        nodeid="tests/test_app.py::test_case",
        headline="AssertionError: assert 'a' == 'b'",
        error_type="AssertionError",
        detail="E   AssertionError: assert 'a' == 'b'",
    )
    diagnosis = Diagnosis(
        failure=failure,
        category="behavioral-regression",
        confidence="medium",
        summary="Assertion failed.",
        evidence=["E   AssertionError: assert 'a' == 'b'"],
    )
    return AuditReport(
        project_path=Path("demo"),
        run=TestRun(
            command=["python", "-m", "pytest"],
            cwd=Path("."),
            returncode=1,
            stdout="FAILED tests/test_app.py::test_case - AssertionError\n",
            stderr="",
            duration_seconds=0.1,
        ),
        failures=[failure],
        diagnoses=[diagnosis],
    )


_EXPLANATION_JSON = json.dumps(
    [
        {
            "nodeid": "tests/test_app.py::test_case",
            "explanation": "The implementation returns 'a' but the test expects 'b'.",
            "fix_outline": "Update the return value computation.",
        }
    ]
)


def _anthropic_response(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _openai_response(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def test_anthropic_provider_request_and_parse() -> None:
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured.update(url=url, payload=payload, headers=headers)
        return _anthropic_response(_EXPLANATION_JSON)

    explanations = explain_failures(
        _report(), provider="anthropic", api_key="key-123", transport=fake_transport
    )

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "key-123"
    assert "tests/test_app.py::test_case" in captured["payload"]["messages"][0]["content"]
    assert explanations[0].failure_nodeid == "tests/test_app.py::test_case"
    assert explanations[0].explanation.endswith("Fix: Update the return value computation.")
    assert explanations[0].model == "claude-haiku-4-5"


def test_openai_provider_request_and_parse() -> None:
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured.update(url=url, payload=payload, headers=headers)
        return _openai_response(_EXPLANATION_JSON)

    explanations = explain_failures(
        _report(), provider="openai", api_key="sk-test", model="deepseek-chat", transport=fake_transport
    )

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer sk-test"
    assert captured["payload"]["model"] == "deepseek-chat"
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert explanations[0].model == "deepseek-chat"


def test_custom_base_url_targets_compatible_endpoint() -> None:
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured["url"] = url
        return _openai_response(_EXPLANATION_JSON)

    explain_failures(
        _report(),
        provider="openai",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        transport=fake_transport,
    )

    assert captured["url"] == "https://api.deepseek.com/chat/completions"


def test_local_endpoint_needs_no_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured["url"] = url
        return _openai_response(_EXPLANATION_JSON)

    explanations = explain_failures(
        _report(), base_url="http://localhost:11434/v1", transport=fake_transport
    )

    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert explanations


def test_auto_provider_prefers_anthropic_env(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
    monkeypatch.setenv("OPENAI_API_KEY", "open-key")
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured["headers"] = headers
        return _anthropic_response(_EXPLANATION_JSON)

    explain_failures(_report(), transport=fake_transport)

    assert captured["headers"]["x-api-key"] == "anth-key"


def test_auto_provider_falls_back_to_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "open-key")
    captured = {}

    def fake_transport(url, payload, headers, timeout):
        captured["headers"] = headers
        return _openai_response(_EXPLANATION_JSON)

    explain_failures(_report(), transport=fake_transport)

    assert captured["headers"]["authorization"] == "Bearer open-key"


def test_missing_api_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(MissingApiKeyError):
        explain_failures(_report())


def test_unknown_provider_rejected() -> None:
    with pytest.raises(LlmRequestError):
        explain_failures(_report(), provider="gemini", api_key="key")


def test_prose_response_is_kept() -> None:
    def fake_transport(url, payload, headers, timeout):
        return _openai_response("The failure looks like a simple value mismatch.")

    explanations = explain_failures(_report(), provider="openai", api_key="key", transport=fake_transport)

    assert explanations[0].failure_nodeid == "(entire report)"
    assert "value mismatch" in explanations[0].explanation


def test_empty_response_rejected() -> None:
    def fake_transport(url, payload, headers, timeout):
        return {"choices": []}

    with pytest.raises(LlmRequestError):
        explain_failures(_report(), provider="openai", api_key="key", transport=fake_transport)


def test_fenced_json_response_parsed() -> None:
    fenced = '```json\n[{"nodeid": "n", "explanation": "x", "fix_outline": ""}]\n```'

    def fake_transport(url, payload, headers, timeout):
        return _anthropic_response(fenced)

    explanations = explain_failures(_report(), provider="anthropic", api_key="key", transport=fake_transport)

    assert explanations[0].failure_nodeid == "n"
    assert explanations[0].explanation == "x"


def test_json_report_includes_llm_explanations() -> None:
    report = replace(
        _report(),
        llm_explanations=[LlmExplanation(failure_nodeid="n", explanation="e", model="m")],
    )

    payload = report.to_dict()

    assert payload["llm_explanations"] == [{"failure_nodeid": "n", "explanation": "e", "model": "m"}]


def _fake_failing_run(project_path: Path, extra_args=None, timeout=120) -> TestRun:
    return TestRun(
        command=["python", "-m", "pytest"],
        cwd=project_path,
        returncode=1,
        stdout="FAILED tests/test_app.py::test_case - AssertionError: assert False\n",
        stderr="",
        duration_seconds=0.1,
    )


def test_cli_skips_llm_analysis_without_api_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "run_pytest", _fake_failing_run)

    exit_code = cli.main(["audit", str(tmp_path), "--llm-explain", "-o", str(tmp_path / "report.md")])

    assert exit_code == 1
    assert "LLM analysis skipped" in capsys.readouterr().out
    assert "## LLM Analysis" not in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_cli_renders_llm_analysis(monkeypatch, tmp_path) -> None:
    def fake_explain(report, provider="auto", model=None, base_url=None):
        assert provider == "openai"
        assert base_url == "https://api.deepseek.com"
        resolved = model or "deepseek-chat"
        return [LlmExplanation(failure_nodeid="tests/test_app.py::test_case", explanation="Why.", model=resolved)]

    monkeypatch.setattr(cli, "run_pytest", _fake_failing_run)
    monkeypatch.setattr(cli, "explain_failures", fake_explain)

    exit_code = cli.main(
        [
            "audit",
            str(tmp_path),
            "--llm-explain",
            "--llm-provider",
            "openai",
            "--llm-base-url",
            "https://api.deepseek.com",
            "-o",
            str(tmp_path / "report.md"),
            "--json-output",
            str(tmp_path / "report.json"),
        ]
    )

    assert exit_code == 1
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## LLM Analysis" in report_text
    assert "Why." in report_text
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["llm_explanations"][0]["model"] == "deepseek-chat"
