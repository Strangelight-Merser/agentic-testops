"""Optional LLM explanation layer over the deterministic audit report.

Design constraints:

- The deterministic pipeline never depends on this module's success. No API
  key, a network error, or an unparseable model response all degrade to the
  plain report instead of failing the audit.
- Provider-neutral: the Anthropic Messages API and any OpenAI-compatible
  Chat Completions endpoint (OpenAI, DeepSeek, Qwen/DashScope, Zhipu,
  Moonshot, local Ollama or vLLM, ...) are both supported, selected with
  ``--llm-provider`` and ``--llm-base-url``.
- No third-party dependency: requests are sent with the standard library. The
  HTTP transport is injectable so tests never touch the network.
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

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"
PROVIDER_AUTO = "auto"
PROVIDERS = (PROVIDER_AUTO, PROVIDER_ANTHROPIC, PROVIDER_OPENAI)

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_API_VERSION = "2023-06-01"
OPENAI_BASE_URL = "https://api.openai.com/v1"

DEFAULT_MODELS = {
    PROVIDER_ANTHROPIC: "claude-haiku-4-5",
    PROVIDER_OPENAI: "gpt-4o-mini",
}
API_KEY_ENV_VARS = {
    PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY",
    PROVIDER_OPENAI: "OPENAI_API_KEY",
}
DEFAULT_TIMEOUT = 60
MAX_TOKENS = 2000

Transport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]

_SYSTEM_PROMPT = (
    "You are a senior Python engineer reviewing a structured pytest failure report. "
    "For every failure, explain the most likely root cause in one or two sentences and "
    "outline a concrete fix in one sentence. Ground every claim in the provided evidence; "
    "if the evidence is insufficient, say so instead of guessing. "
    'Respond with a JSON array only: [{"nodeid": str, "explanation": str, "fix_outline": str}].'
)


class MissingApiKeyError(RuntimeError):
    pass


class LlmRequestError(RuntimeError):
    pass


def explain_failures(
    report: AuditReport,
    provider: str = PROVIDER_AUTO,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    transport: Transport | None = None,
) -> list[LlmExplanation]:
    """Return LLM explanations for the report's failures.

    Raises ``MissingApiKeyError`` when no key is available so the CLI can
    print a clear skip notice; all other failures raise ``LlmRequestError``.
    """
    provider, api_key = _resolve_provider(provider, api_key, base_url)
    model = model or DEFAULT_MODELS[provider]
    if not report.diagnoses:
        return []

    prompt = _render_prompt(report)
    if provider == PROVIDER_ANTHROPIC:
        url, payload, headers = _anthropic_request(prompt, model, api_key, base_url)
    else:
        url, payload, headers = _openai_request(prompt, model, api_key, base_url)

    send = transport if transport is not None else _http_transport
    try:
        response = send(url, payload, headers, timeout)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LlmRequestError(f"LLM request failed: {exc}") from exc

    text = (
        _anthropic_response_text(response)
        if provider == PROVIDER_ANTHROPIC
        else _openai_response_text(response)
    )
    return _parse_explanations(text, model)


def _resolve_provider(provider: str, api_key: str | None, base_url: str | None) -> tuple[str, str]:
    if provider not in PROVIDERS:
        raise LlmRequestError(f"Unknown LLM provider: {provider} (expected one of {', '.join(PROVIDERS)})")

    if provider == PROVIDER_AUTO:
        if api_key:
            # An explicit key without a provider implies the OpenAI-compatible
            # protocol, which is what custom --llm-base-url endpoints speak.
            return PROVIDER_OPENAI, api_key
        if os.environ.get("ANTHROPIC_API_KEY") and not base_url:
            return PROVIDER_ANTHROPIC, os.environ["ANTHROPIC_API_KEY"]
        if os.environ.get("OPENAI_API_KEY"):
            return PROVIDER_OPENAI, os.environ["OPENAI_API_KEY"]
        if base_url:
            # Local endpoints such as Ollama accept any placeholder key.
            return PROVIDER_OPENAI, os.environ.get("LLM_API_KEY", "not-needed")
        raise MissingApiKeyError("Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set")

    resolved = api_key or os.environ.get(API_KEY_ENV_VARS[provider], "")
    if not resolved:
        if provider == PROVIDER_OPENAI and base_url:
            return provider, os.environ.get("LLM_API_KEY", "not-needed")
        raise MissingApiKeyError(f"{API_KEY_ENV_VARS[provider]} is not set")
    return provider, resolved


def _anthropic_request(
    prompt: str, model: str, api_key: str, base_url: str | None
) -> tuple[str, dict[str, Any], dict[str, str]]:
    url = f"{(base_url or ANTHROPIC_BASE_URL).rstrip('/')}/v1/messages"
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
    }
    return url, payload, headers


def _openai_request(
    prompt: str, model: str, api_key: str, base_url: str | None
) -> tuple[str, dict[str, Any], dict[str, str]]:
    url = f"{(base_url or OPENAI_BASE_URL).rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}",
    }
    return url, payload, headers


def _anthropic_response_text(response: dict[str, Any]) -> str:
    return "".join(
        block.get("text", "")
        for block in response.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def _openai_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "") if isinstance(message, dict) else ""
    return str(content).strip()


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


def _http_transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result: dict[str, Any] = json.load(response)
        return result


def _parse_explanations(text: str, model: str) -> list[LlmExplanation]:
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
