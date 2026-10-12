#!/usr/bin/env python3
"""Write a schema-correct PLACEHOLDER public/data/timeline.json.

The real file is produced by the audio pipeline (audio/out/timeline.json) and copied over
this one by the orchestrator. Timings here are synthetic (~2.8 words/s, pauses at
punctuation, gaps between beats, VO ending ~57 s) so scenes can be built before the VO exists.

Run:  python3 tools/make_placeholder_timeline.py
"""
import json
import os
import re

FPS = 30
DURATION = 1800
VO_START = 0.08
VO_END = 57.0

BEATS = [
    ("hook", "Why do we always talk about space like it's somewhere else?"),
    ("echo", "Out there. Up there. Far away."),
    ("loop", "The answer isn't really about space. It's about you."),
    ("truth", "Here's the truth: you've never left space. Not for a single second."),
    ("distance", "It starts just a hundred kilometers up. If your car could drive straight up, you'd be there in about an hour."),
    ("speed", "And right now, sitting perfectly still, you're racing around the Sun at over a hundred thousand kilometers an hour."),
    ("stars", "The iron in your blood? Forged inside stars that exploded before Earth even existed."),
    ("question", "So why does it feel so far away?"),
    ("psych", "Psychologists call it psychological distance. The farther away something feels, the more abstract your brain makes it. Less real. Less yours."),
    ("life", "And we do it with everything. Our dreams. Our goals. The life we keep saying will start... someday."),
    ("payoff", "But you don't go to space. You're already in it."),
    ("final", "And the life you keep waiting for? You're already living it."),
]

# Pause (s) BEFORE each beat (dramatic gaps before question / payoff).
BEAT_GAP = {"question": 0.9, "payoff": 0.8, "psych": 0.6, "final": 0.6}
DEFAULT_BEAT_GAP = 0.45


def word_weight(w: str) -> float:
    letters = len(re.sub(r"[^A-Za-z']", "", w))
    return 0.55 + 0.11 * letters


def pause_after(w: str) -> float:
    if w.endswith("..."):
        return 0.45
    if w[-1] in ".?!":
        return 0.32
    if w[-1] in ",:;":
        return 0.18
    return 0.03


def main() -> None:
    # 1) Build an unscaled layout in "units".
    layout = []  # (beat_id, text, [(word, start_u, end_u)])
    t = 0.0
    for i, (bid, text) in enumerate(BEATS):
        if i > 0:
            t += BEAT_GAP.get(bid, DEFAULT_BEAT_GAP) * 2.2
        words = []
        toks = text.split()
        for j, w in enumerate(toks):
            d = word_weight(w)
            words.append([w, t, t + d])
            t += d
            if j < len(toks) - 1:
                t += pause_after(w) * 2.2
        layout.append((bid, text, words))
    total_u = t
    scale = (VO_END - VO_START) / total_u

    beats_out = []
    for bid, text, words in layout:
        ws = [
            {"text": w, "start": round(VO_START + s * scale, 3), "end": round(VO_START + e * scale, 3)}
            for w, s, e in words
        ]
        beats_out.append({"id": bid, "text": text, "start": ws[0]["start"], "end": ws[-1]["end"], "words": ws})

    n_words = sum(len(b["words"]) for b in beats_out)
    data = {
        "fps": FPS,
        "durationInFrames": DURATION,
        "voStart": beats_out[0]["start"],
        "voEnd": beats_out[-1]["end"],
        "placeholder": True,
        "beats": beats_out,
    }
    out = os.path.join(os.path.dirname(__file__), "..", "public", "data", "timeline.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    speech = sum(b["end"] - b["start"] for b in beats_out)
    print(f"wrote {out}: {n_words} words, voEnd={data['voEnd']}, {n_words / (data['voEnd'] - data['voStart']):.2f} words/s overall")
    for b in beats_out:
        print(f"  {b['id']:9s} {b['start']:6.2f} - {b['end']:6.2f}  ({len(b['words'])} words)")
    _ = speech


if __name__ == "__main__":
    main()
