"""Explanations: per-claim reason codes (SHAP) + generative summaries (IBM Granite).

Reason codes come from exact TreeSHAP contributions, so every score can be
traced to the facts that drove it. The generative layer only *rephrases*
those facts for people; it never changes the score or the decision.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def inr(v: float) -> str:
    """Indian digit grouping: 1234567 -> ₹12,34,567."""
    s = f"{int(round(v))}"
    if len(s) <= 3:
        return f"₹{s}"
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])


def describe(feature: str, f: dict, c: dict) -> str:
    """Plain-language description of one feature value for this claim."""
    motor = c["claim_type"] == "motor"
    prov = c.get("provider_name") or c["provider_id"]
    if feature == "amount_vs_typical":
        return f"Claimed {inr(c['claim_amount'])} is {f[feature]:.1f}× the typical cost of a {c['subtype'].replace('_', ' ')} claim"
    if feature == "log_claim_amount":
        return f"Claim value of {inr(c['claim_amount'])}"
    if feature == "amount_to_sum_insured":
        return f"Claim uses {f[feature]:.0%} of the sum insured"
    if feature == "policy_age_days":
        d = int(f[feature])
        return f"Policy is only {d} days old" if d < 90 else f"Policy has been active for {d:,} days"
    if feature == "report_delay_days":
        return f"Reported {f[feature]:.0f} days after the incident" if f[feature] >= 1 else "Reported on the same day"
    if feature in ("is_night", "incident_hour"):
        return f"Incident time {int(f['incident_hour']):02d}:00" + (" (late night)" if f["is_night"] else "")
    if feature == "is_weekend":
        return "Filed on a weekend" if f[feature] else "Filed on a weekday"
    if feature == "verified_record":
        if f[feature]:
            return "Police report on file" if motor else "Hospital pre-authorisation on file"
        return "No police report filed" if motor else "No cashless pre-authorisation from the hospital"
    if feature == "witness_count":
        return f"{int(f[feature])} witness(es) listed"
    if feature == "prior_claims_12m":
        n = int(f[feature])
        return f"{n} other claim(s) in the last 12 months" if n else "No other claims in the last 12 months"
    if feature == "customer_tenure_years":
        t = f[feature]
        return f"Customer for {t:.0f} years" if t >= 2 else f"New customer ({t:.1f} years)"
    if feature == "customer_age":
        return f"Customer age {int(f[feature])}"
    if feature == "docs_complete":
        return "All documents submitted" if f[feature] else "Supporting documents incomplete"
    if feature == "is_motor":
        return "Motor claim" if f[feature] else "Health claim"
    if feature in ("channel_agent", "channel_app"):
        return f"Filed via {c['channel']}"
    if feature == "shared_phone_customers":
        n = int(f[feature])
        return f"Phone number shared with {n} other customer(s)" if n else "Phone number not shared"
    if feature == "shared_bank_customers":
        n = int(f[feature])
        return f"Bank account shared with {n} other customer(s)" if n else "Bank account not shared"
    if feature == "network_size":
        n = int(f[feature]) - 1
        return (f"Linked to {n} other customer(s) through shared phones/bank accounts"
                if n else "No links to other customers")
    if feature == "provider_claims_30d":
        return f"{prov} has {int(f[feature])} claims in the last 30 days"
    if feature == "provider_amount_ratio_30d":
        return f"{prov}'s recent bills average {f[feature]:.1f}× typical cost"
    if feature == "provider_night_share_30d":
        return f"{f[feature]:.0%} of {prov}'s recent claims are late-night incidents"
    if feature == "provider_network_share_30d":
        return f"{f[feature]:.0%} of {prov}'s recent claims come from linked customer groups"
    if feature == "agent_claims_30d":
        return f"Agent {c['agent_id']} handled {int(f[feature])} claims in 30 days"
    if feature == "agent_network_share_30d":
        return f"{f[feature]:.0%} of agent {c['agent_id']}'s recent claims come from linked customer groups"
    return f"{feature} = {f[feature]}"


def reason_codes(feats: dict, contribs, features: list[str], claim: dict, labels: dict, k: int = 5):
    """Top risk-raising and risk-lowering factors from SHAP contributions."""
    items = sorted(zip(features, contribs), key=lambda t: -abs(t[1]))
    seen, risk, protective = set(), [], []
    for name, v in items:
        text = describe(name, feats, claim)
        if text in seen or abs(v) < 0.05:
            continue
        seen.add(text)
        entry = {"feature": name, "label": labels.get(name, name), "text": text, "impact": round(float(v), 3)}
        (risk if v > 0 else protective).append(entry)
    return risk[:k], protective[:3]


ACTIONS = {
    "fast_track": "Approve for straight-through payment.",
    "review": "Request one additional document (original bill / photos) before payment.",
    "investigate": "Route to the Special Investigation Unit; hold payment pending verification.",
}

CUSTOMER_MSG = {
    "fast_track": "Good news! Your claim {claim_id} for {amount} is approved. The amount will be credited within 24 hours.",
    "review": "Thank you for filing claim {claim_id}. To complete processing quickly, please upload one more document in the app.",
    "investigate": "Thank you for filing claim {claim_id}. It is going through our standard verification and we will update you within 3 working days.",
}


def template_note(claim: dict, result: dict) -> str:
    risks = "; ".join(r["text"] for r in result["reasons"][:3]) or "no strong risk signals"
    mitig = "; ".join(r["text"] for r in result["protective"][:2])
    note = f"{result['decision_label']} - risk {result['score']:.0f}/100. Key signals: {risks}."
    if mitig:
        note += f" Mitigating: {mitig}."
    return note + f" Next step: {ACTIONS[result['decision']]}"


def customer_message(claim: dict, result: dict) -> str:
    # Responsible AI: customers are never told they are suspected of fraud by a machine.
    return CUSTOMER_MSG[result["decision"]].format(claim_id=claim["claim_id"], amount=inr(claim["claim_amount"]))


def _prompt(claim: dict, result: dict, language: str) -> str:
    facts = "\n".join(f"- {r['text']}" for r in result["reasons"]) or "- none"
    mitig = "\n".join(f"- {r['text']}" for r in result["protective"]) or "- none"
    return (
        "You are an assistant for insurance claim investigators. Write a concise, neutral note "
        f"(max 80 words) in {language}. Do not accuse the customer; describe the risk signals and "
        "recommend the next verification step. Use only the facts given.\n\n"
        f"Claim {claim['claim_id']}: {claim['claim_type']} / {claim['subtype']}, amount {inr(claim['claim_amount'])}.\n"
        f"Risk score: {result['score']:.0f}/100 -> {result['decision_label']}.\n"
        f"Risk signals:\n{facts}\nMitigating factors:\n{mitig}\n"
        f"Policy action: {ACTIONS[result['decision']]}\n\nNote:"
    )


def _post_json(url: str, payload: dict, headers: dict, timeout: float = 30) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _watsonx(prompt: str) -> str:
    key, project = os.environ["WATSONX_APIKEY"], os.environ["WATSONX_PROJECT_ID"]
    url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    model = os.environ.get("WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct")
    body = urllib.parse.urlencode({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": key}).encode()
    tok_req = urllib.request.Request("https://iam.cloud.ibm.com/identity/token", data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(tok_req, timeout=30) as r:
        token = json.loads(r.read())["access_token"]
    out = _post_json(f"{url}/ml/v1/text/generation?version=2024-05-31",
                     {"model_id": model, "project_id": project, "input": prompt,
                      "parameters": {"decoding_method": "greedy", "max_new_tokens": 200}},
                     {"Authorization": f"Bearer {token}"})
    return out["results"][0]["generated_text"].strip()


def _ollama(prompt: str) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "granite3.3:2b")
    out = _post_json(f"{host}/api/generate", {"model": model, "prompt": prompt, "stream": False}, {}, timeout=120)
    return out["response"].strip()


def llm_backend() -> str:
    """'watsonx', 'ollama' or 'template' (offline fallback), from CLAIMGUARD_LLM."""
    return os.environ.get("CLAIMGUARD_LLM", "template").lower()


def investigator_note(claim: dict, result: dict, language: str = "English") -> tuple[str, str]:
    """Returns (note, source). Falls back to a deterministic template if no LLM is reachable."""
    backend = llm_backend()
    try:
        if backend == "watsonx":
            return _watsonx(_prompt(claim, result, language)), "IBM Granite (watsonx.ai)"
        if backend == "ollama":
            return _ollama(_prompt(claim, result, language)), "IBM Granite (local, Ollama)"
    except Exception as e:  # noqa: BLE001
        return template_note(claim, result), f"template (LLM unavailable: {type(e).__name__})"
    return template_note(claim, result), "template"
