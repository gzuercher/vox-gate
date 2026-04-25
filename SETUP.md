# VoxGate Setup

Detailed guide for system operators. For an overview see [`README.md`](README.md).

## Option A: Docker (recommended)

### 1. Clone and configure

```bash
git clone git@github.com:gzuercher/vox-gate.git
cd vox-gate
cp .env.example .env
# Edit .env — see next section
```

### 2. Fill in `.env`

Configure at least **one** of the following backends:

**Direct Claude (simplest):**
```bash
ANTHROPIC_API_KEY=sk-ant-...
SYSTEM_PROMPT=You are a helpful assistant. Answer concisely.
API_TOKEN_CLAUDE=a-long-random-string
```

**Custom backend via forwarding:**
```bash
TARGET_URL=http://host.docker.internal:9000/prompt
TARGET_TOKEN=optional-bearer-token
API_TOKEN_CLAUDE=a-long-random-string
```

> ⚠️ **Important:** Always set `API_TOKEN_*` once the server is reachable from outside. Without a token anyone can send requests — with `/claude` active you pay the Anthropic bill for strangers.
>
> Since the security hardening, **the server refuses to start** when a backend is configured and `API_TOKEN` is empty. Only `VOXGATE_ALLOW_OPEN=1` bypasses (local development).
>
> Generate a token: `openssl rand -hex 32`

### 3. Start

```bash
docker compose up -d
```

Default instances:
- **Claude** → http://localhost:8001
- **Dokbot** → http://localhost:8002

### 4. More instances

Add a service in `docker-compose.yml`:

```yaml
notes:
  build: .
  ports:
    - "8003:8000"
  environment:
    - INSTANCE_NAME=Notes
    - INSTANCE_COLOR=#ff6b6b
    - SPEECH_LANG=de-CH
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    - SYSTEM_PROMPT=You are a note-taking assistant.
    - API_TOKEN=${API_TOKEN_NOTES:-}
    - ALLOWED_ORIGIN=https://notes.example.com
```

## Option B: Direct (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# Installs fastapi, uvicorn, httpx, anthropic plus dev tools

export INSTANCE_NAME="Claude"
export INSTANCE_COLOR="#c8ff00"
export ANTHROPIC_API_KEY="sk-ant-..."
export API_TOKEN="your-long-random-token"
export ALLOWED_ORIGIN="https://claude.example.com"

uvicorn server:app --host 127.0.0.1 --port 8000
# IMPORTANT: do not pass --workers N — see scaling notes in README
```

> ⚠️ **Never** run without `API_TOKEN` on a publicly reachable server.

## HTTPS (mandatory for the Web Speech API on Android)

Caddy with automatic certificates:

```
# Caddyfile
claude.example.com {
  reverse_proxy localhost:8001
}
dokbot.example.com {
  reverse_proxy localhost:8002
}
```

```bash
apt install caddy
caddy run --config /etc/caddy/Caddyfile
```

Caddy sets `X-Forwarded-For` automatically. To make rate limiting use the real client IP, also set in `.env`:

```bash
TRUST_PROXY_HEADERS=1
```

> ⚠️ Only enable `TRUST_PROXY_HEADERS=1` when the server is reachable **only** through the proxy. Otherwise clients can set `X-Forwarded-For` themselves and bypass rate limiting.

## Systemd (one unit per instance)

```ini
# /etc/systemd/system/voxgate-claude.service
[Unit]
Description=VoxGate - Claude
After=network.target

[Service]
WorkingDirectory=/opt/voxgate
Environment="INSTANCE_NAME=Claude"
Environment="INSTANCE_COLOR=#c8ff00"
Environment="SPEECH_LANG=de-CH"
Environment="ANTHROPIC_API_KEY=sk-ant-..."
Environment="SYSTEM_PROMPT=You are a helpful assistant. Answer concisely."
Environment="API_TOKEN=long-random-token"
Environment="ALLOWED_ORIGIN=https://claude.example.com"
Environment="TRUST_PROXY_HEADERS=1"
# Do not pass --workers N — sessions are kept in memory (see "Scaling" in README)
ExecStart=/opt/voxgate/.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now voxgate-claude
journalctl -u voxgate-claude -f
```

## Install the PWA on a Pixel

1. Open Chrome → https://claude.example.com
2. Three-dot menu → "Add to Home screen"
3. Repeat for each instance — different URL = different PWA with its own color and icon.

## Custom backend for `/prompt`

Any HTTP service that fulfills this contract works as a target:

```
POST <TARGET_URL>
Content-Type: application/json
Authorization: Bearer <TARGET_TOKEN>     # if TARGET_TOKEN is set

{"text": "voice input text"}
→ {"response": "answer"}
```

### Example: Claude Code wrapper

A minimal backend that invokes the Claude Code CLI:

```python
from fastapi import FastAPI
from pydantic import BaseModel
import subprocess

app = FastAPI()

class Req(BaseModel):
    text: str

@app.post("/prompt")
async def prompt(req: Req):
    result = subprocess.run(
        ["claude", "-p", req.text],
        capture_output=True, text=True, timeout=120,
    )
    return {"response": result.stdout.strip()}
```

Runs on the machine where Claude Code is installed (e.g. your Mac). VoxGate runs on the server and forwards to it.

## Maintenance & operations

- **Logs:** `docker compose logs -f` or `journalctl -u voxgate-* -f`
- **Update:** `git pull && docker compose build && docker compose up -d`
- **Sessions:** kept in memory; lost on restart. Intentional for a lightweight install.
- **Monitor Anthropic costs:** use the console.anthropic.com dashboard, set spending limits.
- **Single-worker constraint:** see the "Scaling" section in `README.md`.
