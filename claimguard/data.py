"""Synthetic motor + health insurance claims with realistic fraud patterns.

Real claims data is confidential, so we simulate an Indian insurer's claim
feed. Fraud mechanisms are modelled on publicly documented indicators
(IRDAI / Insurance Information Bureau of India / NICB red flags):

* opportunistic inflation  - genuine incident, padded bill
* early-policy claims      - policy bought days before the "incident"
* phantom claims           - weak paperwork, no official record, late reporting
* provider billing fraud   - colluding garage/hospital inflates bills
* organised rings          - groups of customers sharing phones / bank accounts,
                             staged late-night incidents, the same colluding
                             provider and agent, claims clustered in time

Distributions deliberately overlap and genuine claims also show red flags
(e.g. honest new policies, families sharing a phone), so the task is not trivial.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import SUBTYPE_WEIGHTS, SUBTYPES, TYPICAL_AMOUNT

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
          "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Indore", "Kochi"]
FIRST = ["Aarav", "Vivaan", "Aditya", "Arjun", "Reyansh", "Ishaan", "Kabir", "Rohan",
         "Rahul", "Vikram", "Siddharth", "Karan", "Priya", "Ananya", "Diya", "Isha",
         "Kavya", "Meera", "Neha", "Pooja", "Riya", "Sneha", "Tanvi", "Zoya", "Imran",
         "Farhan", "Ayesha", "Sana", "Harpreet", "Gurpreet", "Lakshmi", "Suresh",
         "Ramesh", "Anil", "Sunita", "Geeta", "Joseph", "Maria", "Thomas", "Fatima"]
LAST = ["Sharma", "Verma", "Patel", "Shah", "Reddy", "Nair", "Iyer", "Gupta", "Singh",
        "Kumar", "Das", "Bose", "Khan", "Ali", "Mehta", "Joshi", "Rao", "Pillai",
        "Menon", "Chopra", "Kapoor", "Malhotra", "Banerjee", "Mukherjee", "Fernandes",
        "D'Souza", "Gill", "Sandhu", "Yadav", "Mishra"]
GARAGE_WORDS = ["Sai", "Shree", "Balaji", "Ganesh", "Royal", "City", "Express", "Star",
                "National", "Galaxy", "Prime", "Metro"]
HOSPITAL_WORDS = ["Lifeline", "Sunrise", "CarePoint", "Apex", "Nova", "Sanjeevani",
                  "Wellness", "Medicity", "Hope", "Unity", "Arogya", "Trinity"]

START = pd.Timestamp("2025-10-01")
DAYS = 365


def _ids(prefix: str, n: int, width: int = 6) -> list[str]:
    return [f"{prefix}-{i:0{width}d}" for i in range(1, n + 1)]


def _phone(rng) -> str:
    return f"9{rng.integers(100_000_000, 999_999_999)}"


def _bank(rng) -> str:
    return f"AC{rng.integers(10**10, 10**11)}"


def make_customers(rng, n: int) -> pd.DataFrame:
    df = pd.DataFrame({
        "customer_id": _ids("CUS", n),
        "name": [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(n)],
        "customer_age": rng.integers(21, 76, n),
        "customer_tenure_years": np.clip(np.round(rng.gamma(2.0, 2.3, n), 1), 0, 30),
        "city": rng.choice(CITIES, n),
        "phone": [_phone(rng) for _ in range(n)],
        "bank_account": [_bank(rng) for _ in range(n)],
        "ring_id": "",
    })
    # Honest households share a phone or joint account (noise for network features).
    k = int(n * 0.08)
    a = rng.choice(n, k, replace=False)
    b = rng.choice(n, k, replace=False)
    for i, j in zip(a, b):
        if i == j:
            continue
        if rng.random() < 0.6:
            df.at[j, "phone"] = df.at[i, "phone"]
        else:
            df.at[j, "bank_account"] = df.at[i, "bank_account"]
    return df


def make_providers(rng, n_garages: int = 420, n_hospitals: int = 260) -> pd.DataFrame:
    rows = []
    for i in range(n_garages):
        rows.append((f"GAR-{i + 1:04d}", f"{rng.choice(GARAGE_WORDS)} Motors {i + 1}",
                     "motor", rng.choice(CITIES), rng.random() < 0.05))
    for i in range(n_hospitals):
        rows.append((f"HOS-{i + 1:04d}", f"{rng.choice(HOSPITAL_WORDS)} Hospital {i + 1}",
                     "health", rng.choice(CITIES), rng.random() < 0.05))
    return pd.DataFrame(rows, columns=["provider_id", "provider_name", "provider_type",
                                       "city", "colluding"])


def make_rings(rng, customers: pd.DataFrame, providers: pd.DataFrame, agents: list[str],
               n_rings: int) -> dict[str, dict]:
    rings = {}
    pool = rng.permutation(len(customers))
    pos = 0
    for r in range(n_rings):
        size = int(rng.integers(3, 12))
        members = pool[pos:pos + size]
        pos += size
        claim_type = "motor" if rng.random() < 0.6 else "health"
        cands = providers[(providers.provider_type == claim_type) & providers.colluding]
        if cands.empty:
            cands = providers[providers.provider_type == claim_type]
        ring = {
            "ring_id": f"RING-{r + 1:03d}",
            "claim_type": claim_type,
            "provider_id": cands.provider_id.iloc[int(rng.integers(len(cands)))],
            "agent_id": str(rng.choice(agents)),
            "start_day": float(rng.uniform(0, DAYS - 50)),
            "phones": [_phone(rng) for _ in range(int(rng.integers(1, 3)))],
            "banks": [_bank(rng) for _ in range(int(rng.integers(1, 3)))],
        }
        for idx in members:
            share_phone = rng.random() < 0.65
            share_bank = rng.random() < 0.6 or not share_phone
            if share_phone:
                customers.at[idx, "phone"] = rng.choice(ring["phones"])
            if share_bank:
                customers.at[idx, "bank_account"] = rng.choice(ring["banks"])
            customers.at[idx, "ring_id"] = ring["ring_id"]
            rings[customers.at[idx, "customer_id"]] = ring
    return rings


def _base_claim(rng, claim_type: str) -> dict:
    subtype = rng.choice(SUBTYPES[claim_type], p=SUBTYPE_WEIGHTS[claim_type])
    typical = TYPICAL_AMOUNT[(claim_type, subtype)]
    amount = typical * rng.lognormal(0, 0.45)
    sum_insured = round(typical * rng.uniform(3, 10), -4)
    policy_age = int(rng.integers(30, 1800))
    if rng.random() < 0.06:  # honest claims on brand-new policies exist
        policy_age = int(rng.integers(1, 30))
    if claim_type == "motor":
        hour = int(rng.normal(14, 4.5)) % 24
        verified_p = {"theft": 0.92, "collision": 0.65, "flood": 0.5,
                      "windscreen": 0.25, "third_party": 0.85}[subtype]
        witnesses = int(rng.poisson(1.0))
    else:
        hour = int(rng.integers(0, 24))
        verified_p = 0.72
        witnesses = 0
    return {
        "claim_type": claim_type,
        "subtype": subtype,
        "claim_amount": amount,
        "sum_insured": sum_insured,
        "policy_age_days": policy_age,
        "report_delay_days": round(float(rng.gamma(1.5, 1.2)), 1),
        "incident_hour": hour,
        "verified_record": int(rng.random() < verified_p),
        "witness_count": witnesses,
        "prior_claims_12m": int(rng.poisson(0.25)),
        "docs_complete": int(rng.random() < 0.94),
        "channel": rng.choice(["app", "agent", "branch"], p=[0.5, 0.32, 0.18]),
    }


def _apply_fraud(rng, c: dict, fraud_type: str) -> None:
    if fraud_type == "inflation":
        c["claim_amount"] *= rng.uniform(1.5, 3.2)
        c["docs_complete"] = int(rng.random() < 0.8)
    elif fraud_type == "early_policy":
        c["policy_age_days"] = int(rng.integers(1, 45))
        c["claim_amount"] *= rng.uniform(1.0, 1.8)
        c["report_delay_days"] = round(float(rng.gamma(2.0, 2.0)), 1)
    elif fraud_type == "phantom":
        c["docs_complete"] = int(rng.random() < 0.5)
        c["verified_record"] = int(rng.random() < 0.3)
        c["report_delay_days"] = round(float(rng.gamma(3.0, 3.0)), 1)
        c["claim_amount"] *= rng.uniform(1.0, 1.6)
    elif fraud_type == "provider_billing":
        c["claim_amount"] *= rng.uniform(1.4, 2.8)
        c["verified_record"] = int(rng.random() < 0.6)
    elif fraud_type == "staged_ring":
        c["incident_hour"] = int(rng.normal(23, 2.5)) % 24
        c["verified_record"] = int(rng.random() < 0.3)
        c["witness_count"] = int(rng.integers(1, 5)) if c["claim_type"] == "motor" else 0
        c["claim_amount"] *= rng.uniform(1.2, 2.4)
        c["policy_age_days"] = int(rng.integers(5, 400))
        c["prior_claims_12m"] = int(rng.poisson(1.1))
        c["channel"] = "agent" if rng.random() < 0.7 else c["channel"]


def generate(n_claims: int = 60_000, seed: int = 42, n_rings: int = 75):
    rng = np.random.default_rng(seed)
    customers = make_customers(rng, int(n_claims * 0.7))
    providers = make_providers(rng)
    agents = _ids("AGT", 300, 4)
    rings = make_rings(rng, customers, providers, agents, n_rings)

    cust = customers.set_index("customer_id")
    by_type = {t: providers[providers.provider_type == t].reset_index(drop=True)
               for t in ("motor", "health")}

    ring_claimants = []
    for cid in rings:
        ring_claimants += [cid] * int(rng.integers(1, 4))
    n_regular = n_claims - len(ring_claimants)
    regular = list(rng.choice(customers.customer_id.values, n_regular))

    rows = []
    for cid in ring_claimants + regular:
        ring = rings.get(cid)
        info = cust.loc[cid]
        if ring is not None and rng.random() < 0.75:
            fraud_type = "staged_ring"
            c = _base_claim(rng, ring["claim_type"])
            provider_id, agent_id = ring["provider_id"], ring["agent_id"]
            day = ring["start_day"] + rng.uniform(0, 45)
        else:
            ctype = "motor" if rng.random() < 0.55 else "health"
            c = _base_claim(rng, ctype)
            prov = by_type[ctype].iloc[int(rng.integers(len(by_type[ctype])))]
            provider_id, agent_id = prov.provider_id, rng.choice(agents)
            day = rng.uniform(0, DAYS)
            if prov.colluding and rng.random() < 0.3:
                fraud_type = "provider_billing"
            elif rng.random() < 0.04:
                fraud_type = rng.choice(["inflation", "early_policy", "phantom"], p=[0.5, 0.3, 0.2])
            else:
                fraud_type = "none"
        if fraud_type != "none":
            _apply_fraud(rng, c, fraud_type)

        c["claim_amount"] = float(round(min(c["claim_amount"], 0.98 * c["sum_insured"]), -2))
        c.update({
            "ts": START + pd.Timedelta(days=float(day)),
            "customer_id": cid,
            "customer_name": info["name"],
            "customer_age": int(info["customer_age"]),
            "customer_tenure_years": float(info["customer_tenure_years"]),
            "city": info["city"],
            "phone": info["phone"],
            "bank_account": info["bank_account"],
            "provider_id": provider_id,
            "agent_id": agent_id,
            "fraud_type": fraud_type,
            "is_fraud": int(fraud_type != "none"),
        })
        rows.append(c)

    claims = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
    # 0.5% label noise: real investigation outcomes are imperfect.
    flip = rng.random(len(claims)) < 0.005
    claims.loc[flip, "is_fraud"] = 1 - claims.loc[flip, "is_fraud"]
    claims.insert(0, "claim_id", _ids("CLM", len(claims), 7))
    return claims, customers, providers
