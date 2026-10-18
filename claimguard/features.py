"""Feature engineering and the real-time entity store.

The same `build_features` + `EntityStore.observe` pair is used for training
(replaying history in time order) and for live scoring, so there is no
train/serve skew: a feature can only use information that existed *before*
the claim arrived.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque

import pandas as pd

# Reference tariff: typical settled cost (INR) per claim type / subtype.
# In production this comes from the insurer's actuarial tables.
SUBTYPES = {
    "motor": ["collision", "theft", "windscreen", "flood", "third_party"],
    "health": ["day_care", "surgery", "maternity", "accident", "cardiac"],
}
SUBTYPE_WEIGHTS = {
    "motor": [0.45, 0.08, 0.22, 0.07, 0.18],
    "health": [0.30, 0.25, 0.15, 0.18, 0.12],
}
TYPICAL_AMOUNT = {
    ("motor", "collision"): 45_000,
    ("motor", "theft"): 260_000,
    ("motor", "windscreen"): 9_000,
    ("motor", "flood"): 90_000,
    ("motor", "third_party"): 60_000,
    ("health", "day_care"): 32_000,
    ("health", "surgery"): 185_000,
    ("health", "maternity"): 70_000,
    ("health", "accident"): 95_000,
    ("health", "cardiac"): 320_000,
}

WINDOW_SECONDS = 30 * 24 * 3600
NETWORK_RING_SIZE = 3  # customers linked to >=2 others count as a "linked group"

FEATURES = [
    "log_claim_amount",
    "amount_vs_typical",
    "amount_to_sum_insured",
    "policy_age_days",
    "report_delay_days",
    "incident_hour",
    "is_night",
    "is_weekend",
    "verified_record",
    "witness_count",
    "prior_claims_12m",
    "customer_tenure_years",
    "customer_age",
    "docs_complete",
    "is_motor",
    "channel_agent",
    "channel_app",
    "shared_phone_customers",
    "shared_bank_customers",
    "network_size",
    "provider_claims_30d",
    "provider_amount_ratio_30d",
    "provider_night_share_30d",
    "provider_network_share_30d",
    "agent_claims_30d",
    "agent_network_share_30d",
]

FEATURE_LABELS = {
    "log_claim_amount": "Claim value",
    "amount_vs_typical": "Amount vs typical cost",
    "amount_to_sum_insured": "Share of sum insured",
    "policy_age_days": "Policy age",
    "report_delay_days": "Reporting delay",
    "incident_hour": "Incident hour",
    "is_night": "Late-night incident",
    "is_weekend": "Weekend filing",
    "verified_record": "Police report / pre-authorisation",
    "witness_count": "Witnesses",
    "prior_claims_12m": "Prior claims (12m)",
    "customer_tenure_years": "Customer tenure",
    "customer_age": "Customer age",
    "docs_complete": "Documents complete",
    "is_motor": "Motor claim",
    "channel_agent": "Filed via agent",
    "channel_app": "Filed via app",
    "shared_phone_customers": "Shared phone number",
    "shared_bank_customers": "Shared bank account",
    "network_size": "Linked-customer network",
    "provider_claims_30d": "Provider claim spike",
    "provider_amount_ratio_30d": "Provider billing level",
    "provider_night_share_30d": "Provider late-night share",
    "provider_network_share_30d": "Provider linked-group share",
    "agent_claims_30d": "Agent claim volume",
    "agent_network_share_30d": "Agent linked-group share",
}


def to_seconds(ts) -> float:
    return pd.Timestamp(ts).timestamp()


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}
        self.size: dict[str, int] = {}

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1

    def find(self, x: str) -> str:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]

    def component_size(self, x: str) -> int:
        return self.size[self.find(x)]


class EntityStore:
    """In-memory, low-latency state that real-time features are computed from.

    * Identity graph: customers linked by shared phone numbers / bank accounts
      (union-find, O(1) amortised) -> exposes organised fraud rings.
    * Rolling 30-day windows per provider (garage/hospital) and per agent.

    On IBM Z this state lives next to the transaction (Db2 for z/OS / in-memory
    cache), so no customer data leaves the platform to compute features.
    """

    def __init__(self):
        self.uf = _UnionFind()
        self.phone_to_customers: dict[str, set[str]] = defaultdict(set)
        self.bank_to_customers: dict[str, set[str]] = defaultdict(set)
        self.customer_kyc: dict[str, tuple[str, str]] = {}
        self.provider_hist: dict[str, deque] = defaultdict(deque)
        self.agent_hist: dict[str, deque] = defaultdict(deque)

    @classmethod
    def from_customers(cls, customers: pd.DataFrame) -> "EntityStore":
        store = cls()
        for row in customers.itertuples(index=False):
            store.register_customer(row.customer_id, row.phone, row.bank_account)
        return store

    def register_customer(self, customer_id: str, phone: str, bank: str) -> None:
        if self.customer_kyc.get(customer_id) == (phone, bank):
            return
        self.customer_kyc[customer_id] = (phone, bank)
        self.uf.add(customer_id)
        for linked in (self.phone_to_customers[phone] | self.bank_to_customers[bank]):
            self.uf.union(customer_id, linked)
        self.phone_to_customers[phone].add(customer_id)
        self.bank_to_customers[bank].add(customer_id)

    def network_features(self, customer_id: str, phone: str, bank: str) -> dict:
        self.register_customer(customer_id, phone, bank)
        return {
            "shared_phone_customers": len(self.phone_to_customers[phone]) - 1,
            "shared_bank_customers": len(self.bank_to_customers[bank]) - 1,
            "network_size": self.uf.component_size(customer_id),
        }

    @staticmethod
    def _window(hist: deque, now: float) -> deque:
        while hist and now - hist[0][0] > WINDOW_SECONDS:
            hist.popleft()
        return hist

    def provider_features(self, provider_id: str, now: float) -> dict:
        h = self._window(self.provider_hist[provider_id], now)
        n = len(h)
        return {
            "provider_claims_30d": n,
            "provider_amount_ratio_30d": sum(e[1] for e in h) / n if n else 1.0,
            "provider_night_share_30d": sum(e[2] for e in h) / n if n else 0.0,
            "provider_network_share_30d": sum(e[3] for e in h) / n if n else 0.0,
        }

    def agent_features(self, agent_id: str, now: float) -> dict:
        h = self._window(self.agent_hist[agent_id], now)
        n = len(h)
        return {
            "agent_claims_30d": n,
            "agent_network_share_30d": sum(e[1] for e in h) / n if n else 0.0,
        }

    def observe(self, claim: dict, feats: dict) -> None:
        """Update rolling state *after* a claim has been scored."""
        now = to_seconds(claim["ts"])
        linked = 1.0 if feats["network_size"] >= NETWORK_RING_SIZE else 0.0
        self.provider_hist[claim["provider_id"]].append(
            (now, feats["amount_vs_typical"], feats["is_night"], linked)
        )
        self.agent_hist[claim["agent_id"]].append((now, linked))


def build_features(claim: dict, store: EntityStore) -> dict:
    ts = pd.Timestamp(claim["ts"])
    now = ts.timestamp()
    typical = TYPICAL_AMOUNT[(claim["claim_type"], claim["subtype"])]
    amount = float(claim["claim_amount"])
    hour = int(claim["incident_hour"])

    f = {
        "log_claim_amount": math.log1p(amount),
        "amount_vs_typical": amount / typical,
        "amount_to_sum_insured": amount / max(float(claim["sum_insured"]), 1.0),
        "policy_age_days": float(claim["policy_age_days"]),
        "report_delay_days": float(claim["report_delay_days"]),
        "incident_hour": hour,
        "is_night": 1.0 if (hour >= 22 or hour <= 4) else 0.0,
        "is_weekend": 1.0 if ts.dayofweek >= 5 else 0.0,
        "verified_record": float(claim["verified_record"]),
        "witness_count": float(claim["witness_count"]),
        "prior_claims_12m": float(claim["prior_claims_12m"]),
        "customer_tenure_years": float(claim["customer_tenure_years"]),
        "customer_age": float(claim["customer_age"]),
        "docs_complete": float(claim["docs_complete"]),
        "is_motor": 1.0 if claim["claim_type"] == "motor" else 0.0,
        "channel_agent": 1.0 if claim["channel"] == "agent" else 0.0,
        "channel_app": 1.0 if claim["channel"] == "app" else 0.0,
    }
    f.update(store.network_features(claim["customer_id"], claim["phone"], claim["bank_account"]))
    f.update(store.provider_features(claim["provider_id"], now))
    f.update(store.agent_features(claim["agent_id"], now))
    return f
