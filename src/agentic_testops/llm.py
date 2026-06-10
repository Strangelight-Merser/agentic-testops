"""Optional LLM explanation layer over the deterministic audit report.

Design constraints:

- The deterministic pipeline never depends on this module's success. No API
  key, a network error, or an unparseable model response all degrade to the
  plain report instead of failing the audit.
- No third-party dependency: the Anthropic Messages API is called with the
  standard library. The HTTP transport is injectable so tests never touch the
  network.
- The model receives only failure evidence already present in the report
  (node IDs, headlines, evidence lines, patch targets), not project source.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .models import AuditReport, LlmExplanation

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_TIMEOUT = 60
MAX_TOKENS = 2000

Transport = Callable[[dict[str, Any], str, int], dict[str, Any]]

_SYSTEM_PROMPT = (
    "You are a senior Python engineer reviewing a structured pytest failure report. "
    "For every failure, explain the most likely root cause in one or two sentences and "
    "outline a concrete fix in one sentence. Ground every claim in the provided evidence; "
    "if the evidence is insufficient, say so instead of guessing. "
    'Respond with a JSON array only: [{"nodeid": str, "explanation": str, "fix_outline": str}].'
)


def explain_failures(
    report: AuditReport,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
    transport: Transport | None = None,
) -> list[LlmExplanation]:
    """Return LLM explanations for the report's failures.

    Raises ``MissingApiKeyError`` when no key is available so the CLI can
    print a clear skip notice; all other failures raise ``LlmRequestError``.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise MissingApiKeyError("ANTHROPIC_API_KEY is not set")
    if not report.diagnoses:
        return []

    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _render_prompt(report)}],
    }
    send = transport if transport is not None else _http_transport
    try:
        response = send(payload, api_key, timeout)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LlmRequestError(f"LLM request failed: {exc}") from exc
    return _parse_response(response, model)


class MissingApiKeyError(RuntimeError):
    pass


class LlmRequestError(RuntimeError):
    pass


def _render_prompt(report: AuditReport) -> str:
    failures = []
    for diagnosis in report.diagnoses:
        failure = diagnosis.failure
        proposal = next(
            (item for item in report.patch_proposals if item.failure_nodeid == failure.nodeid),
            None,
        )
        failures.append(
            {
                "nodeid": failure.nodeid,
                "headline": failure.headline,
                "error_type": failure.error_type,
                "deterministic_category": diagnosis.category,
                "evidence": diagnosis.evidence[:6],
                "detail": failure.detail[:1500],
                "patch_target": (
                    f"{proposal.target_file}:{proposal.target_line}"
                    if proposal and proposal.target_file
                    else None
                ),
            }
        )
    return json.dumps(
        {"project": report.display_project_path, "failures": failures},
        ensure_ascii=False,
        indent=2,
    )


def _http_transport(payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result: dict[str, Any] = json.load(response)
        return result


def _parse_response(response: dict[str, Any], model: str) -> list[LlmExplanation]:
    text = "".join(
        block.get("text", "")
        for block in response.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
    if not text:
        raise LlmRequestError("LLM response contained no text content")

    items = _extract_json_array(text)
    if items is None:
        # The model ignored the JSON instruction; keep its prose rather than dropping it.
        return [LlmExplanation(failure_nodeid="(entire report)", explanation=text, model=model)]

    explanations = []
    for item in items:
        if not isinstance(item, dict):
            continue
        explanation = str(item.get("explanation", "")).strip()
        fix_outline = str(item.get("fix_outline", "")).strip()
        combined = " ".join(part for part in [explanation, f"Fix: {fix_outline}" if fix_outline else ""] if part)
        if not combined:
            continue
        explanations.append(
            LlmExplanation(
                failure_nodeid=str(item.get("nodeid", "unknown")),
                explanation=combined,
                model=model,
            )
        )
    if not explanations:
        raise LlmRequestError("LLM response JSON contained no usable explanations")
    return explanations


def _extract_json_array(text: str) -> list[Any] | None:
    candidate = text
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else candidate
    start = candidate.find("[")
    end = candidate.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None
