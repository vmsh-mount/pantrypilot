# PantryPilot — Python Project

Health-aware autonomous grocery agent for Swiggy Instamart.

## Quick start

```bash
pip install -r requirements.txt
uvicorn pantrypilot.api:app --reload
# Open http://localhost:8000
```

Interactive Swagger docs at `http://localhost:8000/docs`.

## Run tests

```bash
python3 tests/test_models.py      # 7 tests  — domain model
python3 tests/test_optimizer.py   # 12 tests — CP-SAT optimizer
python3 tests/test_planner.py     # 9 tests  — planner loop
python3 tests/test_api.py         # 13 tests — FastAPI endpoints + web UI
```

No database, no network calls, no API keys. All data is mocked from `fixtures/`.

## CLI demos (no server)

```bash
python3 pantrypilot/optimizer.py   # prints basket + NFI, non-interactive
python3 pantrypilot/planner.py     # full cycle with Y/n confirm prompt
```

## Project layout

```
pantrypilot/           ← Python package
  models.py            Domain types: Member, Household, SKU, BasketLine, Basket, NFI
  optimizer.py         CP-SAT basket optimizer — the demo centrepiece
  mcp_client.py        InstamartClient Protocol + MockInstamartClient
  planner.py           PantryPilotAgent: five-stage loop + plan_cycle/place_confirmed
  api.py               FastAPI: GET /, GET /household, GET /catalogue, POST /cycle, POST /cycle/.../confirm
  static/index.html    Vanilla SPA (Tailwind CDN): household → catalogue → basket → confirm

fixtures/
  household.py            "The Sharmas" — 4-member stress-test household
  instamart_catalogue.py  31 mock SKUs (21 compatible with Sharmas)

tests/
  test_models.py       7 tests
  test_optimizer.py    12 tests
  test_planner.py      9 tests
  test_api.py          13 tests
```

## Pipeline

```
Sense     Read pantry state and Instamart catalogue (mocked)
  ↓
Plan      Compute household weekly targets; apply dietary/allergy filters
  ↓
Optimize  CP-SAT: maximise min(nutrient coverage %) within budget
  ↓
Confirm   4-hour window: confirm via web UI or CLI prompt; one-tap cancel
  ↓
Place     Submit basket via Instamart MCP; update pantry state
```

## The Sharma household (fixture)

Deliberately hard to cater to — exercises every dietary axis:

| Member | Constraint |
|---|---|
| Ramesh, 38M | Vegetarian |
| Priya, 35F | Vegetarian + lactose intolerant |
| Aarav, 5M | Vegetarian + nut allergy |
| Kamala, 62F | Vegetarian + Jain (no onion/garlic/roots) |

10 of 31 catalogue SKUs are filtered out. 21 go to the optimizer. Calcium is the binding constraint (all regular dairy excluded).

## Design principles

**Pantry-offset, not a buy-penalty.** Existing stock is pre-credited in NFI constraints. Overstocked items naturally become poor value — no artificial ban needed.

**NFI overall = worst nutrient.** A basket with 100% protein and 30% iron scores 30%. Never papers over nutritional gaps.

**Strictest-wins dietary exclusion.** The household excludes any ingredient tag any member excludes. Conservative but never incorrect.

**Per-item transparency.** Every basket line carries a `reason` string (e.g. `"low stock → topped up; calcium 38%, protein 12%"`). Computed post-solve in the optimizer.

**No dark patterns.** The confirm window is 4 hours with a visible deadline. One-tap cancel, no auto-charges.

## Roadmap

- [x] Step 1 — Domain model + fixtures + tests
- [x] Step 2 — CP-SAT basket optimizer
- [x] Step 3 — Planner loop with mock MCP
- [x] Step 4 — FastAPI surface + web UI
- [ ] Step 5 — Architecture diagram + submission
