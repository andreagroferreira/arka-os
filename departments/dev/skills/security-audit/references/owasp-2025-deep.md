# OWASP Top 10 (2025) — Deep Reference

> Each vulnerability with code examples, testing methodology, automated tools, and impact.

## A01: Broken Access Control

**Impact:** Unauthorized data access, privilege escalation, account takeover.

### Vulnerable Code (Laravel)

```php
// DANGEROUS: No authorization check
public function show($id)
{
    return User::findOrFail($id); // Any user can access any profile
}
```

### Fixed Code

```php
public function show($id)
{
    $user = User::findOrFail($id);
    $this->authorize('view', $user); // Policy-based authorization
    return new UserResource($user);
}
```

### Testing Methodology

- [ ] Test every endpoint with unauthenticated request
- [ ] Test with low-privilege user accessing high-privilege resources
- [ ] Modify object IDs in requests (IDOR testing)
- [ ] Test HTTP method override (GET vs POST vs PUT)
- [ ] Verify deny-by-default on new endpoints

**Tools:** Burp Autorize, OWASP ZAP Access Control plugin, custom auth matrix tests.

---

## A02: Cryptographic Failures

**Impact:** Data exposure, credential theft, compliance violations.

### Vulnerable Code

```python
# DANGEROUS: Weak hashing, no salt
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()

# DANGEROUS: Hardcoded encryption key
key = "mysecretkey12345"
```

### Fixed Code

```python
# SAFE: bcrypt with automatic salting
from passlib.hash import bcrypt
password_hash = bcrypt.hash(password)

# SAFE: Key from environment, proper algorithm
from cryptography.fernet import Fernet
key = os.environ['ENCRYPTION_KEY']  # Generated with Fernet.generate_key()
cipher = Fernet(key)
```

### Checklist

- [ ] TLS 1.2+ on all connections (no fallback to TLS 1.0/1.1)
- [ ] Passwords hashed with bcrypt/argon2 (never MD5/SHA1)
- [ ] Sensitive data encrypted at rest (AES-256-GCM)
- [ ] No secrets in source code or environment variables in containers
- [ ] Certificate pinning for mobile apps

**Tools:** testssl.sh, SSLyze, git-secrets, TruffleHog.

---

## A03: Supply Chain Failures

**Impact:** Malicious code execution, data exfiltration via dependencies.

### Vulnerable Setup

```json
// DANGEROUS: No lockfile, no integrity checks
{
  "dependencies": {
    "lodash": "^4.0.0",
    "my-internal-lib": "*"
  }
}
```

### Fixed Setup

```json
// SAFE: Pinned versions, lockfile committed
{
  "dependencies": {
    "lodash": "4.17.21"
  }
}
// Plus: npm ci (not npm install), package-lock.json committed
// Plus: .npmrc with registry scope for internal packages
```

### Checklist

- [ ] Lockfiles committed and used in CI (`npm ci`, `composer install --no-dev`)
- [ ] Automated dependency scanning in CI pipeline
- [ ] SBOM (Software Bill of Materials) generated per release
- [ ] Internal package namespace reserved on public registries
- [ ] Signed commits and artifacts in CI/CD

**Tools:** npm audit, Snyk, Dependabot, Socket.dev, Renovate.

---

## A04: Injection

**Impact:** Data theft, data manipulation, complete system compromise.

### Vulnerable Code (SQL)

```php
// DANGEROUS: String concatenation in query
$users = DB::select("SELECT * FROM users WHERE email = '" . $request->email . "'");
```

### Fixed Code

```php
// SAFE: Parameterized query via Eloquent
$users = User::where('email', $request->input('email'))->get();

// SAFE: Parameterized raw query when needed
$users = DB::select("SELECT * FROM users WHERE email = ?", [$request->input('email')]);
```

### Vulnerable Code (NoSQL)

```javascript
// DANGEROUS: MongoDB operator injection
db.users.find({ username: req.body.username, password: req.body.password });
// Attacker sends: { "password": { "$gt": "" } }
```

### Fixed Code

```javascript
// SAFE: Type-check and sanitize
const username = String(req.body.username);
const password = String(req.body.password);
db.users.find({ username, password: hashPassword(password) });
```

### Testing

- [ ] Test all inputs with SQL meta-characters (`'`, `"`, `;`, `--`)
- [ ] Test NoSQL operators in JSON inputs (`$gt`, `$ne`, `$regex`)
- [ ] Test OS command injection (`;`, `|`, `` ` ``)
- [ ] Test LDAP injection, XPath injection if applicable

**Tools:** SQLMap, Commix, Semgrep (SAST), OWASP ZAP (DAST).

---

## A05: Security Misconfiguration

**Impact:** Information disclosure, unauthorized access, full compromise.

### Common Misconfigurations

| Misconfiguration | Risk | Fix |
|-----------------|------|-----|
| Debug mode in production | Stack traces expose internals | `APP_DEBUG=false`, custom error pages |
| Default credentials | Instant admin access | Force password change on first login |
| Directory listing enabled | Source code/config exposure | Disable in web server config |
| Unnecessary HTTP methods | PUT/DELETE on static content | Restrict methods per endpoint |
| Missing security headers | XSS, clickjacking, sniffing | Add all 6 security headers |
| Cloud storage public by default | Data breach | Private by default, explicit public |

### Security Headers (Complete Set)

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
```

**Tools:** SecurityHeaders.com, Mozilla Observatory, Nikto, ScoutSuite (cloud).

---

## A06: Vulnerable and Outdated Components

**Impact:** Known exploits applied automatically, zero-effort compromise.

### Automated Scanning Commands

```bash
# JavaScript
npm audit --production
npx audit-ci --high

# PHP
composer audit

# Python
pip-audit
safety check

# Ruby
bundle audit check --update

# General
trivy fs . --severity HIGH,CRITICAL
```

### Policy

| Severity | Action | Timeline |
|----------|--------|----------|
| Critical (CVSS 9.0+) | Patch immediately | 24 hours |
| High (CVSS 7.0-8.9) | Patch urgently | 7 days |
| Medium (CVSS 4.0-6.9) | Patch in next sprint | 30 days |
| Low (CVSS 0.1-3.9) | Backlog | 90 days |

**Tools:** Dependabot, Renovate, Snyk, Trivy, OWASP Dependency-Check.

---

## A07: Authentication Failures

**Impact:** Account takeover, identity theft, unauthorized access.

### Vulnerable Code

```php
// DANGEROUS: No rate limiting, no MFA, weak session
Route::post('/login', function (Request $request) {
    if (Auth::attempt($request->only('email', 'password'))) {
        return response()->json(['token' => Str::random(40)]);
    }
});
```

### Fixed Code

```php
// SAFE: Rate limited, proper session management
Route::post('/login', function (LoginRequest $request) {
    RateLimiter::hit('login:' . $request->ip(), 5); // 5 attempts per minute

    if (Auth::attempt($request->validated())) {
        $request->session()->regenerate(); // Prevent session fixation
        if ($request->user()->mfa_enabled) {
            return response()->json(['requires_mfa' => true]);
        }
        return response()->json(['token' => $request->user()->createToken('api')->plainTextToken]);
    }

    throw ValidationException::withMessages(['email' => 'Invalid credentials.']);
})->middleware('throttle:5,1');
```

### Checklist

- [ ] Rate limiting on login (5 attempts/min), registration, password reset
- [ ] MFA available and enforced for admin accounts
- [ ] Session regeneration after login
- [ ] Secure cookie flags (HttpOnly, Secure, SameSite=Lax)
- [ ] Password policy (12+ chars, breach check via HIBP API)
- [ ] Account lockout after repeated failures (with notification)

**Tools:** Hydra, Burp Intruder, custom auth test suite.

---

## A08: Data Integrity Failures

**Impact:** Code execution via deserialization, CI/CD pipeline compromise, tampered updates.

### Vulnerable Code

```php
// DANGEROUS: Unvalidated deserialization
$data = unserialize($request->input('data'));

// DANGEROUS: Unsigned CI/CD pipeline
// .github/workflows/deploy.yml with no artifact verification
```

### Fixed Code

```php
// SAFE: Use JSON instead of native serialization
$data = json_decode($request->input('data'), true, 512, JSON_THROW_ON_ERROR);

// SAFE: Validate schema
$validated = Validator::make($data, [
    'name' => 'required|string|max:255',
    'quantity' => 'required|integer|min:1',
])->validated();
```

### Checklist

- [ ] Never use native deserialization on user input (PHP `unserialize`, Java `ObjectInputStream`)
- [ ] Signed artifacts in CI/CD pipeline
- [ ] Integrity verification for third-party data (checksums, signatures)
- [ ] Immutable infrastructure (no runtime modifications)

**Tools:** Semgrep (detect unsafe deserialization), Sigstore/cosign, CI/CD audit.

---

## A09: Logging and Monitoring Failures

**Impact:** Attacks go undetected, no forensic evidence, compliance failures.

### What to Log (Minimum)

| Event | Priority | Fields |
|-------|----------|--------|
| Authentication success/failure | High | user_id, IP, timestamp, user_agent |
| Authorization failures | High | user_id, resource, action, IP |
| Input validation failures | Medium | endpoint, input_field, violation_type |
| Payment transactions | High | amount, user_id, status, transaction_id |
| Admin actions | High | admin_id, action, target, before/after |
| Rate limit hits | Medium | IP, endpoint, limit_type |

### What NOT to Log

- Passwords (even hashed)
- Full credit card numbers (log last 4 only)
- Session tokens or API keys
- PII beyond what is needed for investigation

**Tools:** ELK Stack, Loki+Grafana, Datadog, Sentry (errors).

---

## A10: Exceptional Conditions (Server-Side Request Forgery)

**Impact:** Internal network scanning, cloud metadata theft, service abuse.

### Vulnerable Code

```python
# DANGEROUS: User-controlled URL fetched server-side
import requests
url = request.args.get('url')
response = requests.get(url)  # Attacker can reach internal services
```

### Fixed Code

```python
# SAFE: URL allowlist + block internal ranges
from urllib.parse import urlparse
import ipaddress

ALLOWED_HOSTS = {'api.example.com', 'cdn.example.com'}

def safe_fetch(url):
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Host not in allowlist")
    # Resolve DNS and verify IP is not internal
    ip = socket.gethostbyname(parsed.hostname)
    if ipaddress.ip_address(ip).is_private:
        raise ValueError("Internal IP not allowed")
    return requests.get(url, timeout=5, allow_redirects=False)
```

### Checklist

- [ ] URL allowlist for server-side requests
- [ ] Block RFC1918 and link-local addresses
- [ ] Disable HTTP redirects in server-side requests
- [ ] Network segmentation (web servers cannot reach metadata endpoints)
- [ ] Cloud metadata endpoint blocked (169.254.169.254)

**Tools:** SSRFmap, Burp Collaborator, custom SSRF test payloads.

---

## Vulnerability Severity Quick Reference

| Vulnerability | Typical CVSS | Business Impact |
|--------------|-------------|-----------------|
| A01 Broken Access Control | 7.5-9.8 | Data breach, regulatory fines |
| A02 Cryptographic Failures | 7.0-9.1 | Data exposure, compliance failure |
| A03 Supply Chain | 8.0-10.0 | Full system compromise |
| A04 Injection | 8.6-10.0 | Data theft, system takeover |
| A05 Misconfiguration | 5.0-8.0 | Information disclosure, unauthorized access |
| A06 Vulnerable Components | Varies (known CVE) | Depends on component |
| A07 Auth Failures | 7.0-9.8 | Account takeover, identity theft |
| A08 Data Integrity | 6.0-9.8 | Code execution, pipeline compromise |
| A09 Logging Failures | 4.0-6.0 | Undetected attacks, no forensics |
| A10 SSRF | 7.0-9.8 | Internal network access, cloud compromise |
