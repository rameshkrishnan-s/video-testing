#!/usr/bin/env python3
"""Original procedural score for "You've Never Left Space" -> audio/out/music.wav

    audio/.venv/bin/python audio/music.py

48 kHz stereo, exactly 60.000 s, D minor. Every section boundary, tempo and hit point is
derived from audio/out/timeline.json (see arrangement()), so the score follows the VO if
its timing changes:

  1 MYSTERY      0 -> "never"            low D drone, airy Dm(add9) pad with slow filter
                                         motion, seeded inharmonic "star" bells
  2 WONDER       "never" -> question     Dm9 Bbmaj9 Fadd9 Cadd9 at ~84 BPM (tempo fitted so
                                         that "exploded" lands on a downbeat), opening pad,
                                         sub pulse, 8th-note pluck arp with ping-pong delay;
                                         steps up at the orbit scene, pulls back for "blood?",
                                         swells into the supernova
  3 DROP-OUT     question scene          dry signal cut, reverb tail decays, one soft A5 tone
  4 REFLECTIVE   psych + life            felt-piano melody over Bbmaj9 Gm9 Dm9 Cadd9 ...,
                                         pad returns gradually (tempo fitted so "But" lands
                                         on beat 3)
  5 BLOOM        riser -> "But" -> Bb(add9) swell -> "already": D major (Picardy lift) with
                 pad + formant choir + sub swell -> G/D -> D -> settles back into the opening
                 drone/pad colour; the bed is periodic over 60 s so the loop point is seamless.

Synthesis is additive (every partial is band-limited by construction: no aliasing), the
filter motion is applied per partial, reverbs are FFT convolutions with generated
decaying-noise IRs, and the bus gets voice-carving EQ, tape saturation and glue compression.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dsp import (DUR, N, NT, OUT, SR, TWO_PI, Timeline, butter, circular, compressor, convolve,  # noqa: E402
                 cos01, curve, env_ar, env_perc, fold, hz, integrated_lufs, lp_mag, make_ir,
                 noise_tv, pan_gains, peq, periodic_noise, pingpong, place, shelf, sos_filt,
                 tape_sat, ts, write_wav, pc)

SEED = 20261012
WORKERS = max(1, min(8, os.cpu_count() or 1))

_JOBS: list = []


def _run_job(i):
    return _JOBS[i]()


def run_parallel(jobs):
    """run zero-arg closures in forked worker processes (closures are inherited, not pickled)"""
    global _JOBS
    _JOBS = list(jobs)
    try:
        if WORKERS == 1 or len(_JOBS) < 2:
            return [j() for j in _JOBS]
        with mp.get_context("fork").Pool(WORKERS) as pool:
            return pool.map(_run_job, range(len(_JOBS)), chunksize=1)
    finally:
        _JOBS = []

# ----------------------------------------------------------------------------- harmony
CH = {
    "Dm(add9)": dict(pad=["D3", "A3", "F4", "E5", "A5"], bass="D2", tones="D F A E"),
    "Dm9": dict(pad=["D3", "F3", "C4", "E4", "A4"], bass="D2", tones="D F A C E",
                arp=["D4", "A4", "E5", "F5", "C5", "A4", "E5", "D5"]),
    "Bbmaj9": dict(pad=["Bb2", "F3", "A3", "D4", "C5"], bass="Bb1", tones="Bb D F A C",
                   arp=["Bb3", "F4", "C5", "D5", "A4", "F4", "C5", "A4"]),
    "Fadd9": dict(pad=["C3", "F3", "A3", "G4", "C5"], bass="F2", tones="F A C G",
                  arp=["F4", "C5", "G5", "A5", "G5", "C5", "A4", "C5"]),
    "Cadd9": dict(pad=["C3", "G3", "E4", "G4", "D5"], bass="C2", tones="C E G D",
                  arp=["C4", "G4", "D5", "E5", "G5", "E5", "D5", "G4"]),
    "Gm9": dict(pad=["G2", "D3", "Bb3", "F4", "A4"], bass="G1", tones="G Bb D F A"),
    "Bbadd9": dict(pad=["Bb2", "F3", "D4", "F4", "C5"], bass="Bb1", tones="Bb D F C",
                   choir=["Bb3", "D4", "F4"]),
    "Dadd9": dict(pad=["D3", "A3", "F#4", "A4", "E5"], bass="D2", tones="D F# A E",
                  choir=["D4", "F#4", "A4", "D5"]),
    "G/D": dict(pad=["D3", "G3", "B3", "D4", "A4"], bass="D2", tones="G B D A",
                choir=["B3", "D4", "G4", "B4"]),
    "tone": dict(pad=[], bass="D2", tones="A D E"),
}


def tones(name: str) -> list[int]:
    return [pc(x) for x in CH[name]["tones"].split()]


def arrangement(tl: Timeline | None = None) -> dict:
    """All musical times, derived from the VO timeline."""
    tl = tl or Timeline()
    A: dict = {}
    A["never"] = tl.t("truth", "never")
    A["exploded"] = tl.t("stars", "exploded")
    nb = max(1, int(round((A["exploded"] - A["never"]) / (240.0 / 84.0))))
    A["barsB"] = nb
    A["barB"] = (A["exploded"] - A["never"]) / nb
    A["beatB"] = A["barB"] / 4
    A["bpmB"] = 60.0 / A["beatB"]
    q = lambda t, step: A["never"] + round((t - A["never"]) / step) * step  # noqa: E731
    A["step"] = q(tl.scene_start("speed"), A["beatB"])            # energy step-up (orbit scene)
    A["pull"] = q(tl.scene_start("stars"), A["beatB"] / 2)        # intimate pull-back ("iron in your blood")
    A["forged"] = tl.t("stars", "Forged")
    A["cut"] = tl.scene_start("question")                          # pattern-interrupt drop-out
    A["psych"] = tl.scene_start("psych")
    A["life"] = tl.scene_start("life")
    A["but"] = tl.t("payoff", "But")
    A["beatD"] = (A["but"] - A["psych"]) / 22.0                    # "But" = beat 3 of bar 6
    A["barD"] = 4 * A["beatD"]
    A["bpmD"] = 60.0 / A["beatD"]
    A["already"] = tl.t("payoff", "already")
    A["final"] = tl.beat_start("final")
    A["already2"] = tl.t("final", "You're")
    A["vo_end"] = tl.vo_end
    A["bed_in0"] = DUR - 3.0
    A["bed_in1"] = DUR - 1.5
    # chord timeline
    ch = [(0.0, A["never"], "Dm(add9)")]
    progB = ["Dm9", "Bbmaj9", "Fadd9", "Cadd9"]
    i = 0
    while True:
        t0 = A["never"] + i * A["barB"]
        if t0 >= A["cut"] - 1e-6:
            break
        ch.append((t0, min(t0 + A["barB"], A["cut"]), progB[i % 4]))
        i += 1
    ch.append((A["cut"], A["psych"], "tone"))
    progD = ["Bbmaj9", "Gm9", "Dm9", "Cadd9", "Bbmaj9", "Gm9"]
    for i, name in enumerate(progD):
        t0 = A["psych"] + i * A["barD"]
        ch.append((t0, min(t0 + A["barD"], A["but"]), name))
    ch += [(A["but"], A["already"], "Bbadd9"), (A["already"], A["final"], "Dadd9"),
           (A["final"], A["already2"], "G/D"), (A["already2"], A["bed_in1"], "Dadd9"),
           (A["bed_in1"], DUR, "Dm(add9)")]
    A["chords"] = ch
    return A


def chord_at(A: dict, t: float) -> str:
    for t0, t1, name in A["chords"]:
        if t0 <= t < t1:
            return name
    return A["chords"][-1][2]


# ----------------------------------------------------------------------------- voices
FORMANTS = {
    "ah": [(800, 80, 1.0), (1150, 90, 0.32), (2900, 120, 0.06), (3500, 130, 0.03)],
    "oo": [(350, 60, 1.0), (620, 70, 0.35), (2700, 100, 0.03)],
}


def formant_env(vowel: str):
    fs = FORMANTS[vowel]

    def f(freq):
        return 0.02 + sum(a / (1 + ((freq - F) / bw) ** 2) for F, bw, a in fs)
    return f


def pad_note(t0: float, dur: float, f0: float, rng, cutoff, attack=0.4, release=0.8, tilt=1.0,
             order=2, res=0.15, unison=3, detune=7.0, spread=0.8, drift=2.5, vib_rate=0.0,
             vib_depth=0.0, vib_delay=0.4, formant=None, max_f=13000.0, kmax=48, ctrl=64):
    """additive detuned-unison voice with a per-partial (alias-free) time-varying low-pass.
    cutoff: float or f(t_abs)->Hz. Returns stereo (n,2)."""
    n = ts(dur)
    tr = np.arange(n) / SR
    tc = np.arange(0, n + ctrl, ctrl) / SR
    fc = cutoff(t0 + tc) if callable(cutoff) else np.full(len(tc), float(cutoff))
    out = np.zeros((n, 2))
    K = int(min(kmax, max_f // (f0 * 1.02)))
    for u in range(unison):
        pos = (u - (unison - 1) / 2) / max(1.0, (unison - 1) / 2) if unison > 1 else 0.0
        r1, r2 = rng.uniform(0.06, 0.22, 2)
        p1, p2 = rng.uniform(0, TWO_PI, 2)
        cents = detune * pos + drift * (0.6 * np.sin(TWO_PI * r1 * tr + p1) + 0.4 * np.sin(TWO_PI * r2 * tr + p2))
        if vib_depth:
            ve = cos01((tr - vib_delay) / 0.8)
            cents = cents + vib_depth * ve * np.sin(TWO_PI * vib_rate * rng.uniform(0.93, 1.07) * tr + rng.uniform(0, TWO_PI))
        ph = TWO_PI * np.cumsum(f0 * 2 ** (cents / 1200)) / SR + rng.uniform(0, TWO_PI)
        sig = np.zeros(n)
        for k in range(1, K + 1):
            fk = k * f0
            a = (k ** -tilt) * lp_mag(fk, fc, order, res)
            if formant is not None:
                a = a * formant(fk)
            if a.max() < 2e-4:
                continue
            ai = np.interp(tr, tc, a) if np.ptp(a) > 1e-6 else a[0]
            sig += ai * np.sin(k * ph + rng.uniform(0, TWO_PI))
        gl, gr = pan_gains(spread * pos)
        out[:, 0] += sig * gl
        out[:, 1] += sig * gr
    out *= env_ar(n, attack, release)[:, None] / np.sqrt(unison)
    return out


def bell(f0: float, dur: float, rng, ratios=(1.0, 2.756, 5.404), amps=(1.0, 0.25, 0.08),
         decays=(2.2, 0.8, 0.35), attack=0.0015, detune_cents=3.0):
    """inharmonic struck bar / glass bell (two slightly detuned strikes -> shimmer)"""
    n = ts(dur)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for r, a, d in zip(ratios, amps, decays):
        f = f0 * r
        if f > 17000:
            continue
        for s in (-1, 1):
            fd = f * 2 ** (s * detune_cents / 2400)
            y += 0.5 * a * np.exp(-t / d) * np.sin(TWO_PI * fd * t + rng.uniform(0, TWO_PI))
    return y * env_ar(n, attack, 0.05)


def pluck(f0: float, dur: float, rng, bright=2500.0, tau=0.9):
    n = ts(dur)
    t = np.arange(n) / SR
    y = np.zeros(n)
    K = int(min(30, 11000 // f0))
    for k in range(1, K + 1):
        fk = k * f0 * np.sqrt(1 + 0.00008 * k * k)
        a = k ** -1.0 * lp_mag(fk, bright, 2)
        if a < 2e-4:
            continue
        y += a * np.exp(-t * (1 / tau) * (1 + 0.55 * (k - 1))) * np.sin(TWO_PI * fk * t + rng.uniform(0, TWO_PI))
    return y * env_ar(n, 0.002, 0.08)


def felt_piano(f0: float, dur: float, vel: float, rng):
    """soft felt piano: stretched partials, felt-damped spectrum, two-stage decay, unison-string
    beating, soft hammer, low thump"""
    n = ts(dur)
    t = np.arange(n) / SR
    y = np.zeros(n)
    B = 0.00022
    tau0 = 3.4 * (261.6 / f0) ** 0.45
    fc = 700 + 1900 * vel
    for k in range(1, 26):
        fk = k * f0 * np.sqrt(1 + B * k * k)
        if fk > 11000:
            break
        a = k ** -1.15 * lp_mag(fk, fc, 2)
        if a < 3e-4:
            continue
        tk = tau0 / (1 + 0.5 * (k - 1))
        e = 0.6 * np.exp(-t / (0.3 * tk)) + 0.4 * np.exp(-t / tk)
        d = 2 ** (rng.uniform(0.4, 1.2) / 1200)
        y += a * e * 0.5 * (np.sin(TWO_PI * fk * t + rng.uniform(0, TWO_PI)) +
                            np.sin(TWO_PI * fk * d * t + rng.uniform(0, TWO_PI)))
    y *= env_ar(n, 0.009, 0.25)
    th = rng.standard_normal(ts(0.04)) * env_perc(ts(0.04), 0.002, 0.008)
    th = sos_filt(th, butter("lowpass", 380, 2)) * 0.25 * vel
    y[:len(th)] += th
    return y * vel


def sub_note(f0: float, dur: float, tau: float, attack=0.008):
    n = ts(dur)
    t = np.arange(n) / SR
    e = env_perc(n, attack, tau) * env_ar(n, 0.0005, 0.03)
    ph = TWO_PI * f0 * t
    return e * (np.sin(ph) + 0.22 * np.sin(2 * ph) * np.exp(-t / (0.6 * tau)) + 0.07 * np.sin(3 * ph) * np.exp(-t / (0.4 * tau)))


def hat(dur: float, rng, tau=0.018, hp=7500.0):
    n = ts(dur)
    y = rng.standard_normal(n) * env_perc(n, 0.0008, tau)
    y = sos_filt(y, butter("highpass", hp, 4))
    return sos_filt(y, butter("lowpass", 15000, 2))


# ----------------------------------------------------------------------------- layers
class Bus:
    """dry stereo buffer + reverb sends (all NT long, folded to 60 s at the end)"""

    def __init__(self):
        self.dry = np.zeros((NT, 2))
        self.hall = np.zeros((NT, 2))
        self.space = np.zeros((NT, 2))

    def add(self, x, t0, gain=1.0, pan=0.0, hall=0.0, space=0.0, dry=1.0):
        if dry:
            place(self.dry, x, t0, gain * dry, pan)
        if hall:
            place(self.hall, x, t0, gain * hall, pan)
        if space:
            place(self.space, x, t0, gain * space, pan)

    def scale(self, g):
        g = g[:, None]
        self.dry *= g
        self.hall *= g
        self.space *= g


def q60(f):
    """quantise a frequency to a whole number of cycles per 60 s (periodic bed)"""
    return np.round(np.asarray(f) * DUR) / DUR


def render_bed(A):
    """drone + airy Dm(add9) pad + air, exactly periodic over 60 s (seamless loop)."""
    t_full = np.arange(N) / SR
    g = curve(t_full, [(0.0, 1.0), (A["never"] - 1.4, 1.0), (A["never"] - 0.06, 1.18),
                       (A["never"] + 2.8, 0.0), (A["bed_in0"], 0.0), (A["bed_in1"], 1.0), (DUR, 1.0)])
    act = g > 1e-6
    t = t_full[act]
    ctrl = 480
    tc = np.arange(0, N + ctrl, ctrl) / SR
    bump = curve(tc, [(0.0, 1.0), (A["never"] - 1.6, 1.0), (A["never"] - 0.1, 1.9), (A["never"] + 2.0, 1.0), (DUR, 1.0)])
    fc_c = 1400 * 2 ** (0.5 * np.sin(TWO_PI * 5 / DUR * tc + 0.4) + 0.25 * np.sin(TWO_PI * 3 / DUR * tc + 1.3)) * bump
    jobs = []

    def voice(f0, amp_fn, pan, detune_hz, drift_hz, kmax, seed):
        def job():
            r = np.random.default_rng(seed)
            f = float(q60(f0 + detune_hz))
            rate = int(r.integers(2, 9)) / DUR
            p = r.uniform(0, TWO_PI)
            dh = float(q60(drift_hz)) if drift_hz else 0.0
            ph = TWO_PI * f * t - (dh / rate) * np.cos(TWO_PI * rate * t + p) + r.uniform(0, TWO_PI)
            sig = np.zeros(len(t))
            for k in range(1, kmax + 1):
                if k * f > 13000:
                    break
                a_c = amp_fn(k, k * f)
                if np.max(a_c) < 2e-4:
                    continue
                a = np.interp(t, tc, a_c) if np.ndim(a_c) else a_c
                sig += a * np.sin(k * ph + r.uniform(0, TWO_PI))
            gl, gr = pan_gains(pan)
            return np.stack([sig * gl, sig * gr], 1)
        jobs.append(job)

    # drone: D2 pair beating at 0.1 Hz + quiet D1 sub
    d2 = hz("D2")
    for i, (det, pan) in enumerate(((-0.05, -0.3), (0.05, 0.3))):
        voice(d2, lambda k, f: 0.38 * k ** -1.5 * lp_mag(f, 340.0, 2), pan, det, 0.0, 10, SEED + 100 + i)
    voice(hz("D1"), lambda k, f: 0.2 if k == 1 else 0.0, 0.0, 0.0, 0.0, 1, SEED + 102)
    # airy pad
    sd = SEED + 110
    for nm, gn in zip(CH["Dm(add9)"]["pad"], [0.55, 0.5, 0.42, 0.3, 0.16]):
        f0 = hz(nm)
        for pos in (-1, 0, 1):
            sd += 1
            detune_hz = f0 * (2 ** (6.5 * pos / 1200) - 1)
            voice(f0, lambda k, f, gn=gn: gn / np.sqrt(3) * k ** -1.0 * lp_mag(f, fc_c, 2, 0.2), 0.75 * pos,
                  detune_hz, f0 * (2 ** (2.0 / 1200) - 1), 40, sd)
    out = sum(run_parallel(jobs))
    y = np.zeros((N, 2))
    y[act] = out
    # air: periodic band-limited noise (4-10 kHz), slowly breathing
    air = np.stack([periodic_noise(N, SEED + 11, lambda f: np.exp(-0.5 * (np.log2(np.maximum(f, 1) / 6500) / 0.6) ** 2)),
                    periodic_noise(N, SEED + 12, lambda f: np.exp(-0.5 * (np.log2(np.maximum(f, 1) / 6500) / 0.6) ** 2))], 1)
    air *= (0.005 * (1 + 0.5 * np.sin(TWO_PI * 4 / DUR * t_full + 0.7)))[:, None]
    y += air
    return y * g[:, None]


def render(tl: Timeline | None = None, verbose: bool = True):
    t_start = time.time()
    tl = tl or Timeline()
    A = arrangement(tl)
    rng = np.random.default_rng(SEED)
    T = np.arange(NT) / SR
    nv, ex, cut, beat = A["never"], A["exploded"], A["cut"], A["beatB"]
    ps, bD = A["psych"], A["beatD"]
    but, al, fi, al2 = A["but"], A["already"], A["final"], A["already2"]

    def log(msg):
        if verbose:
            print(f"[music {time.time() - t_start:6.1f}s] {msg}", flush=True)

    log(f"B: {A['barsB']} bars @ {A['bpmB']:.2f} BPM from 'never' {nv:.3f}; D: {A['bpmD']:.2f} BPM")

    main = Bus()      # sections 1-2: everything the drop-out cuts
    free = Bus()      # periodic bed + outro stars (never gated)
    padB, refl, bl = Bus(), Bus(), Bus()

    # ------------------------------------------------ queue all pad / choir notes (rendered in parallel)
    queue = []

    def qpad(bus, t0, dur, f0, gain, sends, **kw):
        queue.append((bus, t0, gain, sends, SEED * 7 + len(queue), dict(t0=t0, dur=dur, f0=f0, **kw)))

    padB_fc = lambda t: curve(t, [(nv, 650), (nv + 1.5 * A["barB"], 1500), (A["step"], 2400),  # noqa: E731
                                  (A["pull"] - 0.1, 2600), (A["pull"] + 0.5, 950), (A["forged"], 1100),
                                  (ex - 0.05, 4500), (ex + 1.0, 3000), (cut, 2600)], log=True)
    for t0, t1, name in A["chords"]:
        if not (nv - 1e-6 <= t0 < cut) or name not in ("Dm9", "Bbmaj9", "Fadd9", "Cadd9"):
            continue
        rel = 0.9
        att = 0.12 if abs(t0 - nv) < 1e-6 else (0.06 if abs(t0 - ex) < 1e-6 else 0.35)
        for j, nm in enumerate(CH[name]["pad"]):
            qpad(padB, t0, (t1 - t0) + rel, hz(nm), 0.34 * (1.0 - 0.08 * j), dict(hall=0.5), cutoff=padB_fc,
                 attack=att, release=rel, res=0.2, detune=8.0, spread=0.85)

    padD_fc = lambda t: curve(t, [(ps, 800), (A["life"], 1300), (but, 1800)], log=True)  # noqa: E731
    for t0, t1, name in A["chords"]:
        if not (ps - 1e-6 <= t0 < but):
            continue
        for j, nm in enumerate(CH[name]["pad"]):
            qpad(refl, t0, (t1 - t0) + 1.0, hz(nm), 0.55 * (1 - 0.08 * j), dict(hall=0.6), cutoff=padD_fc,
                 attack=0.9, release=1.0, res=0.1, detune=6.0, spread=0.8, tilt=1.2)

    padE_fc = lambda t: curve(t, [(but, 700), (al - 0.05, 2400), (al + 0.2, 3300), (fi, 2900), (al2, 2600),  # noqa: E731
                                  (A["vo_end"] + 0.5, 2300), (DUR, 1100)], log=True)
    events = [("Bbadd9", but, al, 0.7, 0.7, "oo", 0.5, 1.0),
              ("Dadd9", al, fi + 0.3, 0.06, 1.45, "ah", 0.95, 0.35),
              ("G/D", fi, al2 + 0.3, 0.5, 1.15, "ah", 0.7, 0.5),
              ("Dadd9", al2, A["bed_in1"] + 0.2, 0.4, 1.1, "ah", 0.62, 0.6)]
    for name, t0, t1, att, gpad, vowel, gch, chatt in events:
        for j, nm in enumerate(CH[name]["pad"]):
            qpad(bl, t0, t1 - t0 + 1.2, hz(nm), 0.3 * gpad * (1 - 0.07 * j), dict(hall=0.6), cutoff=padE_fc,
                 attack=att, release=1.2, res=0.2, detune=9.0, spread=0.9)
        for j, nm in enumerate(CH[name]["choir"]):
            qpad(bl, t0, t1 - t0 + 1.6, hz(nm), 0.5 * gch, dict(hall=0.9), cutoff=5000.0, attack=chatt,
                 release=1.6, tilt=1.4, unison=4, detune=11.0, spread=0.9, drift=3.0, vib_rate=5.1,
                 vib_depth=14.0, formant=formant_env(vowel), kmax=40)

    # --------------------------------------------------------------- 1 bed (periodic)
    bed = render_bed(A) * 0.62
    free.hall[:N] += bed * 0.55
    free.dry[:N] += bed
    log("bed")
    res = run_parallel([lambda it=it: pad_note(rng=np.random.default_rng(it[4]), **it[5]) for it in queue])
    for (bus, t0, gain, sends, _, _), y in zip(queue, res):
        bus.add(y, t0, gain=gain, **sends)
    del res
    log(f"{len(queue)} pad/choir notes")

    # star bells (mystery + outro), seeded, avoiding the echo pings
    echo_t = [tl.t("echo", "Out"), tl.t("echo", "Up"), tl.t("echo", "Far")]
    bell_pool = ["D6", "E6", "F6", "A6", "C7", "D7", "A5"]

    def star_field(t0, t1, rate, gain, bus):
        t = t0 + rng.exponential(1 / rate)
        while t < t1:
            if min(abs(t - e) for e in echo_t) > 0.35:
                f = hz(bell_pool[rng.integers(len(bell_pool))])
                v = gain * np.exp(rng.uniform(np.log(0.3), 0.0))
                y = bell(f, 3.5, rng, decays=(rng.uniform(1.5, 2.8), 0.7, 0.3))
                bus.add(y, t, gain=v, pan=rng.uniform(-0.8, 0.8), dry=0.45, space=1.0)
            t += rng.exponential(1 / rate)

    star_field(0.03, nv - 0.2, 1.4, 0.075, main)
    star_field(A["bed_in0"] + 0.3, DUR - 0.25, 1.1, 0.06, free)
    log("stars")

    # --------------------------------------------------------------- 2 wonder build
    # pad level + quarter-note pump after the orbit step-up
    gB = curve(T, [(nv - 0.02, 0.0), (nv + 0.25, 0.75), (nv + 2 * A["barB"], 0.85), (A["step"] - 0.05, 0.9),
                   (A["step"] + 0.15, 1.2), (A["pull"] - 0.05, 1.2), (A["pull"] + 0.4, 0.55), (A["forged"], 0.65),
                   (ex - 0.02, 1.8), (ex + 1.5, 1.6), (cut, 1.5)])
    ph = np.mod(T - nv, beat)
    pump_on = curve(T, [(A["step"] - 0.01, 0.0), (A["step"] + 0.2, 1.0), (A["pull"] - 0.1, 1.0), (A["pull"] + 0.1, 0.0),
                        (ex, 0.0), (ex + 0.4, 1.0)])
    pump = 1 - 0.2 * pump_on * np.exp(-ph / 0.12) * (1 - np.exp(-ph / 0.008))
    padB.scale(gB * pump)

    # sub pulse
    sub = np.zeros((NT, 2))
    nbeats = int(np.ceil((cut - nv) / beat * 2))
    for i in range(nbeats):
        t = nv + i * beat / 2
        if t >= cut:
            break
        eighth = i % 2 == 1
        if t < A["step"] and eighth:
            continue
        if A["pull"] <= t < A["forged"] - 0.02:
            continue
        name = chord_at(A, t + 1e-4)
        f = hz(CH[name]["bass"])
        v = [1.0, 0.45, 0.7, 0.45, 0.85, 0.45, 0.7, 0.5][i % 8]
        if t < A["step"]:
            v *= 0.7
        if A["forged"] <= t < ex:
            v *= 0.6 + 0.5 * (t - A["forged"]) / (ex - A["forged"])
        tau = 0.22 if t < A["step"] else 0.14
        if abs(t - ex) < 1e-3:
            y, v = sub_note(f, 3.0, 1.1, 0.004), 1.5
        else:
            y = sub_note(f, 0.9, tau)
        place(sub, y, t, v)
    sub = sos_filt(sub, butter("lowpass", 220, 2))
    main.dry += sub * 0.22
    log("sub")

    # arp + ping-pong
    arp = np.zeros((NT, 2))
    arp_fc = lambda t: float(curve(t, [(nv, 1300), (nv + 2 * A["barB"], 2600), (A["step"], 3500), (A["pull"], 3500),  # noqa: E731
                                       (A["pull"] + 0.3, 1100), (A["forged"], 1300), (ex, 4800), (ex + 1.0, 3200), (cut, 3000)], log=True))
    arp_g = lambda t: float(curve(t, [(nv, 0.5), (nv + 2 * A["barB"], 0.75), (A["step"] - 0.05, 0.8), (A["step"] + 0.1, 1.2),  # noqa: E731
                                      (A["pull"] - 0.05, 1.2), (A["pull"] + 0.2, 0.4), (A["forged"], 0.45), (ex, 1.3), (cut, 1.15)]))
    vel = [1.0, 0.62, 0.82, 0.6, 0.92, 0.62, 0.8, 0.66]
    for i in range(nbeats):
        t = nv + i * beat / 2
        if t >= cut - 0.02:
            break
        name = chord_at(A, t + 1e-4)
        f = hz(CH[name]["arp"][i % 8])
        v = vel[i % 8] * arp_g(t) * np.exp(rng.normal(0, 0.06))
        place(arp, pluck(f, 1.6, rng, bright=arp_fc(t)), t, v * 0.16, pan=0.15 * np.sin(i * 0.9))
        if t >= A["step"] and not (A["pull"] <= t < ex):
            place(arp, pluck(f * 2, 1.0, rng, bright=arp_fc(t) * 1.4, tau=0.6), t + 0.004, v * 0.075,
                  pan=-0.3 * np.sin(i * 0.9))
    arp_d = pingpong(arp, 0.75 * beat, 0.42, taps=7, lp=4200, hp=300)
    arp_all = arp + 0.55 * arp_d
    main.dry += arp_all
    main.hall += arp_all * 0.35
    log("arp")

    # hats: offbeat 8ths (+ 16th ghosts) from the orbit step to the pull-back, again after the supernova
    hats = np.zeros((NT, 2))
    for i in range(int((cut - nv) / (beat / 4)) + 1):
        t = nv + i * beat / 4
        if t >= cut - 0.03:
            break
        if not ((A["step"] <= t < A["pull"]) or (ex <= t)):
            continue
        pos = i % 4
        v = 0.55 if pos == 2 else (0.16 if pos in (1, 3) and t >= A["step"] + A["barB"] else 0.0)
        if v:
            y = hat(0.12, rng, tau=0.02 if pos == 2 else 0.012)
            place(hats, y, t, v * np.exp(rng.normal(0, 0.12)) * 0.06, pan=0.3 if pos == 2 else -0.25)
    main.dry += hats
    main.hall += hats * 0.25
    log("hats")

    # swell into the supernova + crash on "exploded"
    fg = A["forged"]
    sw_d = ex - fg + 0.02
    sw = noise_tv(sw_d, lambda f, tt: np.exp(-0.5 * (np.log2(np.maximum(f, 1) / (1200 * 2 ** (2.6 * tt / sw_d))) / 0.9) ** 2), SEED + 31)
    tt = np.arange(len(sw)) / SR
    sw *= (np.exp(3.6 * (tt / sw_d - 1)) * env_ar(len(sw), 0.2, 0.01))[:, None]
    main.add(sw, fg, gain=0.09, hall=0.6)
    crash = noise_tv(3.5, lambda f, tt: lp_mag(f, 11000, 2) * (1 - lp_mag(f, 3200, 2)) * np.exp(-tt / (0.5 + 1.0 * np.exp(-f / 5000))), SEED + 32)
    crash *= env_ar(len(crash), 0.002, 0.3)[:, None]
    main.add(crash, ex, gain=0.075, hall=0.5)
    log("swell/crash")

    # the cut: gate everything of sections 1-2 at the question scene (reverb is applied later
    # and split into pre/post cut so the tail decays naturally)
    gate = 1 - cos01((T - (cut - 0.03)) / 0.03)
    main.dry += padB.dry
    main.hall += padB.hall
    main.space += padB.space
    main.scale(gate)

    # --------------------------------------------------------------- 3 question tone (own path)
    qtone = np.zeros((NT, 2))
    nq = ts(A["psych"] + 3.2 - cut)
    tq = np.arange(nq) / SR
    fa = hz("A5")
    y = np.zeros((nq, 2))
    for s, pan in ((-1, -0.35), (1, 0.35)):
        f = fa + s * 0.2
        phq = TWO_PI * f * tq + 0.002 * f / 5.1 * np.sin(TWO_PI * 5.1 * tq * (1 + 0.03 * s))
        y += np.outer(np.sin(phq) + 0.04 * np.sin(2 * phq), pan_gains(pan))
    y += np.outer(0.18 * np.sin(TWO_PI * hz("A4") * tq), [0.7, 0.7])
    y *= curve(cut + tq, [(cut, 0.0), (cut + 0.6, 1.0), (ps + 0.3, 1.0), (ps + 3.2, 0.0)])[:, None]
    place(qtone, y, cut, 0.022)
    log("question tone")

    # --------------------------------------------------------------- 4 reflective
    gD = curve(T, [(ps, 0.0), (ps + A["barD"] * 1.5, 0.22), (A["life"], 0.42), (but - 1.2, 0.55), (but, 0.25)])
    refl.scale(gD)
    melody = [(0.0, 1.5, "D5", .55), (1.5, .5, "C5", .38), (2.0, 2.0, "A4", .5),
              (4.0, 1.5, "Bb4", .52), (5.5, .5, "A4", .36), (6.0, 2.0, "F4", .45),
              (8.0, 1.0, "A4", .45), (9.0, 1.0, "E5", .52), (10.0, 2.0, "D5", .5),
              (12.0, 1.5, "E5", .52), (13.5, .5, "D5", .38), (14.0, 1.0, "C5", .45), (15.0, 1.0, "G4", .4),
              (16.0, 1.5, "D5", .55), (17.5, .5, "C5", .4), (18.0, 1.0, "A4", .46), (19.0, 1.0, "F5", .5),
              (20.0, 2.0, "D5", .45)]
    lh = {"Bbmaj9": (["Bb2", "F3"], "D4"), "Gm9": (["G2", "D3"], "Bb3"), "Dm9": (["D3", "A3"], "F4"),
          "Cadd9": (["C3", "G3"], "E4")}
    piano = np.zeros((NT, 2))
    for b, dur_b, nm, v in melody:
        place(piano, felt_piano(hz(nm), dur_b * bD + 2.5, v, rng), ps + b * bD + rng.uniform(0, 0.012), 0.95, pan=0.12)
    for t0, t1, name in A["chords"]:
        if not (ps - 1e-6 <= t0 < but) or name not in lh:
            continue
        low, mid = lh[name]
        for j, nm in enumerate(low):
            place(piano, felt_piano(hz(nm), 4.0, 0.42 - 0.08 * j, rng), t0 + 0.03 * j, 0.95, pan=-0.18)
        if t1 - t0 > 2.2 * bD:
            place(piano, felt_piano(hz(mid), 3.0, 0.3, rng), t0 + 2 * bD, 0.95, pan=-0.05)
    refl.add(piano, 0.0, hall=0.45)
    lowr = np.zeros((NT, 2))       # soft low root under "life"
    for t0, t1, name in A["chords"]:
        if A["life"] - 0.3 <= t0 < but:
            f = hz(CH[name]["bass"])
            f = f * 2 if f < 60 else f
            place(lowr, sub_note(f, t1 - t0 + 0.6, 2.0, 0.25) * env_ar(ts(t1 - t0 + 0.6), 0.25, 0.5), t0, 0.1)
    refl.add(sos_filt(lowr, butter("lowpass", 200, 2)), 0.0)
    log("reflective")

    # --------------------------------------------------------------- 5 bloom
    rd = 1.6                       # riser into "But": rising Shepard tone + noise swell
    nr = ts(rd)
    x = np.arange(nr) / SR / rd
    ris = np.zeros(nr)
    for j in range(-1, 6):
        f = hz("D2") * 2 ** (j + 1.0 * x)
        ris += np.exp(-0.5 * (np.log2(f / 700) / 1.1) ** 2) * np.sin(TWO_PI * np.cumsum(f) / SR + rng.uniform(0, TWO_PI))
    rn = noise_tv(rd, lambda f, tt: np.exp(-0.5 * (np.log2(np.maximum(f, 1) / (600 * 2 ** (3.2 * tt / rd))) / 0.8) ** 2), SEED + 41)
    riser = (np.outer(ris, [0.7, 0.7]) * 0.5 + rn * 0.5) * (np.exp(3.2 * (x - 1)) * env_ar(nr, 0.3, 0.006))[:, None]
    bl.add(riser, but - rd, gain=0.10, hall=0.5)
    gE = curve(T, [(but, 1.0), (A["vo_end"], 1.0), (A["vo_end"] + 0.6, 1.08), (A["bed_in0"] + 0.4, 1.0),
                   (A["bed_in1"], 0.3), (A["bed_in1"] + 0.9, 0.0)])
    bl.scale(gE)
    subE = np.zeros((NT, 2))       # sub swell: Bb1 rising into "already", then D2 bloom
    nb_ = ts(al - but)
    tb = np.arange(nb_) / SR
    place(subE, np.sin(TWO_PI * hz("Bb1") * tb) * cos01(tb / (al - but)) ** 2 * env_ar(nb_, 0.01, 0.03), but, 0.55)
    place(subE, sub_note(hz("D2"), 5.0, 2.4, 0.06), al, 1.0)
    place(subE, sub_note(hz("D2"), 4.0, 2.0, 0.35) * env_ar(ts(4.0), 0.01, 1.5), al2, 0.55)
    bl.add(sos_filt(subE, butter("lowpass", 200, 2)), 0.0, gain=0.24)
    for j, nm in enumerate(["D3", "A3", "F#4", "A4", "D5"]):          # felt piano on the lift
        bl.add(felt_piano(hz(nm), 4.0, 0.55, rng), al + 0.022 * j, gain=0.5, hall=0.5, pan=-0.1 + 0.05 * j)
    for j, nm in enumerate(["D6", "F#6", "A6", "D7", "E7", "A7"]):   # sparkle
        bl.add(bell(hz(nm), 3.0, rng), al + 0.06 + j * bD / 4, gain=0.05 * (1 - 0.1 * j),
               pan=-0.6 + 0.24 * j, dry=0.5, space=1.0)
    for j, nm in enumerate(["D3", "G3", "B3", "D4"]):
        bl.add(felt_piano(hz(nm), 3.5, 0.4, rng), fi + 0.03 * j, gain=0.45, hall=0.5)
    for j, nm in enumerate(["D4", "A4", "E5", "F#5", "A5"]):
        bl.add(felt_piano(hz(nm), 4.0, 0.42 - 0.04 * j, rng), al2 + j * bD / 2, gain=0.45, hall=0.55, pan=-0.2 + 0.1 * j)
    log("bloom")

    # --------------------------------------------------------------- reverbs + fold (loop)
    ir_hall = make_ir(4.2, 1.6, seed=3, predelay=0.025, hp=140)
    ir_space = make_ir(7.5, 3.0, seed=5, predelay=0.04, hp=300, lp=11000)
    dry = fold(main.dry + refl.dry + bl.dry + free.dry)
    tN = np.arange(N) / SR
    pre = (tN < cut)[:, None]
    hall_s = fold(main.hall + refl.hall + bl.hall + free.hall)
    space_s = fold(main.space + refl.space + bl.space + free.space)
    rgate = (1 - cos01((tN - cut) / 1.5))[:, None]
    wet = convolve(hall_s * pre, ir_hall) * rgate + convolve(hall_s * ~pre, ir_hall)
    wet += convolve(space_s * pre, ir_space) * rgate + convolve(space_s * ~pre, ir_space)
    q = fold(qtone)
    wet += convolve(q, ir_hall) * 0.8
    mix = dry + 0.5 * wet + q
    log("reverb")

    # --------------------------------------------------------------- bus
    mix *= 10 ** ((-20.0 - integrated_lufs(mix)) / 20)

    def chain(x):
        x = sos_filt(x, butter("highpass", 28.0, 2))
        x = sos_filt(x, peq(260, -1.5, 0.9))
        x = sos_filt(x, peq(2200, -3.5, 0.6))        # carve the voice-presence band
        x = sos_filt(x, shelf("high", 7000, 2.5))    # air above the voice
        x = tape_sat(x, drive_db=4.0, bias=0.04)
        x = sos_filt(x, shelf("high", 14000, -1.5))  # tape HF roll-off
        x, _ = compressor(x, -24.0, 2.0, 30.0, 300.0, knee_db=8.0, rms_ms=30)
        return x
    out = circular(chain, mix, pad=4.0)
    out *= 10 ** ((-20.0 - integrated_lufs(out)) / 20)
    pk = np.abs(out).max()
    if pk > 0.7:
        out *= 0.7 / pk
    log(f"bus: {integrated_lufs(out):.2f} LUFS, peak {20 * np.log10(np.abs(out).max()):.2f} dBFS")
    return out, A


def main():
    out, A = render()
    path = os.path.join(OUT, "music.wav")
    write_wav(path, out)
    print(f"wrote {path}  ({len(out) / SR:.3f} s)")


if __name__ == "__main__":
    main()
