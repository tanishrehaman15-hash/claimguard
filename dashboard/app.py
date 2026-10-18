"""ClaimGuard live dashboard.

    streamlit run dashboard/app.py
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claimguard import ARTIFACTS, DATA  # noqa: E402
from claimguard.explain import inr, investigator_note, llm_backend  # noqa: E402
from claimguard.train import main as train_main  # noqa: E402
from claimguard.features import SUBTYPES, TYPICAL_AMOUNT  # noqa: E402
from claimguard.scorer import Scorer  # noqa: E402

st.set_page_config(page_title="ClaimGuard", page_icon="🛡️", layout="wide")

COLORS = {"fast_track": "#2e9e5b", "review": "#e0a100", "investigate": "#d64545"}
ICON = {"fast_track": "🟢", "review": "🟡", "investigate": "🔴"}
LABEL = {"fast_track": "Fast-track", "review": "Doc check", "investigate": "Investigate"}

st.markdown("""
<style>
.block-container {padding-top: 1.6rem;}
div[data-testid="stMetricValue"] {font-size: 1.7rem;}
.banner {padding: 14px 18px; border-radius: 10px; color: white; font-weight: 600; font-size: 1.15rem;}
.reason-risk {border-left: 4px solid #d64545; padding: 4px 10px; margin: 4px 0; background: rgba(214,69,69,.08);}
.cgtable {overflow:auto; border:1px solid rgba(128,128,128,.25); border-radius:8px;}
.cgtable table {width:100%; border-collapse:collapse; font-size:.85rem;}
.cgtable th {position:sticky; top:0; background:rgba(128,128,128,.18); text-align:left; padding:6px 8px; white-space:nowrap;}
.cgtable td {padding:5px 8px; border-top:1px solid rgba(128,128,128,.15); white-space:nowrap;}
.cgtable .bar {display:inline-block; width:60px; height:8px; background:rgba(128,128,128,.25); border-radius:4px; margin-right:6px; vertical-align:middle;}
.cgtable .bar span {display:block; height:100%; background:#d64545; border-radius:4px;}
.reason-ok {border-left: 4px solid #2e9e5b; padding: 4px 10px; margin: 4px 0; background: rgba(46,158,91,.08);}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Warming up the real-time feature store with 48,000 historical claims ...")
def get_scorer() -> Scorer:
    if not (DATA / "claims.csv").exists() or not (ARTIFACTS / "metadata.json").exists():
        train_main()  # first run (e.g. fresh clone / Streamlit Cloud): build data + model, ~10 s
    return Scorer()


S = get_scorer()
ss = st.session_state
ss.setdefault("feed", [])
ss.setdefault("cursor", 0)
ss.setdefault("running", False)
ss.setdefault("speed", 4)


BIG_ENDIAN = sys.byteorder == "big"  # IBM Z / LinuxONE (s390x)
if BIG_ENDIAN:
    # Plotly base64-encodes numpy arrays in native byte order, which plotly.js reads as
    # little-endian. Send plain JSON lists instead so charts are correct on IBM Z.
    import _plotly_utils.utils as _plotly_utils

    _plotly_utils.to_typed_array_spec = lambda v: v


def show_table(df: pd.DataFrame, height: int = 560, bars: dict | None = None, money: tuple = (), column_config=None) -> None:
    """st.dataframe ships Arrow buffers in the server's byte order, which the browser misreads on
    big-endian IBM Z. There we render a styled HTML table instead; elsewhere the native grid."""
    if not BIG_ENDIAN:
        st.dataframe(df, hide_index=True, use_container_width=True, height=height, column_config=column_config)
        return
    bars = bars or {}
    head = "".join(f"<th>{c}</th>" for c in df.columns)
    body = []
    for row in df.itertuples(index=False):
        cells = []
        for col, v in zip(df.columns, row):
            if col in bars:
                pct = max(0.0, min(1.0, float(v) / bars[col])) * 100
                cells.append(f"<td><div class='bar'><span style='width:{pct:.0f}%'></span></div>"
                             f"<small>{v:.0f}</small></td>" if bars[col] > 1 else
                             f"<td><div class='bar'><span style='width:{pct:.0f}%'></span></div><small>{v:.2f}</small></td>")
            elif col in money:
                cells.append(f"<td style='text-align:right'>{inr(v)}</td>")
            elif isinstance(v, float):
                cells.append(f"<td style='text-align:right'>{v:.2f}</td>")
            else:
                cells.append(f"<td>{v}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(f"<div class='cgtable' style='max-height:{height}px'><table><thead><tr>{head}</tr></thead>"
                f"<tbody>{''.join(body)}</tbody></table></div>", unsafe_allow_html=True)


def score_next(n: int) -> None:
    for _ in range(n):
        if ss.cursor >= len(S.live_claims):
            ss.running = False
            return
        c = S.live_claims[ss.cursor]
        ss.cursor += 1
        ss.feed.append({"claim": c, "result": S.score(c)})


def gauge(score: float, decision: str, height: int = 220) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number={"suffix": "/100"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": COLORS[decision]},
               "steps": [{"range": [0, S.t_low * 100], "color": "rgba(46,158,91,.15)"},
                         {"range": [S.t_low * 100, S.t_high * 100], "color": "rgba(224,161,0,.15)"},
                         {"range": [S.t_high * 100, 100], "color": "rgba(214,69,69,.15)"}]}))
    fig.update_layout(height=height, margin=dict(l=20, r=20, t=30, b=0))
    return fig


def show_reasons(result: dict) -> None:
    st.markdown("**Why this score** (exact SHAP reason codes)")
    for r in result["reasons"]:
        st.markdown(f"<div class='reason-risk'>▲ {r['text']}</div>", unsafe_allow_html=True)
    for r in result["protective"]:
        st.markdown(f"<div class='reason-ok'>▼ {r['text']}</div>", unsafe_allow_html=True)
    if not result["reasons"] and not result["protective"]:
        st.caption("No strong signals either way.")


def contribution_chart(result: dict) -> go.Figure:
    rows = result["reasons"] + result["protective"]
    df = pd.DataFrame(rows).sort_values("impact")
    fig = go.Figure(go.Bar(x=df.impact, y=df.label, orientation="h",
                           marker_color=[COLORS["investigate"] if v > 0 else COLORS["fast_track"] for v in df.impact]))
    fig.update_layout(height=260, margin=dict(l=0, r=10, t=10, b=0), xaxis_title="Impact on risk (log-odds)")
    return fig


def banner(result: dict) -> None:
    st.markdown(f"<div class='banner' style='background:{COLORS[result['decision']]}'>"
                f"{ICON[result['decision']]} {result['decision_label']} · risk {result['score']:.0f}/100 · "
                f"scored in {result['latency_ms']:.2f} ms</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## 🛡️ ClaimGuard")
    st.caption("Real-time AI risk scoring for insurance claims · IBM Z Datathon")
    c1, c2 = st.columns(2)
    if c1.button("⏸ Pause" if ss.running else "▶ Start feed", use_container_width=True, type="primary"):
        ss.running = not ss.running
        st.rerun()
    if c2.button("↺ Reset", use_container_width=True):
        st.cache_resource.clear()
        for k in ("feed", "cursor", "running"):
            ss.pop(k, None)
        st.rerun()
    ss.speed = st.slider("Claims per second", 1, 25, ss.speed)
    show_truth = st.toggle("Show ground truth (demo only)", value=False)
    st.divider()
    st.markdown(f"**Inference engine:** `{S.engine}` on `{platform.machine()}`")
    st.markdown(f"**GenAI notes:** `{llm_backend()}`")
    st.markdown(f"**Thresholds:** fast-track < {S.t_low * 100:.1f} · investigate ≥ {S.t_high * 100:.1f}")
    st.caption("Running on IBM LinuxONE. In production on z/OS the model is served by Machine Learning for z/OS (Snap ML) on the Telum on-chip AI accelerator, inside the claims transaction.")

st.title("ClaimGuard: stop fraudulent claims, pay honest ones faster")
tab_live, tab_inv, tab_file, tab_ring, tab_model = st.tabs(
    ["📡 Live claims", "🔍 Investigate", "📝 File a claim", "🕸️ Fraud rings", "📊 Model & IBM Z"])


# ---------------------------------------------------------------- live feed
@st.fragment(run_every=1.0 if ss.running else None)
def live_panel() -> None:
    if ss.running:
        score_next(ss.speed)
    feed = ss.feed
    st.progress(ss.cursor / len(S.live_claims), text=f"Live period: {ss.cursor:,} / {len(S.live_claims):,} claims replayed")
    k = st.columns(5)
    n = len(feed)
    dec = pd.Series([f["result"]["decision"] for f in feed], dtype="object")
    held = sum(f["claim"]["claim_amount"] for f in feed if f["result"]["decision"] == "investigate")
    lat = [f["result"]["latency_ms"] for f in feed]
    k[0].metric("Claims scored", f"{n:,}")
    k[1].metric("Fast-tracked", f"{(dec == 'fast_track').mean():.0%}" if n else "-", help="Paid straight through, no manual work")
    k[2].metric("Sent to investigators", f"{(dec == 'investigate').sum():,}")
    k[3].metric("Payout held for review", inr(held))
    k[4].metric("Model latency p50", f"{np.median(lat):.2f} ms" if lat else "-")
    if not feed:
        st.info("Press **▶ Start feed** in the sidebar to stream live claims into the model.")
        return

    rows = []
    for f in reversed(feed[-300:]):
        c, r = f["claim"], f["result"]
        row = {"Filed": pd.Timestamp(c["ts"]).strftime("%d %b %H:%M"), "Claim": c["claim_id"],
               "Customer": c["customer_name"], "Type": f"{c['claim_type']} · {c['subtype'].replace('_', ' ')}",
               "Amount (₹)": c["claim_amount"], "Risk": r["score"],
               "Decision": f"{ICON[r['decision']]} {LABEL[r['decision']]}",
               "Top signal": r["reasons"][0]["text"] if r["reasons"] else "-"}
        if show_truth:
            row["Truth"] = f"⚠️ {c['fraud_type']}" if c["is_fraud"] else "genuine"
        rows.append(row)
    left, right = st.columns([2.2, 1])
    with left:
        show_table(pd.DataFrame(rows).head(30), height=560, bars={"Risk": 100}, money=("Amount (₹)",),
                   column_config={"Risk": st.column_config.ProgressColumn("Risk", min_value=0, max_value=100, format="%.0f"),
                                  "Amount (₹)": st.column_config.NumberColumn(format="%d")})
    with right:
        counts = dec.value_counts()
        fig = go.Figure(go.Pie(labels=[LABEL[d] for d in counts.index], values=counts.values, hole=0.6,
                               marker_colors=[COLORS[d] for d in counts.index], sort=False))
        fig.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0), title="Decisions", showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        scores = pd.DataFrame({"score": [f["result"]["score"] for f in feed], "decision": dec.map(LABEL)})
        fig = px.histogram(scores, x="score", color="decision", nbins=40, log_y=True,
                           color_discrete_map={LABEL[d]: COLORS[d] for d in COLORS})
        for t in (S.t_low, S.t_high):
            fig.add_vline(x=t * 100, line_dash="dash", line_color="grey")
        fig.update_layout(height=290, margin=dict(l=0, r=0, t=30, b=0), title="Risk score distribution",
                          showlegend=False, xaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)
    if show_truth:
        truth = np.array([f["claim"]["is_fraud"] for f in feed])
        flagged = dec.values != "fast_track"
        if truth.sum():
            st.caption(f"Ground truth so far: {truth.sum()} fraudulent claims, {(truth & flagged).sum()} stopped before "
                       f"payout ({(truth & flagged).sum() / truth.sum():.0%}); "
                       f"{(~flagged & (truth == 0)).sum()} genuine claims fast-tracked.")


with tab_live:
    live_panel()


# ---------------------------------------------------------------- investigate
with tab_inv:
    flagged = [f for f in reversed(ss.feed) if f["result"]["decision"] != "fast_track"]
    if not flagged:
        st.info("No flagged claims yet. Start the live feed first.")
    else:
        opts = {f"{ICON[f['result']['decision']]} {f['claim']['claim_id']} · {f['claim']['customer_name']} · "
                f"{inr(f['claim']['claim_amount'])} · risk {f['result']['score']:.0f}": f for f in flagged[:200]}
        pick = opts[st.selectbox("Flagged claims (newest first)", list(opts))]
        c, r = pick["claim"], pick["result"]
        banner(r)
        a, b = st.columns([1, 1.3])
        with a:
            st.plotly_chart(gauge(r["score"], r["decision"]), use_container_width=True)
            st.markdown(f"**{c['customer_name']}** · {c['city']} · customer for {c['customer_tenure_years']:.1f} yrs")
            st.markdown(f"{c['claim_type'].title()} · {c['subtype'].replace('_', ' ')} · **{inr(c['claim_amount'])}** "
                        f"(sum insured {inr(c['sum_insured'])})")
            st.markdown(f"Provider **{S.providers.provider_name.get(c['provider_id'], c['provider_id'])}** · agent {c['agent_id']}")
        with b:
            show_reasons(r)
        st.plotly_chart(contribution_chart(r), use_container_width=True)
        g1, g2 = st.columns([3, 1])
        lang = g2.selectbox("Language", ["English", "Hindi", "Tamil", "Bengali", "Marathi"])
        if g1.button("✨ Generate investigator note (IBM Granite)", type="primary"):
            note, src = investigator_note(c, r, lang)
            st.success(note)
            st.caption(f"Source: {src}. GenAI only rephrases the reason codes; it never changes the score or decision.")
        st.markdown("**Message sent to customer**")
        st.info(r["customer_message"])
        with st.expander("All model inputs"):
            st.json({k: round(v, 3) if isinstance(v, float) else v for k, v in r["features"].items()})


# ---------------------------------------------------------------- file a claim
with tab_file:
    ring = S.demo_ring()
    garages = S.providers[(S.providers.provider_type == "motor") & ~S.providers.colluding].index.tolist()
    presets = {
        "Priya: minor fender-bender (genuine)": dict(
            customer_id="CUS-DEMO-PRIYA", name="Priya Nair", phone="9800011122", bank_account="AC90000000001",
            claim_type="motor", subtype="collision", claim_amount=18_000, sum_insured=300_000, policy_age_days=900,
            report_delay_days=0.5, incident_hour=11, verified_record=1, witness_count=1, prior_claims_12m=0,
            customer_tenure_years=6.0, customer_age=34, docs_complete=1, channel="app",
            provider_id=garages[0], agent_id="AGT-0042"),
        "Rahul: 'total loss' on a 9-day-old policy (suspicious)": dict(
            customer_id="CUS-DEMO-RAHUL", name="Rahul Verma", phone=ring["phone"], bank_account=ring["bank_account"],
            claim_type=ring["claim_type"], subtype="collision" if ring["claim_type"] == "motor" else "surgery",
            claim_amount=240_000 if ring["claim_type"] == "motor" else 520_000, sum_insured=600_000,
            policy_age_days=9, report_delay_days=6, incident_hour=23, verified_record=0,
            witness_count=3 if ring["claim_type"] == "motor" else 0, prior_claims_12m=1, customer_tenure_years=0.2,
            customer_age=29, docs_complete=0, channel="agent", provider_id=ring["provider_id"], agent_id=ring["agent_id"]),
    }
    choice = st.radio("Scenario", list(presets), horizontal=True)
    p = presets[choice]
    with st.form(f"claim_{choice}"):
        f1, f2, f3, f4 = st.columns(4)
        ctype = f1.selectbox("Claim type", ["motor", "health"], index=["motor", "health"].index(p["claim_type"]))
        subtype = f1.selectbox("Subtype", SUBTYPES[ctype],
                               index=SUBTYPES[ctype].index(p["subtype"]) if p["subtype"] in SUBTYPES[ctype] else 0)
        amount = f1.number_input("Claim amount (₹)", 1_000, 5_000_000, int(p["claim_amount"]), step=1_000)
        si = f1.number_input("Sum insured (₹)", 10_000, 10_000_000, int(p["sum_insured"]), step=10_000)
        pol = f2.number_input("Policy age (days)", 0, 5_000, int(p["policy_age_days"]))
        delay = f2.number_input("Days from incident to report", 0.0, 90.0, float(p["report_delay_days"]))
        hour = f2.slider("Incident hour", 0, 23, int(p["incident_hour"]))
        verified = f2.checkbox("Police report / hospital pre-auth", bool(p["verified_record"]))
        wit = f3.number_input("Witnesses", 0, 10, int(p["witness_count"]))
        prior = f3.number_input("Claims in last 12 months", 0, 20, int(p["prior_claims_12m"]))
        ten = f3.number_input("Customer tenure (years)", 0.0, 40.0, float(p["customer_tenure_years"]))
        age = f3.number_input("Customer age", 18, 100, int(p["customer_age"]))
        docs = f4.checkbox("All documents submitted", bool(p["docs_complete"]))
        channel = f4.selectbox("Channel", ["app", "agent", "branch"], index=["app", "agent", "branch"].index(p["channel"]))
        phone = f4.text_input("Phone", p["phone"])
        bank = f4.text_input("Bank account", p["bank_account"])
        provider = f4.text_input("Garage / hospital ID", p["provider_id"])
        submitted = st.form_submit_button("Submit claim for real-time scoring", type="primary")
    if submitted:
        claim = dict(claim_id=f"DEMO-{np.random.randint(10_000, 99_999)}", ts=S.clock, customer_id=p["customer_id"],
                     customer_name=p["name"], city="Mumbai", phone=phone, bank_account=bank, claim_type=ctype,
                     subtype=subtype, claim_amount=float(amount), sum_insured=float(si), policy_age_days=int(pol),
                     report_delay_days=float(delay), incident_hour=int(hour), verified_record=int(verified),
                     witness_count=int(wit), prior_claims_12m=int(prior), customer_tenure_years=float(ten),
                     customer_age=int(age), docs_complete=int(docs), channel=channel, provider_id=provider,
                     agent_id=p["agent_id"])
        r = S.score(claim, update_state=False)
        banner(r)
        a, b = st.columns([1, 1.3])
        with a:
            st.plotly_chart(gauge(r["score"], r["decision"]), use_container_width=True)
            st.markdown("**Message to customer**")
            st.info(r["customer_message"])
        with b:
            show_reasons(r)
            note, src = investigator_note(claim, r)
            st.markdown("**Investigator note**")
            st.success(note)
            st.caption(f"Source: {src}")


# ---------------------------------------------------------------- fraud rings
@st.cache_resource(show_spinner="Building identity graph ...")
def ring_table(_s: Scorer):
    cust = _s.customers
    g = nx.Graph()
    for col, kind in (("phone", "📞"), ("bank_account", "🏦")):
        shared = cust[cust.duplicated(col, keep=False)]
        for cid, val in zip(shared.customer_id, shared[col]):
            g.add_edge(cid, f"{kind} {val}")
    claims = _s.claims
    rows, comps = [], {}
    for i, comp in enumerate(nx.connected_components(g)):
        members = [n for n in comp if n.startswith("CUS-")]
        if len(members) < 3:
            continue
        cl = claims[claims.customer_id.isin(members)]
        key = f"NET-{i:04d}"
        comps[key] = (comp, cl)
        rows.append({"Network": key, "Customers": len(members),
                     "Shared phones": sum(n.startswith("📞") for n in comp),
                     "Shared accounts": sum(n.startswith("🏦") for n in comp),
                     "Claims": len(cl), "Total claimed": cl.claim_amount.sum(),
                     "Providers used": cl.provider_id.nunique(),
                     "Claims at one provider": int(cl.provider_id.value_counts().iloc[0]) if len(cl) else 0,
                     "Top provider share": cl.provider_id.value_counts(normalize=True).iloc[0] if len(cl) else 0,
                     "Late-night share": ((cl.incident_hour >= 22) | (cl.incident_hour <= 4)).mean() if len(cl) else 0})
    # Rank by the strongest ring signal: many linked customers funnelling claims to one provider.
    df = pd.DataFrame(rows).sort_values(["Claims at one provider", "Customers"], ascending=False)
    return df, comps, g


with tab_ring:
    st.markdown("Customers linked by **shared phone numbers or bank accounts** form an identity graph. "
                "Organised rings show up as dense clusters that all use the same garage/hospital and agent, "
                "and the model uses these signals in real time.")
    rt, comps, g = ring_table(S)
    show_table(rt.head(25), height=420, bars={"Top provider share": 1}, money=("Total claimed",),
               column_config={"Total claimed": st.column_config.NumberColumn(format="₹%d"),
                              "Top provider share": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
                              "Late-night share": st.column_config.NumberColumn(format="%.2f")})
    if not rt.empty:
        key = st.selectbox("Visualise network", rt.Network.head(25))
        comp, cl = comps[key]
        sub = g.subgraph(comp).copy()
        for c in cl.itertuples():
            sub.add_edge(c.customer_id, f"🏥 {S.providers.provider_name.get(c.provider_id, c.provider_id)}")
        pos = nx.spring_layout(sub, seed=7, k=0.9)
        ex, ey = [], []
        for u, v in sub.edges():
            ex += [pos[u][0], pos[v][0], None]
            ey += [pos[u][1], pos[v][1], None]
        fig = go.Figure(go.Scatter(x=ex, y=ey, mode="lines", line=dict(color="#bbb", width=1), hoverinfo="none"))
        names = S.customers.set_index("customer_id").name
        for kind, color, size in (("CUS-", "#3366cc", 16), ("📞", "#e0a100", 13), ("🏦", "#8e44ad", 13), ("🏥", "#d64545", 20)):
            nodes = [n for n in sub.nodes if n.startswith(kind)]
            labels = [f"{names.get(n, n)} ({n})" if kind == "CUS-" else n for n in nodes]
            fig.add_trace(go.Scatter(x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes], mode="markers+text",
                                     marker=dict(size=size, color=color), text=[l.split(" (")[0] if kind == "CUS-" else l[:2] for l in labels],
                                     textposition="top center", hovertext=labels, hoverinfo="text",
                                     name={"CUS-": "Customer", "📞": "Shared phone", "🏦": "Shared account", "🏥": "Garage / hospital"}[kind]))
        fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0), xaxis_visible=False, yaxis_visible=False,
                          legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------- model & IBM Z
with tab_model:
    m, base = S.meta["test_metrics"], S.meta["rules_baseline"]
    st.markdown(f"Evaluated on the **most recent {m['claims']:,} claims** (time-based hold-out: the model never saw "
                f"the future). Fraud rate {m['fraud_rate']:.1%}.")
    k = st.columns(5)
    k[0].metric("ROC-AUC", f"{m['roc_auc']:.3f}")
    k[1].metric("PR-AUC", f"{m['pr_auc']:.3f}", help=f"Random baseline = {m['fraud_rate']:.3f}")
    k[2].metric("Claims fast-tracked", f"{m['fast_track_rate']:.0%}", help="Paid with zero manual work")
    k[3].metric("Investigator hit-rate", f"{m['investigate_precision']:.0%}")
    k[4].metric("Fraud value stopped", f"{m['fraud_value_stopped_share']:.0%}", help=inr(m["fraud_value_stopped_inr"]))
    a, b = st.columns(2)
    with a:
        bdf = pd.DataFrame({"Approach": ["Red-flag rules", "ClaimGuard AI"] * 2,
                            "Metric": ["Precision"] * 2 + ["Recall"] * 2,
                            "Value": [base["rules_precision"], base["model_precision"], base["rules_recall"], base["model_recall"]]})
        fig = px.bar(bdf, x="Metric", y="Value", color="Approach", barmode="group", text_auto=".0%",
                     color_discrete_sequence=["#999", "#0f62fe"],
                     title=f"Same alert volume ({base['alerts']:,} alerts): rules vs AI")
        fig.update_layout(height=340, yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
    with b:
        imp = pd.DataFrame(S.meta["feature_importance"][:12], columns=["feature", "gain"])
        imp["feature"] = imp.feature.map(S.labels)
        fig = px.bar(imp.iloc[::-1], x="gain", y="feature", orientation="h", title="What the model relies on")
        fig.update_layout(height=340)
        st.plotly_chart(fig, use_container_width=True)
    a, b = st.columns(2)
    with a:
        pr = S.meta["pr_curve"]
        fig = px.line(x=pr["recall"], y=pr["precision"], labels={"x": "Recall", "y": "Precision"}, title="Precision-recall (test)")
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)
    with b:
        bt = pd.Series(S.meta["recall_by_fraud_type"]).rename("caught").reset_index()
        fig = px.bar(bt, x="index", y="caught", text_auto=".0%", title="Fraud stopped before payout, by scheme",
                     labels={"index": "", "caught": ""})
        fig.update_layout(height=320, yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    lat = [f["result"]["latency_ms"] for f in ss.feed]
    st.subheader("Running on IBM Z")
    st.markdown(f"""
| Layer | This prototype | Production on IBM Z |
|---|---|---|
| Inference | {S.engine} on {platform.machine()} · {f'p50 {np.median(lat):.2f} ms / p99 {np.percentile(lat, 99):.2f} ms (this session)' if lat else 'start the feed to measure'} | **Machine Learning for z/OS** (Snap ML tree inference on the **Telum on-chip AI accelerator**), called in-transaction from CICS |
| Feature store | In-memory entity graph + rolling windows | **Db2 for z/OS** / in-memory cache co-located with the claims system, so no data leaves the platform |
| Data protection | Synthetic data | **Pervasive encryption**, Crypto Express HSM keys, **Secure Execution** for the LinuxONE containers |
| GenAI notes | `{llm_backend()}` | **IBM Granite** on LinuxONE / watsonx.ai, which rephrases reason codes and never decides |
| Model training | XGBoost | XGBoost or **IBM Snap ML** on LinuxONE; same ONNX artifact |

ONNX parity check vs native model: max |Δp| = `{S.meta['onnx'].get('max_abs_diff_vs_xgboost', 'n/a')}`.
""")
