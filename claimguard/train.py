"""Generate data, build time-ordered features, train, evaluate and export to ONNX.

    python -m claimguard.train
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from . import ARTIFACTS, DATA
from .data import generate
from .features import FEATURE_LABELS, FEATURES, EntityStore, build_features

FAST_TRACK_FRAUD_RECALL = 0.97   # at most ~3% of fraud may slip into the fast lane
INVESTIGATE_PRECISION = 0.80     # investigators should be right 4 times out of 5


def replay_features(claims: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Compute features exactly as the live scorer would: one claim at a time."""
    store = EntityStore.from_customers(customers)
    rows = []
    for claim in claims.to_dict("records"):
        f = build_features(claim, store)
        store.observe(claim, f)
        rows.append(f)
    return pd.DataFrame(rows, columns=FEATURES)


def pick_thresholds(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    t_low = float(np.quantile(p[y == 1], 1 - FAST_TRACK_FRAUD_RECALL))
    t_high = 0.9
    for t in np.linspace(t_low, 0.99, 400):
        sel = p >= t
        if sel.sum() >= 10 and y[sel].mean() >= INVESTIGATE_PRECISION:
            t_high = float(t)
            break
    return round(t_low, 4), round(max(t_high, t_low + 0.05), 4)


def lane_metrics(df: pd.DataFrame, p: np.ndarray, t_low: float, t_high: float) -> dict:
    y = df.is_fraud.values
    amt = df.claim_amount.values
    fast, inv = p < t_low, p >= t_high
    review = ~fast & ~inv
    fraud_value = float(amt[y == 1].sum())
    return {
        "claims": int(len(y)),
        "fraud_rate": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "fast_track_rate": float(fast.mean()),
        "fast_track_fraud_leak": float(y[fast].sum() / max(y.sum(), 1)),
        "review_rate": float(review.mean()),
        "investigate_rate": float(inv.mean()),
        "investigate_precision": float(y[inv].mean()) if inv.any() else 0.0,
        "investigate_recall": float(y[inv].sum() / max(y.sum(), 1)),
        "fraud_value_total_inr": fraud_value,
        "fraud_value_stopped_inr": float(amt[(y == 1) & ~fast].sum()),
        "fraud_value_stopped_share": float(amt[(y == 1) & ~fast].sum() / max(fraud_value, 1)),
    }


def rules_baseline(feats: pd.DataFrame, y: np.ndarray, p: np.ndarray) -> dict:
    """Typical hand-written red-flag rules vs the model at the same alert volume."""
    flag = ((feats.amount_vs_typical > 2.0) | (feats.policy_age_days < 30)
            | ((feats.verified_record == 0) & (feats.is_night == 1))).values
    k = int(flag.sum())
    top = np.zeros_like(flag)
    top[np.argsort(-p)[:k]] = True
    return {
        "alerts": k,
        "rules_precision": float(y[flag].mean()),
        "rules_recall": float(y[flag].sum() / y.sum()),
        "model_precision": float(y[top].mean()),
        "model_recall": float(y[top].sum() / y.sum()),
    }


def export_onnx(model: xgb.XGBClassifier, X_check: np.ndarray, p_check: np.ndarray) -> dict:
    try:
        from onnxmltools import convert_xgboost
        from onnxmltools.convert.common.data_types import FloatTensorType
    except ImportError:
        # e.g. LinuxONE without ONNX wheels: keep serving the native XGBoost model.
        (ARTIFACTS / "claimguard.onnx").unlink(missing_ok=True)
        return {"skipped": "onnxmltools not installed on this platform"}

    onx = convert_xgboost(model, initial_types=[("float_input", FloatTensorType([None, len(FEATURES)]))],
                          target_opset=15)
    path = ARTIFACTS / "claimguard.onnx"
    path.write_bytes(onx.SerializeToString())
    info = {"path": path.name, "size_kb": round(path.stat().st_size / 1024, 1)}
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        probs = sess.run(None, {"float_input": X_check.astype(np.float32)})[1]
        p_onnx = np.array([r[1] for r in probs]) if isinstance(probs, list) else probs[:, 1]
        info["max_abs_diff_vs_xgboost"] = float(np.abs(p_onnx - p_check).max())
    except Exception as e:  # noqa: BLE001
        info["verify_error"] = str(e)
    return info


def main(n_claims: int = 60_000, seed: int = 42) -> dict:
    ARTIFACTS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    t0 = time.time()

    print(f"[1/5] Generating {n_claims:,} synthetic claims ...")
    claims, customers, providers = generate(n_claims, seed)

    print("[2/5] Replaying claims through the real-time feature store ...")
    feats = replay_features(claims, customers)

    n = len(claims)
    i_train, i_val = int(n * 0.7), int(n * 0.8)
    claims["split"] = ["train"] * i_train + ["val"] * (i_val - i_train) + ["test"] * (n - i_val)
    claims.to_csv(DATA / "claims.csv", index=False)
    customers.to_csv(DATA / "customers.csv", index=False)
    providers.to_csv(DATA / "providers.csv", index=False)

    X, y = feats.values.astype(np.float32), claims.is_fraud.values
    Xtr, ytr = X[:i_train], y[:i_train]
    Xva, yva = X[i_train:i_val], y[i_train:i_val]
    Xte, yte = X[i_val:], y[i_val:]

    print("[3/5] Training gradient-boosted model (time-based split, no leakage) ...")
    params = dict(learning_rate=0.05, max_depth=5, subsample=0.85, colsample_bytree=0.85,
                  min_child_weight=3, eval_metric="aucpr", tree_method="hist", random_state=seed)
    probe = xgb.XGBClassifier(n_estimators=1500, early_stopping_rounds=60, **params)
    probe.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
    best_n = int(probe.best_iteration) + 1
    model = xgb.XGBClassifier(n_estimators=best_n, **params)
    model.fit(Xtr, ytr, verbose=False)

    p_val = model.predict_proba(Xva)[:, 1]
    t_low, t_high = pick_thresholds(yva, p_val)
    p_test = model.predict_proba(Xte)[:, 1]
    test = claims.iloc[i_val:]
    metrics = lane_metrics(test, p_test, t_low, t_high)
    baseline = rules_baseline(feats.iloc[i_val:], yte, p_test)

    prec, rec, _ = precision_recall_curve(yte, p_test)
    idx = np.linspace(0, len(prec) - 1, 120).astype(int)
    by_type = (test.assign(p=p_test, caught=p_test >= t_low)
               .query("is_fraud == 1 and fraud_type != 'none'").groupby("fraud_type").caught.mean().round(3).to_dict())

    gain = model.get_booster().get_score(importance_type="gain")
    importance = sorted(((FEATURES[int(k[1:])], v) for k, v in gain.items()), key=lambda kv: -kv[1])

    print("[4/5] Exporting to ONNX (portable model format) ...")
    model.get_booster().save_model(ARTIFACTS / "model.json")
    onnx_info = export_onnx(model, Xte[:2000], p_test[:2000])

    meta = {
        "model": "XGBoost gradient-boosted trees",
        "n_estimators": best_n,
        "features": FEATURES,
        "feature_labels": FEATURE_LABELS,
        "thresholds": {"fast_track": t_low, "investigate": t_high},
        "policy": {"fast_track_fraud_recall": FAST_TRACK_FRAUD_RECALL,
                   "investigate_precision": INVESTIGATE_PRECISION},
        "test_metrics": metrics,
        "rules_baseline": baseline,
        "recall_by_fraud_type": by_type,
        "pr_curve": {"precision": prec[idx].round(4).tolist(), "recall": rec[idx].round(4).tolist()},
        "feature_importance": [[k, round(v, 3)] for k, v in importance],
        "onnx": onnx_info,
        "data": {"claims": n, "train": i_train, "val": i_val - i_train, "test": n - i_val,
                 "seed": seed, "fraud_rate": float(y.mean())},
    }
    (ARTIFACTS / "metadata.json").write_text(json.dumps(meta, indent=2))

    m = metrics
    print(f"[5/5] Done in {time.time() - t0:.0f}s\n")
    print(f"  ROC-AUC {m['roc_auc']:.3f} | PR-AUC {m['pr_auc']:.3f} | fraud rate {m['fraud_rate']:.1%}")
    print(f"  Fast-tracked {m['fast_track_rate']:.1%} of claims, fraud leak {m['fast_track_fraud_leak']:.1%}")
    print(f"  Investigate queue {m['investigate_rate']:.1%} of claims, precision "
          f"{m['investigate_precision']:.1%}, recall {m['investigate_recall']:.1%}")
    print(f"  Fraud value stopped before payout: {m['fraud_value_stopped_share']:.1%}")
    print(f"  Rules baseline precision {baseline['rules_precision']:.1%} vs model "
          f"{baseline['model_precision']:.1%} at {baseline['alerts']:,} alerts")
    print(f"  ONNX: {onnx_info}")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", type=int, default=60_000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(a.claims, a.seed)
