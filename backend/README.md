# PropTalk US — backend

FastAPI service. Full design in [../docs/architecture.md](../docs/architecture.md).

## Run locally (Windows / PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open http://127.0.0.1:8000/health → `{"status":"ok"}` and http://127.0.0.1:8000/docs for the interactive API.

## Expose to Retell + provision the agent (Phase 3)

Retell calls your tools over HTTPS, so the backend needs a public URL. In dev, run a
free tunnel; the agent (LLM + 6 tools + webhook) is created from code so there are no
dashboard typos. **Creating/updating the agent is $0 — only live calls burn credits**,
so we prove the tool URLs work with curl *through the tunnel* before spending a minute.

One-time: put your Retell key in the repo-root `.env` as `RETELL_API_KEY=` (from the
Retell dashboard → Settings → API Keys).

```powershell
# 1. backend
cd backend; .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8000

# 2. tunnel (new terminal) — copy the https://<random>.trycloudflare.com URL it prints
cloudflared tunnel --url http://localhost:8000

# 3. audition voices, then provision the agent against that tunnel URL
python scripts\retell_provision.py list-voices --female --american --elevenlabs
python scripts\retell_provision.py create --base-url https://<random>.trycloudflare.com --voice-id 11labs-Anna

# 4. PROVE it works before calling (still $0): every check must print 200
$env:BASE_URL="https://<random>.trycloudflare.com"; bash tests/curl/run_all.sh

# 5. clean slate, then make ONE web test call from the Retell dashboard (Agents → Test)
python scripts\reset_demo_state.py
```

The trycloudflare URL changes every restart. When it does, re-point the agent without
recreating it: `python scripts\retell_provision.py update-urls --base-url https://<new>...`
Then `show` prints the current state, `delete` removes the agent + LLM from Retell.
