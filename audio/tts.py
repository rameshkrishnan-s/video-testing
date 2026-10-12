#!/usr/bin/env python3
"""Voiceover pipeline for the 60 s short: Kokoro-82M (af_heart) -> timed, mastered VO.

One command regenerates everything in audio/out/:

    audio/.venv/bin/python audio/tts.py            # pinned speed (reproducible)
    audio/.venv/bin/python audio/tts.py --tune     # re-search the speed for the target end time

Outputs: vo.wav (48 kHz, 24-bit mono, exactly 60.000 s, polished), vo_raw_24k.wav,
timeline.json (BRIEF section 3 schema), vo.srt (one word per cue), beats.txt, validation.txt.

Word timestamps come from Kokoro's own duration predictor: the ONNX graph tensor
`/encoder/Cast_output_0` (integer frames per phoneme token, 1 frame = 600 samples = 25 ms)
is exposed as an extra output (see kokoro_timed.py) and mapped back to words. Because the
predictor folds sentence pauses into the preceding phoneme, word edges that border a pause
are then snapped to the measured acoustic edge (band-wise energy), and the pause lengths are
controlled explicitly (silence inserted at the quietest point).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kokoro_timed import SAMPLE_RATE as SR, TimedKokoro, Word  # noqa: E402

MODELS = os.path.join(HERE, "models")
OUT = os.path.join(HERE, "out")

# ----------------------------------------------------------------------------- script
BEATS: list[tuple[str, str]] = [
    ("hook", "Why do we always talk about space like it's somewhere else?"),
    ("echo", "Out there. Up there. Far away."),
    ("loop", "The answer isn't really about space. It's about you."),
    ("truth", "Here's the truth: you've never left space. Not for a single second."),
    ("distance", "The so-called edge of space? Just a hundred kilometers up. If your car could drive straight up, you'd be there in about an hour."),
    ("speed", "And right now, sitting perfectly still, you're racing around the Sun at over a hundred thousand kilometers an hour."),
    ("stars", "The iron in your blood? Forged inside stars that exploded before Earth even existed."),
    ("question", "So why does it feel so far away?"),
    ("psych", "Psychologists call it psychological distance. The farther away something feels, the more abstractly we think about it. Blurrier. Less yours."),
    ("life", "And we do it with everything. Our dreams. Our goals. The life we keep saying will start... someday."),
    ("payoff", "But you don't go to space. You're already in it."),
    ("final", "And the life you keep waiting for? You're already living it."),
]

# Optional script trims, applied in order only if the VO cannot fit (see --trims N).
SCRIPT_TRIMS: list[tuple[str, str, str]] = [
    ("stars", "stars that exploded before Earth even existed", "stars that exploded before Earth existed"),
    ("speed", "And right now,", "Right now,"),
    ("truth", "Not for a single second.", "Not for a second."),
]

# Gaps (seconds) inserted between consecutive trimmed beat clips (BRIEF assignment).
GAPS = {
    ("hook", "echo"): 0.35, ("echo", "loop"): 0.45, ("loop", "truth"): 0.45,
    ("truth", "distance"): 0.40, ("distance", "speed"): 0.35, ("speed", "stars"): 0.40,
    ("stars", "question"): 0.55, ("question", "psych"): 0.50, ("psych", "life"): 0.45,
    ("life", "payoff"): 0.50, ("payoff", "final"): 0.40,
}

# Pronunciation fixes applied to the espeak phoneme string.
PHONEME_FIXES: dict[str, str] = {
    # espeak glues "for a" into one linked word (fɚɹə); split so word timing maps 1:1
    "fɚɹə sˈɪŋɡəl": "fɚɹ ɐ sˈɪŋɡəl",
}

# Minimum *acoustic* silence between two words, by the punctuation that ends the first one.
# Whatever Kokoro does not already produce is inserted as silence at the quietest point.
MIN_GAP = {".": 0.20, "?": 0.20, "!": 0.20, ":": 0.16, ",": 0.10}
# Beats that are synthesized as separate phrases joined with a controlled silence
# (Kokoro reads "Out there. Up there. Far away." as one unbroken run with no real pauses).
SPLITS: dict[str, list[str]] = {"echo": ["Out there.", "Up there.", "Far away."]}
SPLIT_GAP = {"echo": 0.26}  # silence between the last word of a phrase and the first of the next
# Per-beat overrides: {beat: {word_index_or_text: seconds}}  (silence after that word)
GAP_OVERRIDES: dict[str, dict] = {
    "life": {"everything.": 0.24, "dreams.": 0.24, "goals.": 0.24,
             "start...": 0.35},                  # the ellipsis before "someday"
}

VOICE, LANG = "af_heart", "en-us"
SPEED = 1.00            # global Kokoro speed (pinned by --tune)
TAIL_MULT = 0.95        # payoff + final are read slightly slower for weight
TAIL_BEATS = {"payoff", "final"}
TARGET_END = 56.2       # --tune aims here; accepted window is END_MIN..END_MAX
END_MIN, END_MAX = 54.5, 57.5

VO_FIRST_WORD = 0.08    # first word starts here on the timeline
KEEP = 0.030            # silence kept around each trimmed beat clip
MIN_WORD = 0.060        # minimum word duration
TILE_MAX_GAP = 0.11     # word gaps up to this are split between neighbours (no pause)
THR_QUIET = -34.0       # dB (re band 95th pct): below this = silence / edge of speech
THR_ONSET = -26.0       # dB: audible onset of a word after silence
AUDIO_LEAD = 0.055      # Kokoro's audio leads its predicted token spans by ~55 ms (measured: --measure-lead)
FRIC_EXTRA = 0.025      # words starting with s/sh/f/th: the hiss starts ~25 ms earlier still (measured)
FRIC_INIT = set("sʃfθ")
TOTAL = 60.0
FPS = 30


# ----------------------------------------------------------------------------- helpers
def rms_env(x: np.ndarray, sr: int, hop_ms: float = 5.0, win_ms: float = 20.0) -> tuple[np.ndarray, float]:
    hop, win = int(sr * hop_ms / 1000), int(sr * win_ms / 1000)
    pad = np.pad(x.astype(np.float64), (win // 2, win // 2))
    n = 1 + max(0, (len(x) - 1) // hop)
    idx = np.arange(n)[:, None] * hop + np.arange(win)[None, :]
    return np.sqrt((pad[np.minimum(idx, len(pad) - 1)] ** 2).mean(1)), hop / sr


_LP = butter(4, 3000, "lowpass", fs=SR, output="sos")
_HP = butter(4, 3000, "highpass", fs=SR, output="sos")


def activity_db(x: np.ndarray) -> tuple[np.ndarray, float]:
    """Speech activity in dB per 2.5 ms: max over low/high band, each re its own 95th percentile.

    Band-wise so that weak fricatives (s, f, th) count as speech even though their total
    RMS is ~40 dB under the vowels.
    """
    out = []
    step = 0.0025
    for sos in (_LP, _HP):
        env, step = rms_env(sosfilt(sos, x), SR, hop_ms=2.5, win_ms=10.0)
        out.append(20 * np.log10(np.maximum(env, 1e-9) / max(np.percentile(env, 95), 1e-9)))
    return np.maximum(out[0], out[1]), step


def fade_edges(x: np.ndarray, ms: float = 8.0) -> np.ndarray:
    n = min(int(SR * ms / 1000), len(x) // 2)
    y = x.copy()
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))
    y[:n] *= ramp
    y[len(y) - n:] *= ramp[::-1]
    return y


def end_punct(word: str) -> str:
    w = word.rstrip("\"')”’")
    if w.endswith("..."):
        return "..."
    return w[-1] if w and w[-1] in ".?!:,;" else ""


def quiet_run(db: np.ndarray, step: float, lo: float, hi: float, thr: float, min_len: float):
    """Longest run of frames below thr inside [lo, hi] seconds -> (start, end) or None."""
    a, b = max(0, int(lo / step)), min(len(db), int(hi / step) + 1)
    best, i0 = (0, 0, 0), None
    for k, v in enumerate(list(db[a:b] < thr) + [False]):
        if v and i0 is None:
            i0 = k
        elif not v and i0 is not None:
            if k - i0 > best[0]:
                best = (k - i0, i0, k)
            i0 = None
    if best[0] * step < min_len:
        return None
    return (a + best[1]) * step, (a + best[2]) * step


def insert_silence(audio: np.ndarray, words: list[Word], lo: float, hi: float, extra: float) -> np.ndarray:
    """Insert `extra` seconds of silence at the quietest point between times lo..hi."""
    env, step = rms_env(audio, SR, hop_ms=2.0, win_ms=8.0)
    a, b = int(lo / step), max(int(hi / step), int(lo / step) + 1)
    k = a + int(np.argmin(env[a:b + 1]))
    pos = min(len(audio), max(0, int(round(k * step * SR))))
    n = int(round(extra * SR))
    f = int(0.006 * SR)
    left, right = audio[:pos].copy(), audio[pos:].copy()
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, f))
    if len(left) >= f:
        left[-f:] *= ramp[::-1]
    if len(right) >= f:
        right[:f] *= ramp
    out = np.concatenate([left, np.zeros(n, dtype=audio.dtype), right])
    t_pos = pos / SR
    for w in words:
        if w.start >= t_pos - 1e-9:
            w.start += extra
            w.end += extra
        if w.raw_start >= t_pos - 1e-9:
            w.raw_start += extra
            w.raw_end += extra
    return out


def gap_target(bid: str, i: int, w: Word) -> float:
    ov = GAP_OVERRIDES.get(bid, {})
    if i in ov:
        return ov[i]
    if w.text in ov:
        return ov[w.text]
    p = end_punct(w.text)
    return MIN_GAP.get(p[-1:], 0.0) if p else 0.0


def refine_and_pause(bid: str, audio: np.ndarray, words: list[Word]) -> tuple[np.ndarray, list[str]]:
    """Snap word edges next to pauses to the acoustic edge and enforce pause lengths."""
    log: list[str] = []
    db, step = activity_db(audio)
    # beat start: audible onset of the first word
    w0 = words[0]
    a, z = int(max(0, w0.start - 0.12) / step), int((w0.start + 0.06) / step)
    hit = np.nonzero(db[a:z] > THR_ONSET)[0]
    if len(hit):
        w0.start = (a + hit[0]) * step
    for i in range(len(words) - 1):
        A, B = words[i], words[i + 1]
        punct = end_punct(A.text)
        if not punct and B.start - A.end < 0.10:
            continue
        db, step = activity_db(audio)
        lo = max(A.start + 0.5 * (A.end - A.start), A.end - 0.30)
        hi = min(B.end - 0.5 * (B.end - B.start), B.start + 0.15)
        pred_gap = B.start - A.end
        run = quiet_run(db, step, lo, hi, THR_QUIET, 0.03)
        if run:
            A.end = max(A.start + 0.03, run[0])
            t = run[1]
            nxt = np.nonzero(db[int(t / step):int((t + 0.05) / step)] > THR_ONSET)[0]
            B.start = (int(t / step) + nxt[0]) * step if len(nxt) else t
            B.start = min(B.start, B.end - 0.03)
        gap = B.start - A.end
        target = gap_target(bid, i, A)
        note = f"  after {A.text!r}: predicted gap {pred_gap:.3f}s, acoustic silence {gap:.3f}s"
        if target and gap < target - 0.002:
            extra = target - gap
            audio = insert_silence(audio, words, A.end, B.start, extra)
            note += f" -> +{extra:.3f}s inserted (target {target:.2f}s)"
        elif target and gap > target + 0.08 and bid in GAP_OVERRIDES:
            note += f" (already longer than target {target:.2f}s)"
        log.append(note)
    # beat end: last audible frame
    db, step = activity_db(audio)
    wl = words[-1]
    a = int(wl.start / step)
    hit = np.nonzero(db[a:] > THR_QUIET)[0]
    if len(hit):
        wl.end = max(wl.start + 0.03, (a + hit[-1] + 1) * step)
    return audio, log


def tile_and_floor(words: list[Word]) -> None:
    """Close sub-pause gaps between words, then enforce MIN_WORD by borrowing from neighbours."""
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        g = b.start - a.end
        if 0 < g <= TILE_MAX_GAP:
            mid = a.end + g / 2
            a.end = b.start = mid
    for _ in range(4):
        for i, w in enumerate(words):
            d = MIN_WORD - (w.end - w.start)
            if d <= 1e-9:
                continue
            prev = words[i - 1] if i > 0 else None
            nxt = words[i + 1] if i + 1 < len(words) else None
            for side, nb in (("l", prev), ("r", nxt)):
                if d <= 1e-9 or nb is None:
                    continue
                touching = abs((w.start - nb.end) if side == "l" else (nb.start - w.end)) < 1e-6
                if not touching:  # free space (a pause): extend at most 20 ms into it
                    take = min(d / 2 + 0.0005, 0.02)
                    if side == "l":
                        w.start -= take
                    else:
                        w.end += take
                    d -= take
                else:             # borrow from a neighbouring word that can spare it
                    spare = max(0.0, (nb.end - nb.start) - MIN_WORD - 0.01)
                    take = min(d / 2 + 0.0005, spare)
                    if side == "l":
                        nb.end -= take
                        w.start = nb.end
                    else:
                        nb.start += take
                        w.end = nb.start
                    d -= take


def trim_clip(audio: np.ndarray, words: list[Word]) -> np.ndarray:
    """Trim to KEEP seconds around the first/last word; shift word times to the clip."""
    t0 = max(0.0, words[0].start - KEEP)
    t1 = min(len(audio) / SR, words[-1].end + KEEP)
    i0, i1 = int(round(t0 * SR)), int(round(t1 * SR))
    clip = fade_edges(audio[i0:i1], 6.0)
    for w in words:
        for f in ("start", "end", "raw_start", "raw_end"):
            setattr(w, f, getattr(w, f) - i0 / SR)
    return clip


# ----------------------------------------------------------------------------- build
class Builder:
    def __init__(self, beats: list[tuple[str, str]]):
        self.beats = beats
        self.tk = TimedKokoro(MODELS, VOICE, LANG, PHONEME_FIXES)
        self._cache: dict = {}

    def synth_segment(self, bid: str, text: str, speed: float):
        s = self.tk.synth(text, speed)
        words = [Word(**w.__dict__) for w in s.words]
        for w in words:  # predicted spans lag the audio: move them onto the acoustics
            for f in ("start", "end", "raw_start", "raw_end"):
                setattr(w, f, getattr(w, f) - AUDIO_LEAD)
        for i in range(1, len(words)):  # fricative-initial words: the hiss precedes the vowel
            first = next(c for c in words[i].phonemes if c not in "ˈˌ.,!?:;… ")
            if first in FRIC_INIT:
                words[i].start -= FRIC_EXTRA
                words[i - 1].end = min(words[i - 1].end, max(words[i].start, words[i - 1].start + MIN_WORD))
        audio, plog = refine_and_pause(bid, s.audio, words)
        tile_and_floor(words)
        clip = trim_clip(audio, words)
        return clip, words, s.phonemes, plog

    def beat_clip(self, bid: str, text: str, speed: float):
        key = (bid, text, round(speed, 4))
        if key not in self._cache:
            segs = SPLITS.get(bid, [text])
            assert " ".join(segs).split() == text.split(), (bid, segs)
            parts = [self.synth_segment(bid, seg, speed) for seg in segs]
            if len(parts) == 1:
                self._cache[key] = parts[0]
            else:  # join phrases with an exact silence between last word and next first word
                gap = SPLIT_GAP[bid]
                placed, words, phs, plog = [], [], [], []
                cursor_end = None  # time of previous last word end in the joined clip
                for clip, w, ph, pl in parts:
                    off = 0.0 if cursor_end is None else cursor_end + gap - w[0].start
                    for x in w:
                        for f in ("start", "end", "raw_start", "raw_end"):
                            setattr(x, f, getattr(x, f) + off)
                    placed.append((int(round(off * SR)), clip))
                    words += w
                    phs.append(ph)
                    plog += pl
                    cursor_end = w[-1].end
                n = max(p + len(c) for p, c in placed)
                joined = np.zeros(n, dtype=np.float32)
                for p, c in placed:
                    joined[p:p + len(c)] += c
                plog.append(f"  phrases joined with {gap:.2f}s silence between last/first word")
                self._cache[key] = (joined, words, " | ".join(phs), plog)
        clip, words, ph, plog = self._cache[key]
        return clip, [Word(**w.__dict__) for w in words], ph, plog

    def assemble(self, speed: float, tail_mult: float = TAIL_MULT):
        pieces, beat_meta = [], []
        cursor = 0  # samples
        for n, (bid, text) in enumerate(self.beats):
            sp = speed * (tail_mult if bid in TAIL_BEATS else 1.0)
            clip, words, ph, plog = self.beat_clip(bid, text, sp)
            if n == 0:
                cursor = max(0, int(round((VO_FIRST_WORD - words[0].start) * SR)))
            else:
                cursor += int(round(GAPS[(self.beats[n - 1][0], bid)] * SR))
            off = cursor / SR
            for w in words:
                for f in ("start", "end", "raw_start", "raw_end"):
                    setattr(w, f, getattr(w, f) + off)
            pieces.append((cursor, clip))
            beat_meta.append(dict(id=bid, text=text, speed=sp, words=words, phonemes=ph, plog=plog,
                                  clip_start=cursor / SR, clip_end=(cursor + len(clip)) / SR))
            cursor += len(clip)
        total = int(TOTAL * SR)
        raw = np.zeros(max(total, cursor + SR), dtype=np.float32)
        for pos, clip in pieces:
            raw[pos:pos + len(clip)] += clip
        return raw[:total], beat_meta, beat_meta[-1]["words"][-1].end


# ----------------------------------------------------------------------------- validation
PS_EXTRA = {"abstractly": "AE B S T R AE K T L IY", "blurrier": "B L ER IY ER"}


def ps_align(clip24: np.ndarray, text: str):
    """Independent forced alignment with CMU PocketSphinx (word segments, seconds)."""
    from pocketsphinx import Config, Decoder, get_model_path
    from scipy.signal import resample_poly

    pad = np.zeros(int(0.3 * SR))  # forced alignment wants silence around the utterance
    clip24 = np.concatenate([pad, clip24.astype(np.float64), pad])
    pcm = (np.clip(resample_poly(clip24, 2, 3), -1, 1) * 32767).astype(np.int16).tobytes()
    mp = get_model_path()
    cfg = Config()
    cfg["hmm"] = os.path.join(mp, "en-us", "en-us")
    cfg["dict"] = os.path.join(mp, "en-us", "cmudict-en-us.dict")
    cfg["loglevel"] = "FATAL"
    d = Decoder(cfg)
    groups = []  # PS word indices per script word
    names: list[str] = []
    for w in text.split():
        parts = [re.sub(r"[^a-z']", "", p.lower()) for p in re.split(r"[-–—]", w)]
        parts = [p for p in parts if p]
        groups.append(list(range(len(names), len(names) + len(parts))))
        names += parts
    for n in set(names):
        if n in PS_EXTRA:
            d.add_word(n, PS_EXTRA[n], True)
    d.set_align_text(" ".join(names))
    d.start_utt()
    d.process_raw(pcm, False, True)
    d.end_utt()
    d.set_alignment()
    d.start_utt()
    d.process_raw(pcm, False, True)
    d.end_utt()
    segs = [(s.name, s.start / 100.0 - 0.3, (s.start + s.duration) / 100.0 - 0.3) for s in d.get_alignment().words()]
    segs = [s for s in segs if s[0] not in ("<sil>", "(NULL)", "<s>", "</s>")]
    return segs, groups


def validate(raw: np.ndarray, beats_meta: list[dict]) -> tuple[str, bool]:
    L, ok = [], True
    words_all: list[tuple[str, Word]] = [(b["id"], w) for b in beats_meta for w in b["words"]]
    # 1. structural checks
    prev_end, mono, short = -1.0, True, []
    for bid, w in words_all:
        if w.start < prev_end - 1e-9 or w.end < w.start:
            mono = False
        prev_end = w.end
        if w.end - w.start < MIN_WORD - 1e-6:
            short.append((bid, w.text, round(w.end - w.start, 3)))
    inside = all(b["clip_start"] - 1e-6 <= b["words"][0].start and b["words"][-1].end <= b["clip_end"] + 1e-6
                 for b in beats_meta)
    durs = [w.end - w.start for _, w in words_all]
    L.append(f"words: {len(words_all)}; monotonic & non-overlapping: {mono}; all inside their beat clip: {inside}")
    L.append(f"shortest word {min(durs) * 1000:.0f} ms, longest {max(durs) * 1000:.0f} ms; "
             f"words < {MIN_WORD * 1000:.0f} ms: {short or 'none'}")
    texts_ok = all(" ".join(w.text for w in b["words"]) == b["text"] for b in beats_meta)
    L.append(f"word texts reproduce each beat's script text exactly: {texts_ok}")
    ok &= mono and inside and not short and texts_ok

    # 2. pauses are acoustically silent; word edges next to them sit on the acoustic edge
    db, step = activity_db(raw)
    loud, n_p = [], 0
    for b in beats_meta:
        ws = b["words"]
        for i in range(len(ws) - 1):
            g0, g1 = ws[i].end, ws[i + 1].start
            if g1 - g0 >= 0.12:
                n_p += 1
                seg = db[int((g0 + 0.015) / step):int((g1 - 0.015) / step) + 1]
                loud.append((float(seg.max()) if len(seg) else -99.0, b["id"], ws[i].text))
    worst = max(loud) if loud else (-99, "", "")
    L.append(f"pauses >= 120 ms: {n_p}; loudest activity inside any of them: {worst[0]:.1f} dB re speech "
             f"(threshold for 'silent' = {THR_QUIET:.0f} dB; worst: {worst[1]}:{worst[2]!r})")
    ok &= worst[0] < -26.0
    gaps = [(b["id"], ws[i].text, ws[i + 1].start - ws[i].end) for b in beats_meta
            for ws in [b["words"]] for i in range(len(ws) - 1) if ws[i + 1].start - ws[i].end >= 0.12]
    L.append("pause lengths (s): " + ", ".join(f"{t}={g:.2f}" for _, t, g in gaps))

    # 3. independent check: PocketSphinx forced alignment on each beat clip
    try:
        import pocketsphinx  # noqa: F401
    except ImportError:
        L.append("pocketsphinx not installed: independent alignment check skipped")
        return "\n".join(L), ok
    d_bound, d_on, d_off, b_on, b_off, names = [], [], [], [], [], []
    for b in beats_meta:
        c0 = int(round(b["clip_start"] * SR))
        c1 = int(round(b["clip_end"] * SR))
        clip = raw[c0:c1]
        try:
            segs, groups = ps_align(clip, b["text"])
        except Exception as e:  # noqa: BLE001
            L.append(f"  ({b['id']}: pocketsphinx alignment failed: {e})")
            continue
        ws = b["words"]
        rel = [(w.start - b["clip_start"], w.end - b["clip_start"]) for w in ws]
        ps = [(segs[g[0]][1], segs[g[-1]][2]) for g in groups]
        cdb, cstep = activity_db(clip)
        # PS own bias at the clip edges where the acoustic edge is unambiguous (digital silence beyond)
        on = int(np.argmax(cdb > THR_ONSET)) * cstep
        off = (len(cdb) - int(np.argmax(cdb[::-1] > THR_QUIET))) * cstep
        b_on.append(on - ps[0][0])
        b_off.append(off - ps[-1][1])
        for i in range(len(ws) - 1):
            gap = rel[i + 1][0] - rel[i][1]
            if gap <= 0.01:       # touching words -> compare the shared boundary
                d_bound.append(rel[i][1] - ps[i][1])
            else:                 # real pause -> compare edges separately
                d_off.append(rel[i][1] - ps[i][1])
                d_on.append(rel[i + 1][0] - ps[i + 1][0])
                names.append((b["id"], ws[i].text, ws[i + 1].text, d_off[-1], d_on[-1]))
    def st(name, v):
        a = np.array(v) * 1000
        L.append(f"  {name}: n={len(a)} median {np.median(a):+.0f} ms, IQR [{np.percentile(a, 25):+.0f}, "
                 f"{np.percentile(a, 75):+.0f}] ms, mean|dev from median| {np.abs(a - np.median(a)).mean():.0f} ms, "
                 f"within +-50 ms of median: {(np.abs(a - np.median(a)) <= 50).mean() * 100:.0f}%")
        return a
    L.append("independent check vs PocketSphinx forced alignment (ours - PS):")
    L.append(f"  PS own bias vs acoustic edge at clip start/end (acoustic - PS): "
             f"start {np.median(b_on) * 1000:+.0f} ms, end {np.median(b_off) * 1000:+.0f} ms (PS places edges early)")
    st("internal word boundaries ", d_bound)
    st("word starts after a pause", d_on)
    st("word ends before a pause ", d_off)
    L.append("  pause edges (beat, word | next word, end dev ms, start dev ms): " + "; ".join(
        f"{a}:{x}|{y} {o * 1000:+.0f}/{n_ * 1000:+.0f}" for a, x, y, o, n_ in names))
    return "\n".join(L), ok


# ----------------------------------------------------------------------------- polish
def polish(raw24: np.ndarray, report: list[str]) -> np.ndarray:
    import soxr
    from pedalboard import Compressor, HighpassFilter, HighShelfFilter, Limiter, PeakFilter, Pedalboard

    x = soxr.resample(raw24.astype(np.float64), SR, 48000, quality="VHQ").astype(np.float32)
    hf = sosfilt(butter(4, [5000, 9000], "bandpass", fs=48000, output="sos"), x)
    report.append(f"5-9 kHz share of total energy before polish: "
                  f"{10 * np.log10((hf ** 2).sum() / ((x ** 2).sum() + 1e-12)):.1f} dB")
    # Kokoro's 8-12 kHz band is as strong as 4-8 kHz (hissy / "digital"): shelve it down a little.
    pre = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=70),
        PeakFilter(cutoff_frequency_hz=3500, gain_db=1.5, q=0.7),               # presence
        HighShelfFilter(cutoff_frequency_hz=7500, gain_db=-3.5, q=0.7),         # soft de-harsh
        Compressor(threshold_db=-20, ratio=2.0, attack_ms=15, release_ms=160),  # light, no pumping
    ])
    y = pre(x[None, :], 48000)[0]
    # Shave only the rare transient peaks (plosives, ~0.01 % of samples) so the -3 dBFS peak target does
    # not cost loudness. NB: pedalboard's Limiter has make-up gain (ceiling 0 dBFS), hence the re-normalise.
    a = np.abs(y)
    lim_db = float(np.clip(20 * np.log10(np.percentile(a[a > 1e-4], 99.99)), -12.0, -6.0))
    y = Pedalboard([Limiter(threshold_db=lim_db, release_ms=80)])(y[None, :], 48000)[0]
    report.append(f"limiter threshold {lim_db:.1f} dBFS (99.99th-percentile peak) before peak-normalising")
    y = y * (10 ** (-3 / 20) / float(np.abs(y).max()))
    return y.astype(np.float32)


# ----------------------------------------------------------------------------- outputs
def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_outputs(raw, meta, end, report, trims_applied, speed):
    os.makedirs(OUT, exist_ok=True)
    sf.write(os.path.join(OUT, "vo_raw_24k.wav"), raw, SR, subtype="FLOAT")
    final = polish(raw, report)
    assert len(final) == 48000 * 60
    sf.write(os.path.join(OUT, "vo.wav"), final, 48000, subtype="PCM_24")

    tl = {"fps": FPS, "durationInFrames": int(round(TOTAL * FPS)),
          "voStart": round(meta[0]["words"][0].start, 3), "voEnd": round(end, 3), "beats": []}
    srt, table, n = [], [], 0
    for b in meta:
        ws = b["words"]
        tl["beats"].append({
            "id": b["id"], "text": b["text"],
            "start": round(ws[0].start, 3), "end": round(ws[-1].end, 3),
            "words": [{"text": w.text, "start": round(w.start, 3), "end": round(w.end, 3)} for w in ws]})
        table.append(f"{b['id']:<9} {ws[0].start:7.3f} {ws[-1].end:7.3f}   speed {b['speed']:.3f}   {b['text']}")
        for w in ws:
            n += 1
            srt.append(f"{n}\n{srt_time(w.start)} --> {srt_time(w.end)}\n{w.text}\n")
    with open(os.path.join(OUT, "timeline.json"), "w") as f:
        json.dump(tl, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(OUT, "vo.srt"), "w") as f:
        f.write("\n".join(srt))
    with open(os.path.join(OUT, "beats.txt"), "w") as f:
        f.write(f"speed={speed:.3f} tail_mult={TAIL_MULT} trims={trims_applied or 'none'}\n")
        f.write(f"voStart={tl['voStart']:.3f}  voEnd={tl['voEnd']:.3f}\n\n")
        f.write(f"{'beat':<9} {'start':>7} {'end':>7}\n" + "\n".join(table) + "\n")
    return final, tl


def measure_lead(bld: Builder, speed: float) -> None:
    """Cross-correlate predicted token spans with band energy to measure the audio/duration offset."""
    HPb = butter(4, [4500, 10500], "bandpass", fs=SR, output="sos")
    LPb = butter(4, [200, 1200], "bandpass", fs=SR, output="sos")
    vow, fri, step = set("aeiouɐɑɒɔəɚɛɜɪʊʌæᵻ"), set("sfʃ"), 0.0025
    lags = np.arange(-60, 41)
    cf, cv = np.zeros(len(lags)), np.zeros(len(lags))
    def ind(spans, T, S):
        x = np.zeros(T)
        for ch, a, b in spans:
            if ch in S:
                x[int(a / step):int(b / step)] = 1
        return x
    def corr(x, y):
        out = []
        for L in lags:
            xs, ys = (x[:len(x) - L], y[L:]) if L >= 0 else (x[-L:], y[:L])
            n = min(len(xs), len(ys))
            out.append(np.corrcoef(xs[:n], ys[:n])[0, 1] if xs[:n].std() > 0 else 0.0)
        return np.nan_to_num(np.array(out))
    per = []
    for bid, text in bld.beats:
        for seg in SPLITS.get(bid, [text]):
            sy = bld.tk.synth(seg, speed)
            eh, _ = rms_env(sosfilt(HPb, sy.audio), SR, 2.5, 8.0)
            el, _ = rms_env(sosfilt(LPb, sy.audio), SR, 2.5, 8.0)
            dh, dl = 20 * np.log10(np.maximum(eh, 1e-6)), 20 * np.log10(np.maximum(el, 1e-6))
            cv_i, cf_i = corr(ind(sy.char_spans, len(dl), vow), dl), corr(ind(sy.char_spans, len(dh), fri), dh)
            cv += cv_i
            cf += cf_i
            per.append(lags[np.argmax(cv_i)] * step * 1000)
    print(f"speed {speed}: best lag of vowel spans vs 200-1200 Hz energy: {lags[np.argmax(cv)] * step * 1000:+.1f} ms "
          f"(per-beat median {np.median(per):+.1f}, range {min(per):+.0f}..{max(per):+.0f}); "
          f"fricative spans vs 4.5-10.5 kHz energy: {lags[np.argmax(cf)] * step * 1000:+.1f} ms")
    print("negative = audio happens EARLIER than the predicted span")


def tune(bld: Builder, target: float, tail_mult: float) -> float:
    """end(speed) ~ a/speed + b: two probes, solve, then verify/refine on the 0.01 grid."""
    s1, s2 = 1.00, 1.10
    e1, e2 = bld.assemble(s1, tail_mult)[2], bld.assemble(s2, tail_mult)[2]
    print(f"  speed {s1:.2f} -> VO end {e1:.3f}s\n  speed {s2:.2f} -> VO end {e2:.3f}s", flush=True)
    a = (e1 - e2) / (1 / s1 - 1 / s2)
    b0 = e1 - a / s1
    best = round(a / (target - b0), 2)
    for _ in range(3):
        e = bld.assemble(best, tail_mult)[2]
        print(f"  speed {best:.2f} -> VO end {e:.3f}s", flush=True)
        if abs(e - target) < 0.35:
            break
        best = round(best * e / target, 2)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=SPEED)
    ap.add_argument("--tail-mult", type=float, default=TAIL_MULT)
    ap.add_argument("--tune", action="store_true", help="search speed so VO ends near --target-end")
    ap.add_argument("--target-end", type=float, default=TARGET_END)
    ap.add_argument("--trims", type=int, default=0, help="apply the first N script trims")
    ap.add_argument("--phonemes-only", action="store_true")
    ap.add_argument("--measure-lead", action="store_true", help="measure audio-vs-duration offset and exit")
    a = ap.parse_args()

    beats = [list(b) for b in BEATS]
    applied = []
    for bid, old, new in SCRIPT_TRIMS[:a.trims]:
        for b in beats:
            if b[0] == bid:
                assert old in b[1], (bid, old)
                b[1] = b[1].replace(old, new)
                applied.append(f"{bid}: {old!r} -> {new!r}")
    beats = [tuple(b) for b in beats]

    bld = Builder(beats)
    if a.phonemes_only:
        for bid, text in beats:
            print(f"[{bid}] {text}\n   {bld.tk.phonemize(text)}")
        return
    speed = a.speed
    if a.measure_lead:
        measure_lead(bld, speed)
        return
    if a.tune:
        speed = tune(bld, a.target_end, a.tail_mult)
        print(f"tuned speed = {speed:.2f}  (pin it as SPEED in tts.py)")

    raw, meta, end = bld.assemble(speed, a.tail_mult)
    print(f"speed={speed:.3f} tail_mult={a.tail_mult} VO end={end:.3f}s trims={applied or 'none'}")
    for b in meta:
        print(f"\n[{b['id']}] speed {b['speed']:.3f}  {b['text']}\n   phonemes: {b['phonemes']}")
        for line in b["plog"]:
            print(line)
    if not (END_MIN <= end <= END_MAX):
        print(f"WARNING: VO end {end:.3f}s outside {END_MIN}-{END_MAX}s window", file=sys.stderr)

    report: list[str] = []
    vtxt, ok = validate(raw, meta)
    final, tl = write_outputs(raw, meta, end, report, applied, speed)

    import pyloudnorm as pyln
    lufs = pyln.Meter(48000).integrated_loudness(final.astype(np.float64))
    report.append(f"final vo.wav: peak {20 * np.log10(np.abs(final).max()):.2f} dBFS, integrated {lufs:.1f} LUFS, "
                  f"{len(final) / 48000:.3f} s @ 48 kHz")
    with open(os.path.join(OUT, "validation.txt"), "w") as f:
        f.write(f"speed={speed:.3f} tail_mult={a.tail_mult} trims={applied or 'none'} voEnd={end:.3f}\n")
        f.write(vtxt + "\n" + "\n".join(report) + "\n")
    print("\n=== validation ===\n" + vtxt + "\n" + "\n".join(report))
    print("\nstructural validation passed" if ok else "\nSTRUCTURAL VALIDATION FAILED")
    sys.exit(0 if ok and END_MIN <= end <= END_MAX else 1)


if __name__ == "__main__":
    main()
