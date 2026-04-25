# VoxGate

**Talk to Claude (or another chatbot) by voice — straight from your phone.**

VoxGate is a small web app you install on your smartphone home screen like a native app. Tap the microphone button, speak, and hear the answer read back to you. It works in Swiss German and Swiss French and can serve multiple backends in parallel.

## What can I do with it?

- **Talk to Claude directly** — provide an Anthropic API key and VoxGate calls Claude for you. Conversation context is preserved within a session.
- **Talk to your own backend** — for example a script on your Mac that runs Claude Code in the terminal. VoxGate forwards your spoken prompt as an HTTP POST.
- **Run multiple instances side by side** — e.g. a green PWA "Claude" and a blue PWA "Dokbot", each with its own icon on the home screen.

Typical use case: you go for a walk, tap the Claude icon, ask "What time is it in Tokyo?", and hear the answer without having to type.

## End-user guide

After installing the PWA on your home screen, open the app:

| Element | Function |
|---|---|
| **Microphone button (large)** | Tap to start recording. Tap again to send. |
| **Language (top left)** | Switch between `DE-CH` and `FR-CH`. Choice is persisted. |
| **Speaker (top right)** | Mute/unmute speech output. |
| **Status dot (top right)** | Green = ready, blinking = sending, red = error. |
| **New conversation (bottom)** | Reset the conversation history. |

Replies are read aloud automatically unless muted. If you tap the mic again while audio is playing, the current speech is cancelled.

### Requirements

- **Browser:** Chrome on Android or desktop (Web Speech API). Safari/iOS support is limited.
- **Microphone permission** must be granted on first launch.
- **HTTPS** is mandatory on Android — see Setup below.

## Architecture

```
┌─────────────┐                             ┌──────────────────┐
│  PWA        │     POST /claude            │                  │     Anthropic API
│  (phone     │  ────────────────────────►  │  VoxGate server  │  ────────────────────►  Claude
│  home       │  ◄────────────────────────  │  (FastAPI)       │  ◄────────────────────  (claude-sonnet-4-5)
│  screen)    │                             │                  │
│             │     POST /prompt            │                  │     POST TARGET_URL
│             │  ────────────────────────►  │                  │  ────────────────────►  Custom backend
│             │  ◄────────────────────────  │                  │  ◄────────────────────  (e.g. Mac with Claude Code)
└─────────────┘                             └──────────────────┘
```

The server exposes two endpoints:

- **`/claude`** — calls the Anthropic API directly. Keeps conversation history per session. Uses `ANTHROPIC_API_KEY`.
- **`/prompt`** — forwards to a custom backend (`TARGET_URL`). Stateless. Original use case: voice gateway for any chatbot service.

The PWA uses `/claude`. `/prompt` is kept for backwards compatibility and can be driven by your own clients.

## Quick start (Docker, recommended)

```bash
git clone git@github.com:gzuercher/vox-gate.git
cd vox-gate
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY and API_TOKEN
docker compose up -d
```

Defaults:
- **Claude** at `http://localhost:8001` (green)
- **Dokbot** at `http://localhost:8002` (blue)

## Configuration

Everything is configured via environment variables.

### General

| Variable | Description | Default |
|---|---|---|
| `INSTANCE_NAME` | Name shown in the UI header | `VoxGate` |
| `INSTANCE_COLOR` | Accent color (hex) | `#c8ff00` |
| `SPEECH_LANG` | Default language (Web Speech API) | `de-CH` |
| `MAX_PROMPT_LENGTH` | Maximum text length | `4000` |
| `REQUEST_TIMEOUT` | Outbound request timeout in seconds | `120` |
| `API_TOKEN` | Bearer token for VoxGate itself | *(empty — server refuses to start if a backend is configured)* |
| `ALLOWED_ORIGIN` | Allowed CORS origin | *(empty, blocked)* |
| `RATE_LIMIT_PER_MINUTE` | Requests per minute per IP for `/claude` and `/prompt` | `30` |
| `SESSION_TTL_SECONDS` | Lifetime of an idle session | `1800` |
| `MAX_SESSIONS` | Global cap on concurrently held sessions | `1000` |
| `TRUST_PROXY_HEADERS` | Set to `1` when running behind Caddy/Nginx (X-Forwarded-For) | `0` |
| `VOXGATE_ALLOW_OPEN` | Set to `1` to bypass the fail-loud check (local development only) | *(empty)* |

### Direct Claude backend (`/claude`)

| Variable | Description | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | API key from console.anthropic.com | *(empty, /claude returns 503)* |
| `SYSTEM_PROMPT` | System prompt for Claude | `You are a helpful assistant. Answer concisely.` |
| `CLAUDE_MODEL` | Anthropic model ID | `claude-sonnet-4-5` |

> ⚠️ **Cost warning:** Anthropic API calls cost money. Set `API_TOKEN` before exposing the server publicly, otherwise strangers can run requests on your bill.

### Forwarding backend (`/prompt`)

| Variable | Description | Default |
|---|---|---|
| `TARGET_URL` | Custom backend URL | *(empty, /prompt returns 503)* |
| `TARGET_TOKEN` | Bearer token for the target backend | *(empty)* |

## API reference

### `POST /claude`

Direct Anthropic call with session history.

```json
POST /claude
Authorization: Bearer <API_TOKEN>     // if API_TOKEN is set
Content-Type: application/json

{
  "text": "What time is it in Tokyo?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Response:

```json
{ "response": "Currently it's …" }
```

Errors:
- `401` — token missing or wrong
- `422` — validation failed (`text` too long/empty, `session_id` missing or malformed)
- `429` — rate limit exceeded
- `502` — Anthropic API error
- `503` — `ANTHROPIC_API_KEY` not configured

History: up to 20 messages per `session_id` are kept in memory; older ones are dropped in pairs.

### `POST /prompt`

Pure forwarding to `TARGET_URL`.

```json
POST /prompt
Authorization: Bearer <API_TOKEN>
Content-Type: application/json

{ "text": "Hello backend" }
```

VoxGate forwards:

```json
POST <TARGET_URL>
Authorization: Bearer <TARGET_TOKEN>   // if set
Content-Type: application/json

{ "text": "Hello backend" }
```

The backend must return JSON with a `response` (or `text`) field.

### `GET /config`

Returns instance configuration for the PWA. No auth.

```json
{ "name": "Claude", "color": "#c8ff00", "lang": "de-CH", "maxLength": 4000 }
```

## PWA installation

1. Open Chrome on Android → `https://claude.example.com`
2. Three-dot menu → "Add to Home screen"
3. Repeat for each instance — every icon opens its own PWA with its own color.

## HTTPS (required on Android)

Caddy as reverse proxy with automatic certificates:

```
# Caddyfile
claude.example.com {
    reverse_proxy localhost:8001
}
dokbot.example.com {
    reverse_proxy localhost:8002
}
```

Details, systemd units and an example backend live in [`SETUP.md`](SETUP.md).

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| Microphone doesn't react | Grant permission in the browser. On Android only over HTTPS. |
| No speech output | Check the speaker button (top right). iOS has limited Web Speech support. |
| `503` on `/claude` | `ANTHROPIC_API_KEY` is not set. |
| `401` | `API_TOKEN` missing or wrong. Set it in `localStorage.apiToken` or send the header. |
| `429` | Rate limit hit. Wait or raise `RATE_LIMIT_PER_MINUTE`. |
| Conversation suddenly "forgets" | Likely started with multiple workers — see Scaling. |
| Doesn't work properly on Safari/iOS | Web Speech API is limited there; Chrome recommended. |

## Security

VoxGate is designed for public deployment. Built-in protections:

| Mechanism | Effect |
|---|---|
| **Fail-loud start** | Server refuses to start when a backend (`ANTHROPIC_API_KEY` or `TARGET_URL`) is configured but `API_TOKEN` is empty. Only `VOXGATE_ALLOW_OPEN=1` bypasses (dev). |
| **Timing-safe token check** | Bearer-token comparison via `secrets.compare_digest`. |
| **Rate limiting** | `RATE_LIMIT_PER_MINUTE` requests per IP for `/claude` and `/prompt`. Default 30/min. |
| **Session TTL** | Idle sessions are dropped after `SESSION_TTL_SECONDS` (default 30 min). |
| **Session cap** | At most `MAX_SESSIONS` concurrent sessions; oldest evicted first. |
| **`session_id` validation** | Pattern `^[A-Za-z0-9_-]{8,128}$`. Control characters, newlines etc. rejected. |
| **Security headers** | Strict `Content-Security-Policy` (no inline script), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (microphone only). |
| **Audit log** | Every request is logged with IP, session prefix and text length (no payload). 429 and backend errors too. |
| **CORS** | Default empty = blocked. Set `ALLOWED_ORIGIN` explicitly. |

### Operator obligations

- Set **`API_TOKEN`** before exposing the server publicly — preferably long (≥32 chars, generated via `openssl rand -hex 32`).
- Set **`TRUST_PROXY_HEADERS=1`** once VoxGate runs behind Caddy/Nginx so the rate limit applies to the real client IP. Only enable when the proxy reliably sets `X-Forwarded-For` — otherwise clients can spoof their own IP.
- Set an **Anthropic spending limit** in the console dashboard as insurance against token leaks.
- Avoid **Caddy CSP overrides**: VoxGate sets CSP itself — don't add a separate `header` for CSP in Caddy.
- **Key rotation:** `ANTHROPIC_API_KEY` is cached on first `/claude` call. Restart the container/process after rotation.

### Residual risks

- **localStorage XSS:** the bearer token (when used by the PWA client) lives in `localStorage`. CSP blocks inline scripts, but any future use of `innerHTML` with response data would leak the token. Mind this when changing PWA output rendering.
- **In-memory sessions:** histories live in the process only. Lost on restart. No disk leak — by design.
- **No per-user rate limit:** rate limiting is per IP. Behind NAT/CGNAT users share a quota.

## Scaling & deployment constraints

**VoxGate must run with exactly one Uvicorn worker per process.** The `/claude` endpoint keeps conversation history per `session_id` in an in-memory dict. Each worker process has its own copy — requests routed to different workers see different (or empty) histories. Users would experience sporadic "memory loss" mid-conversation.

The shipped `Dockerfile` and `docker-compose.yml` already start a single worker — out of the box this is fine.

### Why scale at all?

Three typical motives — none of them currently pressing for VoxGate:

1. **CPU utilization.** Python's GIL limits one process to one CPU core. Multiple workers can use multiple cores. Not relevant here: the server is I/O-bound (it just waits for the Anthropic API). One async worker handles hundreds of concurrent requests.
2. **Throughput / concurrent users.** Many simultaneously active sessions could saturate one worker. A personal or family-sized installation will never hit this.
3. **High availability.** Multiple containers behind a load balancer survive the loss of any single instance. The most realistic motivation once VoxGate is shared with others.

### Implications

- Do **not** set `--workers N` (N > 1) on `uvicorn`.
- Do **not** put multiple VoxGate containers behind a load balancer with `/claude` enabled, unless sticky sessions are configured (and even then it's brittle on container restarts).
- Histories are lost on container restart — intentional design for a lightweight install.
- `/prompt` is stateless and unaffected — scaling that part is safe.

### Migration path (if scaling becomes necessary)

Move the `_sessions` dict out of process memory into a shared store. Redis is the standard choice: each worker reads/writes session history from Redis, all workers stay in sync, sessions survive restarts. Adds a dependency and requires reworking `server.py`.

## File structure

```
voxgate/
├── server.py              # FastAPI gateway (/claude, /prompt, /config)
├── pwa/
│   ├── index.html         # Voice UI (TTS, language toggle, sessions)
│   ├── app.js             # PWA logic
│   ├── styles.css         # PWA styles
│   ├── manifest.json      # PWA manifest
│   ├── sw.js              # Service worker
│   └── icon.svg           # App icon
├── tests/
│   └── test_server.py     # pytest tests (endpoints, auth, sessions, security)
├── .claude/
│   └── rules/             # Code rules for Claude Code (security, quality, …)
├── .env.example           # Configuration template
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── Makefile               # make setup/run/test/lint
├── CLAUDE.md              # Playbook for Claude Code
├── CONTRIBUTING.md        # How to contribute
├── SETUP.md               # Detailed setup guide
└── lessons.md             # Lessons learned
```

## Development

```bash
make setup          # create venv, install dependencies
make run            # start server locally
make test           # pytest
make lint           # ruff
make format         # ruff format
make check          # lint + test
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for conventions and workflow.

## Requirements

- Python 3.10+ (or Docker)
- Chrome (desktop or Android) for the Web Speech API
- Anthropic API key (for `/claude`) or a custom backend (for `/prompt`)

## License

MIT
