---
name: ecom
description: >
  E-commerce department. Store management, product optimization, pricing, launches.
  Integrates with Shopify MCP. Use when user says "ecom", "store", "product", "shop".
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# E-commerce Department — ARKA OS

Store management, product optimization, and e-commerce growth.

## Commands

| Command | Description |
|---------|-------------|
| `/ecom audit <url>` | Full store audit (5 agents) |
| `/ecom product <description>` | Create optimized product listing |
| `/ecom pricing <product>` | Pricing strategy analysis |
| `/ecom launch <store>` | New store launch plan |
| `/ecom ads <product>` | E-commerce ad campaigns |
| `/ecom competitors <url>` | Competitive e-commerce analysis |
| `/ecom seo <url>` | E-commerce SEO audit |
| `/ecom email <type>` | E-commerce email flows (cart, post-purchase, win-back) |
| `/ecom report <store>` | Store performance report |

## MCP Integration

Uses Shopify MCP when available for:
- Product management (get-products, get-collections)
- Order management (get-orders, get-order)
- Customer management (get-customers, tag-customer)
- Discount creation (create-discount)
- Store info (get-shop-details)
