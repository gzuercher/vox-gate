---
description: Code quality rules for TypeScript and PHP
globs: "*.ts,*.tsx,*.js,*.jsx,*.php"
---

# Code quality

## TypeScript / JavaScript
- Strict mode: no `any` types; type all functions.
- Error handling: try/catch with meaningful messages; never empty catch blocks.
- No `console.log` in production code. Use a logger (pino).
- Components under 200 lines. Split when exceeded.
- No duplicated code. Extract shared logic into helpers.
- Imports: prefer absolute paths (e.g. `@/lib/utils`).

## PHP
- Follow the PSR-12 coding standard.
- Typing: use PHP 8+ type hints.
- No silenced errors (avoid the `@` operator).
- WordPress: document hooks and filters.
- Laravel: use Form Requests for validation, not controller validation.
