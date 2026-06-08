from agentic_testops.runner import run_pytest


def test_run_pytest_returns_timeout_result(tmp_path) -> None:
    (tmp_path / "test_slow.py").write_text(
        "import time\n\n\ndef test_slow():\n    time.sleep(5)\n",
        encoding="utf-8",
    )

    run = run_pytest(tmp_path, timeout=1)

    assert run.timed_out is True
    assert run.returncode == 124
    assert "timed out" in run.stderr


def test_run_pytest_captures_junit_xml_without_leaking_temp_path(tmp_path) -> None:
    (tmp_path / "test_fail.py").write_text(
        "def test_fail():\n    assert False\n",
        encoding="utf-8",
    )

    run = run_pytest(tmp_path)

    assert run.returncode == 1
    assert "<testsuite" in run.junit_xml
    assert "generated xml file:" not in run.stdout
