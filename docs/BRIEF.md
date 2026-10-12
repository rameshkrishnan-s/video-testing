# "You've Never Left Space" — 60s Short: Master Brief

Every agent working on this video reads this file first. It is the single source of truth
for script, timing contract, look, and file layout. Do not edit it; report suggested
changes back to the orchestrator.

## 1. Deliverable

- Vertical short, **1080x1920, 30 fps, exactly 60.0 s (1800 frames)**, H.264 + AAC, -14 LUFS.
- Style: **cosmic documentary meets kinetic typography.** Real (textured, 3D) Earth,
  deep black-blue space, crisp white type, one warm accent. Calm voice, big ideas, constant motion.
- Goal: curiosity + retention. Hook in the first second, open loop ("it's about you"),
  three escalating "wait, what?" facts, a pattern-interrupt question, a psychological
  reveal, an emotional payoff, and an ending that loops seamlessly into frame 0.

## 2. Script (voiceover, by beat)

| # | beat id    | narration |
|---|------------|-----------|
| 1 | `hook`     | Why do we always talk about space like it's somewhere else? |
| 2 | `echo`     | Out there. Up there. Far away. |
| 3 | `loop`     | The answer isn't really about space. It's about you. |
| 4 | `truth`    | Here's the truth: you've never left space. Not for a single second. |
| 5 | `distance` | The so-called edge of space? Just a hundred kilometers up. If your car could drive straight up, you'd be there in about an hour. |
| 6 | `speed`    | And right now, sitting perfectly still, you're racing around the Sun at over a hundred thousand kilometers an hour. |
| 7 | `stars`    | The iron in your blood? Forged inside stars that exploded before Earth even existed. |
| 8 | `question` | So why does it feel so far away? |
| 9 | `psych`    | Psychologists call it psychological distance. The farther away something feels, the more abstractly we think about it. Blurrier. Less yours. |
| 10 | `life`    | And we do it with everything. Our dreams. Our goals. The life we keep saying will start... someday. |
| 11 | `payoff`  | But you don't go to space. You're already in it. |
| 12 | `final`   | And the life you keep waiting for? You're already living it. |

Facts behind the claims (for on-screen labels):
- Kármán line: conventional (FAI) edge of space, **100 km** altitude; the atmosphere has no sharp edge, which is why "so-called" edge. 100 km at 100 km/h = 1 hour.
- Earth's mean orbital speed: **29.8 km/s ≈ 107,000 km/h**.
- Iron (Fe, atomic number 26) is made in stars and spread by supernovae; the Solar System
  formed ~4.6 billion years ago from that enriched gas.
- Psychological distance / Construal Level Theory (Trope & Liberman): the more distant
  something feels (in space, time, social distance, likelihood), the more abstractly we think about it.

## 3. Timing contract

The voice agent produces `audio/out/timeline.json` (copied by the orchestrator to
`video/public/data/timeline.json`):

```json
{
  "fps": 30,
  "durationInFrames": 1800,
  "voStart": 0.08,
  "voEnd": 57.3,
  "beats": [
    {
      "id": "hook",
      "text": "Why do we always talk about space like it's somewhere else?",
      "start": 0.08,
      "end": 3.35,
      "words": [ { "text": "Why", "start": 0.08, "end": 0.27 }, ... ]
    }
  ]
}
```

- Times are **seconds from video start** (floats). Word `text` keeps the script's casing
  and trailing punctuation (`"else?"`, `"truth:"`).
- VO must finish by **57.5 s** at the latest; the last ~2.5 s are the visual/music outro.

Scenes (defined in `video/src/lib/timeline.ts`) group beats. A scene starts `LEAD = 0.25 s`
before its first beat's first word (scene 1 starts at frame 0) and runs until the next scene
starts; the last scene runs to frame 1800.

| scene id     | beats                  | owner           | captions |
|--------------|------------------------|-----------------|----------|
| `night-sky`  | hook, echo, loop       | Scene agent A   | hidden for hook + echo (kinetic type), shown for loop |
| `pull-back`  | truth                  | Scene agent A   | shown |
| `karman`     | distance               | Scene agent B   | shown |
| `orbit`      | speed                  | Scene agent B   | shown |
| `star-stuff` | stars                  | Scene agent B   | shown |
| `question`   | question               | Scene agent C   | hidden (kinetic type) |
| `psych`      | psych                  | Scene agent C   | shown |
| `someday`    | life                   | Scene agent C   | shown |
| `already`    | payoff, final          | Scene agent A   | hidden (kinetic type) |

"Hidden" beats: the scene itself renders the spoken words as big kinetic type, revealed
word-by-word in sync with `words[].start`.

## 4. Look & feel

Palette (exported from `video/src/lib/theme.ts`):
- `bg0` #04050A (void), `bg1` #0A1022 (deep navy), `bg2` #121A33
- `text` #F4F6FF, `textDim` rgba(244,246,255,0.62)
- `accent` #FFB547 (solar amber — key numbers, "YOU", emphasis)
- `sky` #5CC8FF (atmosphere cyan — HUD lines, data, science labels)
- `danger` #FF5A4E (blood/iron red, used sparingly)

Typography:
- **Montserrat** 800/900 — headlines, kinetic type, captions. Uppercase for kinetic type.
- **JetBrains Mono** 500/700 — HUD labels, units, counters (tabular numbers), small source tags.
- Min sizes at 1080 wide: headline 96px+, captions 68-76px, HUD labels 34px+.

Layout (1080x1920):
- Safe area: 90px left/right, 160px top. **Bottom 380px and right 150px are platform UI**:
  nothing important there.
- **Caption zone: y 1240-1480** (full width). When captions are shown, scene graphics keep
  that band clear of text and busy detail.
- Hero visuals live in y 220-1200.

Motion rules:
- Nothing is ever static for more than ~1 s: slow camera drift / push at minimum.
- Visual change roughly every 1.5-3 s (new element, camera move, cut).
- Ease with `Easing.bezier(0.16, 1, 0.3, 1)` (expo-out) for entrances, springs for pops.
- Visuals may lead the words by a few frames; never lag them.
- All animation driven by `useCurrentFrame()` (no CSS animations, no `useFrame`, no `Math.random()`
  without a seed: use `random(seed)` from `remotion` or `@remotion/noise`).
- Global overlays (film grain, vignette, captions) are applied by the main composition, not by scenes.

## 5. Shot list

**night-sky (hook, echo, loop)** — Ground-level night sky. Dense starfield with a soft Milky Way
band, faint horizon glow, black silhouette of a hill/horizon line at the bottom with one tiny
human figure looking up (around x 540, y ~1560-1640). Slow upward tilt (stars drift down).
- hook: giant kinetic type stacked center (y ~450-1000): `WHY DO WE ALWAYS / TALK ABOUT SPACE /
  LIKE IT'S / SOMEWHERE ELSE?` Words pop in on their timestamps. `SPACE` in amber; `SOMEWHERE ELSE?`
  gets extra weight/scale. Frame 0 already shows "WHY" (no empty first frame).
- echo: the hook text clears; three HUD labels with thin cyan leader lines point up at distant
  stars: `OUT THERE`, `UP THERE`, `FAR AWAY`, each appearing on its word and each smaller / higher
  / dimmer (receding), with a parallax push upward.
- loop: camera tilts back down to the tiny human; an amber targeting reticle locks onto them with
  the label `YOU`. Captions on.

**pull-back (truth)** — The signature shot. From the reticle on the human, a fast continuous
zoom-out: ground → clouds → atmosphere → the whole **3D Earth** hanging in black space, rotating
slowly, sun-lit, with an amber pin "YOU ARE HERE" on the visible hemisphere. Big impact on
"never left space". Gentle settle for "Not for a single second".

**karman (distance)** — Close-up of Earth's curved limb across the lower-middle of the frame with
the thin glowing blue atmosphere band. A vertical altitude ruler rises from the surface with ticks
0-100 km; a dashed amber line at 100 km labelled `KÁRMÁN LINE · EDGE OF SPACE (BY CONVENTION)`; big counter
`100 KM`. On "If your car could drive straight up": a small car icon drives up the ruler while a
HUD readout shows `100 KM/H` → `≈ 1 HOUR`.

**orbit (speed)** — "sitting perfectly still": calm frame, readout `VS. THE GROUND: 0 KM/H` (feels still).
Then the camera pulls out to a top-down solar view: glowing Sun, thin orbit ellipse, Earth racing
along it with a motion trail, background stars streaking. Readout label switches to `VS. THE SUN:` and the counter ramps to `107,000 KM/H` (amber)
with sub-line `≈ 30 KM EVERY SECOND`.

**star-stuff (stars)** — Macro of a red blood drop/cell glow; a periodic-table tile `26 · Fe · IRON`
emerges. Hard cut on "Forged inside stars": a star collapses and **explodes** (flash, shockwave ring,
debris particles, colorful nebula), debris streams toward camera. Label `SUPERNOVA · BEFORE EARTH
EXISTED (> 4.5 BILLION YEARS AGO)`.

**question (question)** — Pattern interrupt. Music drops out. Near-black frame with sparse stars.
Kinetic type center: `SO WHY DOES IT / FEEL SO / FAR AWAY?` word by word; `FAR AWAY?` in amber
and visibly *recedes* (scales down, blurs slightly) as it lands.

**psych (psych)** — Explainer graphic. Title `PSYCHOLOGICAL DISTANCE` with small source tag
`Construal Level Theory · Trope & Liberman`. A `YOU` dot near the bottom of the hero area with a
perspective depth grid receding to a vanishing point above. Objects placed at increasing distance:
near = sharp, colorful, detailed; far = blurred, desaturated, reduced to outline, then a dot.
Axis labels `HERE → THERE` and `NOW → SOMEDAY`. On "Blurrier. Less yours." the far object fades to a dot.

**someday (life)** — Words `DREAMS`, `GOALS`, `THE LIFE YOU WANT` (on their spoken words) are
flung up and away into a starry sky, shrinking/blurring until they become stars. `SOMEDAY` hangs
tiny at the vanishing point, flickering like a distant star.

**already (payoff, final)** — Reversal. On "But you don't go to space": everything rushes back toward
the viewer (warp streaks inward-to-outward), Earth fills the frame, pin `YOU ARE HERE` glows.
Kinetic type: `YOU'RE ALREADY / IN IT.` (amber `IN IT.`). Then the final line as kinetic type:
`AND THE LIFE YOU KEEP WAITING FOR?` → `YOU'RE ALREADY LIVING IT.` Meanwhile the camera returns
to the ground-level night sky with the tiny human (a warm dawn glow touches the horizon briefly).
In the final ~1 s, text fades and the frame settles to match **frame 0 of night-sky** (same
sky, same silhouette, same framing) so the loop is seamless.

## 6. Audio

- VO: Kokoro-82M (`af_heart`), 48 kHz, clean, warm.
- Music: original procedural ambient score synced to beats (mysterious → pulse → drop-out at
  `question` → reflective → warm major bloom at `payoff` → soft tail that loops into the start).
- SFX: synthesized whooshes, sub impacts, risers, ticks, shimmer, supernova boom.
- Master: VO on top, music ducked under voice, -14 LUFS integrated, ≤ -1 dBTP, exactly 60.0 s.

## 7. File layout

```
docs/BRIEF.md                 this file
audio/                        python audio pipeline (tts, music, sfx, mix); models/ is gitignored
audio/out/                    vo.wav, timeline.json, music.wav, sfx.wav, master.wav
video/                        Remotion project
video/public/{data,fonts,textures,img,audio}
video/src/lib/                shared design system (theme, timeline helpers, components)
video/src/scenes/             one file (or folder) per scene
output/                       final deliverable mp4 + poster
```

Rules for all agents: only edit files you own; never run `npm install` in `video/` unless your
task says so; no network downloads except from npm, PyPI, raw.githubusercontent.com and GitHub
release assets; never commit or push (the orchestrator does).
