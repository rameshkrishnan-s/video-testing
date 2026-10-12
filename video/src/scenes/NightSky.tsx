/** night-sky: hook (kinetic), echo (HUD labels receding), loop (reticle locks on YOU). */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CLAMP, COLORS, EASE, HudLabel, KineticWords, Reticle, SkyBackground, Starfield, useSceneTiming } from "../lib";
import { Ground, HUMAN } from "./common";

export const NightSky: React.FC = () => {
  const f = useCurrentFrame();
  const t = useSceneTiming("night-sky");
  const echo = t.beat("echo");
  const loop = t.beat("loop");
  // camera: tilt up through hook/echo, then swing down to the human for loop
  const tilt = interpolate(f, [0, echo.endFrame, loop.startFrame - 4, loop.startFrame + 28], [0, 300, 300, -430], {
    ...CLAMP,
    easing: EASE.inOut,
  });
  const out = t.word("Out", { beat: "echo" }).startFrame;
  const up = t.word("Up", { beat: "echo" }).startFrame;
  const far = t.word("Far", { beat: "echo" }).startFrame;
  const echoOut = loop.startFrame - 2;
  const lift = interpolate(f, [out, echoOut], [0, -120], CLAMP);
  return (
    <AbsoluteFill>
      <SkyBackground pan={[0, tilt * 0.55]} zoom={1.08 + f * 0.0004} rotate={-10} />
      <Starfield seed="night" count={420} camera={{ y: tilt * 0.8 }} twinkle={0.6} />
      <Ground offsetY={tilt} />
      <KineticWords
        words={t.beat("hook").words}
        lines={[4, 3, 2, 2]}
        fontSize={112}
        y={640}
        animation="pop"
        styles={{ 6: { color: COLORS.accent }, 9: { scale: 1.12 }, 10: { scale: 1.12 } }}
        exitFrame={out - 6}
        exitStyle="blur"
      />
      <div style={{ position: "absolute", inset: 0, translate: `0px ${lift}px` }}>
        <HudLabel text="OUT THERE" anchor={[790, 900]} label={[560, 1060]} startFrame={out - 2} fontSize={56} exitFrame={echoOut} marker="ring" />
        <HudLabel text="UP THERE" anchor={[300, 610]} label={[500, 740]} startFrame={up - 2} fontSize={44} opacity={0.85} exitFrame={echoOut} marker="ring" />
        <HudLabel text="FAR AWAY" anchor={[720, 330]} label={[540, 430]} startFrame={far - 2} fontSize={34} opacity={0.7} exitFrame={echoOut} marker="ring" />
      </div>
      <Reticle
        x={HUMAN.x}
        y={HUMAN.y - 430 - 22}
        size={130}
        color={COLORS.accent}
        startFrame={t.word("It's", { beat: "loop" }).startFrame}
        lockDuration={t.word("you.", { beat: "loop" }).startFrame - t.word("It's", { beat: "loop" }).startFrame}
        label="YOU"
        labelPosition="above"
      />
    </AbsoluteFill>
  );
};
