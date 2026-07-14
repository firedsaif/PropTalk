"""The 6 POST /tools/* endpoints Retell's custom functions call mid-call.

Every route is a plain `def` (FastAPI runs sync path operations in its worker
threadpool, so the blocking psycopg calls inside never block the event loop -
see app/db.py). Each route: resolves client_id (query param, 404 if unknown),
takes the Retell function-call envelope as a typed body, does the DB work on
one connection, and logs {tool, latency_ms, ok, reason} via timed_tool.
See docs/rules.md SS9 for the per-tool definition of done.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.db import get_pooled_connection
from app.deps import resolve_client
from app.logging import timed_tool
from app.models.tools import (
    BookTourCall,
    BookTourResponse,
    CheckTourSlotsCall,
    CreateMaintenanceTicketCall,
    EscalateEmergencyCall,
    EscalateEmergencyResponse,
    GetListingsCall,
    GetListingsResponse,
    MaintenanceTicketResponse,
    TakeMessageCall,
    TakeMessageResponse,
    TourSlotsResponse,
)
from app.services import maintenance, messages
from app.services.escalation import create_emergency_ticket
from app.services.listings import search_listings
from app.services.tours import book_tour as book_tour_service
from app.services.tours import get_property, list_open_slots

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/get_available_listings", response_model=GetListingsResponse)
def get_available_listings(body: GetListingsCall, client_id: str = Query(...)):
    retell_call_id = body.call.call_id if body.call else None
    with timed_tool("get_available_listings", client_id=client_id, retell_call_id=retell_call_id) as ctx:
        with get_pooled_connection() as conn:
            resolve_client(conn, client_id)
            args = body.args
            rows = search_listings(
                conn, client_id, beds=args.beds, max_rent=args.max_rent, pets=args.pets, move_in_by=args.move_in_by
            )
        ctx["ok"] = True
        ctx["reason"] = None if rows else "no_matches"
        return GetListingsResponse(count=len(rows), listings=rows)


@router.post("/check_tour_slots", response_model=TourSlotsResponse)
def check_tour_slots(body: CheckTourSlotsCall, client_id: str = Query(...)):
    retell_call_id = body.call.call_id if body.call else None
    with timed_tool("check_tour_slots", client_id=client_id, retell_call_id=retell_call_id) as ctx:
        args = body.args
        with get_pooled_connection() as conn:
            resolve_client(conn, client_id)
            prop = get_property(conn, client_id, args.property_id)
            if prop is None:
                ctx["reason"] = "not_found"
                return TourSlotsResponse(ok=False, reason="not_found")
            if prop["status"] != "available":
                ctx["reason"] = "not_available"
                return TourSlotsResponse(ok=False, reason="not_available")

            slots = list_open_slots(conn, args.property_id, prop["timezone"], args.date_preference)
        if not slots:
            ctx["reason"] = "no_slots"
            return TourSlotsResponse(ok=False, reason="no_slots", property_id=args.property_id, label=prop["label"])

        ctx["ok"] = True
        return TourSlotsResponse(
            ok=True,
            property_id=args.property_id,
            label=prop["label"],
            slots=[s.isoformat() for s in slots],
        )


@router.post("/book_tour", response_model=BookTourResponse)
def book_tour(body: BookTourCall, client_id: str = Query(...)):
    retell_call_id = body.call.call_id if body.call else None
    with timed_tool("book_tour", client_id=client_id, retell_call_id=retell_call_id) as ctx:
        args = body.args
        with get_pooled_connection() as conn:
            resolve_client(conn, client_id)
            prop = get_property(conn, client_id, args.property_id)
            if prop is None:
                ctx["reason"] = "not_found"
                return BookTourResponse(ok=False, reason="not_found")
            if prop["status"] != "available":
                ctx["reason"] = "not_available"
                return BookTourResponse(ok=False, reason="not_available")

            result = book_tour_service(
                conn,
                client_id=client_id,
                retell_call_id=retell_call_id,
                property_id=args.property_id,
                slot_start=args.slot_start_iso,
                prospect_name=args.prospect_name,
                prospect_phone=args.prospect_phone,
                sms_consent=args.sms_consent,
            )
            if not result["ok"]:
                ctx["reason"] = "slot_taken"
                next_slots = list_open_slots(conn, args.property_id, prop["timezone"])
                return BookTourResponse(
                    ok=False, reason="slot_taken", next_available_slots=[s.isoformat() for s in next_slots]
                )

        ctx["ok"] = True
        return BookTourResponse(
            ok=True,
            booking_id=result["booking_id"],
            label=prop["label"],
            address=prop["address"],
            slot_start=args.slot_start_iso.isoformat(),
        )


@router.post("/create_maintenance_ticket", response_model=MaintenanceTicketResponse)
def create_maintenance_ticket(body: CreateMaintenanceTicketCall, client_id: str = Query(...)):
    retell_call_id = body.call.call_id if body.call else None
    with timed_tool("create_maintenance_ticket", client_id=client_id, retell_call_id=retell_call_id) as ctx:
        args = body.args
        with get_pooled_connection() as conn:
            resolve_client(conn, client_id)
            ticket_id = maintenance.create_ticket(
                conn,
                client_id=client_id,
                unit=args.unit,
                issue_type=args.issue_type,
                description=args.description,
                callback_number=args.callback_number,
                permission_to_enter=args.permission_to_enter,
            )
        ctx["ok"] = True
        return MaintenanceTicketResponse(ok=True, ticket_id=ticket_id)


@router.post("/escalate_emergency", response_model=EscalateEmergencyResponse)
def escalate_emergency(body: EscalateEmergencyCall, client_id: str = Query(...)):
    retell_call_id = body.call.call_id if body.call else None
    with timed_tool("escalate_emergency", client_id=client_id, retell_call_id=retell_call_id) as ctx:
        args = body.args
        with get_pooled_connection() as conn:
            client = resolve_client(conn, client_id)
            result = create_emergency_ticket(
                conn,
                client_id=client_id,
                escalation_phone=client["escalation_phone"],
                unit=args.unit,
                issue=args.issue,
                callback_number=args.callback_number,
                caller_safe=args.caller_safe,
            )
        ctx["ok"] = True
        return EscalateEmergencyResponse(ok=True, ticket_id=result["ticket_id"], notified=result["notified"])


@router.post("/take_message", response_model=TakeMessageResponse)
def take_message(body: TakeMessageCall, client_id: str = Query(...)):
    retell_call_id = body.call.call_id if body.call else None
    with timed_tool("take_message", client_id=client_id, retell_call_id=retell_call_id) as ctx:
        args = body.args
        with get_pooled_connection() as conn:
            resolve_client(conn, client_id)
            message_id = messages.create_message(
                conn,
                client_id=client_id,
                caller_name=args.caller_name,
                callback_number=args.callback_number,
                reason=args.reason,
                message=args.message,
            )
        ctx["ok"] = True
        return TakeMessageResponse(ok=True, message_id=message_id)
