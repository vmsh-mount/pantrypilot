# PantryPilot — Swiggy Builders Club Proposal

**Track:** Developer
**Contact:** rangavamsi5@gmail.com
**Repo:** github.com/vmsh-mount/pantrypilot

---

## What It Is

PantryPilot is a health-aware autonomous grocery agent built on Swiggy Instamart. It plans a household's weekly grocery basket from first principles — who lives in the home, what their bodies need, what dietary constraints they carry, and what they already have in the pantry — then confirms and places the order through Instamart.

This is a fundamentally different model from saved lists or subscription cycles. Every week is a fresh optimisation solve. The basket changes when the household changes, not when the user remembers to change it.

---

## The Problem

Indian households are nutritionally complex. A typical family might have a lactose-intolerant adult, a child with a nut allergy, an elderly Jain member, and a working adult on a moderate-activity diet. No two members have the same RDA. No subscription model handles this. Most people either over-buy, buy wrong, or spend significant mental energy planning.

The result: nutrition gaps that are invisible (no one tracks whether the basket actually covers the week's iron or calcium needs), and pantry waste from buying what was bought last week, not what is actually needed.

---

## What the Demo Shows

The submitted demo is a working proof-of-concept — a focused slice of the full product, built to validate the core loop.

**What works end-to-end:**
- Household setup: multi-member form with stacked dietary patterns and allergy profiles
- Dietary filter: 67-SKU Instamart catalogue filtered per household constraints (strictest-wins across all members)
- CP-SAT optimisation: OR-Tools integer programming maximising minimum nutrient coverage across protein, fibre, iron, calcium, and calories — within budget
- Pantry offset: declared stock pre-credited in constraints; only the shortfall is bought
- Nutrition transparency: Nutrition Fit Index (NFI) with ICMR-NIN 2020 RDAs, extended nutrient grid, negative nutrient panel (sodium, saturated fat, added sugar vs WHO ceilings)
- Basket by category: items grouped and diversity-enforced across grains, legumes, vegetables, fruits
- Confirm flow: 4-hour session with deadline shown, one-tap cancel
- Item substitution: pre-computed alternatives per basket line, inline swap

**What is mocked for the demo:**
- Instamart catalogue and pricing (fixture data; production would use live MCP)
- Order placement (mock response; production would call Swiggy Order API)
- Pantry state persistence (in-memory; production would use PostgreSQL)
- Auth (none; production would use Swiggy SSO)

The demo is intentionally scoped to prove the optimisation logic and UX — not to simulate infrastructure.

---

## The Broader Idea

The demo covers roughly 20% of what PantryPilot is designed to be. Features deliberately left out of v1 to keep the demo focused:

**Household intelligence**
- Seasonal nutrition adjustments (summer hydration targets, monsoon immunity focus)
- Health condition overlays: diabetic-friendly, PCOS, post-surgery, cardiac — each maps to a nutrient constraint profile
- Child growth tracking: RDA targets that update as the child ages
- Pregnancy and lactation mode: ICMR-NIN specific elevated targets

**Smarter optimisation**
- Recipe-aware basket: optimise for a planned weekly menu, not just nutrient coverage
- Budget flex: "spend ₹200 more and your NFI goes from 74% to 91%" — optional upsell signal
- Seasonal produce preference: weight local and in-season produce higher in the solver
- Carbon footprint as a soft constraint (optional; separate from nutrition objective)

**Pantry intelligence**
- Consumption rate learning: estimate weekly usage from order history, auto-update pantry
- Expiry tracking: flag items likely to expire before the next cycle
- Waste score: show how much of last week's order was actually used

**Order management**
- Partial-delivery handling: if an item goes out of stock post-confirm, re-optimise the gap
- Multi-slot splitting: some categories delivered same-day, others next-day
- Recurring anchors: always include certain items regardless of optimisation (e.g. tea, salt)

**Personalisation**
- Feedback loop: "we didn't like the ragi atta" removes it from future solves
- Per-member preference weights: one member's preference carries more weight for certain categories
- Festival and occasion mode: Diwali basket, fasting basket, etc.

**Platform integrations**
- Swiggy Dineout integration: meals ordered out reduce the home cooking target for that week
- Health app sync (Google Fit, Apple Health): actual activity data instead of self-reported level
- Physician-prescribed constraint import: structured dietary prescription → constraint profile

---

## Why Instamart Is the Right Platform

The core loop only works with a platform that has: real-time catalogue availability, reliable same-day/next-day delivery, and enough SKU depth to satisfy complex dietary constraints. Instamart is the only platform in India with all three at scale.

PantryPilot is not a comparison tool or an aggregation layer. It is a demand-generation agent — it creates net-new basket volume from households who currently under-plan, and increases basket size by surfacing nutritional gaps that commodity shopping misses (sesame seeds, nutritional yeast, drumstick, amla — items that appear because the solver needs them, not because they were on a list).

Every basket, every confirmation, every item carries "Powered by Swiggy Instamart" attribution. The agent is invisible; Swiggy is the platform.

---

## Architecture (Production)

See `context/architecture.md` for the full diagram. Summary:

- Stateless FastAPI service behind API Gateway (Swiggy SSO auth)
- PostgreSQL for household and pantry state; Redis for session TTL and catalogue cache
- Async CP-SAT worker via job queue (decoupled from API response path)
- Instamart MCP for live catalogue, pricing, and stock
- Swiggy Order API for placement; delivery webhook closes the pantry update loop
- Horizontally scalable; no shared state in API pods

---

## Compliance Notes

- No user data is persisted beyond the session in the demo
- Production design: household data stored under Swiggy user ID, governed by Swiggy platform terms
- MCP used only for the authenticated user's own grocery loop — no bulk queries, no competitive data
- "Powered by Swiggy Instamart" on every basket, confirmation, and receipt
- No auto-confirm: 4-hour window, visible deadline, one-tap cancel
- Optimiser reasoning is exposed to the user (per-item reason strings) — no black-box placement

---

## What We're Asking For

MCP access to Swiggy Instamart APIs (catalogue, pricing, stock, order placement) to replace the demo's fixture data with live data. The core optimisation logic, the constraint model, and the UX are production-ready. The missing piece is real inventory.
