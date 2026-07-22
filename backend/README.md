# PropTalk US — backend

FastAPI service. Full design in [../docs/architecture.md](../docs/architecture.md).
Run everything from `D:\US\backend`. If a script is blocked by execution policy, prefix
it: `powershell -ExecutionPolicy Bypass -File ops\serve.ps1`.

## Everyday gauntlet loop (the short version)

```powershell
cd D:\US\backend

.\ops\serve.ps1          # start EVERYTHING: backend + tunnel + point Retell at it + verify.
                         #   -> prints the tunnel URL and "READY". Safe to re-run any time.

# ...make your web call in the Retell dashboard (Agents -> Willowbrook - Maya -> Test)...

.\ops\after-call.ps1     # after you hang up: emails the summary + prints the outcome.
                         #   (pulls the call from Retell's API - see "Why after-call" below)

.\.venv\Scripts\python.exe scripts\reset_demo_state.py   # clean slate between scenarios (keeps seed)

.\ops\stop.ps1           # stop backend + tunnel when done
```

`serve.ps1` stops old processes first and auto-picks a free port (8000 -> 8001 -> ...),
so a stuck port or a leftover process never blocks you. That's the whole loop.

## Why `after-call.ps1` exists (important)

Dev reaches Retell through a free **cloudflared tunnel**. It handles the small mid-call
tool requests fine, but on this network it reliably **drops the big end-of-call webhook**
(it carries the full transcript), so the summary email won't send on its own.
`after-call.ps1` recovers it by *pulling* the finished call from Retell's API and sending
the summary itself. **The call and the booking are never lost** — only the auto-email,
which this recovers. Permanent fix is the Phase 6 Railway deploy (no tunnel).

## Check it's working / see what's running

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py     # PASS = full path (backend+DB+tunnel) alive; no bash needed
Get-Process cloudflared -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*uvicorn*' } | Select-Object ProcessId
```

## Troubleshooting

- **"The tests didn't run."** The old bash tests (`tests\curl\*.sh`) need `bash` **and**
  default to port 8000, but `serve.ps1` may land on 8001 if 8000 is stuck. Use
  `scripts\smoke_test.py` instead — it reads the live tunnel URL and needs no bash.
- **TUNNEL FAILED (DNS).** `trycloudflare.com` didn't resolve (intermittent here). Just
  run `.\ops\serve.ps1` again — the backend stays up, only the tunnel needs the retry.
  Log: `ops\logs\tunnel.err.log`.
- **BACKEND FAILED.** See `ops\logs\backend.err.log` (usually a missing `.env` value or
  the DB briefly unreachable — also intermittent DNS).
- **Port stuck / "address already in use".** `.\ops\stop.ps1`, wait ~10s, `.\ops\serve.ps1`.
- **Logs:** backend `ops\logs\backend.err.log` (every tool call + latency); tunnel URL in
  `ops\logs\tunnel.err.log`.

## First-time setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Secrets live in the gitignored repo-root `.env` (`RETELL_API_KEY`, `DATABASE_URL`,
`RESEND_API_KEY`, `FROM_EMAIL`, …; `.env.example` documents them). `GET /health` →
`{"status":"ok"}`, `/docs` is the interactive API.

## Retell agent (provisioned from code, $0)

The agent (LLM + 6 tools + webhook) is created from code, not the dashboard, so there are
no paste typos — creating/updating is free, only live calls burn credits. `serve.ps1`
already re-points the agent at the current tunnel every run. Manual commands:

```powershell
python scripts\retell_provision.py show                          # current agent/tunnel state
python scripts\retell_provision.py update-urls --base-url <url>  # re-point at a new tunnel
python scripts\retell_provision.py list-voices --female --american --elevenlabs
```

See [../docs/gauntlet.md](../docs/gauntlet.md) for the scenario scripts + scoreboard, and
[../CLAUDE.md](../CLAUDE.md) for project context.
