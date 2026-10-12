/** Small shared pieces for the scenes (ground silhouette, blood cells, house icon, fades). */
import React from "react";
import { interpolate, random } from "remotion";
import { CLAMP, COLORS, FONTS } from "../lib";

/** Ground-level horizon: hill silhouette + tiny human looking up. The human's feet sit at HUMAN.y + offsetY. */
export const HUMAN = { x: 540, y: 1562 };

export const Ground: React.FC<{ offsetY?: number; dawn?: number; scale?: number; opacity?: number }> = ({
  offsetY = 0,
  dawn = 0,
  scale = 1,
  opacity = 1,
}) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      opacity,
      translate: `0px ${offsetY}px`,
      scale: String(scale),
      transformOrigin: `${HUMAN.x}px ${HUMAN.y - 40}px`,
    }}
  >
    {/* horizon glow */}
    <div
      style={{
        position: "absolute",
        left: -200,
        right: -200,
        top: HUMAN.y - 520,
        height: 900,
        background: `radial-gradient(ellipse 60% 45% at 50% 62%, rgba(92,200,255,${0.16 + dawn * 0.05}), transparent 70%)`,
      }}
    />
    <div
      style={{
        position: "absolute",
        left: -200,
        right: -200,
        top: HUMAN.y - 520,
        height: 900,
        opacity: dawn,
        background: "radial-gradient(ellipse 55% 40% at 50% 66%, rgba(255,181,71,0.55), rgba(255,120,60,0.15) 45%, transparent 75%)",
      }}
    />
    <svg width={1080} height={1920 + 1400} style={{ position: "absolute", left: 0, top: 0 }}>
      <path
        d={`M -10 ${HUMAN.y + 60} C 200 ${HUMAN.y + 10}, 380 ${HUMAN.y - 2}, 540 ${HUMAN.y} S 860 ${HUMAN.y + 40}, 1090 ${HUMAN.y + 24} L 1090 3300 L -10 3300 Z`}
        fill="#020309"
      />
      <path
        d={`M -10 ${HUMAN.y + 150} C 260 ${HUMAN.y + 90}, 700 ${HUMAN.y + 160}, 1090 ${HUMAN.y + 100} L 1090 3300 L -10 3300 Z`}
        fill="#010205"
      />
      {/* tiny human, head tilted up */}
      <g transform={`translate(${HUMAN.x} ${HUMAN.y})`} fill="#020309">
        <circle cx={1.5} cy={-41} r={6} />
        <path d="M -5 -34 L 6 -34 L 7 -14 L 4 -14 L 3 0 L -1 0 L 0 -14 L -2 -14 L -2 0 L -6 0 L -5 -14 L -7 -14 Z" />
      </g>
    </svg>
  </div>
);

/** Soft red blood-cell blobs for the "iron in your blood" macro shot. */
export const BloodField: React.FC<{ frame: number; opacity: number }> = ({ frame, opacity }) => (
  <div style={{ position: "absolute", inset: 0, opacity, background: "radial-gradient(circle at 50% 45%, #3a0508, #120103 70%)" }}>
    {new Array(14).fill(0).map((_, i) => {
      const r = 120 + random(`c${i}`) * 170;
      const x = random(`x${i}`) * 1080 + Math.sin(frame / 40 + i) * 20 - frame * (0.6 + random(`v${i}`));
      const y = random(`y${i}`) * 1500 + 150 + Math.cos(frame / 50 + i) * 16;
      return (
        <div
          key={i}
          style={{
            position: "absolute",
            left: x - r,
            top: y - r * 0.8,
            width: r * 2,
            height: r * 1.6,
            borderRadius: "50%",
            rotate: `${random(`r${i}`) * 180}deg`,
            background: "radial-gradient(ellipse at 50% 50%, rgba(120,8,14,0.9) 0%, rgba(205,30,36,0.95) 38%, rgba(150,12,20,0.75) 62%, transparent 72%)",
            filter: `blur(${4 + random(`b${i}`) * 14}px)`,
          }}
        />
      );
    })}
  </div>
);

/** Periodic-table tile. */
export const ElementTile: React.FC<{ progress: number }> = ({ progress }) => (
  <div
    style={{
      position: "absolute",
      left: 540 - 190,
      top: 520,
      width: 380,
      height: 420,
      border: `4px solid ${COLORS.text}`,
      borderRadius: 18,
      background: "rgba(10,4,6,0.55)",
      backdropFilter: "blur(6px)",
      boxShadow: "0 0 80px rgba(255,90,78,0.45)",
      opacity: progress,
      scale: String(interpolate(progress, [0, 1], [0.7, 1])),
      color: COLORS.text,
      fontFamily: FONTS.display,
    }}
  >
    <div style={{ position: "absolute", left: 30, top: 22, fontFamily: FONTS.mono, fontSize: 52, fontWeight: 700 }}>26</div>
    <div style={{ position: "absolute", left: 0, right: 0, top: 88, textAlign: "center", fontSize: 190, fontWeight: 900, lineHeight: 1 }}>Fe</div>
    <div style={{ position: "absolute", left: 0, right: 0, top: 296, textAlign: "center", fontSize: 52, fontWeight: 800, letterSpacing: "0.12em", color: COLORS.danger }}>IRON</div>
    <div style={{ position: "absolute", left: 0, right: 0, top: 362, textAlign: "center", fontFamily: FONTS.mono, fontSize: 30, color: COLORS.textDim }}>55.845</div>
  </div>
);

/** Simple house icon (the "same thing" seen at different psychological distances). */
export const House: React.FC<{ size: number; outline: number; color: string }> = ({ size, outline, color }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" style={{ overflow: "visible" }}>
    <path
      d="M 10 48 L 50 12 L 90 48 L 80 48 L 80 90 L 20 90 L 20 48 Z"
      fill={color}
      fillOpacity={1 - outline}
      stroke={color}
      strokeWidth={4}
      strokeLinejoin="round"
    />
    <rect x={42} y={62} width={16} height={28} fill={COLORS.bg0} opacity={1 - outline} />
    <rect x={27} y={56} width={12} height={12} fill="#FFE2A8" opacity={1 - outline} />
    <rect x={61} y={56} width={12} height={12} fill="#FFE2A8" opacity={1 - outline} />
  </svg>
);

export const fadeIn = (f: number, start: number, dur = 8) => interpolate(f, [start, start + dur], [0, 1], CLAMP);
export const fadeOut = (f: number, start: number, dur = 8) => interpolate(f, [start, start + dur], [1, 0], CLAMP);
