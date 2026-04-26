# VoxGate + Caddy bundle

Empfohlener Pfad fuer Self-Hosting mit eigener (Sub-)Domain. Caddy
holt das Lets-Encrypt-Zertifikat automatisch und reverse-proxyt auf
VoxGate. Der VoxGate-Container ist nur ueber Caddy erreichbar.

## Voraussetzungen

- Server mit Docker und freien Ports 80 und 443.
- DNS A/AAAA-Eintrag fuer `voxgate.example.com` zeigt auf den Server.
- Kein anderer Webserver auf 80/443.

## Start

```bash
cd deploy/caddy
cp .env.example .env
# Mindestens VOXGATE_DOMAIN, ACME_EMAIL und entweder ANTHROPIC_API_KEY
# oder TARGET_URL eintragen.
docker compose up -d
```

Beim ersten Start holt Caddy ein Zertifikat (kann 30-60 s dauern). Logs:

```bash
docker compose logs -f caddy
docker compose logs -f voxgate
```

Sobald `voxgate` einen Token loggt (oder du selbst einen in `.env`
gesetzt hast), oeffne `https://voxgate.example.com` im Browser, in der
DevTools-Console:

```js
localStorage.apiToken = "<token>"
```

Danach kannst du die PWA installieren ("Add to Home screen").

## Anpassungen

- **Mehrere Instanzen** (z.B. eine fuer Claude, eine fuer einen
  Custom-Bot): Compose-Datei kopieren, zweiten `voxgate-*`-Service
  ergaenzen, Caddyfile um einen weiteren Hostname-Block erweitern.
- **CSP**: VoxGate setzt seine eigene Content-Security-Policy. Im
  Caddyfile keine zusaetzliche `header Content-Security-Policy …`-Direktive
  ergaenzen — sie wuerde mit der serverseitigen kollidieren.

## Weitere Doku

- Konfiguration aller Env-Vars: [`../../SETUP.md`](../../SETUP.md)
- Sicherheits-Checkliste: [`../../SECURITY.md`](../../SECURITY.md)
- Backend-Beispiele fuer `/prompt`: [`../../docs/backends.md`](../../docs/backends.md)
