"""Minimal OpenRouter client: chat completions with per-call usage and cost logging.

Every call appends one JSON line to the usage log (default runs/openrouter_usage.jsonl): model,
upstream provider, request id, tokens, cost in USD, latency, finish reason, and the error code on
failure. Prompts, completions and the API key are never written to the log, and provider error
bodies (which can echo the prompt) are reduced to status + error code.

The key comes from OPENROUTER_API_KEY, read from the environment or from .env (gitignored).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://openrouter.ai/api/v1"
ROOT = Path(__file__).resolve().parents[1]
USAGE_LOG = ROOT / "runs" / "openrouter_usage.jsonl"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class OpenRouterError(RuntimeError):
    def __init__(self, status: int | None, code: str | int | None):
        super().__init__(f"OpenRouter request failed (status={status}, code={code})")
        self.status, self.code = status, code


@dataclass(frozen=True)
class Completion:
    text: str
    finish_reason: str | None
    model: str
    provider: str | None
    request_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    latency_s: float


def api_key_from_env(env_file: Path = ROOT / ".env") -> str:
    if key := os.environ.get("OPENROUTER_API_KEY"):
        return key
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "OPENROUTER_API_KEY" and value.strip():
                return value.strip().strip("'\"")
    raise RuntimeError("OPENROUTER_API_KEY is not set (environment or .env)")


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        log_path: Path = USAGE_LOG,
        timeout: float = 120.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._key = api_key
        self._http = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._log_path = log_path
        self._max_retries = max_retries
        self._sleep = sleep

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 512,
        seed: int | None = None,
        provider_order: list[str] | None = None,
    ) -> Completion:
        """One completion. provider_order pins the upstream host (no fallbacks) for final runs."""
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        if seed is not None:
            body["seed"] = seed
        if provider_order:
            body["provider"] = {"order": provider_order, "allow_fallbacks": False}
        key = self._key or api_key_from_env()
        headers = {"Authorization": f"Bearer {key}"}

        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            status, code = None, None
            try:
                r = self._http.post("/chat/completions", json=body, headers=headers)
                status = r.status_code
                data = r.json() if r.content else {}
                if r.status_code == 200 and "error" not in data:
                    c = self._parse(data, model, time.monotonic() - start)
                    self._log({"status": 200, **asdict(c), "text": None})
                    return c
                code = (data.get("error") or {}).get("code") if isinstance(data, dict) else None
            except (httpx.TransportError, json.JSONDecodeError) as e:
                code = type(e).__name__
            self._log({"status": status, "model": model, "error": code, "attempt": attempt,
                       "latency_s": round(time.monotonic() - start, 3)})
            if status is not None and status not in RETRY_STATUS:
                break
            if attempt < self._max_retries:
                self._sleep(2.0**attempt)
        raise OpenRouterError(status, code)

    def list_models(self) -> list[dict[str, Any]]:
        """Public model catalogue (no key needed)."""
        r = self._http.get("/models")
        if r.status_code != 200:
            raise OpenRouterError(r.status_code, None)
        return r.json()["data"]

    @staticmethod
    def _parse(data: dict[str, Any], model: str, latency: float) -> Completion:
        choice = data["choices"][0]
        usage = data.get("usage") or {}
        return Completion(
            text=choice["message"].get("content") or "",
            finish_reason=choice.get("finish_reason"),
            model=data.get("model", model),
            provider=data.get("provider"),
            request_id=data.get("id"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            cost_usd=usage.get("cost"),
            latency_s=round(latency, 3),
        )

    def _log(self, record: dict[str, Any]) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(), **{k: v for k, v in record.items() if k != "text"}}
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


@dataclass(frozen=True)
class ModelCheck:
    slug: str
    available: bool
    temperature: bool = False
    top_p: bool = False
    seed: bool = False
    prompt_usd_per_m: float | None = None
    completion_usd_per_m: float | None = None


def check_models(catalogue: list[dict[str, Any]], slugs: Iterable[str]) -> list[ModelCheck]:
    """Is each slug served, and does it accept the decoding parameters the experiment fixes?"""
    by_id = {m["id"]: m for m in catalogue}
    out = []
    for slug in slugs:
        m = by_id.get(slug)
        if m is None:
            out.append(ModelCheck(slug, available=False))
            continue
        params = set(m.get("supported_parameters") or [])
        price = m.get("pricing") or {}
        per_m = lambda k: round(float(price[k]) * 1e6, 4) if k in price else None
        out.append(ModelCheck(slug, True, "temperature" in params, "top_p" in params, "seed" in params,
                              per_m("prompt"), per_m("completion")))
    return out
