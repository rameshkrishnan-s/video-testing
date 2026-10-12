"""Kokoro-82M (ONNX) with per-phoneme durations and phoneme -> word alignment.

The stock kokoro-v1.0.onnx only outputs audio. The StyleTTS2 duration predictor
inside it computes integer frame counts per input token
(`/encoder/Cast_output_0`, i.e. round(sum(sigmoid(proj))/speed) clipped to >=1).
We expose that tensor as an extra graph output called `duration` in a patched copy
of the model, run it, and verify the unit: one duration frame == 600 samples at
24 kHz (25 ms), and sum(duration) * 600 == len(audio) exactly.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import numpy as np

SAMPLE_RATE = 24000
SAMPLES_PER_FRAME = 600  # verified: sum(duration) * 600 == len(audio)
DURATION_TENSOR = "/encoder/Cast_output_0"

# characters of the phoneme string that are punctuation (pause carriers), not speech
PUNCT = set(".,!?:;…—-\"“”()")


def patch_model(src: str, dst: str) -> None:
    """Save a copy of the Kokoro ONNX model with the duration tensor as an output."""
    import onnx
    from onnx import TensorProto, helper

    model = onnx.load(src)
    g = model.graph
    produced = {o for n in g.node for o in n.output}
    if DURATION_TENSOR not in produced:
        raise RuntimeError(f"{DURATION_TENSOR} not found in graph; model layout differs")
    g.node.append(helper.make_node("Identity", [DURATION_TENSOR], ["duration"], name="expose_duration"))
    g.output.append(helper.make_tensor_value_info("duration", TensorProto.INT64, ["batch", "sequence_length"]))
    onnx.save(model, dst)


@dataclass
class Word:
    text: str
    start: float
    end: float
    phonemes: str = ""
    # raw (un-adjusted) predicted extents
    raw_start: float = 0.0
    raw_end: float = 0.0


@dataclass
class Synth:
    audio: np.ndarray  # float32 @ 24 kHz
    phonemes: str
    words: list[Word]
    char_spans: list[tuple[str, float, float]] = field(default_factory=list)


class TimedKokoro:
    def __init__(self, models_dir: str, voice: str = "af_heart", lang: str = "en-us",
                 phoneme_fixes: dict[str, str] | None = None):
        from kokoro_onnx import Kokoro

        src = os.path.join(models_dir, "kokoro-v1.0.onnx")
        dst = os.path.join(models_dir, "kokoro-v1.0-dur.onnx")
        if not os.path.exists(dst):
            patch_model(src, dst)
        self.k = Kokoro(dst, os.path.join(models_dir, "voices-v1.0.bin"))
        assert self.k.has_timings
        self.voice = self.k.get_voice_style(voice)
        self.lang = lang
        self.fixes = phoneme_fixes or {}

    def phonemize(self, text: str) -> str:
        ph = self.k.tokenizer.phonemize(text, self.lang)
        ph = " ".join(ph.split())
        for a, b in self.fixes.items():
            ph = ph.replace(a, b)
        return ph

    def synth(self, text: str, speed: float) -> Synth:
        ph = self.phonemize(text)
        tokens = self.k.tokenizer.tokenize(ph)
        assert len(tokens) == len(ph), "phoneme string contains characters outside the vocab"
        audio, dur = self.k._infer(tokens, self.k._style_for(self.voice, len(tokens)), speed)
        dur = np.asarray(dur).ravel().astype(np.int64)
        assert len(dur) == len(ph) + 2, (len(dur), len(ph))
        assert int(dur.sum()) * SAMPLES_PER_FRAME == len(audio), "duration unit check failed"
        # boundaries in seconds; index 0 is the leading pad token
        edges = np.concatenate([[0], np.cumsum(dur)]) * SAMPLES_PER_FRAME / SAMPLE_RATE
        spans = [(ph[i], float(edges[i + 1]), float(edges[i + 2])) for i in range(len(ph))]
        words = align_words(text, ph, spans)
        return Synth(audio.astype(np.float32), ph, words, spans)


def align_words(text: str, ph: str, spans: list[tuple[str, float, float]]) -> list[Word]:
    """Map phoneme-token spans back to the script's whitespace-separated words."""
    script_words = text.split()
    # hyphenated words ("so-called") may phonemize to one group or to several
    parts = [max(1, len([p for p in re.split(r"[-–—]", w) if re.search(r"[A-Za-z0-9]", p)])) for w in script_words]
    groups: list[tuple[int, int]] = []  # [a, b) char ranges of each phoneme group
    i = 0
    for g in ph.split(" "):
        groups.append((i, i + len(g)))
        i += len(g) + 1

    def solve(wi: int, gi: int) -> list[int] | None:
        if wi == len(script_words):
            return [] if gi == len(groups) else None
        for n in range(1, parts[wi] + 1):
            rest = solve(wi + 1, gi + n)
            if rest is not None:
                return [n] + rest
        return None

    expected = solve(0, 0)
    if expected is None:
        raise RuntimeError(f"word/phoneme group mismatch: {len(script_words)} words vs {len(groups)} groups\n{text}\n{ph}")
    words: list[Word] = []
    gi = 0
    for w, n in zip(script_words, expected):
        a, b = groups[gi][0], groups[gi + n - 1][1]
        gi += n
        idx = [j for j in range(a, b) if ph[j] not in PUNCT and ph[j] != " "]
        if not idx:
            raise RuntimeError(f"word {w!r} has no speech phonemes")
        s, e = spans[idx[0]][1], spans[idx[-1]][2]
        words.append(Word(w, s, e, ph[a:b], s, e))
    return words
