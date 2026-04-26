# PantryPilot

Health-aware autonomous grocery agent for Swiggy Instamart. Not a subscription cycle — a weekly re-optimisation that reasons from who you are, not what you bought.

Each run is a fresh CP-SAT solve against ICMR-NIN 2020 RDAs: your household's biology (age, sex, activity), culture (dietary patterns, Jain/vegan/lactose constraints stacked across members), and pantry state (only buy what you actually need) all feed the objective function. The basket changes the moment your household changes.


> **This repository is a demo submission** for the Swiggy Builders Club (Developer Track).
The optimization logic, constraint model, and UX have been designed to demonstrate the broader concept. A production version would be significantly more nuanced, robust, and refined.
Catalogue data, order placement, and authentication are currently mocked — the primary missing component is live Instamart MCP integration.
> See [`context/proposal.md`](../context/proposal.md) for the full product vision beyond this demo.

## Quick start

```bash
pip install -r requirements.txt

# Web app (household form → Swiggy-style plan page)
uvicorn pantrypilot.web.app:app --port 8001 --reload
# → http://localhost:8001

# JSON API (Swagger docs)
uvicorn pantrypilot.api:app --reload
# → http://localhost:8000/docs
```

## Run tests

```bash
python3 tests/test_models.py      # 15 tests — domain model + nutrition
python3 tests/test_optimizer.py   # 12 tests — CP-SAT optimizer
python3 tests/test_planner.py     #  9 tests — planner loop
python3 tests/test_api.py         # 13 tests — JSON API endpoints
python3 tests/test_web.py         # 11 tests — web form + basket page
```

60 tests, no database, no network calls, no API keys. All data mocked from `fixtures/`.

## What this demo covers

| Feature | Status |
|---------|--------|
| Multi-member household setup (stacked dietary patterns, allergies) | ✅ |
| Dietary filter — strictest-wins across all members | ✅ |
| CP-SAT basket optimisation against ICMR-NIN 2020 RDAs | ✅ |
| Pantry offset — only buys the shortfall | ✅ |
| NFI score + extended nutrients + negative nutrient panel | ✅ |
| Basket grouped by category with diversity enforcement | ✅ |
| Delivery slot picker + 4-hour confirm window | ✅ |
| Item substitution — pre-computed alternatives per line | ✅ |
| Live Instamart catalogue & pricing | mocked |
| Real order placement | mocked |
| Auth (Swiggy SSO) | mocked |
| Pantry state persistence | in-memory |

## What is intentionally not in this demo

The demo is a focused slice. Features designed but out of scope for v1:
- Recipe-aware basket (plan for a weekly menu, not just nutrient coverage)
- Health condition overlays (diabetic, PCOS, cardiac, post-surgery constraint profiles)
- Consumption rate learning (estimate weekly usage from order history)
- Partial-delivery re-optimisation (item goes out of stock post-confirm)
- Swiggy Dineout integration (meals ordered out reduce the home cooking target)
- Per-member preference feedback loop
- Festival and fasting mode baskets
- Budget flex signal ("spend ₹200 more, NFI goes from 74% → 91%")

Full product vision: [`context/proposal.md`](../context/proposal.md)

## Pipeline

```
Sense     Read pantry state + Instamart catalogue (mocked via MockInstamartClient)
  ↓
Plan      Compute household weekly targets; apply dietary/allergy filters (strictest-wins)
  ↓
Optimize  CP-SAT: maximise min(nutrient coverage %) within budget — pantry-offset constraints
  ↓
Confirm   4-hour window; confirm or cancel via web UI
  ↓
Place     Submit basket via Instamart MCP; update pantry state
```

## Why this isn't just a subscription model

| Typical grocery automation | PantryPilot |
|---------------------------|-------------|
| Learns from purchase history | Derives from household biology — works on first use |
| Ships the same list every week | Re-solves every week; changes when your household changes |
| Pantry-blind | Only buys the shortfall; existing stock is pre-credited |
| Substitution rules | Constraint optimisation — solver picks sesame seeds because the maths, not a rule |
| Convenience metric | Nutritional accountability — NFI score, sodium ceiling, B12 gap all visible |
| Lock-in model | 4-hour confirm window, one-tap cancel, no auto-charges |

## Project layout

```
pantrypilot/              ← Python package
  models.py               Domain types: Member, Household, SKU, Basket, NFIBreakdown
  optimizer.py            CP-SAT optimizer — maximise min(nutrient coverage %)
  mcp_client.py           InstamartClient protocol + MockInstamartClient
  planner.py              PantryPilotAgent: sense → plan → optimize → confirm → place
  api.py                  JSON API: GET /household, GET /catalogue, POST /cycle, POST /cycle/.../confirm
  static/index.html       Original demo SPA (Tailwind, calls JSON API with fixture household)
  web/
    app.py                Web app: household form + Swiggy-style plan page + /api/* endpoints
    templates/
      household_form.html Multi-member form (JS add/remove members, stacked dietary patterns)
      plan.html           Swiggy-style SPA: household card → catalogue bar → basket+NFI → confirm
      basket.html         Server-rendered basket (extended nutrients, negatives panel)
      base.html           Pico.css base layout

fixtures/
  household.py            "The Sharmas" — 4-member stress-test household + pantry state
  instamart_catalogue.py  67 SKUs; 54 compatible with Sharmas, 13 filtered

tests/
  test_models.py          15 tests
  test_optimizer.py       12 tests
  test_planner.py          9 tests
  test_api.py             13 tests
  test_web.py             11 tests

context/
  proposal.md             Full product vision and Swiggy Builders submission doc
  architecture.md         Production architecture diagram + demo → production delta
  design-decisions.md     Settled architectural choices with rationale
  nutrition-model.md      12-positive + 4-negative nutrient model, ICMR-NIN RDA table
```

## Architecture

See [`context/architecture.md`](../context/architecture.md) for the production architecture diagram and demo → production delta table.
