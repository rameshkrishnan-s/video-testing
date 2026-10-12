/** question: pattern interrupt. Near-black, kinetic question; FAR AWAY recedes. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, KineticWords, Starfield, useSceneTiming } from "../lib";

export const Question: React.FC = () => {
  const f = useCurrentFrame();
  const t = useSceneTiming("question");
  const words = t.beat("question").words;
  const far = words[6].startFrame;
  const s = interpolate(f, [far + 6, t.durationInFrames], [1, 0.62], CLAMP);
  const recede = { color: COLORS.accent, scale: s, filter: `blur(${interpolate(f, [far + 10, t.durationInFrames], [0, 3], CLAMP)}px)`, opacity: interpolate(f, [far + 6, t.durationInFrames], [1, 0.6], CLAMP) };
  return (
    <AbsoluteFill style={{ background: COLORS.bg0 }}>
      <Starfield seed="q" count={140} brightness={0.5} camera={{ zoom: 1 + f * 0.002 }} />
      <KineticWords words={words} lines={[4, 2, 2]} fontSize={118} y={720} animation="blur" styles={{ 6: recede, 7: recede }} />
    </AbsoluteFill>
  );
};
