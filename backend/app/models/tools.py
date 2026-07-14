"""Request/response models for the 6 POST /tools/* endpoints.

Field names and required-ness mirror the JSON schemas in
docs/RETELL_AGENT_CONFIG.md SS C exactly - that file is the contract.

Retell's custom-function request body (default payload mode) is
{"name": ..., "call": {"call_id": ..., ...}, "args": {...}} - each tool's
Args model is wrapped in a `<Tool>Call` envelope below so FastAPI can bind
and validate the whole body directly, no manual JSON parsing needed.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class RetellCallMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str | None = None


# --- 1. get_available_listings ---
class GetListingsArgs(BaseModel):
    beds: int | None = None
    max_rent: int | None = None
    pets: bool | None = None
    move_in_by: date | None = None


class GetListingsCall(BaseModel):
    call: RetellCallMeta | None = None
    args: GetListingsArgs = GetListingsArgs()


class ListingOut(BaseModel):
    property_id: str
    label: str
    beds: int | None
    baths: float | None
    rent: int | None
    available_date: date | None
    pets_allowed: bool | None
    pet_policy: str | None
    highlights: str | None
    address: str | None


class GetListingsResponse(BaseModel):
    ok: bool = True
    count: int
    listings: list[ListingOut]


# --- 2. check_tour_slots ---
class CheckTourSlotsArgs(BaseModel):
    property_id: str
    date_preference: str | None = None


class CheckTourSlotsCall(BaseModel):
    call: RetellCallMeta | None = None
    args: CheckTourSlotsArgs


class TourSlotsResponse(BaseModel):
    ok: bool
    property_id: str | None = None
    label: str | None = None
    slots: list[str] = []
    reason: str | None = None


# --- 3. book_tour ---
class BookTourArgs(BaseModel):
    property_id: str
    slot_start_iso: datetime
    prospect_name: str
    prospect_phone: str
    sms_consent: bool = False


class BookTourCall(BaseModel):
    call: RetellCallMeta | None = None
    args: BookTourArgs


class BookTourResponse(BaseModel):
    ok: bool
    booking_id: str | None = None
    label: str | None = None
    address: str | None = None
    slot_start: str | None = None
    next_available_slots: list[str] = []
    reason: str | None = None


# --- 4. create_maintenance_ticket ---
class CreateMaintenanceTicketArgs(BaseModel):
    unit: str
    issue_type: str
    description: str
    callback_number: str
    permission_to_enter: bool | None = None


class CreateMaintenanceTicketCall(BaseModel):
    call: RetellCallMeta | None = None
    args: CreateMaintenanceTicketArgs


class MaintenanceTicketResponse(BaseModel):
    ok: bool
    ticket_id: str | None = None
    reason: str | None = None


# --- 5. escalate_emergency ---
class EscalateEmergencyArgs(BaseModel):
    unit: str
    issue: str
    callback_number: str
    caller_safe: bool | None = None


class EscalateEmergencyCall(BaseModel):
    call: RetellCallMeta | None = None
    args: EscalateEmergencyArgs


class EscalateEmergencyResponse(BaseModel):
    ok: bool
    ticket_id: str | None = None
    notified: bool = False
    reason: str | None = None


# --- 6. take_message ---
class TakeMessageArgs(BaseModel):
    caller_name: str
    callback_number: str
    reason: str
    message: str


class TakeMessageCall(BaseModel):
    call: RetellCallMeta | None = None
    args: TakeMessageArgs


class TakeMessageResponse(BaseModel):
    ok: bool
    message_id: str | None = None
    reason: str | None = None
