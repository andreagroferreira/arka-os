---
name: dev/laravel-review
description: >
  Laravel/PHP review against ArkaOS conventions — mass assignment, N+1
  queries, Blade XSS, business logic leaking into controllers, missing
  FormRequests, and strict-types gaps — with the fix each one needs.
  TRIGGER: "/dev laravel-review", "review this Laravel", "review the PHP",
  "revê este controller", "revê o Eloquent", "isto está seguro em
  Laravel?", any diff touching *.php, Blade, or Eloquent models. SKIP:
  language-agnostic pre-merge review -> dev/code-review wins; database
  schema/migration design -> dev/db-design wins; a security audit of the
  whole app -> dev/security-audit wins.
allowed-tools: [Read, Grep, Glob, Bash]
metadata:
  origin: arkaos
---

# Laravel Review — `/dev laravel-review`

> **Agent:** Gonçalo (Laravel Specialist) | **Framework:** Laravel conventions, OWASP, ArkaOS Services+Repositories standard

Laravel makes the wrong thing easy: `create($request->all())` is one line
and a mass-assignment hole, an Eloquent relation in a Blade loop is one
property access and an N+1, `{!! $x !!}` is shorter than the escaped form
and an XSS. This review reads a PHP diff for the specific ways the
framework's convenience turns into a defect, and holds it to the ArkaOS
Laravel standard — Services and Repositories, FormRequests everywhere,
`declare(strict_types=1)`, not just to PSR-12.

## Review Priorities

### Critical — Security
- **Mass assignment**: `create($request->all())` or `$guarded = []` → whitelist `$fillable`, or pass `$request->validated()` from a FormRequest.
- **SQL injection**: `DB::raw()`/`whereRaw()`/string-interpolated queries with user input → parameterised bindings or Eloquent.
- **Blade XSS**: `{!! $userInput !!}` without HTMLPurifier → `{{ }}`, or purify explicitly.
- **Command/path**: `exec`/`shell_exec`/`system` or `Storage` paths from user input → validate and sanitise.
- **Unvalidated uploads**: no MIME/size/extension check on file inputs.
- **Weak crypto / secrets**: MD5 for passwords, hardcoded keys.

### Critical — Error handling
- **Swallowed exceptions**: `catch (\Throwable $e) {}` with no log and no re-throw.
- **Missing validation**: a controller action with no FormRequest and no inline rules.

### High — ArkaOS Laravel standard
- **Business logic in controllers** → extract to a Service or Action; the controller orchestrates, it does not decide.
- **Data access outside a Repository** where the ecosystem uses them.
- **No FormRequest** on a write endpoint → `$request->validated()`, never `$request->all()`.
- **Missing `declare(strict_types=1)`** in non-view PHP; untyped public method params/returns.
- **N+1**: an Eloquent relation accessed in a loop or serialisation with no `with()`/`$with`.
- **Missing `$fillable`/`$casts`** on models; **missing Feature test** (`RefreshDatabase`) on the changed behaviour.

## Process

1. `git diff -- '*.php' '*.blade.php'` to scope the change.
2. Run PHPStan/Pint if configured — read their output, do not just report their absence.
3. Read each changed controller/model/service against the priorities, heaviest first.

## Proactive Triggers

Surface these WITHOUT being asked:

- `$request->all()` reaching a `create`/`update`/`fill` → the mass-assignment hole; name the fields it exposes
- a relation accessed inside `@foreach` or an API Resource with no eager load → the N+1 and the `with()` that fixes it
- a controller method over ~15 lines carrying query + business logic → the Service/Action to extract

## Output

```markdown
## Laravel Review

**Scope:** {changed PHP / Blade}
**Verdict:** {APPROVED / CHANGES REQUESTED}

### Critical
- [ ] {file}:{line} — {the hole} → {the fix}

### High (ArkaOS standard)
- [ ] {file}:{line} — {the convention broken} → {the fix}

### Positive
{what follows the standard well}
```
