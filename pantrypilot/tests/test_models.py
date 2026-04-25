"""
Tests for the domain layer.

These verify the constraints are correctly modelled BEFORE the optimizer is
written. If these tests pass, the optimizer can trust:
  - household.excluded_tags() correctly unions dietary + allergy rules
  - sku.is_compatible_with(household) filters reliably
  - household.weekly_targets() aggregates per-member RDAs × 7
  - NFIBreakdown.compute() reports the WORST nutrient as the overall score
"""

import sys
from pathlib import Path


# Allow running tests via `python tests/test_models.py` from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from fixtures.household import fixture_household
from fixtures.instamart_catalogue import fixture_catalogue, get_sku
from pantrypilot.models import (
    Basket,
    BasketLine,
    NFIBreakdown,
    NutrientTargets,
    NutritionPer100g,
    SKU,
    SKUCategory,
)


def test_household_excluded_tags_union():
    hh = fixture_household()
    excluded = hh.excluded_tags()

    # Vegetarian rules (all members)
    assert "meat" in excluded
    assert "fish" in excluded
    assert "egg" in excluded

    # Jain rules (MIL)
    assert "onion" in excluded
    assert "garlic" in excluded
    assert "potato" in excluded
    assert "carrot" in excluded

    # Allergy rules (kid)
    assert "peanut" in excluded


def test_sku_compatibility_filtering():
    hh = fixture_household()
    catalogue = fixture_catalogue()

    compatible = [sku for sku in catalogue if sku.is_compatible_with(hh)]
    incompatible = [sku for sku in catalogue if not sku.is_compatible_with(hh)]

    incompatible_ids = {s.sku_id for s in incompatible}
    # These MUST be filtered out for the fixture household
    assert "sku_onion_1kg" in incompatible_ids
    assert "sku_potato_1kg" in incompatible_ids
    assert "sku_carrot_500g" in incompatible_ids
    assert "sku_masala_everest_kitchenking" in incompatible_ids  # contains onion+garlic
    assert "sku_chips_lays_potato" in incompatible_ids
    assert "sku_peanut_chikki_200g" in incompatible_ids

    # These MUST remain compatible
    compatible_ids = {s.sku_id for s in compatible}
    assert "sku_toor_dal_tata_500g" in compatible_ids
    assert "sku_palak_500g" in compatible_ids
    assert "sku_milk_lactose_free_1l" in compatible_ids


def test_lactose_free_milk_bypasses_lactose_exclusion():
    """
    Priya is lactose-intolerant. Regular dairy is excluded for her, but
    lactose-free milk (tagged 'dairy_lactose_free') should pass. This is
    the kind of detail that a real household needs.
    """
    hh = fixture_household()
    excluded = hh.excluded_tags()
    assert "dairy" in excluded
    assert "dairy_lactose_free" not in excluded

    lactose_free = get_sku("sku_milk_lactose_free_1l")
    regular_milk = get_sku("sku_milk_amul_1l")
    assert lactose_free is not None and regular_milk is not None
    assert lactose_free.is_compatible_with(hh)
    assert not regular_milk.is_compatible_with(hh)


def test_weekly_targets_aggregation():
    hh = fixture_household()
    targets = hh.weekly_targets()

    # Sanity bounds: 4-person household, weekly protein should be in
    # roughly the 1000-1800g range (4 people × ~50g/day × 7).
    assert 800 < targets.protein_g < 2000
    # Calories: ~7000-12000 kcal/week × 4 people roughly.
    assert 30000 < targets.calories_kcal < 80000


def test_nfi_overall_is_minimum_not_average():
    """
    A basket meeting 100% protein but only 30% iron should score 30%
    overall, not 65%. We DELIBERATELY surface the worst nutrient.
    """
    target = NutrientTargets(
        calories_kcal=10000,
        protein_g=400,
        fibre_g=200,
        iron_mg=100,
        calcium_mg=5000,
    )
    basket_actual = NutrientTargets(
        calories_kcal=10000,  # 100%
        protein_g=400,        # 100%
        fibre_g=200,          # 100%
        iron_mg=30,           # 30% — the weakest
        calcium_mg=5000,      # 100%
    )
    nfi = NFIBreakdown.compute(basket_actual, target, estimated=False)
    assert nfi.protein_pct == 100.0
    assert nfi.iron_pct == 30.0
    assert nfi.overall_pct == 30.0  # min, not average


def test_basket_nutrition_aggregation():
    toor = get_sku("sku_toor_dal_tata_500g")
    assert toor is not None
    basket = Basket(
        household_id="hh_demo_001",
        lines=[BasketLine(sku=toor, quantity=2)],  # 1000g toor dal
    )
    nutrition = basket.total_nutrition()
    # 1000g toor at 22.3g protein/100g -> 223g protein
    assert abs(nutrition.protein_g - 223.0) < 0.5
    assert basket.total_price_inr() == 196.0  # 98 × 2


def test_estimated_provenance_propagates_to_basket():
    toor = get_sku("sku_toor_dal_tata_500g")  # estimated
    oats = get_sku("sku_oats_quaker_1kg")     # verified (label)
    assert toor is not None and oats is not None

    estimated_basket = Basket(
        household_id="hh", lines=[BasketLine(sku=toor, quantity=1)]
    )
    verified_basket = Basket(
        household_id="hh", lines=[BasketLine(sku=oats, quantity=1)]
    )
    mixed_basket = Basket(
        household_id="hh",
        lines=[BasketLine(sku=toor, quantity=1), BasketLine(sku=oats, quantity=1)],
    )

    assert estimated_basket.has_estimated_nutrition()
    assert not verified_basket.has_estimated_nutrition()
    assert mixed_basket.has_estimated_nutrition()  # any estimated -> badge


if __name__ == "__main__":
    tests = [
        test_household_excluded_tags_union,
        test_sku_compatibility_filtering,
        test_lactose_free_milk_bypasses_lactose_exclusion,
        test_weekly_targets_aggregation,
        test_nfi_overall_is_minimum_not_average,
        test_basket_nutrition_aggregation,
        test_estimated_provenance_propagates_to_basket,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
