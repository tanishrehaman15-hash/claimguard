"""Re-render frames [A, B) and splice them into the finished video (used for small fixes)."""
import subprocess
import sys

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

from render import BUILD, FPS, HERE, open_page, write_data

FF = imageio_ffmpeg.get_ffmpeg_exe()
A, B = int(sys.argv[1]), int(sys.argv[2])
write_data()
patch = BUILD / "patch.mp4"
enc = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuvj420p", "-r", str(FPS), str(patch)],
                       stdin=subprocess.PIPE)
with sync_playwright() as p:
    browser, page = open_page(p)
    for f in range(A - 60, A):          # warm up so counters/animations are in the right state
        page.evaluate("t => window.render(t)", f / FPS)
    for f in range(A, B):
        page.evaluate("t => window.render(t)", f / FPS)
        enc.stdin.write(page.screenshot(type="jpeg", quality=93))
    browser.close()
enc.stdin.close(); enc.wait()

src, out = BUILD / "video_silent.mp4", HERE / "ClaimGuard_Presentation_3min.mp4"
fixed = BUILD / "video_fixed.mp4"
fc = (f"[0:v]trim=start_frame=0:end_frame={A},setpts=PTS-STARTPTS[a];"
      f"[1:v]setpts=PTS-STARTPTS[p];"
      f"[0:v]trim=start_frame={B},setpts=PTS-STARTPTS[b];[a][p][b]concat=n=3:v=1:a=0[v]")
subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(src), "-i", str(patch), "-filter_complex", fc, "-map", "[v]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), str(fixed)], check=True)
fixed.replace(src)
subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(src), "-i", str(BUILD / "mix.wav"), "-c:v", "copy", "-c:a", "aac",
                "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
print("patched", A, B)
