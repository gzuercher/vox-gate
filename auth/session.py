import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from fastapi import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

logger = logging.getLogger("voxgate.auth.session")

SESSION_COOKIE = "vg_session"
CSRF_COOKIE = "vg_csrf"
_SERIALIZER_SALT = "voxgate.session.v1"


@dataclass(frozen=True)
class SessionData:
    email: str
    provider: str
    subject: str
    csrf: str


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret, salt=_SERIALIZER_SALT)


def issue_session_cookies(
    response: Response,
    *,
    secret: str,
    email: str,
    provider: str,
    subject: str,
    ttl_seconds: int,
    secure: bool,
) -> str:
    csrf = secrets.token_urlsafe(32)
    payload = {"email": email, "provider": provider, "subject": subject, "csrf": csrf}
    token = _serializer(secret).dumps(payload)
    cookie_kwargs = {
        "max_age": ttl_seconds,
        "secure": secure,
        "samesite": "strict",
        "path": "/",
    }
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **cookie_kwargs)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **cookie_kwargs)
    return csrf


def clear_session_cookies(response: Response, *, secure: bool) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=secure, samesite="strict")


def load_session(
    *, cookie_value: Optional[str], secret: str, max_age: int
) -> Optional[SessionData]:
    if not cookie_value:
        return None
    try:
        payload = _serializer(secret).loads(cookie_value, max_age=max_age)
    except SignatureExpired:
        logger.info("session_expired")
        return None
    except BadSignature:
        # Either tampering, an old cookie signed with a previous SESSION_SECRET,
        # or a stray value from another app on the same domain. Log so brute-force
        # attempts on the signing key are visible in the audit trail.
        logger.warning("session_bad_signature")
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return SessionData(
            email=payload["email"],
            provider=payload["provider"],
            subject=payload["subject"],
            csrf=payload["csrf"],
        )
    except KeyError:
        return None


def csrf_matches(header_value: Optional[str], cookie_value: Optional[str]) -> bool:
    if not header_value or not cookie_value:
        return False
    return secrets.compare_digest(header_value, cookie_value)
