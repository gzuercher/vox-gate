---
description: Accessibility rules for UI components
globs: "*.tsx,*.jsx,*.html,*.blade.php"
---

# Accessibility

- Images: always set the `alt` attribute.
- Forms: every input has an associated label.
- Interactive elements: must be keyboard-operable (Tab, Enter, Escape).
- Color contrast: meet WCAG AA (4.5:1 for text, 3:1 for large elements).
- Semantic HTML: use `<button>` instead of `<div onclick>`, plus `<nav>`, `<main>`, `<aside>`.
- ARIA: only when no native HTML element fits.
- Focus management: visible focus ring during keyboard navigation.
