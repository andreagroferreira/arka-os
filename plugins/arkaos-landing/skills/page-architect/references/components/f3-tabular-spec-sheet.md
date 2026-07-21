# F3 · Tabular spec sheet

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT — see `hallmark.LICENSE` in this references directory). Sanitized and adapted for ArkaOS.
Each row is a feature; columns hold name, value, footnote. Hairline rules between rows. Tabular numerics.
*Use when:* features compare quantitatively.
*Don't confuse with:* F1 Bento (which is non-tabular and visually rhythmic).

```html
<table class="spec-sheet tnum">
  <tr><th>Latency</th><td>p99 &lt; 50 ms</td><td class="muted">measured externally</td></tr>
  <tr>…</tr>
</table>
```
