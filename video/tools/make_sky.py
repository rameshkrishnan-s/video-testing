#!/usr/bin/env python3
"""Deterministic generator for the shared space imagery in public/img/.

Outputs
  public/img/sky_milkyway.jpg      2304x4096 deep-space background with a soft Milky Way band
  public/img/sky_milkyway_preview.jpg  576x1024 preview (for quick looks only)
  public/img/starfield_layer.png   2304x4096 transparent dense starfield (parallax layer)
  public/img/grain_0..5.png        512x512 film-grain tiles (gray, mid = 128; for blend modes)
  public/img/grain_rgba_0..5.png   512x512 grain for NORMAL blending (white/black, alpha=|noise|)
  public/img/vignette.png          1080x1920 RGBA vignette (cheaper than CSS gradients)
  public/img/grain_plate_0..2.png  1200x2040 LA grain plates (used by <Grain/>)

Run (needs numpy, pillow, scipy -> tools/.venv):
  tools/.venv/bin/python tools/make_sky.py

Everything is seeded, so re-running produces identical files.
"""
from __future__ import annotations

import os
import time

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "public", "img")
W, H = 2304, 4096
SEED = 1977


# --------------------------------------------------------------------------------------
# Noise helpers
# --------------------------------------------------------------------------------------
def smooth_noise(rng: np.random.Generator, shape: tuple[int, int], feature: float) -> np.ndarray:
    """Isotropic smooth gaussian noise (std ~1) with features of roughly `feature` px."""
    h, w = shape
    step = max(1.0, feature / 4.0)
    lh, lw = int(np.ceil(h / step)) + 6, int(np.ceil(w / step)) + 6
    g = rng.standard_normal((lh, lw)).astype(np.float32)
    g = ndimage.gaussian_filter(g, 1.6, mode="wrap")
    g /= g.std() + 1e-8
    if step <= 1.0:
        return g[:h, :w]
    up = ndimage.zoom(g, step, order=3, prefilter=False)
    oy, ox = int(step * 3), int(step * 3)
    out = up[oy : oy + h, ox : ox + w]
    if out.shape != (h, w):  # zoom rounding
        out = np.pad(out, ((0, h - out.shape[0]), (0, w - out.shape[1])), mode="edge")
    return out / (out.std() + 1e-8)


def fbm(rng, shape, base: float, octaves: int, gain: float = 0.55, lac: float = 2.0) -> np.ndarray:
    total = np.zeros(shape, np.float32)
    amp, f, norm = 1.0, base, 0.0
    for _ in range(octaves):
        total += amp * smooth_noise(rng, shape, f)
        norm += amp * amp
        amp *= gain
        f /= lac
        if f < 2.0:
            break
    return total / np.sqrt(norm)


def ridged(rng, shape, base: float, octaves: int, gain: float = 0.6) -> np.ndarray:
    """Filament-like ridged noise in [0,1] (1 = on a ridge)."""
    total = np.zeros(shape, np.float32)
    amp, f, norm = 1.0, base, 0.0
    for _ in range(octaves):
        n = smooth_noise(rng, shape, f)
        r = 1.0 - np.abs(np.tanh(n * 0.9))
        total += amp * r**3
        norm += amp
        amp *= gain
        f /= 2.0
        if f < 2.0:
            break
    return total / norm


def warp(field: np.ndarray, wx: np.ndarray, wy: np.ndarray) -> np.ndarray:
    h, w = field.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return ndimage.map_coordinates(field, [yy + wy, xx + wx], order=1, mode="reflect")


def upsample(a: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    fy, fx = shape[0] / a.shape[0], shape[1] / a.shape[1]
    out = ndimage.zoom(a, (fy, fx), order=3)
    return out[: shape[0], : shape[1]]


# --------------------------------------------------------------------------------------
# Star colours (approximate blackbody -> sRGB-linear, gently desaturated)
# --------------------------------------------------------------------------------------
def kelvin_to_rgb(T: np.ndarray) -> np.ndarray:
    t = T / 100.0
    r = np.where(t <= 66, 255.0, 329.698727446 * np.power(np.maximum(t - 60, 1e-3), -0.1332047592))
    g = np.where(
        t <= 66,
        99.4708025861 * np.log(np.maximum(t, 1e-3)) - 161.1195681661,
        288.1221695283 * np.power(np.maximum(t - 60, 1e-3), -0.0755148492),
    )
    b = np.where(t >= 66, 255.0, np.where(t <= 19, 0.0, 138.5177312231 * np.log(np.maximum(t - 10, 1e-3)) - 305.0447927307))
    rgb = np.stack([r, g, b], -1).clip(0, 255) / 255.0
    rgb = rgb**2.2  # to linear
    rgb /= rgb.max(-1, keepdims=True)
    return rgb


def star_colors(rng, n: int, desat: float = 0.45) -> np.ndarray:
    # Mixture: mostly F/G/K (5000-7000K), some M (3200K), some A/B (9000-16000K)
    u = rng.random(n)
    T = np.where(
        u < 0.08,
        rng.uniform(3000, 4200, n),
        np.where(u < 0.50, rng.uniform(4400, 6500, n), np.where(u < 0.80, rng.uniform(6500, 9500, n), rng.uniform(9500, 20000, n))),
    )
    c = kelvin_to_rgb(T)
    c = c * (1 - desat) + desat
    lum = c @ np.array([0.2126, 0.7152, 0.0722])
    return (c / lum[:, None]).astype(np.float32)


# --------------------------------------------------------------------------------------
# Star rendering: splat flux into per-sigma layers, then gaussian-blur each layer.
# --------------------------------------------------------------------------------------
SIGMAS = [0.55, 0.75, 1.0, 1.35, 1.8, 2.5]


def render_stars(shape, xs, ys, flux, colors, halo_frac=0.0, halo_sigma=7.0, big_halo=None):
    h, w = shape
    img = np.zeros((3, h, w), np.float32)
    lf = np.log10(np.maximum(flux, 1e-9) / np.percentile(flux, 5))
    sigma_idx = np.clip((lf * 1.25).astype(int), 0, len(SIGMAS) - 1)

    def splat(mask, weights):
        layer = np.zeros((3, h, w), np.float32)
        x, y = xs[mask], ys[mask]
        x0 = np.floor(x).astype(np.int64)
        y0 = np.floor(y).astype(np.int64)
        fx, fy = x - x0, y - y0
        for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            xi = np.clip(x0 + dx, 0, w - 1)
            yi = np.clip(y0 + dy, 0, h - 1)
            idx = yi * w + xi
            for ch in range(3):
                layer[ch] += np.bincount(idx, weights=weights * wt * colors[mask, ch], minlength=h * w).reshape(h, w).astype(np.float32)
        return layer

    def blur(layer, sg):
        for ch in range(3):
            layer[ch] = ndimage.gaussian_filter(layer[ch], sg)
        return layer

    for si, sg in enumerate(SIGMAS):
        m = sigma_idx == si
        if not m.any():
            continue
        img += blur(splat(m, flux[m]), sg)
    if halo_frac > 0:
        m = flux > np.percentile(flux, 97)
        img += blur(splat(m, flux[m] * halo_frac), halo_sigma)
    if big_halo is not None:
        frac, sg, pct = big_halo
        m = flux > np.percentile(flux, pct)
        img += blur(splat(m, flux[m] * frac), sg)
    return np.ascontiguousarray(img.transpose(1, 2, 0))


def tonemap(x: np.ndarray, exposure: float) -> np.ndarray:
    """Soft filmic shoulder, then sRGB encode."""
    y = 1.0 - np.exp(-x * exposure)
    a = 0.055
    return np.where(y <= 0.0031308, 12.92 * y, (1 + a) * np.power(np.maximum(y, 0), 1 / 2.4) - a)


def quantize(img01: np.ndarray, rng) -> np.ndarray:
    # triangular dither (+-1 LSB) kills banding in the dark gradients
    d = (rng.random(img01.shape, dtype=np.float32) - rng.random(img01.shape, dtype=np.float32))
    return np.clip(img01 * 255.0 + d + 0.5, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------------------
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


DEBUG_DIR = os.environ.get("SKY_DEBUG_DIR")


def _dbg(name: str, arr: np.ndarray) -> None:
    if not DEBUG_DIR:
        return
    x = arr.astype(np.float32)
    x = (x - x.min()) / (x.max() - x.min() + 1e-9)
    Image.fromarray((x * 255).astype(np.uint8)).resize((x.shape[1] // 2, x.shape[0] // 2)).save(os.path.join(DEBUG_DIR, f"dbg_{name}.png"))


def aniso_noise(rng, shape, fy: float, fx: float) -> np.ndarray:
    """Smooth gaussian noise (std~1) with feature sizes fy (rows) / fx (cols) in cells."""
    h, w = shape
    sy, sx = max(1.0, fy / 4.0), max(1.0, fx / 4.0)
    lh, lw = int(np.ceil(h / sy)) + 6, int(np.ceil(w / sx)) + 6
    g = rng.standard_normal((lh, lw)).astype(np.float32)
    g = ndimage.gaussian_filter(g, 1.6, mode="wrap")
    up = ndimage.zoom(g, (sy, sx), order=3, prefilter=False)
    oy, ox = int(sy * 3), int(sx * 3)
    out = up[oy : oy + h, ox : ox + w]
    return out / (out.std() + 1e-8)


def aniso_fbm(rng, shape, fy, fx, octaves, gain=0.58, ridge=False):
    total = np.zeros(shape, np.float32)
    amp, norm = 1.0, 0.0
    for _ in range(octaves):
        n = aniso_noise(rng, shape, fy, fx)
        if ridge:
            n = (1.0 - np.abs(np.tanh(n * 0.8))) ** 3
        total += amp * n
        norm += amp * (1 if ridge else amp)
        amp *= gain
        fy /= 2.0
        fx /= 2.0
        if min(fy, fx) < 2.0:
            break
    return total / (norm if ridge else np.sqrt(norm))


def make_milky_way() -> None:
    t0 = time.time()
    rng = np.random.default_rng(SEED)

    # ---- Band space: rows = along-band s, cols = across-band d (CELL full-res px per cell)
    CELL = 2.0
    SMAX, DMAX = 2700.0, 1400.0
    ns, nd = int(2 * SMAX / CELL), int(2 * DMAX / CELL)
    bs = (ns, nd)
    s_ax = (np.arange(ns, dtype=np.float32) * CELL - SMAX)[:, None]
    d_ax = (np.arange(nd, dtype=np.float32) * CELL - DMAX)[None, :]

    curve = 120.0 * np.sin(s_ax / 2600.0 + 0.5) + 45.0 * aniso_noise(rng, (ns, 1), 900, 1)
    d2 = d_ax - curve
    width = 300.0 * (1.0 + 0.16 * aniso_noise(rng, (ns, 1), 700, 1))
    P = np.exp(-((d2 / width) ** 2))
    P2 = np.exp(-((d2 / (width * 2.6)) ** 2))
    B = np.exp(-(((s_ax + 950.0) / 1100.0) ** 2)) * np.exp(-((d2 / (width * 1.35)) ** 2))
    Ms = 0.72 + 0.28 * np.tanh(aniso_noise(rng, (ns, 1), 500, 1))

    # Star clouds: lognormal fbm, elongated along the band
    T = np.exp(0.70 * aniso_fbm(rng, bs, 260, 150, 6, 0.6))
    T /= T.mean()

    glow = P * T * Ms + 0.08 * P2 + 0.9 * B * T
    dens = P * T * Ms + 0.15 * P2 + 0.9 * B * T

    # Dust: rift (off-axis, broken), elongated lanes, thin filaments
    rift_off = 55.0 + 40.0 * aniso_noise(rng, (ns, 1), 500, 1)
    rift_w = 60.0 * (1.0 + 0.5 * aniso_noise(rng, (ns, 1), 260, 1))
    rift = np.exp(-(((d2 - rift_off) / np.maximum(rift_w, 16.0)) ** 2))
    rift *= smoothstep(-0.7, 0.6, aniso_noise(rng, (ns, 1), 420, 1))
    lanes = smoothstep(-0.1, 1.7, aniso_fbm(rng, bs, 240, 90, 6, 0.6))
    lanes *= 0.55 + 0.45 * smoothstep(-1.2, 1.2, aniso_fbm(rng, bs, 60, 30, 4, 0.6))
    fil = aniso_fbm(rng, bs, 300, 70, 4, 0.55, ridge=True)
    fil = smoothstep(0.35, 0.85, fil)
    dzone = np.exp(-((d2 / (width * 1.2)) ** 2))
    tau = dzone * (1.9 * rift * (0.45 + 0.8 * lanes) + 1.25 * lanes**1.4 + 0.8 * fil * (0.25 + lanes))
    tau = ndimage.gaussian_filter(tau, 0.7)

    # Emission knots (pink) & reflection (blue)
    ha = smoothstep(1.9, 2.9, aniso_fbm(rng, bs, 50, 40, 4)) * P * np.exp(-tau)
    ha = ndimage.gaussian_filter(ha, 1.2)
    refl = smoothstep(1.5, 2.5, aniso_fbm(rng, bs, 200, 120, 3)) * P
    hue = aniso_noise(rng, bs, 1200, 600)

    # ---- Map band space -> image (half res for the smooth stuff)
    hs = (H // 2, W // 2)
    yy, xx = np.mgrid[0 : hs[0], 0 : hs[1]].astype(np.float32)
    xx = xx * 2.0 + 1.0
    yy = yy * 2.0 + 1.0
    ang = np.deg2rad(-58.0)
    dx, dy = np.cos(ang), np.sin(ang)
    cx, cy = W * 0.44, H * 0.50
    S_img = (xx - cx) * dx + (yy - cy) * dy
    D_img = -(xx - cx) * dy + (yy - cy) * dx
    coords = [(S_img + SMAX) / CELL, (D_img + DMAX) / CELL]

    def to_img(f):
        f = np.broadcast_to(f, bs).astype(np.float32)
        return ndimage.map_coordinates(f, coords, order=1, mode="nearest")

    glow_i, dens_i, tau_i = to_img(glow), to_img(dens), to_img(tau)
    P2_i, B_i, ha_i, refl_i, hue_i = to_img(P2), to_img(B), to_img(ha), to_img(refl), to_img(hue)
    _dbg("glow", glow_i)
    _dbg("tau", tau_i)
    print(f"  band fields done {time.time() - t0:.1f}s")

    ext = np.stack([np.exp(-tau_i * 0.88), np.exp(-tau_i * 0.97), np.exp(-tau_i * 1.07)], -1)
    arm_col = np.array([0.74, 0.85, 1.00], np.float32)
    warm_col = np.array([1.00, 0.86, 0.68], np.float32)
    mixw = np.clip(0.05 + 0.12 * hue_i + 0.65 * B_i, 0, 1)[..., None]
    gcol = arm_col * (1 - mixw) + warm_col * mixw
    diffuse = glow_i[..., None] * gcol * ext * 0.0125
    diffuse += ha_i[..., None] * np.array([1.0, 0.32, 0.50], np.float32) * 0.012
    diffuse += refl_i[..., None] * np.array([0.40, 0.60, 1.0], np.float32) * 0.006

    vgrad = (yy / H)[..., None]
    base = np.array([0.0006, 0.0008, 0.0020], np.float32) * (1 - vgrad) + np.array([0.0008, 0.0012, 0.0030], np.float32) * vgrad
    air = (0.85 + 0.15 * smooth_noise(rng, hs, 1200))[..., None]
    base = base * air + 0.0008 * P2_i[..., None] * np.array([0.7, 0.8, 1.0], np.float32)

    diffuse_full = np.stack([upsample(diffuse[..., c] + base[..., c], (H, W)) for c in range(3)], -1)
    dens_full = upsample(dens_i, (H, W))
    tau_full = upsample(tau_i, (H, W))
    star_density_band = None  # noqa: F841 (kept for readability)
    print(f"  diffuse done {time.time() - t0:.1f}s")

    # ---- Stars --------------------------------------------------------------------
    # 1) unresolved haze: many very faint stars, density follows the band
    n_haze = 2_600_000
    hx = rng.random(n_haze) * W
    hy = rng.random(n_haze) * H
    hxi, hyi = hx.astype(int), hy.astype(int)
    dens = dens_full[hyi, hxi]
    keep = rng.random(n_haze) < (0.03 + 0.97 * np.clip(dens, 0, 1.6) / 1.6)
    hx, hy = hx[keep], hy[keep]
    hf = (rng.pareto(1.7, hx.size) + 1.0) * 0.017
    hf *= np.exp(-tau_full[hy.astype(int), hx.astype(int)] * 0.9)
    hc = star_colors(rng, hx.size, desat=0.72)
    haze = render_stars((H, W), hx, hy, hf, hc)
    print(f"  haze stars {hx.size} {time.time() - t0:.1f}s")

    # 2) resolved stars: power-law flux, more inside the band, some foreground (dust-free)
    n_st = 60_000
    sx = rng.random(n_st) * W
    sy = rng.random(n_st) * H
    dens_s = dens_full[sy.astype(int), sx.astype(int)]
    keep = rng.random(n_st) < (0.20 + 0.80 * np.clip(dens_s, 0, 1.4) / 1.4)
    sx, sy = sx[keep], sy[keep]
    flux = (rng.pareto(1.30, sx.size) + 1.0) * 0.05
    flux = np.minimum(flux, 40.0)
    fg = rng.random(sx.size) < 0.35
    flux = np.where(fg, flux, flux * np.exp(-tau_full[sy.astype(int), sx.astype(int)] * 1.2))
    sc = star_colors(rng, sx.size, desat=0.40)
    stars = render_stars((H, W), sx, sy, flux, sc, halo_frac=0.05, halo_sigma=6.0, big_halo=(0.03, 22.0, 99.85))
    print(f"  resolved stars {sx.size} {time.time() - t0:.1f}s")

    hdr = diffuse_full + haze + stars
    out = tonemap(hdr, exposure=1.6)
    img = quantize(out, rng)
    Image.fromarray(img).save(os.path.join(OUT, "sky_milkyway.jpg"), quality=94, subsampling=0, optimize=True)
    Image.fromarray(img).resize((W // 4, H // 4), Image.LANCZOS).save(os.path.join(OUT, "sky_milkyway_preview.jpg"), quality=90)
    print(f"  sky_milkyway.jpg written {time.time() - t0:.1f}s; mean sRGB={img.mean():.1f}")


def make_starfield_layer() -> None:
    """Transparent dense starfield: RGB = star colour, A = intensity."""
    t0 = time.time()
    rng = np.random.default_rng(SEED + 101)
    n = 16_000
    xs = rng.random(n) * W
    ys = rng.random(n) * H
    flux = (rng.pareto(1.35, n) + 1.0) * 0.16
    flux = np.minimum(flux, 30.0)
    cols = star_colors(rng, n, desat=0.42)
    img = render_stars((H, W), xs, ys, flux, cols, halo_frac=0.06, halo_sigma=5.0)
    inten = 1.0 - np.exp(-img * 1.4)
    a = inten.max(-1)
    rgb = inten / np.maximum(a[..., None], 1e-6)
    rgb = np.where(a[..., None] > 1e-4, rgb, 1.0)
    # sRGB encode colour (alpha stays linear-ish coverage)
    rgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * np.power(rgb, 1 / 2.4) - 0.055)
    rgba = np.concatenate([rgb, a[..., None]], -1)
    out = np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(os.path.join(OUT, "starfield_layer.png"), optimize=True)
    print(f"  starfield_layer.png written {time.time() - t0:.1f}s")


def make_grain() -> None:
    rng = np.random.default_rng(SEED + 202)
    S = 512
    for i in range(6):
        fine = rng.standard_normal((S, S)).astype(np.float32)
        fine = ndimage.gaussian_filter(fine, 0.55, mode="wrap")
        coarse = ndimage.gaussian_filter(rng.standard_normal((S, S)).astype(np.float32), 1.3, mode="wrap")
        g = fine / fine.std() * 0.8 + coarse / coarse.std() * 0.35
        g /= g.std()
        img = np.clip(128 + g * 34, 0, 255).astype(np.uint8)
        Image.fromarray(img, "L").save(os.path.join(OUT, f"grain_{i}.png"), optimize=True)
    print("  grain tiles written")


def make_overlays() -> None:
    """Pre-rendered overlays (cheaper to composite than CSS gradients / blend modes)."""
    rng = np.random.default_rng(SEED + 303)
    # Vignette: RGBA, colour (2,3,8), alpha = radial falloff + top/bottom edges
    w, h = 1080, 1920
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - w * 0.5) / (w * 0.62)
    ny = (yy - h * 0.47) / (h * 0.60)
    r = np.sqrt(nx * nx + ny * ny)
    rad = np.clip((r - 0.62) / 0.62, 0, 1)
    rad = rad * rad * (3 - 2 * rad) * 0.62
    t = yy / h
    edges = np.maximum(np.clip(1 - t / 0.12, 0, 1) ** 1.6 * 0.35, np.clip((t - 0.80) / 0.20, 0, 1) ** 1.6 * 0.32)
    a = 1 - (1 - rad) * (1 - edges)
    a = a + (rng.random(a.shape, dtype=np.float32) - 0.5) / 255.0 * 2  # dither
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = 2, 3, 8
    rgba[..., 3] = np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(os.path.join(OUT, "vignette.png"), optimize=True)
    # Grain tiles for NORMAL blending: white/black with alpha = |noise|
    S = 512
    for i in range(6):
        fine = ndimage.gaussian_filter(rng.standard_normal((S, S)).astype(np.float32), 0.55, mode="wrap")
        coarse = ndimage.gaussian_filter(rng.standard_normal((S, S)).astype(np.float32), 1.3, mode="wrap")
        g = fine / fine.std() * 0.8 + coarse / coarse.std() * 0.35
        g /= g.std()
        out = np.zeros((S, S, 4), np.uint8)
        pos = g > 0
        out[..., :3] = np.where(pos[..., None], 255, 0)
        out[..., 3] = np.clip(np.abs(g) * 0.33 * 255, 0, 255).astype(np.uint8)
        Image.fromarray(out, "RGBA").save(os.path.join(OUT, f"grain_rgba_{i}.png"), optimize=True)
    # Full-frame grain plates (LA: white/black + alpha), slightly larger than the frame so they
    # can be shifted per frame with a cheap compositor-only transform.
    GW, GH = 1200, 2040
    for i in range(3):
        fine = ndimage.gaussian_filter(rng.standard_normal((GH, GW)).astype(np.float32), 0.55)
        coarse = ndimage.gaussian_filter(rng.standard_normal((GH, GW)).astype(np.float32), 1.3)
        g = fine / fine.std() * 0.8 + coarse / coarse.std() * 0.35
        g /= g.std()
        la = np.zeros((GH, GW, 2), np.uint8)
        la[..., 0] = np.where(g > 0, 255, 0)
        la[..., 1] = np.clip(np.abs(g) * 0.33 * 255, 0, 255).astype(np.uint8)
        Image.fromarray(la, "LA").save(os.path.join(OUT, f"grain_plate_{i}.png"), optimize=True)
    print("  overlays written")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    import sys

    which = sys.argv[1:] or ["sky", "layer", "grain", "overlays"]
    if "sky" in which:
        make_milky_way()
    if "layer" in which:
        make_starfield_layer()
    if "grain" in which:
        make_grain()
    if "overlays" in which:
        make_overlays()
