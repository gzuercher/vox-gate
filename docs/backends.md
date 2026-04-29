# Backend examples

VoxGate has two endpoints:

- **`/claude`** — VoxGate calls the Anthropic API itself. You only
  need `ANTHROPIC_API_KEY` in `.env`.
- **`/prompt`** — VoxGate forwards the text to `TARGET_URL`. You write
  the backend yourself (or use one of the examples below).

## `/prompt` backends

VoxGate sends:

```
POST <TARGET_URL>
Authorization: Bearer <TARGET_TOKEN>      # if set
Content-Type: application/json

{"text": "voice input as text"}
```

and expects JSON back with a `response` (or `text`) field.

> ⚠️ Bind your backend only to `127.0.0.1`, or require a `TARGET_TOKEN`
> of its own. Otherwise VoxGate inadvertently exposes your backend to
> the internet.

### Python / FastAPI — Claude Code wrapper

Calls the Claude CLI as a subprocess. With `--continue` the
conversation context is preserved:

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
        ["claude", "-p", "--continue", req.text],
        capture_output=True, text=True, timeout=120,
    )
    return {"response": result.stdout.strip()}
```

Run: `uvicorn app:app --host 127.0.0.1 --port 9000`

### Node / Express — echo plus logic

```javascript
import express from "express";

const app = express();
app.use(express.json());

app.post("/prompt", (req, res) => {
  const text = req.body.text ?? "";
  // plug in your own logic here
  res.json({ response: `You said: ${text}` });
});

app.listen(9000, "127.0.0.1");
```

### Bash + curl — quick test stub

```bash
#!/usr/bin/env bash
# Tiny HTTP responder via socat/ncat. Test use only.
while true; do
  printf 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n%s' \
    '{"response":"ok"}' | nc -l -p 9000 -q 1
done
```

### Your own service (e.g. zursetti-planner)

If your service already has an HTTP API, just add a `/prompt` endpoint
that fulfils the contract:

```
POST /prompt        →   {"response": "..."}
```

VoxGate is agnostic to what happens inside the backend (database,
in-house LLM calls, tool use, etc.).

## `/claude` clients

If you want to use VoxGate **as** a backend (e.g. to reach Claude with
a voice/TTS wrapper from your own app):

### curl

VoxGate authenticates with cookies set by `POST /auth/login/google`
(plus a CSRF header on every POST). For scripted access, persist
cookies in a jar and forward the `vg_csrf` cookie value in the header:

```bash
# 1) Log in once and store cookies. ID_TOKEN is a Google ID token your
#    script obtained out-of-band (e.g. via a service-account flow).
curl -c cookies.txt -X POST https://voxgate.example.com/auth/login/google \
  -H "Content-Type: application/json" \
  -d "{\"id_token\": \"$ID_TOKEN\"}"

# 2) Use the cookies + CSRF header for subsequent calls.
CSRF=$(awk '$6=="vg_csrf"{print $7}' cookies.txt)
curl -b cookies.txt -X POST https://voxgate.example.com/claude \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the capital of Senegal?",
    "session_id": "my-app-session-001"
  }'
```

`session_id` must match `^[A-Za-z0-9_-]{8,128}$`. Keep it stable per
conversation thread — VoxGate retains up to 20 messages in memory per
session.

### Browser snippet

```javascript
function getCookie(name) {
  const parts = ('; ' + document.cookie).split('; ' + name + '=');
  return parts.length < 2 ? '' : parts.pop().split(';').shift();
}

async function ask(text) {
  const res = await fetch("https://voxgate.example.com/claude", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCookie("vg_csrf"),
    },
    body: JSON.stringify({
      text,
      session_id: localStorage.sessionId ?? crypto.randomUUID(),
    }),
  });
  const { response } = await res.json();
  return response;
}
```

VoxGate manages the history — you only pass `text` and a stable
`session_id`.

## Error codes

| Code | Meaning |
|---|---|
| 401 | Not signed in (cookie missing or expired). |
| 403 | Either the user is not in `ALLOWED_EMAILS`, or the `X-CSRF-Token` header is missing/wrong. |
| 422 | Validation failed (e.g. `text` too long/empty, `session_id` invalid). |
| 429 | Rate limit exceeded. |
| 502 | Backend (Anthropic or your `TARGET_URL`) returned an error. |
| 503 | Backend not configured (`ANTHROPIC_API_KEY` or `TARGET_URL` empty). |
