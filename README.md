# You've Never Left Space — 60s short

**Watch / download:** [`output/youve-never-left-space.mp4`](output/youve-never-left-space.mp4) (1080x1920, 30 fps, 60 s, H.264 + AAC, -14 LUFS)

Hook: *"Why do we always talk about space like it's somewhere else?"* → three facts (the edge of space is 100 km up, you're moving at 107,000 km/h around the Sun, the iron in your blood came from exploded stars) → psychological distance → "You're already in it." The ending loops back into the first frame.

## How it was made
- `docs/BRIEF.md` — script, timing contract, shot list, look.
- `audio/` — Kokoro-82M TTS (`af_heart`) with word timestamps taken from the model's own duration predictor (`tts.py`), an original procedural score + synthesized SFX (`music.py`, `sfx.py`), and the master mix (`mix.py`).
- `video/` — Remotion project: 3D Earth (three.js shader), procedural sky, kinetic type, word-synced captions. Render with `npx remotion render Main`.

## Credits
- Earth textures: NASA Blue Marble / Black Marble derived maps via the three.js examples (public domain).
- Fonts: Montserrat, JetBrains Mono (SIL OFL).
- Voice: Kokoro-82M (Apache 2.0). Music and sound effects: original, generated for this video.
