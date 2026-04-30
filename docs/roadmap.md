# Roadmap

Living document — ideas for future development. Nothing here is a
commitment. Each entry has a rough **value** (why bother) and
**cost/risk** (why it might hurt).

The goal of VoxGate is to stay a small, dependency-light voice
gateway. The current focus is to take VoxGate into **productive use**
and learn from real usage. Items are grouped by priority, not by
estimated time:

- **Höher** — clear value for productive use; pick from here first.
- **Normal** — useful, but not a precondition for productive use.
- **Deliberately not planned** — explicit rejections, with reasons.

---

## Höher

### Automatic dark/light mode
- **Value:** the UI is currently dark-only. Daylight readability on
  phones suffers when the system is set to light mode. Following
  `prefers-color-scheme` would make VoxGate fit the device context
  without manual toggling — relevant for productive daily use.
- **Cost:** small. Move the existing palette into a `:root` /
  `@media (prefers-color-scheme: light)` split, derive `--accent-dim`
  for the light variant, verify contrast on the auth overlay and
  message bubbles. Per-instance `INSTANCE_COLOR` already drives the
  accent, so no server change needed.

### Streaming responses (SSE)
- **Value:** backend replies start playing/showing within ~500 ms
  instead of after the full response. The single biggest
  perceived-quality win in the document — without it VoxGate feels
  noticeably slower than ChatGPT-style apps, and the gap grows with
  longer answers.
- **Cost:** **contract change.** Today the backend returns one JSON
  object; for streaming we'd extend the contract to allow SSE or
  chunked transfer-encoding from TARGET_URL, with VoxGate forwarding
  chunks to the PWA. Backends would need to opt in. PWA: incremental
  TTS plus text accumulation. The tricky part is making
  `speechSynthesis` speak partial sentences without sounding chopped.

### Additional identity providers (Microsoft, Apple, generic OIDC)
- **Value:** users without a Google account get a familiar option, and
  organisations on Microsoft 365 / Entra ID can plug their tenant in
  directly. The backend already routes through a `/auth/login/{provider}`
  endpoint with a generic verifier protocol, so additional providers
  slot in without a data-model change.
- **Cost:** per provider — register a generic OIDC verifier (issuer URL,
  audience, JWKS auto-fetch), wire a frontend button, extend the CSP for
  the new identity domain. ~1 working day per provider once the first
  non-Google one has been done.

### iOS Safari minimum support
- **Value:** unblock iPhone users who currently get a half-broken UX
  (Web Speech API is limited).
- **Cost:** at minimum: detect Safari, show a clear "open in Chrome"
  banner instead of silently failing. Going further (server-side STT
  fallback) is a separate item under Normal.

### Image / camera input
- **Value:** point phone camera at something, ask the backend about it.
  Multimodal is a natural fit for a phone voice gateway, currently
  unused. Whether the backend's LLM supports vision is the backend's
  problem.
- **Cost:** **contract change.** PWA: capture button + preview. Server:
  image upload path (base64 in JSON, or multipart). Extension to the
  TARGET_URL contract (e.g. `attachments: [{mime, data}]`). Privacy
  considerations (where does the image live, audit log, etc.) move
  to the backend along with the data.

---

## Normal

### Server-side STT fallback (Whisper)
- **Value:** unlocks iOS/Safari and any browser with weak Web Speech
  support. Vastly better recognition quality and dialect tolerance —
  a *real* answer to "Schwyzerdütsch erkennen".
- **Cost:** new external dependency (OpenAI Whisper API or a local
  whisper.cpp container). Audio upload path. Cost per request. Token
  privacy concerns. Optional via `STT_BACKEND=webspeech|whisper`.

### Server-side TTS (better voices)
- **Value:** device-installed voices are inconsistent. ElevenLabs /
  OpenAI TTS / Azure produce reliably good audio across phones.
- **Cost:** another external dependency, another API key, latency, per-
  request cost. Streaming support needed to keep perceived speed.

### Edge-pre-auth bundle
- **Value:** ship `deploy/caddy-private/` with Basic Auth or
  Cloudflare Access pre-wired for closed-group setups. Documents the
  pattern, removes guesswork.
- **Cost:** more bundles to maintain. Decide carefully whether docs
  alone (current state) are enough.

### Native mobile apps (iOS/Android)
- **Value:** access to platform STT (Apple's, Google's), better
  background behaviour, push notifications, real wake-word support.
- **Cost:** two new codebases to maintain. PWA-first philosophy
  abandoned. Probably only worth it if the user base demands it.

### Wake word ("Hey VoxGate")
- **Value:** hands-free triggering, true voice assistant feel.
- **Cost:** wake-word detection wants always-on mic, which a PWA
  cannot really do reliably. Native app dependency. Privacy theatre
  unless local — and local wake-word adds yet another dependency.

### Per-user UI settings (lang, voice, mute)
- **Value:** today these are device-local (`localStorage`). Multi-device
  users would benefit from server-side preferences keyed by
  `user_email`. Login already identifies users, so the foundation is
  in place.
- **Cost:** small server-side store (`/auth/me` extended with
  `preferences`), small settings UI in the PWA. Backend stays
  uninvolved — preferences are a VoxGate-only concern.

---

## Deliberately not planned

To keep the roadmap honest, here's what we are *not* going to do, and
why:

- **Built-in user accounts with passwords.** Out of scope. Login goes
  through external identity providers (Google today; OIDC for others
  later). Bringing in our own password reset, email verification, etc.
  is not core to "voice in, voice out".
- **Token in URL (`?key=…`) for easy sharing.** Security antipattern.
  Tokens leak via referer headers, browser history, and access logs.
- **Bundling cloudflared/Tailscale as docker-compose recipes.** The
  upstream tools have excellent setup UIs and docs. We point at them
  in `docs/setup.md` instead of duplicating moving targets.
- **Built-in MCP-server bridge.** Voice-driven tool execution would
  turn VoxGate from a small voice forwarder into a multi-round
  tool-use orchestrator with its own security perimeter, allowlists,
  and connection management. The right place for that complexity is
  the user's own `/chat` backend: it can speak MCP, do tool-use loops
  with the LLM internally, and hand VoxGate just the final reply.
  VoxGate stays small.
- **Built-in LLM integration (Claude/OpenAI/etc.).** Removed in
  the 2026-04-30 refactor. VoxGate is a voice + auth gateway, not an
  LLM client. If you want voice-to-Claude, run a small adapter
  container behind TARGET_URL — that pattern keeps the LLM choice,
  pricing, and credentials out of VoxGate entirely.
- **Local-only mode (Whisper.cpp + llama.cpp + Piper).** Different
  deployment story (model downloads, GPU/CPU choices, far lower
  reply quality), different audience, and a completely separate
  ops-and-update treadmill. If this is ever wanted, it is a sibling
  project ("VoxGate Local"), not a flag inside this one.
- **Plugin / skill ecosystem.** Plugin protocols, sandboxing,
  versioning, and distribution would turn VoxGate into a platform.
  Custom capabilities belong in the user's `/chat` backend, where
  they can be as small or as elaborate as needed without VoxGate
  carrying the maintenance.
- **Hosted SaaS offering.** Abuse handling, payment, GDPR, on-call —
  that is a different business, not a feature. VoxGate stays a thing
  you self-host.

---

## How to use this document

1. When picking work, prefer **Höher** over Normal unless there is an
   explicit reason to jump.
2. Before starting any item, write a short plan — the roadmap entry
   is not a spec.
3. When something here turns out to be a bad idea, delete it and
   record why. Stale items rot the document.
4. Add new ideas with the same value/cost framing. Vague ideas
   ("better UX") have no place here — be concrete.
5. If a Normal entry's own cost note disqualifies it ("would change
   what VoxGate is", "different business", "platform territory"), it
   does not belong on the roadmap — move it to *Deliberately not
   planned* or remove it.
