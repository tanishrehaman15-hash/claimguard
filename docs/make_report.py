"""Build docs/ClaimGuard_Project_Report.pdf (pip install reportlab pypdfium2).

    python docs/make_report.py [path/to/linuxone_metadata.json]
"""
import json
import sys
from pathlib import Path

import pypdfium2
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
M = json.loads((ROOT / "artifacts" / "metadata.json").read_text())
LZ = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else M
T, B = M["test_metrics"], M["rules_baseline"]
LT = LZ["test_metrics"]
DEMO = "https://change-illustrations-tooth-complete.trycloudflare.com"
TEAM = "<your team name>"  # fill in; placeholders are left out of the PDF
REPO = "<github.com/you/claimguard>"

BLUE, INK, MUTED, PANEL = (colors.HexColor(c) for c in ("#0f62fe", "#161616", "#525252", "#f2f4f8"))
RED, GREEN, AMBER = (colors.HexColor(c) for c in ("#d64545", "#2e9e5b", "#b58100"))

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17, textColor=INK,
                    spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=BLUE,
                    spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontName="Helvetica", fontSize=10, leading=14.5,
                      textColor=INK, spaceAfter=6)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8.5, leading=12, textColor=MUTED)
BUL = ParagraphStyle("Bul", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=3)
CAP = ParagraphStyle("Cap", parent=SMALL, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(i, BUL, bulletText="•") for i in items]


def table(rows, widths, header=True, zebra=True):
    data = [[Paragraph(str(c), SMALL if not (header and r == 0) else ParagraphStyle(
        "th", parent=SMALL, textColor=colors.white, fontName="Helvetica-Bold")) for c in row]
        for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d0d0"))]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), BLUE))
    if zebra:
        for r in range(1 if header else 0, len(rows)):
            if r % 2 == 0:
                style.append(("BACKGROUND", (0, r), (-1, r), PANEL))
    t.setStyle(TableStyle(style))
    return t


def img(path, width, caption=None):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(path)).getSize()
    flow = [Image(str(path), width=width, height=width * ih / iw)]
    if caption:
        flow.append(p(caption, CAP))
    return KeepTogether(flow)


def stat_row(items):
    cells = [[Paragraph(f"<font size=20 color='{c}'><b>{v}</b></font><br/><font size=8 color='#525252'>{l}</font>",
                        ParagraphStyle("st", alignment=TA_CENTER, leading=22)) for v, l, c in items]]
    t = Table(cells, colWidths=[42 * mm] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL), ("BOX", (0, 0), (-1, -1), 4, colors.white),
                           ("INNERGRID", (0, 0), (-1, -1), 4, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 9),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return t


def pct(x):
    return f"{x:.0%}"


# Architecture image from the pitch deck
arch = DOCS / "img" / "architecture.png"
pypdfium2.PdfDocument(str(DOCS / "ClaimGuard_Pitch_Deck.pdf"))[3].render(scale=1.5).to_pil().convert("RGB").save(arch)

W = A4[0] - 36 * mm
story = []

# ---------------------------------------------------------------- cover
story += [Spacer(1, 40 * mm),
          p("<font size=34 color='#0f62fe'><b>ClaimGuard</b></font>", ParagraphStyle("t", leading=40)),
          Spacer(1, 6 * mm),
          p("<font size=15>Real-time AI risk scoring for insurance claims on IBM Z</font>", ParagraphStyle("s", leading=20)),
          Spacer(1, 3 * mm),
          p("<font size=11 color='#525252'>Pay honest claims in hours. Stop fraudulent ones before the money leaves.</font>"),
          Spacer(1, 14 * mm),
          table([["Event", "IBM Z Datathon 2026"],
                 ["Theme", "Real-time AI on Transactional Data (Theme 1)"],
                 ["Live demo", f"<link href='{DEMO}' color='#0f62fe'>{DEMO}</link><br/>(running on IBM LinuxONE, s390x)"],
                 *[[k, v] for k, v in (("Team", TEAM), ("Repository", REPO)) if "<" not in v]],
                [35 * mm, W - 35 * mm], header=False),
          Spacer(1, 14 * mm),
          stat_row([(pct(T["fraud_value_stopped_share"]), "fraud value stopped<br/>before payout", "#d64545"),
                    (pct(T["fast_track_rate"]), "claims paid<br/>instantly", "#2e9e5b"),
                    (f"{T['roc_auc']:.2f}", "ROC-AUC<br/>(time hold-out)", "#0f62fe"),
                    ("Live", "on IBM LinuxONE<br/>(s390x)", "#0f62fe")]),
          PageBreak()]

# ---------------------------------------------------------------- 1 summary
story += [p("1. Executive summary", H1),
          p("Insurers check most claims manually, after they are filed and often after they are paid. Honest customers "
            "wait days or weeks, fraud still slips through, and losses return to everyone as higher premiums. "
            "<b>ClaimGuard scores every claim the instant it is filed</b>, inside the claims transaction, and routes it "
            "to one of three lanes: fast-track payout, a one-document check, or an investigator. Every decision carries "
            "exact reason codes, and IBM Granite turns them into a short note for investigators."),
          p(f"On a strict time-based hold-out of the {T['claims']:,} most recent claims, ClaimGuard held "
            f"<b>{pct(T['fraud_value_stopped_share'])}</b> of fraudulent claim value before payout, paid "
            f"<b>{pct(T['fast_track_rate'])}</b> of claims with no manual work, and caught <b>{pct(B['model_recall'])}</b> "
            f"of fraud versus <b>{pct(B['rules_recall'])}</b> for red-flag rules at the same alert volume. "
            "The system is <b>trained and served on a real IBM LinuxONE server</b> today, with a public demo."),
          p("2. The problem", H1),
          p("Two customers show why timing matters:"),
          *bullets(["<b>Priya</b> has a minor accident and claims Rs 18,000. She is honest but waits about two weeks, "
                    "because every claim goes through the same manual queue.",
                    "<b>Rahul</b> claims Rs 2.4 lakh for a 'total loss' on a policy bought 9 days earlier, with no police "
                    "report, through a garage used by seven other customers who share his phone number."]),
          p("Manual checks treat them the same. Rule-based red flags catch only obvious cases, raise many false alarms, "
            "and cannot see hidden links between customers, providers and agents, which is how organised rings operate."),
          p("3. The solution", H1),
          table([["Lane", "What happens", "Share of test claims"],
                 ["<font color='#2e9e5b'><b>Fast-track</b></font>", "Paid straight through, no manual work",
                  f"{pct(T['fast_track_rate'])} (only {pct(T['fast_track_fraud_leak'])} of fraud enters this lane)"],
                 ["<font color='#b58100'><b>Document check</b></font>", "Customer uploads one extra document in-app",
                  pct(T["review_rate"])],
                 ["<font color='#d64545'><b>Investigate</b></font>", "Payout held; investigator gets an explained case",
                  f"{pct(T['investigate_rate'])} ({pct(T['investigate_precision'])} hit-rate)"]],
                [32 * mm, 80 * mm, W - 112 * mm]),
          Spacer(1, 3 * mm),
          p("No claim is ever rejected by a machine: a human decides every high-risk case. Thresholds are business "
            "policy (at most 3% of fraud may be fast-tracked, and investigators should be right about 80% of the time), "
            "not hidden inside the model."),
          PageBreak()]

# ---------------------------------------------------------------- 4 architecture
story += [p("4. Architecture and how it works", H1),
          img(arch, W * 0.8, "Figure 1. ClaimGuard scores claims inside the claims transaction."),
          *bullets(["<b>Stream.</b> Each claim event arrives from the core claims system (replayed feed in the prototype).",
                    "<b>Real-time features (26).</b> Amount vs actuarial tariff, share of sum insured, policy age, reporting "
                    "delay, incident hour, police report / pre-authorisation, documents and channel. Plus an "
                    "<b>identity graph</b> (union-find over shared phones and bank accounts) and <b>rolling 30-day windows</b> "
                    "per garage/hospital and agent (claim spikes, billing level, late-night share, linked-group share).",
                    "<b>Predict.</b> Gradient-boosted trees (XGBoost) give a risk score in about a millisecond.",
                    "<b>Decide.</b> A policy engine maps the score to a lane.",
                    "<b>Explain.</b> Exact TreeSHAP reason codes for every decision. IBM Granite (watsonx.ai or local) rewrites "
                    "them into an investigator note in English, Hindi, Tamil, Bengali or Marathi, and never changes the score."]),
          p("The same <i>build_features → observe</i> code path is used for training (replaying history in time order) and "
            "for live scoring, so there is no train/serve skew and no future leakage."),
          p("5. Data methodology", H1),
          p("Real claims data is confidential, so ClaimGuard includes a simulator of an Indian insurer's motor and health "
            f"claims: {M['data']['claims']:,} claims, 42,000 customers, 680 garages and hospitals, 300 agents, one year. "
            "Fraud mechanisms follow publicly documented red flags (IRDAI, Insurance Information Bureau of India, NICB):"),
          *bullets(["opportunistic <b>inflation</b> of genuine bills", "<b>early-policy</b> claims",
                    "<b>phantom</b> claims with weak paperwork", "<b>provider billing</b> fraud by colluding garages and hospitals",
                    "organised <b>rings</b> sharing phones and bank accounts, staging late-night incidents through one provider and agent"]),
          p("To keep the task honest, genuine and fraudulent distributions overlap (honest new policies, late reports, "
            "families sharing a phone), and 0.5% label noise mimics imperfect investigation outcomes. Evaluation uses a "
            "strict <b>time-based split</b>: 70% train, 10% validation (for thresholds) and 20% test, never a random shuffle."),
          PageBreak()]

# ---------------------------------------------------------------- 6 results
rt = M["recall_by_fraud_type"]
story += [p("6. Results", H1),
          p(f"Evaluated on the {T['claims']:,} most recent claims (fraud rate {pct(T['fraud_rate'])}). Because fraud is rare, "
            "accuracy is misleading; we report ranking quality (ROC-AUC, PR-AUC) and business outcomes."),
          table([["Metric", "Value", "Meaning"],
                 ["ROC-AUC", f"{T['roc_auc']:.3f}", "How well risky claims rank above safe ones (0.5 = random)"],
                 ["PR-AUC", f"{T['pr_auc']:.3f}", f"About {T['pr_auc'] / T['fraud_rate']:.0f}× better than random ({T['fraud_rate']:.3f})"],
                 ["Fraud value stopped before payout", pct(T["fraud_value_stopped_share"]),
                  f"Rs {T['fraud_value_stopped_inr'] / 1e7:.2f} Cr of Rs {T['fraud_value_total_inr'] / 1e7:.2f} Cr"],
                 ["Claims fast-tracked", pct(T["fast_track_rate"]), f"Only {pct(T['fast_track_fraud_leak'])} of fraud enters this lane"],
                 ["Investigator hit-rate", pct(T["investigate_precision"]), f"Queue is {pct(T['investigate_rate'])} of claims"],
                 ["Fraud caught vs rules (same alerts)", f"{pct(B['model_recall'])} vs {pct(B['rules_recall'])}",
                  f"{B['alerts']:,} alerts; precision {pct(B['model_precision'])} vs {pct(B['rules_precision'])}"],
                 ["Scoring latency", "~0.2–1 ms", "Per claim, on a laptop and on 3 LinuxONE vCPUs"]],
                [55 * mm, 30 * mm, W - 85 * mm]),
          p("Fraud stopped before payout, by scheme", H2),
          table([["Scheme", *[k.replace("_", " ") for k in rt]], ["Not fast-tracked", *[pct(v) for v in rt.values()]]],
                [35 * mm] + [(W - 35 * mm) / len(rt)] * len(rt)),
          p("What the model relies on most", H2),
          table([["Feature", "Gain"]] + [[M["feature_labels"][k], f"{v:.1f}"] for k, v in M["feature_importance"][:8]],
                [W - 30 * mm, 30 * mm]),
          p("Graph and provider features rank highest, which confirms that linking customers, providers and agents in real "
            "time adds signal that per-claim rules cannot capture.", SMALL),
          PageBreak()]

# ---------------------------------------------------------------- 7 demo
story += [p("7. The prototype", H1),
          p(f"The dashboard is live at <link href='{DEMO}' color='#0f62fe'>{DEMO}</link>, served from IBM LinuxONE."),
          img(DOCS / "img" / "hd_live.png", W, "Figure 2. Live claims: every claim scored in about a millisecond and routed to a lane. The sidebar shows the s390x (IBM Z) architecture."),
          img(DOCS / "img" / "hd_investigate.png", W, "Figure 3. Investigator view: risk gauge, exact SHAP reason codes and contribution chart."),
          PageBreak(),
          img(DOCS / "img" / "hd_priya.png", W, "Figure 4. Priya's genuine claim: risk 0.6/100, fast-tracked, positive customer message."),
          img(DOCS / "img" / "hd_rahul.png", W, "Figure 5. Rahul's claim: risk 99/100, sent to an investigator, with a neutral customer message."),
          PageBreak(),
          img(DOCS / "img" / "hd_rings.png", W, "Figure 6. Identity graph: linked customers funnelling claims into one garage."),
          img(DOCS / "img" / "hd_model.png", W, "Figure 7. Model and IBM Z tab: metrics, rules vs AI, and the deployment map."),
          PageBreak()]

# ---------------------------------------------------------------- 8 IBM Z
story += [p("8. IBM Z and LinuxONE", H1),
          p("Running live on IBM LinuxONE", H2),
          p("ClaimGuard is trained, tested and served on a real IBM LinuxONE virtual server (s390x, RHEL 9.8). The dashboard, "
            "the scoring API and nginx run as systemd services, and a Cloudflare tunnel compiled for s390x gives the public link."),
          table([["Check on s390x", "Result"],
                 ["Training (60k claims, 26 features)", f"25 s, ROC-AUC {LT['roc_auc']:.3f}, {pct(LT['fraud_value_stopped_share'])} of fraud value stopped"],
                 ["Smoke tests", "6 / 6 pass"],
                 ["Live scoring latency", "~0.3–1 ms per claim (3 vCPUs)"],
                 ["Python AI stack", "numpy, pandas, scikit-learn, XGBoost, Apache Arrow and pyarrow compiled from source for s390x"],
                 ["Big-endian fixes", "Tables rendered as HTML and Plotly arrays sent as JSON lists, because browser libraries assume little-endian data"]],
                [55 * mm, W - 55 * mm]),
          p("Production path on IBM Z", H2),
          table([["Capability", "Role in ClaimGuard"],
                 ["Telum on-chip AI accelerator", "Scores 100% of claims synchronously inside the transaction, with no network hop"],
                 ["Machine Learning for z/OS + IBM Snap ML", "Serves the tree model in-transaction to CICS/COBOL claims apps (Snap ML tree inference uses the Telum accelerator)"],
                 ["Db2 for z/OS", "Feature store next to the claim records, so data never leaves the platform"],
                 ["Pervasive encryption + Crypto Express", "Health and financial data encrypted at rest and in flight, with HSM-protected keys"],
                 ["Secure Execution / Hyper Protect", "Granite and the dashboard run in confidential containers on LinuxONE"],
                 ["IBM Z Deep Learning Compiler", "Path for future neural-network variants exported as ONNX"]],
                [55 * mm, W - 55 * mm]),
          p("The z/OS / Machine Learning for z/OS integration is the designed production path and was not tested in this "
            "prototype; the LinuxONE deployment is live.", SMALL),
          p("9. Responsible AI", H1),
          *bullets(["<b>Human in the loop:</b> high risk means a human decides; the model never rejects a claim.",
                    "<b>Explainable:</b> exact TreeSHAP reason codes for every decision.",
                    "<b>Non-accusatory:</b> customers receive neutral, helpful messages; GenAI only rephrases facts.",
                    "<b>Privacy by design:</b> the model uses phone and bank <i>linkage</i>, not raw identities; on IBM Z data stays encrypted on-platform.",
                    "<b>Fairness:</b> no protected attributes (gender, religion, caste); age and tenure to be monitored for disparate impact before production."]),
          PageBreak()]

# ---------------------------------------------------------------- 10 limits, impact, stack
story += [p("10. Limitations and next steps", H1),
          *bullets(["Results come from synthetic data; a pilot on an insurer's historical claims is the next step (the pipeline is schema-driven).",
                    f"{pct(T['review_rate'])} of claims get a one-document check under the strict 3% fraud-leak policy; insurers can relax it to fast-track more.",
                    "Granite notes use a deterministic template unless watsonx.ai or a local Granite model is configured.",
                    "The free public link changes if the tunnel restarts; a named Cloudflare tunnel or domain would make it permanent.",
                    "Next: Machine Learning for z/OS / Snap ML in a CICS claims flow, drift monitoring and retraining, then crop, life and travel claims."]),
          p("11. Impact", H1),
          table([["Who", "Benefit"],
                 ["Policyholders", "Honest claims paid in hours instead of weeks"],
                 ["Insurers", "Fraud stopped before payout; lower handling cost"],
                 ["Investigators", "A short, explained queue with fraud-ring graphs"],
                 ["Regulators", "Transparent, explainable, human-reviewed decisions"],
                 ["Society", "Lower premiums, more trust in insurance, wider coverage"]], [40 * mm, W - 40 * mm]),
          p("12. Technology and open-source resources", H1),
          table([["Layer", "Tools"],
                 ["Data and ML", "Python, NumPy, pandas, scikit-learn, XGBoost, ONNX, onnxmltools, ONNX Runtime"],
                 ["Graph", "Union-find (custom), NetworkX"],
                 ["Serving", "FastAPI, Uvicorn, nginx, systemd, Cloudflare tunnel (cloudflared)"],
                 ["Dashboard", "Streamlit, Plotly, Apache Arrow"],
                 ["GenAI", "IBM Granite (watsonx.ai or Ollama)"],
                 ["IBM Z", "IBM LinuxONE (s390x), RHEL 9; production path MLz / Snap ML, Telum, Db2 for z/OS"]],
                [35 * mm, W - 35 * mm]),
          Spacer(1, 4 * mm),
          p("Links: XGBoost github.com/dmlc/xgboost · scikit-learn scikit-learn.org · ONNX onnx.ai · ONNX Runtime onnxruntime.ai · "
            "FastAPI fastapi.tiangolo.com · Streamlit streamlit.io · Plotly plotly.com/python · NetworkX networkx.org · "
            "IBM Granite huggingface.co/ibm-granite · IBM zDLC github.com/IBM/zDLC · cloudflared github.com/cloudflare/cloudflared", SMALL)]


def frame(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFillColor(BLUE)
        canvas.rect(0, A4[1] - 5, A4[0], 5, stroke=0, fill=1)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, "ClaimGuard · IBM Z Datathon 2026 · Project report")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, str(doc.page))
    else:
        canvas.setFillColor(BLUE)
        canvas.rect(0, 0, 8, A4[1], stroke=0, fill=1)
    canvas.restoreState()


out = DOCS / "ClaimGuard_Project_Report.pdf"
SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                  bottomMargin=18 * mm, title="ClaimGuard: Project Report", author="ClaimGuard team").build(
    story, onFirstPage=frame, onLaterPages=frame)
print("wrote", out)
