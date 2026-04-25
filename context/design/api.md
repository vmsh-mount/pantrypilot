# Design: FastAPI Surface (Step 4)

**Planned files:**
- `pantrypilot/pantrypilot/api.py` — FastAPI app, two primary endpoints, session store, pydantic models
- `pantrypilot/tests/test_api.py` — endpoint tests using FastAPI's `TestClient`

**Dependency additions** (`requirements.txt`):
```
fastapi>=0.111
uvicorn[standard]>=0.29
httpx>=0.27        # needed by FastAPI TestClient
```

---

## Purpose

Expose the planner loop over HTTP so the demo can be recorded as a Loom walkthrough. A Swiggy reviewer should be able to:

1. Hit `POST /cycle` and see an optimised basket with NFI score returned as JSON
2. Hit `POST /cycle/{session_id}/confirm` to place the order
3. Read the `powered_by: "Swiggy Instamart"` field in every response

Step 4 is also where the confirm stage moves from a blocking CLI prompt to a proper request/response pair with a TTL — satisfying the "4-hour window, one-tap cancel, no dark patterns" requirement.

---

## Scope

**In scope:**
- Two primary endpoints: `/cycle` and `/cycle/{session_id}/confirm`
- Two utility endpoints: `GET /household/{household_id}` and `GET /catalogue`
- In-memory session store with TTL (fixture household only; no real DB)
- Pydantic request/response models at the API boundary
- `PantryPilotAgent.plan_cycle()` and `place_confirmed()` additions (non-breaking)
- `BasketLine.reason: str = ""` field added to `models.py`
- Per-item reason computation in `optimizer.py` (post-solve)
- FastAPI `TestClient` tests
- `uvicorn` run instructions for the Loom recording

**Out of scope:**
- Real Swiggy MCP calls (still mocked)
- Postgres or Redis (still in-memory)
- Authentication / OAuth
- WhatsApp notification channel
- Delivery slot selection

---

## Changes to `planner.py` (non-breaking additions)

The current `run_weekly_cycle()` is a synchronous end-to-end loop that blocks on `input()`. The API needs to split the cycle in two: optimize now, confirm/place later via a separate HTTP call.

Add two public methods to `PantryPilotAgent`:

```python
def plan_cycle(self, household: Household) -> OptimizationResult:
    """Stages 1–3 only. Returns OptimizationResult; does not confirm or place."""
    sense = self._sense(household)
    plan  = self._plan(household, sense)
    return self._optimize(household, plan, sense.pantry)

def place_confirmed(self, household: Household, opt: OptimizationResult) -> PlaceResult:
    """Stage 5 only. Called after the user has confirmed via the API."""
    confirm = ConfirmResult(confirmed=True, basket=opt.basket, reason="confirmed")
    return self._place(household, confirm)
```

`run_weekly_cycle()` is unchanged and stays as the entry point for the CLI demo in step 3.

---

## Session management

Between `POST /cycle` (optimize) and `POST /cycle/{id}/confirm` (place), the `OptimizationResult` must be held somewhere. In step 4 this is an in-memory dict on the FastAPI app state.

```python
@dataclass
class PendingSession:
    household_id: str
    optimization: OptimizationResult
    created_at: float       # time.time()
    ttl_seconds: int = 14400  # 4 hours

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds
```

Sessions are keyed by a `uuid4` string. On confirm or cancel the key is deleted immediately (no replay). Expired sessions return HTTP 410 Gone.

**Step 5 upgrade path:** Replace the in-memory dict with Redis (`SET key value EX 14400`). The session dataclass serialises to JSON; the API code is unchanged except for the storage call.

---

## Endpoints

### `GET /household/{household_id}`

Returns household config for the Loom intro — "here's who we're shopping for."

**Response:**
```json
{
  "household_id": "hh_demo_001",
  "name": "The Sharmas (demo household)",
  "weekly_budget_inr": 2500,
  "pincode": "560001",
  "members": [
    { "name": "Ramesh Sharma", "age": 38, "dietary_patterns": ["vegetarian"], "allergies": [] },
    { "name": "Priya Sharma",  "age": 35, "dietary_patterns": ["vegetarian"], "allergies": ["lactose"] },
    { "name": "Aarav Sharma",  "age": 5,  "dietary_patterns": ["vegetarian"], "allergies": ["nuts"] },
    { "name": "Kamala Sharma", "age": 62, "dietary_patterns": ["vegetarian", "jain"], "allergies": [] }
  ],
  "powered_by": "Swiggy Instamart"
}
```

Step 4 only supports `hh_demo_001`; any other ID returns 404.

---

### `GET /catalogue`

Returns the full catalogue filtered to a household's dietary constraints. Lets the Loom show the filter step explicitly: "31 SKUs → 21 compatible for the Sharmas."

**Query params:** `household_id` (string, required)

**Response `200 OK`:**
```json
{
  "household_id": "hh_demo_001",
  "total_skus": 31,
  "compatible_skus": 21,
  "filtered_out": 10,
  "skus": [
    {
      "sku_id": "sku_milk_lactose_free_1l",
      "name": "Heritage Lactose-Free Milk 1L",
      "brand": "Heritage",
      "price_inr": 95.0,
      "pack_size_g": 1000,
      "tags": ["dairy_lactose_free", "vegetarian"]
    }
  ],
  "powered_by": "Swiggy Instamart"
}
```

**Error responses:**
- `404` — unknown `household_id`

---

### `POST /cycle`

Runs Sense → Plan → Optimize for the given household. Returns a basket and NFI score, plus a `session_id` for the confirm step.

**Request:**
```json
{ "household_id": "hh_demo_001" }
```

**Response `200 OK`:**
```json
{
  "session_id": "3f2a...",
  "household_id": "hh_demo_001",
  "status": "READY_TO_CONFIRM",
  "basket": [
    {
      "sku_id": "sku_milk_lactose_free_1l",
      "name": "Heritage Lactose-Free Milk 1L",
      "brand": "Heritage",
      "quantity": 8,
      "pack_size_g": 1000,
      "price_inr": 95.0,
      "total_price_inr": 760.0,
      "nutrition_estimated": true,
      "reason": "low stock → topped up; calcium 38%, protein 12%"
    }
  ],
  "nfi": {
    "calories_pct": 100.0,
    "protein_pct": 100.0,
    "fibre_pct": 100.0,
    "iron_pct": 100.0,
    "calcium_pct": 100.0,
    "overall_pct": 100.0,
    "contains_estimated": true
  },
  "budget_used_inr": 2490.0,
  "budget_total_inr": 2500.0,
  "binding_nutrient": "calcium",
  "overstocked_skipped": ["sku_basmati_indiagate_1kg", "sku_oil_fortune_1l"],
  "pantry_topup": ["sku_milk_lactose_free_1l"],
  "skus_filtered_out": 10,
  "solve_time_ms": 5.2,
  "confirm_before": "2026-04-25T22:00:00Z",
  "powered_by": "Swiggy Instamart"
}
```

`confirm_before` is the UTC timestamp after which the session expires (now + 4 hours). Surfaces the confirm window to the client.

**Error responses:**
- `404` — unknown `household_id`
- `422` — malformed request body (FastAPI/pydantic handles automatically)

---

### `POST /cycle/{session_id}/confirm`

Confirms or cancels a pending basket. If confirmed, places the order and updates pantry state.

**Request:**
```json
{ "action": "confirm" }
```
or
```json
{ "action": "cancel" }
```

**Response `200 OK` (confirmed):**
```json
{
  "session_id": "3f2a...",
  "status": "PLACED",
  "order_id": "MOCK-hh_demo_001-1745612345678",
  "powered_by": "Swiggy Instamart"
}
```

**Response `200 OK` (cancelled):**
```json
{
  "session_id": "3f2a...",
  "status": "CANCELLED",
  "order_id": null,
  "powered_by": "Swiggy Instamart"
}
```

**Error responses:**
- `404` — session not found (already used or never existed)
- `410 Gone` — session expired (confirm window passed)
- `422` — `action` not `"confirm"` or `"cancel"`

---

## Pydantic models

All request and response models live in `api.py`. They convert to/from domain types at the route handler level — domain types in `models.py` and `optimizer.py` stay as stdlib dataclasses.

```python
# Request models
class CycleRequest(BaseModel):
    household_id: str = "hh_demo_001"

class ConfirmRequest(BaseModel):
    action: Literal["confirm", "cancel"]

# Response models
class MemberResponse(BaseModel): ...
class HouseholdResponse(BaseModel): ...
class BasketLineResponse(BaseModel):
    sku_id: str
    name: str
    brand: str
    quantity: int
    pack_size_g: int
    price_inr: float
    total_price_inr: float
    nutrition_estimated: bool
    reason: str  # e.g. "low stock → topped up; calcium 38%, protein 12%"
class NFIResponse(BaseModel): ...
class CycleResponse(BaseModel): ...
class ConfirmResponse(BaseModel): ...
```

The `powered_by: str = "Swiggy Instamart"` field is on every response model with a hardcoded default. This satisfies the Swiggy program rule: "users should know when they're interacting with Swiggy services."

---

## Per-item reason computation

Each basket line carries a human-readable `reason` string explaining *why the optimizer chose this item*. Computed in `optimizer.py` post-solve (the optimizer already has access to `weekly_targets` and the solved quantities).

**Algorithm (per basket line):**

1. Compute each nutrient's contribution from this line:
   ```python
   contribution[attr] = (sku.nutrition.attr / 100.0) * sku.pack_size_g * quantity
   ```

2. Compute coverage ratio (capped at 1.0):
   ```python
   ratio[attr] = min(1.0, contribution[attr] / weekly_target[attr])
   ```

3. Take the top 2 nutrients by ratio, keeping only those ≥ 5%:
   ```python
   top = sorted(ratios.items(), key=lambda kv: -kv[1])[:2]
   top = [(attr, r) for attr, r in top if r >= 0.05]
   ```

4. Format as `"calcium 38%, protein 12%"`.

5. If the SKU is in `OptimizationResult.pantry_topup`, prepend `"low stock → topped up; "`.

6. If `top` is empty (item contributes <5% to any single nutrient — rare edge case), use `"budget efficiency"` as the fallback.

**Implementation location:** `optimizer.py`, at the end of `BasketOptimizer.optimize()`, after the solve loop populates `basket_lines`. Assign to `BasketLine.reason`.

**Model change required:** Add `reason: str = ""` to `BasketLine` in `models.py`. The field defaults to empty string so existing code and tests are unaffected (no attribute errors).

---

## App wiring

```python
# api.py — startup

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise agent with mock dependencies (step 4 wires real ones here)
    app.state.agent = PantryPilotAgent(
        mcp=MockInstamartClient(catalogue=fixture_catalogue()),
        pantry_store=InMemoryPantryStore({"hh_demo_001": fixture_pantry()}),
    )
    app.state.sessions: dict[str, PendingSession] = {}
    yield

app = FastAPI(title="PantryPilot", lifespan=lifespan)
```

Route handlers pull `agent` and `sessions` from `request.app.state`. This keeps the agent a singleton and avoids re-initialising it per request.

---

## Running the demo

```bash
cd pantrypilot/
pip install -r requirements.txt
uvicorn pantrypilot.api:app --reload
```

Interactive docs at `http://localhost:8000/docs` (FastAPI Swagger UI — good for the Loom recording).

**Loom script (60–90 seconds):**

1. Start server, show Swagger UI briefly
2. `GET /household/hh_demo_001` — "here's the Sharma family: Jain MIL, lactose-intolerant daughter-in-law, nut-allergic 5-year-old"
3. `GET /catalogue?household_id=hh_demo_001` — "31 SKUs in Instamart, 10 filtered out for dietary constraints, 21 go to the optimizer"
4. `POST /cycle` — "the optimizer runs in X ms, builds this basket, hits 100% NFI, calcium was hardest; each item explains itself"
5. Copy `session_id`
6. `POST /cycle/{session_id}/confirm` with `"action": "confirm"` — "order placed"
7. Repeat step 4, then step 6 with `"action": "cancel"` — "4-hour window, one-tap cancel, no surprises"

---

## Testing approach

Use FastAPI's `TestClient` (backed by `httpx`). No live server needed.

```python
from fastapi.testclient import TestClient
from pantrypilot.api import app

client = TestClient(app)
```

Tests to write:

1. `test_get_household_returns_sharma` — GET /household/hh_demo_001 returns correct member count
2. `test_unknown_household_returns_404` — GET /household/unknown returns 404
3. `test_cycle_returns_ready_to_confirm` — POST /cycle returns status READY_TO_CONFIRM and a session_id
4. `test_cycle_basket_has_no_incompatible_skus` — dietary safety end-to-end through the API
5. `test_cycle_response_has_powered_by` — Swiggy branding in response
6. `test_confirm_places_order` — POST confirm with "confirm" returns PLACED + order_id
7. `test_cancel_returns_cancelled` — POST confirm with "cancel" returns CANCELLED, no order_id
8. `test_confirm_session_not_reusable` — second call to same session_id returns 404
9. `test_expired_session_returns_410` — session with ttl=0 returns 410
10. `test_catalogue_filters_incompatible_skus` — GET /catalogue returns 21 compatible, 10 filtered out for hh_demo_001
11. `test_basket_lines_have_reason` — every line in the /cycle response has a non-empty reason string

---

## Decisions

**D1: `/cycle` returns HTTP 200 OK.**

`status: "READY_TO_CONFIRM"` in the body is unambiguous. `200` renders more cleanly in Swagger for the Loom.

**D2: Basket lines include a `reason` field.**

Each `BasketLineResponse` has `reason: str` — a one-line explanation of why the optimizer chose the item (e.g. `"low stock → topped up; calcium 38%, protein 12%"`). Computation spec is in the [Per-item reason computation](#per-item-reason-computation) section above. Implementation touches `models.py` (`BasketLine.reason`) and `optimizer.py` (post-solve annotation).

**D3: `GET /catalogue` is added as a third utility endpoint.**

Shows the "31 SKUs → 21 compatible" filter step in the Loom. Query param: `household_id`. Spec is in the [GET /catalogue](#get-catalogue) section above.

---

## Step 5 handoff notes

- Architecture diagram should show: `HTTP client → FastAPI → PantryPilotAgent → [MockMCP / SwiggyMCP] + [InMemoryStore / PostgresStore]`
- The `powered_by` field and `confirm_before` timestamp are both reviewable by Swiggy for compliance
- The proposal doc needs one edit: remove LangGraph, replace with "plain Python PantryPilotAgent"
- Final README pass: add `uvicorn` run instructions and link to the Loom
