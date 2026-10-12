import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, TYPE } from "../theme";

export type ReticleProps = {
  /** Target centre (px). */
  x: number;
  y: number;
  /** Final bracket box size (px). Default 150. */
  size?: number;
  color?: string;
  /** Local frame when the reticle starts converging. */
  startFrame?: number;
  /** Frames to lock on. Default 18. */
  lockDuration?: number;
  /** Optional label shown after lock (e.g. "YOU"). */
  label?: string;
  labelSize?: number;
  /** Label position relative to the box. Default "below". */
  labelPosition?: "below" | "above" | "right";
  /** Local frame to start fading out (optional). */
  exitFrame?: number;
  exitDuration?: number;
  /** Line thickness (default 4). */
  thickness?: number;
  /** Show outer rotating dashed ring (default true). */
  ring?: boolean;
};

/**
 * Animated targeting reticle: corner brackets converge + rotate in, a dashed ring spins,
 * crosshair ticks, a lock flash, then an optional label. Frames are LOCAL.
 */
export const Reticle: React.FC<ReticleProps> = ({
  x,
  y,
  size = 150,
  color = COLORS.accent,
  startFrame = 0,
  lockDuration = 18,
  label,
  labelSize = TYPE.hud + 8,
  labelPosition = "below",
  exitFrame,
  exitDuration = 10,
  thickness = 4,
  ring = true,
}) => {
  const frame = useCurrentFrame();
  const f = frame - startFrame;
  if (f < 0) return null;
  const p = interpolate(f, [0, lockDuration], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
  const appear = interpolate(f, [0, 4], [0, 1], CLAMP);
  const exit =
    exitFrame !== undefined
      ? interpolate(frame, [exitFrame, exitFrame + exitDuration], [1, 0], CLAMP)
      : 1;
  const alpha = appear * exit;
  if (alpha <= 0) return null;

  const s = size * interpolate(p, [0, 1], [2.1, 1]);
  const rot = interpolate(p, [0, 1], [-50, 0]);
  const flash = interpolate(
    f,
    [lockDuration - 2, lockDuration + 2, lockDuration + 10],
    [0, 1, 0],
    CLAMP,
  );
  const arm = s * 0.26;
  const h = s / 2;
  const labelP = interpolate(f, [lockDuration, lockDuration + 10], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
  const ringR = size * 0.78;
  const circ = 2 * Math.PI * ringR;
  const glow = `drop-shadow(0 0 ${6 + flash * 14}px ${color})`;

  const corner = (sx: number, sy: number) =>
    `M${sx * h},${sy * (h - arm)} L${sx * h},${sy * h} L${sx * (h - arm)},${sy * h}`;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: 0,
        height: 0,
        opacity: alpha,
        pointerEvents: "none",
      }}
    >
      <svg
        width={size * 4}
        height={size * 4}
        viewBox={`${-size * 2} ${-size * 2} ${size * 4} ${size * 4}`}
        style={{
          position: "absolute",
          left: -size * 2,
          top: -size * 2,
          overflow: "visible",
          filter: glow,
        }}
      >
        <g transform={`rotate(${rot})`}>
          {[
            [-1, -1],
            [1, -1],
            [1, 1],
            [-1, 1],
          ].map(([sx, sy], i) => (
            <path
              key={i}
              d={corner(sx, sy)}
              fill="none"
              stroke={color}
              strokeWidth={thickness}
              strokeLinecap="square"
            />
          ))}
        </g>
        {ring ? (
          <circle
            r={ringR * interpolate(p, [0, 1], [1.5, 1])}
            fill="none"
            stroke={color}
            strokeOpacity={0.55}
            strokeWidth={2}
            strokeDasharray={`${circ / 36} ${circ / 36}`}
            transform={`rotate(${frame * 1.2})`}
          />
        ) : null}
        {/* crosshair ticks */}
        {[0, 90, 180, 270].map((a) => (
          <line
            key={a}
            x1={0}
            y1={-h * 0.55}
            x2={0}
            y2={-h * 0.3}
            stroke={color}
            strokeWidth={thickness * 0.6}
            transform={`rotate(${a})`}
            opacity={p}
          />
        ))}
        <circle r={4 + flash * 3} fill={color} opacity={p} />
        {flash > 0 ? (
          <circle
            r={h * (1 + flash * 0.5)}
            fill="none"
            stroke={color}
            strokeWidth={2}
            opacity={flash * 0.8}
          />
        ) : null}
      </svg>
      {label ? (
        <div
          style={{
            position: "absolute",
            left: labelPosition === "right" ? h + 24 : 0,
            top:
              labelPosition === "below"
                ? h + 22
                : labelPosition === "above"
                  ? -h - 22
                  : 0,
            translate:
              labelPosition === "right"
                ? "0 -50%"
                : labelPosition === "above"
                  ? "-50% -100%"
                  : "-50% 0",
            fontFamily: FONTS.mono,
            fontWeight: 700,
            fontSize: labelSize,
            letterSpacing: "0.12em",
            color,
            whiteSpace: "nowrap",
            opacity: labelP,
            scale: String(interpolate(labelP, [0, 1], [0.85, 1])),
            textShadow: `0 0 16px ${color}88, 0 2px 6px rgba(0,0,0,0.9)`,
          }}
        >
          {label}
        </div>
      ) : null}
    </div>
  );
};
