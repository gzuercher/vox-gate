<!--
Keep PRs small and focused. One concern per PR.
`make check` must be green. UI changes need a manual browser
verification note.
-->

## What

<!-- One or two sentences. What does this PR change? -->

## Why

<!-- The motivation. A bug to fix, a use case to enable, a roadmap
item being picked up. Link the issue/discussion if applicable. -->

## Security-relevant?

<!-- Tick if any of these apply: changes to auth, allowlist handling,
session cookies, CSRF, CSP, rate limiting, the /chat → TARGET_URL
forwarding contract, secrets handling, or anything user-visible
that affects what a backend at TARGET_URL receives. -->

- [ ] yes — and I have noted what specifically changed
- [ ] no

## Verified

- [ ] `make check` passes locally
- [ ] If UI changed: clicked through the affected flow in a browser
- [ ] If a new env var was added: documented in `.env.example`,
      `deploy/caddy/.env.example`, and `docs/setup.md`
- [ ] If `/chat` ↔ TARGET_URL contract changed: updated
      `docs/integration.md` *first*
