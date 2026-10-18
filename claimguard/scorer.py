"""Real-time scoring engine: features -> ONNX inference -> decision -> reasons."""
from __future__ import annotations

import json
import time
from functools import lru_cache

import numpy as np
import pandas as pd
import xgboost as xgb

from . import ARTIFACTS, DATA
from .explain import customer_message, reason_codes
from .features import EntityStore, build_features

DECISION_LABELS = {
    "fast_track": "Fast-track approve",
    "review": "Quick document check",
    "investigate": "Send to investigator",
}


class Scorer:
    def __init__(self, artifacts=ARTIFACTS, data=DATA):
        self.meta = json.loads((artifacts / "metadata.json").read_text())
        self.features = self.meta["features"]
        self.labels = self.meta["feature_labels"]
        self.t_low = self.meta["thresholds"]["fast_track"]
        self.t_high = self.meta["thresholds"]["investigate"]

        # Booster gives exact TreeSHAP reason codes; ONNX is the inference artifact
        # (portable model format). On z/OS the tree model is served by MLz / Snap ML on Telum.
        self.booster = xgb.Booster()
        self.booster.load_model(artifacts / "model.json")
        self.engine = "xgboost"
        try:
            import onnxruntime as ort
            self.sess = ort.InferenceSession(str(artifacts / "claimguard.onnx"), providers=["CPUExecutionProvider"])
            self.input_name = self.sess.get_inputs()[0].name
            self.engine = "onnxruntime"
        except Exception:  # noqa: BLE001
            self.sess = None

        self.claims = pd.read_csv(data / "claims.csv", parse_dates=["ts"], dtype={"phone": str, "bank_account": str})
        self.customers = pd.read_csv(data / "customers.csv", dtype={"phone": str, "bank_account": str})
        self.customers["ring_id"] = self.customers.ring_id.fillna("")
        self.providers = pd.read_csv(data / "providers.csv").set_index("provider_id")
        self.store = EntityStore.from_customers(self.customers)
        # Warm the feature store with history; the held-out test period is "live".
        history = self.claims[self.claims.split != "test"]
        for c in history.to_dict("records"):
            self.store.observe(c, build_features(c, self.store))
        self.live_claims = self.claims[self.claims.split == "test"].to_dict("records")
        self.clock = history.ts.max()

    def _predict(self, x: np.ndarray) -> float:
        if self.sess is not None:
            out = self.sess.run(None, {self.input_name: x})[1]
            return float(out[0][1]) if isinstance(out, list) else float(out[0, 1])
        return float(self.booster.predict(xgb.DMatrix(x))[0])

    def decide(self, p: float) -> str:
        if p < self.t_low:
            return "fast_track"
        return "investigate" if p >= self.t_high else "review"

    def score(self, claim: dict, update_state: bool = True) -> dict:
        claim = dict(claim)
        claim.setdefault("provider_name", self.providers.provider_name.get(claim["provider_id"], claim["provider_id"]))
        t0 = time.perf_counter()
        feats = build_features(claim, self.store)
        x = np.array([[feats[k] for k in self.features]], dtype=np.float32)
        p = self._predict(x)
        latency_ms = (time.perf_counter() - t0) * 1000

        contribs = self.booster.predict(xgb.DMatrix(x), pred_contribs=True)[0][:-1]
        decision = self.decide(p)
        risk, protective = reason_codes(feats, contribs, self.features, claim, self.labels)
        result = {
            "claim_id": claim["claim_id"],
            "score": round(p * 100, 1),
            "probability": p,
            "decision": decision,
            "decision_label": DECISION_LABELS[decision],
            "reasons": risk,
            "protective": protective,
            "features": feats,
            "latency_ms": round(latency_ms, 3),
            "engine": self.engine,
        }
        result["customer_message"] = customer_message(claim, result)
        if update_state:
            self.store.observe(claim, feats)
            self.clock = max(self.clock, pd.Timestamp(claim["ts"]))
        return result

    def demo_ring(self) -> dict:
        """The largest motor fraud ring active in the live period, for the 'file a claim' demo."""
        live = self.claims[(self.claims.split == "test") & (self.claims.fraud_type == "staged_ring")]
        motor = live[live.claim_type == "motor"]
        pick = motor if not motor.empty else live
        ring_id = (self.customers.set_index("customer_id").loc[pick.customer_id, "ring_id"]
                   .value_counts().index[0])
        members = self.customers[self.customers.ring_id == ring_id]
        ring_claims = self.claims[self.claims.customer_id.isin(members.customer_id)
                                  & (self.claims.fraud_type == "staged_ring")]
        m = members.iloc[0]
        return {"ring_id": ring_id, "phone": m.phone, "bank_account": m.bank_account,
                "provider_id": ring_claims.provider_id.mode().iloc[0],
                "agent_id": ring_claims.agent_id.mode().iloc[0],
                "claim_type": ring_claims.claim_type.iloc[0]}


@lru_cache(maxsize=1)
def get_scorer() -> Scorer:
    return Scorer()
