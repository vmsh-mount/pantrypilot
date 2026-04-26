# Design Decisions

Settled choices — context for why things are the way they are.

## 1. No LangGraph / no agent framework

Plain Python `sense → plan → optimize → confirm → place` loop in `planner.py`. Each stage is a pure function or method call.

**Why:** The problem has a deterministic solve path (LP/CP). LangGraph adds indirection without giving the optimizer any additional reasoning capability. A demo that's easy to trace is more convincing than one with unexplained orchestration.

## 2. CP-SAT, not linear relaxation

OR-Tools CP-SAT (integer programming) over scipy `linprog`. Pack sizes are discrete units; half a bag of rice isn't a valid purchase.

**Why:** Fractional solutions look wrong to a grocery shopper even if they're mathematically closer to optimal. Integer solutions are explainable.

## 3. NFI overall = min(core 5 only)

`overall_pct = min(protein, fibre, iron, calcium, calories)`. Extended nutrients (zinc, magnesium, etc.) are display-only and never feed into the objective or the overall score.

**Why:** Extended nutrient data is sparse and source quality varies widely (many SKUs are `CATEGORY_ESTIMATE`). Optimizing against uncertain data would shift the basket toward items that merely happen to have source data, not toward genuinely nutritious ones.

## 4. Pantry offset, not buy-penalty

Existing stock enters the model as a fixed pre-credited quantity in the NFI constraints, not as a cost penalty or forced exclusion.

**Why:** A buy-penalty approach requires tuning a λ weight. Pantry-offset is parameter-free: if you have 800g of atta and your target is 1000g, the optimizer sees 200g still needed — exactly correct.

## 5. None ≠ 0 for extended nutrients

`Optional[float] = None` signals a data gap. Zero means genuinely zero. The UI shows "? data gap" rather than "0%".

**Why:** Silently zeroing missing data would make B12 look like a disaster for every plant-based SKU that hasn't been lab-tested. That's misleading. Surfacing gaps is more honest.

## 6. Strictest-wins dietary exclusion

A household excludes any ingredient tag excluded by any member. There is no per-member basket — one basket serves everyone.

**Why:** Realistic — a family shares meals. It intentionally makes the problem harder and forces the optimizer to find SKUs that thread every constraint.

## 7. In-memory session store (4-hour TTL)

Sessions are a `dict[str, PendingSession]`. Delete-on-use: once confirmed or cancelled, the key is gone.

**Why:** Simplicity for a demo. The upgrade path is one line: replace the dict with `Redis SET key value EX 14400`. The interface is identical.

## 8. Sesame seeds as primary calcium source

At 975 mg Ca/100g, sesame seeds dominate the optimizer's calcium coverage vs lactose-free milk at 125 mg/100g.

**Why:** This is nutritionally correct (sesame seeds are genuinely calcium-dense) and makes for a good demo moment — the optimizer surfacing a non-obvious food.

## 9. Web app API-first plan page

The plan page (`plan.html`) is a JS SPA that calls `/api/*` endpoints on the same web server, rather than rendering server-side.

**Why:** It matches the Swiggy UX pattern (async optimise → spinner → reveal), and means the same API endpoints could power a mobile client. Server-rendered basket (`/basket`) is kept for the test suite.

## 10. Household form saves only; optimizer is user-triggered

`POST /household` saves the household and redirects to the plan page. The optimizer does not run until the user clicks "Plan This Week's Grocery Order".

**Why:** Household profiles are cheap to save. Optimization is the demo's centrepiece — it should feel like a deliberate action, not a side effect of filling a form.
