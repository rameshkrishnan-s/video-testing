import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, SPRINGS, TYPE } from "../theme";

/** Anything with a text + a (scene-local) start frame: TimedWord from useSceneTiming() works. */
export type KineticWordInput = {
  text: string;
  startFrame: number;
  /** Optional: replaces `text` for display (e.g. "IT'S" for "it's"). */
  display?: string;
};

export type KineticWordStyle = {
  color?: string;
  /** Font-size multiplier for this word. */
  scale?: number;
  weight?: number;
  letterSpacing?: string;
  /** Extra glow (text-shadow) colour. */
  glow?: string;
  opacity?: number;
  /** Extra transform appended after the entrance (e.g. "translateY(-10px) rotate(-2deg)"). */
  transform?: string;
  /** CSS filter appended (e.g. "blur(2px)") — use for receding words. */
  filter?: string;
};

export type KineticAnimation = "pop" | "slide" | "blur" | "rise" | "none";

export type KineticWordsProps = {
  words: readonly KineticWordInput[];
  /** Words per line, e.g. [4, 3, 2, 2]. If omitted, wraps automatically within `width`. */
  lines?: number[];
  /** Per-word style overrides keyed by word index. */
  styles?: Record<number, KineticWordStyle>;
  /** Default style for all words. */
  baseStyle?: KineticWordStyle;
  fontSize?: number;
  lineHeight?: number;
  /** Gap between words in em (default 0.24). */
  wordGap?: number;
  uppercase?: boolean;
  animation?: KineticAnimation;
  /** Frames the visual leads the voice (default 2). */
  lead?: number;
  /** Centre of the text block (px). Default: x = 540, y = 700. */
  x?: number;
  y?: number;
  /** Max block width (px). Default 900. */
  width?: number;
  align?: "center" | "left" | "right";
  /** Local frame when the whole block starts leaving. */
  exitFrame?: number;
  exitDuration?: number;
  exitStyle?: "fade" | "up" | "down" | "blur" | "shrink";
  color?: string;
  /**
   * Line fitting against `width`: "shrink" (default) scales down only lines that overflow,
   * "fill" scales every line to exactly `width` (justified block look, capped at maxScale),
   * "none" never scales.
   */
  fit?: "shrink" | "fill" | "none";
  /** Max line upscale for fit="fill" (default 1.6). */
  maxScale?: number;
  style?: React.CSSProperties;
};

let measureCtx: CanvasRenderingContext2D | null = null;
/** Width in px of `text` in Montserrat at the given weight/size (fonts are loaded before render). */
export const measureDisplayText = (
  text: string,
  fontSize: number,
  weight = 900,
  letterSpacingEm = -0.015,
): number => {
  if (typeof document === "undefined") return text.length * fontSize * 0.75;
  if (!measureCtx)
    measureCtx = document.createElement("canvas").getContext("2d");
  if (!measureCtx) return text.length * fontSize * 0.75;
  measureCtx.font = `${weight} ${fontSize}px Montserrat`;
  return (
    measureCtx.measureText(text).width +
    letterSpacingEm * fontSize * text.length
  );
};

/** 0..1 entrance progress (with spring overshoot for "pop") for a word at a local frame. */
export const wordEntrance = (
  frame: number,
  appearFrame: number,
  fps: number,
  animation: KineticAnimation,
): number => {
  const t = frame - appearFrame;
  if (animation === "none") return t >= 0 ? 1 : 0;
  if (animation === "pop")
    return spring({ frame: t, fps, config: SPRINGS.pop });
  return interpolate(t, [0, animation === "blur" ? 9 : 11], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
};

/**
 * Big word-synced kinetic type. Each word appears on its timestamp (minus `lead`) with a
 * pop / slide / blur / rise entrance; un-spoken words already reserve their space so the layout
 * never jumps. Words whose appear frame is <= 0 are already (almost fully) visible at frame 0.
 *
 * ```tsx
 * const t = useSceneTiming("night-sky");
 * <KineticWords words={t.beat("hook").words} lines={[4, 3, 2, 2]} styles={{ 6: { color: COLORS.accent } }} />
 * ```
 */
export const KineticWords: React.FC<KineticWordsProps> = ({
  words,
  lines,
  styles = {},
  baseStyle = {},
  fontSize = TYPE.kinetic,
  lineHeight = 1.02,
  wordGap = 0.24,
  uppercase = true,
  animation = "pop",
  lead = 2,
  x = 540,
  y = 700,
  width = 900,
  align = "center",
  exitFrame,
  exitDuration = 10,
  exitStyle = "fade",
  color = COLORS.text,
  fit = "shrink",
  maxScale = 1.6,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // split into lines
  const rows: { w: KineticWordInput; i: number }[][] = [];
  if (lines && lines.length) {
    let idx = 0;
    for (const n of lines) {
      rows.push(words.slice(idx, idx + n).map((w, k) => ({ w, i: idx + k })));
      idx += n;
    }
    if (idx < words.length)
      rows.push(words.slice(idx).map((w, k) => ({ w, i: idx + k })));
  } else {
    rows.push(words.map((w, i) => ({ w, i })));
  }

  const exitP =
    exitFrame !== undefined
      ? interpolate(frame, [exitFrame, exitFrame + exitDuration], [0, 1], {
          ...CLAMP,
          easing: EASE.expoIn,
        })
      : 0;
  if (exitP >= 1) return null;
  const exitTransform =
    exitStyle === "up"
      ? `translateY(${-140 * exitP}px)`
      : exitStyle === "down"
        ? `translateY(${140 * exitP}px)`
        : exitStyle === "shrink"
          ? `scale(${1 - 0.5 * exitP})`
          : "";
  const exitFilter = exitStyle === "blur" ? `blur(${exitP * 18}px)` : "";

  const justify =
    align === "center"
      ? "center"
      : align === "left"
        ? "flex-start"
        : "flex-end";

  return (
    <div
      style={{
        position: "absolute",
        left: x - width / 2,
        top: y,
        width,
        translate: "0 -50%",
        display: "flex",
        flexDirection: "column",
        alignItems: justify,
        pointerEvents: "none",
        opacity: 1 - exitP,
        transform: exitTransform || undefined,
        filter: exitFilter || undefined,
        ...style,
      }}
    >
      {rows.map((row, ri) => {
        let rowSize = fontSize;
        if (fit !== "none" && lines) {
          const natural =
            row.reduce((acc, { w, i }) => {
              const st = { ...baseStyle, ...styles[i] };
              const txt = w.display ?? w.text;
              return (
                acc +
                measureDisplayText(
                  uppercase ? txt.toUpperCase() : txt,
                  fontSize * (st.scale ?? 1),
                  st.weight ?? 900,
                )
              );
            }, 0) +
            wordGap * fontSize * Math.max(0, row.length - 1);
          const k = width / Math.max(1, natural);
          rowSize =
            fontSize *
            (fit === "fill" ? Math.min(k, maxScale) : Math.min(1, k));
        }
        return (
          <div
            key={ri}
            style={{
              display: "flex",
              flexWrap: lines ? "nowrap" : "wrap",
              justifyContent: justify,
              alignItems: "baseline",
              columnGap: `${wordGap}em`,
              fontSize: rowSize,
              lineHeight,
              whiteSpace: lines ? "nowrap" : "normal",
            }}
          >
            {row.map(({ w, i }) => {
              const st: KineticWordStyle = { ...baseStyle, ...styles[i] };
              let appear = w.startFrame - lead;
              if (appear <= 0) appear = Math.min(appear, -8); // visible on frame 0
              const p = wordEntrance(frame, appear, fps, animation);
              const visible = frame >= appear;
              const o = visible
                ? interpolate(
                    frame - appear,
                    [0, animation === "pop" ? 3 : 6],
                    [0, 1],
                    CLAMP,
                  )
                : 0;
              let transform = "";
              let filter = "";
              if (animation === "pop")
                transform = `translateY(${(1 - Math.min(p, 1)) * 0.18}em) scale(${0.55 + 0.45 * p})`;
              if (animation === "slide")
                transform = `translateY(${(1 - p) * 0.55}em)`;
              if (animation === "blur") {
                transform = `scale(${1.18 - 0.18 * p})`;
                filter = `blur(${(1 - p) * 16}px)`;
              }
              if (animation === "rise")
                transform = `translateY(${(1 - p) * 105}%)`;
              if (st.transform) transform += ` ${st.transform}`;
              if (st.filter) filter += ` ${st.filter}`;
              const txt = w.display ?? w.text;
              const glow = st.glow
                ? `, 0 0 ${fontSize * 0.35}px ${st.glow}`
                : "";
              const word = (
                <span
                  style={{
                    display: "inline-block",
                    fontFamily: FONTS.display,
                    fontWeight: st.weight ?? 900,
                    fontSize: `${st.scale ?? 1}em`,
                    letterSpacing: st.letterSpacing ?? "-0.015em",
                    color: st.color ?? color,
                    opacity: o * (st.opacity ?? 1),
                    transform: transform || undefined,
                    transformOrigin: "50% 70%",
                    filter: filter.trim() || undefined,
                    textShadow: `0 6px 30px rgba(0,0,0,0.55), 0 2px 4px rgba(0,0,0,0.5)${glow}`,
                  }}
                >
                  {uppercase ? txt.toUpperCase() : txt}
                </span>
              );
              return animation === "rise" ? (
                <span
                  key={i}
                  style={{
                    display: "inline-block",
                    overflow: "hidden",
                    paddingBottom: "0.06em",
                    marginBottom: "-0.06em",
                  }}
                >
                  {word}
                </span>
              ) : (
                <React.Fragment key={i}>{word}</React.Fragment>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};
