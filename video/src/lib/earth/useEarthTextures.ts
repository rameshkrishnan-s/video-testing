import { useEffect, useState } from "react";
import * as THREE from "three";
import { staticFile, useDelayRender } from "remotion";
import { ASSETS } from "../theme";

export type EarthTextures = {
  day: THREE.Texture;
  night: THREE.Texture;
  /** R = bump, G = roughness (land=1), B = clouds. Linear data. */
  brc: THREE.Texture;
};

let promise: Promise<EarthTextures> | null = null;

const load = (url: string, srgb: boolean): Promise<THREE.Texture> =>
  new Promise((resolve, reject) => {
    new THREE.TextureLoader().load(
      url,
      (t) => {
        t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        t.wrapS = THREE.RepeatWrapping;
        t.wrapT = THREE.ClampToEdgeWrapping;
        t.anisotropy = 1;
        t.generateMipmaps = true;
        t.minFilter = THREE.LinearMipmapLinearFilter;
        t.magFilter = THREE.LinearFilter;
        t.needsUpdate = true;
        resolve(t);
      },
      undefined,
      (e) => reject(new Error(`Failed to load texture ${url}: ${String(e)}`)),
    );
  });

/** Loads (once per page) the Earth textures. */
export const loadEarthTextures = (): Promise<EarthTextures> => {
  if (!promise) {
    promise = Promise.all([
      load(staticFile(ASSETS.earthDay), true),
      load(staticFile(ASSETS.earthNight), true),
      load(staticFile(ASSETS.earthBrc), false),
    ]).then(([day, night, brc]) => ({ day, night, brc }));
  }
  return promise;
};

/**
 * Returns the textures once loaded (null before). Blocks rendering via delayRender until the
 * consumer has mounted with them (continueRender runs in a passive effect AFTER the commit
 * that mounted the <ThreeCanvas>, whose own delayRender then takes over).
 */
export const useEarthTextures = (): EarthTextures | null => {
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [handle] = useState(() => delayRender("Loading Earth textures"));
  const [tex, setTex] = useState<EarthTextures | null>(null);

  useEffect(() => {
    let alive = true;
    loadEarthTextures()
      .then((t) => alive && setTex(t))
      .catch((e) => cancelRender(e));
    return () => {
      alive = false;
    };
  }, [cancelRender]);

  useEffect(() => {
    if (tex) continueRender(handle);
  }, [tex, continueRender, handle]);

  // release on unmount if never loaded
  useEffect(() => () => continueRender(handle), [continueRender, handle]);

  return tex;
};
