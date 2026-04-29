# VoxGate + Caddy bundle

Recommended path for self-hosting with your own (sub-)domain. Caddy
obtains the Let's Encrypt certificate automatically and reverse-proxies
to VoxGate. The VoxGate container is reachable only through Caddy.

## Prerequisites

- Server with Docker and free ports 80 and 443.
- DNS A/AAAA record for `voxgate.example.com` pointing at the server.
- No other web server on 80/443.

## Start

```bash
cd deploy/caddy
cp .env.example .env
# At minimum set VOXGATE_DOMAIN, ACME_EMAIL, and either
# ANTHROPIC_API_KEY or TARGET_URL.
docker compose up -d
```

On first start Caddy fetches a certificate (30-60 s). Logs:

```bash
docker compose logs -f caddy
docker compose logs -f voxgate
```

Open `https://voxgate.example.com` in the browser. The PWA shows a
**Sign in with Google** button. Use a Google account that you added to
`ALLOWED_EMAILS` in `.env`. After login you can install the PWA
("Add to Home screen").

## Customisation

- **Multiple instances** (e.g. one for Claude, one for a custom bot):
  copy the compose file, add a second `voxgate-*` service, extend the
  `Caddyfile` with another hostname block.
- **CSP**: VoxGate sets its own Content-Security-Policy. Do not add a
  separate `header Content-Security-Policy …` directive in the
  Caddyfile — it would collide with the server-side one.

## Further docs

- All env vars: [`../../docs/setup.md`](../../docs/setup.md)
- Security checklist: [`../../docs/security.md`](../../docs/security.md)
- `/prompt` backend examples: [`../../docs/backends.md`](../../docs/backends.md)
