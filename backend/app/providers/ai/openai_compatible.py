import json
import time
from decimal import Decimal
from typing import Any

import httpx

from app.db.models import AnalysisRun, ExternalContent, GenerationRun, Transcript
from app.modules.analysis.schemas import AnalysisL1Result, AnalysisL2Result
from app.modules.content_packages.schemas import GeneratedContentPackageResult
from app.modules.generation.schemas import GeneratedReviewResult, GeneratedScriptResult
from app.modules.prompts.registry import (
    ANALYSIS_SYSTEM_PROMPT,
    resolve_prompt_asset,
)
from app.providers.ai.base import AIProviderRequestError, AnalysisProviderResult
from app.providers.ai.generation import GenerationProviderResult

_GENERATION_SCHEMAS = {
    "script_draft": GeneratedScriptResult,
    "review_summary": GeneratedReviewResult,
    "content_package": GeneratedContentPackageResult,
}


def _trim(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else f"{value[:limit]}\n[truncated]"


def _extract_json(content: str) -> dict:
    normalized = content.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise AIProviderRequestError(
            "AI_OUTPUT_INVALID",
            "AI provider returned content that is not valid JSON.",
            retryable=True,
        ) from exc
    if not isinstance(parsed, dict):
        raise AIProviderRequestError(
            "AI_OUTPUT_INVALID",
            "AI provider returned JSON that is not an object.",
            retryable=True,
        )
    return parsed


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: int,
        json_mode: bool,
        temperature: Decimal,
        max_tokens: int,
        input_cost_per_million_usd: Decimal = Decimal("0"),
        output_cost_per_million_usd: Decimal = Decimal("0"),
        idempotency_key: str | None = None,
        disable_thinking: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.json_mode = json_mode
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.input_cost_per_million_usd = input_cost_per_million_usd
        self.output_cost_per_million_usd = output_cost_per_million_usd
        self.idempotency_key = idempotency_key
        self.disable_thinking = disable_thinking
        self.transport = transport

    async def analyze(
        self,
        *,
        run: AnalysisRun,
        content: ExternalContent,
        transcript: Transcript | None,
        metrics: dict | None = None,
    ) -> AnalysisProviderResult:
        evidence_refs = [f"content:{content.id}"]
        if transcript is not None:
            evidence_refs.append(f"transcript:{transcript.id}")
        schema = AnalysisL1Result if run.analysis_level == "l1" else AnalysisL2Result
        payload = {
            "analysis_level": run.analysis_level,
            "source": {
                "platform": content.platform,
                "content_type": content.content_type,
                "title": _trim(content.title, 4000),
                "body_text": _trim(content.body_text, 20000),
                "published_at": (
                    content.published_at.isoformat() if content.published_at is not None else None
                ),
                "duration_ms": content.duration_ms,
                "language": content.language,
                "author": content.author_snapshot,
                "metrics": metrics,
                "transcript": _trim(transcript.text, 30000) if transcript is not None else None,
            },
            "required_evidence_refs": evidence_refs,
        }
        system_prompt = ANALYSIS_SYSTEM_PROMPT.format(
            schema=json.dumps(schema.model_json_schema(), ensure_ascii=False)
        )
        response, latency_ms = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Analyze the following evidence and return valid JSON only:\n"
                        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
                    ),
                },
            ]
        )
        result = _extract_json(self._message_content(response))
        usage = response.get("usage") or {}
        input_tokens = self._integer(usage.get("prompt_tokens") or usage.get("input_tokens"))
        output_tokens = self._integer(
            usage.get("completion_tokens") or usage.get("output_tokens")
        )
        return AnalysisProviderResult(
            result=result,
            evidence_refs=evidence_refs,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._cost(input_tokens, output_tokens),
            latency_ms=latency_ms,
        )

    async def generate(self, *, run: GenerationRun) -> GenerationProviderResult:
        schema = _GENERATION_SCHEMAS.get(run.generation_type, GeneratedReviewResult)
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        evidence_json = json.dumps(run.evidence_refs)
        system_prompt = resolve_prompt_asset(run.generation_type).system_prompt
        system_prompt = (
            f"{system_prompt}\n"
            f"The JSON Schema to satisfy exactly: {schema_json}\n"
            f"The evidence_refs field must include all of: {evidence_json}."
        )
        response, latency_ms = await self._chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Generate the requested result as valid JSON only:\n"
                        f"{json.dumps(run.input_payload, ensure_ascii=False, default=str)}"
                    ),
                },
            ]
        )
        result = _extract_json(self._message_content(response))
        usage = response.get("usage") or {}
        input_tokens = self._integer(usage.get("prompt_tokens") or usage.get("input_tokens"))
        output_tokens = self._integer(
            usage.get("completion_tokens") or usage.get("output_tokens")
        )
        return GenerationProviderResult(
            result=result,
            evidence_refs=list(run.evidence_refs),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._cost(input_tokens, output_tokens),
            latency_ms=latency_ms,
        )

    async def list_models(self) -> tuple[list[str], int]:
        started = time.monotonic()
        response = await self._request("GET", "/models")
        latency_ms = round((time.monotonic() - started) * 1000)
        data = response.get("data")
        if not isinstance(data, list):
            raise AIProviderRequestError(
                "AI_RESPONSE_INVALID",
                "AI provider model-list response is invalid.",
                retryable=False,
            )
        models = sorted(
            {
                str(item["id"])
                for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
        )
        return models, latency_ms

    async def _chat(self, *, messages: list[dict[str, str]]) -> tuple[dict, int]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": float(self.temperature),
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.disable_thinking:
            # DeepSeek V4 defaults to thinking mode and counts reasoning tokens
            # toward max_tokens. Structured formatting tasks do not need
            # reasoning, so disable it to avoid truncation and slow calls.
            body["thinking"] = {"type": "disabled"}
        started = time.monotonic()
        response = await self._request("POST", "/chat/completions", json_body=body)
        latency_ms = round((time.monotonic() - started) * 1000)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AIProviderRequestError(
                "AI_RESPONSE_INVALID",
                "AI provider response does not contain a completion choice.",
                retryable=True,
            )
        if choices[0].get("finish_reason") == "length":
            raise AIProviderRequestError(
                "AI_OUTPUT_TRUNCATED",
                "AI provider output reached max_tokens before completing.",
                retryable=True,
            )
        return response, latency_ms

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
    ) -> dict:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.idempotency_key and method.upper() == "POST":
            headers["Idempotency-Key"] = self.idempotency_key
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.request(method, path, json=json_body)
        except httpx.TimeoutException as exc:
            raise AIProviderRequestError(
                "AI_PROVIDER_TIMEOUT",
                "AI provider request timed out.",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise AIProviderRequestError(
                "AI_PROVIDER_UNAVAILABLE",
                "AI provider could not be reached.",
                retryable=True,
            ) from exc
        if response.status_code in {401, 403}:
            raise AIProviderRequestError(
                "AI_AUTH_FAILED",
                "AI provider rejected the configured credentials.",
                retryable=False,
            )
        if response.status_code == 429:
            raise AIProviderRequestError(
                "AI_RATE_LIMITED",
                "AI provider rate limit was exceeded.",
                retryable=True,
            )
        if response.status_code >= 500:
            raise AIProviderRequestError(
                "AI_PROVIDER_UNAVAILABLE",
                "AI provider is temporarily unavailable.",
                retryable=True,
            )
        if response.status_code >= 400:
            raise AIProviderRequestError(
                "AI_REQUEST_REJECTED",
                f"AI provider rejected the request with status {response.status_code}.",
                retryable=False,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderRequestError(
                "AI_RESPONSE_INVALID",
                "AI provider returned a non-JSON response.",
                retryable=True,
            ) from exc
        if not isinstance(payload, dict):
            raise AIProviderRequestError(
                "AI_RESPONSE_INVALID",
                "AI provider returned an invalid JSON response.",
                retryable=True,
            )
        return payload

    @staticmethod
    def _message_content(response: dict) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderRequestError(
                "AI_RESPONSE_INVALID",
                "AI provider response is missing message content.",
                retryable=True,
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise AIProviderRequestError(
                "AI_RESPONSE_EMPTY",
                "AI provider returned empty message content.",
                retryable=True,
            )
        return content

    @staticmethod
    def _integer(value: object) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _cost(self, input_tokens: int | None, output_tokens: int | None) -> Decimal:
        return (
            Decimal(input_tokens or 0) * self.input_cost_per_million_usd
            + Decimal(output_tokens or 0) * self.output_cost_per_million_usd
        ) / Decimal(1_000_000)
