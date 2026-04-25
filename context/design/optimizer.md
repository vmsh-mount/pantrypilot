# Design: CP-SAT Basket Optimizer

**File:** `pantrypilot/pantrypilot/optimizer.py`

---

## Purpose

Given a household, a product catalogue, and current pantry state, find a weekly grocery basket that maximises nutritional coverage within the household's budget. This is the computational centrepiece of the demo — it's what makes PantryPilot more than a shopping list.

---

## Model formulation

### Decision variables

```
x[i] ∈ {0, 1, …, MAX_PACKS}   for each compatible, in-stock SKU i
```

`x[i]` is the number of packs of SKU `i` to purchase this week. `MAX_PACKS = 8` is a conservative weekly upper bound.

### Hard constraint: budget

```
sum(x[i] × price[i]) ≤ weekly_budget
```

All prices are in integer paise (×100) to avoid floating-point arithmetic in the solver.

### Objective: maximise minimum nutrient coverage

Introduce `z_pct ∈ {0, …, 100}` as the minimum nutrient coverage percentage across all five nutrients. The objective is:

```
maximise: OBJ_NFI_MULT × z_pct − OBJ_PANTRY_PEN × sum(x[i] for overstocked i)
```

Subject to — for each nutrient `n`:

```
100 × (pantry_contribution[n] + basket_contribution[n]) ≥ z_pct × weekly_target[n]
```

Where `pantry_contribution[n]` is a fixed integer (pre-computed, not a variable) and `basket_contribution[n] = sum(x[i] × nutrition_per_pack[i][n])`.

The constraint says: combined pantry + basket nutrition must cover at least `z_pct`% of the weekly target for every nutrient. Maximising `z_pct` pushes all nutrients up simultaneously and naturally focuses budget on whichever nutrient is hardest to meet.

### Integer scaling

CP-SAT works with integers. Nutrient values are multiplied by `NUTR_SCALE = 10` (one decimal place). Prices by `PRICE_SCALE = 100` (paise). `z_pct` is 0–100. After scaling, every constraint is a linear integer inequality.

---

## Key design: pantry-nutrition offset

The pantry stock is pre-credited as a fixed constant in the NFI constraints, not treated as a soft buy-penalty.

**Why this matters:** If the pantry holds 4.2 kg atta, that atta already contributes ~508 g protein and ~462 g fibre toward the weekly target. The optimizer sees protein as ~52% covered before any purchase. Buying more atta only moves the needle on nutrients that are already close to covered — it has diminishing returns.

Compare this to a penalty approach: a per-pack penalty (`−PENALTY × x[atta]`) creates an arbitrary magic number. Too low and atta still floods the basket. Too high and atta is always blocked even when it's genuinely the right choice.

The offset approach has no magic number. It is just correct nutrition accounting.

### Why atta still appears in the basket

Given the Sharma household (budget ₹2500, calcium the hardest constraint), the optimizer buys **one pack of atta** even though 4.2 kg is already in the pantry. This is correct:

- 5 kg atta at ₹295 is the most efficient protein+fibre source per rupee in the catalogue (12.1 g protein / 100 g, 11 g fibre / 100 g — in a 5 kg pack).
- With pantry already at ~52% protein, one atta pack pushes protein to 100% for ₹295.
- This frees the remaining ≈ ₹2200 of budget entirely for calcium-rich items (lactose-free milk, tofu, leafy greens).
- Without that atta pack, the optimizer would need to spend ~₹600–700 more on pulses to cover protein, leaving less for calcium.

The test suite documents this explicitly and tests that only zero-micronutrient items (rice, oil) are truly absent from the basket.

---

## Tuning constants

| Constant | Value | Role |
|---|---|---|
| `MAX_PACKS` | 8 | Upper bound on packs per SKU per week |
| `NUTR_SCALE` | 10 | Nutrient integer precision (1 decimal place) |
| `PRICE_SCALE` | 100 | Price integer precision (paise) |
| `OBJ_NFI_MULT` | 10,000 | z_pct weight — dominates the objective |
| `OBJ_PANTRY_PEN` | 50 | Per-pack tie-breaker penalty for well-stocked items |
| `PANTRY_WELL_STOCKED_FACTOR` | 0.5 | Pantry ≥ 0.5 × pack_size_g → "well-stocked" |

The NFI multiplier (10,000) dominates the pantry penalty (50 × max 8 packs = 400 max). NFI improvement always wins over pantry avoidance. The penalty is purely a tie-breaker and explainability signal.

---

## Explainability fields in `OptimizationResult`

| Field | Meaning |
|---|---|
| `binding_nutrient` | Nutrient with the lowest % coverage — the bottleneck this week |
| `overstocked_skipped` | Items not bought that had ≥ 0.5× pack size in pantry |
| `pantry_topup` | Items bought that had < 25% of pack size in pantry |
| `budget_used_inr` | Actual spend (useful for audit) |
| `solve_time_ms` | Wall-clock solver time |

These fields exist to satisfy Swiggy's transparency requirement: the optimizer must be inspectable. Users can see why each item was included or excluded.

---

## Performance

The demo solves in 4–8 ms on 21 compatible SKUs (MacBook Air M-series, 2025). CP-SAT overhead dominates over actual search time — the problem is small enough that the solver finds the optimal in the first few nodes.

---

## For future contributors

**Adding a new hard constraint** (e.g. "at least 3 distinct vegetable SKUs"): add a `model.Add(...)` call before `model.Maximize(...)`. CP-SAT handles any number of linear constraints.

**Changing the objective** (e.g. "minimise cost given NFI ≥ 75%"): replace `model.Maximize(OBJ_NFI_MULT * z_pct - ...)` with `model.Minimize(total_cost)` and add `model.Add(z_pct >= 75)` as a hard constraint.

**Adding new nutrients**: extend the `NUTRIENTS` list in `optimizer.py` to include the new attribute name. The `coeff` and `target` dictionaries are built dynamically, so the new nutrient is picked up automatically — provided it exists in both `NutritionPer100g` and `NutrientTargets`.

**Pantry SKUs missing from catalogue**: `_pantry_nutrition_offset()` silently skips pantry items whose SKU ID isn't found in the catalogue. This is intentional — stale pantry data (discontinued SKUs) shouldn't break the optimizer. It should be logged in production.

**Scaling to larger catalogues**: CP-SAT handles hundreds of variables comfortably. The 5 ms solve time would grow roughly linearly with SKU count; even at 500 SKUs it would stay well under 1 s.
