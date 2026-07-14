r"""Provision the Retell agent (LLM + agent + 6 tools + webhook) via the Retell API.

WHY A SCRIPT, NOT THE DASHBOARD: creating/updating an agent costs $0 - only live
calls burn credits. Generating the 6 tool schemas + URLs + prompt from code (instead
of hand-pasting into the dashboard) removes the class of typo that makes a tool call
fail mid-call and waste a test minute. Re-run it any time the tunnel URL changes.

The contract this builds is docs/RETELL_AGENT_CONFIG.md: the system prompt is read
verbatim from that file (section B), and the 6 tool parameter schemas below mirror
section C. Keep them in sync with the doc.

Usage (from backend/, venv active - or call .\.venv\Scripts\python.exe):
  python scripts/retell_provision.py list-voices [--female] [--american]
  python scripts/retell_provision.py create --base-url https://xxx.trycloudflare.com [--voice-id 11labs-Anna]
  python scripts/retell_provision.py update-urls --base-url https://yyy.trycloudflare.com
  python scripts/retell_provision.py show
  python scripts/retell_provision.py delete

Reads RETELL_API_KEY from the repo-root .env. Persists created IDs + current tunnel
URL to scripts/retell_state.json (gitignored).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(REPO / ".env")

API = "https://api.retellai.com"
STATE_FILE = BACKEND / "scripts" / "retell_state.json"
DOC = REPO / "docs" / "RETELL_AGENT_CONFIG.md"

# Demo tenant: Willowbrook (fixed UUID). Hardcoded into every tool + webhook URL as a
# query param for the single-tenant demo; multi-tenant later rides on a dynamic variable.
WILLOWBROOK_ID = "11111111-1111-1111-1111-111111111111"

# These render the {{...}} placeholders in the prompt/greeting even for a bare dashboard
# test call that passes no dynamic variables. Per-client values live on the clients row.
DEFAULT_DYNAMIC_VARIABLES = {
    "company_name": "Willowbrook Property Management",
    "agent_name": "Maya",
    "office_hours": "Monday to Friday, 9 to 6",
}

# Realtime model. gpt-4o-mini proved too weak at tool-calling (it narrated "let me
# check listings" without invoking the tool, then hallucinated fake units) - so we use
# gpt-4.1, which calls functions reliably. Correctness beats latency here: an agent that
# invents inventory is unusable. The real latency lever is deploy location (Phase 5/6),
# not model size.
LLM_MODEL = "gpt-4.1"
LLM_TEMPERATURE = 0.2

# Fallback voice if --voice-id isn't given and auto-pick finds nothing. Overridable.
DEFAULT_VOICE_ID = "11labs-Anna"

# --- the 6 tools (parameter schemas mirror docs/RETELL_AGENT_CONFIG.md SS C) -------------
# speak_during: say a short filler while the tool runs (good for the lookup/booking tools).
# All tools speak_after so the agent always folds the result into its next line.
TOOL_SPECS = [
    {
        "name": "get_available_listings",
        "description": (
            "Search currently available units. Call whenever the caller asks about "
            "apartments, houses, prices, pets, or availability. Filters are optional - "
            "call with whatever is known."
        ),
        "speak_during": True,
        "filler": "Let me pull up what we have available.",
        "parameters": {
            "type": "object",
            "properties": {
                "beds": {"type": "integer", "description": "Minimum bedrooms the caller wants"},
                "max_rent": {"type": "integer", "description": "Maximum monthly budget in USD"},
                "pets": {"type": "boolean", "description": "True if the caller has a pet"},
                "move_in_by": {"type": "string", "description": "Latest acceptable availability date, YYYY-MM-DD"},
            },
            "required": [],
        },
    },
    {
        "name": "check_tour_slots",
        "description": "Get available tour times for a specific property. Call before offering any times.",
        "speak_during": True,
        "filler": "Let me check the calendar for you.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "string",
                    "description": "The short property code from get_available_listings, e.g. '2A' or 'PALM'. Pass it exactly.",
                },
                "date_preference": {
                    "type": "string",
                    "description": "Caller's preferred day/time in natural language, e.g. 'Saturday afternoon'",
                },
            },
            "required": ["property_id"],
        },
    },
    {
        "name": "book_tour",
        "description": (
            "Book a confirmed tour slot. Only call after the caller verbally confirmed the "
            "exact slot and you read their phone number back."
        ),
        "speak_during": True,
        "filler": "Booking that for you now.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "string",
                    "description": "The short property code from get_available_listings, e.g. '2A'. Pass it exactly.",
                },
                "slot_start_iso": {
                    "type": "string",
                    "description": "Chosen slot start time, ISO 8601, as returned by check_tour_slots",
                },
                "prospect_name": {"type": "string"},
                "prospect_phone": {"type": "string", "description": "Digits confirmed back to the caller"},
                "sms_consent": {
                    "type": "boolean",
                    "description": "True ONLY if the caller said yes to a text confirmation",
                },
            },
            "required": ["property_id", "slot_start_iso", "prospect_name", "prospect_phone", "sms_consent"],
        },
    },
    {
        "name": "create_maintenance_ticket",
        "description": "Log a routine (non-emergency) maintenance issue.",
        "speak_during": False,
        "filler": "",
        "parameters": {
            "type": "object",
            "properties": {
                "unit": {"type": "string", "description": "Unit number or property address"},
                "issue_type": {
                    "type": "string",
                    "description": "Short category: plumbing, electrical, appliance, HVAC, pest, other",
                },
                "description": {
                    "type": "string",
                    "description": "What's wrong, in the caller's words, plus how long it's been happening",
                },
                "callback_number": {"type": "string"},
                "permission_to_enter": {
                    "type": "boolean",
                    "description": "May maintenance enter if the tenant is not home",
                },
            },
            "required": ["unit", "issue_type", "description", "callback_number"],
        },
    },
    {
        "name": "escalate_emergency",
        "description": (
            "Immediately alert the on-call human for a true emergency (fire, gas, flooding, "
            "no heat in freezing weather, break-in, lockout at night). Fires an SMS + call to "
            "the escalation phone."
        ),
        "speak_during": False,
        "filler": "",
        "parameters": {
            "type": "object",
            "properties": {
                "unit": {"type": "string"},
                "issue": {"type": "string", "description": "One-line description of the emergency"},
                "callback_number": {"type": "string"},
                "caller_safe": {
                    "type": "boolean",
                    "description": "False if the caller may be in danger (fire/gas/CO) and was told to call 911",
                },
            },
            "required": ["unit", "issue", "callback_number"],
        },
    },
    {
        "name": "take_message",
        "description": (
            "Record a message for the office for anything outside listings, tours, and "
            "maintenance, or when the caller wants a human."
        ),
        "speak_during": False,
        "filler": "",
        "parameters": {
            "type": "object",
            "properties": {
                "caller_name": {"type": "string"},
                "callback_number": {"type": "string"},
                "reason": {
                    "type": "string",
                    "description": "Short category: rent question, lease question, complaint, vendor, wants human, other",
                },
                "message": {"type": "string", "description": "The message in the caller's words"},
            },
            "required": ["caller_name", "callback_number", "reason", "message"],
        },
    },
]


# --- helpers ---------------------------------------------------------------------------
def api_key() -> str:
    key = os.environ.get("RETELL_API_KEY", "").strip()
    if not key:
        sys.exit(
            "RETELL_API_KEY is not set in the repo-root .env.\n"
            "Get it from the Retell dashboard -> Settings -> API Keys (starts with 'key_')."
        )
    return key


def client() -> httpx.Client:
    return httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
        timeout=30,
    )


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"  saved {STATE_FILE.relative_to(REPO)}")


def load_system_prompt() -> str:
    """Extract the fenced code block under '## B. System prompt' in the config doc."""
    doc = DOC.read_text(encoding="utf-8")
    heading = doc.index("## B. System prompt")
    fence = doc.index("```", heading)
    body_start = doc.index("\n", fence) + 1
    body_end = doc.index("```", body_start)
    return doc[body_start:body_end].strip()


def build_tools(base_url: str) -> list[dict]:
    base = base_url.rstrip("/")
    qs = f"?client_id={WILLOWBROOK_ID}"
    tools = []
    for spec in TOOL_SPECS:
        tool = {
            "type": "custom",
            "name": spec["name"],
            "description": spec["description"],
            "url": f"{base}/tools/{spec['name']}{qs}",
            "method": "POST",
            "parameters": spec["parameters"],
            "speak_during_execution": spec["speak_during"],
            "speak_after_execution": True,
        }
        if spec["speak_during"] and spec["filler"]:
            tool["execution_message_description"] = spec["filler"]
        tools.append(tool)
    return tools


def webhook_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/webhooks/retell?client_id={WILLOWBROOK_ID}"


def begin_message() -> str:
    return (
        "Thanks for calling {{company_name}}! This is {{agent_name}}, the office's AI "
        "assistant - calls may be recorded for quality. How can I help you today?"
    )


# --- commands --------------------------------------------------------------------------
def cmd_list_voices(args) -> None:
    with client() as c:
        r = c.get("/list-voices")
        r.raise_for_status()
        voices = r.json()
    for v in voices:
        if args.female and v.get("gender") != "female":
            continue
        if args.american and v.get("accent") != "American":
            continue
        if args.elevenlabs and v.get("provider") != "elevenlabs":
            continue
        print(
            f"{v.get('voice_id'):<24} {v.get('voice_name', ''):<14} "
            f"{v.get('provider', ''):<12} {v.get('gender', ''):<7} "
            f"{v.get('accent', '') or '':<10} {v.get('preview_audio_url', '')}"
        )


def _llm_payload(base_url: str) -> dict:
    return {
        "model": LLM_MODEL,
        "model_temperature": LLM_TEMPERATURE,
        "general_prompt": load_system_prompt(),
        "begin_message": begin_message(),
        "general_tools": build_tools(base_url),
        "default_dynamic_variables": DEFAULT_DYNAMIC_VARIABLES,
    }


def _agent_payload(llm_id: str, base_url: str, voice_id: str) -> dict:
    return {
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
        "voice_id": voice_id,
        "agent_name": "Willowbrook - Maya (demo)",
        "webhook_url": webhook_url(base_url),
        "language": "en-US",
        "voice_speed": 1.0,
        "interruption_sensitivity": 1,
        "enable_backchannel": True,
        "responsiveness": 1,
        "post_call_analysis_model": "gpt-4o-mini",
    }


def cmd_create(args) -> None:
    state = load_state()
    if state.get("agent_id"):
        sys.exit(
            f"An agent already exists ({state['agent_id']}). Use 'update-urls' to point it at a "
            "new tunnel, 'show' to inspect, or 'delete' first to recreate."
        )
    base_url = args.base_url.rstrip("/")
    voice_id = args.voice_id or DEFAULT_VOICE_ID
    with client() as c:
        print("Creating Retell LLM (prompt + 6 tools)...")
        r = c.post("/create-retell-llm", json=_llm_payload(base_url))
        r.raise_for_status()
        llm = r.json()
        llm_id = llm["llm_id"]
        print(f"  llm_id = {llm_id}")

        print("Creating agent (voice + webhook)...")
        r = c.post("/create-agent", json=_agent_payload(llm_id, base_url, voice_id))
        r.raise_for_status()
        agent = r.json()
        agent_id = agent["agent_id"]
        print(f"  agent_id = {agent_id}")

    save_state(
        {
            "llm_id": llm_id,
            "agent_id": agent_id,
            "base_url": base_url,
            "voice_id": voice_id,
            "client_id": WILLOWBROOK_ID,
        }
    )
    print("\nDone. Next: verify tool URLs THROUGH the tunnel with tests/curl (still $0),")
    print("then start a web test call from the Retell dashboard (Agents -> this agent -> Test).")


def cmd_update_urls(args) -> None:
    state = load_state()
    if not state.get("llm_id") or not state.get("agent_id"):
        sys.exit("No saved agent. Run 'create' first.")
    # Full sync: re-pushes the entire LLM config (model, prompt, begin_message, tools,
    # dynamic vars) + the agent webhook, so ANY script change lands with one command,
    # not just tunnel rotations. Defaults to the saved tunnel URL.
    base_url = (args.base_url or state.get("base_url", "")).rstrip("/")
    if not base_url:
        sys.exit("No base URL given and none saved. Pass --base-url.")
    with client() as c:
        print(f"Syncing LLM (model={LLM_MODEL}, {len(TOOL_SPECS)} tools) ...")
        r = c.patch(f"/update-retell-llm/{state['llm_id']}", json=_llm_payload(base_url))
        r.raise_for_status()
        print("Syncing agent webhook ...")
        r = c.patch(f"/update-agent/{state['agent_id']}", json={"webhook_url": webhook_url(base_url)})
        r.raise_for_status()
    state["base_url"] = base_url
    save_state(state)
    print("Done. Re-verify with tests/curl before calling.")


def cmd_show(args) -> None:
    state = load_state()
    if not state:
        print("No retell_state.json yet - nothing provisioned.")
        return
    print(json.dumps(state, indent=2))
    print("\nTool URLs Retell will call:")
    for spec in TOOL_SPECS:
        print(f"  {state['base_url']}/tools/{spec['name']}?client_id={state['client_id']}")
    print(f"Webhook: {webhook_url(state['base_url'])}")


def cmd_delete(args) -> None:
    state = load_state()
    if not state:
        print("Nothing to delete.")
        return
    with client() as c:
        if state.get("agent_id"):
            c.delete(f"/delete-agent/{state['agent_id']}")
            print(f"deleted agent {state['agent_id']}")
        if state.get("llm_id"):
            c.delete(f"/delete-retell-llm/{state['llm_id']}")
            print(f"deleted llm {state['llm_id']}")
    STATE_FILE.unlink(missing_ok=True)
    print("removed retell_state.json")


def main() -> None:
    p = argparse.ArgumentParser(description="Provision the Retell agent for PropTalk US.")
    sub = p.add_subparsers(dest="cmd", required=True)

    lv = sub.add_parser("list-voices", help="List voices available to your account")
    lv.add_argument("--female", action="store_true")
    lv.add_argument("--american", action="store_true")
    lv.add_argument("--elevenlabs", action="store_true")
    lv.set_defaults(func=cmd_list_voices)

    cr = sub.add_parser("create", help="Create the LLM + agent + tools")
    cr.add_argument("--base-url", required=True, help="Public tunnel base URL, e.g. https://xxx.trycloudflare.com")
    cr.add_argument("--voice-id", help=f"Retell voice_id (default {DEFAULT_VOICE_ID})")
    cr.set_defaults(func=cmd_create)

    up = sub.add_parser("update-urls", help="Re-push tools + webhook (new tunnel URL or tool-spec change)")
    up.add_argument("--base-url", help="Defaults to the saved tunnel URL")
    up.set_defaults(func=cmd_update_urls)

    sub.add_parser("show", help="Print saved state + the URLs Retell will call").set_defaults(func=cmd_show)
    sub.add_parser("delete", help="Delete the agent + LLM from Retell").set_defaults(func=cmd_delete)

    args = p.parse_args()
    try:
        args.func(args)
    except httpx.HTTPStatusError as e:
        print(f"\nRetell API error {e.response.status_code}:\n{e.response.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
