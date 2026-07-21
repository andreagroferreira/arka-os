# S1 · Left-margin numbered

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT — see `hallmark.LICENSE` in this references directory). Sanitized and adapted for ArkaOS.
A narrow left column holds `01 — LABEL.`; the wide right column holds the heading and content.
*Use when:* the page is editorial / specimen.
*Don't confuse with:* S5 Bottom-anchored (which puts the label *under* the section).

```html
<header class="head-margin">
  <p class="num-label">01 — Foundations</p>
  <h2>…</h2>
</header>
```
```css
.head-margin { display: grid; grid-template-columns: 10rem 1fr; gap: var(--space-xl); align-items: baseline; }
```
