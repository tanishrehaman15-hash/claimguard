# Deploying ClaimGuard on IBM Z / LinuxONE

The model is trained once and exported to **ONNX** (`artifacts/claimguard.onnx`). That single artifact feeds both IBM Z deployment paths:

```
            ┌── Path A: z/OS ── Machine Learning for z/OS ── CICS/COBOL claims app (in-transaction)
ONNX model ─┤
            └── Path B: LinuxONE ── ClaimGuard API + dashboard (running today; Secure Execution in production)
                                       both run on the Telum on-chip AI accelerator (NNPA)
```

## ✅ Live deployment: IBM LinuxONE (s390x, RHEL 9.8)

ClaimGuard is **trained and served on a real IBM LinuxONE virtual server**: the dashboard runs on `:80` (via nginx) / `:8501`, and the scoring API on `:8000`, as systemd services (`linuxone_services.sh`).

| Check on s390x | Result |
|---|---|
| Training (60k claims, 26 features) | 25 s, ROC-AUC 0.907, 99.0% of fraud value stopped (same as x86) |
| Smoke tests | 6/6 pass |
| Live scoring latency | ~0.4–1 ms per claim (XGBoost, 3 vCPUs) |

**How the stack was built on s390x.** PyPI has no s390x wheels for the scientific stack, so:
- numpy/scipy base from RHEL (`python3.12-scipy`); numpy 1.26.4, pandas 2.2.3, scikit-learn 1.5.2 and XGBoost 2.1.4 compiled from source (`gcc-c++ gcc-gfortran cmake openblas-devel`).
- Apache Arrow 17 C++ (compute, IPC, CSV, JSON, filesystem) plus pyarrow compiled from source with Cython 3.0 (Streamlit needs pyarrow).
- ONNX Runtime has no s390x build, so the scorer automatically serves the native XGBoost model with identical predictions.

**Big-endian fixes (IBM Z is big-endian).** Browser-side libraries assume little-endian binary data, so on s390x the dashboard renders tables as HTML instead of Arrow grids, and sends Plotly arrays as JSON lists instead of base64 buffers (`dashboard/app.py`, `BIG_ENDIAN`).

**SELinux.** systemd needs `chcon -R -t bin_t .venv/bin` to execute the venv interpreter from a home directory.

**Public HTTPS link.** The cloud network blocks inbound web ports, so a `claimguard-tunnel` systemd service runs a Cloudflare quick tunnel from the server (outbound only) to nginx on `:80`. cloudflared has no official s390x release, so it was compiled from source with Go (`GOTOOLCHAIN=auto GOFLAGS=-mod=mod CGO_ENABLED=0 go build ./cmd/cloudflared`). The `*.trycloudflare.com` address changes if the service restarts; get the current one with:

```bash
sudo journalctl -u claimguard-tunnel --no-pager | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1
```

## Path B: LinuxONE (e.g. IBM LinuxONE Community Cloud, s390x)

### 1. Run the whole app unchanged on s390x

All dependencies publish s390x wheels or build from source, and the Dockerfile uses a multi-arch base image.

```bash
git clone <your-repo> && cd claimguard
docker build -f deploy/ibmz/Dockerfile -t claimguard .
docker run -p 8000:8000 -p 8501:8501 claimguard
```

### 2. (Neural-network variants) Compile with the IBM Z Deep Learning Compiler

zDLC targets deep-learning ONNX graphs; for our gradient-boosted trees the recommended Telum path is Machine Learning for z/OS / IBM Snap ML (Path A). The script below is for a future neural model and may not support tree-ensemble operators.

```bash
./deploy/ibmz/compile_zdlc.sh            # produces artifacts/claimguard.so
```

The script runs the zDLC container from the IBM Z and LinuxONE Container Registry (`icr.io/ibmz/zdlc`) with `--maccel=NNPA`, so supported operations are offloaded to the on-chip AI accelerator on z16/z17 and LinuxONE 4/5.

### 3. Serve the compiled model

`zdlc_infer.py` loads the compiled library with zDLC's `PyRuntime` and checks it against ONNX Runtime:

```bash
python deploy/ibmz/zdlc_infer.py artifacts/claimguard.so
```

To use it in production, point `Scorer._predict` at `OMExecutionSession`. The feature store, decision policy and explanations are unchanged.

### 4. Protect it

- Run the container as an **IBM Secure Execution for Linux** guest / **Hyper Protect Virtual Server** so claim data and the model stay encrypted, even from administrators.
- Keep TLS keys and model-signing keys in **Crypto Express HSM** (and use quantum-safe algorithms where available).

## Path A: z/OS with Machine Learning for z/OS (MLz)

1. Import the trained model into **MLz**. For tree ensembles use **IBM Snap ML** (`snapml.BoostingMachineClassifier` can import XGBoost models), whose inference uses the Telum on-chip AI accelerator.
2. Deploy it as an online scoring service.
3. From the CICS/COBOL claims transaction, call the MLz scoring service with the 26-feature vector **before the claim is committed**. Features come from Db2 for z/OS tables that mirror `EntityStore` (identity links + 30-day provider/agent aggregates, maintained by triggers or the claims app).
4. The CICS transaction applies the thresholds from `artifacts/metadata.json` and writes the decision and top reason codes back with the claim record.
5. The Granite explanation service (LinuxONE / watsonx.ai) is called **asynchronously** only for flagged claims, so the core transaction is never slowed down by GenAI.

**Why on-platform matters:** the insurer's claims system of record already runs on IBM Z. Scoring there means 100% of claims are scored synchronously, with no copies of medical or financial data shipped to an external AI service, and with the platform's availability and pervasive encryption.

## Training with IBM Snap ML (optional)

On LinuxONE, `snapml.BoostingMachineClassifier` can replace XGBoost in `train.py` for accelerated training. It also exports to ONNX, so the rest of the pipeline is unchanged.
