#!/usr/bin/env python3
"""
ARKA OS — Project Stack Detector

Analyzes an existing project directory and outputs a JSON report with:
- Framework detection (Laravel, Nuxt, Vue, React, Next.js, Python, etc.)
- Database, cache, queue, auth, payments detection
- Architecture patterns (monolith, API-only, monorepo, services/repos)
- Convention detection (TypeScript, linting, strict mode, etc.)
- Codebase metrics (models, routes, migrations, components, tests)
- Recommended MCP profile

Usage:
    python3 detect-stack.py /path/to/project
    python3 detect-stack.py /path/to/project --json  (machine-readable output)
"""

import json
import os
import sys
import glob
import re
from pathlib import Path


def detect_stack(project_path: str) -> dict:
    """Analyze a project directory and return a comprehensive stack report."""
    p = Path(project_path).resolve()
    if not p.is_dir():
        return {"error": f"Directory not found: {project_path}"}

    result = {
        "project_path": str(p),
        "project_name": p.name,
        "framework": None,
        "language": None,
        "stack": [],
        "database": [],
        "cache": [],
        "queue": [],
        "auth": [],
        "payments": [],
        "css": [],
        "testing": [],
        "architecture": {
            "type": None,
            "patterns": []
        },
        "conventions": {
            "typescript": False,
            "strict_types": False,
            "eslint": False,
            "prettier": False,
            "phpstan": False,
            "conventional_commits": False,
            "docker": False
        },
        "metrics": {
            "models": 0,
            "controllers": 0,
            "routes_files": 0,
            "migrations": 0,
            "components": 0,
            "pages": 0,
            "tests": 0,
            "api_endpoints": 0
        },
        "mcp_profile": "base",
        "files_found": {}
    }

    # ── Check for key config files ──────────────────────────────────────────
    config_files = {
        "composer.json": p / "composer.json",
        "package.json": p / "package.json",
        "nuxt.config.ts": p / "nuxt.config.ts",
        "nuxt.config.js": p / "nuxt.config.js",
        "next.config.ts": p / "next.config.ts",
        "next.config.js": p / "next.config.js",
        "next.config.mjs": p / "next.config.mjs",
        "vite.config.ts": p / "vite.config.ts",
        "vite.config.js": p / "vite.config.js",
        "tsconfig.json": p / "tsconfig.json",
        ".env": p / ".env",
        ".env.example": p / ".env.example",
        "docker-compose.yml": p / "docker-compose.yml",
        "docker-compose.yaml": p / "docker-compose.yaml",
        "Dockerfile": p / "Dockerfile",
        "pyproject.toml": p / "pyproject.toml",
        "requirements.txt": p / "requirements.txt",
        ".eslintrc.json": p / ".eslintrc.json",
        ".eslintrc.js": p / ".eslintrc.js",
        "eslint.config.js": p / "eslint.config.js",
        "eslint.config.mjs": p / "eslint.config.mjs",
        ".prettierrc": p / ".prettierrc",
        ".prettierrc.json": p / ".prettierrc.json",
        "prettier.config.js": p / "prettier.config.js",
        "phpstan.neon": p / "phpstan.neon",
        "phpstan.neon.dist": p / "phpstan.neon.dist",
        "tailwind.config.js": p / "tailwind.config.js",
        "tailwind.config.ts": p / "tailwind.config.ts",
    }

    for name, path in config_files.items():
        if path.exists():
            result["files_found"][name] = True

    # ── Laravel / PHP Detection ─────────────────────────────────────────────
    composer_path = p / "composer.json"
    if composer_path.exists():
        try:
            composer = json.loads(composer_path.read_text())
            require = {**composer.get("require", {}), **composer.get("require-dev", {})}

            if "laravel/framework" in require:
                result["framework"] = "Laravel"
                result["language"] = "PHP"
                version = require.get("laravel/framework", "")
                result["stack"].append(f"Laravel {version}")

                # Auth
                if "laravel/sanctum" in require:
                    result["auth"].append("Sanctum")
                if "laravel/passport" in require:
                    result["auth"].append("Passport")
                if "laravel/fortify" in require:
                    result["auth"].append("Fortify")
                if "laravel/breeze" in require:
                    result["auth"].append("Breeze")
                if "laravel/jetstream" in require:
                    result["auth"].append("Jetstream")

                # Queue
                if "laravel/horizon" in require:
                    result["queue"].append("Horizon")

                # Payments
                if "laravel/cashier" in require:
                    result["payments"].append("Stripe (Cashier)")
                if "laravel/cashier-paddle" in require:
                    result["payments"].append("Paddle (Cashier)")

                # Testing
                if "pestphp/pest" in require:
                    result["testing"].append("Pest")
                if "phpunit/phpunit" in require:
                    result["testing"].append("PHPUnit")

                # AI
                if "echolabs/prism" in require:
                    result["stack"].append("Prism (AI SDK)")
                if "laravel/boost" in require:
                    result["stack"].append("Laravel Boost")

                # MCP
                if "php-mcp/laravel" in require:
                    result["stack"].append("MCP Server")

                # Check for strict_types
                app_path = p / "app"
                if app_path.exists():
                    php_files = list(app_path.rglob("*.php"))[:5]
                    for pf in php_files:
                        try:
                            content = pf.read_text(errors="ignore")[:200]
                            if "declare(strict_types=1)" in content:
                                result["conventions"]["strict_types"] = True
                                break
                        except Exception:
                            pass

        except (json.JSONDecodeError, Exception):
            pass

    # ── Node.js / Frontend Detection ────────────────────────────────────────
    package_path = p / "package.json"
    if package_path.exists():
        try:
            pkg = json.loads(package_path.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            # Nuxt
            if "nuxt" in deps:
                result["framework"] = result["framework"] or "Nuxt"
                result["stack"].append(f"Nuxt {deps.get('nuxt', '')}")
                result["language"] = result["language"] or "TypeScript"

            # Next.js
            if "next" in deps:
                result["framework"] = result["framework"] or "Next.js"
                result["stack"].append(f"Next.js {deps.get('next', '')}")
                result["language"] = result["language"] or "TypeScript"

            # Vue
            if "vue" in deps and "nuxt" not in deps:
                result["framework"] = result["framework"] or "Vue"
                result["stack"].append(f"Vue {deps.get('vue', '')}")

            # React (without Next)
            if "react" in deps and "next" not in deps:
                result["framework"] = result["framework"] or "React"
                result["stack"].append(f"React {deps.get('react', '')}")

            # TypeScript
            if "typescript" in deps:
                result["conventions"]["typescript"] = True
                result["stack"].append("TypeScript")

            # CSS
            if "tailwindcss" in deps:
                result["css"].append("Tailwind CSS")
            if "sass" in deps or "node-sass" in deps:
                result["css"].append("Sass")
            if "@nuxt/ui" in deps:
                result["css"].append("Nuxt UI")
            if "shadcn" in str(deps) or "@radix-ui" in str(deps):
                result["css"].append("shadcn/ui")

            # Auth
            if "next-auth" in deps or "@auth/core" in deps:
                result["auth"].append("NextAuth")
            if "@supabase/supabase-js" in deps or "@supabase/ssr" in deps:
                result["auth"].append("Supabase Auth")
                result["database"].append("Supabase")

            # State
            if "pinia" in deps:
                result["stack"].append("Pinia")
            if "@tanstack/react-query" in deps:
                result["stack"].append("TanStack Query")
            if "zustand" in deps:
                result["stack"].append("Zustand")

            # Testing
            if "vitest" in deps:
                result["testing"].append("Vitest")
            if "jest" in deps:
                result["testing"].append("Jest")
            if "@playwright/test" in deps:
                result["testing"].append("Playwright")
            if "cypress" in deps:
                result["testing"].append("Cypress")

            # Payments
            if "stripe" in deps or "@stripe/stripe-js" in deps:
                result["payments"].append("Stripe")

        except (json.JSONDecodeError, Exception):
            pass

    # ── Python Detection ────────────────────────────────────────────────────
    if (p / "pyproject.toml").exists() or (p / "requirements.txt").exists():
        if not result["framework"]:
            result["language"] = "Python"
            if (p / "manage.py").exists():
                result["framework"] = "Django"
                result["stack"].append("Django")
            elif (p / "app.py").exists() or (p / "main.py").exists():
                # Check for FastAPI or Flask
                for f in ["app.py", "main.py"]:
                    fp = p / f
                    if fp.exists():
                        try:
                            content = fp.read_text(errors="ignore")[:2000]
                            if "fastapi" in content.lower() or "FastAPI" in content:
                                result["framework"] = "FastAPI"
                                result["stack"].append("FastAPI")
                            elif "flask" in content.lower() or "Flask" in content:
                                result["framework"] = "Flask"
                                result["stack"].append("Flask")
                        except Exception:
                            pass

    # ── Database Detection (from .env or docker-compose) ────────────────────
    env_file = p / ".env.example" if (p / ".env.example").exists() else p / ".env"
    if env_file.exists():
        try:
            env_content = env_file.read_text(errors="ignore")
            if "DB_CONNECTION=pgsql" in env_content or "DATABASE_URL=postgres" in env_content:
                result["database"].append("PostgreSQL")
            elif "DB_CONNECTION=mysql" in env_content:
                result["database"].append("MySQL")
            elif "DB_CONNECTION=sqlite" in env_content:
                result["database"].append("SQLite")

            if "REDIS_HOST" in env_content or "REDIS_URL" in env_content:
                result["cache"].append("Redis")
            if "CACHE_DRIVER=redis" in env_content:
                result["cache"].append("Redis Cache")
            if "QUEUE_CONNECTION=redis" in env_content:
                result["queue"].append("Redis Queue")

            if "MAIL_MAILER" in env_content:
                result["stack"].append("Mail")
            if "STRIPE_KEY" in env_content or "STRIPE_SECRET" in env_content:
                if "Stripe" not in result["payments"] and "Stripe (Cashier)" not in result["payments"]:
                    result["payments"].append("Stripe")
        except Exception:
            pass

    # ── Convention Detection ────────────────────────────────────────────────
    if any(k.startswith(".eslint") or k.startswith("eslint.config") for k in result["files_found"]):
        result["conventions"]["eslint"] = True
    if any(k.startswith(".prettier") or k == "prettier.config.js" for k in result["files_found"]):
        result["conventions"]["prettier"] = True
    if any(k.startswith("phpstan") for k in result["files_found"]):
        result["conventions"]["phpstan"] = True
    if any(k.startswith("docker") or k == "Dockerfile" for k in result["files_found"]):
        result["conventions"]["docker"] = True

    # Check for conventional commits (commitlint or similar)
    if (p / ".commitlintrc.json").exists() or (p / "commitlint.config.js").exists():
        result["conventions"]["conventional_commits"] = True

    # ── Tailwind Detection ──────────────────────────────────────────────────
    if any(k.startswith("tailwind.config") for k in result["files_found"]):
        if "Tailwind CSS" not in result["css"]:
            result["css"].append("Tailwind CSS")

    # ── Architecture Analysis ───────────────────────────────────────────────
    # Check for monorepo
    has_api = (p / "api").is_dir()
    has_frontend = (p / "frontend").is_dir()
    has_packages = (p / "packages").is_dir()
    has_apps = (p / "apps").is_dir()

    if (has_api and has_frontend) or has_packages or has_apps:
        result["architecture"]["type"] = "monorepo"
    elif composer_path.exists() and not package_path.exists():
        # Pure backend
        if (p / "resources" / "views").is_dir():
            result["architecture"]["type"] = "monolith"
        else:
            result["architecture"]["type"] = "api-only"
    elif package_path.exists() and not composer_path.exists():
        result["architecture"]["type"] = "frontend-spa"
    else:
        result["architecture"]["type"] = "standard"

    # Check for services/repositories pattern (Laravel)
    if (p / "app" / "Services").is_dir():
        result["architecture"]["patterns"].append("Services")
    if (p / "app" / "Repositories").is_dir():
        result["architecture"]["patterns"].append("Repositories")
    if (p / "app" / "Actions").is_dir():
        result["architecture"]["patterns"].append("Actions")
    if (p / "app" / "DTOs").is_dir() or (p / "app" / "Data").is_dir():
        result["architecture"]["patterns"].append("DTOs")

    # ── Codebase Metrics ────────────────────────────────────────────────────
    def count_files(pattern: str) -> int:
        return len(list(p.rglob(pattern)))

    # Laravel metrics
    if result["framework"] == "Laravel":
        result["metrics"]["models"] = count_files("app/Models/*.php")
        result["metrics"]["controllers"] = count_files("app/Http/Controllers/**/*.php")
        result["metrics"]["migrations"] = count_files("database/migrations/*.php")
        result["metrics"]["routes_files"] = count_files("routes/*.php")
        result["metrics"]["tests"] = count_files("tests/**/*.php")

    # Frontend metrics
    if result["framework"] in ("Nuxt", "Vue", "React", "Next.js"):
        result["metrics"]["components"] = (
            count_files("components/**/*.vue") +
            count_files("components/**/*.tsx") +
            count_files("components/**/*.jsx") +
            count_files("src/components/**/*.vue") +
            count_files("src/components/**/*.tsx") +
            count_files("src/components/**/*.jsx")
        )
        result["metrics"]["pages"] = (
            count_files("pages/**/*.vue") +
            count_files("pages/**/*.tsx") +
            count_files("app/**/*.tsx") +
            count_files("src/pages/**/*.vue") +
            count_files("src/pages/**/*.tsx")
        )
        result["metrics"]["tests"] = (
            count_files("tests/**/*.test.*") +
            count_files("__tests__/**/*.*") +
            count_files("*.test.*") +
            count_files("*.spec.*")
        )

    # ── MCP Profile Recommendation ──────────────────────────────────────────
    fw = result["framework"]
    if result["architecture"]["type"] == "monorepo" and "Laravel" in str(result["stack"]):
        result["mcp_profile"] = "full-stack"
    elif fw == "Laravel":
        # Check for ecommerce indicators
        if any(x in str(result.get("stack", [])) for x in ["Shopify", "Mirakl"]):
            result["mcp_profile"] = "ecommerce"
        else:
            result["mcp_profile"] = "laravel"
    elif fw == "Nuxt":
        result["mcp_profile"] = "nuxt"
    elif fw == "Vue":
        result["mcp_profile"] = "vue"
    elif fw == "React":
        result["mcp_profile"] = "react"
    elif fw == "Next.js":
        result["mcp_profile"] = "nextjs"
    else:
        result["mcp_profile"] = "base"

    return result


def format_report(data: dict) -> str:
    """Format the detection result as a human-readable report."""
    lines = []
    lines.append(f"Project:       {data['project_name']}")
    lines.append(f"Path:          {data['project_path']}")
    lines.append(f"Framework:     {data.get('framework') or 'Unknown'}")
    lines.append(f"Language:      {data.get('language') or 'Unknown'}")
    lines.append(f"Architecture:  {data['architecture']['type'] or 'Unknown'}")

    if data["stack"]:
        lines.append(f"Stack:         {', '.join(data['stack'])}")
    if data["database"]:
        lines.append(f"Database:      {', '.join(data['database'])}")
    if data["cache"]:
        lines.append(f"Cache:         {', '.join(data['cache'])}")
    if data["queue"]:
        lines.append(f"Queue:         {', '.join(data['queue'])}")
    if data["auth"]:
        lines.append(f"Auth:          {', '.join(data['auth'])}")
    if data["payments"]:
        lines.append(f"Payments:      {', '.join(data['payments'])}")
    if data["css"]:
        lines.append(f"CSS:           {', '.join(data['css'])}")
    if data["testing"]:
        lines.append(f"Testing:       {', '.join(data['testing'])}")
    if data["architecture"]["patterns"]:
        lines.append(f"Patterns:      {', '.join(data['architecture']['patterns'])}")

    # Conventions
    conventions = [k for k, v in data["conventions"].items() if v]
    if conventions:
        lines.append(f"Conventions:   {', '.join(conventions)}")

    # Metrics
    m = data["metrics"]
    active_metrics = {k: v for k, v in m.items() if v > 0}
    if active_metrics:
        metrics_str = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in active_metrics.items())
        lines.append(f"Metrics:       {metrics_str}")

    lines.append(f"MCP Profile:   {data['mcp_profile']}")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 detect-stack.py <project-path> [--json]")
        sys.exit(1)

    project_path = sys.argv[1]
    json_mode = "--json" in sys.argv

    result = detect_stack(project_path)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if json_mode:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))
