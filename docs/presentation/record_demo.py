"""Record the live LinuxONE dashboard as a frame sequence, timed to the demo dialogue.

Saves build/demo_frames/%05d.jpg (30 fps) plus build/demo.json with segment start frames and
bounding boxes of the elements the overlays point at.
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
TL = json.loads((BUILD / "timeline.json").read_text())
W, H, FPS = 1440, 810, 30
demo = [ln for ln in TL["lines"] if ln["scene"] == "demo"]


def span(a, b):
    """Seconds from the start of demo line a to the start of line b (or the demo scene end)."""
    end = demo[b]["start"] if b < len(demo) else next(s for s in TL["scenes"] if s["id"] == "demo")["end"]
    return end - demo[a]["start"]


SEGMENTS = {"live": span(1, 3), "investigate": span(3, 5), "priya": span(5, 6), "rahul": span(6, 7), "rings": span(7, 8)}


def main():
    out = BUILD / "demo_frames"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    meta = {"segments": {}, "boxes": {}, "ts": []}
    frame_no = [0]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, color_scheme="dark")
        page.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        start_btn = page.get_by_role("button", name=re.compile("Start feed"))
        start_btn.wait_for(timeout=90_000)
        page.wait_for_timeout(4000)

        clock = {"t": time.time()}

        def snap_until(t_end):
            """Capture frames at 30 fps (real time) until t_end seconds after segment start."""
            while time.time() - clock["t"] < t_end:
                target = clock["t"] + (frame_no[0] - clock["f0"]) / FPS
                meta["ts"].append(round(time.time() - clock["t"], 4))
                page.screenshot(path=str(out / f"{frame_no[0]:05d}.jpg"), type="jpeg", quality=88)
                frame_no[0] += 1
                lag = target - time.time()
                if lag > 0:
                    time.sleep(lag)

        def begin(name):
            clock["t"] = time.time()
            clock["f0"] = frame_no[0]
            meta["segments"][name] = {"frame": frame_no[0], "seconds": SEGMENTS[name]}

        def box(key, locator):
            b = locator.first.bounding_box()
            meta["boxes"][key] = {k: round(v, 1) for k, v in b.items()} if b else None

        def to(locator, block="start"):
            locator.first.evaluate("e => e.scrollIntoView({behavior: 'instant', block: '%s'})" % block)

        def act(fn, until):
            fn()
            snap_until(until)

        # --- live feed: show s390x, then streaming + latency
        begin("live")
        start_btn.click()
        try:
            page.get_by_role("button", name=re.compile("Pause")).wait_for(timeout=4000)
        except Exception:
            start_btn.click()
        box("s390x", page.get_by_text("s390x", exact=True))
        box("kpis", page.locator('[data-testid="stMetric"]').nth(0))
        box("latency", page.locator('[data-testid="stMetric"]').nth(4))
        snap_until(SEGMENTS["live"])
        page.get_by_role("button", name=re.compile("Pause")).click()

        # --- investigate a red claim
        begin("investigate")
        page.get_by_role("tab", name=re.compile("Investigate")).click()
        page.wait_for_timeout(600)
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.wait_for_timeout(300)
        page.get_by_role("option", name=re.compile("🔴")).first.click()
        snap_until(1.8)
        to(page.get_by_text("Why this score"), "start")
        page.wait_for_timeout(300)
        box("reasons", page.locator(".reason-risk").first)
        box("gauge", page.locator(".js-plotly-plot").locator("visible=true").first)
        reasons_bottom = page.locator(".reason-risk").last.bounding_box()
        first = page.locator(".reason-risk").first.bounding_box()
        if first and reasons_bottom:
            meta["boxes"]["reasons_all"] = {"x": first["x"], "y": first["y"], "width": first["width"],
                                            "height": reasons_bottom["y"] + reasons_bottom["height"] - first["y"]}
        snap_until(demo[4]["start"] - demo[3]["start"])
        page.get_by_role("button", name=re.compile("Generate investigator note")).click()
        page.wait_for_timeout(400)
        to(page.get_by_text(re.compile("^Source:")), "center")
        page.wait_for_timeout(300)
        box("note", page.locator('[data-testid="stAlert"]').first)
        meta["note_at"] = demo[4]["start"] - demo[3]["start"]
        snap_until(SEGMENTS["investigate"])

        # --- Priya
        begin("priya")
        to(page.get_by_role("tablist"), "center")
        page.get_by_role("tab", name=re.compile("File a claim")).click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name=re.compile("Submit claim")).click()
        page.wait_for_timeout(900)
        to(page.get_by_text("Investigator note", exact=True), "center")
        page.wait_for_timeout(300)
        box("priya_banner", page.locator(".banner").locator("visible=true").last)
        box("priya_gauge", page.locator(".js-plotly-plot").locator("visible=true").first)
        snap_until(SEGMENTS["priya"])

        # --- Rahul
        begin("rahul")
        to(page.get_by_role("tablist"), "center")
        page.get_by_text(re.compile("Rahul: 'total loss'")).click()
        page.wait_for_timeout(900)
        page.get_by_role("button", name=re.compile("Submit claim")).click()
        page.wait_for_timeout(900)
        to(page.get_by_text("Investigator note", exact=True), "center")
        page.wait_for_timeout(300)
        box("rahul_banner", page.locator(".banner").locator("visible=true").last)
        box("rahul_msg", page.get_by_text(re.compile("standard verification")).locator("visible=true"))
        snap_until(SEGMENTS["rahul"])

        # --- fraud rings
        begin("rings")
        to(page.get_by_role("tablist"), "center")
        page.get_by_role("tab", name=re.compile("Fraud rings")).click()
        page.wait_for_timeout(2500)
        to(page.get_by_text("Visualise network"), "start")
        page.wait_for_timeout(400)
        box("graph", page.locator(".js-plotly-plot").locator("visible=true").last)
        snap_until(SEGMENTS["rings"])
        browser.close()

    meta["frames"] = frame_no[0]
    (BUILD / "demo.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
