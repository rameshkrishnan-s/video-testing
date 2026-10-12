import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { SkyBackground } from "./SkyBackground";
import { Starfield } from "./Starfield";
import { HudLabel } from "./HudLabel";
import { getSceneTiming, type SceneId } from "../timeline";
import { COLORS, FONTS, HERO_ZONE } from "../theme";

/** Temporary stand-in used by src/scenes/*.tsx until the scene agents replace them. */
export const ScenePlaceholder: React.FC<{ id: SceneId }> = ({ id }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = getSceneTiming(id);
  const drift = interpolate(
    frame,
    [0, Math.max(1, t.durationInFrames)],
    [0, -120],
  );
  return (
    <AbsoluteFill>
      <SkyBackground pan={[0, drift]} />
      <Starfield seed={id} camera={{ y: drift * 2 }} />
      <div
        style={{
          position: "absolute",
          left: 90,
          right: 150,
          top: HERO_ZONE.top + 260,
          textAlign: "center",
          fontFamily: FONTS.display,
          fontWeight: 900,
          fontSize: 110,
          color: COLORS.text,
          textTransform: "uppercase",
          letterSpacing: "-0.02em",
          textShadow: "0 6px 30px rgba(0,0,0,0.6)",
        }}
      >
        {id}
      </div>
      <HudLabel
        text={`BEATS: ${t.beatIds.join(" · ").toUpperCase()}`}
        sublabel={`from ${t.from} · ${t.durationInFrames}f · local ${frame}/${durationInFrames}`}
        anchor={[300, 1040]}
        label={[360, 960]}
        startFrame={4}
      />
    </AbsoluteFill>
  );
};
