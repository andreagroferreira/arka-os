---
name: saas/saas-scaffold
description: >
  Scaffold a production-ready SaaS project with auth, database, billing,
  API routes, and dashboard. Generates file tree, schema, and env config.
  Technical scaffolding — for strategy use saas/mvp-build.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# SaaS Scaffold — `/saas scaffold <stack>`

> **Agent:** Tiago (SaaS Lead) | **Frameworks:** Micro-SaaS Playbook, PLG

## Input

| Field | Options | Default |
|-------|---------|---------|
| Product | name | required |
| Description | 1-3 sentences | required |
| Auth | nextauth, clerk, supabase | nextauth |
| Database | neondb, supabase, planetscale | neondb |
| Payments | stripe, lemonsqueezy, none | stripe |
| Features | comma-separated list | -- |

## File Tree (Next.js + App Router)

```
my-saas/
├── app/
│   ├── (auth)/login/page.tsx, register/page.tsx, layout.tsx
│   ├── (dashboard)/dashboard/page.tsx, settings/page.tsx, billing/page.tsx, layout.tsx
│   ├── (marketing)/page.tsx, pricing/page.tsx, layout.tsx
│   └── api/auth/[...nextauth]/route.ts, webhooks/stripe/route.ts,
│         billing/checkout/route.ts, billing/portal/route.ts
├── components/ui/, auth/, dashboard/, marketing/, billing/
├── lib/auth.ts, db.ts, stripe.ts, validations.ts, utils.ts
├── db/schema.ts, migrations/
├── hooks/use-subscription.ts, use-user.ts
├── types/index.ts
├── middleware.ts
├── .env.example
├── drizzle.config.ts
└── next.config.ts
```

## Scaffold Phases

### Phase 1 — Foundation
- [ ] Next.js initialized (TypeScript + App Router)
- [ ] Tailwind CSS configured with custom theme
- [ ] shadcn/ui installed and configured
- [ ] ESLint + Prettier configured
- [ ] `.env.example` created with all variables
- **Validate:** `npm run build` passes with zero errors

### Phase 2 — Database
- [ ] Drizzle ORM installed and configured
- [ ] Schema: users, accounts, sessions, verification_tokens
- [ ] Initial migration generated and applied
- [ ] DB client singleton in `lib/db.ts`
- **Validate:** `db.select().from(users)` returns empty array

### Phase 3 — Authentication
- [ ] Auth provider installed (NextAuth / Clerk / Supabase)
- [ ] OAuth provider configured (Google / GitHub)
- [ ] Session callback adds user ID + subscription status
- [ ] Middleware protects dashboard routes
- [ ] Login/register pages with error states
- **Validate:** Sign in via OAuth, session has `id` + `subscriptionStatus`

### Phase 4 — Payments
- [ ] Stripe client initialized with TypeScript types
- [ ] Checkout session route created
- [ ] Customer portal route created
- [ ] Webhook handler with signature verification
- [ ] Webhook updates subscription status idempotently
- **Validate:** Test checkout with `4242 4242 4242 4242`, verify DB write

### Phase 5 — UI
- [ ] Landing page: hero, features, pricing sections
- [ ] Dashboard layout: sidebar + responsive header
- [ ] Billing page: current plan + upgrade options
- [ ] Settings page: profile update form
- **Validate:** `npm run build` passes, all routes render correctly

## Environment Variables

`NEXT_PUBLIC_APP_URL`, `DATABASE_URL` (with `?sslmode=require`), `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRO_PRICE_ID`

## Common Pitfalls

| Problem | Fix |
|---------|-----|
| Missing `NEXTAUTH_SECRET` in prod | Set and keep consistent across deploys |
| Webhook signature mismatch | Use `stripe listen --forward-to` locally |
| Edge runtime + Drizzle conflict | Use Node runtime for DB routes |
| Unextended session types | Add `declare module "next-auth"` |
| Dev vs prod migration drift | Use `drizzle-kit push` (dev), `drizzle-kit migrate` (prod) |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No .env.example file → flag team setup friction
- Missing health check endpoint → flag monitoring gap
- No database migration strategy → flag deployment chaos

## Output

```markdown
## SaaS Scaffold — [Product Name]

**Stack:** Next.js + [Auth] + [DB] + [Payments]
**Features:** [list]

### Generated Files
[file tree with descriptions]

### Phase Checklist
[5 phases with validation gates]

### Environment Setup
[.env.example contents]

### Next Steps
1. [immediate action items]
```
