# Composio App Research — Pattern Analysis

Research records analyzed: **100**

## Preliminary Findings

- OAuth 2.0 is the dominant authentication pattern, appearing in 52.0% of the researched apps.
- 69.0% of the current research set has evidence of MCP availability.
- 33.0% of apps are currently classified as easy toolkit opportunities.
- 50.0% are classified as moderate buildability opportunities.
- 33 apps currently fall into the preliminary easy-win cluster.
- 9 apps show preliminary signs of access or commercial gating.
- 9 data-quality issues were detected automatically; these should be included in the verification pass rather than silently corrected.

## Authentication

- OAuth 2.0: 52.0%
- API key: 32.0%
- Basic Auth: 19.0%

## API Surface

- REST: 53.0%
- Webhooks: 23.0%
- GraphQL: 13.0%
- RPC: 2.0%
- Other: 2.0%
- SOAP: 1.0%

### API Breadth

- broad: 57.0%
- moderate: 27.0%
- unknown: 16.0%

## MCP

- yes: 69.0%
- no: 22.0%
- unknown: 9.0%

## Buildability

- moderate: 50.0%
- easy: 33.0%
- difficult: 9.0%
- unknown: 8.0%

## Preliminary Priority Clusters

### mcp_opportunity

Count: **37**

HubSpot, Attio, Close, DealCloud, Freshdesk, Pylon, LiveAgent, Plain, Slack, Twilio, Lark (Larksuite), Telegram, Vonage, Meta Ads, GoHighLevel, Mailchimp, Klaviyo, systeme.io, Pinterest, Shopify, WooCommerce, BigCommerce, SE Ranking, Ahrefs, Clay, Supabase, Neo4j, Snowflake, MongoDB Atlas, Notion, Jira, Asana, Coda, Smartsheet, Plaid, Ramp, Otter AI

### easy_win

Count: **33**

Salesforce, Pipedrive, Twenty, Zoho CRM, Zendesk, Intercom, Help Scout, Gorgias, Zoho Cliq, Pumble, Aircall, Google Ads, SendGrid, DataForSEO, MrScraper, Apify, Firecrawl, Bright Data, Waterfall.io, GitHub, Vercel, Netlify, Sentry, Linear, Monday.com, ClickUp, Harvest, Stripe, Fathom, Reducto, higgsfield, Mermaid CLI, YouTube Transcript

### standard

Count: **9**

Podio, WhatsApp Business, Threads (Meta), Magento (Adobe Commerce), Squarespace, Ecwid, Gumroad, Xero, Devin

### gated

Count: **9**

Copper, Front, Gladly, Discord, LinkedIn Ads, Brex, PitchBook, NotebookLM, Grain

### needs_investigation

Count: **8**

fanbasis, Cloudflare, Datadog, Airtable, Binance, Paygent Connect, iPayX, QuickBooks

### difficult

Count: **4**

Salesforce Commerce Cloud, Amazon Selling Partner, Sherlock, Consensus

## Data Quality

Detected **9** issues.

- `HubSpot` — `authentication.methods` — contains_non_string_value
- `HubSpot` — `authentication.methods` — contains_non_string_value
- `HubSpot` — `authentication.methods` — contains_non_string_value
- `HubSpot` — `authentication.token_types` — contains_non_string_value
- `HubSpot` — `authentication.token_types` — contains_non_string_value
- `Apify` — `evidence` — missing_url
- `Binance` — `evidence` — missing_url
- `Binance` — `evidence` — missing_url
- `Grain` — `confidence` — not_numeric

## Evidence Coverage

- Total evidence items: 959
- Average evidence items/app: 9.59
