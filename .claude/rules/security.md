---
description: Security checks for code files
globs: "*.ts,*.tsx,*.js,*.jsx,*.php"
---

# Security

- No secrets (API keys, passwords, tokens) in code. Use environment variables.
- Validate all user input: zod (TypeScript) or Laravel Validation (PHP).
- SQL: parameterized statements or ORM only. Never string concatenation.
- No `dangerouslySetInnerHTML` without DOMPurify.
- No `eval()`, `Function()`, or `innerHTML` with user input.
- HTTP responses: no sensitive data in error messages.
- API routes: verify authentication and authorization.
- PHP: never use `$_GET` / `$_POST` directly; always sanitize.
- Laravel: enable mass assignment protection (`$fillable` / `$guarded`).
