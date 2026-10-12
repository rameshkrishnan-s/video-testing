/** Perf probe: toggle layers via input props, e.g. --props='{"sky":true}'. */
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Captions, Grain, SkyBackground, Starfield, Vignette, COLORS } from "../lib";

export type PerfTestProps = { sky?: boolean; rotate?: boolean; stars?: boolean; grain?: boolean; vignette?: boolean; captions?: boolean };

export const PerfTest: React.FC<PerfTestProps> = ({ sky, rotate, stars, grain, vignette, captions }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg0 }}>
      {sky ? <SkyBackground pan={[0, -frame]} rotate={rotate ? frame * 0.05 : 0} /> : null}
      {stars ? <Starfield camera={{ y: -frame * 2 }} /> : null}
      {vignette ? <Vignette /> : null}
      {captions ? <Captions frameOffset={200} /> : null}
      {grain ? <Grain /> : null}
    </AbsoluteFill>
  );
};
