"""REST scoring service - the integration point for the core claims system.

    uvicorn claimguard.api:app --port 8000

On IBM Z the same contract is served by Machine Learning for z/OS (called from
CICS/COBOL) or by this container on LinuxONE.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from . import __version__
from .explain import investigator_note
from .scorer import get_scorer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_scorer()  # warm the model and feature store before taking traffic
    yield


app = FastAPI(title="ClaimGuard", version=__version__, lifespan=lifespan,
              description="Real-time AI risk scoring for insurance claims (IBM Z Datathon)")


class Claim(BaseModel):
    claim_id: str
    ts: datetime = Field(default_factory=datetime.now)
    customer_id: str
    phone: str
    bank_account: str
    claim_type: Literal["motor", "health"]
    subtype: str
    claim_amount: float = Field(gt=0)
    sum_insured: float = Field(gt=0)
    policy_age_days: int = Field(ge=0)
    report_delay_days: float = Field(ge=0)
    incident_hour: int = Field(ge=0, le=23)
    verified_record: int = Field(ge=0, le=1, description="Police report (motor) / pre-authorisation (health)")
    witness_count: int = Field(ge=0)
    prior_claims_12m: int = Field(ge=0)
    customer_tenure_years: float = Field(ge=0)
    customer_age: int = Field(ge=18)
    docs_complete: int = Field(ge=0, le=1)
    channel: Literal["app", "agent", "branch"]
    provider_id: str
    agent_id: str


@app.get("/health")
def health() -> dict:
    s = get_scorer()
    return {"status": "ok", "engine": s.engine, "version": __version__}


@app.get("/v1/model")
def model_info() -> dict:
    m = get_scorer().meta
    return {k: m[k] for k in ("model", "thresholds", "test_metrics", "rules_baseline", "onnx")}


@app.post("/v1/claims/score")
def score(claim: Claim, explain: bool = False, language: str = "English") -> dict:
    s = get_scorer()
    c = claim.model_dump()
    result = s.score(c)
    result.pop("features")
    if explain:
        result["investigator_note"], result["note_source"] = investigator_note(c, result, language)
    return result
