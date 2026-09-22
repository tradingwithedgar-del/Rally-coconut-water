#!/usr/bin/env python3
"""Cut the five generated shots into the finished 20.000s vertical Reel.

Stage 1 trims and normalizes each raw clip to 1080x1920 / 30fps / 48kHz.
Stage 2 concatenates them, burns the on-screen copy and the end card, mixes
audio and normalizes loudness for Instagram.

All text in the finished ad is drawn here, locally, by FFmpeg. Nothing legible
is ever asked of the video model, which is why the prompts forbid text outright.

    python3 scripts/assemble.py
    python3 scripts/assemble.py --placeholder   # build from synthetic slates,
                                                # to exercise the pipeline with
                                                # no API calls and no spend
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(ROOT, "shots.json")
RAW_DIR = os.path.join(ROOT, "build", "raw")
CUT_DIR = os.path.join(ROOT, "build", "cut")
TXT_DIR = os.path.join(ROOT, "build", "text")
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(ROOT, "build", "grand-nash-reel-20s.mp4")

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def ffmpeg_bin():
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found. Install it, or: pip install imageio-ffmpeg")


def require_filters(ffmpeg):
    """Some minimal/static builds ship without drawtext, which we depend on."""
    proc = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True)
    listing = proc.stdout + proc.stderr
    missing = [f for f in ("drawtext", "drawbox", "loudnorm") if (" %s " % f) not in listing]
    if missing:
        sys.exit(
            "This ffmpeg build is missing: %s\n"
            "All on-screen text is drawn by ffmpeg, so drawtext is required.\n"
            "Install a full build (apt install ffmpeg / brew install ffmpeg) and make sure\n"
            "it is on PATH ahead of any minimal one." % ", ".join(missing)
        )


def font_path():
    override = os.environ.get("REEL_FONT")
    if override and os.path.exists(override):
        return override
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    sys.exit("No bold TTF found. Set REEL_FONT=/path/to/Font-Bold.ttf")


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit("FFmpeg failed:\n%s\n\n%s" % (" ".join(cmd[:12]) + " ...", proc.stderr[-4000:]))
    return proc


def probe_duration(ffmpeg, path):
    proc = subprocess.run([ffmpeg, "-i", path], capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            hours, minutes, seconds = stamp.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return None


def make_placeholders(ffmpeg, spec):
    """Synthetic stand-ins so the edit can be validated without spending money."""
    os.makedirs(RAW_DIR, exist_ok=True)
    font = font_path()
    for index, shot in enumerate(spec["shots"]):
        dest = os.path.join(RAW_DIR, shot["id"] + ".mp4")
        shade = 0x18 + index * 0x12
        label = shot["label"].replace(":", "\\:").replace("'", "")
        run([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=0x%02x%02x%02x:s=1080x1920:d=5:r=30" % (shade, shade, shade + 0x10),
            "-f", "lavfi", "-i", "sine=frequency=%d:duration=5" % (180 + index * 40),
            "-vf", "drawtext=fontfile=%s:text='%s':fontcolor=white:fontsize=56:"
                   "x=(w-tw)/2:y=(h-th)/2,drawtext=fontfile=%s:text='%%{pts\\:hms}':"
                   "fontcolor=0x888888:fontsize=40:x=(w-tw)/2:y=h*0.6" % (font, label, font),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", dest,
        ])
    print("Built %d placeholder slates in build/raw/" % len(spec["shots"]))


def cut_shots(ffmpeg, spec):
    os.makedirs(CUT_DIR, exist_ok=True)
    master = spec["master"]
    width, height, fps = master["width"], master["height"], master["fps"]
    paths = []

    for shot in spec["shots"]:
        source = os.path.join(RAW_DIR, shot["id"] + ".mp4")
        if not os.path.exists(source):
            sys.exit(
                "Missing %s\nRun scripts/generate.py first, or use --placeholder "
                "to validate the edit without generating." % source
            )
        available = probe_duration(ffmpeg, source)
        start, length = shot["trim_start"], shot["edit_duration"]
        if available is not None and start + length > available + 0.05:
            start = max(0.0, available - length)
            print("  ! %s is only %.2fs; trimming from %.2fs instead" % (shot["id"], available, start))

        dest = os.path.join(CUT_DIR, shot["id"] + ".mp4")
        # Scale-and-crop to fill 9:16 exactly, in case the model returns a near-miss.
        vf = (
            "scale=%d:%d:force_original_aspect_ratio=increase,"
            "crop=%d:%d,fps=%d,setsar=1,format=yuv420p" % (width, height, width, height, fps)
        )
        run([
            ffmpeg, "-y", "-ss", "%.3f" % start, "-t", "%.3f" % length, "-i", source,
            "-f", "lavfi", "-t", "%.3f" % length, "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-filter_complex",
            "[0:v]%s[v];[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];"
            "[a0][1:a]amix=inputs=2:duration=first:dropout_transition=0:weights=1 0[a]" % vf,
            "-map", "[v]", "-map", "[a]",
            "-t", "%.3f" % length,
            "-c:v", "libx264", "-preset", "slow", "-crf", "17",
            "-c:a", "aac", "-b:a", "192k", "-video_track_timescale", "30000",
            dest,
        ])
        paths.append(dest)
        print("  cut %s -> %.2fs" % (shot["id"], length))
    return paths


def esc(path):
    return path.replace("\\", "/").replace(":", "\\:")


def build_text_files(spec):
    """drawtext textfile= avoids the escaping minefield and supports real newlines."""
    os.makedirs(TXT_DIR, exist_ok=True)
    written = []
    for index, overlay in enumerate(spec["overlays"]):
        path = os.path.join(TXT_DIR, "ov%02d.txt" % index)
        with open(path, "w") as handle:
            handle.write(overlay["text"])
        written.append(path)
    card = spec["end_card"]
    for key in ("headline", "subhead", "detail", "kicker"):
        path = os.path.join(TXT_DIR, "card_%s.txt" % key)
        with open(path, "w") as handle:
            handle.write(card[key])
    return written


def drawtext(font, textfile, size, y_expr, color, start, end, fade=0.25):
    """A drawtext clause that fades in and out on alpha."""
    alpha = (
        "if(lt(t,{s}),0,"
        "if(lt(t,{s}+{f}),(t-{s})/{f},"
        "if(lt(t,{e}-{f}),1,"
        "if(lt(t,{e}),({e}-t)/{f},0))))"
    ).format(s=start, e=end, f=fade)
    return (
        "drawtext=fontfile='%s':textfile='%s':fontcolor=%s:fontsize=%d:"
        "line_spacing=14:x=(w-text_w)/2:y=%s:"
        "shadowcolor=black@0.85:shadowx=0:shadowy=4:"
        "box=0:alpha='%s':enable='between(t,%.2f,%.2f)'"
        % (esc(font), esc(textfile), color, size, y_expr, alpha, start, end)
    )


def build_filters(spec, font, overlay_files):
    total = spec["master"]["total_seconds"]
    card = spec["end_card"]
    card_start = card["start"]
    chain = []

    # Open from black, close to black. Cheap, and it makes the cut feel authored.
    chain.append("fade=t=in:st=0:d=0.5")
    chain.append("fade=t=out:st=%.2f:d=0.45" % (total - 0.45))

    # Scrim under the end card so white type stays legible over moving footage.
    chain.append(
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.62:t=fill:"
        "enable='gte(t,%.2f)'" % card_start
    )

    for overlay, path in zip(spec["overlays"], overlay_files):
        chain.append(
            drawtext(font, path, overlay["size"], "h*0.60", "white",
                     overlay["start"], overlay["end"])
        )

    card_end = total - 0.05
    chain.append(drawtext(font, os.path.join(TXT_DIR, "card_kicker.txt"), 40,
                          "h*0.355", "0xC9D6E8", card_start + 0.10, card_end, 0.30))
    chain.append(drawtext(font, os.path.join(TXT_DIR, "card_headline.txt"), 86,
                          "h*0.415", "white", card_start + 0.20, card_end, 0.30))
    chain.append(drawtext(font, os.path.join(TXT_DIR, "card_subhead.txt"), 72,
                          "h*0.505", "0x54C6FF", card_start + 0.45, card_end, 0.30))
    chain.append(drawtext(font, os.path.join(TXT_DIR, "card_detail.txt"), 44,
                          "h*0.600", "white", card_start + 0.75, card_end, 0.30))
    return ",".join(chain)


def assemble(ffmpeg, spec, cuts):
    font = font_path()
    overlay_files = build_text_files(spec)
    total = spec["master"]["total_seconds"]
    lufs = spec["master"]["loudness_lufs"]

    concat_list = os.path.join(ROOT, "build", "concat.txt")
    with open(concat_list, "w") as handle:
        for path in cuts:
            handle.write("file '%s'\n" % path.replace("'", "'\\''"))

    music = next((p for p in (os.path.join(ASSETS, "music.mp3"), os.path.join(ASSETS, "music.wav"))
                  if os.path.exists(p)), None)
    vo = next((p for p in (os.path.join(ASSETS, "vo.wav"), os.path.join(ASSETS, "vo.mp3"))
               if os.path.exists(p)), None)

    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_list]
    inputs = 1
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
        music_idx = inputs
        inputs += 1
        print("  mixing music bed: %s" % os.path.basename(music))
    if vo:
        cmd += ["-i", vo]
        vo_idx = inputs
        inputs += 1
        print("  mixing voiceover: %s" % os.path.basename(vo))

    graph = ["[0:v]%s[v]" % build_filters(spec, font, overlay_files)]

    # Diegetic sound from the shots carries the film; anything else sits under it.
    graph.append("[0:a]atrim=0:%.3f,asetpts=N/SR/TB,volume=1.0[dia]" % total)
    legs = ["[dia]"]
    if music:
        graph.append(
            "[%d:a]atrim=0:%.3f,asetpts=N/SR/TB,volume=0.22,"
            "afade=t=in:st=0:d=1.0,afade=t=out:st=%.2f:d=1.2[bed]" % (music_idx, total, total - 1.2)
        )
        legs.append("[bed]")
    if vo:
        graph.append("[%d:a]atrim=0:%.3f,asetpts=N/SR/TB,volume=1.4[vox]" % (vo_idx, total))
        legs.append("[vox]")

    if len(legs) == 1:
        graph.append("[dia]loudnorm=I=%.1f:TP=-1.5:LRA=11,alimiter=limit=0.95[a]" % lufs)
    else:
        graph.append(
            "%samix=inputs=%d:duration=first:normalize=0,"
            "loudnorm=I=%.1f:TP=-1.5:LRA=11,alimiter=limit=0.95[a]"
            % ("".join(legs), len(legs), lufs)
        )

    cmd += [
        "-filter_complex", ";".join(graph),
        "-map", "[v]", "-map", "[a]",
        "-t", "%.3f" % total,
        "-r", "%d" % spec["master"]["fps"],
        "-c:v", "libx264", "-preset", "slow", "-crf", "19",
        "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p",
        "-x264-params", "keyint=60:min-keyint=60:scenecut=0",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        OUT,
    ]
    run(cmd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--placeholder", action="store_true",
                        help="synthesize stand-in clips instead of using generated footage")
    args = parser.parse_args()

    with open(SPEC_PATH) as handle:
        spec = json.load(handle)

    planned = sum(s["edit_duration"] for s in spec["shots"])
    if abs(planned - spec["master"]["total_seconds"]) > 0.001:
        sys.exit("shots.json edit_durations sum to %.3fs, not %.3fs"
                 % (planned, spec["master"]["total_seconds"]))

    ffmpeg = ffmpeg_bin()
    require_filters(ffmpeg)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)

    if args.placeholder:
        make_placeholders(ffmpeg, spec)

    print("Cutting shots...")
    cuts = cut_shots(ffmpeg, spec)
    print("Assembling master...")
    assemble(ffmpeg, spec, cuts)

    actual = probe_duration(ffmpeg, OUT)
    print("\nDone: %s" % OUT)
    print("Runtime: %.3fs (target %.3fs)" % (actual or -1, spec["master"]["total_seconds"]))
    print("Size: %.1f MB" % (os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
