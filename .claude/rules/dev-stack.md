---
description: Tech stack and build commands for VoxGate
globs: "*.py,*.html,*.js,*.json"
---

# Development Stack

## Tech Stack
- **Backend:** Python 3.10+, FastAPI, Uvicorn
- **Frontend:** Vanilla HTML/CSS/JS (no build step)
- **Speech:** Web Speech API (`de-CH`)
- **CLI:** Claude Code (`claude -p`)
- **Reverse Proxy:** Caddy (production)

## Build & Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Verification

Check every change before reporting it as done:
1. Server must start without errors
2. `POST /prompt` must return a valid response
3. If UI change: verify in browser

## Do not self-implement

| Topic | Use instead |
|---|---|
| Auth/Login | Bearer token via `API_TOKEN` env var |
| Password hashing | Not applicable (token-based) |
| Input validation | Pydantic `Field` constraints |
