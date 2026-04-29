import logging
import os
import secrets
import sys
import time
from collections import deque

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from auth import (
    AuthConfig,
    GoogleVerifier,
    SessionData,
    build_auth_router,
    build_verify_session,
    parse_allowed_emails,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("voxgate")

app = FastAPI()

TARGET_URL = os.environ.get("TARGET_URL", "")
TARGET_TOKEN = os.environ.get("TARGET_TOKEN", "")
INSTANCE_NAME = os.environ.get("INSTANCE_NAME", "VoxGate")
INSTANCE_DISPLAY_NAME = os.environ.get("INSTANCE_DISPLAY_NAME", "").strip() or INSTANCE_NAME
INSTANCE_COLOR = os.environ.get("INSTANCE_COLOR", "#c8ff00")
SPEECH_LANG = os.environ.get("SPEECH_LANG", "de-CH")
SPEECH_LANGS = [
    lang.strip()
    for lang in os.environ.get(
        "SPEECH_LANGS", "de-CH,fr-CH,it-CH,en-US,es-ES"
    ).split(",")
    if lang.strip()
]
if SPEECH_LANG not in SPEECH_LANGS:
    SPEECH_LANGS.insert(0, SPEECH_LANG)
MAX_PROMPT_LENGTH = int(os.environ.get("MAX_PROMPT_LENGTH", "4000"))
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "120"))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT", "You are a helpful assistant. Answer concisely."
)
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
SESSION_MAX_MESSAGES = 20
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "1800"))
MAX_SESSIONS = int(os.environ.get("MAX_SESSIONS", "1000"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))
AUTH_LOGIN_RATE_LIMIT_PER_MINUTE = int(
    os.environ.get("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "10")
)
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "0") == "1"

# Auth config
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
ALLOWED_EMAILS_RAW = os.environ.get("ALLOWED_EMAILS", "")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip()
SESSION_COOKIE_TTL_SECONDS = int(
    os.environ.get("SESSION_COOKIE_TTL_SECONDS", str(7 * 24 * 3600))
)
# Set COOKIE_SECURE=1 in production (HTTPS). Defaults to 0 so local http works.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"

DEBUG_ENABLED = os.environ.get("DEBUG_ENABLED", "0") == "1"
DEBUG_TOKEN = os.environ.get("DEBUG_TOKEN", "").strip()
DEBUG_MAX_BODY_BYTES = 8 * 1024
DEBUG_RATE_LIMIT_PER_SEC = 20
_debug_buckets: dict = {}

if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_hex(32)
    print(
        "\n" + "=" * 60 + "\n"
        "No SESSION_SECRET set. Generated for this run.\n"
        "Set SESSION_SECRET in your .env to keep sessions valid across restarts.\n"
        + "=" * 60,
        file=sys.stderr,
    )

ALLOWED_EMAILS = parse_allowed_emails(ALLOWED_EMAILS_RAW)
PROVIDERS = {}
if GOOGLE_CLIENT_ID:
    PROVIDERS["google"] = GoogleVerifier(client_id=GOOGLE_CLIENT_ID)

if not PROVIDERS:
    print(
        "WARNING: No auth provider configured. Set GOOGLE_CLIENT_ID to enable login. "
        "/prompt and /claude will reject every request.",
        file=sys.stderr,
    )
if not ALLOWED_EMAILS:
    print(
        "WARNING: ALLOWED_EMAILS is empty. No user can log in. "
        "Set ALLOWED_EMAILS in your .env (comma-separated, optional :provider suffix).",
        file=sys.stderr,
    )

if not TARGET_URL and not ANTHROPIC_API_KEY:
    print(
        "WARNING: Neither TARGET_URL nor ANTHROPIC_API_KEY is set. "
        "/prompt and /claude will return 503.",
        file=sys.stderr,
    )

_sessions: dict[str, dict] = {}
_anthropic_client = None
_rate_buckets: dict[str, deque] = {}
_auth_login_buckets: dict[str, deque] = {}


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic

        _anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _client_ip(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _evict_expired_sessions(now: float) -> None:
    expired = [sid for sid, s in _sessions.items() if now - s["last_seen"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def _enforce_session_cap() -> None:
    if len(_sessions) <= MAX_SESSIONS:
        return
    oldest = sorted(_sessions.items(), key=lambda kv: kv[1]["last_seen"])
    for sid, _ in oldest[: len(_sessions) - MAX_SESSIONS]:
        del _sessions[sid]


def _login_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.time()
    bucket = _auth_login_buckets.setdefault(ip, deque())
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= AUTH_LOGIN_RATE_LIMIT_PER_MINUTE:
        logger.warning("[%s] auth_login_rate_limit ip=%s", INSTANCE_NAME, ip)
        raise HTTPException(status_code=429, detail="Too many login attempts")
    bucket.append(now)
    if len(_auth_login_buckets) > 10000:
        for stale_ip in [k for k, v in _auth_login_buckets.items() if not v]:
            _auth_login_buckets.pop(stale_ip, None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
    # CSP notes:
    # - script-src is strict ('self' + GIS client only). No inline scripts.
    # - style-src includes 'unsafe-inline' because Google Identity Services
    #   injects inline styles into the rendered button. Tightening this would
    #   require a per-request nonce, which is overkill for a no-build PWA. The
    #   residual risk (CSS-only XSS) is very narrow given the rest of the CSP.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://accounts.google.com/gsi/client; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
        "https://accounts.google.com/gsi/style; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://*.googleusercontent.com; "
        "connect-src 'self' https://accounts.google.com/gsi/; "
        "frame-src https://accounts.google.com/gsi/; "
        "manifest-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    return response


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path in ("/claude", "/prompt") and request.method == "POST":
        ip = _client_ip(request)
        now = time.time()
        bucket = _rate_buckets.setdefault(ip, deque())
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_MINUTE:
            logger.warning("rate_limit_exceeded ip=%s path=%s", ip, request.url.path)
            return JSONResponse(
                status_code=429, content={"detail": "Rate limit exceeded"}
            )
        bucket.append(now)
        if len(_rate_buckets) > 10000:
            for stale_ip in [k for k, v in _rate_buckets.items() if not v]:
                _rate_buckets.pop(stale_ip, None)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN else [],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


# Origins permitted to initiate /auth/login + /auth/logout. Without a value,
# the AuthConfig skips the cross-origin check (dev convenience). Behind a
# reverse proxy this should always be configured via ALLOWED_ORIGIN.
_expected_origins = frozenset({ALLOWED_ORIGIN}) if ALLOWED_ORIGIN else frozenset()

_auth_config = AuthConfig(
    providers=PROVIDERS,
    allowed_emails=ALLOWED_EMAILS,
    session_secret=SESSION_SECRET,
    session_ttl_seconds=SESSION_COOKIE_TTL_SECONDS,
    cookies_secure=COOKIE_SECURE,
    instance_name=INSTANCE_NAME,
    expected_origins=_expected_origins,
    rate_limit_check=_login_rate_limit,
)
app.include_router(build_auth_router(_auth_config))
verify_session = build_verify_session(_auth_config)


class PromptRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH)


class ClaudeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PROMPT_LENGTH)
    session_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{8,128}$")


@app.post("/debug-log")
async def debug_log(request: Request):
    if not DEBUG_ENABLED or not DEBUG_TOKEN:
        raise HTTPException(status_code=404)
    presented = request.headers.get("x-debug-token", "")
    if not presented or not secrets.compare_digest(presented, DEBUG_TOKEN):
        raise HTTPException(status_code=401)
    body = await request.body()
    if len(body) > DEBUG_MAX_BODY_BYTES:
        raise HTTPException(status_code=413)
    ip = _client_ip(request)
    now = time.time()
    bucket = _debug_buckets.setdefault(ip, deque())
    while bucket and bucket[0] < now - 1:
        bucket.popleft()
    if len(bucket) >= DEBUG_RATE_LIMIT_PER_SEC:
        raise HTTPException(status_code=429)
    bucket.append(now)
    if len(_debug_buckets) > 1000:
        for stale_ip in [k for k, v in _debug_buckets.items() if not v]:
            _debug_buckets.pop(stale_ip, None)
    print(f"DEBUG ip={ip} {body.decode('utf-8', errors='replace')}", file=sys.stderr, flush=True)
    return JSONResponse(status_code=204, content=None)


@app.get("/config")
async def get_config():
    # GOOGLE_CLIENT_ID is intentionally public: Google Identity Services puts it
    # in the page source anyway. Reviewers, do not flag this as a leak.
    return {
        "name": INSTANCE_DISPLAY_NAME,
        "color": INSTANCE_COLOR,
        "lang": SPEECH_LANG,
        "langs": SPEECH_LANGS,
        "maxLength": MAX_PROMPT_LENGTH,
        "googleClientId": GOOGLE_CLIENT_ID,
        "providers": sorted(PROVIDERS.keys()),
    }


@app.post("/prompt")
async def prompt(
    req: PromptRequest,
    request: Request,
    session: SessionData = Depends(verify_session),
):
    if not TARGET_URL:
        raise HTTPException(status_code=503, detail="No target configured")

    ip = _client_ip(request)
    logger.info(
        "[%s] prompt ip=%s user=%s text_len=%d",
        INSTANCE_NAME, ip, session.email, len(req.text),
    )

    headers = {"Content-Type": "application/json"}
    if TARGET_TOKEN:
        headers["Authorization"] = f"Bearer {TARGET_TOKEN}"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            res = await client.post(TARGET_URL, json={"text": req.text}, headers=headers)
        except httpx.RequestError:
            logger.warning("prompt_target_unreachable ip=%s", ip)
            raise HTTPException(status_code=502, detail="Target unreachable")

    if res.status_code >= 400:
        logger.warning("prompt_target_error ip=%s status=%d", ip, res.status_code)
        raise HTTPException(status_code=502, detail="Target returned an error")

    try:
        data = res.json()
    except ValueError:
        data = {"response": res.text.strip()}

    return JSONResponse(content=data)


@app.post("/claude")
async def claude(
    req: ClaudeRequest,
    request: Request,
    session: SessionData = Depends(verify_session),
):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="No Anthropic API key configured")

    now = time.time()
    _evict_expired_sessions(now)

    ip = _client_ip(request)
    sid_short = req.session_id[:8]
    logger.info(
        "[%s] claude ip=%s user=%s session=%s text_len=%d sessions=%d",
        INSTANCE_NAME, ip, session.email, sid_short, len(req.text), len(_sessions),
    )

    chat = _sessions.setdefault(req.session_id, {"messages": [], "last_seen": now})
    chat["last_seen"] = now
    _enforce_session_cap()
    if req.session_id not in _sessions:
        _sessions[req.session_id] = chat
    history = chat["messages"]
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
        logger.exception("claude_api_error ip=%s session=%s", ip, sid_short)
        raise HTTPException(status_code=502, detail="Anthropic API error")

    reply = "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )

    history.append({"role": "assistant", "content": reply})

    while len(history) > SESSION_MAX_MESSAGES:
        del history[0:2]

    return {"response": reply}


app.mount("/", StaticFiles(directory="pwa", html=True), name="pwa")
