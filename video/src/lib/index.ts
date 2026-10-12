/** Barrel: `import { ... } from "../lib";` */
import "./fonts";

export * from "./theme";
export * from "./timeline";
export { ensureFonts } from "./fonts";
export {
  SkyBackground,
  skyCoverScale,
  type SkyBackgroundProps,
} from "./components/SkyBackground";
export {
  Starfield,
  type StarfieldProps,
  type StarfieldCamera,
} from "./components/Starfield";
export {
  Grain,
  Vignette,
  type GrainProps,
  type VignetteProps,
} from "./components/Overlays";
export { Glow, type GlowProps } from "./components/Glow";
export { HudLabel, type HudLabelProps } from "./components/HudLabel";
export {
  Counter,
  counterValue,
  formatNumber,
  type CounterProps,
} from "./components/Counter";
export { Reticle, type ReticleProps } from "./components/Reticle";
export {
  Captions,
  buildCaptionChunks,
  layoutLines,
  type CaptionChunk,
  type CaptionsProps,
} from "./components/Captions";
export {
  KineticWords,
  wordEntrance,
  measureDisplayText,
  type KineticWordsProps,
  type KineticWordInput,
  type KineticWordStyle,
  type KineticAnimation,
} from "./components/KineticWords";
export { Earth3D, type Earth3DProps } from "./earth/Earth3D";
export { EarthPin, type EarthPinSpec } from "./earth/EarthPin";
export * from "./earth/earthMath";
export { loadEarthTextures } from "./earth/useEarthTextures";
export {
  SceneHarness,
  GlobalOverlays,
  type GlobalOverlaysProps,
} from "./SceneHarness";
