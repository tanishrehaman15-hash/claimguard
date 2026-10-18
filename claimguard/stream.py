"""Replay the held-out claim period against the scoring API, like a live feed.

    python -m claimguard.stream --rate 20 --limit 200
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request

import pandas as pd

from . import DATA

FIELDS = ["claim_id", "customer_id", "phone", "bank_account", "claim_type", "subtype", "claim_amount",
          "sum_insured", "policy_age_days", "report_delay_days", "incident_hour", "verified_record",
          "witness_count", "prior_claims_12m", "customer_tenure_years", "customer_age", "docs_complete",
          "channel", "provider_id", "agent_id"]
ICON = {"fast_track": "🟢", "review": "🟡", "investigate": "🔴"}


def main(url: str, rate: float, limit: int) -> None:
    claims = pd.read_csv(DATA / "claims.csv", parse_dates=["ts"], dtype={"phone": str, "bank_account": str})
    live = claims[claims.split == "test"].head(limit)
    lat = []
    for c in live.to_dict("records"):
        body = {k: c[k] for k in FIELDS}
        body["ts"] = c["ts"].isoformat()
        req = urllib.request.Request(f"{url}/v1/claims/score", data=json.dumps(body, default=str).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            res = json.loads(r.read())
        lat.append(res["latency_ms"])
        top = res["reasons"][0]["text"] if res["reasons"] else "-"
        truth = "FRAUD" if c["is_fraud"] else "ok"
        print(f"{ICON[res['decision']]} {res['claim_id']}  ₹{c['claim_amount']:>10,.0f}  "
              f"score {res['score']:5.1f}  [{truth:5}]  {top}")
        time.sleep(1 / rate)
    lat.sort()
    print(f"\nScored {len(lat)} claims · model latency p50 {lat[len(lat) // 2]:.2f} ms · "
          f"p99 {lat[int(len(lat) * 0.99) - 1]:.2f} ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--rate", type=float, default=10, help="claims per second")
    ap.add_argument("--limit", type=int, default=200)
    a = ap.parse_args()
    main(a.url, a.rate, a.limit)
