import React from "react";
import { AbsoluteFill, Img, random, staticFile, useCurrentFrame } from "remotion";
import { ASSETS } from "../theme";

export type GrainProps = {
  /** Added to useCurrentFrame() so a scene preview matches Main (SceneHarness passes scene.from). */
  frameOffset?: number;
  /** Grain strength (layer opacity). Default 0.11. */
  opacity?: number;
  /** Change the grain pattern every N frames (default 1 = every frame, like film). */
  every?: number;
};

/**
 * Film grain: three pre-rendered 1200x2040 plates (white/black, alpha = |noise|), NORMAL
 * blending, shifted per frame with a compositor-only transform (blend modes or repainted
 * tiled backgrounds cost 130-350 ms/frame in software compositing; this is ~free).
 * Also dithers dark gradients against banding. Deterministic per frame.
 */
export const Grain: React.FC<GrainProps> = ({ frameOffset = 0, opacity = 0.11, every = 1 }) => {
  const f = Math.floor((useCurrentFrame() + frameOffset) / every);
  const plate = f % ASSETS.grainPlates.length;
  const ox = -Math.floor(random(`grain-x-${f}`) * 118);
  const oy = -Math.floor(random(`grain-y-${f}`) * 118);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden", opacity }}>
      {ASSETS.grainPlates.map((src, i) => (
        <Img
          key={src}
          src={staticFile(src)}
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: 1200,
            height: 2040,
            maxWidth: "none",
            transform: `translate(${ox}px, ${oy}px)`,
            visibility: i === plate ? "visible" : "hidden",
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

export type VignetteProps = {
  /** 0..1+ opacity of the baked vignette (corners ~0.55 dark + top/bottom edge darkening). Default 1. */
  strength?: number;
};

/** Soft cinematic vignette + gentle top/bottom gradient (pre-rendered public/img/vignette.png). */
export const Vignette: React.FC<VignetteProps> = ({ strength = 1 }) =>
  strength > 0 ? (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <Img src={staticFile(ASSETS.vignette)} style={{ width: "100%", height: "100%", opacity: Math.min(1, strength) }} />
    </AbsoluteFill>
  ) : null;
