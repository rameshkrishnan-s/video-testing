#!/usr/bin/env python3
"""Final mix + master: vo.wav + music.wav + sfx.wav -> audio/out/master.wav

    audio/.venv/bin/python audio/mix.py           # rebuild master.wav from vo.wav + stems
    audio/.venv/bin/python audio/mix.py --all     # re-render music.wav and sfx.wav first

Chain
  VO      centred, untouched (already polished by tts.py)
  music   VO-keyed sidechain duck (DUCK_DB, attack 60 ms, release 350 ms, 25 ms look-ahead);
          bus gain set automatically so the ducked music sits MUSIC_UNDER_VO_LU below the VO
          (gated loudness over speech regions only)
  sfx     at the cue gains baked into sfx.wav, plus a light VO-keyed duck (SFX_DUCK_DB)
  master  gentle bus compression (1.5:1) -> gain to -14 LUFS -> 4x-oversampled true-peak
          limiter (ceiling -1.3 dBTP) -> 3 ms anti-click tapers at both file edges.
          All stateful stages run "circularly" so the end of the file flows into its start.
Writes master.wav (48 kHz, 24-bit, stereo, exactly 2,880,000 samples) and the analysis set
in audio/out/analysis/ (PNGs + report.json).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dsp import (N, OUT, SR, Timeline, _ar_smooth, butter, circular, sos_filt, compressor, env_ar, gain_curve_to_audio,  # noqa: E402
                 gated_loudness, integrated_lufs, level_db, lra, read_wav, tp_limiter, true_peak_db, ts,
                 write_wav)

TARGET_LUFS = -14.0
TP_CEIL = -1.3            # limiter ceiling (dBTP); spec is <= -1.0 dBTP
DUCK_DB = 6.0             # music reduction while the VO speaks
DUCK_ATTACK_MS = 60.0
DUCK_RELEASE_MS = 350.0
DUCK_LOOKAHEAD_MS = 25.0
SFX_DUCK_DB = 2.0
BAND = (900.0, 4500.0)    # speech-presence band that gets extra, VO-keyed reduction (dynamic EQ)
MUSIC_BAND_DUCK_DB = 4.0  # extra on top of DUCK_DB, band only
SFX_BAND_DUCK_DB = 5.0    # extra on top of SFX_DUCK_DB, band only
MUSIC_UNDER_VO_LU = 14.0  # ducked music vs VO, speech regions
HOP = 48                  # 1 ms control rate


def duck_curve(vo, depth_db, attack_ms, release_ms, lookahead_ms, lo=-50.0, hi=-34.0):
    """gain (dB, <= 0) at control rate from the VO level; reduction ramps in between lo and hi dBFS"""
    lev = level_db(vo, 0.01, HOP)
    la = int(round(lookahead_ms / 1000 * SR / HOP))
    lev = np.concatenate([lev[la:], np.full(la, lev[-1])])
    x = np.clip((lev - lo) / (hi - lo), 0, 1)
    target = depth_db * x * x * (3 - 2 * x)
    a_att = np.exp(-HOP / (SR * attack_ms / 1000))
    a_rel = np.exp(-HOP / (SR * release_ms / 1000))
    return -_ar_smooth(target, a_att, a_rel)


def split_band(x):
    """zero-phase band split: band + rest == x exactly"""
    sos = butter("bandpass", list(BAND), 2)
    band = circular(lambda z: signal.sosfiltfilt(sos, z, axis=0), x, pad=1.0)
    return band, x - band


def apply_duck(x, duck_db_ctrl, full_db, band_db):
    """full-band reduction (full_db at full VO) plus extra reduction in the speech band"""
    band, rest = split_band(x)
    s = duck_db_ctrl / DUCK_DB                       # 0 .. -1
    g_full = 10 ** (gain_curve_to_audio(s * full_db, len(x), HOP) / 20)[:, None]
    g_band = 10 ** (gain_curve_to_audio(s * (full_db + band_db), len(x), HOP) / 20)[:, None]
    return rest * g_full + band * g_band


def speech_mask(tl, n=N, pad=0.03):
    m = np.zeros(n, bool)
    for _, w in tl.words():
        m[max(0, ts(w["start"] - pad)):ts(w["end"] + pad)] = True
    return m


def master_chain(mix, gain_db):
    def proc(x):
        x = sos_filt(x, butter("highpass", 12.0, 2))      # DC / infrasonic blocker
        x, _ = compressor(x, -16.0 - gain_db, 1.5, 15.0, 220.0, knee_db=10.0, rms_ms=20)
        return x * 10 ** (gain_db / 20)
    y = circular(proc, mix, pad=3.0)
    y = circular(lambda x: tp_limiter(x, TP_CEIL, 1.5, 80.0)[0], y, pad=1.0)
    return y


def build(verbose=True, analysis=True):
    t0 = time.time()
    tl = Timeline()
    vo = read_wav(os.path.join(OUT, "vo.wav"))
    music = read_wav(os.path.join(OUT, "music.wav"))
    sfx = read_wav(os.path.join(OUT, "sfx.wav"))
    assert len(vo) == len(music) == len(sfx) == N, (len(vo), len(music), len(sfx))
    vo2 = np.stack([vo, vo], 1)

    # ---- ducking
    duck = duck_curve(vo, DUCK_DB, DUCK_ATTACK_MS, DUCK_RELEASE_MS, DUCK_LOOKAHEAD_MS)
    music_d = apply_duck(music, duck, DUCK_DB, MUSIC_BAND_DUCK_DB)
    sfx_d = apply_duck(sfx, duck, SFX_DUCK_DB, SFX_BAND_DUCK_DB)

    # ---- music level relative to the VO over speech regions
    sm = speech_mask(tl)
    l_vo = gated_loudness(vo2, sm)
    l_mu = gated_loudness(music_d, sm)
    g_music_db = (l_vo - MUSIC_UNDER_VO_LU) - l_mu
    music_d *= 10 ** (g_music_db / 20)
    mix = vo2 + music_d + sfx_d
    if verbose:
        print(f"[mix] VO {l_vo:.2f} LUFS (speech), music bus {g_music_db:+.2f} dB -> ducked music "
              f"{gated_loudness(music_d, sm):.2f} LUFS under speech")

    # ---- master: iterate gain so the limited result lands on -14 LUFS
    gain = TARGET_LUFS - integrated_lufs(mix)
    for it in range(6):
        out = master_chain(mix, gain)
        L = integrated_lufs(out)
        tp = true_peak_db(out)
        if verbose:
            print(f"[mix] pass {it + 1}: gain {gain:+.2f} dB -> {L:.2f} LUFS, {tp:.2f} dBTP")
        if abs(L - TARGET_LUFS) < 0.05 and tp <= -1.0:
            break
        gain += TARGET_LUFS - L
    out = out * env_ar(N, 0.003, 0.003)[:, None]        # anti-click tapers at the file edges
    assert len(out) == N
    path = os.path.join(OUT, "master.wav")
    write_wav(path, out)
    out = read_wav(path)                                 # measure what was written (24-bit)
    res = {"integrated_LUFS": round(integrated_lufs(out), 2), "true_peak_dBTP": round(true_peak_db(out), 2),
           "LRA_LU": round(lra(out), 2), "samples": len(out)}
    if verbose:
        print(f"[mix] wrote {path}: {res}  ({time.time() - t0:.1f}s)")
    settings = {"duck_db": DUCK_DB, "duck_attack_ms": DUCK_ATTACK_MS, "duck_release_ms": DUCK_RELEASE_MS,
                "duck_lookahead_ms": DUCK_LOOKAHEAD_MS, "sfx_duck_db": SFX_DUCK_DB, "band_hz": BAND,
                "music_band_extra_duck_db": MUSIC_BAND_DUCK_DB, "sfx_band_extra_duck_db": SFX_BAND_DUCK_DB,
                "music_bus_gain_db": round(g_music_db, 2), "master_gain_db": round(gain, 2),
                "limiter_ceiling_dBTP": TP_CEIL}
    if analysis:
        import analyze
        # stems at their in-mix level (same master gain) for the analysis plots
        k = 10 ** (gain / 20)
        rep = analyze.report(vo2 * k, music_d * k, sfx_d * k, out, duck_db=duck, music_raw=music,
                             extra={"mix_settings": settings})
        if verbose:
            print(json.dumps({k: rep[k] for k in ("master", "speech_regions", "word_masking_1_4kHz", "loop_seam")}, indent=1))
    return out, res, settings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="re-render music.wav and sfx.wav first")
    ap.add_argument("--no-analysis", action="store_true")
    a = ap.parse_args()
    if a.all:
        import music
        import sfx
        music.main()
        sfx.main()
    build(analysis=not a.no_analysis)


if __name__ == "__main__":
    main()
