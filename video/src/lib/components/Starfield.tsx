import React, { useLayoutEffect, useMemo, useRef } from "react";
import {
  AbsoluteFill,
  random,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { noise2D } from "@remotion/noise";

export type StarfieldCamera = {
  /** Pan in px for the NEAREST layer (far layers move less = parallax). */
  x?: number;
  y?: number;
  /** Zoom around warpCenter; near layers zoom more than far ones. 1 = none. */
  zoom?: number;
  /** Roll in degrees around the frame centre. */
  rotate?: number;
};

export type StarfieldProps = {
  /** Deterministic seed. */
  seed?: string | number;
  /** Number of stars (default 1100). */
  count?: number;
  camera?: StarfieldCamera;
  /**
   * 0..1 radial warp streaks (hyperspace look). Streaks point away from `warpCenter`; length
   * grows with distance from it and with star depth. Use for rush / warp moments.
   */
  warp?: number;
  /** Reverse warp direction (streaks point inward, i.e. flying backwards). */
  warpInward?: boolean;
  /** Pixel centre of the warp / zoom. Default frame centre. */
  warpCenter?: [number, number];
  /** Directional motion streak (px, nearest layer), e.g. [0, -160] for a fast tilt. */
  streak?: [number, number];
  /** Twinkle amount 0..1 (default 0.35). */
  twinkle?: number;
  /** Global brightness multiplier (default 1). */
  brightness?: number;
  /** Star size multiplier (default 1). */
  size?: number;
  /** Overall opacity. */
  opacity?: number;
  /** Tint colour mixed into all stars (e.g. COLORS.sky) and its amount 0..1. */
  tint?: string;
  tintAmount?: number;
  style?: React.CSSProperties;
};

type Star = {
  x: number; // 0..1 of the wrap area
  y: number;
  z: number; // depth 0.12 (far) .. 1 (near)
  mag: number; // base brightness 0..1
  r: number;
  g: number;
  b: number;
  tw: number; // twinkle sensitivity
  ci: number; // colour index
};

const STAR_COLORS: [number, number, number][] = [
  [255, 244, 234], // G/K white-warm
  [255, 250, 245],
  [236, 242, 255], // A white-blue
  [205, 222, 255], // B blue
  [255, 222, 190], // K orange
  [255, 205, 170], // M
];

const makeStars = (seed: string | number, count: number): Star[] => {
  const stars: Star[] = [];
  for (let i = 0; i < count; i++) {
    const r1 = random(`${seed}-x-${i}`);
    const r2 = random(`${seed}-y-${i}`);
    const r3 = random(`${seed}-z-${i}`);
    const r4 = random(`${seed}-m-${i}`);
    const r5 = random(`${seed}-c-${i}`);
    const r6 = random(`${seed}-t-${i}`);
    // more far stars than near ones
    const z = 0.12 + 0.88 * Math.pow(r3, 2.2);
    // power-law brightness, brighter for nearer stars
    const mag = Math.min(
      1,
      0.1 + 0.55 * Math.pow(r4, 4) + 0.5 * z * Math.pow(r4, 1.5),
    );
    const ci =
      r5 < 0.45
        ? 0
        : r5 < 0.65
          ? 1
          : r5 < 0.8
            ? 2
            : r5 < 0.88
              ? 3
              : r5 < 0.96
                ? 4
                : 5;
    const [cr, cg, cb] = STAR_COLORS[ci];
    stars.push({
      x: r1,
      y: r2,
      z,
      mag,
      r: cr,
      g: cg,
      b: cb,
      tw: 0.3 + 0.7 * r6,
      ci,
    });
  }
  return stars;
};

const hexToRgb = (hex: string): [number, number, number] => {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
};

/** Soft gaussian dot sprite (white-hot core, coloured halo). */
const makeSprite = (rgb: [number, number, number]): HTMLCanvasElement => {
  const s = document.createElement("canvas");
  s.width = 64;
  s.height = 64;
  const c = s.getContext("2d")!;
  const col = rgb.map((v) => Math.round(v)).join(",");
  const g = c.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.1, `rgba(${col},0.9)`);
  g.addColorStop(0.28, `rgba(${col},0.3)`);
  g.addColorStop(0.6, `rgba(${col},0.06)`);
  g.addColorStop(1, `rgba(${col},0)`);
  c.fillStyle = g;
  c.fillRect(0, 0, 64, 64);
  return s;
};

/**
 * Procedural parallax starfield on a <canvas> (transparent). Layer it over <SkyBackground/>
 * for depth. Deterministic: same frame + props = same pixels.
 */
export const Starfield: React.FC<StarfieldProps> = ({
  seed = "stars",
  count = 1100,
  camera = {},
  warp = 0,
  warpInward = false,
  warpCenter,
  streak = [0, 0],
  twinkle = 0.35,
  brightness = 1,
  size = 1,
  opacity = 1,
  tint,
  tintAmount = 0,
  style,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const ref = useRef<HTMLCanvasElement>(null);
  const stars = useMemo(() => makeStars(seed, count), [seed, count]);
  const [cx, cy] = warpCenter ?? [width / 2, height / 2];
  const palette = useMemo(() => {
    const t = tint ? hexToRgb(tint) : null;
    return STAR_COLORS.map((c): [number, number, number] =>
      t && tintAmount > 0
        ? [
            c[0] + (t[0] - c[0]) * tintAmount,
            c[1] + (t[1] - c[1]) * tintAmount,
            c[2] + (t[2] - c[2]) * tintAmount,
          ]
        : c,
    );
  }, [tint, tintAmount]);
  const sprites = useMemo(
    () => (typeof document === "undefined" ? [] : palette.map(makeSprite)),
    [palette],
  );

  useLayoutEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = "lighter";

    // wrap area larger than the frame so pans/rotations never run out of stars
    const margin = 0.25;
    const areaW = width * (1 + 2 * margin);
    const areaH = height * (1 + 2 * margin);
    const camX = camera.x ?? 0;
    const camY = camera.y ?? 0;
    const zoom = camera.zoom ?? 1;
    const rot = ((camera.rotate ?? 0) * Math.PI) / 180;
    const cosR = Math.cos(rot);
    const sinR = Math.sin(rot);
    const warpLen = Math.max(0, warp);

    for (let i = 0; i < stars.length; i++) {
      const s = stars[i];
      // parallax pan with wrap-around
      let x =
        ((((s.x * areaW - camX * s.z) % areaW) + areaW) % areaW) -
        width * margin;
      let y =
        ((((s.y * areaH - camY * s.z) % areaH) + areaH) % areaH) -
        height * margin;
      // roll around frame centre
      if (rot !== 0) {
        const dx = x - width / 2;
        const dy = y - height / 2;
        x = width / 2 + dx * cosR - dy * sinR;
        y = height / 2 + dx * sinR + dy * cosR;
      }
      // per-layer zoom around warp centre
      const zf = 1 + (zoom - 1) * s.z;
      x = cx + (x - cx) * zf;
      y = cy + (y - cy) * zf;
      if (x < -200 || x > width + 200 || y < -200 || y > height + 200) continue;

      const tw =
        twinkle > 0
          ? 1 +
            twinkle *
              s.tw *
              0.55 *
              noise2D(`${seed}-tw`, i * 0.731, frame * 0.07)
          : 1;
      const a = Math.min(1, s.mag * brightness * tw);
      if (a <= 0.01) continue;
      const [r, g, b] = palette[s.ci];
      const rad = (0.55 + 2.1 * s.z * s.z + 1.2 * s.mag * s.z) * size;

      // streak vector (tail offset from head)
      let tx = -streak[0] * s.z;
      let ty = -streak[1] * s.z;
      if (warpLen > 0) {
        const dx = x - cx;
        const dy = y - cy;
        // tail stays between the warp centre and the star (k < 1) so streaks never cross it
        const k = Math.min(0.85, warpLen * (0.06 + 0.8 * s.z * s.z));
        tx += (warpInward ? dx : -dx) * k;
        ty += (warpInward ? dy : -dy) * k;
      }
      const len = Math.hypot(tx, ty);
      const col = `${Math.round(r)},${Math.round(g)},${Math.round(b)}`;
      if (len > 1.5) {
        const grad = ctx.createLinearGradient(x + tx, y + ty, x, y);
        grad.addColorStop(0, `rgba(${col},0)`);
        grad.addColorStop(0.7, `rgba(${col},${(a * 0.45).toFixed(3)})`);
        grad.addColorStop(1, `rgba(${col},${a.toFixed(3)})`);
        ctx.strokeStyle = grad;
        ctx.lineCap = "round";
        ctx.lineWidth = Math.max(0.8, rad * 0.9);
        ctx.beginPath();
        ctx.moveTo(x + tx, y + ty);
        ctx.lineTo(x, y);
        ctx.stroke();
      }
      // head
      const d = rad * 4.2;
      ctx.globalAlpha = a;
      ctx.drawImage(sprites[s.ci], x - d / 2, y - d / 2, d, d);
      ctx.globalAlpha = 1;
    }
    ctx.globalCompositeOperation = "source-over";
  });

  return (
    <AbsoluteFill style={{ opacity, pointerEvents: "none", ...style }}>
      <canvas
        ref={ref}
        width={width}
        height={height}
        style={{ width, height }}
      />
    </AbsoluteFill>
  );
};
