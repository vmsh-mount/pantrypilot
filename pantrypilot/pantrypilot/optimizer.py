"""
PantryPilot CP-SAT basket optimizer — Step 2.

Picks a weekly grocery basket for a household subject to:

  Hard constraints
  ────────────────
  • Budget cap (weekly_budget_inr)
  • Dietary / allergy filtering (pre-applied: optimizer only sees compatible SKUs)

  Objective: maximise  min(coverage%) across five nutrients
  ─────────────────────────────────────────────────────────
  coverage(nutrient) = (pantry_stock_nutrition + basket_nutrition) / weekly_target
  capped per nutrient at 100 % so excess protein doesn't paper over missing calcium.

  Why pantry-offset instead of a buy-penalty?
    If pantry already holds 4.2 kg atta, the atta packs already contribute
    ~52 % protein coverage before any purchase. Buying another 5 kg atta
    barely moves the NFI needle (protein is almost covered) while costing
    ₹295. The optimizer naturally skips it — no artificial penalty needed.

    A small overstocking penalty is retained as a tie-breaker so that
    the overstocked_skipped explainability field is populated even in
    otherwise-tied cases.

  Integer scaling
  ───────────────
  CP-SAT works with integers. All nutrient values are multiplied by
  NUTR_SCALE=10 (one decimal place) and prices by PRICE_SCALE=100 (paise).
  The z_pct variable is 0–100 (integer percentage).
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# When running as `python3 pantrypilot/optimizer.py` from the project root,
# Python puts the file's own directory on sys.path instead of the project root.
# This fixup runs before the package imports so both modes work.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ortools.sat.python import cp_model

from pantrypilot.models import (
    Basket,
    BasketLine,
    Household,
    NFIBreakdown,
    PantryItem,
    SKU,
)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

NUTR_SCALE = 10        # multiply float nutrients → integer (1 decimal place)
PRICE_SCALE = 100      # multiply float prices → integer (paise)
OBJ_NFI_MULT = 10_000  # z_pct weight in objective (dominates penalty)
OBJ_PANTRY_PEN = 50    # per-pack tie-breaker penalty for well-stocked items
MAX_PACKS = 8          # upper bound on packs of any single SKU per week

# An item is "well-stocked" in pantry if pantry_g >= this fraction of pack_size_g.
PANTRY_WELL_STOCKED_FACTOR = 0.5

NUTRIENTS = ["calories_kcal", "protein_g", "fibre_g", "iron_mg", "calcium_mg"]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class OptimizationResult:
    """
    Full result from optimise_basket().

    Designed for transparency: every field that explains a basket decision
    is exposed here, not buried in solver internals.
    """

    basket: Basket
    nfi: NFIBreakdown
    status: str            # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "TIMEOUT"
    solve_time_ms: float
    binding_nutrient: str  # nutrient with lowest % coverage — the bottleneck
    budget_used_inr: float
    budget_total_inr: float
    # Explainability
    overstocked_skipped: list[str] = field(default_factory=list)
    pantry_topup: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pantry_stock(pantry: list[PantryItem]) -> dict[str, float]:
    return {item.sku_id: item.quantity_g for item in pantry}


def _pantry_nutrition_offset(
    pantry: list[PantryItem],
    catalogue: list[SKU],
) -> dict[str, int]:
    """
    Pre-committed nutrition from existing pantry stock, scaled by NUTR_SCALE.
    This is the fixed offset added to basket contributions in the NFI constraints.
    """
    sku_lookup = {s.sku_id: s for s in catalogue}
    offset: dict[str, float] = {attr: 0.0 for attr in NUTRIENTS}
    for item in pantry:
        sku = sku_lookup.get(item.sku_id)
        if sku is None:
            continue
        for attr in NUTRIENTS:
            offset[attr] += getattr(sku.nutrition, attr) * item.quantity_g / 100.0
    return {attr: round(v * NUTR_SCALE) for attr, v in offset.items()}


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


def optimise_basket(
    household: Household,
    catalogue: list[SKU],
    pantry: list[PantryItem],
    *,
    time_limit_s: float = 5.0,
) -> OptimizationResult:
    """
    Build and solve the CP-SAT grocery basket optimisation.

    Parameters
    ----------
    household     : Target household (budget, members, dietary patterns).
    catalogue     : Full SKU list (e.g. fixture_catalogue() or live MCP response).
    pantry        : Current pantry stock. May be an empty list.
    time_limit_s  : CP-SAT wall-clock limit. The demo solves in <100 ms.

    Returns
    -------
    OptimizationResult with basket, NFI score, solve metadata, and
    explainability fields.
    """
    t0 = time.perf_counter()

    # 1. Pre-filter: keep only compatible, in-stock SKUs
    skus = [s for s in catalogue if s.is_compatible_with(household) and s.in_stock]
    n = len(skus)

    pantry_stock = _pantry_stock(pantry)
    weekly_targets = household.weekly_targets()
    budget_paise = round(household.weekly_budget_inr * PRICE_SCALE)

    # 2. Precompute integer coefficients
    price_paise = [round(s.price_inr * PRICE_SCALE) for s in skus]

    def nut_per_pack(s: SKU, attr: str) -> int:
        """Nutrient contribution (scaled) from one pack of SKU s."""
        return round(getattr(s.nutrition, attr) * s.pack_size_g / 100.0 * NUTR_SCALE)

    coeff = {attr: [nut_per_pack(s, attr) for s in skus] for attr in NUTRIENTS}
    target = {
        attr: round(getattr(weekly_targets, attr) * NUTR_SCALE) for attr in NUTRIENTS
    }

    # Fixed offset: nutrition already available in pantry
    pantry_offset = _pantry_nutrition_offset(pantry, catalogue)

    # Pantry flags for explainability
    is_well_stocked = [
        pantry_stock.get(s.sku_id, 0) >= PANTRY_WELL_STOCKED_FACTOR * s.pack_size_g
        for s in skus
    ]
    is_low_stock = [
        0 < pantry_stock.get(s.sku_id, 0) < 0.25 * s.pack_size_g
        for s in skus
    ]

    # 3. Build CP-SAT model
    model = cp_model.CpModel()

    # Decision variables: x[i] = packs of skus[i] to purchase this week
    x = [model.NewIntVar(0, MAX_PACKS, f"x_{s.sku_id}") for s in skus]

    # Hard constraint: total basket cost ≤ weekly budget
    model.Add(sum(x[i] * price_paise[i] for i in range(n)) <= budget_paise)

    # z_pct: the minimum nutrient coverage percentage (0–100)
    # Maximising z_pct is equivalent to maximising the worst-nutrient NFI score.
    z_pct = model.NewIntVar(0, 100, "z_pct")

    for attr in NUTRIENTS:
        if target[attr] <= 0:
            continue
        basket_contrib = sum(x[i] * coeff[attr][i] for i in range(n))
        total_contrib = pantry_offset[attr] + basket_contrib
        # Constraint: total_contrib / target ≥ z_pct / 100
        # Rearranged to avoid division: 100 × total_contrib ≥ z_pct × target
        model.Add(100 * total_contrib >= z_pct * target[attr])

    # Objective: maximise NFI (dominant term) with tie-breaker for overstocking
    obj_terms = [OBJ_NFI_MULT * z_pct]
    for i in range(n):
        if is_well_stocked[i]:
            obj_terms.append(-OBJ_PANTRY_PEN * x[i])

    model.Maximize(sum(obj_terms))

    # 4. Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.log_search_progress = False

    status_code = solver.Solve(model)
    solve_ms = (time.perf_counter() - t0) * 1000

    STATUS = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "TIMEOUT",
    }
    status = STATUS.get(status_code, "UNKNOWN")

    # 5. Extract result
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        empty = Basket(household_id=household.household_id, lines=[])
        empty_nfi = NFIBreakdown(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False)
        return OptimizationResult(
            basket=empty,
            nfi=empty_nfi,
            status=status,
            solve_time_ms=solve_ms,
            binding_nutrient="none",
            budget_used_inr=0.0,
            budget_total_inr=float(household.weekly_budget_inr),
        )

    lines = [
        BasketLine(sku=skus[i], quantity=solver.Value(x[i]))
        for i in range(n)
        if solver.Value(x[i]) > 0
    ]
    basket = Basket(household_id=household.household_id, lines=lines)

    # NFI is computed against targets, including pantry contribution
    # (we report against target only, not pantry-adjusted, so the user
    #  sees whether the full week's need is met from all sources combined)
    pantry_items_in_scope = [
        item for item in pantry
        if any(s.sku_id == item.sku_id for s in catalogue)
    ]
    from pantrypilot.models import NutrientTargets
    pantry_nutr = NutrientTargets(
        calories_kcal=pantry_offset["calories_kcal"] / NUTR_SCALE,
        protein_g=pantry_offset["protein_g"] / NUTR_SCALE,
        fibre_g=pantry_offset["fibre_g"] / NUTR_SCALE,
        iron_mg=pantry_offset["iron_mg"] / NUTR_SCALE,
        calcium_mg=pantry_offset["calcium_mg"] / NUTR_SCALE,
    )
    combined_nutrition = basket.total_nutrition() + pantry_nutr

    nfi = NFIBreakdown.compute(
        combined_nutrition,
        weekly_targets,
        estimated=basket.has_estimated_nutrition(),
    )

    nutrient_pcts = {
        "calories": nfi.calories_pct,
        "protein": nfi.protein_pct,
        "fibre": nfi.fibre_pct,
        "iron": nfi.iron_pct,
        "calcium": nfi.calcium_pct,
    }
    binding_nutrient = min(nutrient_pcts, key=nutrient_pcts.__getitem__)

    overstocked_skipped = [
        skus[i].sku_id
        for i in range(n)
        if is_well_stocked[i] and solver.Value(x[i]) == 0
    ]
    pantry_topup = [
        skus[i].sku_id
        for i in range(n)
        if is_low_stock[i] and solver.Value(x[i]) > 0
    ]

    # Per-item reason: top-2 nutrients by coverage contribution (≥5% threshold)
    _t = {
        "calories": weekly_targets.calories_kcal,
        "protein":  weekly_targets.protein_g,
        "fibre":    weekly_targets.fibre_g,
        "iron":     weekly_targets.iron_mg,
        "calcium":  weekly_targets.calcium_mg,
    }
    _topup_set = set(pantry_topup)
    for line in lines:
        c = line.nutrition_contribution()
        ratios = [
            (name, min(1.0, getattr(c, {"calories": "calories_kcal", "protein": "protein_g",
                                        "fibre": "fibre_g", "iron": "iron_mg",
                                        "calcium": "calcium_mg"}[name]) / _t[name]))
            for name in _t if _t[name] > 0
        ]
        top = [(name, r) for name, r in sorted(ratios, key=lambda kv: -kv[1])[:2] if r >= 0.05]
        line.reason = (
            ", ".join(f"{name} {round(r * 100)}%" for name, r in top)
            if top else "budget efficiency"
        )
        if line.sku.sku_id in _topup_set:
            line.reason = "low stock → topped up; " + line.reason

    return OptimizationResult(
        basket=basket,
        nfi=nfi,
        status=status,
        solve_time_ms=solve_ms,
        binding_nutrient=binding_nutrient,
        budget_used_inr=basket.total_price_inr(),
        budget_total_inr=float(household.weekly_budget_inr),
        overstocked_skipped=overstocked_skipped,
        pantry_topup=pantry_topup,
    )


# ---------------------------------------------------------------------------
# Demo (python pantrypilot/optimizer.py)
# ---------------------------------------------------------------------------


def _demo() -> None:
    import sys as _sys

    # Allow `python3 pantrypilot/optimizer.py` from the project root
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from fixtures.household import fixture_household, fixture_pantry
    from fixtures.instamart_catalogue import fixture_catalogue

    hh = fixture_household()
    pantry = fixture_pantry()
    catalogue = fixture_catalogue()
    compatible = [s for s in catalogue if s.is_compatible_with(hh)]

    print("\n" + "=" * 60)
    print("  PantryPilot — CP-SAT Basket Optimizer Demo")
    print("=" * 60)
    print(f"  Household  : {hh.name}")
    print(f"  Budget     : ₹{hh.weekly_budget_inr} / week")
    print(f"  Members    : {', '.join(m.name.split()[0] for m in hh.members)}")
    print(f"  Catalogue  : {len(compatible)} compatible / {len(catalogue)} total SKUs")
    print(f"  Pantry     : {len(pantry)} items pre-stocked")

    result = optimise_basket(hh, catalogue, pantry)

    print(f"\n  Status     : {result.status}  ({result.solve_time_ms:.1f} ms)")
    print(f"  Spend      : ₹{result.budget_used_inr:.0f} of ₹{result.budget_total_inr:.0f}")

    print("\n  ── Basket ───────────────────────────────────────────────")
    if not result.basket.lines:
        print("  (empty)")
    for line in sorted(result.basket.lines, key=lambda l: -l.total_price_inr()):
        est = "~" if line.sku.nutrition.is_estimated else " "
        print(
            f"  {est}{line.quantity:2d}×  {line.sku.name:<42s}  ₹{line.total_price_inr():>5.0f}"
        )

    print("\n  ── Nutrition Fit Index (NFI, pantry + basket) ───────────")
    nfi = result.nfi
    rows = [
        ("Calories", nfi.calories_pct),
        ("Protein", nfi.protein_pct),
        ("Fibre", nfi.fibre_pct),
        ("Iron", nfi.iron_pct),
        ("Calcium", nfi.calcium_pct),
    ]
    for label, pct in rows:
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        is_binding = label.lower() == result.binding_nutrient and nfi.overall_pct < 100.0
        marker = " ← binding" if is_binding else ""
        print(f"  {label:<10s}  {bar}  {pct:5.1f}%{marker}")
    est_note = "  * contains estimated nutrition (see SKU provenance)" if nfi.contains_estimated else ""
    print(f"  {'─'*52}")
    print(f"  Overall NFI  {nfi.overall_pct:5.1f}%  (worst-nutrient score){est_note}")

    if result.overstocked_skipped:
        print("\n  ── Skipped (well-stocked in pantry) ─────────────────────")
        for sid in result.overstocked_skipped:
            print(f"    - {sid}")

    if result.pantry_topup:
        print("\n  ── Topped up (low in pantry) ────────────────────────────")
        for sid in result.pantry_topup:
            print(f"    + {sid}")

    print()


if __name__ == "__main__":
    _demo()
