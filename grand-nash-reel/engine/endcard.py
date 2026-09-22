#!/usr/bin/env python3
"""Render the deterministic 3-second branded end card.

Built entirely with FFmpeg from brand/brand.json and the ad's end_card block.
No model touches this, which is the only way the phone number and URL are
guaranteed correct.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ffmpeg_bin():
    import shutil
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


def esc(path):
    return path.replace("\\", "/").replace(":", "\\:")


def font_path(brand):
    override = os.environ.get("REEL_FONT")
    candidates = [override, brand["type"]["font"],
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    sys.exit("No bold TTF found. Set REEL_FONT=/path/to/Font-Bold.ttf")


def text_clause(font, textfile, size, y, color, spacing=0, alpha=1.0):
    return (
        "drawtext=fontfile='%s':textfile='%s':fontcolor=%s@%.2f:fontsize=%d:"
        "line_spacing=16:x=(w-text_w)/2:y=%s" % (esc(font), esc(textfile), color, alpha, size, y)
    )


def build(spec, brand, out_path, seconds=None, fps=None):
    ffmpeg = ffmpeg_bin()
    font = font_path(brand)
    card = spec["end_card"]
    pal = brand["palette"]
    logo = brand["logo"]
    seconds = seconds or spec["master"]["endcard_seconds"]
    fps = fps or spec["master"]["fps"]
    width = spec["master"]["width"]
    height = spec["master"]["height"]

    txt_dir = os.path.join(ROOT, "build", spec["ad_id"], "text")
    os.makedirs(txt_dir, exist_ok=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines = {
        "brand": brand["name"].upper(),
        "headline": card["headline_wrapped"],
        "sub1": card["sub1"],
        "sub2": card["sub2"],
        "cta": card["cta_wrapped"],
        "detail": "%s   |   %s" % (brand["website"], brand["phone"]),
    }
    paths = {}
    for key, value in lines.items():
        path = os.path.join(txt_dir, "card_%s.txt" % key)
        with open(path, "w") as handle:
            handle.write(value)
        paths[key] = path

    logo_path = os.path.join(ROOT, logo["path"])
    if not os.path.exists(logo_path):
        sys.exit("Logo not found at %s (brand.json -> logo.path)" % logo_path)

    bg = pal["background"].replace("#", "0x")
    amber = pal["amber"].replace("#", "0x")
    offwhite = pal["offwhite"].replace("#", "0x")
    grey = pal["grey"].replace("#", "0x")

    logo_top = int(height * 0.200)
    graph = [
        "[0:v]format=rgba[flat]",
        "[2:v]scale=%d:-1[logo]" % logo["width_px"],
        "[flat][logo]overlay=x=(W-w)/2:y=%d[plated]" % logo_top,
    ]
    # The warm drift is screened over the FINISHED plate, not painted behind it.
    # A baked-in logo background then receives the identical wash as the card, so
    # the mark has no visible edge. This is what makes an opaque JPEG usable here.
    # Both legs must be forced to the same RGB layout before blending, or the
    # gradient is read as YUV and the whole card picks up a magenta cast.
    graph.append("[1:v]format=gbrp[grad]")
    graph.append("[plated]format=gbrp[plate]")
    graph.append("[plate][grad]blend=all_mode=screen:all_opacity=0.10[washed]")

    chain = []
    chain.append("drawbox=x=(iw-320)/2:y=%d:w=320:h=3:color=%s@0.85:t=fill"
                 % (int(height * 0.497), amber))
    chain.append(text_clause(font, paths["brand"], 36, "h*0.452", offwhite, alpha=0.80))
    chain.append(text_clause(font, paths["headline"], 54, "h*0.527", offwhite))
    chain.append(text_clause(font, paths["sub1"], 36, "h*0.629", grey))
    chain.append(text_clause(font, paths["sub2"], 36, "h*0.667", amber))
    chain.append(text_clause(font, paths["cta"], 48, "h*0.724", offwhite))
    chain.append(text_clause(font, paths["detail"], 38, "h*0.822", amber, alpha=0.95))
    chain.append("fade=t=in:st=0:d=0.35")
    graph.append("[washed]%s,format=yuv420p[v]" % ",".join(chain))

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-t", "%.3f" % seconds,
        "-i", "color=c=%s:s=%dx%d:r=%d" % (bg, width, height, fps),
        "-f", "lavfi", "-i",
        "gradients=s=%dx%d:c0=%s:c1=%s:type=radial:speed=0.012:d=%.3f:r=%d"
        % (width, height, "0x2A2112", "0x000000", seconds, fps),
        "-loop", "1", "-t", "%.3f" % seconds, "-i", logo_path,
        "-f", "lavfi", "-t", "%.3f" % seconds,
        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex", ";".join(graph),
        "-map", "[v]", "-map", "3:a",
        "-t", "%.3f" % seconds, "-r", "%d" % fps,
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        out_path,
    ]
    run(cmd)
    return out_path


def main():
    ad = sys.argv[1] if len(sys.argv) > 1 else "hvac-01"
    spec = json.load(open(os.path.join(ROOT, "ads", ad, "spec.json")))
    brand = json.load(open(os.path.join(ROOT, "brand", "brand.json")))
    out = os.path.join(ROOT, "build", ad, "endcard.mp4")
    build(spec, brand, out)
    print("Wrote %s" % out)


if __name__ == "__main__":
    main()
