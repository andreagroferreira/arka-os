---
name: brand/design-system
description: >
  Ships a production design system in 5 deliverables: design-tokens.json
  (primitive + semantic layers), an Atomic Design component catalog (atoms to
  pages), WCAG 2.2 AA conformance report, Storybook CSF3 story stubs, and an
  integration guide. TRIGGER: "design system", "cria o design system", "design
  tokens", "component library", "biblioteca de componentes", "/brand
  design-system". SKIP: only a color palette -> brand/colors; implementing the
  components in application code -> dev frontend workflows (this skill
  specifies the system, it does not build the app); reviewing an existing UI
  against brand guidelines -> brand/design-review.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Design System — `/brand design-system`

> **Lead:** Sofia D. (UX Designer) + Isabel (Visual Designer) | **Framework:** Atomic Design (Brad Frost) + Design Tokens + WCAG 2.2 AA

## What ships

A production design system in 5 deliverables:

1. **`design-tokens.json`** — semantic token layer
2. **Component catalog** — atoms → molecules → organisms → templates → pages
3. **WCAG 2.2 AA conformance report** — pass / waiver per component
4. **Storybook story stubs** — one story per component, ready to drop into Storybook
5. **Integration guide** — how to wire the system into a Vue/React/Vanilla project

## Token JSON schema

The token system has a **two-layer architecture**: raw primitives + semantic aliases. Semantic tokens reference primitives; surfaces reference semantic tokens. Never reference primitives directly in components.

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/",
  "primitive": {
    "color": {
      "neutral": {
        "0":   { "$value": "#FFFFFF",  "$type": "color" },
        "50":  { "$value": "#FAFAFA",  "$type": "color" },
        "100": { "$value": "#F4F4F5",  "$type": "color" },
        "900": { "$value": "#18181B",  "$type": "color" },
        "1000":{ "$value": "#0A0A0A",  "$type": "color" }
      },
      "accent": {
        "500": { "$value": "#00FF88",  "$type": "color" }
      }
    },
    "size": {
      "0": { "$value": "0",    "$type": "dimension" },
      "1": { "$value": "4px",  "$type": "dimension" },
      "2": { "$value": "8px",  "$type": "dimension" },
      "4": { "$value": "16px", "$type": "dimension" }
    }
  },
  "semantic": {
    "color": {
      "background": { "$value": "{primitive.color.neutral.1000}", "$type": "color" },
      "surface":    { "$value": "{primitive.color.neutral.900}",  "$type": "color" },
      "text":       { "$value": "{primitive.color.neutral.50}",   "$type": "color" },
      "accent":     { "$value": "{primitive.color.accent.500}",   "$type": "color" }
    },
    "space": {
      "compact":  { "$value": "{primitive.size.2}",  "$type": "dimension" },
      "default":  { "$value": "{primitive.size.4}",  "$type": "dimension" },
      "generous": { "$value": "{primitive.size.6}",  "$type": "dimension" }
    },
    "radius": { "$value": "{primitive.size.2}", "$type": "dimension" },
    "motion": {
      "duration": {
        "fast":   { "$value": "150ms",  "$type": "duration" },
        "base":   { "$value": "250ms",  "$type": "duration" },
        "slow":   { "$value": "400ms",  "$type": "duration" }
      },
      "easing": {
        "standard": { "$value": "cubic-bezier(0.4, 0, 0.2, 1)", "$type": "cubicBezier" }
      }
    }
  }
}
```

Required token groups: `color`, `space`, `typography`, `radius`, `elevation`, `motion`, `border`. Each group must have at minimum 3 semantic tokens. Primitives are reusable; semantics are intentional.

## Atomic Design 5-Level Component Manifest

Each component is documented with: name, level, props, slots, accessibility notes, Storybook story stub.

### Level 1 — Atoms (10-15 required)
Indivisible UI primitives. Examples:

| Component | Props | A11y notes |
|---|---|---|
| Button | `variant` (primary/secondary/ghost), `size`, `disabled`, `loading` | role=button, aria-busy on loading, keyboard-actionable |
| Input | `type`, `value`, `placeholder`, `disabled`, `invalid` | aria-invalid on invalid, aria-describedby for error |
| Label | `htmlFor`, `required` | explicit for association required |
| Icon | `name`, `size`, `decorative` | role=img + aria-label OR aria-hidden when decorative |
| Avatar | `src`, `alt`, `fallback`, `size` | alt required unless decorative |
| Badge | `variant`, `count` | aria-live polite when count changes |
| Spinner | `size`, `label` | role=status + aria-label |
| Switch | `checked`, `disabled` | role=switch + aria-checked |
| Checkbox | `checked`, `indeterminate`, `disabled` | aria-checked tri-state support |
| Link | `href`, `external`, `variant` | rel=noopener for external |

### Level 2 — Molecules (8-12 required)
Composed pairs of atoms with one task focus. Examples:

| Component | Composes | A11y notes |
|---|---|---|
| FormField | Label + Input + ErrorMessage | aria-describedby chain |
| SearchBar | Input + Button + Icon | role=search, aria-label on form |
| Card | Heading + Body + optional Footer | semantic landmark when standalone |
| NavItem | Icon + Label + (Badge) | aria-current when active |
| Tab | Label + (Icon) + (Badge) | role=tab, aria-selected |
| Toast | Icon + Body + DismissButton | role=status or alert, dismissible |
| Tooltip | Anchor + Content | aria-describedby on anchor |
| Breadcrumb | Link[] + separator | nav landmark, aria-current on last |

### Level 3 — Organisms (6-10 required)
Complete sections of UI. Examples:

| Component | Composes | A11y notes |
|---|---|---|
| NavBar | Logo + NavItem[] + Avatar | nav landmark, skip-link target |
| HeroSection | Heading + Body + CTA + (Media) | one h1 per page rule |
| CardGrid | Card[] with layout | role=list when semantic, gap-aware |
| Dialog | Header + Body + Footer + FocusTrap | role=dialog, aria-labelledby, focus trap |
| DataTable | Header + Row[] with sort/filter | proper th scope, aria-sort |
| Sidebar | NavItem[] + collapse | nav landmark, persisted state |
| EmptyState | Icon + Heading + Body + (CTA) | role=region |

### Level 4 — Templates (3-5 required)
Page-level layouts with content slots. Examples: DashboardTemplate, ContentTemplate, MarketingTemplate, AuthTemplate, SettingsTemplate.

### Level 5 — Pages (2-3 required, production examples)
Production-ready pages with real content. Examples: LandingPage, DashboardHome, SettingsAccount.

## WCAG 2.2 AA Gates

Every component must pass:

| Criterion | Check | Tool |
|---|---|---|
| 1.4.3 Contrast (Minimum) | Body text ≥ 4.5:1 against background; large text ≥ 3:1 | manual + axe |
| 1.4.11 Non-text Contrast | UI components and graphical objects ≥ 3:1 against adjacent colors | manual + axe |
| 2.1.1 Keyboard | All functionality available via keyboard | manual |
| 2.4.7 Focus Visible | Visible focus indicator on all interactive elements | manual |
| 2.5.8 Target Size (Minimum) | Pointer targets ≥ 24×24 CSS pixels | manual |
| 4.1.2 Name, Role, Value | All UI components expose accessible name and role to AT | axe + screen reader |
| 4.1.3 Status Messages | Status updates announced without focus change | screen reader |

Components failing any criterion either remediate or document a **permanent waiver** with concrete user-impact rationale. Waivers require Quality Gate approval.

## Storybook Export Contract

Each component must ship one `.stories.{ts,mdx}` file with:

- **Default** story — props at defaults, single state visible
- **AllVariants** story — every variant prop combination
- **Interactive** story — controls (Storybook args) exposed for every prop
- **A11y** story — screen-reader narration sample + keyboard nav sequence

Story stubs use the CSF3 format:

```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  component: Button,
  parameters: { a11y: { test: 'error' } },
  argTypes: {
    variant: { control: 'select', options: ['primary', 'secondary', 'ghost'] },
    size: { control: 'select', options: ['sm', 'md', 'lg'] },
    disabled: { control: 'boolean' },
  },
};
export default meta;

type Story = StoryObj<typeof Button>;
export const Default: Story = { args: { variant: 'primary', size: 'md' } };
export const AllVariants: Story = { /* render all variants in a grid */ };
```

## Integration Guide (delivery artifact)

A standalone markdown explaining:
- How to install token files (CSS variables / JSON / Tailwind config)
- How to import components in Vue / React / Vanilla
- How to extend the system (adding tokens, adding components, namespacing)
- How to run the WCAG audit locally (`npx axe-core --tags wcag2aa`)
- How to update Storybook stories when components change

## Output → Obsidian: `WizardingCode/Brand/DesignSystems/<project>-<date>/`

Delivers: `design-tokens.json` + component catalog (markdown with screenshots / mermaid hierarchy) + WCAG report + Storybook stubs + integration guide.
