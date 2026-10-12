import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, TYPE } from "../theme";

export type HudLabelProps = {
  text: string;
  /** Point being labelled (px). Gets a small dot / tick. */
  anchor: [number, number];
  /** End of the leader line, where the text starts (px). */
  label: [number, number];
  /** Leader goes diagonal then horizontal (true, default) or straight to `label`. */
  elbow?: boolean;
  /** Length of the horizontal run after the elbow (px). Default 40. */
  run?: number;
  /** Local frame when the draw-on starts. */
  startFrame?: number;
  /** Frames for the full draw-on (dot -> line -> text). Default 20. */
  duration?: number;
  /** Local frame when it starts to disappear (optional). */
  exitFrame?: number;
  exitDuration?: number;
  /** Line + dot colour (default sky cyan). */
  color?: string;
  /** Text colour (default near-white). */
  textColor?: string;
  fontSize?: number;
  fontWeight?: number;
  /** Second, dimmer line under the label (e.g. units / source). */
  sublabel?: string;
  sublabelSize?: number;
  /** Marker drawn at the anchor. */
  marker?: "dot" | "ring" | "tick" | "none";
  /** Text box on the left or right of the line end. Default: away from the anchor. */
  side?: "left" | "right";
  /** Overall opacity multiplier. */
  opacity?: number;
  /** Line width (default 2.5). */
  lineWidth?: number;
};

/**
 * HUD callout: JetBrains Mono label + thin leader line + anchor marker, animated draw-on.
 * All frames are LOCAL (useCurrentFrame() of the caller's sequence).
 */
export const HudLabel: React.FC<HudLabelProps> = ({
  text,
  anchor,
  label,
  elbow = true,
  run = 40,
  startFrame = 0,
  duration = 20,
  exitFrame,
  exitDuration = 10,
  color = COLORS.sky,
  textColor = COLORS.text,
  fontSize = TYPE.hud,
  fontWeight = 700,
  sublabel,
  sublabelSize = TYPE.hudSmall,
  marker = "dot",
  side,
  opacity = 1,
  lineWidth = 2.5,
}) => {
  const frame = useCurrentFrame() - startFrame;
  if (frame < 0) return null;
  const d = Math.max(4, duration);
  const markerP = interpolate(frame, [0, d * 0.3], [0, 1], {
    ...CLAMP,
    easing: EASE.backOut,
  });
  const lineP = interpolate(frame, [d * 0.15, d * 0.65], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
  const textP = interpolate(frame, [d * 0.5, d], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
  const exitP =
    exitFrame !== undefined
      ? interpolate(
          frame + startFrame,
          [exitFrame, exitFrame + exitDuration],
          [1, 0],
          CLAMP,
        )
      : 1;
  const alpha = opacity * exitP;
  if (alpha <= 0) return null;

  const dir = side ?? (label[0] >= anchor[0] ? "right" : "left");
  const sgn = dir === "right" ? 1 : -1;
  const pts: [number, number][] = elbow
    ? [anchor, label, [label[0] + sgn * run, label[1]]]
    : [anchor, label];
  const segs = pts
    .slice(1)
    .map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
  const total = segs.reduce((a, b) => a + b, 0);
  const end = pts[pts.length - 1];
  const path = pts
    .map(
      (p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`,
    )
    .join(" ");

  // characters typed on, with a block cursor while typing
  const chars = Math.round(text.length * textP);
  const typing = textP > 0 && textP < 1;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        opacity: alpha,
      }}
    >
      <svg
        width="100%"
        height="100%"
        style={{ position: "absolute", inset: 0, overflow: "visible" }}
      >
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth={lineWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={total}
          strokeDashoffset={total * (1 - lineP)}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
        {marker === "dot" ? (
          <circle
            cx={anchor[0]}
            cy={anchor[1]}
            r={6 * markerP}
            fill={color}
            style={{ filter: `drop-shadow(0 0 8px ${color})` }}
          />
        ) : null}
        {marker === "ring" ? (
          <>
            <circle
              cx={anchor[0]}
              cy={anchor[1]}
              r={11 * markerP}
              fill="none"
              stroke={color}
              strokeWidth={2}
            />
            <circle
              cx={anchor[0]}
              cy={anchor[1]}
              r={3 * markerP}
              fill={color}
            />
          </>
        ) : null}
        {marker === "tick" ? (
          <line
            x1={anchor[0] - 10 * markerP}
            y1={anchor[1]}
            x2={anchor[0] + 10 * markerP}
            y2={anchor[1]}
            stroke={color}
            strokeWidth={3}
          />
        ) : null}
      </svg>
      <div
        style={{
          position: "absolute",
          left: end[0] + sgn * 14,
          top: end[1],
          translate: dir === "right" ? "0 -50%" : "-100% -50%",
          textAlign: dir === "right" ? "left" : "right",
          whiteSpace: "nowrap",
          fontFamily: FONTS.mono,
          color: textColor,
          textShadow: "0 0 14px rgba(0,0,0,0.85), 0 2px 4px rgba(0,0,0,0.9)",
        }}
      >
        <div
          style={{
            fontSize,
            fontWeight,
            letterSpacing: "0.06em",
            lineHeight: 1.1,
          }}
        >
          {text.slice(0, chars)}
          {typing ? (
            <span
              style={{
                display: "inline-block",
                width: 0,
                overflow: "visible",
                verticalAlign: "-0.12em",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: fontSize * 0.5,
                  height: fontSize * 0.95,
                  background: color,
                  marginLeft: 2,
                }}
              />
            </span>
          ) : null}
          <span style={{ opacity: 0 }}>{text.slice(chars)}</span>
        </div>
        {sublabel ? (
          <div
            style={{
              fontSize: sublabelSize,
              fontWeight: 500,
              letterSpacing: "0.05em",
              color: COLORS.textDim,
              marginTop: 6,
              opacity: interpolate(textP, [0.5, 1], [0, 1], CLAMP),
            }}
          >
            {sublabel}
          </div>
        ) : null}
      </div>
    </div>
  );
};
