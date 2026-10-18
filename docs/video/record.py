"""Record the live LinuxONE dashboard, one continuous take timed to the narration.

Writes build/demo.webm and build/marks.json (scene start offsets in the recording).
"""
import json
import re
import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from script import URL

HERE = Path(__file__).parent
BUILD = HERE / "build"
DUR = json.loads((BUILD / "durations.json").read_text())["full"]
W, H = 1440, 810
PAD = 0.6


def main():
    tmp = BUILD / "rec"
    shutil.rmtree(tmp, ignore_errors=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(tmp),
                                  record_video_size={"width": W, "height": H}, color_scheme="dark")
        t0 = time.time()
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        start_btn = page.get_by_role("button", name=re.compile("Start feed"))
        start_btn.wait_for(timeout=90_000)
        page.wait_for_timeout(4000)
        marks = {}

        def scene(name):
            marks[name] = time.time() - t0
            return marks[name]

        def hold(name):
            remaining = marks[name] + DUR[name] + PAD - (time.time() - t0)
            if remaining > 0:
                page.wait_for_timeout(int(remaining * 1000))

        def to(locator, block="start"):
            locator.first.evaluate("e => e.scrollIntoView({behavior: 'smooth', block: '%s'})" % block)
            page.wait_for_timeout(1200)

        def top():
            to(page.get_by_role("tablist"), "center")

        def tab(label):
            page.get_by_role("tab", name=re.compile(label)).click()
            page.wait_for_timeout(1500)

        # --- live feed
        scene("live")
        start_btn.click()
        try:
            page.get_by_role("button", name=re.compile("Pause")).wait_for(timeout=5000)
        except Exception:
            start_btn.click()
        hold("live")
        page.get_by_role("button", name=re.compile("Pause")).click()
        page.wait_for_timeout(800)

        # --- investigate a red (investigate-lane) claim
        scene("investigate")
        tab("Investigate")
        page.wait_for_timeout(1500)
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.wait_for_timeout(800)
        page.get_by_role("option", name=re.compile("🔴")).first.click()
        page.wait_for_timeout(4000)
        to(page.get_by_text("Why this score"), "start")
        page.wait_for_timeout(3500)
        page.get_by_role("button", name=re.compile("Generate investigator note")).click()
        page.wait_for_timeout(1000)
        to(page.get_by_text(re.compile("^Source:")), "center")
        hold("investigate")

        # --- file two claims: Priya then Rahul
        top()
        scene("file")
        tab("File a claim")
        page.wait_for_timeout(1200)
        page.get_by_role("button", name=re.compile("Submit claim")).click()
        page.wait_for_timeout(1200)
        to(page.get_by_text("Investigator note", exact=True), "center")
        page.wait_for_timeout(int(DUR["file"] * 0.30 * 1000))
        top()
        page.get_by_text(re.compile("Rahul: 'total loss'")).click()
        page.wait_for_timeout(1500)
        page.get_by_role("button", name=re.compile("Submit claim")).click()
        page.wait_for_timeout(1200)
        to(page.get_by_text("Investigator note", exact=True), "center")
        hold("file")

        # --- fraud rings
        top()
        scene("rings")
        tab("Fraud rings")
        page.wait_for_timeout(3500)
        to(page.get_by_text("Visualise network"), "start")
        hold("rings")

        # --- model and IBM Z
        top()
        scene("model")
        tab("Model & IBM Z")
        page.wait_for_timeout(int(DUR["model"] * 0.5 * 1000))
        to(page.get_by_text("Running on IBM Z"), "start")
        hold("model")

        video = page.video
        ctx.close()
        browser.close()
        out = BUILD / "demo.webm"
        Path(video.path()).replace(out)
    (BUILD / "marks.json").write_text(json.dumps(marks, indent=1))
    print("recorded", out, marks)


if __name__ == "__main__":
    main()
