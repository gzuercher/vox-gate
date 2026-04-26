# VoxGate – Claude Code Playbook

Voice gateway PWA – each instance forwards speech input via HTTP to a configurable backend.
No Claude CLI in the container; the server is a pure forwarding proxy.

## Working principles

- Ask instead of guessing. Communicate uncertainty openly.
- No irreversible actions without explicit confirmation (deleting files, pushing, deploying).
- Never store secrets, passwords, or API keys in files.
- Describe changes before making them when they are non-trivial in scope.

## Language

- **All project content is English**: code, comments, documentation,
  README, commit messages, variable and function names, technical
  identifiers.
- **Exception:** UI text follows the product target language (Swiss
  German for the PWA).
- Conversation language with the user follows the user's lead in chat.

## Tech stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, httpx
- **Frontend:** Vanilla HTML/CSS/JS, Web Speech API, PWA
- **Container:** Docker, docker-compose
- **Reverse proxy:** Caddy (production)

## Build & run

```bash
docker compose up -d            # Docker
# or
make setup && make run          # local
```

## Learning from mistakes

When you are corrected, record the lesson in `docs/lessons.md`:
`- [YYYY-MM-DD]: [What was wrong] → [Correct approach]`

## Escalation

Show a visible warning (⚠️ Review recommended) for changes touching:
- Authentication and access control
- Public APIs
- Deployment and infrastructure
- Personal data (DSG/GDPR)

## Developer rules

For technical details the rules in `.claude/rules/` apply additionally:
- `security.md` — security rules
- `code-quality.md` — code quality and standards
- `accessibility.md` — accessibility
- `dev-stack.md` — development stack and verification
