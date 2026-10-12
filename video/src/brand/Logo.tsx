/** Channel avatar (800x800, shown as a circle): Earth + amber "you are here" pin on deep space. */
import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, Earth3D, Starfield, directionFromAngles, fullPlanetCamera } from "../lib";
import "../lib/fonts";

export const Logo: React.FC = () => (
  <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 45%, ${COLORS.bg2}, ${COLORS.bg0} 70%)` }}>
    <Starfield seed="logo" count={90} brightness={0.6} />
    <Earth3D
      camera={fullPlanetCamera({ fill: 0.7, width: 800, height: 800, offsetY: 30 })}
      facingLat={22}
      facingLon={-60}
      sunDirection={directionFromAngles(-38, 22)}
      halo={1.2}
      antialias
    />
    {/* pin, tip resting on the planet */}
    <svg width={800} height={800} style={{ position: "absolute", inset: 0 }}>
      <defs>
        <radialGradient id="pinGlow">
          <stop offset="0%" stopColor={COLORS.accent} stopOpacity={0.6} />
          <stop offset="100%" stopColor={COLORS.accent} stopOpacity={0} />
        </radialGradient>
      </defs>
      <ellipse cx={400} cy={418} rx={46} ry={14} fill="#000" opacity={0.35} />
      <circle cx={400} cy={300} r={170} fill="url(#pinGlow)" />
      <path
        d="M 400 418 C 372 370, 316 330, 316 270 A 84 84 0 1 1 484 270 C 484 330, 428 370, 400 418 Z"
        fill={COLORS.accent}
        stroke="#FFE0A6"
        strokeWidth={5}
      />
      <circle cx={400} cy={268} r={34} fill={COLORS.bg0} />
    </svg>
  </AbsoluteFill>
);
