import os
import sys

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI()

API_TOKEN = os.environ.get("API_TOKEN", "")
TARGET_URL = os.environ.get("TARGET_URL", "")
TARGET_TOKEN = os.environ.get("TARGET_TOKEN", "")
INSTANCE_NAME = os.environ.get("INSTANCE_NAME", "VoxGate")
INSTANCE_COLOR = os.environ.get("INSTANCE_COLOR", "#c8ff00")
SPEECH_LANG = os.environ.get("SPEECH_LANG", "de-CH")
MAX_PROMPT_LENGTH = int(os.environ.get("MAX_PROMPT_LENGTH", "4000"))
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "120"))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT", "You are a helpful assistant. Answer concisely."
)
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
SESSION_MAX_MESSAGES = 20

_sessions: dict[str, list[dict]] = {}
_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic

        _anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client

if not API_TOKEN:
    print(
        "WARNING: API_TOKEN is not set. The /prompt endpoint is unauthenticated!\n"
        "Set API_TOKEN environment variable to enable authentication.",
        file=sys.stderr,
    )

if not TARGET_URL:
    print(
        "WARNING: TARGET_URL is not set. The server has no forwarding target.\n"
        "Set TARGET_URL to the backend endpoint (e.g. http://host:port/endpoint).",
        file=sys.stderr,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN else [],
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)

security = HTTPBearer(auto_error=False)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not API_TOKEN:
        return
    if not credentials or credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class PromptRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH)


class ClaudeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH)
    session_id: str = Field(..., min_length=1, max_length=128)


@app.get("/config")
async def get_config():
    return {
        "name": INSTANCE_NAME,
        "color": INSTANCE_COLOR,
        "lang": SPEECH_LANG,
        "maxLength": MAX_PROMPT_LENGTH,
    }


@app.post("/prompt")
async def prompt(req: PromptRequest, _=Depends(verify_token)):
    if not TARGET_URL:
        raise HTTPException(status_code=503, detail="No target configured")

    headers = {"Content-Type": "application/json"}
    if TARGET_TOKEN:
        headers["Authorization"] = f"Bearer {TARGET_TOKEN}"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            res = await client.post(TARGET_URL, json={"text": req.text}, headers=headers)
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Target unreachable")

    if res.status_code >= 400:
        raise HTTPException(status_code=502, detail="Target returned an error")

    try:
        data = res.json()
    except ValueError:
        data = {"response": res.text.strip()}

    return JSONResponse(content=data)


@app.post("/claude")
async def claude(req: ClaudeRequest, _=Depends(verify_token)):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="No Anthropic API key configured")

    history = _sessions.setdefault(req.session_id, [])
    history.append({"role": "user", "content": req.text})

    try:
        client = _get_anthropic_client()
        message = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history,
        )
    except Exception:
        history.pop()
        raise HTTPException(status_code=502, detail="Anthropic API error")

    reply = "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )

    history.append({"role": "assistant", "content": reply})

    while len(history) > SESSION_MAX_MESSAGES:
        del history[0:2]

    return {"response": reply}


app.mount("/", StaticFiles(directory="pwa", html=True), name="pwa")
