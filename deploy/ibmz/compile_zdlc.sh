#!/usr/bin/env bash
# Compile the ONNX model for the IBM Telum on-chip AI accelerator with the IBM Z Deep Learning Compiler.
# Run on an IBM Z / LinuxONE (s390x) host with Docker or Podman.
# Pick the current zDLC tag from the IBM Z and LinuxONE Container Registry (icr.io/ibmz/zdlc).
set -euo pipefail
cd "$(dirname "$0")/../.."

ZDLC_IMAGE="${ZDLC_IMAGE:-icr.io/ibmz/zdlc:latest}"
ENGINE="${ENGINE:-$(command -v podman || command -v docker)}"

"$ENGINE" run --rm -v "$PWD/artifacts":/workdir:z "$ZDLC_IMAGE" \
  --EmitLib --O3 --mcpu=z16 --maccel=NNPA \
  -o /workdir/claimguard /workdir/claimguard.onnx

echo "Compiled: artifacts/claimguard.so (NNPA-accelerated)"
