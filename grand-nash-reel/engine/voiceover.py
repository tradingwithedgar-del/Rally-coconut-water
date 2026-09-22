#!/usr/bin/env python3
"""Generate the narration on Higgsfield text-to-speech, then fit it to the edit.

Each voiceover line has a fixed window in the timeline. The line is generated
once, measured, and time-fitted locally with atempo rather than regenerated at a
different speech_rate - a local fit costs nothing and a regeneration is another
paid request. Anything needing more than a 15% stretch is reported instead of
silently squashed, because past that the read stops sounding human.

    python3 engine/voiceover.py hvac-01
    python3 engine/voiceover.py hvac-01 --dry-run
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

MAX_TEMPO = 1.15
MIN_TEMPO = 0.85


def fit(src, dest, target):
    """Nudge a take onto its exact window length without another paid call."""
    actual = common.probe_duration(src)
    if not actual:
        sys.exit("Could not measure %s" % src)
    tempo = actual / target
    clamped = max(MIN_TEMPO, min(MAX_TEMPO, tempo))
    filters = ["atempo=%.4f" % clamped] if abs(clamped - 1.0) > 0.005 else []
    filters.append("apad")
    common.run([
        common.ffmpeg_bin(), "-y", "-i", src,
        "-af", ",".join(filters), "-t", "%.3f" % target,
        "-ar", "48000", "-ac", "2", dest,
    ])
    return actual, tempo, clamped


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ad", nargs="?", default="hvac-01")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec, _ = common.load(args.ad)
    audio_dir = common.build_dir(args.ad, "audio")
    manifest = common.read_manifest(args.ad)

    key, secret = ("DRY", "RUN") if args.dry_run else common.credentials()
    auth = spec["api"]["auth_header"].format(key_id=key, key_secret=secret)
    params = {k: v for k, v in spec["audio_params"].items() if not k.startswith("_")}

    for line in spec["voiceover"]:
        target = round(line["end"] - line["start"], 3)
        raw = os.path.join(audio_dir, line["id"] + "_raw.wav")
        fitted = os.path.join(audio_dir, line["id"] + ".wav")

        body = {k: v for k, v in params.items() if k not in ("model", "voice_name")}
        body["text"] = line["text"]

        if args.dry_run:
            print("\nPOST %s%s" % (spec["api"]["base_url"], spec["api"]["audio_endpoint"]))
            print(json.dumps(body, indent=2))
            print("  -> must fit %.2fs window (%.2f - %.2f)" % (target, line["start"], line["end"]))
            continue

        if not os.path.exists(raw) or args.force:
            result = common.submit_and_wait(
                spec, spec["api"]["audio_endpoint"], body, auth,
                "%s (%s, %.2fs window)" % (line["id"], params.get("voice_name"), target))
            if result.get("status") != "completed":
                sys.exit("%s ended as '%s':\n%s"
                         % (line["id"], result.get("status"), json.dumps(result, indent=2)[:1500]))
            url = ((result.get("audio") or {}).get("url")
                   or (result.get("video") or {}).get("url")
                   or result.get("url"))
            if not url:
                sys.exit("Completed but no audio url for %s:\n%s"
                         % (line["id"], json.dumps(result, indent=2)[:1500]))
            common.download(url, raw)
            manifest.setdefault("audio", {})[line["id"]] = {
                "text": line["text"],
                "model": params.get("model"),
                "endpoint": spec["api"]["audio_endpoint"],
                "settings": body,
                "window": [line["start"], line["end"]],
                "request_id": result.get("request_id"),
                "status": result.get("status"),
                "source_url": url,
                "cost_metadata": common.cost_metadata(result),
            }
        else:
            print("[skip] %s already generated" % line["id"])

        actual, wanted, applied = fit(raw, fitted, target)
        note = "fit %.2fs -> %.2fs (atempo %.3f)" % (actual, target, applied)
        if abs(wanted - applied) > 0.005:
            note += "  WARNING: needed %.3f, clamped to %.3f - rewrite this line" % (wanted, applied)
            print("    ! %s" % note)
        else:
            print("    %s" % note)
        entry = manifest.setdefault("audio", {}).setdefault(line["id"], {})
        entry["raw_duration_s"] = round(actual, 3)
        entry["target_duration_s"] = target
        entry["atempo_applied"] = round(applied, 4)
        entry["local_path"] = os.path.relpath(fitted, common.ROOT)
        common.write_manifest(args.ad, manifest)

    if not args.dry_run:
        print("\nNext: python3 engine/assemble.py %s" % args.ad)


if __name__ == "__main__":
    main()
