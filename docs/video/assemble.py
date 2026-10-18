"""Assemble slides + demo footage + narration into 1080p MP4s (full and <=3:00 cut)."""
import json
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import pypdfium2

from script import CUTS, SCENES

HERE = Path(__file__).parent
BUILD = HERE / "build"
FF = imageio_ffmpeg.get_ffmpeg_exe()
DUR = json.loads((BUILD / "durations.json").read_text())
MARKS = json.loads((BUILD / "marks.json").read_text())
VISUAL = {sid: vis for sid, vis, _ in SCENES}
PAD = 0.6
FPS = 30
VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
AENC = ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def run(args):
    subprocess.run([FF, "-y", "-loglevel", "error", *args], check=True)


def render_slides():
    out = BUILD / "slides"
    out.mkdir(exist_ok=True)
    pdf = pypdfium2.PdfDocument(str(HERE.parent / "ClaimGuard_Pitch_Deck.pdf"))
    for i in range(len(pdf)):
        pdf[i].render(scale=1.5).to_pil().convert("RGB").save(out / f"{i}.png")  # 1280x720 pt -> 1920x1080
    return out


def segment(cut, sid, slides):
    d = DUR[cut][sid] + PAD
    audio = BUILD / "audio" / f"{cut}_{sid}.wav"
    out = BUILD / "seg" / f"{cut}_{sid}.mp4"
    out.parent.mkdir(exist_ok=True)
    fade = f"fade=t=in:st=0:d=0.35,fade=t=out:st={d - 0.35:.2f}:d=0.35"
    kind, ref = VISUAL[sid]
    if kind == "slide":
        frames = int(d * FPS)
        # Gentle push-in so slides don't feel static.
        vf = (f"scale=3840:-1,zoompan=z='min(zoom+0.00025,1.06)':d={frames}:"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS},{fade}")
        video_in = ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.2f}", "-i", str(slides / f"{ref}.png")]
    else:
        vf = f"fps={FPS},scale=1920:1080:flags=lanczos,{fade}"
        video_in = ["-ss", f"{MARKS[sid]:.2f}", "-t", f"{d:.2f}", "-i", str(BUILD / "demo.webm")]
    run([*video_in, "-i", str(audio), "-filter_complex",
         f"[0:v]{vf}[v];[1:a]apad,atrim=0:{d:.2f},afade=t=out:st={d - 0.25:.2f}:d=0.25[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{d:.2f}", *VENC, *AENC, str(out)])
    return out


def main(cuts):
    slides = render_slides()
    for cut in cuts:
        segs = [segment(cut, sid, slides) for sid in CUTS[cut]["scenes"]]
        listing = BUILD / f"{cut}_list.txt"
        listing.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
        name = {"full": "ClaimGuard_Demo_Full.mp4", "short": "ClaimGuard_Demo_3min.mp4"}[cut]
        run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart",
             str(HERE / name)])
        print("wrote", name)


if __name__ == "__main__":
    main(sys.argv[1:] or list(CUTS))
