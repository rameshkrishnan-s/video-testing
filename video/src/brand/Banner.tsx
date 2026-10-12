/** Channel banner (2560x1440). Everything important sits in the 1546x423 centre strip (y 508-931) visible on all devices. */
import React from "react";
import { AbsoluteFill } from "remotion";
import { COLORS, Earth3D, FONTS, SkyBackground, Starfield, limbCamera } from "../lib";
import "../lib/fonts";

export const Banner: React.FC = () => (
  <AbsoluteFill style={{ background: COLORS.bg0 }}>
    <SkyBackground rotate={-78} zoom={1.05} brightness={0.95} />
    <Starfield seed="banner" count={700} brightness={0.8} />
    <Earth3D
      camera={limbCamera({ altitude: 0.07, horizonY: 0.6, fov: 34 })}
      specular={0.2}
      facingLat={18}
      facingLon={-30}
      sunDirection={[-0.45, 0.82, 0.2]}
      antialias
    />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", top: -40 }}>
      <div style={{ fontFamily: FONTS.display, fontWeight: 900, fontSize: 132, letterSpacing: "0.03em", color: COLORS.text, lineHeight: 1, textShadow: "0 6px 40px rgba(0,0,0,0.65)" }}>
        ALREADY IN <span style={{ color: COLORS.accent }}>SPACE</span>
      </div>
      <div style={{ marginTop: 30, fontFamily: FONTS.mono, fontWeight: 600, fontSize: 36, letterSpacing: "0.22em", color: COLORS.sky, textShadow: "0 2px 16px rgba(0,0,0,0.8)" }}>
        SPACE · SCIENCE · THE LIFE YOU&apos;RE ALREADY LIVING
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);
