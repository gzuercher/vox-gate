---
description: Run build and tests, fix any errors
---

1. Run `make check` (lint + tests). If `make` is unavailable, fall
   back to `.venv/bin/ruff check .` followed by `.venv/bin/pytest`.
2. If errors appear:
   - Analyse the message.
   - Fix the underlying cause (no shortcuts that hide the failure).
   - Re-run until everything is green.
3. Report the result: what ran, what failed, what was fixed.
