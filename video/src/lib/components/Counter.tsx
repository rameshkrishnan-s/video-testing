import React from "react";
import { interpolate, useCurrentFrame, type EasingFunction } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, TYPE } from "../theme";

export type CounterProps = {
  from?: number;
  to: number;
  /** Local frame where counting starts. */
  startFrame?: number;
  /** Frames to reach `to`. Default 30. */
  duration?: number;
  /** Default expo-out. */
  easing?: EasingFunction;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  /** Thousands separator. Default ",". */
  separator?: string;
  font?: "mono" | "display";
  fontSize?: number;
  fontWeight?: number;
  color?: string;
  /** Glow colour (text-shadow) — set to null for none. Default = color at low alpha. */
  glow?: string | null;
  /** Small unit after the number (rendered smaller + dim), e.g. "KM/H". */
  unit?: string;
  unitScale?: number;
  style?: React.CSSProperties;
};

/** Format with fixed decimals and a thousands separator (deterministic, no Intl). */
export const formatNumber = (
  v: number,
  decimals = 0,
  separator = ",",
): string => {
  const neg = v < 0;
  const fixed = Math.abs(v).toFixed(decimals);
  const [int, frac] = fixed.split(".");
  const withSep = int.replace(/\B(?=(\d{3})+(?!\d))/g, separator);
  return `${neg ? "-" : ""}${withSep}${frac ? `.${frac}` : ""}`;
};

/** Value of a counter at a frame (for custom renderers). */
export const counterValue = (
  frame: number,
  o: {
    from?: number;
    to: number;
    startFrame?: number;
    duration?: number;
    easing?: EasingFunction;
  },
): number =>
  interpolate(
    frame,
    [o.startFrame ?? 0, (o.startFrame ?? 0) + Math.max(1, o.duration ?? 30)],
    [o.from ?? 0, o.to],
    {
      ...CLAMP,
      easing: o.easing ?? EASE.expoOut,
    },
  );

/** Eased number ticker with tabular digits (digits don't jitter while counting). */
export const Counter: React.FC<CounterProps> = ({
  from = 0,
  to,
  startFrame = 0,
  duration = 30,
  easing,
  decimals = 0,
  prefix = "",
  suffix = "",
  separator = ",",
  font = "mono",
  fontSize = TYPE.counter,
  fontWeight,
  color = COLORS.text,
  glow,
  unit,
  unitScale = 0.36,
  style,
}) => {
  const frame = useCurrentFrame();
  const v = counterValue(frame, { from, to, startFrame, duration, easing });
  const shown = Number(v.toFixed(decimals));
  const g = glow === undefined ? `${color}55` : glow;
  return (
    <div
      style={{
        fontFamily: font === "mono" ? FONTS.mono : FONTS.display,
        fontWeight: fontWeight ?? (font === "mono" ? 700 : 900),
        fontSize,
        color,
        fontVariantNumeric: "tabular-nums",
        fontFeatureSettings: '"tnum" 1',
        letterSpacing: font === "mono" ? "-0.02em" : "-0.01em",
        lineHeight: 1,
        whiteSpace: "nowrap",
        textShadow: g
          ? `0 0 ${fontSize * 0.25}px ${g}, 0 4px 18px rgba(0,0,0,0.6)`
          : "0 4px 18px rgba(0,0,0,0.6)",
        ...style,
      }}
    >
      {prefix}
      {formatNumber(shown, decimals, separator)}
      {suffix}
      {unit ? (
        <span
          style={{
            fontSize: fontSize * unitScale,
            marginLeft: fontSize * 0.12,
            opacity: 0.8,
            letterSpacing: "0.04em",
            fontWeight: 700,
          }}
        >
          {unit}
        </span>
      ) : null}
    </div>
  );
};
