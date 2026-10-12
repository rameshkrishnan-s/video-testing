"""Shared DSP + timeline helpers for music.py, sfx.py and mix.py.

Everything renders at 48 kHz. Time-domain buffers are float64, shape (n,) for mono or
(n, 2) for stereo. Long renders use a 60 s "loop" convention: material that rings past
60.000 s is folded back onto the start (fold()), and stateful processors run through
circular() so their state at 0 s is the state they had at 60 s. That makes the end of
the master flow seamlessly into its start when the video loops.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SR = 48000
DUR = 60.0
N = int(round(SR * DUR))           # 2,880,000 samples
TAIL = 8.0                         # render headroom past 60 s (folded back onto the start)
NT = N + int(round(TAIL * SR))
TWO_PI = 2.0 * np.pi


def ts(t: float) -> int:
    """seconds -> sample index"""
    return int(round(t * SR))


# ============================================================================ timeline
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9']", "", s.lower().replace("’", "'"))


SCENES = [
    ("night-sky", ["hook", "echo", "loop"]),
    ("pull-back", ["truth"]),
    ("karman", ["distance"]),
    ("orbit", ["speed"]),
    ("star-stuff", ["stars"]),
    ("question", ["question"]),
    ("psych", ["psych"]),
    ("someday", ["life"]),
    ("already", ["payoff", "final"]),
]


class Timeline:
    """Look up beats / words in audio/out/timeline.json by id and (normalised) text."""

    LEAD = 0.25

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(OUT, "timeline.json")
        with open(self.path) as f:
            self.d = json.load(f)
        self.beats = {b["id"]: b for b in self.d["beats"]}

    def word(self, bid: str, text: str, n: int = 0) -> dict:
        key = _norm(text)
        hits = [w for w in self.beats[bid]["words"] if _norm(w["text"]) == key]
        if len(hits) <= n:
            raise KeyError(f"word {text!r} #{n} not found in beat {bid!r}")
        return hits[n]

    def t(self, bid: str, text: str, n: int = 0, edge: str = "start") -> float:
        return float(self.word(bid, text, n)[edge])

    def beat_start(self, bid: str) -> float:
        return float(self.beats[bid]["words"][0]["start"])

    def beat_end(self, bid: str) -> float:
        return float(self.beats[bid]["words"][-1]["end"])

    def scene_start(self, key: str) -> float:
        """scene start by scene id or by any beat id it contains"""
        for i, (sid, bids) in enumerate(SCENES):
            if key == sid or key in bids:
                return 0.0 if i == 0 else max(0.0, self.beat_start(bids[0]) - self.LEAD)
        raise KeyError(key)

    def scenes(self) -> list[tuple[str, float, float]]:
        starts = [self.scene_start(sid) for sid, _ in SCENES]
        ends = starts[1:] + [DUR]
        return [(sid, a, b) for (sid, _), a, b in zip(SCENES, starts, ends)]

    def words(self) -> list[tuple[str, dict]]:
        return [(b["id"], w) for b in self.d["beats"] for w in b["words"]]

    @property
    def vo_end(self) -> float:
        return max(float(w["end"]) for _, w in self.words())


# ============================================================================ pitch
_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6,
       "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def midi(name: str) -> int:
    m = re.fullmatch(r"([A-G][#b]?)(-?\d)", name)
    if not m:
        raise ValueError(name)
    return 12 * (int(m.group(2)) + 1) + _PC[m.group(1)]


def mhz(m: float) -> float:
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def hz(name: str) -> float:
    return mhz(midi(name))


def pc(name: str) -> int:
    return _PC[name]


def nearest_tone(target_hz: float, pcs) -> float:
    """frequency of the pitch (any octave) from pitch-class set `pcs` nearest to target_hz"""
    tm = 69 + 12 * np.log2(target_hz / 440.0)
    cands = [12 * o + p for o in range(0, 10) for p in pcs]
    best = min(cands, key=lambda m: abs(m - tm))
    return mhz(best)


# ============================================================================ envelopes
def cos01(x):
    x = np.clip(x, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * x)


def curve(t, pts, log: bool = False, shape: str = "cos"):
    """Automation through (time, value) points, eased (raised cosine) between points."""
    pts = sorted(pts)
    tp = np.array([p[0] for p in pts], float)
    vp = np.array([p[1] for p in pts], float)
    if log:
        vp = np.log(vp)
    t = np.asarray(t, float)
    if len(tp) == 1:
        v = np.full_like(t, vp[0])
        return np.exp(v) if log else v
    i = np.clip(np.searchsorted(tp, t, side="right") - 1, 0, len(tp) - 2)
    t0, t1 = tp[i], tp[i + 1]
    x = np.clip((t - t0) / np.maximum(t1 - t0, 1e-9), 0, 1)
    x = cos01(x) if shape == "cos" else x
    v = vp[i] + (vp[i + 1] - vp[i]) * x
    v = np.where(t <= tp[0], vp[0], np.where(t >= tp[-1], vp[-1], v))
    return np.exp(v) if log else v


def env_ar(n: int, attack: float, release: float, curve_pow: float = 1.0):
    """1.0 sustain with raised-cosine attack (s) at the start and release (s) at the end."""
    e = np.ones(n)
    a = min(n, max(1, ts(attack)))
    r = min(n - a, max(1, ts(release)))
    e[:a] = cos01(np.arange(a) / a) ** curve_pow
    if r > 0:
        e[n - r:] *= cos01(1.0 - np.arange(r) / r)
    return e


def env_perc(n: int, attack: float, tau: float):
    """raised-cosine attack then exponential decay (time constant tau)"""
    t = np.arange(n) / SR
    a = max(attack, 1e-4)
    e = np.where(t < a, cos01(t / a), np.exp(-(t - a) / tau))
    return e


def fade_edges(x, fin: float = 0.002, fout: float = 0.005):
    n = len(x)
    e = env_ar(n, fin, fout)
    return x * (e[:, None] if x.ndim == 2 else e)


# ============================================================================ stereo / placement
def pan_gains(p: float):
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


def to_stereo(x, pan: float = 0.0):
    if x.ndim == 2:
        return x
    gl, gr = pan_gains(pan)
    return np.stack([x * gl, x * gr], 1)


def place(buf, x, t0: float, gain: float = 1.0, pan: float = 0.0):
    """add x (mono or stereo) into stereo buf starting at time t0 (clips to buffer)"""
    x = to_stereo(x, pan) * gain
    i0 = ts(t0)
    a = max(0, -i0)
    b = min(len(x), len(buf) - i0)
    if b > a:
        buf[i0 + a:i0 + b] += x[a:b]
    return buf


def fold(y, n: int = N):
    """wrap everything past n samples back onto the start (circular / loop-consistent)"""
    out = y[:n].copy()
    i = n
    while i < len(y):
        seg = y[i:i + n]
        out[:len(seg)] += seg
        i += n
    return out


def circular(fn, x, pad: float = 3.0):
    """Run a stateful processor as if the 60 s signal were looping: prepend its last `pad`
    seconds (and append its first), process, keep the middle."""
    p = ts(pad)
    ext = np.concatenate([x[-p:], x, x[:p]], 0)
    y = fn(ext)
    return y[p:p + len(x)]


# ============================================================================ filters
def sos_filt(x, sos):
    return signal.sosfilt(sos, x, axis=0)


def butter(kind: str, f, order: int = 2):
    return signal.butter(order, f, btype=kind, fs=SR, output="sos")


def _biquad_sos(b, a):
    b = np.asarray(b, float) / a[0]
    a = np.asarray(a, float) / a[0]
    return np.array([[b[0], b[1], b[2], 1.0, a[1], a[2]]])


def peq(f0: float, gain_db: float, q: float = 0.7):
    """RBJ peaking EQ biquad (sos)"""
    A = 10 ** (gain_db / 40)
    w = TWO_PI * f0 / SR
    al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return _biquad_sos(b, a)


def shelf(kind: str, f0: float, gain_db: float, s: float = 0.7):
    """RBJ low/high shelf biquad (sos)"""
    A = 10 ** (gain_db / 40)
    w = TWO_PI * f0 / SR
    cw, sw = np.cos(w), np.sin(w)
    al = sw / 2 * np.sqrt((A + 1 / A) * (1 / s - 1) + 2)
    if kind == "low":
        b = [A * ((A + 1) - (A - 1) * cw + 2 * np.sqrt(A) * al), 2 * A * ((A - 1) - (A + 1) * cw),
             A * ((A + 1) - (A - 1) * cw - 2 * np.sqrt(A) * al)]
        a = [(A + 1) + (A - 1) * cw + 2 * np.sqrt(A) * al, -2 * ((A - 1) + (A + 1) * cw),
             (A + 1) + (A - 1) * cw - 2 * np.sqrt(A) * al]
    else:
        b = [A * ((A + 1) + (A - 1) * cw + 2 * np.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * cw),
             A * ((A + 1) + (A - 1) * cw - 2 * np.sqrt(A) * al)]
        a = [(A + 1) - (A - 1) * cw + 2 * np.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * cw),
             (A + 1) - (A - 1) * cw - 2 * np.sqrt(A) * al]
    return _biquad_sos(b, a)


def lp_mag(f, fc, order: int = 2, res: float = 0.0):
    """magnitude of a smooth low-pass (Butterworth-like) with an optional resonance bump"""
    r = np.maximum(f / fc, 1e-6)
    m = 1.0 / np.sqrt(1.0 + r ** (2 * order))
    if res:
        m = m * (1.0 + res * np.exp(-0.5 * (np.log2(r) / 0.3) ** 2))
    return m


def bp_mag(f, fc, q):
    """2nd-order band-pass magnitude"""
    f = np.maximum(f, 1.0)
    return 1.0 / np.sqrt(1.0 + (q * (f / fc - fc / f)) ** 2)


# ============================================================================ noise
def noise_tv(dur: float, shape, seed: int, stereo: bool = True, nperseg: int = 1024, hop: int = 256):
    """White noise filtered by a time-varying magnitude response.
    shape(f[:,None], t[None,:]) -> (nf, nt) gains (t in seconds from the noise start)."""
    n = ts(dur)
    rng = np.random.default_rng(seed)
    chans = []
    for _ in range(2 if stereo else 1):
        w = rng.standard_normal(n + nperseg)
        f, tt, Z = signal.stft(w, SR, nperseg=nperseg, noverlap=nperseg - hop)
        M = shape(f[:, None], tt[None, :])
        _, y = signal.istft(Z * M, SR, nperseg=nperseg, noverlap=nperseg - hop)
        chans.append(y[:n])
    return np.stack(chans, 1) if stereo else chans[0]


def periodic_noise(n: int, seed: int, mag=None):
    """noise that is exactly periodic over n samples (built in the DFT domain).
    mag(f) shapes the spectrum."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n, 1 / SR)
    spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
    if mag is not None:
        spec *= mag(f)
    spec[0] = 0
    y = np.fft.irfft(spec, n)
    return y / (np.std(y) + 1e-12)


# ============================================================================ reverb
def make_ir(rt_low: float = 3.0, rt_high: float = 1.2, length: float | None = None,
            predelay: float = 0.02, seed: int = 0, f_lo: float = 300.0, f_hi: float = 7000.0,
            hp: float = 150.0, lp: float = 12000.0, early: int = 8, build: float = 0.015):
    """Stereo decaying-noise impulse response with frequency-dependent RT60 (rt_low below
    f_lo, rt_high above f_hi), soft diffuse build-up, sparse early reflections, pre-delay.
    Normalised to unit energy per channel; L/R independent (decorrelated)."""
    length = length or (1.3 * max(rt_low, rt_high) + 0.2)
    n = ts(length)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    chans = []
    for ch in range(2):
        def shape(f, tt):
            x = np.clip((np.log(np.maximum(f, 20)) - np.log(f_lo)) / (np.log(f_hi) - np.log(f_lo)), 0, 1)
            rt = rt_low + (rt_high - rt_low) * x
            rt = rt * np.where(f < 120, 0.75, 1.0)              # shorter sub-bass tail
            return np.exp(-6.907755 * tt / rt)
        y = noise_tv(length, shape, seed=seed * 7 + ch, stereo=False)
        y = y * (1 - np.exp(-t / build))
        # early reflections
        for k in range(early):
            d = rng.uniform(0.004, 0.07)
            g = rng.uniform(0.25, 0.7) * np.exp(-d / 0.05) * (1 if rng.random() > 0.5 else -1)
            i = ts(d)
            if i < n:
                y[i] += g * 3.0 * np.std(y[:ts(0.1)])
        chans.append(y)
    ir = np.stack(chans, 1)
    ir = sos_filt(ir, butter("highpass", hp, 2))
    ir = sos_filt(ir, butter("lowpass", lp, 2))
    ir = np.concatenate([np.zeros((ts(predelay), 2)), ir], 0)
    ir /= np.sqrt((ir ** 2).sum(0, keepdims=True))
    return ir


def convolve(x, ir, circ: bool = True):
    """stereo convolution: L->IR_L, R->IR_R (mono input feeds both). circ=True folds the
    tail onto the start (loop-consistent, output length = input length)."""
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    ys = [signal.oaconvolve(x[:, c], ir[:, c]) for c in range(2)]
    y = np.stack(ys, 1)
    return fold(y, len(x)) if circ else y[:len(x) + len(ir) - 1]


def reverb_tail(x, ir):
    """convolve a short mono/stereo sound and keep the full tail (non-circular)"""
    return convolve(x, ir, circ=False)


# ============================================================================ delay
def pingpong(x, delay: float, fb: float, taps: int = 8, lp: float = 5000.0, hp: float = 250.0,
             first: int = 0):
    """ping-pong echo: each repeat alternates channel, gets darker and quieter"""
    m = x.mean(1) if x.ndim == 2 else x
    out = np.zeros((len(m), 2))
    tap = sos_filt(m, butter("highpass", hp, 1))
    sos = butter("lowpass", lp, 1)
    d = ts(delay)
    for i in range(1, taps + 1):
        tap = sos_filt(tap, sos) * fb
        k = d * i
        if k >= len(m):
            break
        out[k:, (i - 1 + first) % 2] += tap[:len(m) - k]
    return out


# ============================================================================ dynamics
def _ar_smooth(target, a_att: float, a_rel: float, rising_is_attack: bool = True):
    """one-pole smoother with separate attack / release coefficients (control rate)"""
    out = np.empty(len(target))
    s = float(target[0])
    tl = target.tolist()
    for i, v in enumerate(tl):
        if (v > s) == rising_is_attack:
            s = a_att * s + (1 - a_att) * v
        else:
            s = a_rel * s + (1 - a_rel) * v
        out[i] = s
    return out


def level_db(x, win: float = 0.01, hop: int = 48):
    """RMS level (dBFS) at control rate (every `hop` samples)"""
    p = (x ** 2).mean(1) if x.ndim == 2 else x ** 2
    p = uniform_filter1d(p, max(1, ts(win)), mode="nearest")
    return 10 * np.log10(p[::hop] + 1e-14)


def gain_curve_to_audio(g_db_ctrl, n: int, hop: int = 48):
    return np.interp(np.arange(n), np.arange(len(g_db_ctrl)) * hop, g_db_ctrl)


def compressor(x, thresh_db: float, ratio: float, attack_ms: float, release_ms: float,
               knee_db: float = 6.0, rms_ms: float = 10.0, makeup_db: float = 0.0, hop: int = 48):
    """feed-forward RMS compressor with soft knee; returns (y, gain_db_ctrl)"""
    lev = level_db(x, rms_ms / 1000, hop)
    over = lev - thresh_db
    k = knee_db
    slope = 1 - 1 / ratio
    gr = np.where(over <= -k / 2, 0.0,
                  np.where(over >= k / 2, over * slope, slope * (over + k / 2) ** 2 / (2 * k)))
    a_att = np.exp(-hop / (SR * attack_ms / 1000))
    a_rel = np.exp(-hop / (SR * release_ms / 1000))
    grs = _ar_smooth(gr, a_att, a_rel)
    g_db = makeup_db - grs
    g = 10 ** (gain_curve_to_audio(g_db, len(x), hop) / 20)
    return x * (g[:, None] if x.ndim == 2 else g), g_db


def true_peak_db(x, os: int = 4) -> float:
    up = signal.resample_poly(x, os, 1, axis=0)
    return 20 * np.log10(np.abs(up).max() + 1e-12)


def tp_limiter(x, ceiling_db: float = -1.2, lookahead_ms: float = 1.5, release_ms: float = 60.0,
               os: int = 4):
    """true-peak brickwall limiter: required gain from 4x-oversampled peaks, forward min over
    the look-ahead window, causal moving average (guarantees gain <= required gain at every
    sample), then a one-pole release."""
    c = 10 ** (ceiling_db / 20)
    up = signal.resample_poly(x, os, 1, axis=0)
    pk = np.abs(up).max(1).reshape(-1, os).max(1)[:len(x)]
    pk = maximum_filter1d(pk, 3)
    req = np.minimum(1.0, c / np.maximum(pk, 1e-12))
    L = max(1, ts(lookahead_ms / 1000))
    if L % 2:
        L += 1
    h = L // 2
    cmin = minimum_filter1d(req, size=L + 1, mode="nearest")            # window [n-h, n+h]
    g1 = np.concatenate([cmin[h:], np.full(h, cmin[-1])])                 # window [n, n+L]
    cav = uniform_filter1d(g1, size=L + 1, mode="nearest")               # window [n-h, n+h]
    y = np.concatenate([np.full(h, cav[0]), cav[:-h]])                    # window [n-L, n]
    y = np.minimum(y, req)
    a = np.exp(-1.0 / (SR * release_ms / 1000))
    yl = y.tolist()
    r = np.empty(len(yl))
    s = yl[0]
    for i, v in enumerate(yl):
        s = a * s + (1 - a) * v
        if s > v:
            s = v
        r[i] = s
    return x * r[:, None], r


def tape_sat(x, drive_db: float = 3.0, bias: float = 0.05):
    """gentle tape-style saturation: 2x oversampled asymmetric tanh, unity small-signal gain"""
    g = 10 ** (drive_db / 20)
    up = signal.resample_poly(x, 2, 1, axis=0)
    tb = np.tanh(g * bias)
    y = (np.tanh(g * (up + bias)) - tb) / (g * (1 - tb ** 2))
    y = signal.resample_poly(y, 1, 2, axis=0)[:len(x)]
    y = sos_filt(y, butter("highpass", 12.0, 1))
    return y


# ============================================================================ loudness
K_SOS = np.array([
    [1.53512485958697, -2.69169618940638, 1.19839281085285, 1.0, -1.69065929318241, 0.73248077421585],
    [1.0, -2.0, 1.0, 1.0, -1.99004745483398, 0.99007225036621],
])


def kweight(x):
    return signal.sosfilt(K_SOS, x, axis=0)


def loudness_curve(x, win: float = 3.0, hop: float = 0.1):
    """short-term (win=3) or momentary (win=0.4) loudness in LUFS, centred windows"""
    z = kweight(x if x.ndim == 2 else x[:, None])
    p = (z ** 2).sum(1)
    pm = uniform_filter1d(p, ts(win), mode="constant")
    idx = np.arange(0, len(x), ts(hop))
    return idx / SR, -0.691 + 10 * np.log10(pm[idx] + 1e-14)


def integrated_lufs(x) -> float:
    import pyloudnorm as pyln
    return float(pyln.Meter(SR).integrated_loudness(x))


def lra(x) -> float:
    import pyloudnorm as pyln
    return float(pyln.Meter(SR).loudness_range(x))


def gated_loudness(x, mask) -> float:
    """loudness (LUFS) of x restricted to samples where mask is True (400 ms blocks, 75% overlap,
    BS.1770 absolute+relative gating) -- used to compare stems over speech regions only"""
    z = kweight(x if x.ndim == 2 else x[:, None])
    p = (z ** 2).sum(1)
    blk, hopb = ts(0.4), ts(0.1)
    vals = []
    for i in range(0, len(x) - blk, hopb):
        if mask[i:i + blk].mean() > 0.8:
            vals.append(p[i:i + blk].mean())
    vals = np.array(vals)
    if not len(vals):
        return -np.inf
    lk = -0.691 + 10 * np.log10(vals + 1e-14)
    vals = vals[lk > -70]
    rel = -0.691 + 10 * np.log10(vals.mean()) - 10
    lk = -0.691 + 10 * np.log10(vals + 1e-14)
    vals = vals[lk > rel]
    return float(-0.691 + 10 * np.log10(vals.mean()))


# ============================================================================ io
def write_wav(path: str, x, subtype: str = "PCM_24"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.asarray(x, np.float64), SR, subtype=subtype)


def read_wav(path: str):
    x, sr = sf.read(path, always_2d=False)
    assert sr == SR, (path, sr)
    return x.astype(np.float64)
