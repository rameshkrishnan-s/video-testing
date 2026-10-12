#!/usr/bin/env python3
"""Synthesised sound effects for "You've Never Left Space".

    audio/.venv/bin/python audio/sfx.py

Writes
  audio/out/sfx/<name>.wav   each effect on its own (48 kHz stereo, peak -1 dBFS, unity gain)
  audio/out/sfx_cues.json    cue list: name, time (sync point on the video timeline), start
                             (= time - anchor; where the file begins), anchor, gain_db, ref
  audio/out/sfx.wav          the SFX stem (all cues at their gain_db), exactly 60.000 s, the
                             tail past 60 s folded onto the start (loop-consistent)

Every cue is placed from audio/out/timeline.json word timings; tonal effects take their
pitches from the score's harmony at that moment (music.arrangement), so they stay in key.
Nothing here uses samples: noise is shaped in the STFT domain, tones are additive.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dsp import (N, NT, OUT, SR, TWO_PI, Timeline, bp_mag, butter, cos01, env_ar, env_perc, fold,  # noqa: E402
                 lp_mag, make_ir, nearest_tone, noise_tv, pan_gains, place, reverb_tail, sos_filt, ts,
                 write_wav)
from music import arrangement, bell, chord_at, tones  # noqa: E402

SEED = 4242
_IR: dict = {}


def ir(name: str):
    if name not in _IR:
        _IR[name] = {
            "room": lambda: make_ir(0.9, 0.4, seed=21, predelay=0.008, hp=200, length=1.2),
            "hall": lambda: make_ir(3.4, 1.4, seed=22, predelay=0.02, hp=150),
            "space": lambda: make_ir(6.5, 2.6, seed=23, predelay=0.035, hp=250, lp=11000),
            "dark": lambda: make_ir(2.8, 0.7, seed=24, predelay=0.012, hp=50, lp=4500),
        }[name]()
    return _IR[name]


def rng(k: int):
    return np.random.default_rng(SEED + k)


def st(x, pan=0.0):
    if x.ndim == 2:
        return x
    gl, gr = pan_gains(pan)
    return np.stack([x * gl, x * gr], 1)


def verb(x, name, wet, dry=1.0):
    """dry + wet (full tail kept)"""
    x = st(x)
    y = reverb_tail(x, ir(name)) * wet
    y[:len(x)] += dry * x
    return trim(y)


def trim(y, floor_db=-80.0):
    a = np.abs(y).max(1) if y.ndim == 2 else np.abs(y)
    thr = a.max() * 10 ** (floor_db / 20)
    idx = np.where(a > thr)[0]
    end = (idx[-1] + 1) if len(idx) else len(y)
    y = y[:end]
    k = min(len(y), ts(0.02))
    y[-k:] *= cos01(1 - np.arange(k) / k)[:, None] if y.ndim == 2 else cos01(1 - np.arange(k) / k)
    return y


def width(y, w):
    m = 0.5 * (y[:, 0] + y[:, 1])
    s = 0.5 * (y[:, 0] - y[:, 1]) * w
    return np.stack([m + s, m - s], 1)


# ----------------------------------------------------------------------------- primitives
def boom(dur, f0, f1, sweep, decay, attack=0.003, drive=1.8, lp=350.0):
    """pitch-dropping sine sub with soft saturation (harmonics so it reads on small speakers)"""
    n = ts(dur)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / sweep)
    y = np.sin(TWO_PI * np.cumsum(f) / SR) * env_perc(n, attack, decay)
    y = np.tanh(drive * y) / np.tanh(drive)
    y = sos_filt(y, butter("lowpass", lp, 2))
    return y * env_ar(n, 0.0005, 0.05)


def noise_burst(dur, seed, lo, hi, attack, tau, stereo=True):
    n = ts(dur)
    y = noise_tv(dur, lambda f, tt: (1 - lp_mag(f, lo, 2)) * lp_mag(f, hi, 2), seed, stereo=stereo)
    e = env_perc(n, attack, tau) * env_ar(n, 0.0002, 0.02)
    return y * (e[:, None] if stereo else e)


def whoosh(dur, fc, q, env, seed, flange=None, w_fn=None, tilt=0.0):
    """band-pass swept noise. fc(tt)->Hz, env(tt)->gain (tt = seconds from start),
    flange(tt)->comb delay (s) or None, w_fn(tt)-> stereo width"""
    def shape(f, tt):
        m = bp_mag(f, fc(tt), q) + 0.35 * bp_mag(f, 2.1 * fc(tt), q * 1.3)
        if tilt:
            m = m * (np.maximum(f, 50) / 1000.0) ** tilt
        if flange is not None:
            m = m * np.sqrt(1.49 + 1.4 * np.cos(TWO_PI * f * flange(tt))) / 1.7
        return m
    y = noise_tv(dur, shape, seed)
    tt = np.arange(len(y)) / SR
    y = y * env(tt)[:, None]
    if w_fn is not None:
        m = 0.5 * (y[:, 0] + y[:, 1])
        s = 0.5 * (y[:, 0] - y[:, 1]) * w_fn(tt)
        y = np.stack([m + s, m - s], 1)
    return y * env_ar(len(y), 0.003, 0.03)[:, None]


def tick(f, decay=0.004, click=0.35, seed=0, dur=0.05):
    n = ts(dur)
    t = np.arange(n) / SR
    y = np.sin(TWO_PI * f * t) * env_perc(n, 0.0003, decay)
    c = rng(seed).standard_normal(n) * env_perc(n, 0.0002, 0.0012)
    c = sos_filt(c, butter("highpass", 6000, 2))
    return (y + click * c) * env_ar(n, 0.0001, 0.005)


def reverse_swell(src, irname, length, fade_in=0.15):
    """reverse reverb: wet tail of src, reversed, cropped to `length` (loudest at the end)"""
    wet = reverb_tail(st(src), ir(irname))[::-1]
    y = wet[-ts(length):].copy()
    y *= (cos01(np.arange(len(y)) / ts(fade_in)) * env_ar(len(y), 0.0001, 0.004))[:, None]
    return y


# ----------------------------------------------------------------------------- effects
def fx_hook_boom():
    b = boom(2.6, 78.0, 34.0, 0.22, 0.85, attack=0.002)
    air = noise_burst(1.0, SEED + 1, 2800, 13000, 0.004, 0.16)
    air = verb(air, "space", 0.7, 1.0)
    y = np.zeros((max(len(air), len(b)), 2))
    y[:len(b)] += st(b) * 1.0
    y[:len(air)] += air * 0.22
    return y, 0.0


def fx_hook_pop(strength=1.0, seed=0):
    n = ts(0.12)
    t = np.arange(n) / SR
    f = 170 + 300 * np.exp(-t / 0.012)
    pop = np.sin(TWO_PI * np.cumsum(f) / SR) * env_perc(n, 0.001, 0.028)
    tk = tick(7200, 0.002, 0.6, seed=seed, dur=0.12)
    y = 0.8 * pop + 0.35 * strength * tk
    return verb(y, "room", 0.25), 0.0


def fx_ping(f0, i, seed):
    """shimmering glass ping; i = 0,1,2 -> more distant (more reverb, darker, narrower)"""
    r = rng(seed)
    n = ts(2.2)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for ratio, a, d in ((1.0, 1.0, 1.1), (2.0, 0.22, 0.7), (3.0, 0.07, 0.35), (4.16, 0.05, 0.2)):
        for s in (-1, 1):
            fd = f0 * ratio * 2 ** (s * 4.0 / 2400)
            y += 0.5 * a * np.exp(-t / d) * np.sin(TWO_PI * fd * t + 0.002 * fd * np.sin(TWO_PI * 5.5 * t) / 5.5 + r.uniform(0, TWO_PI))
    y *= env_ar(n, 0.0015, 0.05)
    shimmer = 0.25 * np.sin(TWO_PI * 2 * f0 * t) * cos01(t / 0.25) * np.exp(-t / 0.9)
    dry_lp = [10000, 6500, 4200][i]
    y = sos_filt(y, butter("lowpass", dry_lp, 2))
    wet_amt = [0.55, 0.85, 1.2][i]
    dry_amt = [1.0, 0.6, 0.35][i]
    pan = [-0.25, 0.25, 0.0][i]
    out = verb(st(y, pan) * dry_amt, "space", wet_amt / max(dry_amt, 1e-3), 1.0)
    sh = reverb_tail(st(shimmer), ir("space")) * 0.6
    z = np.zeros((max(len(out), len(sh)), 2))
    z[:len(out)] += out
    z[:len(sh)] += sh
    return trim(z), 0.0


def fx_lockon(f1, f2):
    n = ts(0.4)
    t = np.arange(n) / SR
    b1 = np.sin(TWO_PI * f1 * t) * env_perc(n, 0.001, 0.012)
    d = ts(0.075)
    b2 = np.zeros(n)
    b2[d:] = np.sin(TWO_PI * f2 * t[:n - d]) * env_perc(n - d, 0.001, 0.03)
    th = np.zeros(n)
    th[d:] = boom(0.4 - 0.075, 150, 85, 0.02, 0.04, attack=0.002, drive=1.2, lp=600)
    y = 0.55 * b1 + 0.5 * b2 + 0.6 * th
    return verb(y, "room", 0.3), 0.0


def fx_riser(dur, seed):
    n = ts(dur)
    t = np.arange(n) / SR
    x = t / dur
    nz = noise_tv(dur, lambda f, tt: bp_mag(f, 300 * (5000 / 300) ** ((tt / dur) ** 1.3), 1.4), seed)
    tone = np.zeros(n)
    f0 = 146.83 * 4 ** (x ** 1.5)
    for det in (-9, 0, 9):
        ph = TWO_PI * np.cumsum(f0 * 2 ** (det / 1200)) / SR + rng(seed + det).uniform(0, TWO_PI)
        for k in range(1, 30):
            a = 1.0 / k * lp_mag(k * f0, 3500, 2)
            if (k * f0).max() > 14000:
                break
            tone += a * np.sin(k * ph)
    tone /= np.abs(tone).max()
    e = np.exp(4.2 * (x - 1)) * env_ar(n, 0.05, 0.006)
    y = (nz / np.abs(nz).max() * 0.8 + st(tone) * 0.35) * e[:, None]
    y = width(y, 0.4 + 0.8 * 1.0)
    return y, dur


def fx_zoom_out_whoosh():
    dur, pre = 1.9, 0.12
    fc = lambda tt: 120 + 2600 * np.exp(-np.maximum(tt - pre * 0.5, 0) / 0.45)  # noqa: E731
    env = lambda tt: np.where(tt < pre, (tt / pre) ** 2, np.exp(-(tt - pre) / 0.55))  # noqa: E731
    fl = lambda tt: 0.0006 + 0.004 * np.clip(tt / dur, 0, 1)  # noqa: E731
    y = whoosh(dur, fc, 1.1, env, SEED + 11, flange=fl, w_fn=lambda tt: 0.6 + 0.6 * np.clip(tt / 0.6, 0, 1))
    return y, pre


def fx_impact(seed):
    b = boom(3.2, 60.0, 30.0, 0.16, 1.05, attack=0.002, drive=2.2)
    punch = boom(0.5, 140.0, 62.0, 0.03, 0.09, attack=0.001, drive=1.5, lp=900)
    tr = noise_burst(0.12, seed, 120, 2400, 0.0008, 0.012)
    y = np.zeros((len(b), 2))
    y += st(b) * 1.0
    y[:len(punch)] += st(punch) * 0.55
    y[:len(tr)] += tr * 0.18
    return verb(y, "dark", 0.3), 0.0


def fx_ruler_ticks(times):
    t0 = times[0]
    dur = times[-1] - t0 + 0.3
    y = np.zeros((ts(dur), 2))
    for i, tt in enumerate(times):
        f = 2800 * 2 ** (i / (len(times) - 1))
        place(y, tick(f, 0.005, 0.25, seed=100 + i), tt - t0, 0.7 + 0.3 * i / (len(times) - 1),
              pan=-0.1 + 0.2 * i / (len(times) - 1))
    return verb(y, "room", 0.35), 0.0


def fx_car_whoosh():
    dur, pre = 0.8, 0.08
    fc = lambda tt: 450 * (2700 / 450) ** np.clip(tt / 0.55, 0, 1)  # noqa: E731
    env = lambda tt: np.where(tt < 0.28, cos01(tt / 0.28), np.exp(-(tt - 0.28) / 0.16))  # noqa: E731
    y = whoosh(dur, fc, 2.0, env, SEED + 21)
    t = np.arange(len(y)) / SR
    th = (np.clip(t / dur, 0, 1) - 0.5) * 1.2           # left -> right
    m = y.mean(1)
    gl, gr = pan_gains(th)
    return np.stack([m * gl, m * gr], 1) * 1.4, pre


def fx_chime(f1, f2, seed):
    r = rng(seed)
    a = bell(f1, 2.0, r, ratios=(1.0, 2.0, 2.76), amps=(1.0, 0.12, 0.08), decays=(1.1, 0.5, 0.25), attack=0.003)
    b = bell(f2, 2.0, r, ratios=(1.0, 2.0, 2.76), amps=(1.0, 0.12, 0.08), decays=(1.3, 0.5, 0.25), attack=0.003)
    y = np.zeros(ts(2.2))
    y[:len(a)] += 0.8 * a
    k = ts(0.11)
    y[k:k + len(b)] += b[:len(y) - k]
    return verb(y, "hall", 0.5), 0.0


def fx_racing_whoosh():
    dur, pre = 1.7, 0.3
    def fc(tt):
        up = 180 * (3500 / 180) ** np.clip(tt / (pre + 0.15), 0, 1)
        return np.where(tt < pre + 0.15, up, 900 + 2600 * np.exp(-(tt - pre - 0.15) / 0.35))
    env = lambda tt: np.where(tt < pre + 0.08, np.exp(4.0 * (tt / (pre + 0.08) - 1)), np.exp(-(tt - pre - 0.08) / 0.3))  # noqa: E731
    fl = lambda tt: 0.004 - 0.0035 * np.clip(tt / dur, 0, 1)  # noqa: E731
    y = whoosh(dur, fc, 1.2, env, SEED + 31, flange=fl, w_fn=lambda tt: 0.5 + 0.7 * np.clip((tt - pre) / 0.5, 0, 1))
    rum = noise_tv(dur, lambda f, tt: lp_mag(f, 140, 3) * (1 - lp_mag(f, 35, 2)), SEED + 32)
    rum *= env(np.arange(len(rum)) / SR)[:, None]
    return y + 0.8 * rum / (np.abs(rum).max() + 1e-9) * np.abs(y).max(), pre


def fx_counter_ticks(t0, t1):
    T = t1 - t0
    r0, r1 = 6.5, 34.0
    k = r1 / r0
    # n(tau) = r0*T/ln(k) * (k^(tau/T) - 1); tick at every integer n
    nmax = r0 * T / np.log(k) * (k - 1)
    taus = [T * np.log(1 + i * np.log(k) / (r0 * T)) / np.log(k) for i in range(int(nmax))]
    taus = [tt for tt in taus if tt < T - 0.03]
    r = rng(41)
    y = np.zeros((ts(T + 0.2), 2))
    for i, tt in enumerate(taus):
        f = 5200 * np.exp(r.normal(0, 0.03)) * (1 + 0.15 * tt / T)
        g = (0.55 + 0.45 * tt / T) * np.exp(r.normal(0, 0.08))
        place(y, tick(f, 0.0025, 0.4, seed=200 + i, dur=0.03), tt, g, pan=0.15 * (1 if i % 2 else -1))
    return verb(y, "room", 0.25), 0.0


def fx_soft_hit(f_glint):
    th = boom(0.9, 96.0, 55.0, 0.05, 0.2, attack=0.003, drive=1.6, lp=500)
    gl = bell(f_glint, 1.6, rng(51), ratios=(1.0, 2.76), amps=(1.0, 0.1), decays=(0.8, 0.2), attack=0.002)
    y = np.zeros(max(len(th), len(gl)))
    y[:len(th)] += th
    y[:len(gl)] += 0.12 * gl
    return verb(y, "room", 0.3), 0.0


def fx_heartbeat():
    lub = boom(0.6, 64.0, 42.0, 0.03, 0.085, attack=0.006, drive=2.0, lp=300)
    dub = boom(0.6, 72.0, 47.0, 0.025, 0.07, attack=0.006, drive=2.0, lp=320)
    y = np.zeros(ts(1.0))
    y[:len(lub)] += lub
    k = ts(0.24)
    y[k:k + len(dub)] += 0.72 * dub[:len(y) - k]
    return verb(y, "dark", 0.15), 0.0


def fx_reverse_swell(pcs, length, seed, irname="hall", oct_hz=600.0):
    r = rng(seed)
    src = np.zeros(ts(0.6))
    for j, p in enumerate(sorted(pcs)):
        f = nearest_tone(oct_hz * 2 ** (j / max(1, len(pcs))), [p])
        src += bell(f, 0.6, r, ratios=(1.0, 2.0), amps=(1.0, 0.2), decays=(0.4, 0.2), attack=0.001)
    nb = noise_burst(0.6, seed + 1, 300, 9000, 0.0005, 0.03, stereo=False)
    src = src / np.abs(src).max() * 0.6 + nb / np.abs(nb).max() * 0.6
    y = reverse_swell(src, irname, length)
    return y / np.abs(y).max(), length


def fx_supernova():
    b = boom(5.5, 52.0, 24.0, 0.35, 1.8, attack=0.002, drive=2.4, lp=300)
    rum = noise_tv(5.5, lambda f, tt: lp_mag(f, 200, 3) * (1 - lp_mag(f, 28, 2)) * np.exp(-tt / 1.7), SEED + 61)
    t = np.arange(len(rum)) / SR
    flut = 1 + 0.35 * np.sin(TWO_PI * 3.1 * t + 1) * np.sin(TWO_PI * 0.7 * t)
    rum = rum / np.abs(rum).max() * (flut * cos01(t / 0.04))[:, None]
    crack = noise_burst(0.2, SEED + 62, 200, 3200, 0.0005, 0.022)
    sw = whoosh(1.8, lambda tt: 90 + 1700 * np.exp(-tt / 0.4), 1.0,
                lambda tt: cos01(tt / 0.03) * np.exp(-tt / 0.5), SEED + 63)
    y = np.zeros((len(b), 2))
    y += st(b) * 1.0
    y += rum * 0.5
    y[:len(crack)] += crack / np.abs(crack).max() * 0.3
    y[:len(sw)] += sw / np.abs(sw).max() * 0.25
    return verb(y, "dark", 0.35), 0.0


def fx_debris(dur=3.6):
    r = rng(71)
    y = np.zeros((ts(dur), 2))
    t = 0.0
    while t < dur - 0.05:
        lam = 70 * np.exp(-t / 0.7) + 3.0
        t += r.exponential(1 / lam)
        if t >= dur - 0.05:
            break
        n = ts(r.uniform(0.001, 0.004))
        fc = np.exp(r.uniform(np.log(1500), np.log(8000)))
        c = r.standard_normal(n + 64)
        c = sos_filt(c, butter("bandpass", [fc / 1.4, min(fc * 1.4, 20000)], 2))[:n + 64] * env_perc(n + 64, 0.0002, n / SR / 2.5)
        g = np.exp(r.normal(0, 0.6)) * np.exp(-t / 1.4)
        place(y, c, t, g, pan=r.uniform(-0.9, 0.9))
        if r.random() < 0.04:
            place(y, boom(0.3, 130, 60, 0.02, 0.05, attack=0.001, drive=1.2, lp=700), t, 0.25 * np.exp(-t / 1.4),
                  pan=r.uniform(-0.6, 0.6))
    return verb(y, "space", 0.6), 0.0


def fx_inhale(pcs, length):
    sw, _ = fx_reverse_swell(pcs, length, 81, "hall", oct_hz=520.0)
    up = whoosh(length, lambda tt: 400 * (2600 / 400) ** (tt / length), 1.6,
                lambda tt: np.exp(3.0 * (tt / length - 1)), SEED + 82)
    up *= env_ar(len(up), 0.05, 0.004)[:, None]
    y = sw[:len(up)] + 0.45 * up / np.abs(up).max()
    return y / np.abs(y).max(), length


def fx_glass(f0, i, seed):
    r = rng(seed)
    n = ts(2.6)
    t = np.arange(n) / SR
    det = [4.0, 6.0, 11.0][i]
    y = np.zeros(n)
    for ratio, a, d in ((1.0, 1.0, 1.8), (2.0, 0.12, 0.9), (3.01, 0.04, 0.4)):
        for s in (-1, 1):
            y += 0.5 * a * np.exp(-t / d) * np.sin(TWO_PI * f0 * ratio * 2 ** (s * det / 2400) * t + r.uniform(0, TWO_PI))
    y *= env_ar(n, 0.025, 0.1)
    if i == 2:
        y = sos_filt(y, butter("lowpass", 1800, 2))
    pan = [-0.2, 0.25, 0.0][i]
    return verb(st(y, pan), "hall", [0.45, 0.75, 1.1][i], [1.0, 0.75, 0.45][i]), 0.0


def fx_recede(f_tone, seed, pan):
    dur, pre = 1.1, 0.03
    fc = lambda tt: 350 + 1900 * np.exp(-tt / 0.3)  # noqa: E731
    env = lambda tt: np.where(tt < 0.04, cos01(tt / 0.04), np.exp(-(tt - 0.04) / 0.33))  # noqa: E731
    y = whoosh(dur, fc, 1.8, env, seed)
    y = y / np.abs(y).max()
    n = len(y)
    t = np.arange(n) / SR
    fr = f_tone * 2 ** (-3 / 12 * (1 - np.exp(-t / 0.35)))
    tone = np.zeros(n)
    for ratio, a in ((1.0, 1.0), (1.5, 0.4)):
        tone += a * np.sin(TWO_PI * np.cumsum(fr * ratio) / SR)
    tone *= env(t) * env_ar(n, 0.004, 0.05)
    y = st(y.mean(1), pan) * 0.8 + st(tone, pan) * 0.22
    dry = y * np.exp(-t / 0.5)[:, None]
    wet = reverb_tail(y, ir("space")) * 0.6
    wet[:n] += dry
    return trim(wet), pre


def fx_twinkle(f0):
    r = rng(91)
    y = np.zeros(ts(1.0))
    for k, (dt, a) in enumerate(((0.0, 1.0), (0.13, 0.45), (0.31, 0.25))):
        b = bell(f0, 0.69, r, ratios=(1.0, 2.76), amps=(1.0, 0.1), decays=(0.35, 0.1), attack=0.002)
        i = ts(dt)
        y[i:i + len(b)] += a * b[:len(y) - i]
    return verb(st(y, 0.3), "space", 2.0, 0.35), 0.0


def fx_reverse_cymbal(length):
    r = rng(101)
    dur = 3.0
    n = ts(dur)
    t = np.arange(n) / SR
    metal = np.zeros(n)
    for f in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0):
        ph = TWO_PI * f * t + r.uniform(0, TWO_PI)
        for k in range(1, 60, 2):                       # band-limited square partials
            if k * f > 16000:
                break
            metal += np.sin(k * ph) / k
    metal = sos_filt(metal, butter("highpass", 5500, 4)) * np.exp(-t / 0.9)
    nz = noise_tv(dur, lambda f, tt: (1 - lp_mag(f, 4500, 2)) * lp_mag(f, 15000, 2) * np.exp(-tt / (0.6 + 0.6 * np.exp(-f / 6000))), SEED + 102)
    cym = st(metal / np.abs(metal).max()) * 0.35 + nz / np.abs(nz).max()
    cym = verb(cym, "hall", 0.35)
    y = cym[::-1][-ts(length):].copy()
    y *= (cos01(np.arange(len(y)) / ts(0.25)) * env_ar(len(y), 0.0001, 0.004))[:, None]
    return y / np.abs(y).max(), length


def fx_warp():
    dur = 1.5
    tp = 0.55
    def fc(tt):
        return np.where(tt < tp, 250 * (4000 / 250) ** (tt / tp), 700 + 3300 * np.exp(-(tt - tp) / 0.18))
    env = lambda tt: np.where(tt < tp, np.exp(3.5 * (tt / tp - 1)), np.exp(-(tt - tp) / 0.28))  # noqa: E731
    fl = lambda tt: np.where(tt < tp, 0.006 - 0.0055 * tt / tp, 0.0005 + 0.002 * (tt - tp))  # noqa: E731
    y = whoosh(dur, fc, 1.4, env, SEED + 111, flange=fl, w_fn=lambda tt: 0.25 + 1.0 * np.clip((tt - tp + 0.15) / 0.3, 0, 1))
    push = noise_tv(dur, lambda f, tt: lp_mag(f, 180, 3) * (1 - lp_mag(f, 40, 2)), SEED + 112)
    push = push / np.abs(push).max() * (cos01((np.arange(len(push)) / SR - tp + 0.2) / 0.2) * np.exp(-np.maximum(np.arange(len(push)) / SR - tp, 0) / 0.3))[:, None]
    y = y / np.abs(y).max() + 0.5 * push
    return y, 0.0


def fx_warm_impact():
    b = boom(3.5, 74.0, 36.7, 0.12, 1.0, attack=0.005, drive=1.6)
    body = noise_tv(1.5, lambda f, tt: lp_mag(f, 420, 2) * (1 - lp_mag(f, 45, 2)), SEED + 121)
    tb = np.arange(len(body)) / SR
    body = body / np.abs(body).max() * (env_perc(len(body), 0.015, 0.32))[:, None]
    tr = noise_burst(0.1, SEED + 122, 150, 1800, 0.001, 0.008)
    y = np.zeros((len(b), 2))
    y += st(b)
    y[:len(body)] += body * 0.35
    y[:len(tr)] += tr / np.abs(tr).max() * 0.12
    del tb
    return verb(y, "hall", 0.4), 0.0


def fx_shimmer(freqs):
    r = rng(131)
    dur = 3.0
    n = ts(dur)
    t = np.arange(n) / SR
    y = np.zeros((n, 2))
    for j, f in enumerate(freqs):
        trem = 1 + 0.5 * np.sin(TWO_PI * r.uniform(5, 11) * t + r.uniform(0, TWO_PI)) * np.sin(TWO_PI * r.uniform(0.7, 1.7) * t)
        s = np.sin(TWO_PI * f * t + r.uniform(0, TWO_PI)) * trem * cos01(t / 0.18) * np.exp(-t / 1.3) * 0.8 ** j
        y += st(s, -0.7 + 1.4 * j / max(1, len(freqs) - 1))
    y *= env_ar(n, 0.01, 0.2)[:, None]
    return verb(y, "space", 0.9), 0.0


# ----------------------------------------------------------------------------- cue sheet
def cue_sheet(tl: Timeline, A: dict):
    """(name, generator, sync time, gain_db, ref) for every effect"""
    w = tl.t
    pcs_at = lambda t: tones(chord_at(A, t))  # noqa: E731
    C = []

    def add(name, gen, t, gain_db, ref):
        C.append((name, gen, t, gain_db, ref))

    add("hook_boom", fx_hook_boom, 0.0, -9.0, "t=0 (hook start)")
    for i, (word, strength) in enumerate((("always", 0.7), ("talk", 0.8), ("space", 1.0), ("somewhere", 0.85), ("else?", 1.0))):
        add(f"hook_pop_{i + 1}_{word.strip('?')}", lambda s=strength, i=i: fx_hook_pop(s, seed=10 + i),
            w("hook", word) - 0.012, -29.0 + 2.0 * (strength - 1), f"hook:'{word}'")
    for i, word in enumerate(("Out", "Up", "Far")):
        t = w("echo", word)
        f = nearest_tone([880.0, 1245.0, 1760.0][i], pcs_at(t))
        add(f"echo_ping_{i + 1}_{word.lower()}", lambda f=f, i=i: fx_ping(f, i, 20 + i), t, [-25.0, -27.5, -30.0][i], f"echo:'{word}'")
    t = w("loop", "you.")
    p = pcs_at(t)
    add("loop_lockon", lambda: fx_lockon(nearest_tone(1760, p), nearest_tone(2640, p)), t, -27.0, "loop:'you.'")
    add("truth_riser", lambda: fx_riser(1.2, SEED + 5), w("truth", "never"), -24.0, "truth: 1.2 s ending on 'never'")
    add("never_whoosh", fx_zoom_out_whoosh, w("truth", "never"), -20.0, "truth:'never' (zoom-out)")
    add("never_impact", lambda: fx_impact(SEED + 6), w("truth", "never"), -6.0, "truth:'never'")
    tj, tu = w("distance", "Just"), w("distance", "up.")
    ticks = list(np.linspace(tj, tu, 11))
    add("distance_ruler_ticks", lambda: fx_ruler_ticks(ticks), tj, -31.0, "distance:'Just'..'up.' (11 ticks, 0-100 km)")
    add("distance_car_whoosh", fx_car_whoosh, w("distance", "car"), -27.0, "distance:'car'")
    t = w("distance", "hour.")
    p = pcs_at(t)
    add("distance_hour_chime", lambda: fx_chime(nearest_tone(784, p), nearest_tone(1175, p), 7), t, -27.0, "distance:'hour.'")
    add("speed_racing_whoosh", fx_racing_whoosh, w("speed", "racing"), -22.0, "speed:'racing'")
    tr, th = w("speed", "racing"), w("speed", "hour.")
    add("speed_counter_ticks", lambda: fx_counter_ticks(tr, th), tr, -34.0, "speed:'racing'..'hour.' (accelerating)")
    p = pcs_at(th)
    add("speed_counter_hit", lambda: fx_soft_hit(nearest_tone(1760, p)), th, -13.0, "speed:'hour.'")
    add("stars_heartbeat", fx_heartbeat, w("stars", "blood?"), -8.0, "stars:'blood?'")
    tf = w("stars", "Forged")
    add("stars_reverse_swell", lambda: fx_reverse_swell(pcs_at(tf + 0.01), min(0.8, tf - w("stars", "blood?") - 0.05), 31),
        tf, -19.0, "stars: into 'Forged'")
    te = w("stars", "exploded")
    add("stars_supernova_boom", fx_supernova, te, -4.0, "stars:'exploded'")
    add("stars_supernova_debris", fx_debris, te + 0.04, -25.0, "stars:'exploded' (+40 ms)")
    tq = tl.scene_start("question")
    add("question_inhale", lambda: fx_inhale(pcs_at(tq - 0.5), 1.0), tq, -17.0, "question scene start (ends there)")
    for i, word in enumerate(("distance.", "feels,", "Blurrier.")):
        t = w("psych", word)
        f = nearest_tone([1175.0, 880.0, 660.0][i], pcs_at(t))
        add(f"psych_glass_{i + 1}", lambda f=f, i=i: fx_glass(f, i, 40 + i), t, [-34.0, -35.5, -36.0][i], f"psych:'{word}'")
    for i, (word, pan) in enumerate((("dreams.", -0.35), ("goals.", 0.35), ("life", 0.0))):
        t = w("life", word)
        f = nearest_tone(700.0, pcs_at(t))
        add(f"life_recede_{i + 1}_{word.strip('.')}", lambda f=f, i=i, pan=pan: fx_recede(f, SEED + 50 + i, pan), t,
            [-24.0, -25.0, -25.5][i], f"life:'{word}'")
    t = w("life", "someday.")
    add("life_someday_twinkle", lambda: fx_twinkle(nearest_tone(2349, pcs_at(t))), t, -30.0, "life:'someday.'")
    tb = w("payoff", "But")
    add("payoff_reverse_cymbal", lambda: fx_reverse_cymbal(1.5), tb, -22.0, "payoff: into 'But'")
    add("payoff_warp_whoosh", fx_warp, tb, -18.0, "payoff:'But' (toward camera)")
    add("payoff_already_impact", fx_warm_impact, w("payoff", "already"), -7.0, "payoff:'already'")
    t = w("final", "living")
    p = pcs_at(t)
    add("final_living_shimmer", lambda: fx_shimmer([nearest_tone(f, p) for f in (1175, 1480, 1760, 2637, 3520)]), t, -27.0,
        "final:'living'")
    return C


def render(tl: Timeline | None = None, verbose: bool = True):
    tl = tl or Timeline()
    A = arrangement(tl)
    stem = np.zeros((NT, 2))
    cues = []
    os.makedirs(os.path.join(OUT, "sfx"), exist_ok=True)
    for name, gen, t, gain_db, ref in cue_sheet(tl, A):
        y, anchor = gen()
        y = st(np.asarray(y, float))
        y = y / (np.abs(y).max() + 1e-12) * 10 ** (-1 / 20)       # file: peak -1 dBFS
        start = t - anchor
        write_wav(os.path.join(OUT, "sfx", f"{name}.wav"), y)
        place(stem, y, start, 10 ** (gain_db / 20))
        cues.append({"name": name, "time": round(t, 4), "start": round(start, 4), "anchor": round(anchor, 4),
                     "duration": round(len(y) / SR, 3), "gain_db": gain_db, "ref": ref, "file": f"sfx/{name}.wav"})
        if verbose:
            print(f"  {name:28s} t={t:7.3f}  start={start:7.3f}  {len(y) / SR:5.2f}s  {gain_db:+6.1f} dB   {ref}")
    stem = fold(stem, N)
    return stem, cues


def main():
    stem, cues = render()
    write_wav(os.path.join(OUT, "sfx.wav"), stem)
    with open(os.path.join(OUT, "sfx_cues.json"), "w") as f:
        json.dump({"sample_rate": SR, "note": "time = sync point (s) on the 60 s timeline; the file starts at "
                   "start = time - anchor; files are peak -1 dBFS, gain_db is the level used in sfx.wav",
                   "cues": cues}, f, indent=2)
    print(f"wrote sfx.wav, sfx_cues.json and {len(cues)} files in out/sfx/  (stem peak "
          f"{20 * np.log10(np.abs(stem).max()):.1f} dBFS)")


if __name__ == "__main__":
    main()
