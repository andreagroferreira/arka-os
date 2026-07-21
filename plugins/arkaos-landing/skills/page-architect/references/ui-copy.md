# UI copy — microcopy for interface strings

> Derived from [hallmark](https://github.com/nutlope/hallmark) (MIT) — see `hallmark.LICENSE` in this references directory.

General prose and anti-slop writing rules live in `arka/skills/human-writing` — this file covers UI strings only: buttons, links, labels, errors, empty states, loading states, and the typographic characters inside them.

Words are part of the design. A great layout with stock strings looks generic. Tight microcopy in an average layout reads as considered.

## Principles

- **Specific verbs.** "Save changes" beats "OK" beats "Submit".
- **Labels describe.** "Email address" beats "Email".
- **Link text stands alone.** "View pricing plans" beats "Click here".
- **Errors are instructions.** Describe what broke, why, how to fix — in that order.
- **Active voice.** "We couldn't find your account" beats "Your account could not be found".
- **Consistency.** Pick one of "Delete" or "Remove". Pick one of "Sign in" or "Log in". Use it everywhere.

## Buttons

Use the verb for the action the button performs.

Good: `Save changes`, `Create account`, `Send invitation`, `Copy link`, `Open file`.
Bad: `OK`, `Submit`, `Click here`, `Continue` (only as the secondary button of a multi-step flow).

## Error messages

Three parts:

1. **What happened.** Past tense, factual. "That card was declined."
2. **Why, if known.** "Your bank flagged the charge."
3. **What to do.** Imperative. "Try another card, or contact your bank."

Never apologetic for the *user's* input. Don't say "Oops!" on a validation error. A form that won't accept a value should explain the value, not perform embarrassment.

## Empty states

Three beats:

1. One line naming what's empty. "No projects yet."
2. One line on why this matters / what projects are. "Projects group your tasks and team."
3. One button. The single next action. "Create a project".

## Loading

- Short wait: spinner with no text.
- Medium wait (>2s): spinner + "Loading…".
- Long wait (>10s): spinner + progress indication + an honest label — "Compiling (this can take a minute)."

## Microcopy bans

- "Click here." Link text must stand alone.
- "Oops!", "Uh oh!", "Something went wrong." Name the thing that broke.
- "Enter your email below." If the input is below, you don't need to say so.
- Exclamation marks in error states.
- Humour in frustration paths (forgot-password, payment-failed, account-locked).
- Stock placeholder names: Jane Doe, John Smith, Lorem Ipsum (unless the page is a lorem-ipsum tool).

For banned marketing prose (cliché verbs, empty feature-feeling promises, templated opening lines), defer to `arka/skills/human-writing` — those rules are owned there, not here.

## Honest copy

- **Never invent metrics.** No fabricated user counts, uptime percentages, revenue figures, or "trusted by 10,000 teams" claims the brief didn't supply. If the page design calls for a number the user hasn't given, leave a clearly-marked placeholder and ask.
- **Never invent testimonials.** No fabricated quotes, reviewer names, company logos, star ratings, or press mentions. A testimonial block with invented content is worse than no testimonial block.
- **A placeholder must look like a placeholder**, not like a confident decision. The skill refuses to pass invented specifics off as the final copy.
- If the brief gives you nothing to work with, *say so to the user* and ask one question that elicits a specific noun, verb, or place. The user knows their product; the model is not allowed to invent specificity.

## Proper typography

- Curly quotes: `"Hello"`, `'word'`.
- Em-dash for interruption: `—` (U+2014). En-dash for ranges: `10–20` (U+2013). Never `--`.
- Ellipsis: `…` (U+2026). Never `...`.
- Apostrophe: `’`. Never the prime `'`.
- Non-breaking space before units: `10 kg`, `5 min` (use `&nbsp;` or U+00A0).

If the text is loaded from a CMS, configure Smart Quotes in the CMS. If it's hard-coded, write it correctly.
