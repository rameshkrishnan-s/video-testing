import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, TYPE } from "../theme";
import type { ProjectedPoint } from "./earthMath";

export type EarthPinSpec = {
  lat: number;
  lon: number;
  /** Text next to the pin, e.g. "YOU ARE HERE". Omit for a bare dot. */
  label?: string;
  /** Default amber accent. */
  color?: string;
  /** 0..1 reveal (dot pops, then leader line draws, then label). Default 1. */
  progress?: number;
  /** Dot diameter in px (default 18). */
  size?: number;
  /** Where the label goes. Default "right". */
  labelSide?: "right" | "left";
  /** Leader line rise/run in px (default [70, -90] = right & up). */
  leader?: [number, number];
  /** Pulsing rings (default true). */
  pulse?: boolean;
  /** Label font size (default TYPE.hud). */
  fontSize?: number;
};

/** HTML pin drawn at a projected point (used by Earth3D `pins`, usable standalone). */
export const EarthPin: React.FC<
  EarthPinSpec & {
    point: Pick<ProjectedPoint, "x" | "y" | "visible" | "facing">;
  }
> = ({
  point,
  label,
  color = COLORS.accent,
  progress = 1,
  size = 18,
  labelSide = "right",
  leader,
  pulse = true,
  fontSize = TYPE.hud,
}) => {
  const frame = useCurrentFrame();
  if (!point.visible || progress <= 0) return null;
  const limbFade = interpolate(point.facing, [0.02, 0.22], [0, 1], CLAMP);
  const pop = interpolate(progress, [0, 0.35], [0, 1], {
    ...CLAMP,
    easing: EASE.backOut,
  });
  const lineP = interpolate(progress, [0.25, 0.7], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
  const textP = interpolate(progress, [0.55, 1], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
  const [runRaw, rise] = leader ?? [70, -90];
  const run = labelSide === "left" ? -Math.abs(runRaw) : Math.abs(runRaw);
  const len = Math.hypot(run, rise);

  const rings = pulse
    ? [0, 0.5].map((off) => {
        const t = (((frame / 48 + off) % 1) + 1) % 1;
        return { scale: 1 + t * 2.6, opacity: (1 - t) * 0.7 };
      })
    : [];

  return (
    <div
      style={{
        position: "absolute",
        left: point.x,
        top: point.y,
        opacity: limbFade,
        pointerEvents: "none",
      }}
    >
      {rings.map((r, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: -size / 2,
            top: -size / 2,
            width: size,
            height: size,
            borderRadius: "50%",
            border: `2px solid ${color}`,
            scale: String(r.scale * pop),
            opacity: r.opacity * pop,
          }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          left: -size / 2,
          top: -size / 2,
          width: size,
          height: size,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 ${size}px ${color}, 0 0 ${size * 2.5}px ${color}88`,
          scale: String(pop),
        }}
      />
      {label ? (
        <>
          <svg
            style={{
              position: "absolute",
              left: Math.min(0, run) - 2,
              top: Math.min(0, rise) - 2,
              overflow: "visible",
            }}
            width={Math.abs(run) + 4}
            height={Math.abs(rise) + 4}
          >
            <line
              x1={(run < 0 ? -run : 0) + 2}
              y1={(rise < 0 ? -rise : 0) + 2}
              x2={(run < 0 ? 0 : run) + 2}
              y2={(rise < 0 ? 0 : rise) + 2}
              stroke={color}
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeDasharray={len}
              strokeDashoffset={len * (1 - lineP)}
            />
          </svg>
          <div
            style={{
              position: "absolute",
              left: run,
              top: rise,
              translate: labelSide === "left" ? "-100% -50%" : "0 -50%",
              paddingLeft: labelSide === "left" ? 0 : 14,
              paddingRight: labelSide === "left" ? 14 : 0,
              whiteSpace: "nowrap",
              fontFamily: FONTS.mono,
              fontWeight: 700,
              fontSize,
              letterSpacing: "0.08em",
              color,
              opacity: textP,
              textShadow: `0 0 18px rgba(0,0,0,0.9), 0 2px 6px rgba(0,0,0,0.9)`,
              clipPath: `inset(-20% ${labelSide === "left" ? 0 : (1 - textP) * 100}% -20% ${labelSide === "left" ? (1 - textP) * 100 : 0}%)`,
            }}
          >
            {label}
          </div>
        </>
      ) : null}
    </div>
  );
};
