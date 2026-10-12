/**
 * Shared design tokens for "You've Never Left Space".
 * Source of truth for colours, type, layout zones and easing. See DESIGN_SYSTEM.md.
 */
import { Easing } from "remotion";

// ---------------------------------------------------------------------------------------
// Video
// ---------------------------------------------------------------------------------------
export const VIDEO = {
  width: 1080,
  height: 1920,
  fps: 30,
  durationInFrames: 1800,
} as const;

// ---------------------------------------------------------------------------------------
// Palette (BRIEF §4)
// ---------------------------------------------------------------------------------------
export const COLORS = {
  bg0: "#04050A", // void
  bg1: "#0A1022", // deep navy
  bg2: "#121A33",
  text: "#F4F6FF",
  textDim: "rgba(244,246,255,0.62)",
  accent: "#FFB547", // solar amber — key numbers, "YOU", emphasis
  sky: "#5CC8FF", // atmosphere cyan — HUD lines, data, science labels
  danger: "#FF5A4E", // blood / iron red, sparingly
  // helpers
  black: "#000000",
  white: "#FFFFFF",
  shadow: "rgba(2,3,8,0.85)",
} as const;

/** `rgba()` string from a #RRGGBB hex + alpha. */
export const withAlpha = (hex: string, alpha: number): string => {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
};

// ---------------------------------------------------------------------------------------
// Typography
// ---------------------------------------------------------------------------------------
export const FONTS = {
  /** Headlines, kinetic type, captions. Use weight 800/900. */
  display: "Montserrat, sans-serif",
  /** HUD labels, units, counters, source tags. Use weight 500/700 + tabular nums. */
  mono: "'JetBrains Mono', monospace",
} as const;

/** Minimum / recommended sizes at 1080 px width (BRIEF §4). */
export const TYPE = {
  headline: 112, // min 96
  headlineMin: 96,
  kinetic: 128,
  caption: 72, // 68-76
  hud: 36, // min 34
  hudMin: 34,
  hudSmall: 28, // only for secondary tags (source line); keep >= 26
  counter: 150,
} as const;

// ---------------------------------------------------------------------------------------
// Layout (1080x1920)
// ---------------------------------------------------------------------------------------
export const SAFE = {
  left: 90,
  right: 90,
  top: 160,
  /** Bottom 380 px are covered by platform UI. */
  bottomUi: 380,
  /** Right 150 px are covered by platform UI (like/comment buttons). */
  rightUi: 150,
} as const;

/** Usable box for anything important. */
export const SAFE_BOX = {
  x0: SAFE.left,
  x1: VIDEO.width - SAFE.rightUi, // 930
  y0: SAFE.top,
  y1: VIDEO.height - SAFE.bottomUi, // 1540
} as const;

/** Captions band (full width). Keep clear of text / busy detail while captions show. */
export const CAPTION_ZONE = { top: 1240, bottom: 1480 } as const;

/** Where hero visuals live. */
export const HERO_ZONE = { top: 220, bottom: 1200 } as const;

/** Horizontal centre of the platform-safe area (slightly left of frame centre). */
export const SAFE_CENTER_X = (SAFE_BOX.x0 + SAFE_BOX.x1) / 2; // 510

// ---------------------------------------------------------------------------------------
// Motion
// ---------------------------------------------------------------------------------------
export const EASE = {
  /** Entrances (BRIEF default). */
  expoOut: Easing.bezier(0.16, 1, 0.3, 1),
  /** Exits / accelerations. */
  expoIn: Easing.bezier(0.7, 0, 0.84, 0),
  /** Camera moves, symmetric. */
  inOut: Easing.bezier(0.65, 0, 0.35, 1),
  /** Gentle sine-like in/out. */
  sineInOut: Easing.bezier(0.37, 0, 0.63, 1),
  /** Slight overshoot (back-out) for pops without a spring. */
  backOut: Easing.bezier(0.34, 1.56, 0.64, 1),
  linear: Easing.linear,
} as const;

/** Spring configs for `spring({frame, fps, config})`. */
export const SPRINGS = {
  /** Word pop: quick, small overshoot. */
  pop: { damping: 12, stiffness: 220, mass: 0.6 },
  /** Snappy without bounce. */
  snappy: { damping: 200, stiffness: 300, mass: 0.6 },
  /** Soft settle. */
  soft: { damping: 26, stiffness: 90, mass: 1 },
} as const;

/** Common clamp option bag for interpolate(). */
export const CLAMP = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

// ---------------------------------------------------------------------------------------
// Assets (all relative to public/, use with staticFile())
// ---------------------------------------------------------------------------------------
export const ASSETS = {
  sky: "img/sky_milkyway.jpg", // 2304x4096
  skySize: { width: 2304, height: 4096 },
  starLayer: "img/starfield_layer.png", // 2304x4096 transparent
  grain: [0, 1, 2, 3, 4, 5].map((i) => `img/grain_${i}.png`),
  earthDay: "textures/earth_day_4096.jpg",
  earthNight: "textures/earth_night_4096.jpg",
  /** R = bump/elevation, G = roughness (land=1, ocean=0), B = clouds. */
  earthBrc: "textures/earth_bump_roughness_clouds_4096.jpg",
  moon: "textures/moon_1024.jpg",
} as const;
