# Budly AI Agent System

This repository uses the 264-page `Agent 7 - Affiliate - Blueprint.pdf` as an
operating-system model for multiple business agents serving Compassionate Care
Cultivators and Wake'n'Bake Lounge.

The current priority is **Budly Sales**, a zero-cost customer sales-agent MVP.
The earlier affiliate recruiter remains available as a later-stage prototype.

It includes:

- A customer-facing, mobile-friendly guided chat for all five sales journeys
- A local sales-agent CLI that works without paid services
- Customer discovery, opportunity scoring, and lifecycle state transitions
- Approved-catalog matching with a safe no-match outcome
- Education-first, compliance-aware conversation rules
- SQLite customer and audit storage
- Optional OpenAI Responses API support
- Botpress, Airtable, and GoAffPro implementation mapping
- Blueprint summary, requirements, rollout plan, and tests

## Quick start

Use the bundled Codex Python runtime or any Python 3.11+ installation:

```powershell
python -m src.sales_agent
```

Run the test suite:

```powershell
python -m unittest discover -s tests -v
```

No third-party packages are required. Sales records are written to `data/sales.db`.

## Launch the customer chat

```powershell
python -m src.web_app
```

Then open `http://127.0.0.1:8787`. The local experience guides shoppers through
consumer wellness, culinary, books/courses, NFT membership, or wholesale paths.
It presents only sales-safe catalog fields; medical and negotiated-commercial
questions are saved for human review.

## Deploy to WordPress

The installable zero-cost WordPress package is located at
`deploy/wordpress/budly-sales-agent.zip`. Upload and activate it from the
WordPress Plugins screen. It creates the **Ask Budly** and **Customer Policies**
pages, reads current WooCommerce product data, and sends qualified human
handoffs to `budlysupport@gmail.com`.

See `deploy/wordpress/INSTALL.md` for the WordPress and Wix launch checklist.

## Optional OpenAI mode

Copy `.env.example` values into your environment and set `OPENAI_API_KEY`.
The local rules engine remains the source of truth for score, status, and
escalation; the model only drafts the prospect-facing response.

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "gpt-5.6-luna"
python -m src.sales_agent
```

## Configure the catalog

The 32 live product names and URLs from both WooCommerce shop pages are loaded in
`config/products.json`. Wholesale products are marked for human sales rather than
automated recommendation. Prices, descriptions, claims, ingredients, availability,
shipping terms, and refund rules remain unapproved until reviewed individually.

See `docs/SALES_AGENT_INPUTS.md` for the required product and policy fields.

## What is production-ready vs. still external

The local sales workflow, scoring, validation, persistence, audit trail, risk
routing, catalog matching, and tests are implemented. Customer deployment still
requires an approved catalog, business policies, checkout links, and compliance
review. No paid platform is needed to validate the workflow locally.

Sales model: [`docs/SALES_AGENT_MODEL.md`](docs/SALES_AGENT_MODEL.md)

Required inputs: [`docs/SALES_AGENT_INPUTS.md`](docs/SALES_AGENT_INPUTS.md)
