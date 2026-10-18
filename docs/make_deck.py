"""Build docs/ClaimGuard_Pitch_Deck.pdf from artifacts/metadata.json (pip install reportlab)."""
import json
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT / "artifacts" / "metadata.json").read_text())
T, B = M["test_metrics"], M["rules_baseline"]
TEAM = "Team <your team name>"
REPO = "github.com/<you>/claimguard"
DEMO = "change-illustrations-tooth-complete.trycloudflare.com"
# Placeholders (containing "<") are left off the slides until filled in.
CREDIT = "  |  ".join(x for x in (TEAM, REPO) if "<" not in x)

W, H = 1280, 720
INK, MUTED, BLUE, RED, GREEN, AMBER = (HexColor(c) for c in ("#161616", "#525252", "#0f62fe", "#d64545", "#2e9e5b", "#e0a100"))
BG, PANEL = HexColor("#ffffff"), HexColor("#f2f4f8")

c = canvas.Canvas(str(ROOT / "docs" / "ClaimGuard_Pitch_Deck.pdf"), pagesize=(W, H))
page = [0]


def text(x, y, s, size=22, color=INK, font="Helvetica", anchor="l"):
    c.setFont(font, size)
    c.setFillColor(color)
    {"l": c.drawString, "c": c.drawCentredString, "r": c.drawRightString}[anchor](x, y, s)


def para(x, y, lines, size=22, color=INK, lead=1.45, font="Helvetica"):
    for i, ln in enumerate(lines):
        text(x, y - i * size * lead, ln, size, color, font)


def bullets(x, y, items, size=22, color=INK, gap=1.7, dot=BLUE):
    for i, it in enumerate(items):
        yy = y - i * size * gap
        c.setFillColor(dot)
        c.circle(x + 6, yy + size * 0.32, 5, stroke=0, fill=1)
        text(x + 24, yy, it, size, color)


def box(x, y, w, h, fill=PANEL, stroke=None, r=14):
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(2)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke else 0, fill=1)


def arrow(x1, y1, x2, y2, color=MUTED):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(2.5)
    p = c.beginPath()
    if x1 == x2:  # vertical, pointing down
        c.line(x1, y1, x2, y2 + 10)
        p.moveTo(x2, y2)
        p.lineTo(x2 - 7, y2 + 14)
        p.lineTo(x2 + 7, y2 + 14)
    else:
        c.line(x1, y1, x2 - 10, y2)
        p.moveTo(x2, y2)
        p.lineTo(x2 - 14, y2 + 7)
        p.lineTo(x2 - 14, y2 - 7)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def slide(title, kicker=None):
    if page[0]:
        c.showPage()
    page[0] += 1
    c.setFillColor(BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(BLUE)
    c.rect(0, H - 8, W, 8, stroke=0, fill=1)
    if kicker:
        text(70, H - 70, kicker.upper(), 15, BLUE, "Helvetica-Bold")
    text(70, H - 118, title, 40, INK, "Helvetica-Bold")
    text(W - 70, 30, f"ClaimGuard  |  IBM Z Datathon 2026  |  {page[0]}", 13, MUTED, anchor="r")


def stat(x, y, w, value, label, color=BLUE):
    box(x, y, w, 150)
    text(x + w / 2, y + 72, value, 50, color, "Helvetica-Bold", "c")
    text(x + w / 2, y + 30, label, 17, MUTED, anchor="c")


def image(path, x, y, w):
    img = ImageReader(str(path))
    iw, ih = img.getSize()
    h = w * ih / iw
    c.drawImage(img, x, y, w, h)
    c.setStrokeColor(HexColor("#d0d0d0"))
    c.rect(x, y, w, h, stroke=1, fill=0)
    return h


# 1 Title
page[0] += 1
c.setFillColor(HexColor("#0b1d3a"))
c.rect(0, 0, W, H, stroke=0, fill=1)
c.setFillColor(BLUE)
c.rect(0, 0, 18, H, stroke=0, fill=1)
text(90, 470, "ClaimGuard", 92, white, "Helvetica-Bold")
text(90, 400, "Pay honest claims in hours. Stop fraud before payout.", 34, HexColor("#c6d4ff"))
text(90, 330, "Real-time AI risk scoring for insurance claims, inside the transaction on IBM Z", 24, HexColor("#a8b3c7"))
text(90, 230, f"Live on IBM LinuxONE:  {DEMO}", 22, HexColor("#78a9ff"), "Helvetica-Bold")
text(90, 150, "IBM Z Datathon 2026  |  Theme 1: Real-time AI on Transactional Data", 20, HexColor("#a8b3c7"))
if CREDIT:
    text(90, 115, CREDIT, 20, HexColor("#a8b3c7"))

# 2 Problem
slide("Fraud and slow payouts hurt everyone", "The problem")
box(70, 230, 540, 330, HexColor("#eaf6ef"))
text(100, 515, "Priya: honest", 28, GREEN, "Helvetica-Bold")
para(100, 470, ["Minor accident, Rs 18,000 repair.", "Waits ~2 weeks while her claim", "is checked by hand like everyone else's."], 22)
box(670, 230, 540, 330, HexColor("#fbecec"))
text(700, 515, "Rahul: suspicious", 28, RED, "Helvetica-Bold")
para(700, 470, ["Rs 2.4 lakh 'total loss' on a 9-day-old", "policy, no police report, same garage", "as 7 linked customers."], 22)
para(70, 175, ["Manual checks are slow and miss organised rings; red-flag rules raise false alarms.",
               "Fraud losses become higher premiums, and honest customers pay twice: in money and in waiting."], 22, MUTED)

# 3 Solution
slide("Score every claim the instant it is filed", "Our solution")
lanes = [(GREEN, "Fast-track payout", f"{T['fast_track_rate']:.0%} of claims", "paid with zero manual work"),
         (AMBER, "Quick document check", f"{T['review_rate']:.0%} of claims", "one extra upload in the app"),
         (RED, "Send to investigator", f"{T['investigate_rate']:.0%} of claims", f"{T['investigate_precision']:.0%} hit-rate, payout held")]
for i, (col, name, share, sub) in enumerate(lanes):
    x = 70 + i * 390
    box(x, 250, 360, 290)
    c.setFillColor(col)
    c.roundRect(x, 500, 360, 40, 14, stroke=0, fill=1)
    text(x + 24, 368 + 100, name, 26, INK, "Helvetica-Bold")
    text(x + 24, 390, share, 44, col, "Helvetica-Bold")
    text(x + 24, 345, sub, 20, MUTED)
para(70, 190, ["Every decision ships with exact reason codes (TreeSHAP) and an IBM Granite-written note.",
               "No claim is ever rejected by a machine: humans decide every high-risk case."], 22, MUTED)

# 4 Architecture
slide("How it works: AI inside the claims transaction", "Architecture")
steps = [("Claim filed", "app / agent / branch"), ("Claims system", "CICS / COBOL on IBM Z"),
         ("Feature store", "identity graph +\n30-day windows (Db2)"), ("AI model", "MLz / Snap ML on\nTelum AI accelerator"),
         ("Decision", "fast-track / check /\ninvestigate")]
for i, (t1, t2) in enumerate(steps):
    x = 60 + i * 238
    box(x, 400, 205, 150, HexColor("#e5edff") if i in (2, 3) else PANEL, BLUE if i == 3 else None)
    text(x + 102, 505, t1, 23, INK, "Helvetica-Bold", "c")
    for j, ln in enumerate(t2.split("\n")):
        text(x + 102, 465 - j * 24, ln, 17, MUTED, anchor="c")
    if i < 4:
        arrow(x + 207, 475, x + 236, 475)
box(536, 200, 440, 130, HexColor("#fff6e0"))
text(756, 285, "TreeSHAP reason codes -> IBM Granite", 21, INK, "Helvetica-Bold", "c")
text(756, 250, "investigator note + neutral customer message", 18, MUTED, anchor="c")
text(756, 225, "(LinuxONE, Secure Execution, async)", 16, MUTED, anchor="c")
arrow(774, 398, 774, 332)
bullets(70, 300, ["26 real-time features", "~0.2 ms model latency", "Same code for training and serving: no leakage"], 19)

# 5 Demo
slide("Live demo: scoring a stream of claims", "Prototype")
h = image(ROOT / "docs/img/live.jpg", 70, 150, 560)
image(ROOT / "docs/img/investigate.jpg", 650, 150, 560)
text(70, 125, "Live feed: every claim scored in ~0.2 ms, routed to a lane", 18, MUTED)
text(650, 125, "Investigator view: exact reason codes for each flagged claim", 18, MUTED)

# 6 Rings
slide("Seeing what rules cannot: fraud rings", "Graph intelligence")
image(ROOT / "docs/img/rings.jpg", 60, 140, 640)
bullets(740, 520, ["Linked by shared phones / accounts", "Claims funnelled to one garage", "Same agent, late-night incidents",
                   "Graph updates in real time"], 21, gap=1.9)
text(740, 220, "Rings caught before payout:", 22, INK, "Helvetica-Bold")
text(740, 165, f"{M['recall_by_fraud_type'].get('staged_ring', 0):.0%}", 60, RED, "Helvetica-Bold")

# 7 Results
slide(f"Results on the {T['claims']:,} most recent claims (time hold-out)", "Impact, measured")
stat(70, 400, 260, f"{T['fraud_value_stopped_share']:.0%}", "fraud value stopped", RED)
stat(355, 400, 260, f"{T['fast_track_rate']:.0%}", "claims paid instantly", GREEN)
stat(640, 400, 260, f"{T['roc_auc']:.2f}", "ROC-AUC", BLUE)
stat(925, 400, 285, f"{T['investigate_precision']:.0%}", "investigator hit-rate", BLUE)
text(70, 340, f"Same alert volume ({B['alerts']:,} alerts): share of fraud caught", 22, INK, "Helvetica-Bold")
for i, (name, v, col) in enumerate([("Red-flag rules", B["rules_recall"], HexColor("#a0a0a0")), ("ClaimGuard AI", B["model_recall"], BLUE)]):
    y = 270 - i * 70
    text(70, y + 12, name, 20, MUTED)
    c.setFillColor(col)
    c.roundRect(280, y, 800 * v, 44, 8, stroke=0, fill=1)
    text(290 + 800 * v, y + 12, f"{v:.0%}", 22, INK, "Helvetica-Bold")
text(70, 90, f"PR-AUC {T['pr_auc']:.2f} vs {T['fraud_rate']:.2f} random  |  only {T['fast_track_fraud_leak']:.0%} of fraud reaches the fast lane  |  ONNX parity 3e-7", 18, MUTED)

# 8 IBM Z
slide("Why IBM Z: intelligence where the transaction happens", "IBM Z integration")
rows = [("Live on IBM LinuxONE (s390x)", "trained + served on LinuxONE today, public demo"),
        ("Telum on-chip AI accelerator", "scores 100% of claims synchronously, no network hop"),
        ("Machine Learning for z/OS", "serves the model in-transaction to CICS/COBOL claims apps"),
        ("IBM Snap ML", "tree-model inference on Telum; imports our XGBoost model"),
        ("Db2 for z/OS", "feature store next to claim records, data never leaves"),
        ("Pervasive encryption + Crypto Express", "health & financial data encrypted, HSM keys"),
        ("Secure Execution / Hyper Protect", "Granite + dashboard in confidential containers")]
for i, (k, v) in enumerate(rows):
    y = 540 - i * 62
    box(70, y - 14, 1140, 52, PANEL if i % 2 == 0 else BG, r=8)
    text(95, y + 4, k, 21, BLUE, "Helvetica-Bold")
    text(560, y + 4, v, 20, INK)

# 9 Responsible AI + data
slide("Responsible by design, rigorous data", "Trust")
text(70, 560, "Responsible AI", 26, INK, "Helvetica-Bold")
bullets(70, 510, ["Human decides every high-risk claim", "Exact reason code for every score", "Neutral, non-accusatory customer messages",
                  "GenAI explains; it never decides", "No protected attributes used"], 20)
text(680, 560, "Data methodology", 26, INK, "Helvetica-Bold")
bullets(680, 510, ["60k-claim simulator: 5 documented fraud schemes", "Overlapping distributions + 0.5% label noise",
                   "Strict time split 70 / 10 / 20, no shuffle", "Thresholds set by business policy on validation",
                   "Plug-in ready for real insurer data"], 20)

# 10 Close
slide("Impact and what's next", "Value")
bullets(70, 540, ["Policyholders: paid in hours, not weeks", "Insurers: fraud stopped before payout, lower handling cost",
                  "Investigators: short, explained queue with fraud-ring graphs", "Society: lower premiums, more trust, wider coverage"], 24)
text(70, 320, f"Try it now (running on IBM LinuxONE): {DEMO}", 22, BLUE, "Helvetica-Bold")
text(70, 270, "Next: real insurer data -> MLz / Snap ML in a CICS claims flow -> crop, life & travel claims", 22, MUTED)
text(70, 180, "Honest claims paid in hours. Fraud stopped before payout.", 32, BLUE, "Helvetica-Bold")
if CREDIT:
    text(70, 130, CREDIT, 20, MUTED)

c.save()
print("wrote docs/ClaimGuard_Pitch_Deck.pdf")
