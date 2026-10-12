/** orbit: "sitting still" (0 km/h vs the ground) → top-down solar view, Earth racing along its orbit at 107,000 km/h. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { CLAMP, COLORS, Counter, EASE, Earth3D, FONTS, Glow, SkyBackground, Starfield, fullPlanetCamera, useSceneTiming } from "../lib";
import { fadeIn } from "./common";

const SUN = { x: 540, y: 820 };
const R = { x: 400, y: 250 };

export const Orbit: React.FC = () => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const t = useSceneTiming("orbit");
  const racing = t.word("racing", { beat: "speed" }).startFrame;
  const hundred = t.word("hundred", { beat: "speed" }).startFrame;
  const hour = t.word("hour.", { beat: "speed" }).startFrame;
  const sw = interpolate(f, [racing - 8, racing + 6], [0, 1], { ...CLAMP, easing: EASE.inOut }); // switch to solar view
  const ang = -Math.PI * 0.15 + Math.max(0, f - racing + 8) * 0.045;
  const ex = SUN.x + Math.cos(ang) * R.x;
  const ey = SUN.y + Math.sin(ang) * R.y;
  const trail = Array.from({ length: 26 }, (_, i) => {
    const a = ang - i * 0.035;
    return `${i ? "L" : "M"} ${SUN.x + Math.cos(a) * R.x} ${SUN.y + Math.sin(a) * R.y}`;
  }).join(" ");
  return (
    <AbsoluteFill>
      <SkyBackground pan={[f * 0.3, 0]} rotate={-6} brightness={0.8} />
      <Starfield seed="orbit" count={520} warp={interpolate(f, [racing, racing + 10, hour + 10], [0, 0.55, 0.3], CLAMP)} />
      {/* calm Earth, then it shrinks away as the solar view takes over */}
      <AbsoluteFill style={{ opacity: 1 - sw, scale: String(1 - sw * 0.5) }}>
        <Earth3D camera={fullPlanetCamera({ fill: 0.62, width, height, offsetY: -140 })} facingLat={30} facingLon={-80 + f * 0.04} cloudDrift={f * 0.02} />
      </AbsoluteFill>
      <div style={{ position: "absolute", left: 0, right: 0, top: 1120, textAlign: "center", fontFamily: FONTS.mono, fontSize: 44, fontWeight: 700, color: COLORS.sky, opacity: fadeIn(f, 6) * (1 - sw) }}>
        VS. THE GROUND: 0 KM/H
      </div>
      <AbsoluteFill style={{ opacity: sw }}>
        <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
          <ellipse cx={SUN.x} cy={SUN.y} rx={R.x} ry={R.y} fill="none" stroke={COLORS.sky} strokeOpacity={0.35} strokeWidth={2} strokeDasharray="4 10" />
          <path d={trail} fill="none" stroke={COLORS.sky} strokeWidth={7} strokeLinecap="round" opacity={0.7} />
        </svg>
        <Glow x={SUN.x} y={SUN.y} radius={300} color={COLORS.accent} intensity={1.2} core={0.25} />
        <div style={{ position: "absolute", left: SUN.x - 70, top: SUN.y - 70, width: 140, height: 140, borderRadius: "50%", background: "radial-gradient(circle, #fff8e6 0%, #ffd27a 45%, #ff9a2e 80%, rgba(255,120,30,0) 100%)" }} />
        <Glow x={ex} y={ey} radius={70} color={COLORS.sky} intensity={0.9} />
        <div style={{ position: "absolute", left: ex - 18, top: ey - 18, width: 36, height: 36, borderRadius: "50%", background: "radial-gradient(circle at 35% 35%, #bfe8ff, #2b7bd6 55%, #0b2a5a)" }} />
        <div style={{ position: "absolute", left: ex + 28, top: ey - 18, fontFamily: FONTS.mono, fontSize: 28, fontWeight: 700, color: COLORS.text }}>YOU</div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 230, textAlign: "center", fontFamily: FONTS.mono, fontSize: 40, fontWeight: 700, color: COLORS.sky }}>VS. THE SUN:</div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 290, textAlign: "center" }}>
          <Counter from={0} to={107000} startFrame={racing} duration={Math.max(20, hundred + 18 - racing)} easing={EASE.expoOut} suffix=" KM/H" font="display" fontSize={124} fontWeight={900} color={COLORS.accent} />
        </div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 450, textAlign: "center", fontFamily: FONTS.mono, fontSize: 36, fontWeight: 600, color: COLORS.text, opacity: fadeIn(f, hour - 4) }}>
          ≈ 30 KM EVERY SECOND
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
