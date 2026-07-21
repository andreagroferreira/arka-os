# T1 · Pull-quote with marginalia

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT — see `hallmark.LICENSE` in this references directory). Sanitized and adapted for ArkaOS.

A quote sits in the wide column; the attribution and source link float in the narrow margin column.
*Use when:* the page already has a marginalia rhythm (Tufte-leaning, editorial).
*Don't confuse with:* T3 Single huge quote (which is centered and dominates).

```html
<aside class="proof-margin">
  <blockquote class="serif-italic">"…"</blockquote>
  <p class="attribution muted">— Name<br />Role, Company</p>
</aside>
```
