/** already: warp back to Earth ("you're already in it"), then down to the human; ends matching night-sky frame 0 for a seamless loop. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { CLAMP, COLORS, EASE, Earth3D, KineticWords, SkyBackground, Starfield, fullPlanetCamera, useSceneTiming } from "../lib";
import { Ground } from "./common";

const PIN = { lat: 40.7, lon: -74 };

export const Already: React.FC = () => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const t = useSceneTiming("already");
  const D = t.durationInFrames;
  const pay = t.beat("payoff").words;
  const fin = t.beat("final").words;
  const fs = t.beat("final").startFrame;
  const fill = interpolate(f, [0, 28, fs - 8, fs + 14], [0.06, 0.8, 0.84, 4], { ...CLAMP, easing: EASE.expoOut });
  const earthOn = interpolate(f, [fs + 2, fs + 14], [1, 0], CLAMP);
  const groundOn = interpolate(f, [fs + 2, fs + 14], [0, 1], CLAMP);
  const groundScale = interpolate(f, [fs, fs + 18], [0.15, 1], { ...CLAMP, easing: EASE.expoOut });
  const tilt = interpolate(f, [D - 70, D - 6], [-430, 0], { ...CLAMP, easing: EASE.inOut });
  const dawn = interpolate(f, [fs + 10, fs + 50, D - 60, D - 12], [0, 0.9, 0.9, 0], CLAMP);
  return (
    <AbsoluteFill>
      <SkyBackground pan={[0, interpolate(f, [fs, D - 6], [-230, 0], { ...CLAMP, easing: EASE.inOut })]} zoom={1.08} rotate={-10} />
      <Starfield seed="night" count={420} camera={{ y: f >= fs ? tilt * 0.8 : 0 }} warp={interpolate(f, [0, 4, 30], [0, 1, 0], CLAMP)} />
      {earthOn > 0 ? (
        <AbsoluteFill style={{ opacity: earthOn }}>
          <Earth3D
            camera={fullPlanetCamera({ fill, width, height, offsetY: 120 })}
            facingLat={PIN.lat - 6}
            facingLon={PIN.lon + 4 + f * 0.04}
            cloudDrift={f * 0.02}
            pins={[{ ...PIN, label: "YOU ARE HERE", progress: interpolate(f, [22, 40], [0, 1], CLAMP) }]}
          />
        </AbsoluteFill>
      ) : null}
      {groundOn > 0 ? <Ground offsetY={tilt} dawn={dawn} scale={groundScale} opacity={groundOn} /> : null}
      <KineticWords words={pay.slice(0, 6)} lines={[3, 3]} fontSize={96} y={330} animation="pop" exitFrame={pay[6].startFrame - 3} exitStyle="up" />
      <KineticWords words={pay.slice(6)} lines={[2, 2]} fontSize={128} y={330} animation="pop" styles={{ 2: { color: COLORS.accent }, 3: { color: COLORS.accent } }} exitFrame={fs - 4} exitStyle="blur" />
      <KineticWords words={fin.slice(0, 7)} lines={[4, 3]} fontSize={92} y={470} animation="rise" exitFrame={fin[7].startFrame - 3} exitStyle="up" />
      <KineticWords words={fin.slice(7)} lines={[2, 2]} fontSize={124} y={470} animation="pop" styles={{ 2: { color: COLORS.accent }, 3: { color: COLORS.accent } }} exitFrame={D - 40} exitDuration={22} exitStyle="fade" />
    </AbsoluteFill>
  );
};
