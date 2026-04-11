"""
ARKA OS — Command Registry for MCP Prompts Server.

Data-driven registry of all department commands exposed as MCP prompts.
Each command maps to a SKILL.md file that provides the full instruction set.
"""

COMMANDS: dict[str, dict] = {
    # ── System (arka) ────────────────────────────────────────────────────────
    "arka_standup": {
        "department": "system",
        "skill_dir": "arka",
        "slash_command": "/arka standup",
        "title": "ARKA — Daily Standup",
        "description": "Daily standup: summarize active projects, tasks, meetings, and priorities.",
        "arguments": [],
    },
    "arka_status": {
        "department": "system",
        "skill_dir": "arka",
        "slash_command": "/arka status",
        "title": "ARKA — System Status",
        "description": "System status: version, departments, personas, skills, MCPs.",
        "arguments": [],
    },
    # ── Dev ───────────────────────────────────────────────────────────────────
    "dev_do": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev do",
        "title": "Dev — Smart Orchestrator",
        "description": "Smart orchestrator that routes to the correct dev workflow.",
        "arguments": [
            {"name": "description", "description": "What you want to build or fix", "required": True},
        ],
    },
    "dev_feature": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev feature",
        "title": "Dev — Implement Feature",
        "description": "Implement a feature end-to-end with 8-phase enterprise workflow.",
        "arguments": [
            {"name": "description", "description": "Feature description", "required": True},
        ],
    },
    "dev_api": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev api",
        "title": "Dev — Generate API",
        "description": "Generate API endpoints with tests and documentation.",
        "arguments": [
            {"name": "spec", "description": "API specification or description", "required": True},
        ],
    },
    "dev_plan": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev plan",
        "title": "Dev — Architecture Plan",
        "description": "Architecture planning only (no code output).",
        "arguments": [
            {"name": "description", "description": "What to plan", "required": True},
        ],
    },
    "dev_debug": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev debug",
        "title": "Dev — Debug Issue",
        "description": "Diagnose and fix a bug.",
        "arguments": [
            {"name": "issue", "description": "Bug or issue description", "required": True},
        ],
    },
    "dev_refactor": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev refactor",
        "title": "Dev — Refactor Code",
        "description": "Refactor code with quality gates.",
        "arguments": [
            {"name": "target", "description": "Code or component to refactor", "required": True},
        ],
    },
    "dev_db": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev db",
        "title": "Dev — Database Schema",
        "description": "Database schema design and migrations.",
        "arguments": [
            {"name": "description", "description": "Schema or migration description", "required": True},
        ],
    },
    "dev_review": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev review",
        "title": "Dev — Code Review",
        "description": "Code review of current changes.",
        "arguments": [],
    },
    "dev_test": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev test",
        "title": "Dev — Run Tests",
        "description": "Generate and run test suite.",
        "arguments": [],
    },
    "dev_deploy": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev deploy",
        "title": "Dev — Deploy",
        "description": "Deploy to an environment.",
        "arguments": [
            {"name": "environment", "description": "Target environment (dev/staging/prod)", "required": True},
        ],
    },
    "dev_docs": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev docs",
        "title": "Dev — Documentation",
        "description": "Generate technical documentation.",
        "arguments": [],
    },
    "dev_research": {
        "department": "dev",
        "skill_dir": "arka-dev",
        "slash_command": "/dev research",
        "title": "Dev — Research",
        "description": "Research a library, framework, or integration.",
        "arguments": [
            {"name": "topic", "description": "Research topic", "required": True},
        ],
    },
    "dev_scaffold": {
        "department": "dev",
        "skill_dir": "arka-scaffold",
        "slash_command": "/dev scaffold",
        "title": "Dev — Scaffold Project",
        "description": "Create a new project from a starter template.",
        "arguments": [
            {"name": "type", "description": "Project type (laravel, nuxt-saas, nuxt-landing, vue-saas, react, nextjs, etc.)", "required": True},
            {"name": "name", "description": "Project name", "required": True},
        ],
    },
    # ── Marketing ─────────────────────────────────────────────────────────────
    "mkt_social": {
        "department": "mkt",
        "skill_dir": "arka-marketing",
        "slash_command": "/mkt social",
        "title": "Mkt — Social Media Posts",
        "description": "Generate social media posts for multiple platforms.",
        "arguments": [
            {"name": "topic", "description": "Content topic", "required": True},
            {"name": "persona", "description": "Persona name for style (optional)", "required": False},
        ],
    },
    "mkt_calendar": {
        "department": "mkt",
        "skill_dir": "arka-marketing",
        "slash_command": "/mkt calendar",
        "title": "Mkt — Content Calendar",
        "description": "Create a content calendar for a week or month.",
        "arguments": [
            {"name": "period", "description": "Time period (week or month)", "required": True},
        ],
    },
    "mkt_email": {
        "department": "mkt",
        "skill_dir": "arka-marketing",
        "slash_command": "/mkt email",
        "title": "Mkt — Email Sequence",
        "description": "Create email sequences (welcome, nurture, launch, cart).",
        "arguments": [
            {"name": "type", "description": "Email type (welcome, nurture, launch, cart)", "required": True},
            {"name": "topic", "description": "Email topic", "required": True},
        ],
    },
    "mkt_landing": {
        "department": "mkt",
        "skill_dir": "arka-marketing",
        "slash_command": "/mkt landing",
        "title": "Mkt — Landing Page Copy",
        "description": "Generate landing page copy for a product.",
        "arguments": [
            {"name": "product", "description": "Product name or description", "required": True},
            {"name": "persona", "description": "Persona name for style (optional)", "required": False},
        ],
    },
    "mkt_ads": {
        "department": "mkt",
        "skill_dir": "arka-marketing",
        "slash_command": "/mkt ads",
        "title": "Mkt — Ad Copy",
        "description": "Generate ad copy for multiple platforms.",
        "arguments": [
            {"name": "product", "description": "Product name or description", "required": True},
            {"name": "persona", "description": "Persona name for style (optional)", "required": False},
        ],
    },
    "mkt_blog": {
        "department": "mkt",
        "skill_dir": "arka-marketing",
        "slash_command": "/mkt blog",
        "title": "Mkt — Blog Article",
        "description": "Write an SEO-optimized blog article.",
        "arguments": [
            {"name": "topic", "description": "Blog topic", "required": True},
            {"name": "persona", "description": "Persona name for style (optional)", "required": False},
        ],
    },
    # ── E-commerce ────────────────────────────────────────────────────────────
    "ecom_audit": {
        "department": "ecom",
        "skill_dir": "arka-ecommerce",
        "slash_command": "/ecom audit",
        "title": "Ecom — Store Audit",
        "description": "Full e-commerce store audit with parallel analysis.",
        "arguments": [
            {"name": "url", "description": "Store URL", "required": True},
        ],
    },
    "ecom_product": {
        "department": "ecom",
        "skill_dir": "arka-ecommerce",
        "slash_command": "/ecom product",
        "title": "Ecom — Product Listing",
        "description": "Create an optimized product listing.",
        "arguments": [
            {"name": "description", "description": "Product description", "required": True},
        ],
    },
    "ecom_pricing": {
        "department": "ecom",
        "skill_dir": "arka-ecommerce",
        "slash_command": "/ecom pricing",
        "title": "Ecom — Pricing Strategy",
        "description": "Pricing strategy analysis for a product.",
        "arguments": [
            {"name": "product", "description": "Product name", "required": True},
        ],
    },
    "ecom_launch": {
        "department": "ecom",
        "skill_dir": "arka-ecommerce",
        "slash_command": "/ecom launch",
        "title": "Ecom — Store Launch",
        "description": "New store launch plan.",
        "arguments": [
            {"name": "store", "description": "Store name", "required": True},
        ],
    },
    # ── Finance ───────────────────────────────────────────────────────────────
    "fin_report": {
        "department": "fin",
        "skill_dir": "arka-finance",
        "slash_command": "/fin report",
        "title": "Fin — Financial Report",
        "description": "Generate a financial report (monthly/quarterly).",
        "arguments": [
            {"name": "period", "description": "Report period (month or quarter)", "required": True},
        ],
    },
    "fin_forecast": {
        "department": "fin",
        "skill_dir": "arka-finance",
        "slash_command": "/fin forecast",
        "title": "Fin — Revenue Forecast",
        "description": "Revenue and expense forecast.",
        "arguments": [
            {"name": "months", "description": "Number of months to project", "required": True},
        ],
    },
    "fin_budget": {
        "department": "fin",
        "skill_dir": "arka-finance",
        "slash_command": "/fin budget",
        "title": "Fin — Budget Planning",
        "description": "Project budget planning.",
        "arguments": [
            {"name": "project", "description": "Project name", "required": True},
        ],
    },
    "fin_negotiate": {
        "department": "fin",
        "skill_dir": "arka-finance",
        "slash_command": "/fin negotiate",
        "title": "Fin — Negotiation Prep",
        "description": "Prepare for bank or investor negotiation.",
        "arguments": [
            {"name": "context", "description": "Negotiation context", "required": True},
        ],
    },
    "fin_pitch": {
        "department": "fin",
        "skill_dir": "arka-finance",
        "slash_command": "/fin pitch",
        "title": "Fin — Investor Pitch",
        "description": "Investor pitch preparation.",
        "arguments": [
            {"name": "investor", "description": "Investor name or type", "required": True},
        ],
    },
    # ── Operations ────────────────────────────────────────────────────────────
    "ops_tasks": {
        "department": "ops",
        "skill_dir": "arka-operations",
        "slash_command": "/ops tasks",
        "title": "Ops — Task Management",
        "description": "View and manage tasks (via ClickUp).",
        "arguments": [],
    },
    "ops_email": {
        "department": "ops",
        "skill_dir": "arka-operations",
        "slash_command": "/ops email",
        "title": "Ops — Email",
        "description": "Send or draft emails (via Gmail).",
        "arguments": [
            {"name": "type", "description": "Email type or action", "required": True},
        ],
    },
    "ops_calendar": {
        "department": "ops",
        "skill_dir": "arka-operations",
        "slash_command": "/ops calendar",
        "title": "Ops — Calendar",
        "description": "View and manage schedule (via Google Calendar).",
        "arguments": [],
    },
    "ops_meeting": {
        "department": "ops",
        "skill_dir": "arka-operations",
        "slash_command": "/ops meeting",
        "title": "Ops — Meeting",
        "description": "Schedule and prepare a meeting.",
        "arguments": [
            {"name": "topic", "description": "Meeting topic", "required": True},
        ],
    },
    "ops_automate": {
        "department": "ops",
        "skill_dir": "arka-operations",
        "slash_command": "/ops automate",
        "title": "Ops — Automate Process",
        "description": "Create automation for a routine process.",
        "arguments": [
            {"name": "process", "description": "Process description", "required": True},
        ],
    },
    # ── Strategy ──────────────────────────────────────────────────────────────
    "strat_brainstorm": {
        "department": "strat",
        "skill_dir": "arka-strategy",
        "slash_command": "/strat brainstorm",
        "title": "Strat — Brainstorm",
        "description": "Structured brainstorming with 5 perspectives.",
        "arguments": [
            {"name": "topic", "description": "Brainstorm topic", "required": True},
        ],
    },
    "strat_market": {
        "department": "strat",
        "skill_dir": "arka-strategy",
        "slash_command": "/strat market",
        "title": "Strat — Market Analysis",
        "description": "Market analysis and opportunity mapping.",
        "arguments": [
            {"name": "sector", "description": "Market sector", "required": True},
        ],
    },
    "strat_competitor": {
        "department": "strat",
        "skill_dir": "arka-strategy",
        "slash_command": "/strat competitor",
        "title": "Strat — Competitive Analysis",
        "description": "Competitive intelligence deep-dive.",
        "arguments": [
            {"name": "url", "description": "Competitor URL or name", "required": True},
        ],
    },
    "strat_swot": {
        "department": "strat",
        "skill_dir": "arka-strategy",
        "slash_command": "/strat swot",
        "title": "Strat — SWOT Analysis",
        "description": "SWOT analysis for a business.",
        "arguments": [
            {"name": "business", "description": "Business name", "required": True},
        ],
    },
    "strat_evaluate": {
        "department": "strat",
        "skill_dir": "arka-strategy",
        "slash_command": "/strat evaluate",
        "title": "Strat — Evaluate Idea",
        "description": "Evaluate a new idea (pros, cons, risks, ROI).",
        "arguments": [
            {"name": "idea", "description": "Idea description", "required": True},
        ],
    },
    # ── Knowledge Base ────────────────────────────────────────────────────────
    "kb_learn": {
        "department": "kb",
        "skill_dir": "arka-knowledge",
        "slash_command": "/kb learn",
        "title": "KB — Learn from Content",
        "description": "Queue URLs for async download and transcription.",
        "arguments": [
            {"name": "urls", "description": "One or more URLs to learn from", "required": True},
            {"name": "persona", "description": "Persona name to associate (optional)", "required": False},
        ],
    },
    "kb_search": {
        "department": "kb",
        "skill_dir": "arka-knowledge",
        "slash_command": "/kb search",
        "title": "KB — Search Knowledge",
        "description": "Search the knowledge base by topic.",
        "arguments": [
            {"name": "query", "description": "Search query", "required": True},
        ],
    },
    "kb_persona": {
        "department": "kb",
        "skill_dir": "arka-knowledge",
        "slash_command": "/kb persona",
        "title": "KB — View Persona",
        "description": "View or manage a persona profile.",
        "arguments": [
            {"name": "name", "description": "Persona name", "required": True},
        ],
    },
    "kb_write": {
        "department": "kb",
        "skill_dir": "arka-knowledge",
        "slash_command": "/kb write",
        "title": "KB — Generate Content",
        "description": "Generate content using a persona's style and knowledge.",
        "arguments": [
            {"name": "persona", "description": "Persona name", "required": True},
            {"name": "type", "description": "Content type to generate", "required": True},
        ],
    },
}
