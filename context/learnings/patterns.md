# Patterns and Gotchas

Recurring design patterns, non-obvious behaviours, and surprises. Dense reference — skip what isn't relevant.

---

## Dietary tag union pattern

All dietary and allergy filtering runs through a single gating function:

```python
household.excluded_tags()           # → set[str]
sku.is_compatible_with(household)   # → bool (ingredient_tags.isdisjoint(excluded))
```

Member-level exclusion sets are unioned at the household level. Pre-filtering happens before the CP-SAT model is built.

**Gotcha:** Tag vocabulary is defined by the catalogue. A typo (`"onions"` vs `"onion"`) silently passes the filter. No schema enforcement.

**Gotcha:** `"dairy_lactose_free"` is a distinct tag — NOT in the excluded set even though `"dairy"` is. Heritage Lactose-Free Milk passes because it lacks the `"dairy"` tag. Test: `test_lactose_free_milk_bypasses_lactose_exclusion`.

---

## CP-SAT integer scaling

CP-SAT requires integers. All floats are scaled before entering the model:

```python
NUTR_SCALE = 10    # 1 decimal place
PRICE_SCALE = 100  # paise

nutr_per_pack = round(per_100g * pack_size_g / 100.0 * NUTR_SCALE)
price_paise   = round(price_inr * PRICE_SCALE)
```

NFI coverage constraint avoids division by rearranging:

```python
# coverage ≥ z_pct/100  →  100 × total ≥ z_pct × target
model.Add(100 * (pantry_offset[attr] + basket_contrib) >= z_pct * target[attr])
```

**Gotcha:** `z_pct * target[attr]` looks like a product of two CP-SAT variables but `target[attr]` is a plain Python int computed before the model is built. CP-SAT accepts `variable × constant` in linear expressions.

---

## Pantry-offset pattern

Existing pantry stock is a fixed integer offset in the NFI constraints — not a decision variable, not a buy-penalty.

```python
pantry_offset[attr] = round(
    sum(sku.nutrition.attr * item.quantity_g / 100.0 for item in pantry)
    * NUTR_SCALE
)
total = pantry_offset[attr] + basket_contribution_expr
model.Add(100 * total >= z_pct * target[attr])
```

**Effect:** Overstocked items have diminishing marginal NFI return and are naturally skipped. `OBJ_PANTRY_PEN=50` is only a tie-breaker to populate `overstocked_skipped`.

**When the optimizer still buys an overstocked item:** Atta (4200g pantry) gets purchased because 5kg/₹295 is the cheapest protein+fibre source, freeing ~₹500 for calcium. This is correct. Tests document and accept it.

---

## NFI min-not-average

```python
overall_pct = min(protein_pct, fibre_pct, iron_pct, calcium_pct, calories_pct)
```

Maximising `z_pct` in CP-SAT is equivalent to maximising `NFI_overall` because z_pct is bounded by the hardest-to-cover nutrient.

**Display gotcha:** When all nutrients hit 100%, `binding_nutrient` is whichever `min()` picks first (currently `"calories"` due to dict insertion order). The UI suppresses the `← binding` marker when `NFI_overall == 100%`.

---

## Per-item reason annotation

Computed in `optimizer.py` post-solve, after `pantry_topup` is known:

```python
for line in lines:
    contrib = line.nutrition_contribution()  # NutrientTargets
    ratios = [
        (name, min(1.0, getattr(contrib, attr) / weekly_targets.attr))
        for name, attr in NUTRIENT_MAP.items() if weekly_targets.attr > 0
    ]
    top = [(n, r) for n, r in sorted(ratios, key=lambda kv: -kv[1])[:2] if r >= 0.05]
    line.reason = (
        ", ".join(f"{n} {round(r*100)}%" for n, r in top)
        if top else "budget efficiency"
    )
    if line.sku.sku_id in pantry_topup_set:
        line.reason = "low stock → topped up; " + line.reason
```

`BasketLine.reason: str = ""` is a stdlib dataclass field with a default — existing code that doesn't set it still works.

---

## API split: plan_cycle / place_confirmed

`run_weekly_cycle()` blocks on `input()` — unusable in an HTTP handler. The API uses two thinner methods:

```python
# POST /cycle calls:
opt = agent.plan_cycle(hh)        # stages 1-3: Sense → Plan → Optimize

# POST /cycle/{id}/confirm calls:
place = agent.place_confirmed(hh, opt)   # stage 5: Place (pantry updated here)
```

`plan_cycle` = `_sense` + `_plan` + `_optimize`. `place_confirmed` = `_place` with a synthetic `ConfirmResult(confirmed=True)`. `run_weekly_cycle` is unchanged for the CLI demo.

---

## Session store pattern

`OptimizationResult` is stored between POST /cycle and POST /cycle/{id}/confirm:

```python
@dataclass
class PendingSession:
    household_id: str
    optimization: OptimizationResult
    created_at: float
    ttl_seconds: int = 14400  # 4 hours

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds
```

Keyed by `uuid4` string in `app.state.sessions`. Deleted on use (confirm or cancel) — no replay. Expired sessions: HTTP 410.

---

## TestClient isolation pattern

Each test creates its own TestClient to get fresh app state (lifespan re-runs on each `with` block):

```python
def test_something():
    with TestClient(app) as client:
        resp = client.post("/cycle", json={"household_id": "hh_demo_001"})
        ...
```

To test session expiry, mutate `app.state.sessions` directly (shared object within the `with` block):

```python
app.state.sessions[session_id].ttl_seconds = 0
```

**Why fresh TestClient per test:** The planner's `InMemoryPantryStore` accumulates state on confirm — a placed order changes the pantry for the next optimizer run in that app instance.

---

## Dependency injection via Protocol

```python
class PantryPilotAgent:
    def __init__(self, mcp: InstamartClient, pantry_store: PantryStore) -> None: ...
```

Both interfaces are `typing.Protocol`. Swapping mock → real in step 5 requires changing only the wiring in `api.py` lifespan, not the agent code.

**Gotcha:** Protocol doesn't enforce at runtime without `runtime_checkable`. Mismatches are caught by mypy, not at import time.

---

## Static file serving from api.py

```python
from pathlib import Path
from fastapi.responses import FileResponse

_STATIC = Path(__file__).parent / "static"

@app.get("/")
def get_ui() -> FileResponse:
    return FileResponse(_STATIC / "index.html")
```

`Path(__file__).parent` is always the directory containing `api.py`, regardless of where uvicorn is invoked from. No `StaticFiles` mount needed for a single-file SPA.

---

## Frontend: double RAF for CSS transition animation

NFI bars start at `width:0%` in HTML, then animate to the actual value. Without the double `requestAnimationFrame`, the initial state isn't painted before the transition fires:

```javascript
// After setHtml() renders bars with style="width:0%"
requestAnimationFrame(() => requestAnimationFrame(() => {
    document.querySelectorAll('.nfi-bar[data-target]').forEach(el => {
        el.style.width = el.dataset.target + '%';
    });
}));
```

---

## Fixture catalogue tripwires (10 incompatible SKUs)

| SKU | Reason |
|---|---|
| `sku_onion_1kg`, `sku_potato_1kg`, `sku_carrot_500g` | Jain |
| `sku_masala_everest_kitchenking`, `sku_chips_lays_potato` | Jain (contains onion/potato) |
| `sku_peanut_chikki_200g` | Nut allergy (Aarav) |
| `sku_milk_amul_1l`, `sku_paneer_milky_mist_200g`, `sku_curd_nandini_400g`, `sku_ghee_amul_500ml` | Lactose (Priya) |

All 10 must be absent from any optimised basket for hh_demo_001.

---

## Patching builtins.input for CLI confirm tests

```python
with patch("builtins.input", return_value="n"):
    result = agent.run_weekly_cycle(hh, auto_confirm=False)
assert result.status == "DECLINED"
```

**Gotcha:** `return_value` returns the same string for every `input()` call. Use `side_effect=[...]` if the code calls `input()` multiple times.

---

## Pantry accumulation (no consumption model)

```python
stock = {item.sku_id: item.quantity_g for item in current}
for line in basket.lines:
    stock[line.sku.sku_id] = stock.get(line.sku.sku_id, 0) + line.sku.pack_size_g * line.quantity
```

Pantry only grows. No deduction. Three cases: item exists (increment), new item (default 0), item not in basket (unchanged). V1 documented limitation.

---

## sys.path fixup for __main__ scripts

Test files and runnable scripts both need the project root on sys.path:

```python
# Top of test files (before any package imports):
sys.path.insert(0, str(Path(__file__).parent.parent))

# Top of pantrypilot/*.py __main__ blocks only:
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

`api.py` omits this entirely — it's only ever imported, never run directly. Fixtures are importable because the test (or uvicorn) already has the project root on sys.path before importing `pantrypilot.api`.
