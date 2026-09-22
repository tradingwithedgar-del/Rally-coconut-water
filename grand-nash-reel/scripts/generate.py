#!/usr/bin/env python3
"""Generate the five Seedance 2.5 shots via the Higgsfield pay-as-you-go REST API.

This talks to the open/pay-as-you-go platform at api.higgsfield.ai directly.
It is deliberately NOT the Higgsfield MCP server and NOT the subscription-credit
app: authentication is a pay-as-you-go API key pair, billed per request.

Stdlib only, so it runs anywhere python3 does.

    export HF_CREDENTIALS="KEY_ID:KEY_SECRET"
    python3 scripts/generate.py                 # generate anything not already downloaded
    python3 scripts/generate.py --shot 03_empty_office --force
    python3 scripts/generate.py --dry-run       # print the exact requests, call nothing
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(ROOT, "shots.json")
RAW_DIR = os.path.join(ROOT, "build", "raw")

POLL_INTERVAL = 5
POLL_TIMEOUT = 900
TERMINAL = {"completed", "failed", "nsfw", "canceled", "cancelled"}


def credentials():
    combined = os.environ.get("HF_CREDENTIALS") or os.environ.get("HF_KEY")
    if combined and combined.count(":") == 1:
        return tuple(combined.split(":"))
    key, secret = os.environ.get("HF_API_KEY"), os.environ.get("HF_API_SECRET")
    if key and secret:
        return key, secret
    sys.exit(
        "No Higgsfield pay-as-you-go credentials found.\n"
        "Set HF_CREDENTIALS='KEY_ID:KEY_SECRET' (or HF_API_KEY + HF_API_SECRET).\n"
        "Create a key pair in the Higgsfield API console, not the subscription app."
    )


def request(method, url, auth, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        hint = ""
        if exc.code == 401:
            hint = "  -> key pair rejected. Check HF_CREDENTIALS."
        elif exc.code == 403:
            hint = "  -> out of pay-as-you-go balance, or key lacks access to this model."
        elif exc.code == 422:
            hint = "  -> the model rejected a parameter. Fix model_params in shots.json."
        sys.exit("HTTP %s from %s\n%s%s" % (exc.code, url, detail, "\n" + hint if hint else ""))


def submit(spec, shot, auth, verbose):
    url = spec["api"]["base_url"] + spec["api"]["endpoint"]
    prompt = shot["prompt"] + "\n\n" + spec["style_bible"] + "\n\n" + spec["no_text_clause"]
    body = {k: v for k, v in spec["model_params"].items() if not k.startswith("_")}
    body["prompt"] = prompt
    if verbose:
        print("POST %s\n%s" % (url, json.dumps(body, indent=2)[:4000]))
        return None
    resp = request("POST", url, auth, body)
    request_id = resp.get("request_id")
    if not request_id:
        sys.exit("No request_id in submit response: %s" % json.dumps(resp)[:500])
    return request_id


def wait(spec, request_id, auth):
    path = spec["api"]["status_path"].format(request_id=request_id)
    url = spec["api"]["base_url"] + path
    deadline = time.time() + POLL_TIMEOUT
    last = None
    while time.time() < deadline:
        resp = request("GET", url, auth)
        status = resp.get("status")
        if status != last:
            print("    status: %s" % status)
            last = status
        if status in TERMINAL:
            return resp
        time.sleep(POLL_INTERVAL)
    sys.exit("Timed out after %ss waiting on request %s" % (POLL_TIMEOUT, request_id))


def download(url, dest):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as handle:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot", action="append", help="only this shot id (repeatable)")
    parser.add_argument("--force", action="store_true", help="regenerate even if the file exists")
    parser.add_argument("--dry-run", action="store_true", help="print requests, call nothing")
    args = parser.parse_args()

    with open(SPEC_PATH) as handle:
        spec = json.load(handle)
    os.makedirs(RAW_DIR, exist_ok=True)

    key, secret = ("DRY", "RUN") if args.dry_run else credentials()
    auth = spec["api"]["auth_header"].format(key_id=key, key_secret=secret)

    shots = spec["shots"]
    if args.shot:
        wanted = set(args.shot)
        shots = [s for s in shots if s["id"] in wanted]
        missing = wanted - {s["id"] for s in shots}
        if missing:
            sys.exit("Unknown shot id(s): %s" % ", ".join(sorted(missing)))

    manifest = {}
    for shot in shots:
        dest = os.path.join(RAW_DIR, shot["id"] + ".mp4")
        if os.path.exists(dest) and not args.force and not args.dry_run:
            print("[skip] %s already downloaded" % shot["id"])
            manifest[shot["id"]] = dest
            continue

        print("[gen ] %s - %s" % (shot["id"], shot["label"]))
        request_id = submit(spec, shot, auth, args.dry_run)
        if args.dry_run:
            continue

        result = wait(spec, request_id, auth)
        if result.get("status") != "completed":
            sys.exit(
                "Shot %s ended as '%s'. Full response:\n%s"
                % (shot["id"], result.get("status"), json.dumps(result, indent=2)[:2000])
            )
        video = (result.get("video") or {}).get("url")
        if not video:
            sys.exit("Completed but no video url for %s:\n%s" % (shot["id"], json.dumps(result)[:1000]))
        download(video, dest)
        print("    saved %s (%.1f MB)" % (dest, os.path.getsize(dest) / 1e6))
        manifest[shot["id"]] = dest

    if not args.dry_run and manifest:
        path = os.path.join(ROOT, "build", "manifest.json")
        with open(path, "w") as handle:
            json.dump(manifest, handle, indent=2)
        print("\nWrote %s\nNext: python3 scripts/assemble.py" % path)


if __name__ == "__main__":
    main()
