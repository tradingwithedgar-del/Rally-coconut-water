# Grand Nash Studio — 20s Instagram Reel producer

Generates five cinematic shots on **Seedance 2.5** through the **Higgsfield
pay-as-you-go REST API**, then cuts them into one 9:16, 20.000-second Reel with
FFmpeg.

The creative brief, beat sheet, caption and VO script are in
[CREATIVE.md](CREATIVE.md). This file is the operating manual.

## Why the text is burned in locally

Video models cannot reliably render a phone number. Every prompt in
`shots.json` carries a hard no-text clause — no captions, logos, watermarks,
signage, or legible phone UI — and **all** on-screen copy (the beat lines and
the CTA end card with the URL and phone number) is drawn by FFmpeg in
`assemble.py`. That is the only way to guarantee the number on screen is
actually your number.

## Requirements

- Python 3.8+ (standard library only — no pip installs needed for the API client)
- **FFmpeg with `drawtext`** (i.e. built with libfreetype). `apt install ffmpeg`
  or `brew install ffmpeg` is fine. Minimal static builds often omit `drawtext`;
  `assemble.py` checks for it up front and tells you if yours does.
- A Higgsfield **pay-as-you-go API key pair**, created in the Higgsfield API
  console. This is *not* the MCP server and *not* subscription credits — it
  bills per request against your pay-as-you-go balance.

## Run it

```bash
cp .env.example .env         # then fill in your key pair
export HF_CREDENTIALS="KEY_ID:KEY_SECRET"

./produce.sh                 # generate all five shots, then assemble
```

Or step by step:

```bash
python3 scripts/generate.py --dry-run        # print the exact API requests, spend nothing
python3 scripts/generate.py                  # generate + download the five shots
python3 scripts/assemble.py                  # cut the 20s master
```

Output: `build/grand-nash-reel-20s.mp4` — 1080×1920, 30fps, H.264 high profile,
AAC 48kHz stereo, normalized to −14 LUFS, faststart, exactly 20.000s.

### Validate the edit without spending anything

```bash
python3 scripts/assemble.py --placeholder
```

Builds five synthetic slates and runs the entire cut on them. Use it to check
timing, copy, and type placement before you commit to generating footage.

## Iterating on a single shot

Generation is cached — `generate.py` skips any shot already in `build/raw/`.
To re-roll one shot (the usual case: a take where the actor's blocking is off):

```bash
python3 scripts/generate.py --shot 03_empty_office --force
python3 scripts/assemble.py
```

Everything creative lives in `shots.json`: prompts, trim points, per-shot
editorial length, overlay copy and timing, and the end card. `assemble.py`
refuses to run if the shot durations no longer sum to 20.000s, so you cannot
quietly drift off the target runtime while re-timing the cut.

## Layout

```
shots.json              Prompts, timings, overlay copy, end card, API + model params
scripts/generate.py     Higgsfield pay-as-you-go client: submit, poll, download
scripts/assemble.py     Trim/normalize -> concat -> burn text -> mix audio -> master
produce.sh              Both stages, in order
assets/                 Optional: drop music.mp3 and/or vo.wav here to have them mixed
build/raw/              Generated 5s source clips (one per shot)
build/cut/              Trimmed, normalized shots
build/grand-nash-reel-20s.mp4
```

## API contract this targets

```
POST https://api.higgsfield.ai/bytedance/seedance-2.5/text-to-video
Authorization: Key <KEY_ID>:<KEY_SECRET>
{ "prompt": "...", "aspect_ratio": "9:16", "duration": 5,
  "resolution": "1080p", "generate_audio": true, "enhance_prompt": false }
-> { "request_id": "...", "status": "queued" }

GET https://api.higgsfield.ai/requests/<request_id>/status
-> { "status": "completed", "video": { "url": "https://..." } }
```

Endpoint, auth format and every model parameter are declared in the `api` and
`model_params` blocks of `shots.json` and nowhere else, so if Higgsfield renames
a field you fix it in one place. A 422 from the API is surfaced verbatim with
the offending parameter, which is your signal to edit that block.

**Why every shot is generated at 5 seconds:** the editorial lengths are 4.5 /
3.5 / 4.0 / 4.0 / 4.0. Rather than trust the model to honor a 3.5s request, each
shot is generated at the 5s floor and trimmed to its exact length during
assembly, using the `trim_start` in `shots.json` to pick the best window of the
take. Cost is five 5s generations; the runtime is exact regardless of what the
model returns.
