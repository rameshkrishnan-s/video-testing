/**
 * Remotion CLI config (applies to `npx remotion render|still|studio`).
 * Node APIs (@remotion/renderer) ignore this file — pass the same options there.
 *
 * Environment notes:
 * - Chromium is pre-installed; Remotion must not download its own browser.
 * - No GPU: WebGL runs on SwiftShader via ANGLE ("swangle").
 */
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setBrowserExecutable(
  "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
);
Config.setChromiumOpenGlRenderer("swangle");
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(95);
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
// Earth3D (software WebGL) + big images can be slow on CPU-only machines.
Config.setDelayRenderTimeoutInMilliseconds(120000);
