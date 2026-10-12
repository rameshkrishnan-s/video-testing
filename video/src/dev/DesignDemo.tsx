/**
 * DesignDemo — every shared component on one timeline (reference for scene agents).
 *   0- 59  KineticWords (pop) over Sky + Starfield
 *  60-119  HudLabels + Reticle + Glow
 * 120-179  Counter + Starfield warp
 */
import React from "react";
import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from "remotion";
import {
  CLAMP,
  COLORS,
  Counter,
  EASE,
  Glow,
  HudLabel,
  KineticWords,
  Reticle,
  SkyBackground,
  Starfield,
  GlobalOverlays,
} from "../lib";
import "../lib/fonts";

export const DESIGN_DEMO_FRAMES = 180;

const DEMO_WORDS = [
  "Why",
  "do",
  "we",
  "always",
  "talk",
  "about",
  "space",
  "like",
  "it's",
  "somewhere",
  "else?",
].map((text, i) => ({
  text,
  startFrame: 2 + i * 4,
}));

export const DesignDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const warp = interpolate(frame, [130, 165], [0, 1], {
    ...CLAMP,
    easing: EASE.expoIn,
  });
  return (
    <AbsoluteFill>
      <SkyBackground
        pan={[0, interpolate(frame, [0, 180], [0, -260])]}
        rotate={interpolate(frame, [0, 180], [0, 6])}
      />
      <Starfield
        seed="demo"
        camera={{
          y: interpolate(frame, [0, 180], [0, -500]),
          zoom: 1 + warp * 0.6,
        }}
        warp={warp}
      />
      <Sequence durationInFrames={60} layout="none">
        <KineticWords
          words={DEMO_WORDS}
          lines={[4, 3, 2, 2]}
          y={720}
          styles={{
            6: { color: COLORS.accent },
            9: { scale: 1.12 },
            10: { scale: 1.12 },
          }}
          exitFrame={50}
          exitStyle="up"
        />
      </Sequence>
      <Sequence from={60} durationInFrames={60} layout="none">
        <HudLabel
          text="OUT THERE"
          anchor={[700, 420]}
          label={[560, 560]}
          startFrame={0}
        />
        <HudLabel
          text="UP THERE"
          anchor={[330, 300]}
          label={[420, 430]}
          startFrame={10}
          fontSize={34}
          opacity={0.8}
          sublabel="≈ 100 KM"
        />
        <Glow
          x={540}
          y={980}
          radius={260}
          color={COLORS.accent}
          intensity={0.55}
          streak={1.6}
        />
        <Reticle x={540} y={980} size={140} startFrame={18} label="YOU" />
      </Sequence>
      <Sequence from={120} durationInFrames={60} layout="none">
        <div
          style={{
            position: "absolute",
            left: 0,
            width: 1080,
            top: 640,
            display: "flex",
            justifyContent: "center",
          }}
        >
          <Counter
            from={0}
            to={107000}
            startFrame={4}
            duration={40}
            color={COLORS.accent}
            unit="KM/H"
            fontSize={140}
          />
        </div>
      </Sequence>
      <GlobalOverlays frameOffset={0} captions={false} />
    </AbsoluteFill>
  );
};
