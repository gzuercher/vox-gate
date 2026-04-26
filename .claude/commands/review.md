---
description: Code review of the current branch
---

Run a thorough code review:

1. Show `git diff main...HEAD` (or whatever the main branch is).
2. For every changed file check for:
   - Security issues (see `.claude/rules/security.md`)
   - Code quality (see `.claude/rules/code-quality.md`)
   - Accessibility for UI changes (see `.claude/rules/accessibility.md`)
3. Verify that tests are present and meaningful.
4. Summarize:
   - ✅ What is good
   - ⚠️ What should be improved (with a concrete suggestion)
   - 🛑 What is blocking (security, breaking changes)

Be direct and constructive. No filler.
