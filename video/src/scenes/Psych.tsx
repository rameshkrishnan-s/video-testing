/** psych: psychological distance — the same thing gets blurrier, greyer, more abstract the farther it is. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, Starfield, useSceneTiming } from "../lib";
import { House, fadeIn } from "./common";

const VP = { x: 540, y: 580 };
const FLOOR = 1190;
const DEPTHS = [0, 0.36, 0.64, 0.86];

export const Psych: React.FC = () => {
  const f = useCurrentFrame();
  const t = useSceneTiming("psych");
  const w = (q: string) => t.word(q, { beat: "psych" }).startFrame;
  const appear = [w("farther"), w("away"), w("something"), w("feels,")];
  const abstract = interpolate(f, [w("abstractly"), w("abstractly") + 14], [0, 1], CLAMP);
  const blurrier = interpolate(f, [w("Blurrier."), w("Blurrier.") + 10], [1, 2.2], CLAMP);
  const lessYours = interpolate(f, [w("yours."), w("yours.") + 12], [0, 1], CLAMP);
  const grid = interpolate(f, [0, 24], [0, 1], { ...CLAMP, easing: EASE.expoOut });
  return (
    <AbsoluteFill style={{ background: `linear-gradient(${COLORS.bg0}, ${COLORS.bg1})` }}>
      <Starfield seed="psych" count={200} brightness={0.45} />
      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0, opacity: grid }}>
        {new Array(15).fill(0).map((_, i) => {
          const x = -1100 + i * 235;
          return <line key={`v${i}`} x1={x} y1={FLOOR} x2={VP.x} y2={VP.y} stroke={COLORS.sky} strokeOpacity={0.22} strokeWidth={2} />;
        })}
        {new Array(9).fill(0).map((_, i) => {
          const k = Math.pow((i + 1) / 9, 2);
          return <line key={`h${i}`} x1={0} x2={1080} y1={VP.y + (FLOOR - VP.y) * k} y2={VP.y + (FLOOR - VP.y) * k} stroke={COLORS.sky} strokeOpacity={0.12 + 0.12 * k} strokeWidth={2} />;
        })}
      </svg>
      <div style={{ position: "absolute", left: 0, right: 0, top: 150, textAlign: "center", opacity: fadeIn(f, 2, 10) }}>
        <div style={{ fontFamily: FONTS.display, fontWeight: 900, fontSize: 78, color: COLORS.text, letterSpacing: "0.02em" }}>PSYCHOLOGICAL DISTANCE</div>
        <div style={{ fontFamily: FONTS.mono, fontWeight: 500, fontSize: 28, color: COLORS.textDim, marginTop: 10 }}>CONSTRUAL LEVEL THEORY · TROPE &amp; LIBERMAN</div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: VP.y - 52, textAlign: "center", fontFamily: FONTS.mono, fontSize: 30, fontWeight: 700, color: COLORS.textDim, opacity: fadeIn(f, appear[3]) }}>THERE · SOMEDAY</div>
      {DEPTHS.map((d, i) => {
        const p = interpolate(f, [appear[i] - 2, appear[i] + 10], [0, 1], { ...CLAMP, easing: EASE.expoOut });
        const y = FLOOR - 70 - (FLOOR - 70 - VP.y - 30) * Math.pow(d, 0.75);
        const x = VP.x + (i % 2 ? 1 : -1) * 200 * (1 - d);
        const size = 300 * (1 - 0.82 * d) * (1 - (d > 0.6 ? lessYours * 0.85 : 0));
        const outline = d > 0.3 ? abstract * Math.min(1, d * 1.3) : 0;
        return (
          <div key={i} style={{ position: "absolute", left: x - size / 2, top: y - size, opacity: p * (1 - d * 0.45), scale: String(0.6 + 0.4 * p), filter: `blur(${d * 7 * blurrier}px) saturate(${1 - d})` }}>
            <House size={size} outline={outline} color={d > 0.3 ? "#cfd6e6" : COLORS.accent} />
          </div>
        );
      })}
      <div style={{ position: "absolute", left: VP.x - 16, top: FLOOR - 40, width: 32, height: 32, borderRadius: "50%", background: COLORS.accent, boxShadow: `0 0 30px ${COLORS.accent}` }} />
      <div style={{ position: "absolute", left: VP.x + 30, top: FLOOR - 42, fontFamily: FONTS.mono, fontSize: 30, fontWeight: 700, color: COLORS.accent }}>YOU · HERE · NOW</div>
    </AbsoluteFill>
  );
};
