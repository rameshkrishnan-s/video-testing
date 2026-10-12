import React from "react";
import { withAlpha } from "../theme";

export type GlowProps = {
  /** Centre in px. */
  x: number;
  y: number;
  /** Radius of the wide halo in px. */
  radius: number;
  /** #RRGGBB. Default warm white. */
  color?: string;
  /** 0..1+ overall intensity. Default 1. */
  intensity?: number;
  /** Relative size of the hot core (0..1 of radius). Default 0.12. 0 = no core. */
  core?: number;
  /** Anamorphic horizontal streak: length as a multiple of radius (0 = none). */
  streak?: number;
  /** Streak angle in degrees (default 0 = horizontal). */
  streakAngle?: number;
  /** Blend mode. "screen" (default) is safe; "plus-lighter" is fully additive. */
  blend?: "screen" | "plus-lighter" | "normal";
  style?: React.CSSProperties;
};

/**
 * Soft radial light / lens bloom: wide halo + hot core + optional anamorphic streak.
 * Pure CSS gradients (cheap, crisp at any scale). Animate x/y/radius/intensity per frame.
 */
export const Glow: React.FC<GlowProps> = ({
  x,
  y,
  radius,
  color = "#FFF4E0",
  intensity = 1,
  core = 0.12,
  streak = 0,
  streakAngle = 0,
  blend = "screen",
  style,
}) => {
  const i = Math.max(0, intensity);
  if (i <= 0.001 || radius <= 0) return null;
  const halo = `radial-gradient(circle at 50% 50%, ${withAlpha(color, Math.min(1, 0.55 * i))} 0%, ${withAlpha(color, Math.min(1, 0.22 * i))} 22%, ${withAlpha(color, Math.min(1, 0.07 * i))} 48%, ${withAlpha(color, 0)} 72%)`;
  const coreR = radius * core;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        width: 0,
        height: 0,
        pointerEvents: "none",
        mixBlendMode: blend,
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: x - radius,
          top: y - radius,
          width: radius * 2,
          height: radius * 2,
          background: halo,
          mixBlendMode: blend,
        }}
      />
      {core > 0 ? (
        <div
          style={{
            position: "absolute",
            left: x - coreR,
            top: y - coreR,
            width: coreR * 2,
            height: coreR * 2,
            borderRadius: "50%",
            background: `radial-gradient(circle, rgba(255,255,255,${Math.min(1, i)}) 0%, ${withAlpha(color, Math.min(1, 0.8 * i))} 35%, ${withAlpha(color, 0)} 100%)`,
            mixBlendMode: blend,
          }}
        />
      ) : null}
      {streak > 0 ? (
        <div
          style={{
            position: "absolute",
            left: x - radius * streak,
            top: y - radius * 0.06,
            width: radius * streak * 2,
            height: radius * 0.12,
            rotate: `${streakAngle}deg`,
            background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${withAlpha(color, Math.min(1, 0.6 * i))} 0%, ${withAlpha(color, Math.min(1, 0.15 * i))} 40%, ${withAlpha(color, 0)} 100%)`,
            mixBlendMode: blend,
          }}
        />
      ) : null}
    </div>
  );
};
