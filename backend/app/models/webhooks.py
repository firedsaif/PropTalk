"""Shape of the Retell webhook payload (call_started / call_ended / call_analyzed).
Only the fields we use are typed; everything else is ignored.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RetellCallAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    call_summary: str | None = None
    custom_analysis_data: dict | None = None


class RetellCall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    call_id: str
    from_number: str | None = None
    start_timestamp: int | None = None
    end_timestamp: int | None = None
    duration_ms: int | None = None
    transcript: str | None = None
    recording_url: str | None = None
    disconnection_reason: str | None = None
    call_analysis: RetellCallAnalysis | None = None


class RetellWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event: str
    call: RetellCall
