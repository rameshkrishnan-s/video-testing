#!/usr/bin/env python3
"""Analysis plots + metrics for the score / SFX / master (audio/out/analysis/).

    audio/.venv/bin/python audio/analyze.py          # analyse the files currently in audio/out

mix.py calls report() after writing master.wav.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dsp import (N, OUT, SR, Timeline, butter, gated_loudness, integrated_lufs, loudness_curve,  # noqa: E402
                 lra, read_wav, sos_filt, true_peak_db, ts)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AN = os.path.join(OUT, "analysis")
plt.rcParams.update({"figure.facecolor": "#0b0e17", "axes.facecolor": "#0b0e17", "axes.edgecolor": "#8a93a8",
                     "axes.labelcolor": "#d8dcea", "xtick.color": "#a9b0c3", "ytick.color": "#a9b0c3",
                     "text.color": "#e8ebf5", "grid.color": "#2a3146", "font.size": 9})


def _scene_lines(ax, tl, labels=True, ymax=None):
    for sid, t0, t1 in tl.scenes():
        ax.axvline(t0, color="#5CC8FF", lw=0.6, alpha=0.5)
        if labels:
            ax.text(t0 + 0.15, 1.0, sid, transform=ax.get_xaxis_transform(), va="top", fontsize=7, color="#5CC8FF")


def spectrogram_png(x, path, title, tl, fmax=16000):
    m = x.mean(1) if x.ndim == 2 else x
    f, t, S = signal.spectrogram(m, SR, nperseg=4096, noverlap=4096 - 1024, window="hann")
    S = 10 * np.log10(S + 1e-14)
    fig, ax = plt.subplots(figsize=(16, 5), dpi=110)
    vmax = np.percentile(S, 99.7)
    ax.pcolormesh(t, f, S, vmin=vmax - 80, vmax=vmax, cmap="magma", shading="auto")
    ax.set_yscale("symlog", linthresh=200)
    ax.set_ylim(20, fmax)
    ax.set_xlim(0, 60)
    ax.set_xlabel("s")
    ax.set_ylabel("Hz")
    ax.set_title(title)
    _scene_lines(ax, tl)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def levels_png(tracks: dict, path, tl, title="Short-term loudness (3 s) and momentary (0.4 s)"):
    fig, ax = plt.subplots(figsize=(16, 5.5), dpi=110)
    cols = {"vo": "#F4F6FF", "music": "#FFB547", "music_ducked": "#FFB547", "sfx": "#5CC8FF", "master": "#FF5A4E"}
    for name, x in tracks.items():
        t, lm = loudness_curve(x, 0.4, 0.05)
        ax.plot(t, np.maximum(lm, -70), lw=0.6, alpha=0.55, color=cols.get(name, "#aaa"),
                ls="--" if name == "music" else "-")
        t, ls = loudness_curve(x, 3.0, 0.1)
        ax.plot(t, np.maximum(ls, -70), lw=1.8, color=cols.get(name, "#aaa"), label=name,
                ls="--" if name == "music" else "-")
    ax.set_ylim(-60, -5)
    ax.set_xlim(0, 60)
    ax.grid(True, lw=0.4)
    ax.set_ylabel("LUFS")
    ax.set_xlabel("s")
    ax.legend(loc="lower left", ncol=5, facecolor="#0b0e17")
    ax.set_title(title)
    _scene_lines(ax, tl)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def speech_mask(tl, n=N, pad=0.03):
    m = np.zeros(n, bool)
    for _, w in tl.words():
        m[max(0, ts(w["start"] - pad)):ts(w["end"] + pad)] = True
    return m


def section_table(x, tl):
    rows = []
    for sid, t0, t1 in tl.scenes():
        seg = x[ts(t0):ts(t1)]
        t, ls = loudness_curve(seg, min(3.0, (t1 - t0) * 0.9), 0.1)
        rows.append((sid, t0, t1, float(np.max(ls)), float(np.median(ls))))
    return rows


def word_masking(vo, bed, tl, band=(1000, 4000)):
    """per word: VO level vs (music+sfx) level in the 1-4 kHz speech-presence band (dB)"""
    sos = butter("bandpass", list(band), 4)
    v = sos_filt(vo.mean(1) if vo.ndim == 2 else vo, sos)
    b = sos_filt(bed.mean(1) if bed.ndim == 2 else bed, sos)
    res = []
    for bid, w in tl.words():
        a, z = ts(w["start"]), ts(w["end"])
        pv = 10 * np.log10(np.mean(v[a:z] ** 2) + 1e-14)
        pb = 10 * np.log10(np.mean(b[a:z] ** 2) + 1e-14)
        res.append((bid, w["text"], w["start"], pv - pb))
    return res


def click_scan(x, thresh_db=14.0):
    """isolated HF spikes: 1 ms HF energy that jumps far above its 60 ms neighbourhood"""
    m = x.mean(1) if x.ndim == 2 else x
    hp = sos_filt(m, butter("highpass", 9000, 4))
    p = hp ** 2
    short = uniform_filter1d(p, ts(0.001))
    longw = uniform_filter1d(p, ts(0.06))
    ratio = 10 * np.log10((short + 1e-16) / (longw + 1e-16))
    loud = 10 * np.log10(short + 1e-16) > -70
    idx = np.where((ratio > thresh_db) & loud)[0]
    hits = []
    last = -10 ** 9
    for i in idx:
        if i - last > ts(0.05):
            hits.append(round(i / SR, 3))
        last = i
    return hits


def stereo_stats(x):
    L, R = x[:, 0], x[:, 1]
    corr = float(np.sum(L * R) / np.sqrt(np.sum(L * L) * np.sum(R * R) + 1e-20))
    mono = 0.5 * (L + R)
    st = integrated_lufs(x)
    mo = integrated_lufs(np.stack([mono, mono], 1))
    side = 0.5 * (L - R)
    return {"correlation": round(corr, 3), "mono_minus_stereo_LU": round(mo - st, 2),
            "side_to_mid_dB": round(10 * np.log10(np.mean(side ** 2) / (np.mean(mono ** 2) + 1e-20)), 2)}


def seam_png(x, path):
    k = ts(0.03)
    seg = np.concatenate([x[-k:], x[:k]], 0)
    t = (np.arange(len(seg)) - k) / SR * 1000
    fig, ax = plt.subplots(figsize=(10, 3.5), dpi=110)
    ax.plot(t, seg[:, 0], lw=0.8, color="#FFB547", label="L")
    ax.plot(t, seg[:, 1], lw=0.8, color="#5CC8FF", label="R", alpha=0.8)
    ax.axvline(0, color="#FF5A4E", lw=0.8)
    ax.set_xlabel("ms around the loop point (end of file -> start of file)")
    ax.set_title("Loop seam: last 30 ms of master followed by its first 30 ms")
    ax.legend(facecolor="#0b0e17")
    ax.grid(True, lw=0.4)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def ducking_png(vo, gain_db, path, tl, hop=48):
    fig, ax = plt.subplots(figsize=(16, 3.8), dpi=110)
    t = np.arange(len(gain_db)) * hop / SR
    m = vo.mean(1) if vo.ndim == 2 else vo
    env = 20 * np.log10(np.sqrt(uniform_filter1d(m ** 2, ts(0.02)))[::hop] + 1e-9)
    ax.plot(t, np.maximum(env, -80) / 10, lw=0.5, color="#F4F6FF", alpha=0.5, label="VO RMS (dB/10)")
    ax.plot(t, gain_db, lw=1.4, color="#FFB547", label="music duck gain (dB)")
    ax.set_xlim(0, 60)
    ax.set_ylim(-9, 1)
    ax.grid(True, lw=0.4)
    ax.legend(loc="lower right", facecolor="#0b0e17")
    ax.set_title("VO-keyed sidechain ducking of the music bus")
    _scene_lines(ax, tl)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def masking_png(rows, path):
    fig, ax = plt.subplots(figsize=(16, 3.5), dpi=110)
    t = [r[2] for r in rows]
    d = [r[3] for r in rows]
    ax.scatter(t, d, s=10, color="#5CC8FF")
    worst = sorted(rows, key=lambda r: r[3])[:6]
    for r in worst:
        ax.annotate(r[1], (r[2], r[3]), fontsize=7, color="#FFB547", xytext=(2, -9), textcoords="offset points")
    ax.axhline(10, color="#FF5A4E", lw=0.8, ls="--")
    ax.set_xlim(0, 60)
    ax.set_ylabel("dB")
    ax.set_title("Per-word VO level minus music+SFX level in the 1-4 kHz band (higher = clearer)")
    ax.grid(True, lw=0.4)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def report(vo, music_ducked, sfx, master, duck_db=None, music_raw=None, extra=None):
    os.makedirs(AN, exist_ok=True)
    tl = Timeline()
    vo2 = np.stack([vo, vo], 1) if vo.ndim == 1 else vo
    R: dict = {}
    R["master"] = {"integrated_LUFS": round(integrated_lufs(master), 2), "true_peak_dBTP": round(true_peak_db(master), 2),
                   "sample_peak_dBFS": round(20 * np.log10(np.abs(master).max()), 2), "LRA_LU": round(lra(master), 2),
                   "samples": int(len(master)), "duration_s": len(master) / SR,
                   "dc_offset": [float(f"{v:.2e}") for v in master.mean(0)]}
    R["master"].update(stereo_stats(master))
    sm = speech_mask(tl, len(master))
    lv = gated_loudness(vo2, sm)
    lm = gated_loudness(music_ducked, sm)
    R["speech_regions"] = {"vo_LUFS": round(lv, 2), "music_ducked_LUFS": round(lm, 2), "vo_minus_music_LU": round(lv - lm, 2),
                           "sfx_LUFS": round(gated_loudness(sfx, sm), 2)}
    R["sections_master"] = [{"scene": s, "t0": round(a, 3), "t1": round(b, 3), "max_short_term_LUFS": round(mx, 1),
                             "median_short_term_LUFS": round(md, 1)} for s, a, b, mx, md in section_table(master, tl)]
    R["sections_music_ducked"] = [{"scene": s, "max_short_term_LUFS": round(mx, 1), "median_short_term_LUFS": round(md, 1)}
                                  for s, a, b, mx, md in section_table(music_ducked, tl)]
    mk = word_masking(vo2, music_ducked + sfx, tl)
    R["word_masking_1_4kHz"] = {"min_dB": round(min(r[3] for r in mk), 1), "median_dB": round(float(np.median([r[3] for r in mk])), 1),
                                "worst": [{"beat": b, "word": w, "t": round(t, 2), "dB": round(d, 1)} for b, w, t, d in sorted(mk, key=lambda r: r[3])[:8]]}
    seam = np.abs(master[0] - master[-1]).max()
    dif = np.abs(np.diff(master, axis=0)).max(1)
    R["loop_seam"] = {"first_sample": master[0].round(6).tolist(), "last_sample": master[-1].round(6).tolist(),
                      "jump": float(f"{seam:.2e}"), "median_step": float(f"{np.median(dif):.2e}"),
                      "p99.9_step": float(f"{np.percentile(dif, 99.9):.2e}")}
    if music_raw is not None:
        R["clicks_music"] = click_scan(music_raw)
    R["clicks_sfx"] = click_scan(sfx)
    if extra:
        R.update(extra)
    with open(os.path.join(AN, "report.json"), "w") as f:
        json.dump(R, f, indent=2)
    # plots
    spectrogram_png(master, os.path.join(AN, "spectrogram_master.png"), "master.wav", tl)
    if music_raw is not None:
        spectrogram_png(music_raw, os.path.join(AN, "spectrogram_music.png"), "music.wav (stem, unducked)", tl)
    spectrogram_png(sfx, os.path.join(AN, "spectrogram_sfx.png"), "sfx.wav (stem)", tl)
    levels_png({"vo": vo2, "music_ducked": music_ducked, "sfx": sfx, "master": master},
               os.path.join(AN, "loudness_mix.png"), tl)
    if music_raw is not None:
        levels_png({"music": music_raw}, os.path.join(AN, "loudness_music_stem.png"), tl,
                   "music.wav stem loudness (unducked, stem level)")
    if duck_db is not None:
        ducking_png(vo, duck_db, os.path.join(AN, "ducking.png"), tl)
    seam_png(master, os.path.join(AN, "loop_seam.png"))
    masking_png(mk, os.path.join(AN, "word_masking.png"))
    return R


if __name__ == "__main__":
    tl = Timeline()
    which = sys.argv[1:] or ["music"]
    os.makedirs(AN, exist_ok=True)
    for name in which:
        x = read_wav(os.path.join(OUT, f"{name}.wav"))
        spectrogram_png(x, os.path.join(AN, f"spectrogram_{name}.png"), f"{name}.wav", tl)
        levels_png({name: x}, os.path.join(AN, f"loudness_{name}.png"), tl, f"{name}.wav loudness")
        for s, a, b, mx, md in section_table(x, tl):
            print(f"{name:6s} {s:11s} {a:6.2f}-{b:6.2f}  max {mx:6.1f}  median {md:6.1f}")
        if x.ndim == 2:
            print(name, stereo_stats(x), "clicks:", click_scan(x)[:20])
