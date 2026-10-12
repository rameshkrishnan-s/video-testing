/**
 * EarthTest — reference shots for Earth3D (also a living example of the camera recipes).
 *   0- 89  full planet, slow rotation, YOU ARE HERE pin
 *  90-179  close limb shot (day side), Kármán-style
 * 180-269  fast zoom-out from low altitude to the full planet
 * 270-359  sunrise limb (sun behind the planet)
 */
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  CLAMP,
  EASE,
  Earth3D,
  SkyBackground,
  Starfield,
  directionFromAngles,
  expLerp,
  fullPlanetCamera,
  limbCamera,
  mixCameras,
  nadirCamera,
  type EarthCamera,
  type Vec3,
} from "../lib";
import "../lib/fonts";

export const EARTH_TEST_FRAMES = 360;

export type EarthTestProps = { aa?: boolean; clouds?: boolean; atmo?: boolean; sky?: boolean };

export const EarthTest: React.FC<EarthTestProps> = ({ aa = true, clouds = true, atmo = true, sky = true }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const section = Math.min(3, Math.floor(frame / 90));
  const f = frame - section * 90;

  let camera: EarthCamera;
  let sun: Vec3 = directionFromAngles(-62, 18);
  let facingLon = -40 + frame * 0.06;
  let facingLat = 28;
  let pins: { lat: number; lon: number; label?: string; progress?: number }[] =
    [];
  let skyPan: [number, number] = [0, 0];

  if (section === 0) {
    camera = fullPlanetCamera({ fill: 0.86, width, height, offsetY: -40 });
    facingLon = -75 + f * 0.08;
    facingLat = 22;
    pins = [
      {
        lat: 40.7,
        lon: -74,
        label: "YOU ARE HERE",
        progress: interpolate(f, [10, 40], [0, 1], CLAMP),
      },
    ];
  } else if (section === 1) {
    camera = limbCamera({ altitude: 0.16, horizonY: 0.6, fov: 42 });
    facingLon = -160 + f * 0.03;
    facingLat = 5;
    sun = directionFromAngles(-70, 30);
    skyPan = [0, -200];
  } else if (section === 2) {
    const t = interpolate(f, [0, 75], [0, 1], { ...CLAMP, easing: EASE.inOut });
    const far = fullPlanetCamera({ fill: 0.72, width, height });
    const alt = expLerp(0.12, far.position[2] - 1, t);
    camera = mixCameras(
      nadirCamera({ altitude: alt, fov: 30 }),
      far,
      interpolate(t, [0.7, 1], [0, 1], CLAMP),
    );
    camera = {
      ...camera,
      position: [
        camera.position[0],
        camera.position[1],
        Math.max(camera.position[2], 1 + alt),
      ],
    };
    facingLon = -74 + f * 0.02;
    facingLat = 40.7;
    pins = [
      {
        lat: 40.7,
        lon: -74,
        progress: interpolate(t, [0.5, 0.8], [0, 1], CLAMP),
      },
    ];
  } else {
    camera = limbCamera({ altitude: 0.1, horizonY: 0.62, fov: 46 });
    facingLon = 100 + f * 0.03;
    facingLat = 10;
    // sun just below the horizon, ahead of the camera (+Y in world for limbCamera heading 0)
    sun = [0.15, 0.97, -0.18];
    skyPan = [0, -300];
  }

  return (
    <AbsoluteFill>
      {sky ? <SkyBackground pan={skyPan} rotate={-12} brightness={0.9} /> : null}
      {sky ? <Starfield seed="earthtest" count={500} brightness={0.8} /> : null}
      <Earth3D
        camera={camera}
        sunDirection={sun}
        facingLon={facingLon}
        facingLat={facingLat}
        cloudDrift={frame * 0.02}
        antialias={aa}
        cloudOpacity={clouds ? 1 : 0}
        atmosphere={atmo ? 1 : 0}
        halo={atmo ? 1 : 0}
        pins={pins}
      />
    </AbsoluteFill>
  );
};
