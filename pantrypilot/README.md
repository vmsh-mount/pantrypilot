# PantryPilot

Health-aware autonomous grocery agent for Swiggy Instamart.

Optimises a household's weekly grocery basket respecting every member's dietary restrictions, allergy profile, and nutritional needs — using OR-Tools CP-SAT against ICMR-NIN 2020 RDAs.

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
  design-decisions.md     Settled architectural choices with rationale
  nutrition-model.md      12-positive + 4-negative nutrient model, ICMR-NIN RDA table
```

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

## The Sharma household (fixture)

Deliberately hard to cater to — exercises every dietary axis:

| Member | Age | Constraint |
|--------|-----|------------|
| Ramesh | 38M | Vegetarian |
| Priya  | 35F | Vegetarian + lactose intolerant |
| Aarav  |  5M | Vegetarian + nut allergy |
| Kamala | 62F | Vegetarian + Jain (no onion/garlic/roots) |

13 of 67 catalogue SKUs are filtered out (dairy, onion/garlic, peanuts). Calcium is the binding constraint — sesame seeds (975 mg Ca/100g) are the optimizer's primary calcium source.

## Nutrition model

**12 positive nutrients tracked** against ICMR-NIN 2020 RDAs (sex × age band):
- Core 5 (optimizer constraints): calories, protein, dietary fibre, iron, calcium
- Extended 7 (display only): zinc, magnesium, potassium, vitamin A, vitamin C, folate, vitamin B12

**4 negative nutrients monitored** against WHO/ICMR ceilings:
- Sodium (< 2000 mg/day), saturated fat (< 10% kcal), added sugar (< 25 g/day), ultra-processed items

`None ≠ 0` — missing source data is surfaced as "data gap" in the UI, never silently zeroed.

## Design principles

**Pantry-offset constraints.** Existing stock is pre-credited in NFI constraints. Overstocked items become poor value naturally — no artificial bans.

**NFI overall = worst of core 5.** A basket scoring 100% protein and 30% iron is a 30% basket. Never papers over gaps.

**Strictest-wins dietary exclusion.** Any ingredient tag excluded by any member is excluded household-wide.

**Per-item transparency.** Every basket line carries a reason string (`"low stock → topped up; calcium 38%, protein 12%"`). Computed post-solve.

**No dark patterns.** 4-hour confirm window with visible deadline. One-tap cancel. No auto-charges.

## Architecture

See [`context/architecture.md`](../context/architecture.md) for the production architecture diagram and demo → production delta table.

## Roadmap

- [x] Step 1 — Domain model + ICMR-NIN RDAs + fixtures
- [x] Step 2 — CP-SAT basket optimizer
- [x] Step 3 — Planner loop with mock MCP
- [x] Step 4 — JSON API + web UI (household form + Swiggy-style plan page)
- [ ] Step 5 — Architecture diagram + Loom walkthrough + submission
