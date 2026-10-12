/**
 * GLSL for Earth3D. Earth is ALWAYS centred at the world origin with radius 1.
 * All three materials output display-referred sRGB themselves (no three.js tone-mapping
 * chunks), so renderer colour settings don't matter.
 */

const COMMON = /* glsl */ `
vec3 acesFilm(vec3 x) {
  return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}
vec3 toSRGB(vec3 c) {
  c = max(c, vec3(0.0));
  return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
}
float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

float erfApprox(float x) {
  float x2 = x * x;
  float a = 0.147;
  float t = 1.0 - exp(-x2 * (1.2732395 + a * x2) / (1.0 + a * x2));
  return sign(x) * sqrt(max(t, 0.0));
}
float erfcx(float x) { // x >= 0, upper-bound approximation (exact at 0 and infinity)
  return 2.0 / (1.7724539 * (x + sqrt(x * x + 1.2732395)));
}
// Optical depth of an exponential atmosphere (scale height H, Earth radius 1) along a view
// ray with impact parameter b and closest-approach parameter tc; normalised so that a ray
// grazing the surface (b = 1, full chord) == 1. b < 1 = ray ends on the surface.
float opticalDepth(float b, float tc, float H) {
  float full = sqrt(6.2831853 * H);
  if (b >= 1.0) {
    float sig = sqrt(2.0 * b * H);
    float half_ = exp(-(b - 1.0) / H) * sqrt(1.5707963 * b * H);
    return half_ * (1.0 - erfApprox(-tc / sig)) / full;
  }
  float bb = max(b, 1e-4);
  float mu = sqrt(max(1.0 - bb * bb, 0.0));
  float t = sqrt(1.5707963 * H) / bb * erfcx(mu / (bb * sqrt(2.0 * H)));
  return t / full;
}
float hash13(vec3 p3) {
  p3 = fract(p3 * 0.1031);
  p3 += dot(p3, p3.zyx + 31.32);
  return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float n000 = hash13(i), n100 = hash13(i + vec3(1, 0, 0)), n010 = hash13(i + vec3(0, 1, 0)), n110 = hash13(i + vec3(1, 1, 0));
  float n001 = hash13(i + vec3(0, 0, 1)), n101 = hash13(i + vec3(1, 0, 1)), n011 = hash13(i + vec3(0, 1, 1)), n111 = hash13(i + vec3(1, 1, 1));
  return mix(mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y), mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y), f.z);
}
float fbm3(vec3 p) {
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { s += a * vnoise(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.5; }
  return s / 0.9375;
}
// Atmospheric scattering colour for optical depth tau, sun cosine muS at the scattering point,
// view/sun cosine cosT. Linear light.
vec3 scatter(float tau, float muS, float cosT) {
  float light = smoothstep(-0.28, 0.18, muS);
  vec3 sunset = mix(vec3(1.0, 0.40, 0.16), vec3(1.0), smoothstep(-0.06, 0.32, muS));
  float rayleigh = 0.75 * (1.0 + cosT * cosT);
  float g = 0.76;
  float mie = (1.0 - g * g) / pow(1.0 + g * g - 2.0 * g * cosT, 1.5);
  vec3 beta = vec3(0.16, 0.42, 1.0);
  return (1.0 - exp(-tau * beta * 3.0)) * (rayleigh * 0.62 + mie * 0.03 * min(tau, 1.0)) * light * sunset;
}
float cloudMask(float b) {
  // B channel has a hazy floor (~0.2); keep wisps, kill the floor.
  float c = smoothstep(0.16, 0.92, b);
  return c * c * (1.6 - 0.6 * c);
}
`;

export const surfaceVertex = /* glsl */ `
varying vec2 vUv;
varying vec3 vLocal;
varying vec3 vWorld;
void main() {
  vUv = uv;
  vLocal = position;
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorld = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`;

export const surfaceFragment = /* glsl */ `
uniform sampler2D uDay;
uniform sampler2D uNight;
uniform sampler2D uBrc;
uniform vec3 uSun;        // world, normalised (Earth -> Sun)
uniform vec3 uSunLocal;   // same in Earth-local frame
uniform mat3 uRot;        // Earth local -> world
uniform float uCloudU;    // cloud texture u offset (drift)
uniform float uNightK;
uniform float uSpec;
uniform float uBump;
uniform float uExposure;
uniform float uCloudShadow;
uniform float uAtmo;      // aerial haze strength
uniform float uH;         // atmosphere scale height
uniform float uDetail;    // 0..1 procedural close-range detail
uniform float uSeed;
varying vec2 vUv;
varying vec3 vLocal;
varying vec3 vWorld;
${COMMON}

void main() {
  vec3 nL = normalize(vLocal);
  float cosLat = max(length(nL.xz), 0.03);
  vec3 east = normalize(vec3(nL.z, 0.0, -nL.x) + vec3(1e-5, 0.0, 0.0));
  vec3 north = cross(nL, east);

  // --- bump from elevation (R channel), in texture space
  vec2 tx = vec2(1.0 / 4096.0, 1.0 / 2048.0);
  vec4 brc = texture2D(uBrc, vUv);
  float h0 = brc.r;
  float hR = texture2D(uBrc, vUv + vec2(tx.x, 0.0)).r;
  float hU = texture2D(uBrc, vUv + vec2(0.0, tx.y)).r;
  vec2 grad = vec2((hR - h0) / (tx.x * 6.2831853 * cosLat), (hU - h0) / (tx.y * 3.1415927));
  vec3 nB = normalize(nL - uBump * 0.010 * (grad.x * east + grad.y * north));

  vec3 Ng = normalize(uRot * nL);
  vec3 Nb = normalize(uRot * nB);
  vec3 V = normalize(cameraPosition - vWorld);
  vec3 L = uSun;
  float NdotLg = dot(Ng, L);
  float NdotL = dot(Nb, L);

  // --- albedo grading
  vec3 day = texture2D(uDay, vUv).rgb;
  float ocean = 1.0 - smoothstep(0.25, 0.6, brc.g);
  day = mix(day, day * vec3(0.30, 0.36, 0.40), ocean);           // deep navy ocean
  float lum = dot(day, vec3(0.2126, 0.7152, 0.0722));
  day = mix(vec3(lum), day, mix(0.88, 1.0, ocean));               // calmer land greens
  if (uDetail > 0.0) {
    float dn = fbm3(nL * 420.0);
    day *= mix(1.0, 0.78 + 0.44 * dn, uDetail * (1.0 - ocean));
  }

  // --- clouds: shadow (sampled toward the sun) + coverage here
  vec2 sunT = vec2(dot(uSunLocal, east), dot(uSunLocal, north));
  vec2 cUv = vUv + vec2(uCloudU, 0.0);
  vec2 shUv = cUv + vec2(sunT.x / (6.2831853 * cosLat), sunT.y / 3.1415927) * 0.0045;
  float cShadow = cloudMask(texture2D(uBrc, shUv).b);
  float cHere = cloudMask(texture2D(uBrc, cUv).b);
  float shadow = 1.0 - uCloudShadow * 0.6 * cShadow;

  // --- sunlight with warm terminator
  float lit = smoothstep(-0.02, 0.08, NdotLg);
  vec3 sunCol = mix(vec3(1.0, 0.50, 0.26), vec3(1.0, 0.97, 0.93), smoothstep(0.0, 0.32, NdotLg));
  float diff = max(NdotL, 0.0) * lit;
  vec3 col = day * diff * sunCol * shadow * 1.9;

  // --- ocean specular glint (Blinn-Phong + Fresnel), using the smooth normal
  vec3 H = normalize(L + V);
  float NdotH = max(dot(Ng, H), 0.0);
  float VdotH = max(dot(V, H), 0.0);
  float fres = 0.04 + 0.96 * pow(1.0 - VdotH, 5.0);
  float glint = pow(NdotH, 260.0) * 2.4 + pow(NdotH, 30.0) * 0.16;
  col += sunCol * glint * (0.35 + 0.65 * fres) * ocean * shadow * (1.0 - 0.85 * cHere) * smoothstep(0.0, 0.12, NdotLg) * uSpec;

  // --- night side: city lights (sparkly up close) + faint moonlit ground
  float nightMask = (1.0 - smoothstep(-0.10, 0.06, NdotLg)) * uNightK;
  if (nightMask > 0.0) {
    vec3 night = texture2D(uNight, vUv).rgb;
    float nl = max(max(night.r, night.g), night.b);
    vec3 lights = night * smoothstep(0.010, 0.09, nl);
    if (uDetail > 0.0) {
      float sp = smoothstep(0.55, 0.85, vnoise(nL * 2600.0)) * 2.2 + smoothstep(0.5, 0.9, vnoise(nL * 900.0 + 7.0)) * 0.6;
      lights *= mix(1.0, sp, uDetail);
    }
    vec3 cityCol = lights * vec3(1.25, 0.86, 0.52) * 5.0;
    col += (cityCol * (1.0 - 0.75 * cHere) + night * 0.16) * nightMask;
  }

  // --- atmosphere between camera and surface (linear light): extinction + in-scatter
  vec3 rd = -V;
  float tc = -dot(cameraPosition, rd);
  float b = min(length(cameraPosition + rd * tc), 0.99999);
  float tau = opticalDepth(b, tc, uH);
  col *= exp(-tau * vec3(0.16, 0.42, 1.0) * 1.1);
  col += scatter(tau, NdotLg, dot(rd, L)) * uAtmo * 0.6;

  col = acesFilm(col * uExposure);
  col = toSRGB(col);
  col += (hash12(gl_FragCoord.xy + uSeed) - 0.5) / 255.0;
  // analytic silhouette antialiasing (canvas is premultiplied alpha)
  float bRaw = length(cameraPosition + rd * tc);
  float edge = clamp((1.0 - bRaw) / max(fwidth(bRaw), 1e-6), 0.0, 1.0);
  gl_FragColor = vec4(col * edge, edge);
}
`;

export const cloudFragment = /* glsl */ `
uniform sampler2D uBrc;
uniform vec3 uSun;
uniform mat3 uRot;
uniform float uCloudU;
uniform float uOpacity;
uniform float uExposure;
uniform float uAtmo;
uniform float uH;
uniform float uDetail;
uniform float uSeed;
varying vec2 vUv;
varying vec3 vLocal;
varying vec3 vWorld;
${COMMON}

void main() {
  vec2 cUv = vUv + vec2(uCloudU, 0.0);
  float c = cloudMask(texture2D(uBrc, cUv).b);
  if (c * uOpacity < 0.004) discard;
  // cheap relief: brighter tops, darker thin edges
  vec2 tx = vec2(1.0 / 4096.0, 1.0 / 2048.0) * 2.0;
  float cx = (cloudMask(texture2D(uBrc, cUv + vec2(tx.x, 0.0)).b) - c) * 2.0;
  float cy = (cloudMask(texture2D(uBrc, cUv + vec2(0.0, tx.y)).b) - c) * 2.0;

  vec3 nL = normalize(vLocal);
  if (uDetail > 0.0) {
    float dn = fbm3(nL * 160.0 + vec3(uCloudU * 40.0, 0.0, 0.0));
    c = clamp(c * mix(1.0, 0.45 + 1.0 * dn, uDetail), 0.0, 1.0);
  }
  vec3 east = normalize(vec3(nL.z, 0.0, -nL.x) + vec3(1e-5, 0.0, 0.0));
  vec3 north = cross(nL, east);
  vec3 nB = normalize(nL - 0.35 * (cx * east + cy * north));

  vec3 Ng = normalize(uRot * nL);
  vec3 Nb = normalize(uRot * nB);
  vec3 V = normalize(cameraPosition - vWorld);
  float NdotLg = dot(Ng, uSun);
  float NdotL = dot(Nb, uSun);

  float lit = smoothstep(-0.06, 0.10, NdotLg);
  vec3 sunCol = mix(vec3(1.0, 0.48, 0.24), vec3(1.0, 0.98, 0.96), smoothstep(0.0, 0.30, NdotLg));
  float diff = clamp(NdotL * 0.85 + 0.15, 0.0, 1.0) * lit;
  vec3 col = vec3(0.96, 0.97, 1.0) * diff * sunCol * 1.45 * (0.72 + 0.28 * c);

  float mu = max(dot(Ng, V), 0.0);
  float a = clamp(c * uOpacity, 0.0, 1.0);
  a = 1.0 - pow(1.0 - a, 1.0 + 1.8 * (1.0 - mu));   // thicker towards the limb
  a *= smoothstep(0.0, 0.08, mu);                     // fade right at the silhouette

  // same atmosphere as the surface (clouds sit low)
  vec3 rd = -V;
  float tc = -dot(cameraPosition, rd);
  float b = min(length(cameraPosition + rd * tc), 0.99999);
  float tau = opticalDepth(b, tc, uH) * 0.85;
  col *= exp(-tau * vec3(0.16, 0.42, 1.0) * 1.1);
  col += scatter(tau, NdotLg, dot(rd, uSun)) * uAtmo * 0.6;

  col = acesFilm(col * uExposure);
  col = toSRGB(col);
  col += (hash12(gl_FragCoord.xy + uSeed + 17.0) - 0.5) / 255.0;
  gl_FragColor = vec4(col, a);
}
`;

/**
 * Analytic exponential atmosphere (no ray-marching) seen AGAINST SPACE: optical depth along
 * each view ray from its impact parameter b (closest approach to the Earth centre). Only rays
 * that miss the planet (b >= 1) are drawn here — the haze over the disk is computed in linear
 * light inside the surface/cloud shaders. Output is ADDITIVE with alpha 0 (pure light added
 * over whatever is behind the canvas).
 */
export const atmosphereVertex = /* glsl */ `
varying vec3 vWorld;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorld = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
`;

export const atmosphereFragment = /* glsl */ `
uniform vec3 uSun;
uniform float uIntensity;  // limb glow
uniform float uHalo;       // wide soft halo
uniform float uH;          // scale height (Earth radii) of the thin layer
uniform float uH2;         // scale height of the halo
uniform float uExposure;
uniform float uSeed;
varying vec3 vWorld;
${COMMON}

void main() {
  vec3 ro = cameraPosition;
  vec3 rd = normalize(vWorld - ro);
  float tc = -dot(ro, rd);                 // param of closest approach
  vec3 pc = ro + rd * tc;
  float bRaw = length(pc);
  float fw = fwidth(bRaw);
  // over the disk: handled by the surface shader — except a 2px skirt under the
  // antialiased silhouette, so no dark seam appears between planet and glow
  if (bRaw < 1.0 - 2.0 * fw) discard;
  float b = max(bRaw, 1.0);

  vec3 p = tc < 0.0 ? ro : pc;             // lighting at closest approach
  float muS = dot(normalize(p), uSun);
  float cosT = dot(rd, uSun);

  float tau = opticalDepth(b, tc, uH);
  vec3 glow = scatter(tau, muS, cosT) * uIntensity;

  // soft outer halo
  float tau2 = opticalDepth(b, tc, uH2);
  vec3 halo = (1.0 - exp(-tau2 * vec3(0.22, 0.48, 1.0) * 1.2)) * smoothstep(-0.35, 0.3, muS)
            * mix(vec3(1.0, 0.55, 0.3), vec3(1.0), smoothstep(-0.1, 0.3, muS));
  float g = 0.76;
  float mie = (1.0 - g * g) / pow(1.0 + g * g - 2.0 * g * cosT, 1.5);
  halo *= uHalo * 0.14 * (1.0 + mie * 0.02);

  vec3 col = (glow + halo) * uExposure;
  col = 1.0 - exp(-col * 1.1);            // soft shoulder
  col = toSRGB(col);
  float m = max(max(col.r, col.g), col.b);
  col += (hash12(gl_FragCoord.xy + uSeed + 41.0) - 0.5) / 255.0 * smoothstep(0.0, 0.03, m);
  gl_FragColor = vec4(max(col, vec3(0.0)), 0.0);
}
`;
