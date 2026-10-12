/** star-stuff: iron in your blood → a star collapses and explodes (supernova). */
import React from "react";
import { AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, Glow, SkyBackground, SPRINGS, Starfield, useSceneTiming } from "../lib";
import { BloodField, ElementTile, fadeIn } from "./common";

const C = { x: 540, y: 800 };

export const StarStuff: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useSceneTiming("star-stuff");
  const iron = t.word("iron", { beat: "stars" }).startFrame;
  const forged = t.word("Forged", { beat: "stars" }).startFrame;
  const boom = t.word("exploded", { beat: "stars" }).startFrame + 2;
  const tile = spring({ frame: f - iron + 2, fps, config: SPRINGS.pop });
  const inBlood = f < forged - 1;
  const since = f - boom;
  const starR = interpolate(f, [forged - 1, boom - 4, boom], [240, 120, 40], { ...CLAMP, easing: EASE.expoIn });
  const ring = interpolate(since, [0, 45], [0, 1100], { ...CLAMP, easing: EASE.expoOut });
  return (
    <AbsoluteFill style={{ background: COLORS.bg0 }}>
      {inBlood ? (
        <>
          <BloodField frame={f} opacity={1} />
          <ElementTile progress={tile} />
        </>
      ) : (
        <>
          <SkyBackground zoom={1.15 + f * 0.001} rotate={20} brightness={0.55} />
          <Starfield seed="nova" count={380} brightness={0.7} camera={{ zoom: 1 + Math.max(0, since) * 0.004 }} />
          {since < 0 ? (
            <Glow x={C.x} y={C.y} radius={starR} color="#bcd8ff" intensity={1.4} core={0.35} streak={0.6} />
          ) : (
            <>
              {/* nebula bloom */}
              <Glow x={C.x - 60} y={C.y - 40} radius={interpolate(since, [0, 60], [200, 700], CLAMP)} color="#ff4fa0" intensity={0.7} />
              <Glow x={C.x + 80} y={C.y + 50} radius={interpolate(since, [0, 60], [200, 650], CLAMP)} color={COLORS.accent} intensity={0.7} />
              <Glow x={C.x} y={C.y} radius={interpolate(since, [0, 60], [150, 520], CLAMP)} color={COLORS.sky} intensity={0.6} />
              <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
                <circle cx={C.x} cy={C.y} r={ring} fill="none" stroke="#e8f4ff" strokeWidth={interpolate(since, [0, 45], [30, 3], CLAMP)} opacity={interpolate(since, [0, 50], [0.9, 0], CLAMP)} />
                {new Array(160).fill(0).map((_, i) => {
                  const a = random(`a${i}`) * Math.PI * 2;
                  const v = 6 + random(`v${i}`) * 26;
                  const d = v * Math.pow(Math.max(0, since), 0.85);
                  const len = 10 + v * 1.6;
                  const x1 = C.x + Math.cos(a) * d;
                  const y1 = C.y + Math.sin(a) * d;
                  const col = [COLORS.accent, "#ffffff", "#ff7bc0", COLORS.sky][i % 4];
                  return <line key={i} x1={x1} y1={y1} x2={x1 - Math.cos(a) * len} y2={y1 - Math.sin(a) * len} stroke={col} strokeWidth={2 + (i % 3)} strokeLinecap="round" opacity={interpolate(since, [0, 70], [1, 0.25], CLAMP)} />;
                })}
              </svg>
              <Glow x={C.x} y={C.y} radius={interpolate(since, [0, 8, 40], [500, 260, 140], CLAMP)} color="#ffffff" intensity={1.3} core={0.3} />
            </>
          )}
          <div style={{ position: "absolute", left: 0, right: 0, top: 230, textAlign: "center", opacity: fadeIn(f, boom - 2, 6) }}>
            <div style={{ fontFamily: FONTS.display, fontWeight: 900, fontSize: 96, color: COLORS.text, letterSpacing: "0.06em" }}>SUPERNOVA</div>
            <div style={{ fontFamily: FONTS.mono, fontWeight: 600, fontSize: 30, color: COLORS.accent, marginTop: 8 }}>BEFORE EARTH EXISTED · &gt;4.5 BILLION YEARS AGO</div>
          </div>
          <AbsoluteFill style={{ background: "#fff", opacity: interpolate(since, [-1, 0, 10], [0, 0.9, 0], CLAMP) }} />
        </>
      )}
      <AbsoluteFill style={{ background: COLORS.bg0, opacity: interpolate(f, [t.durationInFrames - 6, t.durationInFrames], [0, 1], CLAMP) }} />
    </AbsoluteFill>
  );
};
