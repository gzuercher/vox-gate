# Contributing

Danke für dein Interesse an VoxGate. Diese Datei beschreibt den Workflow, die Konventionen und wie du neue Features ergänzt.

## Sprache

- **Kommunikation, Issues, PR-Beschreibungen, Commit-Messages:** Deutsch (Imperativ, z.B. *"Füge Validierung hinzu"*).
- **Code, Kommentare, technische Bezeichner, Doku-Strings:** Englisch.
- **UI-Texte:** Deutsch (Schweiz).

## Setup

```bash
git clone git@github.com:gzuercher/vox-gate.git
cd vox-gate
make setup        # venv anlegen, Abhängigkeiten installieren
make test         # Tests ausführen
make check        # Lint + Tests
```

## Code-Konventionen

Die verbindlichen Regeln liegen in `.claude/rules/` und gelten sowohl für menschliche Mitwirkende als auch für Claude Code:

- [`.claude/rules/security.md`](.claude/rules/security.md) — Keine Secrets im Code, Bearer-Token via Env-Var, Eingaben validieren.
- [`.claude/rules/code-quality.md`](.claude/rules/code-quality.md) — Strict Typing, keine leeren `catch`-Blöcke, Komponenten unter 200 Zeilen.
- [`.claude/rules/accessibility.md`](.claude/rules/accessibility.md) — Semantisches HTML, ARIA, Tastaturbedienung, Farbkontraste (WCAG AA).
- [`.claude/rules/dev-stack.md`](.claude/rules/dev-stack.md) — Tech-Stack und Verifikationsregeln.

Zusätzlich:

- **Linter:** `ruff` — Konfiguration in `pyproject.toml`, Line-Length 100. `make lint` muss grün sein.
- **Tests:** Jeder neue Endpoint braucht pytest-Tests in `tests/`. Externe Aufrufe (Anthropic, httpx) mocken — keine echten API-Calls in Tests.
- **Imports:** Absolute Pfade bevorzugen.
- **Keine neuen Dependencies** ohne Diskussion. VoxGate soll leichtgewichtig bleiben.

## Workflow

1. Feature-Branch von `main` abzweigen.
2. Implementieren — `make check` muss durchlaufen.
3. PR auf `main` öffnen mit aussagekräftiger Beschreibung (was, warum).
4. Bei sicherheitsrelevanten Änderungen (Auth, öffentliche APIs, Deployment, Personendaten) im PR explizit darauf hinweisen.

## Neue Endpoints hinzufügen

1. Pydantic-Request-Modell in `server.py` definieren (`Field(..., min_length=1, max_length=…)`).
2. Endpoint mit `_=Depends(verify_token)` schützen, falls Auth gewünscht.
3. Externe Calls in einer Funktion kapseln, damit Tests sie mocken können (siehe `_get_anthropic_client`).
4. Tests in `tests/test_server.py` ergänzen — mindestens: Happy Path, Validierungs-Fehler, Auth-Fehler, Backend-Fehler.
5. Endpoint in `README.md` unter "API-Referenz" dokumentieren.
6. Falls neue Env-Variable: `.env.example` und Konfigurations-Tabelle in `README.md` ergänzen.

## Arbeit mit Claude Code

VoxGate wird primär mit Claude Code entwickelt. Hilfreiche Slash-Commands:

- `/commit-push-pr` — Git-Workflow automatisieren
- `/review` — Code-Review des aktuellen Branches
- `/build-and-test` — Build und Tests ausführen
- `/security-review` — Sicherheits-Review der Änderungen

Wenn Claude einen Fehler macht: korrigiere sofort und dokumentiere die Lektion in `lessons.md` (Format: `- [Datum]: [Was falsch war] → [Korrekte Vorgehensweise]`). Bei wiederkehrenden Mustern ergänze stattdessen `CLAUDE.md` oder eine Regel unter `.claude/rules/`.

## Persönliche Einstellungen

Persönliche Overrides gehören in `.claude/settings.local.json` (gitignored), nicht in committed-Dateien.

## Erweiterung der Regeln

1. Neue Datei in `.claude/rules/` anlegen.
2. Frontmatter mit `globs` setzen, falls die Regel nur für bestimmte Dateitypen gelten soll.
3. Kurz, spezifisch und mit Begründung.
4. PR öffnen und im Team abstimmen.
