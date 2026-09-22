#!/usr/bin/env python3
"""Generate the ad's Seedance 2.5 source clips on the Higgsfield pay-as-you-go API.

    export HF_CREDENTIALS="KEY_ID:KEY_SECRET"
    python3 engine/generate.py hvac-01
    python3 engine/generate.py hvac-01 --dry-run
    python3 engine/generate.py hvac-01 --shot clip3_caller_finds_help --force
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ad", nargs="?", default="hvac-01")
    ap.add_argument("--shot", action="append", help="only this shot id (repeatable)")
    ap.add_argument("--force", action="store_true", help="regenerate even if downloaded")
    ap.add_argument("--dry-run", action="store_true", help="print payloads, spend nothing")
    args = ap.parse_args()

    spec, _ = common.load(args.ad)
    clips_dir = common.build_dir(args.ad, "clips")
    manifest = common.read_manifest(args.ad)

    key, secret = ("DRY", "RUN") if args.dry_run else common.credentials()
    auth = spec["api"]["auth_header"].format(key_id=key, key_secret=secret)

    shots = spec["shots"]
    if args.shot:
        wanted = set(args.shot)
        shots = [s for s in shots if s["id"] in wanted]
        missing = wanted - {s["id"] for s in shots}
        if missing:
            sys.exit("Unknown shot id(s): %s" % ", ".join(sorted(missing)))

    params = {k: v for k, v in spec["video_params"].items() if not k.startswith("_")}
    billable = 0

    for shot in shots:
        dest = os.path.join(clips_dir, shot["id"] + ".mp4")
        if os.path.exists(dest) and not args.force and not args.dry_run:
            print("[skip] %s already downloaded" % shot["id"])
            continue

        body = dict(params)
        body["prompt"] = shot["prompt"]
        body["duration"] = shot["gen_duration"]
        billable += shot["gen_duration"]

        if args.dry_run:
            print("\nPOST %s%s" % (spec["api"]["base_url"], spec["api"]["video_endpoint"]))
            print(json.dumps(body, indent=2))
            continue

        result = common.submit_and_wait(
            spec, spec["api"]["video_endpoint"], body, auth,
            "%s - %s (%ds)" % (shot["id"], shot["label"], shot["gen_duration"]))

        entry = {
            "prompt": shot["prompt"],
            "model": "bytedance/seedance-2.5",
            "endpoint": spec["api"]["video_endpoint"],
            "settings": body,
            "generated_duration_s": shot["gen_duration"],
            "editorial_duration_s": shot["edit_duration"],
            "trim_start_s": shot["trim_start"],
            "request_id": result.get("request_id"),
            "status": result.get("status"),
            "local_path": os.path.relpath(dest, common.ROOT),
            "cost_metadata": common.cost_metadata(result),
        }

        if result.get("status") != "completed":
            entry["error"] = json.dumps(result)[:2000]
            manifest["video"][shot["id"]] = entry
            common.write_manifest(args.ad, manifest)
            sys.exit("Shot %s ended as '%s'. Manifest updated." % (shot["id"], result.get("status")))

        video_url = (result.get("video") or {}).get("url")
        if not video_url:
            entry["error"] = "completed but no video.url"
            manifest["video"][shot["id"]] = entry
            common.write_manifest(args.ad, manifest)
            sys.exit("No video url for %s:\n%s" % (shot["id"], json.dumps(result)[:1000]))

        common.download(video_url, dest)
        entry["source_url"] = video_url
        entry["downloaded_bytes"] = os.path.getsize(dest)
        manifest["video"][shot["id"]] = entry
        common.write_manifest(args.ad, manifest)
        print("    saved %s (%.1f MB)" % (dest, os.path.getsize(dest) / 1e6))

    if args.dry_run:
        print("\n%d clips, %d billable generated seconds at %s"
              % (len(shots), billable, params.get("resolution")))
    else:
        print("\nManifest: %s" % common.manifest_path(args.ad))
        print("Next: python3 engine/voiceover.py %s" % args.ad)


if __name__ == "__main__":
    main()
