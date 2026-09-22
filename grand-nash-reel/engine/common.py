#!/usr/bin/env python3
"""Shared Higgsfield pay-as-you-go client plus manifest handling.

Stdlib only. This is the pay-as-you-go REST platform at api.higgsfield.ai,
authenticated with a key pair and billed per request. It is deliberately not
the MCP server and not subscription credits.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLL_INTERVAL = 5
POLL_TIMEOUT = 900
TERMINAL = {"completed", "failed", "nsfw", "canceled", "cancelled"}


def load(ad):
    spec = json.load(open(os.path.join(ROOT, "ads", ad, "spec.json")))
    brand = json.load(open(os.path.join(ROOT, "brand", "brand.json")))
    return spec, brand


def build_dir(ad, *parts):
    path = os.path.join(ROOT, "build", ad, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def credentials():
    combined = os.environ.get("HF_CREDENTIALS") or os.environ.get("HF_KEY")
    if combined and combined.count(":") == 1:
        return tuple(combined.split(":"))
    key, secret = os.environ.get("HF_API_KEY"), os.environ.get("HF_API_SECRET")
    if key and secret:
        return key, secret
    sys.exit(
        "No Higgsfield pay-as-you-go credentials found.\n"
        "  export HF_CREDENTIALS='KEY_ID:KEY_SECRET'\n"
        "Create the key pair in the Higgsfield API console. Every request in this\n"
        "pipeline, video and text-to-speech alike, is billed against that balance."
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
        hints = {
            401: "key pair rejected - check HF_CREDENTIALS.",
            403: "out of pay-as-you-go balance, or this key cannot use this model.",
            404: "endpoint path not found - fix api.*_endpoint in the ad's spec.json.",
            422: "a parameter was rejected - fix video_params/audio_params in spec.json.",
        }
        hint = hints.get(exc.code, "")
        sys.exit("HTTP %s from %s\n%s%s" % (exc.code, url, detail, "\n  -> " + hint if hint else ""))
    except urllib.error.URLError as exc:
        sys.exit(
            "Could not reach %s (%s).\nIf you are on a restricted network, allow "
            "api.higgsfield.ai outbound." % (url, exc.reason)
        )


def submit_and_wait(spec, endpoint, body, auth, label):
    url = spec["api"]["base_url"] + endpoint
    print("[submit] %s" % label)
    resp = request("POST", url, auth, body)
    request_id = resp.get("request_id")
    if not request_id:
        sys.exit("No request_id in response: %s" % json.dumps(resp)[:500])
    print("    request_id %s" % request_id)

    status_url = spec["api"]["base_url"] + spec["api"]["status_path"].format(request_id=request_id)
    deadline = time.time() + POLL_TIMEOUT
    last = None
    while time.time() < deadline:
        result = request("GET", status_url, auth)
        status = result.get("status")
        if status != last:
            print("    status: %s" % status)
            last = status
        if status in TERMINAL:
            result["request_id"] = request_id
            return result
        time.sleep(POLL_INTERVAL)
    sys.exit("Timed out after %ss on request %s" % (POLL_TIMEOUT, request_id))


def download(url, dest):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=300) as resp, \
            open(dest, "wb") as handle:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)


def manifest_path(ad):
    return os.path.join(ROOT, "build", ad, "manifest.json")


def read_manifest(ad):
    path = manifest_path(ad)
    if os.path.exists(path):
        return json.load(open(path))
    return {"ad_id": ad, "video": {}, "audio": {}}


def write_manifest(ad, manifest):
    path = manifest_path(ad)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(manifest, open(path, "w"), indent=2)
    return path


def cost_metadata(result):
    """Capture whatever billing fields the API happens to return.

    Higgsfield's documented response does not promise a cost field, so this
    records what is actually present rather than inventing a number.
    """
    keys = ("credits", "cost", "credits_used", "price", "billing", "usage")
    found = {k: result[k] for k in keys if k in result}
    return found or None


def ffmpeg_bin():
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found. Install it, or: pip install imageio-ffmpeg")


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit("FFmpeg failed:\n%s" % proc.stderr[-4000:])
    return proc


def probe_duration(path):
    proc = subprocess.run([ffmpeg_bin(), "-i", path], capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return None
