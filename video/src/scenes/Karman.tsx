/** karman: Earth limb close-up, altitude ruler to 100 km, a car driving straight up for an hour. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, Counter, EASE, Earth3D, FONTS, HudLabel, SkyBackground, Starfield, limbCamera, useSceneTiming } from "../lib";
import { fadeIn } from "./common";

const RX = 800;
const Y0 = 1215; // 0 km (horizon)
const Y100 = 430; // 100 km
const kmY = (km: number) => Y0 + (Y100 - Y0) * (km / 100);

export const Karman: React.FC = () => {
  const f = useCurrentFrame();
  const t = useSceneTiming("karman");
  const edge = t.word("edge", { beat: "distance" }).startFrame;
  const hundred = t.word("hundred", { beat: "distance" }).startFrame;
  const car = t.word("car", { beat: "distance" }).startFrame;
  const drive = t.word("drive", { beat: "distance" }).startFrame;
  const hour = t.word("hour.", { beat: "distance" }).startFrame;
  const grow = interpolate(f, [edge - 4, hundred + 16], [0, 1], { ...CLAMP, easing: EASE.expoOut });
  const carP = interpolate(f, [drive, hour + 4], [0, 1], { ...CLAMP, easing: EASE.inOut });
  const carY = kmY(100 * carP);
  const camera = limbCamera({ altitude: interpolate(f, [0, t.durationInFrames], [0.16, 0.115]), horizonY: 0.64, fov: 44 });
  return (
    <AbsoluteFill>
      <SkyBackground pan={[0, -260 - f * 0.4]} rotate={-14} brightness={0.85} />
      <Starfield seed="karman" count={380} brightness={0.75} camera={{ y: -f * 0.3 }} />
      <Earth3D camera={camera} facingLat={24} facingLon={-36 + f * 0.03} sunDirection={[-0.45, 0.82, 0.2]} cloudDrift={f * 0.02} />
      {/* ruler */}
      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
        <line x1={RX} y1={Y0} x2={RX} y2={Y0 + (Y100 - Y0) * grow} stroke={COLORS.sky} strokeWidth={3} />
        {[0, 20, 40, 60, 80, 100].map((km) => {
          const o = interpolate(grow, [km / 100 - 0.05, km / 100], [0, 1], CLAMP);
          return (
            <g key={km} opacity={o}>
              <line x1={RX - 16} x2={RX + 16} y1={kmY(km)} y2={kmY(km)} stroke={COLORS.sky} strokeWidth={3} />
              <text x={RX + 30} y={kmY(km) + 11} fill={COLORS.sky} fontFamily={FONTS.mono} fontSize={32} fontWeight={600}>
                {km} KM
              </text>
            </g>
          );
        })}
        <line
          x1={0}
          x2={1080 * interpolate(f, [hundred, hundred + 18], [0, 1], { ...CLAMP, easing: EASE.expoOut })}
          y1={Y100}
          y2={Y100}
          stroke={COLORS.accent}
          strokeWidth={4}
          strokeDasharray="18 12"
        />
      </svg>
      <HudLabel text="KÁRMÁN LINE" sublabel="EDGE OF SPACE · BY CONVENTION" anchor={[RX, Y100]} label={[120, 300]} side="right" startFrame={hundred + 8} color={COLORS.accent} textColor={COLORS.accent} fontSize={40} />
      <div style={{ position: "absolute", left: 90, top: 560, opacity: fadeIn(f, hundred - 2) }}>
        <Counter from={0} to={100} startFrame={hundred - 2} duration={22} suffix=" KM" font="display" fontSize={150} fontWeight={900} color={COLORS.text} />
      </div>
      {/* car driving straight up */}
      <div style={{ position: "absolute", left: RX - 26, top: carY - 46, opacity: fadeIn(f, car - 4, 6), scale: String(interpolate(f, [car - 4, car + 6], [0.4, 1], { ...CLAMP, easing: EASE.backOut })) }}>
        <svg width={52} height={92} viewBox="0 0 52 92">
          <rect x={4} y={4} width={44} height={84} rx={14} fill={COLORS.accent} />
          <rect x={10} y={18} width={32} height={18} rx={5} fill="#3a2a10" />
          <rect x={10} y={58} width={32} height={14} rx={4} fill="#3a2a10" />
          <rect x={0} y={14} width={6} height={16} rx={2} fill="#111" />
          <rect x={46} y={14} width={6} height={16} rx={2} fill="#111" />
          <rect x={0} y={62} width={6} height={16} rx={2} fill="#111" />
          <rect x={46} y={62} width={6} height={16} rx={2} fill="#111" />
        </svg>
      </div>
      <div style={{ position: "absolute", left: RX - 330, top: carY - 26, width: 280, textAlign: "right", fontFamily: FONTS.mono, fontSize: 36, fontWeight: 700, color: COLORS.accent, opacity: fadeIn(f, drive, 6) * interpolate(f, [hour, hour + 6], [1, 0], CLAMP) }}>
        100 KM/H →
      </div>
      <div style={{ position: "absolute", left: 90, top: 780, fontFamily: FONTS.display, fontWeight: 900, fontSize: 96, color: COLORS.accent, opacity: fadeIn(f, hour - 2, 6), scale: String(interpolate(f, [hour - 2, hour + 8], [0.7, 1], { ...CLAMP, easing: EASE.backOut })), transformOrigin: "left center" }}>
        ≈ 1 HOUR
      </div>
    </AbsoluteFill>
  );
};
