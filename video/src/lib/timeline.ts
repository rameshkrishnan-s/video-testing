/**
 * Timing contract (BRIEF §3).
 *
 * - `public/data/timeline.json` holds VO beats + word timestamps in SECONDS (global).
 *   It is a placeholder until the orchestrator copies the real one over it.
 * - SCENE_DEFS groups beats into scenes. Scene start = first word of its first beat - LEAD
 *   (scene 1 starts at frame 0); a scene runs until the next one starts; the last runs to 1800.
 * - NOTHING in here hard-codes frame numbers: everything is derived from the JSON, so the
 *   real VO timings drop in without code changes.
 *
 * Scene code should use `useSceneTiming(id)` (scene-LOCAL frames, i.e. the frame numbers
 * `useCurrentFrame()` returns inside the scene). Global helpers exist for captions/Main.
 */
import { useMemo } from "react";
import timelineJson from "../../public/data/timeline.json";
import { VIDEO } from "./theme";

// ---------------------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------------------
export type BeatId =
  | "hook"
  | "echo"
  | "loop"
  | "truth"
  | "distance"
  | "speed"
  | "stars"
  | "question"
  | "psych"
  | "life"
  | "payoff"
  | "final";

export type SceneId =
  | "night-sky"
  | "pull-back"
  | "karman"
  | "orbit"
  | "star-stuff"
  | "question"
  | "psych"
  | "someday"
  | "already";

export type RawWord = { text: string; start: number; end: number };
export type RawBeat = {
  id: string;
  text: string;
  start: number;
  end: number;
  words: RawWord[];
};
export type TimelineJson = {
  fps: number;
  durationInFrames: number;
  voStart: number;
  voEnd: number;
  beats: RawBeat[];
  placeholder?: boolean;
};

export type TimedWord = {
  /** As spoken in the script, with casing + trailing punctuation ("else?", "truth:"). */
  text: string;
  /** Lower-case, punctuation stripped ("else", "truth", "it's"). Use for matching. */
  clean: string;
  beatId: BeatId;
  /** Index within its beat. */
  index: number;
  /** Index within the whole VO. */
  globalIndex: number;
  /** Seconds from VIDEO start (always global). */
  start: number;
  end: number;
  /** Frames. Global in BEATS/ALL_WORDS, scene-local in useSceneTiming(). */
  startFrame: number;
  endFrame: number;
};

export type TimedBeat = {
  id: BeatId;
  text: string;
  start: number;
  end: number;
  startFrame: number;
  endFrame: number;
  words: TimedWord[];
  /** False when the scene renders this beat as kinetic type (no global captions). */
  captions: boolean;
};

export type SceneDef = {
  id: SceneId;
  beats: BeatId[];
  /** Beats whose captions are hidden (the scene shows kinetic type instead). */
  captionsHidden: BeatId[];
  owner: "A" | "B" | "C";
};

export type Scene = SceneDef & {
  /** Global start frame (use as <Sequence from>). */
  from: number;
  durationInFrames: number;
  /** Global end frame (exclusive) = from + durationInFrames. */
  to: number;
};

export type SceneTiming = Omit<Scene, "beats"> & {
  /** Beat ids of this scene (same as SCENE_DEFS). */
  beatIds: BeatId[];
  /** Beats of this scene with scene-LOCAL frames. */
  beats: TimedBeat[];
  /** All words of this scene, scene-LOCAL frames. */
  words: TimedWord[];
  /** Beat by id (scene-local frames). Throws if the beat is not in this scene. */
  beat: (id: BeatId) => TimedBeat;
  /**
   * Find a word by its cleaned text ("space", "you're", "100"...). `nth` = 0-based occurrence
   * within the scene (or within `beat`). Never throws: if missing, warns and returns a
   * synthetic word at the start of the beat/scene so renders don't crash.
   */
  word: (query: string, opts?: { beat?: BeatId; nth?: number }) => TimedWord;
  /** Word by index within a beat (clamped). */
  wordAt: (beat: BeatId, index: number) => TimedWord;
  /** Seconds -> frames helper (fps from timeline). */
  sec: (seconds: number) => number;
};

// ---------------------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------------------
export const FPS = VIDEO.fps;
export const TOTAL_FRAMES = VIDEO.durationInFrames;
/** Scenes start this many seconds before their first word. */
export const LEAD = 0.25;

/** BRIEF §3 scene table. Order matters. */
export const SCENE_DEFS: readonly SceneDef[] = [
  {
    id: "night-sky",
    beats: ["hook", "echo", "loop"],
    captionsHidden: ["hook", "echo"],
    owner: "A",
  },
  { id: "pull-back", beats: ["truth"], captionsHidden: [], owner: "A" },
  { id: "karman", beats: ["distance"], captionsHidden: [], owner: "B" },
  { id: "orbit", beats: ["speed"], captionsHidden: [], owner: "B" },
  { id: "star-stuff", beats: ["stars"], captionsHidden: [], owner: "B" },
  {
    id: "question",
    beats: ["question"],
    captionsHidden: ["question"],
    owner: "C",
  },
  { id: "psych", beats: ["psych"], captionsHidden: [], owner: "C" },
  { id: "someday", beats: ["life"], captionsHidden: [], owner: "C" },
  {
    id: "already",
    beats: ["payoff", "final"],
    captionsHidden: ["payoff", "final"],
    owner: "A",
  },
] as const;

export const BEAT_IDS: readonly BeatId[] = SCENE_DEFS.flatMap((s) => s.beats);
export const HIDDEN_CAPTION_BEATS: ReadonlySet<BeatId> = new Set(
  SCENE_DEFS.flatMap((s) => s.captionsHidden),
);

// ---------------------------------------------------------------------------------------
// Normalisation
// ---------------------------------------------------------------------------------------
export const TIMELINE = timelineJson as TimelineJson;

/** Seconds -> frame, rounding DOWN so visuals never lag the voice. */
export const toStartFrame = (t: number): number =>
  Math.max(0, Math.floor(t * FPS + 1e-6));
/** Seconds -> frame for ends (rounded). */
export const toEndFrame = (t: number): number =>
  Math.max(0, Math.round(t * FPS));
export const secondsToFrames = (s: number): number => Math.round(s * FPS);

export const cleanWord = (w: string): string =>
  w
    .toLowerCase()
    .replace(/[‘’]/g, "'")
    .replace(/[^a-z0-9'%\-]/g, "")
    .replace(/^'+|'+$/g, "");

const buildBeats = (): TimedBeat[] => {
  const byId = new Map<string, RawBeat>();
  for (const b of TIMELINE.beats) byId.set(b.id, b);
  let g = 0;
  return BEAT_IDS.map((id) => {
    const raw = byId.get(id);
    if (!raw || raw.words.length === 0) {
      throw new Error(
        `timeline.json is missing beat "${id}" (or it has no words)`,
      );
    }
    const words: TimedWord[] = raw.words.map((w, i) => {
      const startFrame = toStartFrame(w.start);
      return {
        text: w.text,
        clean: cleanWord(w.text),
        beatId: id,
        index: i,
        globalIndex: g++,
        start: w.start,
        end: w.end,
        startFrame,
        endFrame: Math.max(startFrame + 1, toEndFrame(w.end)),
      };
    });
    const start = raw.words[0].start;
    const end = raw.words[raw.words.length - 1].end;
    return {
      id,
      text: raw.text,
      start,
      end,
      startFrame: toStartFrame(start),
      endFrame: Math.max(toStartFrame(start) + 1, toEndFrame(end)),
      words,
      captions: !HIDDEN_CAPTION_BEATS.has(id),
    };
  });
};

/** All beats, GLOBAL frames, in script order. */
export const BEATS: readonly TimedBeat[] = buildBeats();
/** All words, GLOBAL frames. */
export const ALL_WORDS: readonly TimedWord[] = BEATS.flatMap((b) => b.words);

const buildScenes = (): Scene[] => {
  const froms = SCENE_DEFS.map((def, i) => {
    if (i === 0) return 0;
    const first = BEATS.find((b) => b.id === def.beats[0])!;
    return Math.max(0, Math.round((first.start - LEAD) * FPS));
  });
  // enforce strictly increasing starts
  for (let i = 1; i < froms.length; i++)
    froms[i] = Math.max(froms[i], froms[i - 1] + 1);
  return SCENE_DEFS.map((def, i) => {
    const from = froms[i];
    const to = i < froms.length - 1 ? froms[i + 1] : TOTAL_FRAMES;
    return { ...def, from, to, durationInFrames: Math.max(1, to - from) };
  });
};

/** Scenes with GLOBAL from / durationInFrames. */
export const SCENES: readonly Scene[] = buildScenes();

export const getScene = (id: SceneId): Scene => {
  const s = SCENES.find((x) => x.id === id);
  if (!s) throw new Error(`Unknown scene ${id}`);
  return s;
};

/** Beat with GLOBAL frames. */
export const getBeat = (id: BeatId): TimedBeat => {
  const b = BEATS.find((x) => x.id === id);
  if (!b) throw new Error(`Unknown beat ${id}`);
  return b;
};

/** Which scene contains a given global frame. */
export const sceneAtFrame = (globalFrame: number): Scene =>
  SCENES.find((s) => globalFrame >= s.from && globalFrame < s.to) ??
  SCENES[SCENES.length - 1];

// ---------------------------------------------------------------------------------------
// Scene-local timing
// ---------------------------------------------------------------------------------------
const shiftWord = (w: TimedWord, by: number): TimedWord => ({
  ...w,
  startFrame: w.startFrame - by,
  endFrame: w.endFrame - by,
});

const shiftBeat = (b: TimedBeat, by: number): TimedBeat => ({
  ...b,
  startFrame: b.startFrame - by,
  endFrame: b.endFrame - by,
  words: b.words.map((w) => shiftWord(w, by)),
});

const cache = new Map<SceneId, SceneTiming>();

/** Pure version of useSceneTiming (memoised). Frames are scene-LOCAL. */
export const getSceneTiming = (id: SceneId): SceneTiming => {
  const hit = cache.get(id);
  if (hit) return hit;
  const scene = getScene(id);
  const beats = scene.beats.map((bid) => shiftBeat(getBeat(bid), scene.from));
  const words = beats.flatMap((b) => b.words);

  const beat = (bid: BeatId): TimedBeat => {
    const b = beats.find((x) => x.id === bid);
    if (!b) throw new Error(`Beat "${bid}" is not part of scene "${id}"`);
    return b;
  };

  const word: SceneTiming["word"] = (query, opts) => {
    const q = cleanWord(query);
    const pool = opts?.beat ? beat(opts.beat).words : words;
    const matches = pool.filter((w) => w.clean === q);
    const nth = opts?.nth ?? 0;
    const found = matches[Math.min(nth, matches.length - 1)];
    if (found) return found;
    // eslint-disable-next-line no-console
    console.warn(
      `[timeline] word "${query}" not found in scene ${id}${opts?.beat ? `/${opts.beat}` : ""}`,
    );
    const fallback = pool[0] ?? words[0];
    return { ...fallback, text: query, clean: q };
  };

  const wordAt: SceneTiming["wordAt"] = (bid, index) => {
    const ws = beat(bid).words;
    return ws[Math.max(0, Math.min(ws.length - 1, index))];
  };

  const { beats: beatIds, ...rest } = scene;
  const timing: SceneTiming = {
    ...rest,
    beatIds,
    beats,
    words,
    beat,
    word,
    wordAt,
    sec: secondsToFrames,
  };
  cache.set(id, timing);
  return timing;
};

/**
 * Scene-local timing for a scene component.
 *
 * ```tsx
 * const t = useSceneTiming("karman");
 * const frame = useCurrentFrame();            // local frame inside the scene
 * const car = t.word("car");                  // { startFrame, endFrame, ... } local
 * const opacity = interpolate(frame, [car.startFrame - 3, car.startFrame + 8], [0, 1], CLAMP);
 * ```
 */
export const useSceneTiming = (id: SceneId): SceneTiming =>
  useMemo(() => getSceneTiming(id), [id]);

/** Index of the word being spoken at `frame` (same frame space as `words`), or -1. */
export const activeWordIndex = (
  words: readonly TimedWord[],
  frame: number,
): number => {
  for (let i = words.length - 1; i >= 0; i--) {
    if (frame >= words[i].startFrame) return frame < words[i].endFrame ? i : -1;
  }
  return -1;
};

/** Index of the last word that has started at `frame` (-1 if none). */
export const lastStartedWordIndex = (
  words: readonly TimedWord[],
  frame: number,
): number => {
  for (let i = words.length - 1; i >= 0; i--)
    if (frame >= words[i].startFrame) return i;
  return -1;
};
