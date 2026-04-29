# VoxGate

**Talk to Claude (or another chatbot) by voice — straight from your phone.**

VoxGate is a small web app you install on your phone home screen like a
native app. Tap the mic, speak, and hear the answer read back to you.

## Languages

VoxGate is language-agnostic by design — Claude itself replies in any
language you speak. The UI offers a small selectable set (default:
German, French, Italian, English, Spanish — Swiss locales for the
first three). What actually works depends on three independent layers:

| Layer | What it does | Caveats |
|---|---|---|
| **Speech recognition** | Browser converts your voice to text | Standard variants only — no Schwyzerdütsch / regional dialects. Quality varies by browser (Chrome best, Safari/iOS limited). |
| **LLM (Claude)** | Understands and answers | Multilingual; not a limit here. |
| **TTS (read-aloud)** | Browser speaks the response | Depends on the voices installed on the device. The locale tag (`de-CH`, `fr-CH`, …) is a *preference*, not a guarantee. |

The selectable list is configurable via `SPEECH_LANGS` (see
[`docs/setup.md`](docs/setup.md#configuration)).

## What do you want to do?

### A) Talk to Claude by voice — own (sub-)domain

Recommended path. You need a subdomain pointing at your server and an
Anthropic API key.

```bash
git clone git@github.com:gzuercher/vox-gate.git
cd vox-gate/deploy/caddy
cp .env.example .env
# Fill in: VOXGATE_DOMAIN, ACME_EMAIL, ANTHROPIC_API_KEY
docker compose up -d
```

Caddy fetches a Let's Encrypt certificate automatically. Details:
[`deploy/caddy/README.md`](deploy/caddy/README.md).

### B) Reach your own bot by voice (e.g. a planner)

Same setup as A, but instead of `ANTHROPIC_API_KEY` you set
`TARGET_URL` pointing at your backend. Your backend implements a small
HTTP contract — see [`docs/backends.md`](docs/backends.md).

### C) Existing reverse-proxy infra (Traefik, Kubernetes, nginx)

Use the root `docker-compose.yml`. It only ships the VoxGate container;
cert handling and hostname routing happen in your infra. Notes:
[`docs/setup.md`](docs/setup.md#reverse-proxy).

### D) No domain of your own (Cloudflare Tunnel / Tailscale Funnel)

VoxGate works behind any tunnel — Cloudflare or Tailscale provide HTTPS
and a hostname. Concept and pointers to the official setups:
[`docs/setup.md`](docs/setup.md#tunnel-in-front).

---

## Using the app

After installing the PWA on your home screen, open it:

| Element | Function |
|---|---|
| **Mic button (large)** | Tap to start recording. Tap again to send. |
| **Language (top left)** | Switch between `DE-CH` and `FR-CH`. Persisted. |
| **Speaker (top right)** | Mute/unmute speech output. |
| **Status dot (top right)** | Green = ready, blinking = sending, red = error. |
| **New conversation (bottom)** | Reset the conversation history. |

Replies are read aloud automatically unless muted. If you tap the mic
again while audio is playing, the current speech is cancelled.

### Requirements

- **Browser:** Chrome on Android or desktop (Web Speech API).
  Safari/iOS support is limited.
- **Microphone permission** must be granted on first launch.
- **HTTPS** is mandatory on Android — solved by Caddy/tunnel above.

## Installing the PWA on your phone

1. Open Chrome on Android → `https://your-voxgate-host`.
2. The first screen offers **Sign in with Google**. Use a Google
   account that the operator has added to `ALLOWED_EMAILS`. The login
   produces a server-signed, `HttpOnly` session cookie — no token is
   stored in the browser.
3. Three-dot menu → "Add to Home screen".
4. The app now opens like any other app, with its own icon and color.

If you deploy multiple instances on different hostnames, repeat for
each — every URL becomes its own PWA with its own color.

To switch accounts or sign out, tap the **VoxGate logo** in the header.

## Access (operator + user)

VoxGate authenticates users via **Google Sign-In**. The operator lists
permitted Google accounts in `ALLOWED_EMAILS`; everybody else is
rejected at login. Practical guidance:

- **Set `GOOGLE_CLIENT_ID` and `ALLOWED_EMAILS`** in `.env` before
  sharing the URL.
- **Set a stable `SESSION_SECRET`** so sessions survive container
  restarts. The auto-generated, per-restart secret is fine for
  development but logs everyone out on every restart.
- **Granting access:** add the user's Google e-mail to
  `ALLOWED_EMAILS`. Takes effect on the next request — no restart.
- **Revoking access:** remove the e-mail from `ALLOWED_EMAILS`. The
  next request from that user's session returns 403, which kicks the
  PWA back to the login screen.
- **Lost device:** the device's session cookie remains valid until its
  TTL expires (`SESSION_COOKIE_TTL_SECONDS`, default 7 days) or until
  the e-mail is revoked. For immediate revocation, remove the e-mail
  from the allowlist.

Edge-level pre-auth (HTTP Basic Auth in your reverse proxy, Cloudflare
Access, Tailscale-only access) is independently possible — see
[`docs/setup.md`](docs/setup.md) and the security checklist in
[`docs/security.md`](docs/security.md).

## Troubleshooting

| Problem | What to do |
|---|---|
| Mic doesn't react | Grant permission in the browser. On Android the page must be HTTPS. |
| No speech output | Check the speaker button. iOS has limited Web Speech support. |
| `401` error | Session expired or missing. The PWA shows the Google Sign-In screen automatically. |
| `403` error | Your Google account is not in `ALLOWED_EMAILS` (ask the operator) or your session was revoked. |
| `429` error | Rate limit hit. Wait and retry. |
| `503` on `/claude` | Anthropic backend not configured — set `ANTHROPIC_API_KEY`. |
| Conversation suddenly "forgets" | Server restart — sessions are in-memory by design. |
| Doesn't work on Safari/iOS | Web Speech API is limited there; use Chrome. |

---

The rest is reference material for developers and clients calling the
HTTP API. For installation/operation see [`docs/setup.md`](docs/setup.md).
For the security checklist see [`docs/security.md`](docs/security.md).
For backend examples see [`docs/backends.md`](docs/backends.md). For
contributing see [`docs/contributing.md`](docs/contributing.md). For
where the project might go next see [`docs/roadmap.md`](docs/roadmap.md).

## Architecture

```
┌─────────────┐                             ┌──────────────────┐
│  PWA        │     POST /claude            │                  │     Anthropic API
│  (phone     │  ────────────────────────►  │  VoxGate server  │  ────────────────────►  Claude
│  home       │  ◄────────────────────────  │  (FastAPI)       │  ◄────────────────────  (claude-sonnet-4-5)
│  screen)    │                             │                  │
│             │     POST /prompt            │                  │     POST TARGET_URL
│             │  ────────────────────────►  │                  │  ────────────────────►  Custom backend
│             │  ◄────────────────────────  │                  │  ◄────────────────────  (e.g. zursetti-planner)
└─────────────┘                             └──────────────────┘
```

The server exposes two endpoints:

- **`/claude`** — calls the Anthropic API directly. Keeps conversation
  history per session. Uses `ANTHROPIC_API_KEY`.
- **`/prompt`** — forwards to a custom backend (`TARGET_URL`).
  Stateless. Voice gateway for any chatbot service.

## API reference

All authenticated endpoints require:

- the `vg_session` cookie (set by `POST /auth/login/{provider}`),
- a matching `X-CSRF-Token` header echoing the `vg_csrf` cookie.

The PWA handles both transparently. For programmatic access, log in
through `POST /auth/login/google` first and reuse the cookie jar.

### `POST /claude`

```json
POST /claude
Cookie: vg_session=…; vg_csrf=…
X-CSRF-Token: <value of vg_csrf>
Content-Type: application/json

{
  "text": "What time is it in Tokyo?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Response: `{ "response": "Currently it's …" }`

`session_id` must match `^[A-Za-z0-9_-]{8,128}$`. Up to 20 messages
per session are kept in memory; older ones are dropped in pairs.

### `POST /prompt`

```json
POST /prompt
Cookie: vg_session=…; vg_csrf=…
X-CSRF-Token: <value of vg_csrf>
Content-Type: application/json

{ "text": "Hello backend" }
```

VoxGate forwards to `TARGET_URL` and expects JSON with a `response`
(or `text`) field back.

### `GET /config`

Returns instance configuration for the PWA. No auth.

```json
{ "name": "Claude", "color": "#c8ff00", "lang": "de-CH", "maxLength": 4000,
  "googleClientId": "123-abc.apps.googleusercontent.com",
  "providers": ["google"] }
```

### Auth endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /auth/login/{provider}` | none — Origin-checked when `ALLOWED_ORIGIN` is set | Exchange a provider ID token for a VoxGate session. Body: `{"id_token": "..."}`. Today only `provider=google` is registered; unknown providers return 404. Sets `vg_session` (HttpOnly) and `vg_csrf` cookies. |
| `POST /auth/logout` | session cookie + CSRF (when logged in) | Clears both cookies. Idempotent: if no session is present, returns 200 without requiring CSRF. |
| `GET /auth/me` | session cookie | Returns `{"email": "...", "provider": "..."}` for the signed-in user, or 401 if no valid session. Re-runs the allowlist check, so a revoked user gets 403 even with a still-valid cookie. |
| `GET /auth/providers` | none | Returns `{"providers": ["google", ...]}` — the identity providers configured for this instance. |

The `ALLOWED_EMAILS` env var accepts entries like `alice@example.com`
(any configured provider acceptable) or `alice@example.com:google`
(only via Google). Useful once a second provider is registered.

### Errors

| Code | Meaning |
|---|---|
| 401 | Token missing or wrong |
| 422 | Validation failed |
| 429 | Rate limit exceeded |
| 502 | Backend error |
| 503 | Backend not configured |

## File structure

```
voxgate/
├── server.py              # FastAPI gateway (/claude, /prompt, /config)
├── pwa/                   # PWA (HTML, JS, CSS, manifest, service worker)
├── tests/                 # pytest tests
├── deploy/
│   └── caddy/             # Bundled Caddy + VoxGate (recommended path)
├── docs/
│   ├── setup.md           # Installation and operation
│   ├── security.md        # Operator checklist
│   ├── contributing.md    # Development workflow
│   ├── backends.md        # /prompt and /claude examples
│   ├── roadmap.md         # Future-development ideas
│   └── lessons.md         # Lessons learned
├── .claude/rules/         # Code rules for Claude Code
├── .env.example           # Configuration template (api-only, root)
├── docker-compose.yml     # api-only (no proxy bundled)
├── Dockerfile
├── pyproject.toml
├── Makefile               # make setup/run/test/lint
├── README.md              # This file
├── CLAUDE.md              # Playbook for Claude Code
└── LICENSE
```

## License

MIT
