import React from "react";
import { AbsoluteFill, Img, staticFile, useVideoConfig } from "remotion";
import { ASSETS, COLORS } from "../theme";

export type SkyBackgroundProps = {
  /**
   * Camera pan in composition px (screen space). Positive y = view moves DOWN (stars drift up);
   * negative y = camera tilts up (stars drift down). Rotation pivots around the frame centre.
   */
  pan?: [number, number];
  /** 1 = native image pixels (crisp; default). <1 shows more sky (min ≈ 0.47 = cover). */
  zoom?: number;
  /** Camera roll in degrees. */
  rotate?: number;
  /** Brightness multiplier (CSS filter). Default 1. */
  brightness?: number;
  /** Saturation multiplier (CSS filter). Default 1. */
  saturate?: number;
  /** Overall opacity (fades to bg0). Default 1. */
  opacity?: number;
  /** Gaussian blur in px (e.g. for depth-of-field moments). Default 0. */
  blur?: number;
  /** If true (default) zoom is raised automatically so no image edge is ever visible. */
  autoCover?: boolean;
  /** Override image (path relative to public/). Must be ASSETS.skySize unless width/height given. */
  src?: string;
  imageWidth?: number;
  imageHeight?: number;
  style?: React.CSSProperties;
  children?: React.ReactNode;
};

/** Minimum scale so the rotated + panned frame stays inside the image. */
export const skyCoverScale = (
  frameW: number,
  frameH: number,
  imgW: number,
  imgH: number,
  rotateDeg: number,
  pan: [number, number],
): number => {
  const t = (rotateDeg * Math.PI) / 180;
  const c = Math.abs(Math.cos(t));
  const s = Math.abs(Math.sin(t));
  const hx = (frameW * c + frameH * s) / 2;
  const hy = (frameW * s + frameH * c) / 2;
  // pan expressed in image axes
  const px = Math.abs(pan[0] * Math.cos(-t) - pan[1] * Math.sin(-t));
  const py = Math.abs(pan[0] * Math.sin(-t) + pan[1] * Math.cos(-t));
  return Math.max((hx + px) / (imgW / 2), (hy + py) / (imgH / 2)) * 1.002;
};

/**
 * Full-frame Milky Way backdrop (public/img/sky_milkyway.jpg, 2304x4096) with a virtual
 * camera: pan / zoom / rotate. Always paints bg0 behind so nothing is ever transparent.
 */
export const SkyBackground: React.FC<SkyBackgroundProps> = ({
  pan = [0, 0],
  zoom = 1,
  rotate = 0,
  brightness = 1,
  saturate = 1,
  opacity = 1,
  blur = 0,
  autoCover = true,
  src = ASSETS.sky,
  imageWidth = ASSETS.skySize.width,
  imageHeight = ASSETS.skySize.height,
  style,
  children,
}) => {
  const { width, height } = useVideoConfig();
  const minScale = autoCover
    ? skyCoverScale(width, height, imageWidth, imageHeight, rotate, pan)
    : 0;
  const scale = Math.max(zoom, minScale);
  const filters = [
    brightness !== 1 ? `brightness(${brightness})` : "",
    saturate !== 1 ? `saturate(${saturate})` : "",
    blur > 0 ? `blur(${blur}px)` : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <AbsoluteFill
      style={{ backgroundColor: COLORS.bg0, overflow: "hidden", ...style }}
    >
      <Img
        src={staticFile(src)}
        style={{
          position: "absolute",
          left: (width - imageWidth) / 2,
          top: (height - imageHeight) / 2,
          width: imageWidth,
          height: imageHeight,
          maxWidth: "none",
          transformOrigin: "50% 50%",
          transform: `translate(${-pan[0]}px, ${-pan[1]}px) rotate(${rotate}deg) scale(${scale})`,
          filter: filters || undefined,
          opacity,
        }}
      />
      {children}
    </AbsoluteFill>
  );
};
