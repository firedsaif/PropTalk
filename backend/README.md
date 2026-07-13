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

## Expose to Retell (later — Phase 3)

Retell calls your tools over HTTPS, so the backend needs a public URL. In dev, run a free tunnel and point Retell's function URLs at it (update them when the URL changes):

```powershell
cloudflared tunnel --url http://localhost:8000   # no account needed
# or: ngrok http 8000                              # needs a free authtoken
```
