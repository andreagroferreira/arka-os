# F2 · Sticky-scroll stack

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT — see `hallmark.LICENSE` in this references directory). Sanitized and adapted for ArkaOS.
Sticky left pane, scrolling right pane that cycles through related screenshots.
*Use when:* feature has multiple sub-states worth showing in sequence.
*Don't confuse with:* F4 Step sequence (which is linearly numbered, not synced).

```html
<section class="sticky-stack">
  <div class="pane-sticky"><h3>…</h3><p>…</p></div>
  <div class="pane-scroll">
    <figure>1</figure><figure>2</figure><figure>3</figure>
  </div>
</section>
```
```css
.sticky-stack { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2xl); }
/* `calc(--banner-height + --space-xl)` so the sticky pane docks below the
   nav with breathing room. Falls back to --space-xl alone when no sticky
   nav is on the page (slop-test gate 56). */
.pane-sticky { position: sticky; top: calc(var(--banner-height, 0px) + var(--space-xl)); align-self: start; z-index: var(--z-sticky); }
```
