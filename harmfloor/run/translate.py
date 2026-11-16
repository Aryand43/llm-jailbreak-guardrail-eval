"""Back-translation of non-English responses before judging (multilingual experiment).

The guardrail always sees the original response: whether it misses harm in other languages is
what the experiment measures. The judge, however, should not be the weak link, so responses in
another language are translated to English first (as in the MultiJail paper, which translated
responses before evaluation). Translation can itself lose harmful detail; the human check covers
a sample per language.

Models often answer a non-English prompt in English. `needs_translation` skips those, using the
script for non-Latin languages and an English stop-word rate for Latin-script ones.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

# MultiJail language code -> NLLB-200 code
NLLB_CODES = {"zh": "zho_Hans", "it": "ita_Latn", "vi": "vie_Latn", "ar": "arb_Arab", "ko": "kor_Hang",
              "th": "tha_Thai", "bn": "ben_Beng", "sw": "swh_Latn", "jv": "jav_Latn"}

_SCRIPTS = {"zh": r"[一-鿿]", "ar": r"[؀-ۿ]", "ko": r"[가-힯ᄀ-ᇿ]",
            "th": r"[฀-๿]", "bn": r"[ঀ-৿]"}
_EN_STOPWORDS = frozenset("""the and to of a in is that it for you on with as are this be or not can
your have i an by from at if will but they their we what how which there would should about""".split())


def needs_translation(text: str, lang: str) -> bool:
    """True if `text` appears to be in `lang` rather than English."""
    if lang == "en" or not text.strip():
        return False
    if lang in _SCRIPTS:
        letters = re.findall(r"\w", text)
        native = re.findall(_SCRIPTS[lang], text)
        return bool(letters) and len(native) / len(letters) >= 0.2
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if not words:
        return True
    return sum(w in _EN_STOPWORDS for w in words) / len(words) < 0.15


def _segments(text: str, max_chars: int = 400) -> list[str]:
    """NLLB is trained on sentences: split on lines, then on sentence ends if a line is long."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if len(line) <= max_chars:
            out.append(line)
            continue
        out += [s for s in re.split(r"(?<=[.!?。！？])\s*", line) if s.strip()]
    return out


class Translator(Protocol):
    name: str

    def to_english(self, texts: list[str], lang: str) -> list[str]: ...

    def info(self) -> dict[str, Any]: ...


class NLLBTranslator:
    """facebook/nllb-200-distilled-600M via transformers on the GPU (installed with vLLM)."""

    def __init__(self, model: str = "facebook/nllb-200-distilled-600M", batch_size: int = 32):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.name = model
        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(model)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(model, torch_dtype=torch.float16).to("cuda").eval()
        self._batch = batch_size

    def to_english(self, texts: list[str], lang: str) -> list[str]:
        self._tok.src_lang = NLLB_CODES[lang]
        eng = self._tok.convert_tokens_to_ids("eng_Latn")
        results = []
        for text in texts:
            segs = _segments(text)
            done = []
            for i in range(0, len(segs), self._batch):
                batch = self._tok(segs[i:i + self._batch], return_tensors="pt", padding=True,
                                  truncation=True, max_length=512).to("cuda")
                with self._torch.no_grad():
                    out = self._model.generate(**batch, forced_bos_token_id=eng, max_new_tokens=512)
                done += self._tok.batch_decode(out, skip_special_tokens=True)
            results.append("\n".join(done))
        return results

    def info(self) -> dict[str, Any]:
        import transformers

        return {"translator": self.name, "transformers_version": transformers.__version__}


class FakeTranslator:
    """Marks text as translated without changing meaning; for tests and dry runs."""

    name = "fake-translator"

    def to_english(self, texts: list[str], lang: str) -> list[str]:
        return [f"[{lang}->en] {t}" for t in texts]

    def info(self) -> dict[str, Any]:
        return {"translator": self.name}


def make_translator(kind: str, model: str | None = None) -> Translator:
    if kind == "vllm":  # same switch as the model backends: real models on the GPU
        return NLLBTranslator(model or "facebook/nllb-200-distilled-600M")
    if kind == "fake":
        return FakeTranslator()
    raise ValueError(f"unknown translator backend {kind!r}")
