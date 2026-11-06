"""Model backends for the run stages.

VLLMBackend runs an open-weight model on a local GPU with vLLM (installed only on the GPU
machine). FakeBackend is deterministic and needs no model; it lets every stage be tested and
dry-run on a laptop. Both expose the same two calls the stages need:

    sample(conversations, ...)          -> n responses per conversation
    next_token_probs(conversations, ts) -> P(first generated token = t) for each t in ts
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Protocol

Message = dict[str, str]


@dataclass(frozen=True)
class Generation:
    text: str
    finish_reason: str | None


class Backend(Protocol):
    name: str

    def sample(self, conversations: list[list[Message]], *, n: int, temperature: float, top_p: float,
               max_tokens: int, seed: int | None) -> list[list[Generation]]: ...

    def next_token_probs(self, conversations: list[list[Message]], tokens: list[str]) -> list[dict[str, float]]: ...

    def info(self) -> dict[str, Any]: ...


class VLLMBackend:
    """One model, loaded once per process. Stages run in separate processes so each gets the GPU."""

    def __init__(self, model: str, **engine_kwargs: Any):
        import vllm  # GPU machine only: `uv pip install vllm`

        self.name = model
        self._version = vllm.__version__
        self._engine_kwargs = engine_kwargs
        self._llm = vllm.LLM(model=model, **engine_kwargs)

    def sample(self, conversations, *, n, temperature, top_p, max_tokens, seed):
        from vllm import SamplingParams

        params = SamplingParams(n=n, temperature=temperature, top_p=top_p, max_tokens=max_tokens, seed=seed)
        outs = self._llm.chat(conversations, params, use_tqdm=True)
        return [[Generation(o.text, o.finish_reason) for o in out.outputs] for out in outs]

    def next_token_probs(self, conversations, tokens):
        from vllm import SamplingParams

        params = SamplingParams(n=1, temperature=0.0, max_tokens=1, logprobs=20)
        outs = self._llm.chat(conversations, params, use_tqdm=True)
        result = []
        for out in outs:
            mass: dict[str, float] = {}
            for lp in out.outputs[0].logprobs[0].values():
                key = (lp.decoded_token or "").strip().lower()
                mass[key] = mass.get(key, 0.0) + math.exp(lp.logprob)
            result.append({t: mass.get(t, 0.0) for t in tokens})
        return result

    def info(self):
        return {"backend": "vllm", "vllm_version": self._version, "model": self.name, "engine": self._engine_kwargs}


def _unit(*parts: Any) -> float:
    """Deterministic pseudo-random number in [0, 1) from its arguments."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


class FakeBackend:
    """Deterministic stand-in. Responses, guard probabilities and judge verdicts are hash-derived,
    so a dry run exercises every stage and the analysis end to end without a model."""

    def __init__(self, name: str = "fake"):
        self.name = name

    def sample(self, conversations, *, n, temperature, top_p, max_tokens, seed):
        out = []
        for conv in conversations:
            key = conv[-1]["content"]
            if conv and conv[0]["role"] == "system" and "GRADER" in conv[0]["content"]:
                u = _unit(self.name, key)
                refused = int(u < 0.6)
                out.append([Generation(f"refused: {refused}\nconvincing: {1 + int(u * 5) % 5}\nspecific: "
                                       f"{1 + int(u * 7) % 5}", "stop")] * n)
            else:
                out.append([Generation(f"fake reply {i} to: {key[:40]}", "stop") for i in range(n)])
        return out

    def next_token_probs(self, conversations, tokens):
        res = []
        for conv in conversations:
            p = _unit(self.name, conv[-1]["content"])
            res.append({t: (p if t == "unsafe" else 1 - p if t == "safe" else 0.0) for t in tokens})
        return res

    def info(self):
        return {"backend": "fake", "model": self.name}


def make_backend(kind: str, model: str, engine_kwargs: dict[str, Any] | None = None) -> Backend:
    if kind == "vllm":
        return VLLMBackend(model, **(engine_kwargs or {}))
    if kind == "fake":
        return FakeBackend(model)
    raise ValueError(f"unknown backend {kind!r} (use vllm or fake)")
