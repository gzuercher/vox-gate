# Backend contract

> **Live version:** every running VoxGate instance serves this document
> at `GET /backend-contract` (no auth, `text/markdown`). Backend
> integrators can `curl https://<voxgate-host>/backend-contract` to get
> the contract their target instance is actually shipping with — no need
> to check out the repo or guess the version.

VoxGate is a pure forwarding proxy. Every authenticated `POST /chat` is
enriched with the verified user e-mail and forwarded to `TARGET_URL`.
The backend at `TARGET_URL` is responsible for all chat logic — system
prompts, model selection, history, routing, tool calls, anything else.
VoxGate has no built-in LLM integration.

This document is the **strict** contract between VoxGate and that
backend. Any deviation surfaces as a `502` to the PWA.

## Request: VoxGate → backend

`POST <TARGET_URL>` with `Content-Type: application/json`. If
`TARGET_TOKEN` is configured, an `Authorization: Bearer <TARGET_TOKEN>`
header is added.

```json
{
  "user":        "<text the user typed or spoke>",
  "user_email":  "<verified Google e-mail of the signed-in user>",
  "session_id":  "<opaque, client-generated, [A-Za-z0-9_-]{8,128}>",
  "metadata": {
    "lang":     "<BCP-47 tag the PWA was using, e.g. de-CH>",
    "instance": "<INSTANCE_NAME from VoxGate's .env>"
  }
}
```

Field semantics:

| Field | Trust | Purpose |
|---|---|---|
| `user` | user-typed | Free text. Already validated for length (`MAX_PROMPT_LENGTH`, default 4000). |
| `user_email` | **server-injected, verified** | Authenticated by Google + allowlisted by the operator. Backends can rely on this for ACL decisions and *should not* trust any client-provided e-mail field. |
| `session_id` | client-generated | Opaque correlator. VoxGate keeps no state for it. The backend may use it as its own conversation key. |
| `metadata.lang` | client-set | The UI language at the moment of sending. May differ from `INSTANCE_NAME`'s default. Hint, not a guarantee. |
| `metadata.instance` | server-set | Useful when one backend serves multiple VoxGate instances (different families/contexts). |

Backends may receive additional `metadata.*` fields in future versions.
**Treat unknown fields as informational, do not reject them.**

## Response: backend → VoxGate

The backend must respond with HTTP 2xx **and** a JSON body of exactly
this shape:

```json
{ "response": "<assistant reply, plain string>" }
```

Strict rules:

- HTTP status `< 400`. `4xx` and `5xx` are forwarded as `502` to the
  PWA — the backend is the source of truth on what is or is not an
  error, but VoxGate intentionally collapses all backend errors into a
  single client-visible status.
- Body must be valid JSON. Plain-text responses are rejected.
- Body must be a JSON object (not an array, not a primitive).
- The object must contain key `"response"`.
- The value of `"response"` must be a string. Empty strings are
  allowed (e.g., the backend deliberately stays silent).

Anything else → VoxGate logs `backend_bad_shape` and returns `502`.

Additional keys in the response are tolerated but ignored — the PWA
sees only `{"response": ...}`. If you have metadata to surface in the
UI, propose extending the contract; do not stuff it into ad-hoc keys.

## Failure modes summary

| Backend behaviour | VoxGate response |
|---|---|
| Unreachable / connection refused / DNS fail / timeout | `502 Backend unreachable` |
| HTTP 4xx or 5xx | `502 Backend returned an error` |
| Non-JSON body | `502 Backend response was not JSON` |
| JSON without `response` string field | `502 Backend response did not match contract` |

For completeness, the PWA can also see request-validation errors that
never reach the backend — `422` when `text` is empty/too long or
`session_id` does not match `^[A-Za-z0-9_-]{8,128}$`. Backends do not
need to handle these: VoxGate rejects the request before forwarding.

## Minimal reference backend (Python)

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/")
async def chat(req: Request):
    body = await req.json()
    user = body["user"]
    email = body["user_email"]
    session = body["session_id"]
    # ... do whatever (LLM call, planner, lookup, …)
    return {"response": f"hello {email}, you said: {user}"}
```

Set `TARGET_URL=http://your-backend:port/` in the VoxGate `.env` and
you're talking. See [`backends.md`](backends.md) for richer examples.
