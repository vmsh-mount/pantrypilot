# Design: Planner Loop (Step 3)

**Planned files:**
- `pantrypilot/pantrypilot/mcp_client.py` — MCP client protocol + mock implementation
- `pantrypilot/pantrypilot/planner.py` — five pipeline stages wired into a runnable loop
- `pantrypilot/tests/test_planner.py` — end-to-end tests using the mock client

---

## Purpose

Wire the five pipeline stages into a single callable end-to-end loop, with a mock Instamart MCP client standing in for the real Swiggy API. The result is a fully runnable demo that can be recorded for the Loom walkthrough in step 4 — without needing real API access.

Step 3 is also where the seams for step 4 (FastAPI) are designed in. The mock client and the pantry store are injected dependencies; swapping them for real implementations in step 4 should require no changes to the planner itself.

---

## Scope

**In scope for step 3:**
- All five pipeline stages as Python functions
- Mock MCP client returning fixture catalogue data and simulating order placement
- In-memory pantry state (loaded from fixture at cycle start, updated after placement)
- Standalone `run_weekly_cycle()` entry point with printed output — usable as a demo script
- `PlannerResult` type capturing the full cycle outcome
- Tests covering the happy path, dietary safety through the full loop, and order placement

**Out of scope (deferred to step 4):**
- Real Swiggy MCP API calls
- HTTP endpoints
- Persistent pantry state (database)
- Asynchronous 4-hour confirm window
- Delivery slot selection
- Price-change re-optimisation (interface designed for it; not triggered in mock)

---

## The five stages

### Stage 1 — Sense

```python
def sense(household: Household, mcp: InstamartClient, pantry_store: PantryStore) -> SenseResult
```

**Inputs:** household (pincode drives the catalogue query), MCP client, pantry store  
**Outputs:** `SenseResult(catalogue: list[SKU], pantry: list[PantryItem])`

Responsibilities:
- Call `mcp.get_catalogue(pincode)` to get current SKUs with live prices and stock status
- Call `pantry_store.load(household_id)` to get current pantry state
- Return both together so downstream stages have a consistent snapshot

**Why a snapshot:** Sense is called once per cycle. All downstream stages use the same `catalogue` and `pantry` objects from that single call. This prevents a race condition where prices fetched at optimize time differ from prices at place time (within a single run; across runs, price drift is handled separately — see error scenarios below).

In the mock: `mcp.get_catalogue()` returns `fixture_catalogue()`. `pantry_store.load()` returns `fixture_pantry()`.

---

### Stage 2 — Plan

```python
def plan(household: Household, sense: SenseResult) -> PlanResult
```

**Inputs:** household, sense snapshot  
**Outputs:** `PlanResult(compatible_skus: list[SKU], weekly_targets: NutrientTargets, excluded_tags: set[str])`

Responsibilities:
- Compute `household.weekly_targets()`
- Apply `household.excluded_tags()` to filter `sense.catalogue` down to compatible, in-stock SKUs
- Surface the excluded count for explainability

This stage is pure computation — no I/O, no side effects. It exists as a named stage (rather than happening inline in optimize) so tests can verify the filter step independently, and so step 4 can expose filter results in the API response.

---

### Stage 3 — Optimize

```python
def optimize(household: Household, plan: PlanResult, pantry: list[PantryItem]) -> OptimizationResult
```

Thin wrapper around the existing `optimise_basket()` from `optimizer.py`. The planner calls it with the pre-filtered `plan.compatible_skus` rather than the full catalogue — dietary safety has already been enforced by stage 2.

No new logic here. The stage exists as a named step for pipeline clarity and testability.

---

### Stage 4 — Confirm

```python
def confirm(result: OptimizationResult, *, auto: bool = False) -> ConfirmResult
```

**Inputs:** optimization result, `auto` flag  
**Outputs:** `ConfirmResult(confirmed: bool, basket: Basket | None, reason: str)`

For step 3, two modes:

**`auto=True`** (default for tests): immediately confirms without user input. Returns the basket unchanged.

**`auto=False`** (default for the demo script): prints the basket summary and NFI to stdout and waits for a `[Y/n]` prompt. This makes `python3 pantrypilot/planner.py` actually interactive — good for Loom recording without needing FastAPI.

The confirm stage does not modify the basket in step 3. In step 4 it becomes a two-step HTTP flow: POST to stage the basket, GET/PATCH to confirm or edit within a 4-hour window.

---

### Stage 5 — Place

```python
def place(confirmed: ConfirmResult, mcp: InstamartClient, pantry_store: PantryStore) -> PlaceResult
```

**Inputs:** confirmed basket, MCP client, pantry store  
**Outputs:** `PlaceResult(order_id: str, status: str, pantry_updated: bool)`

Responsibilities:
- Call `mcp.place_order(basket)` to submit the order
- On success: call `pantry_store.update(household_id, basket)` to deduct ordered items from pantry and add new stock
- On failure: return the error without crashing; let the caller decide whether to retry

**Pantry update logic (step 3):** After a successful order, each `BasketLine` adds `quantity × pack_size_g` grams to the corresponding pantry item. Items already in pantry get their quantity incremented; new items are added. This is in-memory for step 3.

In the mock: `mcp.place_order()` returns a synthetic `order_id` and always succeeds.

---

## MCP client interface

### Protocol definition

```python
from typing import Protocol

class InstamartClient(Protocol):
    def get_catalogue(self, pincode: str) -> list[SKU]:
        """Return current in-stock SKUs with live prices for the given pincode."""
        ...

    def place_order(self, basket: Basket) -> PlaceResult:
        """Submit a confirmed basket as an Instamart order."""
        ...
```

Two methods only. This is deliberately minimal — it covers exactly what the planner needs for step 3. Step 4 may extend it with `get_delivery_slots()` and `get_cart_status()` if needed.

### Mock implementation

```python
class MockInstamartClient:
    def get_catalogue(self, pincode: str) -> list[SKU]:
        return fixture_catalogue()   # always returns the full mock catalogue

    def place_order(self, basket: Basket) -> PlaceResult:
        order_id = f"MOCK-{basket.household_id}-{int(time.time())}"
        return PlaceResult(order_id=order_id, status="PLACED", pantry_updated=False)
```

The mock is intentionally simple. It doesn't simulate stock depletion, price changes, or partial availability. Those scenarios belong in integration tests against a staging MCP environment.

### Real implementation (step 4 notes)

The real `SwiggyInstamartClient` will call the Swiggy MCP tools via their Python SDK. The important constraints from the Swiggy program rules:

- **No caching catalogue responses** beyond a single cycle. Prices/stock must be fetched fresh per run.
- **Server-side calls only.** MCP is never called from the client/browser.
- **Per-user authentication.** Each call is scoped to the authenticated user's OAuth token.
- **No speculative queries.** Only query for what will actually be used in this user's basket.

The real client will implement the same `InstamartClient` Protocol, so no planner code changes are needed.

---

## Pantry state

### Interface

```python
class PantryStore(Protocol):
    def load(self, household_id: str) -> list[PantryItem]: ...
    def save(self, household_id: str, items: list[PantryItem]) -> None: ...
```

### Mock implementation

`InMemoryPantryStore` holds a dict keyed by `household_id`. Initialised from `fixture_pantry()` for the Sharma household. State is lost between Python process runs, which is fine for step 3.

### Step 4 upgrade

`PostgresPantryStore` reads/writes to a `pantry_items` table. The planner calls the same `load()` / `save()` interface — no changes to planner code.

---

## PlannerResult type

```python
@dataclass
class PlannerResult:
    household_id: str
    status: str                    # "PLACED" | "CONFIRMED_NOT_PLACED" | "DECLINED" | "ERROR"
    optimization: OptimizationResult
    order_id: str | None           # set if status == "PLACED"
    error: str | None              # set if status == "ERROR"
    cycle_time_ms: float           # wall-clock time for the full cycle
```

The `optimization` field is always present even if the order wasn't placed — so the caller can always inspect the basket and NFI score regardless of what happened downstream.

---

## Top-level entry point

```python
def run_weekly_cycle(
    household: Household,
    mcp: InstamartClient,
    pantry_store: PantryStore,
    *,
    auto_confirm: bool = False,
) -> PlannerResult:
```

Each stage is called in sequence; the result of each stage flows into the next. No shared mutable state between stages — everything passes through function returns.

The `__main__` block in `planner.py` instantiates `MockInstamartClient` and `InMemoryPantryStore`, loads the Sharma household, and calls `run_weekly_cycle(..., auto_confirm=False)` so the confirm prompt appears.

---

## Error scenarios

Three error scenarios are in-scope for the interface design (not the mock, but the code should be structured to handle them in step 4):

**1. Price change between sense and place**
Prices fetched at Sense time may differ from what Instamart actually charges at Place time. The real `place_order()` response will include the final charged prices. If any item's price changed enough to bust the budget, `PlaceResult.status` returns `"PRICE_CHANGED"` and the planner should surface this to the user rather than silently placing an over-budget order.

**2. Out-of-stock at placement**
An item in the basket is no longer available when `place_order()` is called. Two options: (a) drop the item and re-optimize without it, or (b) surface it to the user for manual resolution. V1 should do (b) — automatic re-optimization on placement errors risks placing an order the user didn't review.

**3. Partial fulfilment**
Instamart may partially fulfil an order (some items out of stock, rest proceed). The pantry update should only credit items that were actually delivered. The real `PlaceResult` should include a `fulfilled_lines: list[BasketLine]` field alongside the full basket.

These are not implemented in the mock. The interfaces are designed to support them.

---

## File layout

```
pantrypilot/pantrypilot/
  mcp_client.py       ← InstamartClient Protocol + MockInstamartClient
  planner.py          ← PantryStore Protocol + InMemoryPantryStore + 5 stage functions
                         + run_weekly_cycle() + PlannerResult + __main__ demo

pantrypilot/tests/
  test_planner.py     ← end-to-end tests using MockInstamartClient
```

---

## Testing approach

Tests in `test_planner.py` use `MockInstamartClient` and `InMemoryPantryStore` initialised with Sharma fixtures. They should verify:

1. Full cycle completes with status `"PLACED"`
2. Placed basket contains no incompatible SKUs (dietary safety through the full loop)
3. Pantry state is updated after a successful placement
4. Declining at confirm stage returns `"DECLINED"` and does not place an order
5. `cycle_time_ms` is under 200 ms (e2e including optimizer)

Tests do **not** verify the basket contents in detail — that belongs in `test_optimizer.py`. The planner tests verify the pipeline wiring, not the optimization logic.

---

## Open questions

**Q1: Should planner.py include a post-order pantry consumption model?**

After placing an order, PantryPilot should also model weekly consumption so the pantry state for next week's cycle reflects what was used, not just what was ordered. Without this, the pantry grows unboundedly each cycle (each order adds stock but nothing is ever consumed).

Options:
- (a) Skip in step 3 — pantry state is reset from fixture each cycle anyway
- (b) Add a simple `consume(household, pantry)` function that deducts estimated weekly consumption based on household size and average portion sizes per SKU category

Option (a) is fine for a demo. Option (b) makes repeated cycles meaningful. Recommend (a) for step 3, (b) as a named v2 item.

**Q2: How interactive should the confirm stage be in the demo script?**

Currently proposed as a simple `[Y/n]` prompt. Alternatives:
- (a) Just `[Y/n]` — minimal, unambiguous, easy to Loom
- (b) `[Y/n/edit]` where `edit` lets the user remove a specific line item before confirming — more realistic demo but adds non-trivial parsing
- (c) Auto-confirm only, no CLI interaction — keeps step 3 focused on the pipeline plumbing

Recommend (a). The Loom walkthrough needs to show a confirm moment; (a) is enough for that without over-building confirm logic that belongs in the WhatsApp/HTTP layer.

**Q3: Single function or agent class?**

Current proposal: top-level `run_weekly_cycle(household, mcp, pantry_store)` function with the MCP client and pantry store as explicit parameters.

Alternative: `class PantryPilotAgent` with `__init__(self, mcp, pantry_store)` and `run_weekly_cycle(self, household)` method.

The class approach makes dependency injection cleaner when FastAPI instantiates the agent once at startup and reuses it across requests. The functional approach is simpler for testing and avoids state.

Recommend the class approach with a thin `__init__` that only stores injected dependencies — no state beyond that. It signals the right seam for step 4 without adding complexity.

---

## Step 4 handoff notes

When FastAPI is added in step 4, the wiring is:

```python
# api.py
agent = PantryPilotAgent(
    mcp=SwiggyInstamartClient(oauth_token=...),
    pantry_store=PostgresPantryStore(db=...),
)

@app.post("/cycle/{household_id}")
async def trigger_cycle(household_id: str):
    household = await db.get_household(household_id)
    result = await asyncio.to_thread(agent.run_weekly_cycle, household)
    return result
```

The planner itself stays synchronous. Step 4 wraps it in `asyncio.to_thread` to avoid blocking the event loop. No changes to `planner.py`.

The confirm stage becomes async in step 4: `run_weekly_cycle` returns after the optimize stage, storing the `OptimizationResult` in a short-lived session. A separate `/confirm/{session_id}` endpoint handles the user's response. This means the planner in step 4 is split into two calls: `run_until_confirm()` and `complete_after_confirm()`.
