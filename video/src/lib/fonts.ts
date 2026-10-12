/**
 * Local font loading. Importing this module (done by Root.tsx / theme users) registers
 * Montserrat + JetBrains Mono variable fonts. `loadFont()` calls delayRender() internally,
 * so no frame is captured before the fonts are ready.
 */
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

let loaded: Promise<unknown> | null = null;

export const ensureFonts = (): Promise<unknown> => {
  if (loaded) return loaded;
  loaded = Promise.all([
    loadFont({
      family: "Montserrat",
      url: staticFile("fonts/Montserrat-VariableFont_wght.ttf"),
      format: "truetype",
      weight: "100 900",
      style: "normal",
      display: "block",
    }),
    loadFont({
      family: "JetBrains Mono",
      url: staticFile("fonts/JetBrainsMono-VariableFont_wght.ttf"),
      format: "truetype",
      weight: "100 800",
      style: "normal",
      display: "block",
    }),
  ]);
  return loaded;
};

// Kick off immediately on import (module side effect, runs once per page).
ensureFonts();
