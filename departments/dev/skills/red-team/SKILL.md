---
name: dev/red-team
description: >
  Offensive security engagement planning: MITRE ATT&CK kill-chain, technique scoring, attack path analysis, OPSEC assessment.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Red Team Engagement — `/dev red-team`

> **Agent:** Bruno (Security Engineer) | **Framework:** MITRE ATT&CK, Cyber Kill Chain

**All red team activities require written authorization (signed Rules of Engagement).**

## What It Does

Plans structured adversary simulations using MITRE ATT&CK techniques. Scores attack paths, identifies choke points, assesses OPSEC risks, and targets crown jewel assets.

## Kill-Chain Phases

| Phase | Order | MITRE Tactic | Examples |
|-------|-------|-------------|----------|
| Reconnaissance | 1 | TA0043 | T1595, T1596, T1598 |
| Initial Access | 2 | TA0001 | T1190, T1566, T1078 |
| Execution | 3 | TA0002 | T1059, T1047, T1204 |
| Persistence | 4 | TA0003 | T1053, T1543, T1136 |
| Privilege Escalation | 5 | TA0004 | T1055, T1548, T1134 |
| Credential Access | 6 | TA0006 | T1003, T1110, T1558 |
| Lateral Movement | 7 | TA0008 | T1021, T1550, T1534 |
| Exfiltration / Impact | 8 | TA0010/TA0040 | T1048, T1486, T1491 |

## Access Levels

| Level | Starting Position | Scope |
|-------|------------------|-------|
| External | No internal access, internet only | Phishing, public exploits |
| Internal | Network foothold, no credentials | Internal recon, lateral prep |
| Credentialed | Valid credentials (assumed breach) | Full kill chain |

## Technique Scoring

```
effort_score = detection_risk x (prerequisites + 1)
```

| Technique | Detection Risk | Prerequisites | Effort | MITRE ID |
|-----------|---------------|---------------|--------|----------|
| Spearphishing link | 0.4 | none | 0.4 | T1566.001 |
| Scheduled task | 0.5 | execution | 1.0 | T1053.005 |
| PowerShell exec | 0.7 | initial_access | 1.4 | T1059.001 |
| LSASS dump | 0.8 | local_admin | 1.6 | T1003.001 |
| Pass-the-Hash | 0.6 | cred_access + network | 1.8 | T1550.002 |
| Ransomware deploy | 0.9 | persist + lateral | 2.7 | T1486 |

## OPSEC Checklist (Before Each Phase)

- [ ] Technique is in scope per Rules of Engagement
- [ ] Known detection signatures identified for this technique
- [ ] Less-detectable alternative evaluated
- [ ] Cleanup artifacts defined for post-exercise removal
- [ ] If detected, does it reveal the full operation or only current foothold

## Crown Jewel Targeting

| Crown Jewel | Attack Path | Detection Priority |
|-------------|------------|-------------------|
| Domain Controller | Kerberoasting, DCSync, Golden Ticket | Highest |
| Database servers | Lateral movement, DBA account, data staging | High |
| Payment systems | Network pivot, service account, exfiltration | Highest |
| Source code repos | VPN, internal git, code signing keys | High |
| Cloud management | Phishing, credential, AssumeRole chain | Highest |

## Anti-Patterns

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| No written authorization | Criminal offense under CFAA and equivalents |
| Skipping kill-chain order | Single detection wipes all footholds |
| No crown jewels defined | Drifts into open-ended vulnerability hunting |
| Avoiding all detectable techniques | Unrealistic engagement, does not validate detection |
| No real-time documentation | Retroactive logs are unreliable for reporting |
| Leaving artifacts post-exercise | Creates permanent security risks |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Default credentials in production → CRITICAL flag
- No rate limiting on auth endpoints → flag brute force risk
- Publicly exposed admin panel → flag attack surface

## Output

```markdown
## Red Team Engagement Plan: <target>

### Authorization: RoE signed <date>, scope: <defined scope>
### Access Level: <external/internal/credentialed>
### Crown Jewels: <target assets>

### Kill-Chain Plan
| Phase | Technique | MITRE ID | Effort | OPSEC Risk |
|-------|-----------|----------|--------|-----------|
| Initial Access | Spearphishing | T1566.001 | 0.4 | Low |
| Execution | PowerShell | T1059.001 | 1.4 | Medium |
| Credential Access | LSASS dump | T1003.001 | 1.6 | High |
| Lateral Movement | Pass-the-Hash | T1550.002 | 1.8 | Medium |

### Choke Points: T1003 (credential dump) — blocks 3 attack paths
### Total Effort Score: 5.2
### Detection Gaps: <identified gaps in blue team coverage>
### Recommendation: Focus detection investment on choke point T1003
```

## References

- [mitre-attack-web.md](references/mitre-attack-web.md) — MITRE ATT&CK tactics and techniques mapped to web application attack surfaces
