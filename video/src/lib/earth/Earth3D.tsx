/**
 * Earth3D — the hero planet. ThreeCanvas + custom shaders:
 *  day albedo lit by the sun (bump-mapped relief, warm terminator), city lights on the night
 *  side, a separate cloud shell (drifts via `cloudDrift`) with cloud shadows, ocean sun glint,
 *  analytic atmosphere (thin bright limb + soft outer halo, sunset tint at the terminator).
 *
 * Everything is driven by props — animate them from useCurrentFrame() in your scene. Never use
 * useFrame(). Transparent background: composite over <SkyBackground/> / <Starfield/>.
 *
 * Earth = unit sphere at the origin. Cameras: see earthMath.ts recipes
 * (fullPlanetCamera, limbCamera, nadirCamera, orbitCamera, mixCameras, expLerp).
 */
import React, { useLayoutEffect, useMemo } from "react";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { useEarthTextures, type EarthTextures } from "./useEarthTextures";
import {
  applyCamera,
  DEFAULT_SUN,
  earthEuler,
  fullPlanetCamera,
  projectLatLon,
  type EarthCamera,
  type EarthOrientation,
  type Vec3,
} from "./earthMath";
import {
  atmosphereFragment,
  atmosphereVertex,
  cloudFragment,
  surfaceFragment,
  surfaceVertex,
} from "./shaders";
import { EarthPin, type EarthPinSpec } from "./EarthPin";

export type Earth3DProps = EarthOrientation & {
  /** Canvas size in px (default: composition size). The canvas is absolutely positioned at 0,0. */
  width?: number;
  height?: number;
  /** Camera (default: fullPlanetCamera()). */
  camera?: EarthCamera;
  /** Direction from Earth to Sun in WORLD space (need not be normalised). */
  sunDirection?: Vec3;
  /** Extra longitudinal rotation of the cloud layer in degrees (animate slowly, e.g. frame*0.02). */
  cloudDrift?: number;
  /** Cloud opacity multiplier 0..1 (default 1). */
  cloudOpacity?: number;
  /** City lights intensity (default 1). */
  nightLights?: number;
  /** Thin limb glow intensity (default 1). */
  atmosphere?: number;
  /** Soft outer halo intensity (default 1). */
  halo?: number;
  /** Atmosphere thickness multiplier (default 1). >1 = thicker, more stylised. */
  atmosphereThickness?: number;
  /** Overall exposure (default 1). */
  exposure?: number;
  /** Ocean glint strength (default 1). */
  specular?: number;
  /** Relief (bump) strength (default 1). */
  bump?: number;
  /** Procedural close-range detail 0..1 (default: automatic from camera altitude). */
  detail?: number;
  /** HTML pins projected onto the globe. */
  pins?: EarthPinSpec[];
  /** Antialiasing (MSAA). Default true. */
  antialias?: boolean;
  style?: React.CSSProperties;
  /** Extra R3F content in the same world (Earth radius 1 at origin). */
  children?: React.ReactNode;
};

type SceneProps = Required<
  Pick<
    Earth3DProps,
    | "facingLon"
    | "facingLat"
    | "tilt"
    | "camera"
    | "sunDirection"
    | "cloudDrift"
    | "cloudOpacity"
    | "nightLights"
    | "atmosphere"
    | "halo"
    | "atmosphereThickness"
    | "exposure"
    | "specular"
    | "bump"
    | "width"
    | "height"
  >
> & {
  tex: EarthTextures;
  seed: number;
  detail?: number;
  children?: React.ReactNode;
};

const EarthScene: React.FC<SceneProps> = (p) => {
  const cam = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const geos = useMemo(
    () => ({
      surface: new THREE.SphereGeometry(1, 320, 160),
      clouds: new THREE.SphereGeometry(1.0045, 256, 128),
      atmo: new THREE.SphereGeometry(1.35, 96, 48),
    }),
    [],
  );

  const materials = useMemo(() => {
    const surface = new THREE.ShaderMaterial({
      vertexShader: surfaceVertex,
      fragmentShader: surfaceFragment,
      uniforms: {
        uDay: { value: p.tex.day },
        uNight: { value: p.tex.night },
        uBrc: { value: p.tex.brc },
        uSun: { value: new THREE.Vector3() },
        uSunLocal: { value: new THREE.Vector3() },
        uRot: { value: new THREE.Matrix3() },
        uCloudU: { value: 0 },
        uNightK: { value: 1 },
        uSpec: { value: 1 },
        uBump: { value: 1 },
        uExposure: { value: 1 },
        uCloudShadow: { value: 1 },
        uAtmo: { value: 1 },
        uH: { value: 0.0065 },
        uDetail: { value: 0 },
        uSeed: { value: 0 },
      },
    });
    const clouds = new THREE.ShaderMaterial({
      vertexShader: surfaceVertex,
      fragmentShader: cloudFragment,
      transparent: true,
      depthWrite: false,
      uniforms: {
        uBrc: { value: p.tex.brc },
        uSun: { value: new THREE.Vector3() },
        uRot: { value: new THREE.Matrix3() },
        uCloudU: { value: 0 },
        uOpacity: { value: 1 },
        uExposure: { value: 1 },
        uAtmo: { value: 1 },
        uH: { value: 0.0065 },
        uDetail: { value: 0 },
        uSeed: { value: 0 },
      },
    });
    const atmo = new THREE.ShaderMaterial({
      vertexShader: atmosphereVertex,
      fragmentShader: atmosphereFragment,
      transparent: true,
      depthWrite: false,
      depthTest: false,
      side: THREE.BackSide,
      blending: THREE.CustomBlending,
      blendEquation: THREE.AddEquation,
      blendSrc: THREE.OneFactor,
      blendDst: THREE.OneFactor,
      blendSrcAlpha: THREE.ZeroFactor,
      blendDstAlpha: THREE.OneFactor,
      uniforms: {
        uSun: { value: new THREE.Vector3() },
        uIntensity: { value: 1 },
        uHalo: { value: 1 },
        uH: { value: 0.012 },
        uH2: { value: 0.06 },
        uExposure: { value: 1 },
        uSeed: { value: 0 },
      },
    });
    return { surface, clouds, atmo };
  }, [p.tex]);

  useLayoutEffect(
    () => () => {
      materials.surface.dispose();
      materials.clouds.dispose();
      materials.atmo.dispose();
    },
    [materials],
  );
  useLayoutEffect(
    () => () => {
      geos.surface.dispose();
      geos.clouds.dispose();
      geos.atmo.dispose();
    },
    [geos],
  );

  const euler = earthEuler({
    facingLon: p.facingLon,
    facingLat: p.facingLat,
    tilt: p.tilt,
  });
  const rot4 = new THREE.Matrix4().makeRotationFromEuler(euler);
  const rot3 = new THREE.Matrix3().setFromMatrix4(rot4);
  const sun = new THREE.Vector3(...p.sunDirection).normalize();
  const sunLocal = sun.clone().applyMatrix3(rot3.clone().transpose());
  const cloudU = -p.cloudDrift / 360;
  const H = 0.0065 * p.atmosphereThickness;
  // procedural detail fades in below ~0.6 Earth radii altitude (texture runs out of pixels)
  const camAlt = Math.hypot(...p.camera.position) - 1;
  const detail = p.detail ?? Math.min(1, Math.max(0, (0.6 - camAlt) / 0.45));

  // Imperative per-frame updates (run before @remotion/three advances the R3F frame).
  useLayoutEffect(() => {
    applyCamera(cam, p.camera, p.width / p.height);
    const s = materials.surface.uniforms;
    s.uSun.value.copy(sun);
    s.uSunLocal.value.copy(sunLocal);
    s.uRot.value.copy(rot3);
    s.uCloudU.value = cloudU;
    s.uNightK.value = p.nightLights;
    s.uSpec.value = p.specular;
    s.uBump.value = p.bump;
    s.uExposure.value = p.exposure;
    s.uCloudShadow.value = p.cloudOpacity;
    s.uAtmo.value = p.atmosphere;
    s.uH.value = H;
    s.uDetail.value = detail;
    s.uSeed.value = p.seed;
    const c = materials.clouds.uniforms;
    c.uSun.value.copy(sun);
    c.uRot.value.copy(rot3);
    c.uCloudU.value = cloudU;
    c.uOpacity.value = p.cloudOpacity;
    c.uExposure.value = p.exposure;
    c.uAtmo.value = p.atmosphere;
    c.uH.value = H;
    c.uDetail.value = detail;
    c.uSeed.value = p.seed;
    const a = materials.atmo.uniforms;
    a.uSun.value.copy(sun);
    a.uIntensity.value = p.atmosphere;
    a.uHalo.value = p.halo;
    a.uH.value = H;
    a.uH2.value = 0.05 * p.atmosphereThickness;
    a.uExposure.value = p.exposure;
    a.uSeed.value = p.seed;
  });

  return (
    <>
      <group rotation={euler}>
        <mesh
          geometry={geos.surface}
          material={materials.surface}
          renderOrder={0}
        />
        {p.cloudOpacity > 0 ? (
          <mesh
            geometry={geos.clouds}
            material={materials.clouds}
            renderOrder={1}
          />
        ) : null}
      </group>
      {p.atmosphere > 0 || p.halo > 0 ? (
        <mesh
          geometry={geos.atmo}
          material={materials.atmo}
          renderOrder={10}
          frustumCulled={false}
        />
      ) : null}
      {p.children}
    </>
  );
};

export const Earth3D: React.FC<Earth3DProps> = (props) => {
  const { width: vw, height: vh } = useVideoConfig();
  const frame = useCurrentFrame();
  const width = props.width ?? vw;
  const height = props.height ?? vh;
  const tex = useEarthTextures();
  const camera = props.camera ?? fullPlanetCamera({ width, height });
  const orientation: EarthOrientation = {
    facingLon: props.facingLon ?? 0,
    facingLat: props.facingLat ?? 0,
    tilt: props.tilt ?? 0,
  };

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        width,
        height,
        ...props.style,
      }}
    >
      {tex ? (
        <ThreeCanvas
          width={width}
          height={height}
          gl={{
            antialias: props.antialias ?? true,
            alpha: true,
            premultipliedAlpha: true,
            preserveDrawingBuffer: true,
          }}
          style={{ position: "absolute", left: 0, top: 0 }}
        >
          <EarthScene
            tex={tex}
            width={width}
            height={height}
            facingLon={orientation.facingLon!}
            facingLat={orientation.facingLat!}
            tilt={orientation.tilt!}
            camera={camera}
            sunDirection={props.sunDirection ?? DEFAULT_SUN}
            cloudDrift={props.cloudDrift ?? 0}
            cloudOpacity={props.cloudOpacity ?? 1}
            nightLights={props.nightLights ?? 1}
            atmosphere={props.atmosphere ?? 1}
            halo={props.halo ?? 1}
            atmosphereThickness={props.atmosphereThickness ?? 1}
            exposure={props.exposure ?? 1}
            specular={props.specular ?? 1}
            bump={props.bump ?? 1}
            detail={props.detail}
            seed={(frame % 64) * 1.37}
          >
            {props.children}
          </EarthScene>
        </ThreeCanvas>
      ) : null}
      {props.pins?.map((pin, i) => {
        const pt = projectLatLon({
          lat: pin.lat,
          lon: pin.lon,
          altitude: 0.002,
          orientation,
          camera,
          width,
          height,
        });
        return <EarthPin key={i} {...pin} point={pt} />;
      })}
    </div>
  );
};
