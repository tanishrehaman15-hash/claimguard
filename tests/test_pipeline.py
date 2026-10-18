"""Smoke tests. Run after `./run.sh train`."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from claimguard import ARTIFACTS
from claimguard.data import generate
from claimguard.explain import inr
from claimguard.features import FEATURES, EntityStore, build_features

pytestmark = pytest.mark.skipif(not (ARTIFACTS / "metadata.json").exists(), reason="run ./run.sh train first")


def test_generator_and_features_are_consistent():
    claims, customers, _ = generate(n_claims=2_000, seed=1, n_rings=5)
    assert claims.ts.is_monotonic_increasing
    assert 0.02 < claims.is_fraud.mean() < 0.2
    store = EntityStore.from_customers(customers)
    f = build_features(claims.iloc[0].to_dict(), store)
    assert list(f) == FEATURES


def test_rolling_window_uses_only_the_past():
    store = EntityStore()
    base = dict(customer_id="C1", phone="p", bank_account="b", claim_type="motor", subtype="collision",
                claim_amount=45_000, sum_insured=500_000, policy_age_days=100, report_delay_days=1,
                incident_hour=12, verified_record=1, witness_count=0, prior_claims_12m=0,
                customer_tenure_years=3, customer_age=40, docs_complete=1, channel="app",
                provider_id="G1", agent_id="A1")
    for day in range(5):
        c = {**base, "ts": pd.Timestamp("2026-01-01") + pd.Timedelta(days=day)}
        f = build_features(c, store)
        assert f["provider_claims_30d"] == day
        store.observe(c, f)
    later = {**base, "ts": pd.Timestamp("2026-03-01")}
    assert build_features(later, store)["provider_claims_30d"] == 0


def test_shared_identity_links_customers():
    store = EntityStore()
    store.register_customer("A", "111", "x")
    store.register_customer("B", "111", "y")
    store.register_customer("C", "222", "y")
    assert store.network_features("C", "222", "y")["network_size"] == 3


def test_inr_format():
    assert inr(1234567) == "₹12,34,567"
    assert inr(999) == "₹999"


def test_api_scores_live_claim():
    from claimguard.api import app
    from claimguard.scorer import get_scorer

    s = get_scorer()
    c = s.live_claims[0]
    body = {k: c[k] for k in ["claim_id", "customer_id", "phone", "bank_account", "claim_type", "subtype",
                              "claim_amount", "sum_insured", "policy_age_days", "report_delay_days",
                              "incident_hour", "verified_record", "witness_count", "prior_claims_12m",
                              "customer_tenure_years", "customer_age", "docs_complete", "channel",
                              "provider_id", "agent_id"]}
    body["ts"] = c["ts"].isoformat()
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        r = client.post("/v1/claims/score?explain=true", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        assert 0 <= out["score"] <= 100
        assert out["decision"] in {"fast_track", "review", "investigate"}
        assert out["investigator_note"]


def test_ring_claim_scores_higher_than_genuine():
    from claimguard.scorer import get_scorer

    s = get_scorer()
    ring = s.demo_ring()
    common = dict(ts=s.clock, claim_type="motor", subtype="collision", sum_insured=600_000, channel="app",
                  customer_age=35, agent_id="AGT-0042")
    genuine = s.score({**common, "claim_id": "T1", "customer_id": "CUS-T1", "phone": "9000000001",
                       "bank_account": "AC1", "claim_amount": 18_000, "policy_age_days": 900,
                       "report_delay_days": 0.5, "incident_hour": 11, "verified_record": 1, "witness_count": 1,
                       "prior_claims_12m": 0, "customer_tenure_years": 6, "docs_complete": 1,
                       "provider_id": "GAR-0001"}, update_state=False)
    fraud = s.score({**common, "claim_id": "T2", "customer_id": "CUS-T2", "phone": ring["phone"],
                     "bank_account": ring["bank_account"], "claim_amount": 240_000, "policy_age_days": 9,
                     "report_delay_days": 6, "incident_hour": 23, "verified_record": 0, "witness_count": 3,
                     "prior_claims_12m": 1, "customer_tenure_years": 0.2, "docs_complete": 0,
                     "provider_id": ring["provider_id"], "agent_id": ring["agent_id"]}, update_state=False)
    assert genuine["decision"] == "fast_track"
    assert fraud["decision"] == "investigate"
