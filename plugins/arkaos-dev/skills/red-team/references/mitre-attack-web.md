# MITRE ATT&CK for Web Applications — Deep Reference

> Tactics, techniques, detection strategies, and tools mapped to web application attack surfaces.

## ATT&CK Tactics Mapped to Web Apps

| # | Tactic | Goal | Web App Relevance |
|---|--------|------|-------------------|
| 1 | **Reconnaissance** (TA0043) | Gather information | Technology fingerprinting, endpoint discovery |
| 2 | **Initial Access** (TA0001) | Gain entry | Exploiting web vulnerabilities, credential abuse |
| 3 | **Execution** (TA0002) | Run attacker code | Server-side injection, client-side scripts |
| 4 | **Persistence** (TA0003) | Maintain access | Backdoor accounts, webshells, modified code |
| 5 | **Privilege Escalation** (TA0004) | Gain higher access | IDOR, broken access control, role manipulation |
| 6 | **Credential Access** (TA0006) | Steal credentials | Session hijacking, credential stuffing, token theft |
| 7 | **Collection** (TA0009) | Gather target data | Data scraping, API abuse, database extraction |
| 8 | **Exfiltration** (TA0010) | Steal data out | API data export, DNS tunneling, file download |

## Tactic 1: Reconnaissance

| Technique | MITRE ID | Method | Detection |
|-----------|----------|--------|-----------|
| Technology fingerprinting | T1592 | HTTP headers, error pages, `/robots.txt`, `sitemap.xml` | Monitor unusual crawling patterns |
| Endpoint enumeration | T1595.002 | Directory brute-force (`/admin`, `/api/v1/users`) | WAF rate limiting, 404 spike alerts |
| JavaScript analysis | T1592.004 | Source map extraction, API endpoint discovery in JS | Remove source maps in production |
| DNS enumeration | T1596.001 | Subdomain brute-force, certificate transparency logs | Monitor CT logs for your domains |
| Social engineering recon | T1598 | Employee LinkedIn, GitHub commits with emails | Security awareness training |

**Detection tools:** WAF logs, Cloudflare analytics, GoAccess, custom 404 rate alerts.

## Tactic 2: Initial Access

| Technique | MITRE ID | Method | Detection |
|-----------|----------|--------|-----------|
| SQL Injection | T1190 | `' OR 1=1--` in input fields, URL params | WAF SQL patterns, parameterized query audit |
| XSS (Stored/Reflected) | T1190 | `<script>` in user input, reflected URL params | CSP violations, output encoding audit |
| SSRF | T1190 | Internal URL in user-controlled params | Allowlist outbound requests, block RFC1918 |
| Authentication bypass | T1078 | Default credentials, JWT none algorithm | Credential audit, JWT validation hardening |
| API abuse | T1190 | Broken object-level authorization (BOLA) | Object-level access control audit |
| File upload exploitation | T1190 | Webshell upload via image field | File type validation (magic bytes), upload isolation |
| Dependency confusion | T1195.002 | Malicious package with internal name | Package namespace reservation, SBOM |

**Detection tools:** ModSecurity/WAF rules, Burp Suite, OWASP ZAP, Semgrep.

## Tactic 3: Execution

| Technique | MITRE ID | Method | Detection |
|-----------|----------|--------|-----------|
| Server-side template injection (SSTI) | T1059 | `{{7*7}}` in template inputs | Input sanitization, sandbox templates |
| OS command injection | T1059 | `; cat /etc/passwd` in shell-invoked params | Avoid `exec()`, use parameterized APIs |
| Deserialization attacks | T1059 | Crafted serialized objects (Java, PHP, Python) | Avoid native deserialization, use JSON |
| Server-side request forgery | T1059 | Trigger server to fetch attacker URLs | URL allowlisting, network segmentation |
| Webshell execution | T1059.004 | PHP/JSP shell uploaded or injected | File integrity monitoring, webshell scanners |

**Detection tools:** RASP (Runtime Application Self-Protection), file integrity monitoring, syscall auditing.

## Tactic 4: Persistence

| Technique | MITRE ID | Method | Detection |
|-----------|----------|--------|-----------|
| Backdoor admin account | T1136.001 | Create hidden admin via SQL injection or API | User account audit, alert on admin creation |
| Webshell deployment | T1505.003 | Upload PHP/JSP file to web root | File integrity monitoring (AIDE, Tripwire) |
| Scheduled task/cron | T1053 | Add cron job via command injection | Cron audit, immutable infrastructure |
| Modified application code | T1554 | Inject backdoor into deployed code | Git integrity checks, signed deployments |
| OAuth app installation | T1098.003 | Register malicious OAuth app with broad scopes | OAuth app audit, scope restriction policies |
| Cookie/session manipulation | T1556 | Forge long-lived session tokens | Short session TTL, token rotation |

**Detection tools:** Git diff monitoring, AIDE/Tripwire, deploy artifact checksums.

## Tactic 5: Privilege Escalation

| Technique | MITRE ID | Method | Detection |
|-----------|----------|--------|-----------|
| IDOR | T1548 | Change `user_id=123` to `user_id=456` in API | Object-level authorization on every endpoint |
| Role parameter tampering | T1548 | `{"role": "admin"}` in registration payload | Server-side role assignment, ignore client role |
| JWT manipulation | T1548 | Algorithm confusion (`none`, `HS256` vs `RS256`) | Strict algorithm validation, key management |
| Path traversal | T1548 | `../../etc/passwd` in file parameters | Canonicalize paths, chroot file access |
| GraphQL introspection abuse | T1548 | Discover admin mutations via schema introspection | Disable introspection in production |

**Detection tools:** Authorization test suites, Burp Autorize plugin, custom IDOR scanners.

## Tactic 6: Credential Access

| Technique | MITRE ID | Method | Detection |
|-----------|----------|--------|-----------|
| Credential stuffing | T1110.004 | Automated login with breached credential lists | Rate limiting, CAPTCHA, breach detection |
| Session hijacking | T1539 | XSS to steal `document.cookie` | HttpOnly + Secure flags, CSP |
| Token theft from storage | T1552 | Access localStorage/sessionStorage via XSS | Use httpOnly cookies, not localStorage |
| Password spraying | T1110.003 | Common passwords across many accounts | Account lockout, anomaly detection |
| OAuth token theft | T1528 | Phishing redirect to attacker OAuth callback | Strict redirect URI validation |
| API key extraction | T1552.001 | Keys in client-side JavaScript, git history | Server-side key management, git-secrets |

**Detection tools:** Have I Been Pwned API, fail2ban, rate limiter middleware, git-secrets.

## Detection Strategy Matrix

| Layer | What to Monitor | Tools | Alert Threshold |
|-------|----------------|-------|-----------------|
| **Edge/CDN** | Request rate, geo anomalies, bot score | Cloudflare, AWS WAF | Rate > 100 req/s per IP |
| **WAF** | SQL/XSS patterns, protocol violations | ModSecurity, AWS WAF | Any rule match on critical endpoints |
| **Application** | Auth failures, IDOR attempts, input validation | Custom logging, RASP | > 5 auth failures per account/min |
| **API Gateway** | Rate limits, schema violations, unusual patterns | Kong, AWS API GW | Schema violation on sensitive endpoints |
| **Database** | Unusual queries, bulk data access, schema changes | Query logging, DBA alerts | > 1000 rows returned in single query |
| **Infrastructure** | Outbound connections, file changes, new processes | OSSEC, Falco | Any unexpected outbound connection |

## Attack Path Examples

### Path 1: Data Exfiltration via IDOR

```
Recon (endpoint enumeration)
  --> Initial Access (BOLA on GET /api/users/{id})
    --> Collection (iterate all user IDs)
      --> Exfiltration (bulk download via API)
```

Choke point: Object-level authorization on API endpoints.

### Path 2: Webshell via File Upload

```
Recon (identify upload functionality)
  --> Initial Access (upload PHP file as image)
    --> Execution (access webshell URL)
      --> Persistence (webshell remains on disk)
        --> Privilege Escalation (server runs as www-data, pivot to root)
```

Choke point: File upload validation (magic bytes, extension, isolated storage).

### Path 3: Account Takeover via XSS

```
Recon (find reflected XSS in search)
  --> Initial Access (craft XSS payload URL)
    --> Credential Access (steal session cookie)
      --> Privilege Escalation (target is admin user)
        --> Collection (access admin dashboard data)
```

Choke point: Content Security Policy + HttpOnly cookies.

## Tools by Phase

| Phase | Offensive Tool | Defensive Tool |
|-------|---------------|----------------|
| Reconnaissance | Amass, subfinder, httpx | Cloudflare, GoAccess |
| Initial Access | Burp Suite, SQLMap, OWASP ZAP | ModSecurity, Semgrep |
| Execution | Commix, tplmap | RASP, Falco |
| Persistence | Weevely, webshell generators | AIDE, Tripwire, OSSEC |
| Privilege Escalation | Autorize (Burp), custom scripts | Authorization test suites |
| Credential Access | Hydra, Patator | fail2ban, rate limiters |
| Exfiltration | Custom scripts, DNS tunneling | DLP, egress filtering |

## Quick Reference: Top 10 Web App Detections to Implement

1. Rate limit authentication endpoints (5 failures / minute / account)
2. CSP header with report-uri (detect XSS attempts)
3. WAF with OWASP Core Rule Set (broad coverage)
4. File integrity monitoring on web root (detect webshells)
5. Alert on admin account creation (detect backdoor accounts)
6. Log and alert on authorization failures (detect IDOR)
7. Monitor outbound connections from web servers (detect SSRF/exfil)
8. Alert on bulk data access patterns (detect scraping/exfil)
9. JWT validation with strict algorithm enforcement (detect token manipulation)
10. Dependency vulnerability scanning in CI/CD (detect supply chain attacks)
