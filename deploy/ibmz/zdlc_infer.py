"""Score claims with the zDLC-compiled model and check parity with ONNX Runtime.

Run on IBM Z / LinuxONE after compile_zdlc.sh. PyRuntime ships with the zDLC
image (or build it from onnx-mlir).

    python deploy/ibmz/zdlc_infer.py artifacts/claimguard.so
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from claimguard import ARTIFACTS, DATA  # noqa: E402
from claimguard.train import replay_features  # noqa: E402

from PyRuntime import OMExecutionSession  # noqa: E402

lib = sys.argv[1] if len(sys.argv) > 1 else str(ARTIFACTS / "claimguard.so")
claims = pd.read_csv(DATA / "claims.csv", parse_dates=["ts"], dtype={"phone": str, "bank_account": str})
customers = pd.read_csv(DATA / "customers.csv", dtype={"phone": str, "bank_account": str})
X = replay_features(claims, customers).values.astype(np.float32)[-1000:]

sess = OMExecutionSession(lib)
t0 = time.perf_counter()
outputs = sess.run([X])
dt = (time.perf_counter() - t0) * 1000
p_z = np.asarray(outputs[-1])[:, 1]

try:
    import onnxruntime as ort
    ref = ort.InferenceSession(str(ARTIFACTS / "claimguard.onnx")).run(None, {"float_input": X})[1]
    ref = np.array([r[1] for r in ref]) if isinstance(ref, list) else ref[:, 1]
    print(f"max |p_zdlc - p_onnxruntime| = {np.abs(p_z - ref).max():.2e}")
except ImportError:
    pass
print(f"Scored {len(X)} claims in {dt:.2f} ms on Telum ({dt / len(X) * 1000:.1f} µs/claim)")
