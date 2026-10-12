/** someday: dreams, goals, the life you want get flung into the sky until they're just stars. SOMEDAY flickers far away. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, EASE, FONTS, Glow, SkyBackground, Starfield, useSceneTiming } from "../lib";
import { fadeIn } from "./common";

const VP = { x: 540, y: 330 };

const Fly: React.FC<{ text: string; start: number; dx: number; y0: number; f: number }> = ({ text, start, dx, y0, f }) => {
  const p = interpolate(f, [start + 4, start + 32], [0, 1], { ...CLAMP, easing: EASE.expoIn });
  const pop = interpolate(f, [start - 2, start + 6], [0.6, 1], { ...CLAMP, easing: EASE.backOut });
  const x = 540 + (VP.x + dx - 540) * p;
  const y = y0 + (VP.y + 40 - y0) * p;
  return (
    <>
      <div style={{ position: "absolute", left: 0, top: y - 70, width: 1080, textAlign: "center", translate: `${x - 540}px 0px`, scale: String(pop * (1 - 0.97 * p)), opacity: fadeIn(f, start - 2, 4) * (1 - interpolate(p, [0.85, 1], [0, 1], CLAMP)), filter: `blur(${p * 6}px)`, fontFamily: FONTS.display, fontWeight: 900, fontSize: 130, color: COLORS.text, textShadow: "0 0 30px rgba(92,200,255,0.5)" }}>
        {text}
      </div>
      <Glow x={VP.x + dx} y={VP.y + 40} radius={34} color={COLORS.sky} intensity={interpolate(p, [0.8, 1], [0, 1], CLAMP) * (0.8 + 0.2 * Math.sin(f / 5 + dx))} />
    </>
  );
};

export const Someday: React.FC = () => {
  const f = useCurrentFrame();
  const t = useSceneTiming("someday");
  const w = (q: string) => t.word(q, { beat: "life" }).startFrame;
  const some = w("someday.");
  return (
    <AbsoluteFill>
      <SkyBackground pan={[0, 120 + f * 0.5]} zoom={1.12} rotate={8} />
      <Starfield seed="someday" count={420} camera={{ zoom: 1 + f * 0.0012 }} />
      <Fly text="DREAMS" start={w("dreams.")} dx={-150} y0={640} f={f} />
      <Fly text="GOALS" start={w("goals.")} dx={160} y0={900} f={f} />
      <Fly text="THE LIFE" start={w("life")} dx={10} y0={770} f={f} />
      <div style={{ position: "absolute", left: 0, right: 0, top: VP.y - 120, textAlign: "center", fontFamily: FONTS.mono, fontWeight: 700, fontSize: 42, letterSpacing: "0.5em", color: COLORS.accent, opacity: fadeIn(f, some - 2, 10) * (0.55 + 0.45 * Math.abs(Math.sin(f / 3.3))), textShadow: `0 0 18px ${COLORS.accent}` }}>
        SOMEDAY
      </div>
    </AbsoluteFill>
  );
};
