import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import {
  BEATS,
  type BeatId,
  type TimedBeat,
  type TimedWord,
} from "../timeline";
import { CAPTION_ZONE, CLAMP, COLORS, EASE, FONTS, TYPE } from "../theme";

export type CaptionChunk = {
  beatId: BeatId;
  words: TimedWord[];
  /** Words split into display lines (max 2). */
  lines: TimedWord[][];
  /** GLOBAL frames. */
  startFrame: number;
  endFrame: number;
  /** True if the next chunk starts exactly when this one ends (no fade-out). */
  handoff: boolean;
};

export type CaptionOptions = {
  maxWords?: number;
  maxChars?: number;
  /** Pause (s) that forces a new chunk. */
  gapBreak?: number;
  /** Frames a chunk appears before its first word. */
  lead?: number;
  /** Frames a chunk lingers after its last word (if nothing follows sooner). */
  hold?: number;
};

const DEFAULTS: Required<CaptionOptions> = {
  maxWords: 3,
  maxChars: 16,
  gapBreak: 0.35,
  lead: 2,
  hold: 14,
};

const lineLen = (ws: TimedWord[]) =>
  ws.map((w) => w.text.length).reduce((a, b) => a + b, 0) +
  Math.max(0, ws.length - 1);

/** Split words into <= 2 balanced lines of <= maxChars, or null if impossible. */
export const layoutLines = (
  ws: TimedWord[],
  maxChars: number,
): TimedWord[][] | null => {
  if (lineLen(ws) <= maxChars) return [ws];
  let best: TimedWord[][] | null = null;
  let bestScore = Infinity;
  for (let i = 1; i < ws.length; i++) {
    const a = ws.slice(0, i);
    const b = ws.slice(i);
    const la = lineLen(a);
    const lb = lineLen(b);
    if (la > maxChars || lb > maxChars) continue;
    const score = Math.max(la, lb) + (la > lb ? 0 : 0.5); // prefer top line slightly longer
    if (score < bestScore) {
      bestScore = score;
      best = [a, b];
    }
  }
  if (!best && ws.length === 1) return [ws]; // single very long word: allow overflow
  return best;
};

const endsPhrase = (t: string) => /[.,!?;:…]$/.test(t) || t.endsWith("...");

/** Chunk caption-visible beats into 1-3 word pages (GLOBAL frames). Pure + deterministic. */
export const buildCaptionChunks = (
  beats: readonly TimedBeat[] = BEATS,
  options: CaptionOptions = {},
): CaptionChunk[] => {
  const o = { ...DEFAULTS, ...options };
  const raw: { beatId: BeatId; words: TimedWord[] }[] = [];
  for (const beat of beats) {
    if (!beat.captions) continue;
    // 1) phrases: split at punctuation and long pauses
    const phrases: TimedWord[][] = [];
    let cur: TimedWord[] = [];
    beat.words.forEach((w, i) => {
      if (cur.length > 0) {
        const prev = cur[cur.length - 1];
        if (endsPhrase(prev.text) || w.start - prev.end > o.gapBreak) {
          phrases.push(cur);
          cur = [];
        }
      }
      cur.push(w);
      if (i === beat.words.length - 1) phrases.push(cur);
    });
    // 2) each phrase -> balanced chunks of <= maxWords that fit in 2 lines
    for (const ph of phrases) {
      let k = Math.ceil(ph.length / o.maxWords);
      for (; k <= ph.length; k++) {
        const sizes = Array.from(
          { length: k },
          (_, j) => Math.floor(ph.length / k) + (j < ph.length % k ? 1 : 0),
        );
        let idx = 0;
        const parts = sizes.map((n) => {
          const part = ph.slice(idx, idx + n);
          idx += n;
          return part;
        });
        if (parts.every((p) => layoutLines(p, o.maxChars))) {
          parts.forEach((p) => raw.push({ beatId: beat.id, words: p }));
          break;
        }
      }
    }
  }
  return raw.map((c, i) => {
    const first = c.words[0];
    const last = c.words[c.words.length - 1];
    const next = raw[i + 1];
    const startFrame = Math.max(first.startFrame - o.lead, 0);
    const nextStart = next
      ? Math.max(next.words[0].startFrame - o.lead, 0)
      : Infinity;
    const naturalEnd = last.endFrame + o.hold;
    const endFrame = Math.max(startFrame + 1, Math.min(naturalEnd, nextStart));
    return {
      beatId: c.beatId,
      words: c.words,
      lines: layoutLines(c.words, o.maxChars) ?? [c.words],
      startFrame,
      endFrame,
      handoff: endFrame >= nextStart,
    };
  });
};

const CHUNKS = buildCaptionChunks();

export type CaptionsProps = {
  /** Added to useCurrentFrame() to get the GLOBAL frame (SceneHarness passes scene.from). */
  frameOffset?: number;
  fontSize?: number;
  /** Uppercase captions (default false: script casing). */
  uppercase?: boolean;
  /** Override the chunk list (testing). */
  chunks?: CaptionChunk[];
  /** Vertical band (default CAPTION_ZONE). */
  zone?: { top: number; bottom: number };
};

const OUTLINE = [
  "0 0 2px rgba(4,5,10,0.95)",
  "0 0 1px rgba(4,5,10,0.95)",
  "0 3px 4px rgba(4,5,10,0.75)",
  "0 6px 24px rgba(0,0,0,0.65)",
  "0 0 40px rgba(0,0,0,0.35)",
].join(", ");

/**
 * Global caption track (Main + SceneHarness). 1-3 word chunks centred in CAPTION_ZONE,
 * Montserrat 800, active word amber with a small spring pop. Beats with captions=false
 * (kinetic-type beats) are skipped.
 */
export const Captions: React.FC<CaptionsProps> = ({
  frameOffset = 0,
  fontSize = TYPE.caption,
  uppercase = false,
  chunks = CHUNKS,
  zone = CAPTION_ZONE,
}) => {
  const { fps, width } = useVideoConfig();
  const g = useCurrentFrame() + frameOffset;
  const chunk = chunks.find((c) => g >= c.startFrame && g < c.endFrame);
  if (!chunk) return null;

  const tIn = g - chunk.startFrame;
  const tOut = chunk.endFrame - g;
  const inP = interpolate(tIn, [0, 5], [0, 1], {
    ...CLAMP,
    easing: EASE.expoOut,
  });
  const outP = chunk.handoff ? 1 : interpolate(tOut, [0, 4], [0, 1], CLAMP);
  const opacity = Math.min(inP, outP);

  // active word = last word that has started
  let active = -1;
  chunk.words.forEach((w, i) => {
    if (g >= w.startFrame) active = i;
  });

  let wi = 0;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        width,
        top: zone.top,
        height: zone.bottom - zone.top,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        pointerEvents: "none",
        opacity,
        translate: `0 ${interpolate(inP, [0, 1], [18, 0])}px`,
        scale: String(interpolate(inP, [0, 1], [0.96, 1])),
      }}
    >
      {chunk.lines.map((line, li) => (
        <div
          key={li}
          style={{
            display: "flex",
            justifyContent: "center",
            gap: fontSize * 0.3,
            maxWidth: 800,
            fontFamily: FONTS.display,
            fontWeight: 800,
            fontSize,
            lineHeight: 1.12,
            letterSpacing: "-0.005em",
            color: COLORS.text,
            textShadow: OUTLINE,
            whiteSpace: "nowrap",
          }}
        >
          {line.map((w) => {
            const i = wi++;
            const isActive = i === active;
            const since = g - w.startFrame;
            const pop = isActive
              ? spring({
                  frame: since,
                  fps,
                  config: { damping: 11, stiffness: 240, mass: 0.5 },
                })
              : 0;
            const nextStart = chunk.words[i + 1]?.startFrame;
            const after =
              !isActive && nextStart !== undefined && g >= nextStart
                ? g - nextStart
                : Infinity;
            const decay = after < 5 ? 1 - after / 5 : 0;
            const scale = isActive ? 1 + 0.05 * pop : 1 + 0.05 * decay;
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  color: isActive ? COLORS.accent : COLORS.text,
                  scale: String(scale),
                  transformOrigin: "50% 60%",
                }}
              >
                {uppercase ? w.text.toUpperCase() : w.text}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};
