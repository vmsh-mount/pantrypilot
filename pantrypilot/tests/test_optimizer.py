"""
Tests for the CP-SAT basket optimizer (step 2).

These tests verify the optimizer's behaviour at the boundary level —
not that specific brands appear, but that the invariants the demo depends
on hold for the Sharma fixture household.

Run from the pantrypilot/ project root:
    python3 tests/test_optimizer.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fixtures.household import fixture_household, fixture_pantry
from fixtures.instamart_catalogue import fixture_catalogue
from pantrypilot.optimizer import optimise_basket


def test_result_is_optimal():
    """The 21-SKU catalogue should yield OPTIMAL (not just FEASIBLE) within 5 s."""
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    assert result.status == "OPTIMAL", f"Expected OPTIMAL, got {result.status}"


def test_budget_not_exceeded():
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    assert result.budget_used_inr <= result.budget_total_inr + 0.01, (
        f"Basket cost ₹{result.budget_used_inr:.2f} exceeds budget ₹{result.budget_total_inr}"
    )


def test_only_compatible_skus_in_basket():
    """No line in the basket may contain an excluded ingredient tag."""
    hh = fixture_household()
    excluded = hh.excluded_tags()
    result = optimise_basket(hh, fixture_catalogue(), fixture_pantry())
    for line in result.basket.lines:
        violations = line.sku.ingredient_tags & excluded
        assert not violations, (
            f"{line.sku.sku_id} contains excluded tags: {violations}"
        )


def test_zero_micronutrient_items_absent_from_basket():
    """
    Basmati rice (850 g in pantry, 10 mg Ca / 100 g) and sunflower oil
    (720 g in pantry, zero micronutrients) should not appear in the basket.

    Rice: pantry already contributes its modest protein/calories; buying more
    is terrible calcium/iron value per rupee vs leafy greens or pulses.
    Oil: contributes only calories (900 kcal / 100 g) and nothing else —
    once calories are covered from other sources the optimizer has no reason
    to spend budget on it.

    Note: Atta (4200 g in pantry) MAY still appear in the basket — it is
    the single most efficient protein + fibre source per rupee (5 kg pack),
    so the optimizer correctly buys one pack to hit protein/fibre targets
    cheaply, freeing budget for calcium-rich items. The pantry offset ensures
    it buys at most one pack rather than filling the basket with atta.
    """
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    basket_ids = {line.sku.sku_id for line in result.basket.lines}
    assert "sku_basmati_indiagate_1kg" not in basket_ids, (
        "Rice (poor Ca/Fe density) should not appear when better options exist"
    )
    assert "sku_oil_fortune_1l" not in basket_ids, (
        "Sunflower oil (zero micronutrients) should not appear in basket"
    )


def test_pantry_topup_tracking_works():
    """
    Lactose-free milk has only 200 g in pantry (< 0.25 × 1000 g = 250 g)
    and the optimizer heavily relies on it for calcium.  It must appear in
    pantry_topup — the explainability field that shows which low-stock items
    the basket is topping up.

    Note: toor dal (80 g pantry) may NOT appear in the basket if the optimizer
    finds a nutritionally superior and cheaper pulse (e.g. chickpeas at ₹85
    vs toor dal at ₹98 with better fibre and calcium).  The optimizer chooses
    the best option — "low pantry" is a signal, not a mandate to restock that
    exact SKU.
    """
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    assert result.pantry_topup, "pantry_topup should be non-empty when low-stock items are bought"
    assert "sku_milk_lactose_free_1l" in result.pantry_topup, (
        "Low-stock lactose-free milk was bought but not flagged in pantry_topup"
    )


def test_no_regular_dairy_in_basket():
    """
    Priya is lactose-intolerant → 'dairy' tag is excluded for the whole household.
    Regular milk, paneer, curd, and ghee must all be absent.
    """
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    basket_ids = {line.sku.sku_id for line in result.basket.lines}
    regular_dairy = {
        "sku_milk_amul_1l",
        "sku_paneer_milky_mist_200g",
        "sku_curd_nandini_400g",
        "sku_ghee_amul_500ml",
    }
    hits = regular_dairy & basket_ids
    assert not hits, f"Regular dairy items in basket: {hits}"


def test_calcium_sources_present():
    """
    Calcium is the binding constraint for the Sharmas: all regular dairy is
    excluded, pantry contributes almost no calcium (only 200 g lactose-free milk
    = 250 mg vs a ~26 000 mg weekly target). The optimizer must lean on
    lactose-free milk, tofu, and/or leafy greens.
    """
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    basket_ids = {line.sku.sku_id for line in result.basket.lines}
    high_calcium_ids = {
        "sku_milk_lactose_free_1l",   # 125 mg Ca / 100 g
        "sku_tofu_urbanplatter_400g", # 350 mg Ca / 100 g
        "sku_methi_250g",             # 176 mg Ca / 100 g
        "sku_palak_500g",             # 99 mg Ca / 100 g
        "sku_haldi_tata_200g",        # 183 mg Ca / 100 g
        "sku_rajma_organicindia_500g",# 143 mg Ca / 100 g
    }
    found = basket_ids & high_calcium_ids
    assert found, (
        f"Expected at least one calcium-rich SKU in basket; got basket: {basket_ids}"
    )


def test_nfi_overall_equals_minimum_nutrient():
    """
    NFI overall must equal the minimum individual coverage — not the average.
    This is documented as a deliberate design choice (surfaces the bottleneck).
    """
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    nfi = result.nfi
    expected_min = min(
        nfi.calories_pct, nfi.protein_pct, nfi.fibre_pct, nfi.iron_pct, nfi.calcium_pct
    )
    assert abs(nfi.overall_pct - expected_min) < 0.01, (
        f"NFI overall {nfi.overall_pct:.2f}% ≠ min {expected_min:.2f}%"
    )


def test_binding_nutrient_matches_lowest_coverage():
    """binding_nutrient must name the nutrient with the lowest coverage %."""
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    nfi = result.nfi
    pcts = {
        "calories": nfi.calories_pct,
        "protein": nfi.protein_pct,
        "fibre": nfi.fibre_pct,
        "iron": nfi.iron_pct,
        "calcium": nfi.calcium_pct,
    }
    expected_binding = min(pcts, key=pcts.__getitem__)
    assert result.binding_nutrient == expected_binding, (
        f"binding_nutrient={result.binding_nutrient!r} but lowest coverage "
        f"is {expected_binding!r} at {pcts[expected_binding]:.1f}%"
    )


def test_basket_not_empty():
    """A funded household with compatible SKUs should always get a non-empty basket."""
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    assert result.basket.lines, "Basket is unexpectedly empty"


def test_solve_time_under_one_second():
    """CP-SAT should solve the 21-SKU catalogue in well under 1 s."""
    result = optimise_basket(fixture_household(), fixture_catalogue(), fixture_pantry())
    assert result.solve_time_ms < 1000, (
        f"Solver took {result.solve_time_ms:.0f} ms — expected < 1000 ms"
    )


def test_zero_budget_returns_optimal_empty_basket():
    """
    A household with ₹0 budget cannot buy anything. The model is still
    feasible (x=0 is valid), returns OPTIMAL with an empty basket and
    z_pct=0 (pantry might still contribute some coverage, but basket is empty).
    """
    hh = fixture_household()
    import dataclasses
    zero_budget_hh = dataclasses.replace(hh, weekly_budget_inr=0)
    result = optimise_basket(zero_budget_hh, fixture_catalogue(), [])
    assert result.status in ("OPTIMAL", "FEASIBLE"), f"Unexpected status: {result.status}"
    assert result.basket.lines == [], "Zero-budget basket should be empty"
    assert result.budget_used_inr == 0.0


if __name__ == "__main__":
    tests = [
        test_result_is_optimal,
        test_budget_not_exceeded,
        test_only_compatible_skus_in_basket,
        test_zero_micronutrient_items_absent_from_basket,
        test_pantry_topup_tracking_works,
        test_no_regular_dairy_in_basket,
        test_calcium_sources_present,
        test_nfi_overall_equals_minimum_nutrient,
        test_binding_nutrient_matches_lowest_coverage,
        test_basket_not_empty,
        test_solve_time_under_one_second,
        test_zero_budget_returns_optimal_empty_basket,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
