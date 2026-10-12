import React from "react";
import { AbsoluteFill } from "remotion";
import { Captions } from "./components/Captions";
import { Grain, Vignette } from "./components/Overlays";
import { getScene, type SceneId } from "./timeline";
import { COLORS } from "./theme";
import "./fonts";

export type GlobalOverlaysProps = {
  /** Global frame of local frame 0 (0 in Main, scene.from in a scene preview). */
  frameOffset?: number;
  captions?: boolean;
  grain?: boolean;
  vignette?: boolean;
};

/** Overlays applied ONCE on top of everything by Main (and by SceneHarness for previews). */
export const GlobalOverlays: React.FC<GlobalOverlaysProps> = ({
  frameOffset = 0,
  captions = true,
  grain = true,
  vignette = true,
}) => (
  <>
    {vignette ? <Vignette /> : null}
    {captions ? <Captions frameOffset={frameOffset} /> : null}
    {grain ? <Grain frameOffset={frameOffset} /> : null}
  </>
);

/**
 * Renders a scene exactly as it appears in Main: scene content (local frame 0 = scene start)
 * + global overlays offset to global time. Used by the per-scene "Scene-<id>" compositions.
 */
export const SceneHarness: React.FC<{
  id: SceneId;
  children: React.ReactNode;
  overlays?: boolean;
}> = ({ id, children, overlays = true }) => {
  const scene = getScene(id);
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg0 }}>
      <AbsoluteFill>{children}</AbsoluteFill>
      {overlays ? <GlobalOverlays frameOffset={scene.from} /> : null}
    </AbsoluteFill>
  );
};
