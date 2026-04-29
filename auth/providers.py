from dataclasses import dataclass
from typing import Protocol


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    email: str
    provider: str
    subject: str


class IdpVerifier(Protocol):
    name: str

    def verify(self, id_token: str) -> VerifiedIdentity: ...


class GoogleVerifier:
    name = "google"

    def __init__(self, client_id: str):
        if not client_id:
            raise ValueError("GoogleVerifier requires a non-empty client_id")
        self._client_id = client_id

    def verify(self, id_token: str) -> VerifiedIdentity:
        # Imported lazily so the dependency is only required when Google is configured.
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        try:
            claims = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
                self._client_id,
            )
        except ValueError as exc:
            raise AuthError(f"invalid Google ID token: {exc}") from exc

        if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise AuthError("unexpected issuer")
        if not claims.get("email_verified"):
            raise AuthError("email not verified by Google")
        email = (claims.get("email") or "").strip().lower()
        subject = claims.get("sub") or ""
        if not email or not subject:
            raise AuthError("token missing email or subject")
        return VerifiedIdentity(email=email, provider=self.name, subject=subject)
