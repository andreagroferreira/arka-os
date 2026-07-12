# Open Source License Compatibility Matrix — Deep Reference

> Companion to `dependency-audit/SKILL.md`. License obligations, compatibility rules, and commercial implications.

## License Classification

| License | Type | OSI Approved | Copyleft Strength |
|---------|------|-------------|-------------------|
| MIT | Permissive | Yes | None |
| ISC | Permissive | Yes | None |
| BSD-2-Clause | Permissive | Yes | None |
| BSD-3-Clause | Permissive | Yes | None |
| Apache-2.0 | Permissive | Yes | None (patent grant) |
| MPL-2.0 | Weak copyleft | Yes | File-level |
| LGPL-2.1 | Weak copyleft | Yes | Library-level |
| LGPL-3.0 | Weak copyleft | Yes | Library-level |
| GPL-2.0 | Strong copyleft | Yes | Entire work |
| GPL-3.0 | Strong copyleft | Yes | Entire work |
| AGPL-3.0 | Network copyleft | Yes | Entire work + network use |
| SSPL | Source-available | No | Entire service stack |
| BSL 1.1 | Source-available | No | Time-delayed open source |
| Proprietary | Proprietary | No | Full restriction |

## Compatibility Matrix

Can you combine code under these licenses in the SAME project?

| Dependency License | Your Project: MIT | Your Project: Apache-2.0 | Your Project: GPL-3.0 | Your Project: Proprietary |
|-------------------|:-:|:-:|:-:|:-:|
| MIT | OK | OK | OK | OK |
| BSD-2/3 | OK | OK | OK | OK |
| Apache-2.0 | OK | OK | OK | OK |
| MPL-2.0 | OK (keep MPL files) | OK (keep MPL files) | OK | OK (keep MPL files) |
| LGPL-2.1/3.0 | OK (dynamic link) | OK (dynamic link) | OK | OK (dynamic link only) |
| GPL-2.0 | NO | NO | OK (if "or later") | NO |
| GPL-3.0 | NO | NO | OK | NO |
| AGPL-3.0 | NO | NO | OK (becomes AGPL) | NO |

**Key:** OK = compatible. NO = license violation.

## Obligations by License

### Permissive Licenses (MIT, BSD, ISC, Apache-2.0)

| Obligation | MIT | BSD-2 | BSD-3 | Apache-2.0 |
|------------|:---:|:-----:|:-----:|:----------:|
| Include copyright notice | Yes | Yes | Yes | Yes |
| Include license text | Yes | Yes | Yes | Yes |
| State changes | No | No | No | Yes |
| Patent grant | No | No | No | Yes |
| No endorsement clause | No | No | Yes | No |
| NOTICE file preservation | No | No | No | Yes |

### Copyleft Licenses (MPL, LGPL, GPL, AGPL)

| Obligation | MPL-2.0 | LGPL-3.0 | GPL-3.0 | AGPL-3.0 |
|------------|:-------:|:--------:|:-------:|:--------:|
| Source code of modified files | Yes | Yes | Yes | Yes |
| Source code of entire work | No | No | Yes | Yes |
| Network use triggers copyleft | No | No | No | Yes |
| Allow reverse engineering | No | Yes | Yes | Yes |
| Provide installation info | No | No | Yes | Yes |
| Anti-tivoization clause | No | No | Yes | Yes |

## Commercial Use Decision Tree

```
START: Is the dependency's license identified?
  NO  --> STOP. Do not use. Unknown license = all rights reserved.
  YES --> Is it permissive (MIT, BSD, ISC, Apache)?
    YES --> SAFE for commercial use. Include attribution.
    NO  --> Is it weak copyleft (MPL, LGPL)?
      YES --> SAFE if:
        MPL: Keep modified MPL files open-source
        LGPL: Dynamic linking only (no static linking in proprietary)
      NO  --> Is it strong copyleft (GPL)?
        YES --> NOT SAFE for proprietary. Your entire project becomes GPL.
               Exception: GPL with Classpath Exception (like OpenJDK)
        NO  --> Is it network copyleft (AGPL)?
          YES --> NOT SAFE. Even SaaS use triggers copyleft.
          NO  --> Is it source-available (SSPL, BSL)?
            YES --> Review specific terms. Usually NOT safe for competing services.
            NO  --> Legal review required.
```

## Common Ecosystem License Risks

### Node.js (npm)

| Risk Pattern | Example | Action |
|-------------|---------|--------|
| Transitive GPL dependency | `node-sass` (deprecated, had GPL deps) | Audit full tree with `license-checker` |
| License field missing in package.json | Small utilities | Check source repo manually |
| "SEE LICENSE IN" custom file | Some enterprise libs | Read the actual file |
| Dual license with one GPL option | Some databases | Verify you are using the permissive option |

### PHP (Composer)

| Risk Pattern | Example | Action |
|-------------|---------|--------|
| Laravel itself is MIT | Framework code | Safe |
| Packages wrapping GPL tools | ImageMagick bindings | Check if wrapper license differs from tool |
| WordPress ecosystem (GPL-2.0+) | Themes, plugins | All derivatives must be GPL |

### Python (pip)

| Risk Pattern | Example | Action |
|-------------|---------|--------|
| PSF license (Python itself) | Standard lib | Safe, permissive |
| LGPL in scientific computing | Some NumPy deps historically | Dynamic linking usually fine |
| GPL in CLI tools used via subprocess | `pandoc` (GPL) | Subprocess call != linking (generally safe) |

## Dual Licensing Strategies

| Strategy | How It Works | Example |
|----------|-------------|---------|
| Open core | AGPL for community, proprietary for enterprise | MongoDB (was AGPL, now SSPL) |
| GPL + commercial | GPL for open use, paid license for proprietary embedding | MySQL, Qt |
| MIT + paid support | MIT code, paid for SLA/support/features | Many SaaS tools |
| BSL time-delay | Source-available now, becomes open source after N years | CockroachDB, Sentry |

## License Audit Automation

### npm

```bash
# List all licenses
npx license-checker --summary

# Fail CI on copyleft
npx license-checker --failOn "GPL-2.0;GPL-3.0;AGPL-3.0"

# Export for legal review
npx license-checker --csv --out licenses.csv
```

### Composer (PHP)

```bash
# List licenses
composer licenses

# Detailed with dependencies
composer licenses --format=json
```

### pip (Python)

```bash
pip-licenses --format=table --with-urls
pip-licenses --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0"
```

## License Change Risks

| Event | Risk | Action |
|-------|------|--------|
| Maintainer relicenses (MIT -> BSL) | Future versions restricted | Pin to last MIT version |
| CLA-based project changes license | All contributor code affected | Monitor project governance |
| Acquisition changes license | New owner may restrict | Evaluate fork options |
| License removed from package | Defaults to all-rights-reserved | Contact maintainer, find alternative |

### Notable License Changes (Precedents)

| Project | From | To | Year | Impact |
|---------|------|----|------|--------|
| Elasticsearch | Apache-2.0 | SSPL | 2021 | AWS forked as OpenSearch |
| Redis modules | BSD | SSPL | 2024 | Community forks (Valkey) |
| HashiCorp (Terraform) | MPL-2.0 | BSL 1.1 | 2023 | OpenTofu fork |
| MongoDB | AGPL-3.0 | SSPL | 2018 | Cloud providers stopped offering |

## NOTICE File Template

When using Apache-2.0 licensed code, preserve and extend the NOTICE file:

```
This product includes software developed by [Original Author].
Licensed under the Apache License, Version 2.0.

Modifications by [Your Company], [Year].
```

## Quick Reference: "Can I Use This?"

| Your Project Type | Safe Licenses | Caution | Blocked |
|-------------------|--------------|---------|---------|
| Proprietary SaaS | MIT, BSD, ISC, Apache-2.0 | MPL, LGPL (check linking) | GPL, AGPL, SSPL |
| Proprietary desktop app | MIT, BSD, ISC, Apache-2.0 | LGPL (dynamic link only) | GPL, AGPL |
| Open source (MIT) | MIT, BSD, ISC, Apache-2.0 | MPL | GPL, AGPL (would change your license) |
| Open source (GPL-3.0) | All OSI-approved | SSPL, BSL | Proprietary, GPL-2.0-only |
| Internal tool (never distributed) | All (copyleft not triggered) | AGPL (network use triggers) | SSPL (service use triggers) |
