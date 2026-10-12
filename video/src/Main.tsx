import React from "react";
import {
  AbsoluteFill,
  Html5Audio,
  Sequence,
  getStaticFiles,
  staticFile,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./lib/theme";
import { SCENES, getScene, type SceneId } from "./lib/timeline";
import { GlobalOverlays, SceneHarness } from "./lib/SceneHarness";
import { SCENE_COMPONENTS } from "./scenes";
import "./lib/fonts";

const MASTER_AUDIO = "audio/master.wav";

/** The full 60 s video: all scenes back to back (from SCENES) + global overlays + master audio if present. */
export const Main: React.FC = () => {
  const { fps } = useVideoConfig();
  const hasAudio = getStaticFiles().some((f) => f.name === MASTER_AUDIO);
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg0 }}>
      {SCENES.map((s) => {
        const Scene = SCENE_COMPONENTS[s.id];
        return (
          <Sequence
            key={s.id}
            name={s.id}
            from={s.from}
            durationInFrames={s.durationInFrames}
            premountFor={fps}
          >
            <Scene />
          </Sequence>
        );
      })}
      <GlobalOverlays frameOffset={0} />
      {hasAudio ? <Html5Audio src={staticFile(MASTER_AUDIO)} /> : null}
    </AbsoluteFill>
  );
};

/** One scene rendered exactly as in Main (local frame 0 = scene start). */
export const ScenePreview: React.FC<{ id: SceneId }> = ({ id }) => {
  const Scene = SCENE_COMPONENTS[id];
  getScene(id);
  return (
    <SceneHarness id={id}>
      <Scene />
    </SceneHarness>
  );
};
