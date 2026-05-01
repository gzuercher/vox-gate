# Security policy

VoxGate authenticates users (Google Sign-In + operator allowlist),
forwards their authenticated requests to a backend at `TARGET_URL`,
and acts as the auth boundary in front of that backend. Issues that
weaken any of those boundaries are taken seriously.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security problems.**

Instead, report privately to the maintainer:

- **GitHub:** open a [private vulnerability report](https://github.com/gzuercher/vox-gate/security/advisories/new)
  via the Security tab. This is the preferred channel.

Include:

- A description of the issue and where it lives (file/path/endpoint).
- Steps to reproduce, ideally a minimal proof-of-concept.
- Your assessment of impact (information disclosure, privilege
  escalation, denial of service, …).
- Whether the issue is already public anywhere.

You will get an acknowledgement within **5 business days**. A fix
plan or a "won't fix" decision (with reasoning) within **30 days**.
If the issue is critical and actively exploitable, an out-of-band
fix is shipped sooner. After a fix is released, the reporter is
credited in the changelog unless they prefer to stay anonymous.

## In scope

- The VoxGate server (`server.py`, `auth/`).
- The PWA (`pwa/`).
- The bundled Caddy deployment (`deploy/caddy/`).
- The default configuration values shipped in `.env.example` and
  `deploy/caddy/.env.example`.

## Out of scope

- The backend running at the operator-configured `TARGET_URL`. Its
  security is the operator's responsibility.
- Issues that require an operator to deliberately weaken the
  configuration documented in [`docs/security.md`](docs/security.md)
  (the operator security checklist) — e.g. disabling `COOKIE_SECURE`
  on a public deployment, or adding `*` to `ALLOWED_ORIGIN`.
- Vulnerabilities in upstream dependencies (FastAPI, httpx,
  google-auth, itsdangerous, Caddy). Please report those upstream;
  we will take the fix once a release is available.
- Browser-specific behaviour outside our control (e.g. Safari Web
  Speech limitations).

## Operator security checklist

Operator-side hardening — what to set in `.env`, what to layer at
the edge, residual risks — is documented in
[`docs/security.md`](docs/security.md). That checklist is part of
"using VoxGate safely" rather than the vulnerability-disclosure
process governed by this document.
