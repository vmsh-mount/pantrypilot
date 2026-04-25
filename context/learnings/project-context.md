# Project Context

Dense reference for resuming work. Enough to continue without reading any code.

---

## What it is

PantryPilot is a health-aware autonomous grocery agent for Swiggy Instamart. It runs a weekly loop — **Sense → Plan → Optimize → Confirm → Place** — that builds a nutritionally balanced basket for a household within budget, respecting every member's dietary constraints and allergies. Built as a Swiggy Builders Club submission (Developer track).

The centerpiece is a CP-SAT optimizer that maximises `min(nutrient coverage %)` across five nutrients (calories, protein, fibre, iron, calcium) subject to a hard budget cap, dietary filtering, and pantry-offset nutrition (existing stock credited before purchasing anything new).

---

## Build status

| Step | Description | Status | Tests |
|---|---|---|---|
| 1 | Domain model + fixtures | Done | 7 |
| 2 | CP-SAT basket optimizer | Done | 12 |
| 3 | Planner loop + mock MCP | Done | 9 |
| 4 | FastAPI + web UI | Done | 13 |
| 5 | Architecture diagram + submission | **Pending** | — |

All commands run from `pantrypilot/` (the Python project root):

```bash
# Verify all 41 tests
python3 tests/test_models.py && python3 tests/test_optimizer.py \
  && python3 tests/test_planner.py && python3 tests/test_api.py

# Start the web demo (open http://localhost:8000)
uvicorn pantrypilot.api:app --reload

# CLI demos (non-web)
python3 pantrypilot/optimizer.py   # optimizer only, non-interactive
python3 pantrypilot/planner.py     # full cycle, Y/n prompt
```

---

## File inventory

```
pantrypilot/pantrypilot/          ← Python package
  models.py         Domain types: Member, Household, SKU, PantryItem, BasketLine
                    (has reason: str = "" field), Basket, NFIBreakdown,
                    NutrientTargets, NutritionPer100g. ICMR-NIN 2020 RDAs.
                    DIETARY_EXCLUSIONS dicts. Enums: Sex, ActivityLevel,
                    DietaryPattern, Allergy, SKUCategory.

  optimizer.py      optimise_basket(household, catalogue, pantry) → OptimizationResult.
                    CP-SAT via OR-Tools. Decision vars x[i]=packs (0..8).
                    Maximises z_pct (min nutrient coverage). Budget hard constraint.
                    Pantry-offset: existing stock as fixed int offset in NFI constraints.
                    OBJ_PANTRY_PEN=50 tie-breaker for well-stocked items.
                    Post-solve: per-item reason annotation on BasketLine.reason.
                    OptimizationResult fields: basket, nfi, status, solve_time_ms,
                    binding_nutrient, budget_used_inr, budget_total_inr,
                    overstocked_skipped, pantry_topup.

  mcp_client.py     InstamartClient Protocol (get_catalogue, place_order).
                    MockInstamartClient(catalogue=...) — takes catalogue at init,
                    place_order returns MOCK-{household_id}-{timestamp_ms}.
                    PlaceResult(order_id, status, error).

  planner.py        PantryPilotAgent(mcp, pantry_store).
                    run_weekly_cycle(hh, *, auto_confirm) — full CLI loop.
                    plan_cycle(hh) → OptimizationResult — stages 1-3 only (API use).
                    place_confirmed(hh, opt) → PlaceResult — stage 5 only (API use).
                    PantryStore Protocol + InMemoryPantryStore.
                    _apply_order_to_pantry — adds stock only (no consumption model).
                    SenseResult, PlanResult, ConfirmResult, PlannerResult types.

  api.py            FastAPI app. Lifespan initialises agent + session dict + household registry.
                    GET  /             → FileResponse(static/index.html)
                    GET  /household/{id} → HouseholdResponse (404 if unknown)
                    GET  /catalogue?household_id= → CatalogueResponse (21 compatible, 10 filtered)
                    POST /cycle        → runs plan_cycle(), stores PendingSession, returns CycleResponse
                    POST /cycle/{id}/confirm → confirm or cancel; session deleted on use; 410 if expired
                    PendingSession(household_id, optimization, created_at, ttl_seconds=14400).
                    All Pydantic response models in same file.

  static/index.html Vanilla SPA (Tailwind CDN, no build step).
                    Auto-loads household + catalogue on DOMContentLoaded (parallel fetch).
                    "Optimise" button → spinner → POST /cycle → renders basket+NFI.
                    Basket: 2-col layout (basket left, NFI bars right).
                    Each item: brand avatar, name, reason (italic), ↑ low-stock badge.
                    NFI: animated progress bars, overall score in large text.
                    Confirm bar: deadline in local time, Confirm/Cancel buttons.
                    Outcome card: green (placed) or grey (cancelled).

pantrypilot/fixtures/
  household.py          fixture_household() → hh_demo_001 "The Sharmas"
                        fixture_pantry() → 6 items (3 well-stocked, 2 low, 1 empty)
  instamart_catalogue.py fixture_catalogue() → 31 SKUs (21 compatible with Sharmas)

pantrypilot/tests/
  test_models.py    7 tests — exclusion logic, RDA aggregation, NFI semantics
  test_optimizer.py 12 tests — budget, dietary safety, pantry decisions, timing
  test_planner.py   9 tests — pipeline wiring, pantry update, confirm/decline
  test_api.py       13 tests — all 4 endpoints, session TTL, one-use sessions, branding

pantrypilot/requirements.txt
  ortools>=9.10, fastapi>=0.111, uvicorn[standard]>=0.29, httpx>=0.27
```

---

## The Sharma household (hh_demo_001)

The stress-test fixture — exercises every dietary axis in one case.

| Member | Age | Constraints |
|---|---|---|
| Ramesh | 38M moderate | vegetarian |
| Priya | 35F moderate | vegetarian + lactose intolerant |
| Aarav | 5M moderate | vegetarian + nut allergy |
| Kamala | 62F sedentary | vegetarian + Jain |

Combined exclusions: meat/fish/egg, dairy, peanut/almond/cashew/walnut, onion/garlic/potato/ginger/carrot/radish/beetroot/sweet_potato.

10 of 31 catalogue SKUs are incompatible (regular dairy, onion/garlic/potato products, peanuts). 21 remain.

Weekly budget: ₹2500. Calcium is the binding constraint — all regular dairy excluded, optimizer covers it via lactose-free milk + chickpeas + leafy greens.

Fixture pantry: atta 4200g (well-stocked), rice 850g (well-stocked), oil 720g (well-stocked), toor dal 80g (low), lactose-free milk 200g (low), paneer 0g (empty, but incompatible — never topped up).

**Expected optimizer output (hh_demo_001):** 7 basket lines, 100% NFI overall, ₹2480/₹2500, OPTIMAL, ~3-5ms.

---

## Settled design decisions

**No LangGraph.** Plain Python `PantryPilotAgent` with five private stage methods. The proposal doc still mentions LangGraph — needs edit before submission.

**Stdlib dataclasses in domain layer; Pydantic only at API boundary.** `BasketLine.reason` is a stdlib dataclass field, not Pydantic.

**Strictest-wins dietary exclusion.** Household excludes any tag any member excludes. Conservative but never wrong. V2: per-member consumption shares (documented in `Household.excluded_tags()` docstring).

**NFI overall = min, not average.** 100% protein + 30% calcium = 30% basket. Surfaces the weakest nutrient. The CP-SAT z_pct variable is naturally bounded by the hardest nutrient.

**Pantry-offset, not a buy-penalty.** Existing pantry stock is a fixed integer offset in NFI constraints. Overstocked items have diminishing marginal NFI return and are naturally skipped. OBJ_PANTRY_PEN=50 is a tie-breaker only.

**Atta (4200g pantry) appears in the basket — this is correct.** 5kg/₹295 is the cheapest protein+fibre source. One pack pushes protein+fibre to 100%, freeing ~₹500 for calcium. Tests document and accept this.

**Five nutrients in v1.** Calories, protein, fibre, iron, calcium. Enough to make the optimizer earn its keep. Documented as a simplification.

**MockInstamartClient takes catalogue at init.** Not hard-coded to `fixture_catalogue()`. Fixture imports stay out of production code.

**No pantry consumption model.** `_apply_order_to_pantry` only adds stock. Pantry grows each cycle. V2 item.

**HTTP 200 for POST /cycle** (not 202). Status field `"READY_TO_CONFIRM"` in body is unambiguous.

**Per-item `reason` field on BasketLine.** Top-2 nutrients by coverage ratio ≥5%, formatted as `"calcium 38%, protein 12%"`. Prepend `"low stock → topped up; "` if in pantry_topup. Computed post-solve in optimizer.py. Fallback: `"budget efficiency"`.

**Session store: in-memory dict with 4h TTL.** Sessions deleted on use (no replay). Expired sessions return HTTP 410. Step 5 upgrade path: Redis `SET key value EX 14400`.

**Frontend: vanilla SPA, no build step.** Tailwind CSS via CDN. Served by `GET /` → `FileResponse`. `_STATIC = Path(__file__).parent / "static"` in api.py.

---

## Swiggy platform constraints (from Swiggy Builders Context doc)

| Rule | Implementation |
|---|---|
| No misrepresenting prices/availability | All prices from mock MCP; never inferred |
| No hiding the brand | `powered_by: "Swiggy Instamart"` on every API response |
| No dark patterns | 4-hour TTL session; one-tap cancel; confirm_before timestamp in response |
| Optimizer must be transparent | per-item reason, binding_nutrient, overstocked_skipped, pantry_topup |
| MCP only for authenticated user's loop | No bulk/speculative catalogue queries |

---

## Step 5 remaining work

- [ ] Architecture diagram: `Browser → FastAPI → PantryPilotAgent → [MockMCP/SwiggyMCP] + [InMemoryStore/PostgresStore]`
- [ ] Edit proposal doc: remove LangGraph, replace with "plain Python PantryPilotAgent"
- [ ] Fill `[YOU]` placeholders in `context/Grocery Automation Responses.md` (name, email, GitHub, LinkedIn)
- [ ] Record 60–90 second Loom walkthrough using the web UI (uvicorn + browser)
- [ ] Final README pass: link to Loom, architecture diagram
- [ ] Consider: pantrypilot.in domain for redirect URI
