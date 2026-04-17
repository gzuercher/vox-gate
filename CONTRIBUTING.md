# Contributing

## Getting started

1. Clone the repo
2. Run `claude` in the project directory
3. `/help` shows available commands

## Available commands

- `/commit-push-pr` — Automate git workflow
- `/review` — Code review of current branch
- `/build-and-test` — Run build and tests

## When Claude makes a mistake

1. **Correct immediately.** Don't let it slide.
2. **Document the lesson:** Tell Claude: "Document this lesson in lessons.md"
3. **Note in PR:** If it's a recurring issue, update CLAUDE.md or a rule

## Extending rules

1. Create a `.md` file in `.claude/rules/`
2. Set `globs` in frontmatter to relevant file types
3. Keep the rule short and specific
4. Create a PR

## Personal settings

For personal overrides: `.claude/settings.local.json` (git-ignored).
