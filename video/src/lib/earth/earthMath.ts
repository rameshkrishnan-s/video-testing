/**
 * Pure (non-React) math shared by Earth3D and by scenes that need to know where things
 * are on screen. World units: Earth radius = 1, Earth centre = origin.
 *
 * Orientation: `facingLon`/`facingLat` = the geographic point that faces +Z (towards a
 * default camera on the +Z axis); `tilt` rolls the globe in the screen plane (deg).
 */
import * as THREE from "three";

export type Vec3 = [number, number, number];

export type EarthOrientation = {
  /** Longitude (deg, east positive) facing +Z. Animate for rotation, e.g. -40 + frame * 0.03. */
  facingLon?: number;
  /** Latitude (deg) facing +Z. */
  facingLat?: number;
  /** Roll of the globe in the screen plane (deg, positive = counter-clockwise). */
  tilt?: number;
};

export type EarthCamera = {
  /** World position. Earth radius = 1. */
  position: Vec3;
  /** Look-at point (default origin). */
  target?: Vec3;
  /** Vertical field of view in degrees (default 30). */
  fov?: number;
  /** Roll around the view axis (deg). */
  roll?: number;
  /** Up vector before roll (default [0,1,0]). */
  up?: Vec3;
};

const D2R = Math.PI / 180;

/** Unit-sphere position of a lat/lon in Earth-LOCAL coordinates (matches SphereGeometry UVs). */
export const latLonToLocal = (
  lat: number,
  lon: number,
  radius = 1,
): THREE.Vector3 => {
  const la = lat * D2R;
  const lo = lon * D2R;
  return new THREE.Vector3(
    Math.cos(la) * Math.cos(lo),
    Math.sin(la),
    -Math.cos(la) * Math.sin(lo),
  ).multiplyScalar(radius);
};

/** Euler (order ZXY) that rotates the Earth so (facingLat, facingLon) faces +Z. */
export const earthEuler = (o: EarthOrientation = {}): THREE.Euler =>
  new THREE.Euler(
    (o.facingLat ?? 0) * D2R,
    (-90 - (o.facingLon ?? 0)) * D2R,
    (o.tilt ?? 0) * D2R,
    "ZXY",
  );

/** Local -> world rotation matrix for the Earth. */
export const earthMatrix = (o: EarthOrientation = {}): THREE.Matrix4 =>
  new THREE.Matrix4().makeRotationFromEuler(earthEuler(o));

/** World position of a lat/lon (+ altitude in Earth radii). */
export const latLonToWorld = (
  lat: number,
  lon: number,
  o: EarthOrientation = {},
  altitude = 0,
): THREE.Vector3 =>
  latLonToLocal(lat, lon, 1 + altitude).applyMatrix4(earthMatrix(o));

/** Normalised direction from spherical angles (deg). azimuth 0 = +Z (towards default camera), 90 = +X (right). */
export const directionFromAngles = (
  azimuthDeg: number,
  elevationDeg: number,
): Vec3 => {
  const az = azimuthDeg * D2R;
  const el = elevationDeg * D2R;
  return [
    Math.sin(az) * Math.cos(el),
    Math.sin(el),
    Math.cos(az) * Math.cos(el),
  ];
};

/** Clip planes adapted to the camera distance (keeps depth precision for close limb shots). */
const clipPlanes = (dist: number): { near: number; far: number } => ({
  near: Math.min(0.5, Math.max(0.0005, (dist - 1.02) * 0.5)),
  far: dist + 4,
});

/** Apply an EarthCamera to a three.js PerspectiveCamera (used by Earth3D AND projectors). */
export const applyCamera = (
  cam: THREE.PerspectiveCamera,
  c: EarthCamera,
  aspect: number,
): THREE.PerspectiveCamera => {
  const target = c.target ?? [0, 0, 0];
  cam.position.set(...c.position);
  cam.up.set(...(c.up ?? [0, 1, 0]));
  cam.lookAt(new THREE.Vector3(...target));
  if (c.roll) cam.rotateZ(c.roll * D2R);
  const { near, far } = clipPlanes(cam.position.length());
  cam.fov = c.fov ?? 30;
  cam.aspect = aspect;
  cam.near = near;
  cam.far = far;
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld(true);
  return cam;
};

export const makeCamera = (
  c: EarthCamera,
  width: number,
  height: number,
): THREE.PerspectiveCamera =>
  applyCamera(new THREE.PerspectiveCamera(), c, width / height);

export type ProjectedPoint = {
  /** Pixel coordinates in the Earth3D canvas (same as the composition if full-frame). */
  x: number;
  y: number;
  /** On the camera-facing hemisphere and in front of the camera. */
  visible: boolean;
  /** dot(surface normal, direction to camera): 1 = facing, 0 = on the limb, <0 = far side. */
  facing: number;
  /** Distance from camera (world units). */
  distance: number;
};

/** Project a world-space point into canvas pixels. */
export const projectWorld = (
  p: THREE.Vector3,
  camera: EarthCamera,
  width: number,
  height: number,
): ProjectedPoint => {
  const cam = makeCamera(camera, width, height);
  const ndc = p.clone().project(cam);
  const toCam = cam.position.clone().sub(p);
  const distance = toCam.length();
  const facing = p.clone().normalize().dot(toCam.normalize());
  // occlusion test against the unit sphere for points above the surface
  const dir = p.clone().sub(cam.position).normalize();
  const b = cam.position.dot(dir);
  const c = cam.position.lengthSq() - 1;
  const disc = b * b - c;
  let occluded = false;
  if (disc > 0) {
    const tHit = -b - Math.sqrt(disc);
    occluded = tHit > 1e-4 && tHit < distance - 1e-4;
  }
  return {
    x: ((ndc.x + 1) / 2) * width,
    y: ((1 - ndc.y) / 2) * height,
    visible: !occluded && ndc.z < 1 && ndc.z > -1 && facing > -0.02,
    facing,
    distance,
  };
};

/**
 * Screen position of a lat/lon for the given orientation + camera. Use it to place HTML labels
 * (pins, leader lines) exactly over the 3D Earth.
 */
export const projectLatLon = (args: {
  lat: number;
  lon: number;
  altitude?: number;
  orientation?: EarthOrientation;
  camera: EarthCamera;
  width: number;
  height: number;
}): ProjectedPoint =>
  projectWorld(
    latLonToWorld(
      args.lat,
      args.lon,
      args.orientation ?? {},
      args.altitude ?? 0,
    ),
    args.camera,
    args.width,
    args.height,
  );

/** Screen-space centre + radius (px) of the Earth disk (approximate for off-axis views). */
export const projectEarthDisk = (
  camera: EarthCamera,
  width: number,
  height: number,
): { x: number; y: number; radius: number } => {
  const cam = makeCamera(camera, width, height);
  const center = new THREE.Vector3(0, 0, 0).project(cam);
  const dist = cam.position.length();
  const angR = Math.asin(Math.min(1, 1 / dist));
  const pxPerTan = height / 2 / Math.tan((cam.fov * D2R) / 2);
  return {
    x: ((center.x + 1) / 2) * width,
    y: ((1 - center.y) / 2) * height,
    radius: Math.tan(angR) * pxPerTan,
  };
};

// ---------------------------------------------------------------------------------------
// Camera recipes
// ---------------------------------------------------------------------------------------

/** Camera orbiting `target` at `distance` (azimuth 0 = on +Z). */
export const orbitCamera = (o: {
  distance: number;
  azimuth?: number;
  elevation?: number;
  target?: Vec3;
  fov?: number;
  roll?: number;
}): EarthCamera => {
  const t = o.target ?? [0, 0, 0];
  const d = directionFromAngles(o.azimuth ?? 0, o.elevation ?? 0);
  return {
    position: [
      t[0] + d[0] * o.distance,
      t[1] + d[1] * o.distance,
      t[2] + d[2] * o.distance,
    ],
    target: t,
    fov: o.fov ?? 30,
    roll: o.roll ?? 0,
  };
};

/**
 * "Planet hanging in space": camera on +Z looking at the centre, distance chosen so the
 * planet's diameter is `fill` x frame width. `offsetY` (px, +down) shifts the planet on screen.
 */
export const fullPlanetCamera = (
  o: {
    fill?: number;
    fov?: number;
    width?: number;
    height?: number;
    offsetY?: number;
    offsetX?: number;
  } = {},
): EarthCamera => {
  const fov = o.fov ?? 30;
  const width = o.width ?? 1080;
  const height = o.height ?? 1920;
  const fill = o.fill ?? 0.8;
  const tanHalf = Math.tan((fov * D2R) / 2);
  const k = fill * (width / height) * tanHalf; // tan(angular radius)
  const dist = 1 / Math.sin(Math.atan(k));
  // shift the target so the planet moves on screen
  const pxToWorld = (dist * tanHalf) / (height / 2);
  const tx = -(o.offsetX ?? 0) * pxToWorld;
  const ty = (o.offsetY ?? 0) * pxToWorld;
  return { position: [tx, ty, dist], target: [tx, ty, 0], fov };
};

/**
 * Close limb shot: camera `altitude` (Earth radii) above the facing point, looking at the
 * horizon (towards +Y / north if tilt=0). The limb is placed at `horizonY` (0 = top, 1 = bottom
 * of frame). `heading` rotates the view direction around the local vertical (deg).
 */
export const limbCamera = (
  o: {
    altitude?: number;
    horizonY?: number;
    fov?: number;
    heading?: number;
    roll?: number;
    height?: number;
  } = {},
): EarthCamera => {
  const h = o.altitude ?? 0.18;
  const fov = o.fov ?? 40;
  const horizonY = o.horizonY ?? 0.62;
  const r = 1 + h;
  const dip = Math.acos(1 / r); // angle of the horizon below horizontal
  const tanHalf = Math.tan((fov * D2R) / 2);
  const pitch = dip - Math.atan((2 * horizonY - 1) * tanHalf); // look-down angle
  const hd = (o.heading ?? 0) * D2R;
  // camera on +Z axis; "forward" tangent = +Y rotated by heading around Z
  const fwd = new THREE.Vector3(-Math.sin(hd), Math.cos(hd), 0);
  const upR = new THREE.Vector3(0, 0, 1);
  const dir = fwd
    .clone()
    .multiplyScalar(Math.cos(pitch))
    .addScaledVector(upR, -Math.sin(pitch));
  const up = fwd
    .clone()
    .multiplyScalar(Math.sin(pitch))
    .addScaledVector(upR, Math.cos(pitch));
  const pos = new THREE.Vector3(0, 0, r);
  const target = pos.clone().add(dir);
  return {
    position: [pos.x, pos.y, pos.z],
    target: [target.x, target.y, target.z],
    up: [up.x, up.y, up.z],
    fov,
    roll: o.roll ?? 0,
  };
};

/**
 * Straight-down camera at `altitude` above the facing point (top-down zoom). Interpolate
 * altitude exponentially for a fast zoom-out: altitude = a0 * (a1 / a0) ** t.
 */
export const nadirCamera = (o: {
  altitude: number;
  fov?: number;
  roll?: number;
}): EarthCamera => ({
  position: [0, 0, 1 + o.altitude],
  target: [0, 0, 0],
  fov: o.fov ?? 30,
  roll: o.roll ?? 0,
});

/** Exponential (perceptually even) interpolation, e.g. for altitudes / distances. */
export const expLerp = (a: number, b: number, t: number): number =>
  a * Math.pow(b / a, t);

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerp3 = (a: Vec3, b: Vec3, t: number): Vec3 => [
  lerp(a[0], b[0], t),
  lerp(a[1], b[1], t),
  lerp(a[2], b[2], t),
];

/** Blend two cameras (positions/targets/up linearly, fov/roll linearly). */
export const mixCameras = (
  a: EarthCamera,
  b: EarthCamera,
  t: number,
): EarthCamera => ({
  position: lerp3(a.position, b.position, t),
  target: lerp3(a.target ?? [0, 0, 0], b.target ?? [0, 0, 0], t),
  up: lerp3(a.up ?? [0, 1, 0], b.up ?? [0, 1, 0], t),
  fov: lerp(a.fov ?? 30, b.fov ?? 30, t),
  roll: lerp(a.roll ?? 0, b.roll ?? 0, t),
});

/** Default sun: upper-left-front, gives a ~70% lit gibbous Earth with a visible terminator. */
export const DEFAULT_SUN: Vec3 = directionFromAngles(-62, 18);
