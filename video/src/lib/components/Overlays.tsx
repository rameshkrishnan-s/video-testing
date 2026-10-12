import React from "react";
import { AbsoluteFill, random, staticFile, useCurrentFrame } from "remotion";
import { ASSETS } from "../theme";

export type GrainProps = {
  /** Added to useCurrentFrame() so a scene preview matches Main (SceneHarness passes scene.from). */
  frameOffset?: number;
  /** Overlay-blend grain strength (mid-tones). Default 0.13. */
  opacity?: number;
  /** Faint additive grain that dithers dark gradients (prevents banding). Default 0.035. */
  darkDither?: number;
  /** Change grain pattern every N frames (default 1 = every frame, like film). */
  every?: number;
};

/** Film grain from the 512px tiles in public/img/grain_*.png. Deterministic per frame. */
export const Grain: React.FC<GrainProps> = ({
  frameOffset = 0,
  opacity = 0.13,
  darkDither = 0.035,
  every = 1,
}) => {
  const f = Math.floor((useCurrentFrame() + frameOffset) / every);
  const tile = ASSETS.grain[f % ASSETS.grain.length];
  const ox = Math.floor(random(`grain-x-${f}`) * 512);
  const oy = Math.floor(random(`grain-y-${f}`) * 512);
  const bg: React.CSSProperties = {
    backgroundImage: `url(${staticFile(tile)})`,
    backgroundRepeat: "repeat",
    backgroundSize: "512px 512px",
    backgroundPosition: `${ox}px ${oy}px`,
    pointerEvents: "none",
  };
  return (
    <>
      <AbsoluteFill style={{ ...bg, mixBlendMode: "overlay", opacity }} />
      {darkDither > 0 ? (
        <AbsoluteFill
          style={{
            ...bg,
            backgroundPosition: `${(ox + 211) % 512}px ${(oy + 97) % 512}px`,
            mixBlendMode: "screen",
            opacity: darkDither,
          }}
        />
      ) : null}
    </>
  );
};

export type VignetteProps = {
  /** 0..1 darkness at the corners. Default 0.55. */
  strength?: number;
  /** Extra darkening at the very top/bottom for UI + caption legibility. Default 0.35. */
  edges?: number;
  color?: string;
};

/** Soft cinematic vignette + gentle top/bottom gradient. */
export const Vignette: React.FC<VignetteProps> = ({
  strength = 0.55,
  edges = 0.35,
  color = "2,3,8",
}) => (
  <>
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        background: `radial-gradient(ellipse 85% 70% at 50% 46%, rgba(${color},0) 55%, rgba(${color},${strength * 0.6}) 82%, rgba(${color},${strength}) 100%)`,
      }}
    />
    {edges > 0 ? (
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background: `linear-gradient(to bottom, rgba(${color},${edges}) 0%, rgba(${color},0) 12%, rgba(${color},0) 80%, rgba(${color},${edges * 0.9}) 100%)`,
        }}
      />
    ) : null}
  </>
);
