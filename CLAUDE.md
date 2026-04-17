# VoiceClaude – Claude Code Playbook

Voice-controlled PWA that sends speech input to a FastAPI server, which invokes the Claude Code CLI.

## Grundhaltung

- Frage nach, statt zu raten. Unsicherheit offen kommunizieren.
- Keine irreversiblen Aktionen ohne explizite Bestätigung (Dateien löschen, pushen, deployen).
- Keine Secrets, Passwörter oder API-Keys in Dateien speichern.
- Änderungen beschreiben bevor sie gemacht werden, wenn sie grösseren Umfang haben.

## Sprache

- Kommunikation mit dem Benutzer: Deutsch
- Entwicklung (Code, Kommentare, Dokumentation, README, Variablen, Funktionen, technische Bezeichner): Englisch
- Ausnahme: UI-Texte richten sich nach der Zielsprache des Produkts (Deutsch).
- Commit-Messages: Deutsch, Imperativ ("Füge Validierung hinzu")

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn
- **Frontend:** Vanilla HTML/CSS/JS, Web Speech API, PWA
- **CLI:** Claude Code (`claude -p`)
- **Reverse Proxy:** Caddy (production)

## Build & Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Fehler-Lernen

Wenn du korrigiert wirst, dokumentiere die Lektion in `lessons.md`:
`- [Datum]: [Was falsch war] → [Korrekte Vorgehensweise]`

## Eskalation

Gib eine sichtbare Warnung (⚠️ Review empfohlen) bei:
- Authentifizierung und Zugriffsrechte
- Öffentliche APIs
- Deployment und Infrastruktur
- Personendaten (DSG/DSGVO)

## Entwickler-Regeln

Für technische Details gelten zusätzlich die Regeln in `.claude/rules/`:
- `security.md` — Sicherheitsregeln
- `code-quality.md` — Codequalität und Standards
- `accessibility.md` — Zugänglichkeit
