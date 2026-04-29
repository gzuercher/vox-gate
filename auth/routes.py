import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pydantic import BaseModel

from .providers import AuthError, IdpVerifier, VerifiedIdentity
from .session import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    SessionData,
    clear_session_cookies,
    csrf_matches,
    issue_session_cookies,
    load_session,
)

logger = logging.getLogger("voxgate.auth")


@dataclass
class AuthConfig:
    providers: dict[str, IdpVerifier]
    # Allowlist: lowercased email -> optional provider name.
    # If provider is None, every configured provider is acceptable for that email.
    allowed_emails: dict[str, Optional[str]]
    session_secret: str
    session_ttl_seconds: int
    cookies_secure: bool
    instance_name: str = "voxgate"
    # Origins that may initiate state-changing auth requests (login, logout).
    # Empty set = no enforcement (dev convenience). In production this should
    # mirror ALLOWED_ORIGIN so that login-CSRF cannot fix a victim's session.
    expected_origins: frozenset[str] = field(default_factory=frozenset)
    # Optional pre-flight rate-limit hook so the server can plug in its IP-based limiter.
    rate_limit_check: Optional[Callable[[Request], None]] = field(default=None)


def parse_allowed_emails(raw: str) -> dict[str, Optional[str]]:
    """
    Parse ALLOWED_EMAILS env var.

    Format: comma-separated entries. Each entry is either ``email`` or ``email:provider``.
    Empty/whitespace entries are ignored. Email is lowercased and stripped.
    Entries with more than one colon (e.g. ``a@b.c:google:extra``) are rejected
    with a warning — that pattern would silently lock the user out otherwise.
    """
    out: dict[str, Optional[str]] = {}
    for raw_entry in raw.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        if ":" in entry:
            email, _, provider = entry.partition(":")
            email = email.strip().lower()
            provider = provider.strip().lower() or None
            if provider and ":" in provider:
                logger.warning(
                    "ALLOWED_EMAILS: ignoring entry %r — extra colon in provider",
                    raw_entry,
                )
                continue
        else:
            email = entry.lower()
            provider = None
        if email:
            out[email] = provider
    return out


def _allowlist_check(config: AuthConfig, identity: VerifiedIdentity) -> bool:
    if identity.email not in config.allowed_emails:
        return False
    bound = config.allowed_emails[identity.email]
    if bound is None:
        return True
    return bound == identity.provider


def _check_origin(config: AuthConfig, request: Request) -> None:
    """Block cross-site POSTs to /auth/login and /auth/logout.

    SameSite=Strict on the session cookie does not protect the login endpoint
    itself (no cookie exists yet at that point), so we reject any request whose
    Origin (or Referer fallback) is outside `expected_origins`. With no
    `expected_origins` configured we skip — the dev convenience case.
    """
    if not config.expected_origins:
        return
    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        # Fall back to Referer's origin component. Some old browsers omit Origin.
        referer = (request.headers.get("referer") or "").strip()
        if referer:
            # Strip path and query.
            try:
                from urllib.parse import urlparse

                parsed = urlparse(referer)
                if parsed.scheme and parsed.netloc:
                    origin = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                origin = ""
    if origin not in config.expected_origins:
        logger.warning(
            "[%s] auth_cross_origin_blocked path=%s origin=%r",
            config.instance_name, request.url.path, origin,
        )
        raise HTTPException(status_code=403, detail="Cross-site request blocked")


class LoginBody(BaseModel):
    id_token: str


def build_auth_router(config: AuthConfig) -> APIRouter:
    router = APIRouter(prefix="/auth")

    @router.get("/me")
    def me(
        session_cookie: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        session = load_session(
            cookie_value=session_cookie,
            secret=config.session_secret,
            max_age=config.session_ttl_seconds,
        )
        if session is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        # Live-check allowlist on every status call so revocation takes effect quickly.
        identity = VerifiedIdentity(
            email=session.email, provider=session.provider, subject=session.subject
        )
        if not _allowlist_check(config, identity):
            raise HTTPException(status_code=403, detail="Email no longer allowed")
        return {"email": session.email, "provider": session.provider}

    @router.get("/providers")
    def providers():
        return {"providers": sorted(config.providers.keys())}

    @router.post("/login/{provider}")
    def login(
        provider: str,
        body: LoginBody,
        request: Request,
        response: Response,
    ):
        _check_origin(config, request)
        if config.rate_limit_check is not None:
            config.rate_limit_check(request)
        verifier = config.providers.get(provider)
        if verifier is None:
            raise HTTPException(status_code=404, detail="Unknown auth provider")
        try:
            identity = verifier.verify(body.id_token)
        except AuthError as exc:
            # Cap the exception string so accidental token fragments cannot leak.
            logger.warning(
                "[%s] auth_verify_failed provider=%s reason=%s",
                config.instance_name, provider, str(exc)[:120],
            )
            raise HTTPException(status_code=401, detail="Invalid token") from exc
        if not _allowlist_check(config, identity):
            logger.warning(
                "[%s] auth_not_allowed provider=%s email=%s",
                config.instance_name, provider, identity.email,
            )
            raise HTTPException(status_code=403, detail="Email not allowed")
        issue_session_cookies(
            response,
            secret=config.session_secret,
            email=identity.email,
            provider=identity.provider,
            subject=identity.subject,
            ttl_seconds=config.session_ttl_seconds,
            secure=config.cookies_secure,
        )
        logger.info(
            "[%s] auth_login_ok provider=%s email=%s",
            config.instance_name, identity.provider, identity.email,
        )
        return {"email": identity.email, "provider": identity.provider}

    @router.post("/logout")
    def logout(
        request: Request,
        response: Response,
        session_cookie: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
        csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
    ):
        # Cross-site POST cannot log a victim out (availability attack).
        _check_origin(config, request)
        # Idempotent: logout when not logged in is a no-op.
        # When a session is present, require the CSRF token so an attacker
        # cannot wipe a victim's session via a forged same-site request.
        if session_cookie:
            if not _csrf_ok(session_cookie, csrf_cookie, x_csrf_token, config):
                raise HTTPException(status_code=403, detail="CSRF token mismatch")
        clear_session_cookies(response, secure=config.cookies_secure)
        return {"ok": True}

    return router


def _csrf_ok(
    session_cookie_value: Optional[str],
    csrf_cookie: Optional[str],
    header: Optional[str],
    config: AuthConfig,
) -> bool:
    """Atomic CSRF validation: header must match cookie, and (if a valid signed
    session is present) the cookie must match the csrf bound into the session.

    Returns True only when *all* required pieces line up. Centralised here so
    that future protected endpoints can call the same predicate instead of
    re-implementing the chain.
    """
    if not csrf_matches(header, csrf_cookie):
        return False
    if session_cookie_value:
        session = load_session(
            cookie_value=session_cookie_value,
            secret=config.session_secret,
            max_age=config.session_ttl_seconds,
        )
        if session is None:
            return False
        if not csrf_matches(session.csrf, csrf_cookie):
            return False
    return True


def build_verify_session(config: AuthConfig):
    """Return a FastAPI dependency that validates session + CSRF and yields SessionData."""

    def verify_session(
        request: Request,
        session_cookie: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
        csrf_cookie: Optional[str] = Cookie(default=None, alias=CSRF_COOKIE),
        x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
    ) -> SessionData:
        session = load_session(
            cookie_value=session_cookie,
            secret=config.session_secret,
            max_age=config.session_ttl_seconds,
        )
        if session is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        # Atomic CSRF validation: header == csrf_cookie == session.csrf.
        # Splitting the comparisons across multiple if-blocks is brittle —
        # a future refactor could accidentally reorder them. Keep it in one
        # predicate.
        if not (
            csrf_matches(x_csrf_token, csrf_cookie)
            and csrf_matches(session.csrf, csrf_cookie)
        ):
            raise HTTPException(status_code=403, detail="CSRF token mismatch")
        identity = VerifiedIdentity(
            email=session.email, provider=session.provider, subject=session.subject
        )
        if not _allowlist_check(config, identity):
            raise HTTPException(status_code=403, detail="Email no longer allowed")
        request.state.user_email = session.email
        request.state.user_provider = session.provider
        return session

    return verify_session
