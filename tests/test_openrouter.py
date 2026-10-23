import json

import httpx
import pytest

from harmfloor import openrouter as orc

OK = {
    "id": "gen-123",
    "model": "meta-llama/llama-3.1-8b-instruct",
    "provider": "DeepInfra",
    "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "cost": 0.0000021},
}


def make_client(tmp_path, responses, sleeps=None):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        status, body = responses[min(len(calls), len(responses)) - 1]
        return httpx.Response(status, json=body)

    client = orc.OpenRouterClient(
        api_key="sk-secret", log_path=tmp_path / "usage.jsonl",
        transport=httpx.MockTransport(handler), sleep=(sleeps.append if sleeps is not None else lambda s: None),
    )
    return client, calls


def log_lines(tmp_path):
    return [json.loads(l) for l in (tmp_path / "usage.jsonl").read_text().splitlines()]


def test_chat_returns_completion_and_logs_usage(tmp_path):
    client, calls = make_client(tmp_path, [(200, OK)])
    c = client.chat("meta-llama/llama-3.1-8b-instruct", [{"role": "user", "content": "hi"}], seed=42)
    assert c.text == "hello" and c.cost_usd == pytest.approx(2.1e-6) and c.provider == "DeepInfra"
    body = json.loads(calls[0].content)
    assert body["usage"] == {"include": True} and body["seed"] == 42 and body["temperature"] == 0.7
    assert calls[0].headers["Authorization"] == "Bearer sk-secret"
    (rec,) = log_lines(tmp_path)
    assert rec["prompt_tokens"] == 12 and rec["completion_tokens"] == 3 and rec["request_id"] == "gen-123"
    raw = (tmp_path / "usage.jsonl").read_text()
    assert "sk-secret" not in raw and "hello" not in raw and "hi" not in raw  # no key, prompt or completion


def test_provider_pinning(tmp_path):
    client, calls = make_client(tmp_path, [(200, OK)])
    client.chat("m", [{"role": "user", "content": "x"}], provider_order=["DeepInfra"])
    assert json.loads(calls[0].content)["provider"] == {"order": ["DeepInfra"], "allow_fallbacks": False}


def test_retries_rate_limits_then_succeeds(tmp_path):
    sleeps = []
    client, calls = make_client(tmp_path, [(429, {"error": {"code": 429}}), (502, {}), (200, OK)], sleeps)
    assert client.chat("m", [{"role": "user", "content": "x"}]).text == "hello"
    assert len(calls) == 3 and sleeps == [1.0, 2.0]
    assert [r["status"] for r in log_lines(tmp_path)] == [429, 502, 200]


def test_client_errors_are_not_retried_and_hide_the_body(tmp_path):
    client, calls = make_client(tmp_path, [(400, {"error": {"code": 400, "message": "echoes the prompt: x"}})])
    with pytest.raises(orc.OpenRouterError) as e:
        client.chat("m", [{"role": "user", "content": "x"}])
    assert len(calls) == 1 and "echoes" not in str(e.value) and e.value.status == 400


def test_error_inside_a_200_is_an_error(tmp_path):
    client, _ = make_client(tmp_path, [(200, {"error": {"code": 502}})] * 5)
    with pytest.raises(orc.OpenRouterError):
        client.chat("m", [{"role": "user", "content": "x"}])


def test_api_key_from_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nOPENROUTER_API_KEY='sk-from-file'\n")
    assert orc.api_key_from_env(env) == "sk-from-file"
    with pytest.raises(RuntimeError):
        orc.api_key_from_env(tmp_path / "missing")


def test_check_models():
    catalogue = [{"id": "a/served", "supported_parameters": ["temperature", "top_p"],
                  "pricing": {"prompt": "0.0000001", "completion": "0.0000004"}}]
    served, missing = orc.check_models(catalogue, ["a/served", "b/missing"])
    assert served.available and served.temperature and not served.seed
    assert served.prompt_usd_per_m == pytest.approx(0.1) and served.completion_usd_per_m == pytest.approx(0.4)
    assert not missing.available
