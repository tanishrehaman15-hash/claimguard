"""Render stage.html frame by frame (deterministic), mux with the audio mix, and write subtitles.

    python render.py            # full video
    python render.py --stills 5 40 100   # preview PNGs at given seconds
"""
import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

from script import TEAM, URL

HERE = Path(__file__).parent
BUILD = HERE / "build"
FF = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
TL = json.loads((BUILD / "timeline.json").read_text())


def write_data():
    demo = json.loads((BUILD / "demo.json").read_text())
    (BUILD / "data.js").write_text(
        f"window.TL={json.dumps(TL)};window.DEMO={json.dumps(demo)};window.TEAM={json.dumps(TEAM)};window.URL={json.dumps(URL)};")


def srt():
    def ts(x):
        h, r = divmod(x, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"
    out = []
    for k, ln in enumerate(TL["lines"], 1):
        out.append(f"{k}\n{ts(ln['start'])} --> {ts(ln['end'] + 0.15)}\n{ln['text']}\n")
    (HERE / "ClaimGuard_Presentation.srt").write_text("\n".join(out), encoding="utf-8")


def open_page(p):
    browser = p.chromium.launch(args=["--allow-file-access-from-files", "--force-color-profile=srgb"])
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    page.goto((HERE / "stage.html").as_uri(), wait_until="networkidle")
    page.evaluate("window.ready")
    page.wait_for_timeout(800)
    return browser, page


def stills(times):
    write_data()
    with sync_playwright() as p:
        browser, page = open_page(p)
        for t in times:
            for k in range(int(t * FPS) + 1):  # seek forward frame by frame so callbacks/counters settle
                if k % 15 == 0 or k == int(t * FPS):
                    page.evaluate("t => window.render(t)", k / FPS)
            page.screenshot(path=str(BUILD / f"still_{t:06.2f}.png"))
            print("still", t)
        browser.close()


def full():
    write_data()
    srt()
    n = int(TL["duration"] * FPS)
    silent = BUILD / "video_silent.mp4"
    enc = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg",
                            "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-r", str(FPS), str(silent)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        browser, page = open_page(p)
        for f in range(n):
            page.evaluate("t => window.render(t)", f / FPS)
            enc.stdin.write(page.screenshot(type="jpeg", quality=93))
            if f % 300 == 0:
                print(f"frame {f}/{n}", flush=True)
        browser.close()
    enc.stdin.close()
    enc.wait()
    out = HERE / "ClaimGuard_Presentation_3min.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(BUILD / "mix.wav"), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", nargs="*", type=float)
    a = ap.parse_args()
    stills(a.stills) if a.stills else full()
