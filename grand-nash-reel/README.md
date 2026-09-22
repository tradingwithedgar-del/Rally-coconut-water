# Grand Nash Studio — Reel producer

Generates cinematic 9:16 Instagram Reel ads on the **Higgsfield pay-as-you-go
REST API** (Seedance 2.5 for picture, Higgsfield TTS for narration) and cuts
them with FFmpeg into a 20.000-second master.

Two ads share one engine:

| Ad | Vertical | Concept |
|----|----------|---------|
| `hvac-01` | HVAC | *The Hottest Call of the Night* — AC fails in a Houston heat wave |
| `plumbing-01` | Plumbing | *The 11:47 Call* — a burst supply line at midnight |

Every ad is **17.0s of generated footage + a 3.0s deterministic end card**.

## Requirements

- Python 3.8+ (standard library only)
- **FFmpeg with `drawtext`, `sidechaincompress` and `gradients`** —
  `apt install ffmpeg` or `brew install ffmpeg`. Minimal static builds omit
  `drawtext`; the assembler checks and tells you.
- A Higgsfield **pay-as-you-go API key pair**. Not the MCP server, not
  subscription credits. The same pair bills both video and speech.

## Run

```bash
cp .env.example .env          # add your key pair
./produce.sh hvac-01
```

Outputs land in `build/hvac-01/`:

```
clips/     five Seedance 2.5 source clips
audio/     narration, raw and length-fitted
cut/       trimmed shots
endcard.mp4
out/final_captioned.mp4       <- the deliverable
out/final_clean.mp4           <- no captions
manifest.json                 <- prompt, settings, job id, path, status, cost metadata
```

### Spend nothing while you check the edit

```bash
python3 engine/generate.py  hvac-01 --dry-run   # print the exact payloads
python3 engine/voiceover.py hvac-01 --dry-run
python3 engine/assemble.py  hvac-01 --placeholder
```

`--placeholder` builds stand-in clips and narration and runs the whole cut, so
you can verify timing, captions and the end card before committing to spend.

## Re-rolling one shot

Generation is cached per clip.

```bash
python3 engine/generate.py hvac-01 --shot clip3_caller_finds_help --force
python3 engine/assemble.py hvac-01
```

## Swapping things

**Phone, website, CTA, logo, colours** → `brand/brand.json`. Shared by every ad.
See `brand/README-swap.md`. The end card is the only place they appear, and it
is drawn by FFmpeg, never by a model — the one way to guarantee the number on
screen is right.

**Script, captions, end-card headline** → `ads/<id>/spec.json`.

**Switching trade (plumbing ↔ HVAC)** → copy an ad directory, then edit in
`spec.json`: the five `prompt` fields, `end_card.sub2`
(`FOR HVAC COMPANIES`), `end_card.headline_wrapped`, and any caption naming the
trade. Nothing in `engine/` is trade-specific.

**A Spanish-first version later** → copy `ads/hvac-01` to `ads/hvac-01-es`,
translate `voiceover[].text` and `captions[].text`, flip the Clip 3 dialogue so
the English line is the answer, and set `audio_params.voice_id` to a Spanish
preset (`list_voices` in the Higgsfield console). The engine never inspects
language, so nothing else changes. Leave the `end_card` phone and URL alone.

## Why every clip generates long and gets trimmed

Seedance 2.5's **minimum duration is 4 seconds**, and the edit calls for beats
of 3.0–4.0s. Each shot is generated at 4–5s and trimmed to its exact editorial
length using `trim_start`, so the runtime is exact no matter what the model
returns — and you get a window to pick from instead of one fixed take.
`assemble.py` refuses to run if the shot durations stop summing to 17.0s.

## Audio

Narration is generated per line, then **length-fitted locally with `atempo`**
rather than regenerated at a different speech rate — a local fit is free, a
regeneration is another paid request. Anything needing more than a 15% stretch
is reported rather than silently squashed. The diegetic bed ducks under the
narration via `sidechaincompress`; Clip 3's bilingual exchange sits in a
narration gap, so it is never ducked. Final master is normalized to −14 LUFS.

## API contract

```
POST {base_url}{video_endpoint}      Authorization: Key <KEY_ID>:<KEY_SECRET>
POST {base_url}{audio_endpoint}
GET  {base_url}/requests/<id>/status  ->  { status, video|audio: { url } }
```

Base URL, auth format and the status path are verified against the official
`higgsfield-ai/higgsfield-js` SDK. The two **endpoint paths** are declared in
each `spec.json` under `api` and nowhere else — if Higgsfield renames one, a 404
identifies it and the fix is one line.
