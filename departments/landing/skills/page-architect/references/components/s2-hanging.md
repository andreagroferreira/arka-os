# S2 · Hanging

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT — see `hallmark.LICENSE` in this references directory). Sanitized and adapted for ArkaOS.

Heading floats above the section in negative space; no border, no rule.
*Use when:* the content has a quiet, room-to-breathe energy.
*Don't confuse with:* S3 Sticky-pinned (which moves with scroll).

```html
<header class="head-hang">
  <h2>…</h2>
</header>
```
```css
.head-hang { padding-block: var(--space-3xl) var(--space-xl); }
```
