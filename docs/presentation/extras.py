"""Render the YouTube thumbnail (PNG) and the flyer (PNG + PDF) from extras.html."""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent

with sync_playwright() as p:
    b = p.chromium.launch(args=["--allow-file-access-from-files"])
    page = b.new_page(viewport={"width": 1280, "height": 720})
    page.goto((HERE / "extras.html").as_uri(), wait_until="networkidle")
    page.evaluate("window.ready")
    page.locator("#thumb").screenshot(path=str(HERE / "ClaimGuard_Thumbnail.png"))
    page.set_viewport_size({"width": 1240, "height": 1754})
    page.locator("#flyer").screenshot(path=str(HERE / "ClaimGuard_Flyer.png"))
    page.evaluate("document.getElementById('thumb').style.display='none'")
    page.pdf(path=str(HERE / "ClaimGuard_Flyer.pdf"), width="1240px", height="1754px", print_background=True,
             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("ok")
