---
description: Tech Stacks, Build-Commands und Projektstruktur für Entwicklungsprojekte
globs: "*.ts,*.tsx,*.js,*.jsx,*.php,*.blade.php,package.json,composer.json"
---

# Entwicklungs-Stack

## Tech Stacks

### Next.js (Standard für neue Projekte)
- Framework: Next.js (App Router) mit TypeScript
- Styling: Tailwind CSS
- Paketmanager: pnpm
- Linting: ESLint, Prettier
- Tests: vitest, React Testing Library
- ORM: Prisma oder Drizzle
- Auth: NextAuth.js / Auth.js
- Validierung: zod

### PHP (Legacy und Laravel)
- WordPress: Theme/Plugin-Entwicklung, WooCommerce
- Laravel: Composer, PHPUnit, Laravel Pint
- Custom PHP: PSR-12 Standard

## Build & Test Commands

### Next.js
```bash
pnpm install        # Install dependencies
pnpm dev            # Development server
pnpm build          # Production build
pnpm test           # Run tests
pnpm lint           # Linting
pnpm format         # Prettier
```

### Laravel
```bash
composer install     # Install dependencies
php artisan serve    # Dev server
php artisan test     # Run tests
./vendor/bin/pint    # Formatting
```

### WordPress
```bash
composer install     # Install dependencies (if Composer is used)
npm run build        # Asset build (if available)
```

## Verifikation

Prüfe JEDE Änderung bevor du sie als fertig meldest:
1. Build muss durchlaufen
2. Linting muss bestehen
3. Falls UI-Änderung: beschreibe was du visuell erwartest

## Verbotene Eigenimplementierungen

Baue folgendes NIEMALS selbst. Verwende die genannte Bibliothek oder frage nach:

| Thema | Verwende stattdessen |
|---|---|
| Auth/Login | NextAuth.js / Auth.js (Next.js), Laravel Sanctum (PHP) |
| Passwort-Hashing | bcrypt, argon2 |
| JWT | jose |
| E-Mail | Resend, Postmark |
| Zahlungen | Stripe SDK |
| Datei-Upload | UploadThing, presigned URLs |
| Rate Limiting | @upstash/ratelimit, Laravel throttle |
| Validierung | zod (TS), Laravel Validation (PHP) |

## Projektstruktur (Next.js)

```
src/
├── app/              # App Router pages and layouts
├── components/
│   ├── ui/           # Reusable UI components
│   └── features/     # Domain-specific components
├── lib/              # Utility functions, configurations
├── hooks/            # Custom React hooks
├── types/            # TypeScript types
└── server/           # Server logic, DB queries, services
```
