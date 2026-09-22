#!/usr/bin/env python3
"""Cut the clips into the finished 20.000s Reel: captioned and clean versions.

Stage 1 trims each clip to its editorial length at 1080x1920 / 24fps.
Stage 2 concatenates them, appends the deterministic end card, lays the
narration over the diegetic bed with ducking, and exports twice - once with
burned-in captions, once clean.

    python3 engine/assemble.py hvac-01
    python3 engine/assemble.py hvac-01 --placeholder   # no API, no spend
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import endcard as endcard_mod


def font_path(brand):
    """First bold TTF that actually exists on this machine."""
    candidates = [os.environ.get("REEL_FONT"), brand["type"]["font"]] + [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    sys.exit(
        "No bold font found on this machine.\n"
        "Point REEL_FONT at one, e.g.\n"
        "  macOS:  export REEL_FONT='/System/Library/Fonts/Supplemental/Arial Bold.ttf'\n"
        "  Linux:  export REEL_FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )


def require_filters(ffmpeg):
    import subprocess
    proc = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True)
    listing = proc.stdout + proc.stderr
    missing = [f for f in ("drawtext", "drawbox", "loudnorm", "sidechaincompress", "gradients")
               if (" %s " % f) not in listing]
    if missing:
        sys.exit("This ffmpeg build is missing: %s\nInstall a full build (apt install ffmpeg)."
                 % ", ".join(missing))


def make_placeholders(ffmpeg, spec, ad):
    clips = common.build_dir(ad, "clips")
    audio = common.build_dir(ad, "audio")
    font = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    for i, shot in enumerate(spec["shots"]):
        shade = 0x14 + i * 0x0E
        common.run([
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=0x%02x%02x%02x:s=1080x1920:d=%d:r=24"
            % (shade, shade, shade + 0x0C, shot["gen_duration"]),
            "-f", "lavfi", "-i", "sine=frequency=%d:duration=%d" % (150 + i * 30, shot["gen_duration"]),
            "-vf", "drawtext=fontfile=%s:text='%s':fontcolor=white:fontsize=48:"
                   "x=(w-tw)/2:y=(h-th)/2" % (font, shot["label"].replace(":", "")),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            os.path.join(clips, shot["id"] + ".mp4"),
        ])
    for line in spec["voiceover"]:
        target = line["end"] - line["start"]
        common.run([
            ffmpeg, "-y", "-f", "lavfi",
            "-i", "sine=frequency=220:duration=%.3f" % target,
            "-af", "volume=0.25", "-ar", "48000", "-ac", "2",
            os.path.join(audio, line["id"] + ".wav"),
        ])
    print("Built %d placeholder clips and %d narration stand-ins"
          % (len(spec["shots"]), len(spec["voiceover"])))


def cut_clips(ffmpeg, spec, ad):
    cut_dir = common.build_dir(ad, "cut")
    clips_dir = os.path.join(common.ROOT, "build", ad, "clips")
    m = spec["master"]
    paths = []
    for shot in spec["shots"]:
        src = os.path.join(clips_dir, shot["id"] + ".mp4")
        if not os.path.exists(src):
            sys.exit("Missing %s\nRun engine/generate.py %s first, or pass --placeholder."
                     % (src, ad))
        available = common.probe_duration(src)
        start, length = shot["trim_start"], shot["edit_duration"]
        if available is not None and start + length > available + 0.05:
            start = max(0.0, available - length)
            print("  ! %s is only %.2fs; trimming from %.2fs" % (shot["id"], available, start))
        dest = os.path.join(cut_dir, shot["id"] + ".mp4")
        vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
              "fps=%d,setsar=1,format=yuv420p"
              % (m["width"], m["height"], m["width"], m["height"], m["fps"]))
        common.run([
            ffmpeg, "-y", "-ss", "%.3f" % start, "-t", "%.3f" % length, "-i", src,
            "-f", "lavfi", "-t", "%.3f" % length,
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-filter_complex",
            "[0:v]%s[v];[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];"
            "[a0][1:a]amix=inputs=2:duration=first:dropout_transition=0:weights=1 0[a]" % vf,
            "-map", "[v]", "-map", "[a]", "-t", "%.3f" % length,
            "-c:v", "libx264", "-preset", "slow", "-crf", "17",
            "-c:a", "aac", "-b:a", "192k", dest,
        ])
        paths.append(dest)
        print("  cut %-28s %.2fs" % (shot["id"], length))
    return paths


def esc(p):
    return p.replace("\\", "/").replace(":", "\\:")


def caption_chain(spec, brand, ad):
    """Captions sit in the upper-middle, clear of Instagram's bottom controls."""
    font = font_path(brand)
    txt_dir = common.build_dir(ad, "text")
    amber = brand["palette"]["amber"].replace("#", "0x")
    clauses = []
    for i, cap in enumerate(spec["captions"]):
        path = os.path.join(txt_dir, "cap%02d.txt" % i)
        open(path, "w").write(cap["text"])
        s, e, fade = cap["start"], cap["end"], 0.22
        alpha = ("if(lt(t,{s}),0,if(lt(t,{s}+{f}),(t-{s})/{f},"
                 "if(lt(t,{e}-{f}),1,if(lt(t,{e}),({e}-t)/{f},0))))").format(s=s, e=e, f=fade)
        clauses.append(
            "drawtext=fontfile='%s':textfile='%s':fontcolor=white:fontsize=%d:"
            "line_spacing=14:x=(w-text_w)/2:y=h*0.30:"
            "borderw=3:bordercolor=black@0.55:"
            "shadowcolor=black@0.8:shadowx=0:shadowy=3:"
            "alpha='%s':enable='between(t,%.2f,%.2f)'"
            % (esc(font), esc(path), cap["size"], alpha, s, e))
    # A hairline amber tick under the feature captions ties them to the brand.
    clauses.append("drawbox=x=(iw-140)/2:y=h*0.30-26:w=140:h=3:color=%s@0.9:t=fill:"
                   "enable='between(t,10.8,14.3)'" % amber)
    return ",".join(clauses)


def assemble(ffmpeg, spec, brand, ad, cuts, captioned):
    m = spec["master"]
    out_dir = common.build_dir(ad, "out")
    out = os.path.join(out_dir, "final_captioned.mp4" if captioned else "final_clean.mp4")

    card = os.path.join(common.ROOT, "build", ad, "endcard.mp4")
    if not os.path.exists(card):
        endcard_mod.build(spec, brand, card)

    concat = os.path.join(common.ROOT, "build", ad, "concat.txt")
    with open(concat, "w") as fh:
        for p in cuts + [card]:
            fh.write("file '%s'\n" % p.replace("'", "'\\''"))

    total = m["total_seconds"]
    vo_lines = [l for l in spec["voiceover"]
                if os.path.exists(os.path.join(common.ROOT, "build", ad, "audio", l["id"] + ".wav"))]

    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat]
    for line in vo_lines:
        cmd += ["-i", os.path.join(common.ROOT, "build", ad, "audio", line["id"] + ".wav")]

    vchain = ["fade=t=in:st=0:d=0.4"]
    if captioned:
        vchain.append(caption_chain(spec, brand, ad))
    graph = ["[0:v]%s,format=yuv420p[v]" % ",".join(vchain)]

    # Narration bus: each fitted line delayed to its exact mark, then summed.
    if vo_lines:
        legs = []
        for i, line in enumerate(vo_lines, start=1):
            graph.append("[%d:a]adelay=%d|%d,apad,atrim=0:%.3f,asetpts=N/SR/TB[vo%d]"
                         % (i, int(line["start"] * 1000), int(line["start"] * 1000), total, i))
            legs.append("[vo%d]" % i)
        if len(legs) > 1:
            graph.append("%samix=inputs=%d:duration=first:normalize=0[vo]" % ("".join(legs), len(legs)))
        else:
            graph.append("%sanull[vo]" % legs[0])
        graph.append("[vo]asplit=2[vo_mix][vo_key]")
        # Diegetic bed ducks under narration; the Spanish exchange in clip 3 sits in
        # a narration gap, so it is never pushed down by this.
        graph.append("[0:a]atrim=0:%.3f,asetpts=N/SR/TB,aresample=48000[bed]" % total)
        graph.append("[bed][vo_key]sidechaincompress=threshold=0.045:ratio=9:attack=12:"
                     "release=260:makeup=1[ducked]")
        graph.append("[ducked][vo_mix]amix=inputs=2:duration=first:normalize=0,"
                     "loudnorm=I=%.1f:TP=-1.5:LRA=11,alimiter=limit=0.95[a]" % m["loudness_lufs"])
    else:
        graph.append("[0:a]atrim=0:%.3f,asetpts=N/SR/TB,"
                     "loudnorm=I=%.1f:TP=-1.5:LRA=11[a]" % (total, m["loudness_lufs"]))

    cmd += [
        "-filter_complex", ";".join(graph),
        "-map", "[v]", "-map", "[a]",
        "-t", "%.3f" % total, "-r", "%d" % m["fps"],
        "-c:v", "libx264", "-preset", "slow", "-crf", "19",
        "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", out,
    ]
    common.run(cmd)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ad", nargs="?", default="hvac-01")
    ap.add_argument("--placeholder", action="store_true")
    args = ap.parse_args()

    spec, brand = common.load(args.ad)
    m = spec["master"]
    footage = sum(s["edit_duration"] for s in spec["shots"])
    if abs(footage - m["footage_seconds"]) > 0.001:
        sys.exit("Shot edit_durations sum to %.3fs, not %.3fs" % (footage, m["footage_seconds"]))
    if abs(footage + m["endcard_seconds"] - m["total_seconds"]) > 0.001:
        sys.exit("footage + end card != total_seconds")

    ffmpeg = common.ffmpeg_bin()
    require_filters(ffmpeg)

    if args.placeholder:
        make_placeholders(ffmpeg, spec, args.ad)

    print("Cutting clips...")
    cuts = cut_clips(ffmpeg, spec, args.ad)
    print("Rendering end card...")
    endcard_mod.build(spec, brand, os.path.join(common.ROOT, "build", args.ad, "endcard.mp4"))

    for captioned in (True, False):
        print("Assembling %s version..." % ("captioned" if captioned else "clean"))
        out = assemble(ffmpeg, spec, brand, args.ad, cuts, captioned)
        print("  %s  %.3fs" % (out, common.probe_duration(out) or -1))


if __name__ == "__main__":
    main()
