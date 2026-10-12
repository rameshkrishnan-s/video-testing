/** pull-back: from the human on the ground, a continuous zoom-out to the whole Earth with a YOU ARE HERE pin. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { CLAMP, EASE, Earth3D, SkyBackground, Starfield, expLerp, fullPlanetCamera, mixCameras, nadirCamera, useSceneTiming } from "../lib";
import { Ground } from "./common";

const PIN = { lat: 40.7, lon: -74 };

export const PullBack: React.FC = () => {
  const f = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const t = useSceneTiming("pull-back");
  const reveal = t.word("never", { beat: "truth" }).startFrame + 10;
  const p = interpolate(f, [0, reveal], [0, 1], { ...CLAMP, easing: EASE.inOut });
  const farCam = fullPlanetCamera({ fill: 0.8, width, height, offsetY: -90 });
  const alt = expLerp(0.02, farCam.position[2] - 1, p);
  const cam0 = mixCameras(nadirCamera({ altitude: alt, fov: 34 }), farCam, interpolate(p, [0.7, 1], [0, 1], CLAMP));
  const camera = { ...cam0, position: [cam0.position[0], cam0.position[1], Math.max(cam0.position[2], 1 + alt)] as [number, number, number] };
  const groundScale = interpolate(f, [0, 16], [1, 0.12], { ...CLAMP, easing: EASE.expoIn });
  return (
    <AbsoluteFill>
      <SkyBackground pan={[0, -120 + f * 0.6]} zoom={1.1 - p * 0.06} rotate={-10} />
      <Starfield seed="pull" count={450} camera={{ zoom: 1.6 - p * 0.6 }} />
      <AbsoluteFill style={{ opacity: interpolate(f, [2, 14], [0, 1], CLAMP) }}>
        <Earth3D
          camera={camera}
          facingLat={PIN.lat - 6}
          facingLon={PIN.lon + 8 + f * 0.05}
          cloudDrift={f * 0.02}
          pins={[{ ...PIN, label: "YOU ARE HERE", progress: interpolate(f, [reveal - 6, reveal + 16], [0, 1], CLAMP) }]}
        />
      </AbsoluteFill>
      <Ground offsetY={-430} scale={groundScale} opacity={interpolate(f, [6, 16], [1, 0], CLAMP)} />
      {/* impact flash on the reveal */}
      <AbsoluteFill style={{ background: "#cfe9ff", opacity: interpolate(f, [reveal - 10, reveal - 7, reveal + 6], [0, 0.35, 0], CLAMP), mixBlendMode: "screen" }} />
    </AbsoluteFill>
  );
};
