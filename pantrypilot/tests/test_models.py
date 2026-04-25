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
    NegativeTotals,
    NutrientTargets,
    NutritionPer100g,
    NutritionSource,
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


def test_extended_nutrients_none_treated_as_zero_in_contribution():
    """
    Nutrients with None values in the SKU nutrition data contribute 0.0
    to nutrition_contribution(), not an error.
    Toor dal is a plant food — vitamin_b12_mcg is None (no B12 in plants).
    """
    toor = get_sku("sku_toor_dal_tata_500g")
    assert toor is not None
    assert toor.nutrition.vitamin_b12_mcg is None  # plant food, no B12
    line = BasketLine(sku=toor, quantity=1)
    contrib = line.nutrition_contribution()
    assert contrib.vitamin_b12_mcg == 0.0
    # zinc IS now populated for toor dal; check it contributes correctly
    assert toor.nutrition.zinc_mg is not None
    assert contrib.zinc_mg > 0.0


def test_missing_positive_nutrients_returns_b12_for_plants():
    """Plant foods without B12 data show vitamin_b12_mcg as missing."""
    toor = get_sku("sku_toor_dal_tata_500g")
    assert toor is not None
    line = BasketLine(sku=toor, quantity=1)
    missing = line.missing_positive_nutrients()
    assert "vitamin_b12_mcg" in missing
    # zinc, mag, pot are now filled for toor dal — not in missing list
    assert "zinc_mg" not in missing
    assert "magnesium_mg" not in missing


def test_nfi_overall_unchanged_by_extended_nutrients():
    """
    Extended pcts are display-only; they must NOT pull down overall_pct.
    Basket with perfect core-5 coverage but zero extended = 100% overall.
    """
    target = NutrientTargets(
        calories_kcal=10000,
        protein_g=400,
        fibre_g=200,
        iron_mg=100,
        calcium_mg=5000,
        zinc_mg=500,       # large non-zero target
        vitamin_b12_mcg=50,
    )
    basket_actual = NutrientTargets(
        calories_kcal=10000,
        protein_g=400,
        fibre_g=200,
        iron_mg=100,
        calcium_mg=5000,
        zinc_mg=0.0,        # zero contribution (data gap)
        vitamin_b12_mcg=0.0,
    )
    nfi = NFIBreakdown.compute(basket_actual, target, estimated=False)
    assert nfi.overall_pct == 100.0          # core-5 all met
    assert nfi.zinc_pct == 0.0              # extended shows gap
    assert nfi.vitamin_b12_pct == 0.0


def test_negative_totals_sums_correctly():
    """Basket.negative_totals() accumulates sodium/sat-fat/added-sugar from lines."""
    # Build a minimal SKU with known negative values
    sku = SKU(
        sku_id="test_sku",
        name="Test SKU",
        brand="Test",
        category=SKUCategory.OTHER,
        pack_size_g=100,
        price_inr=10,
        nutrition=NutritionPer100g(
            calories_kcal=200,
            protein_g=5,
            fibre_g=2,
            iron_mg=1,
            calcium_mg=50,
            sodium_mg=400.0,
            saturated_fat_g=3.0,
            added_sugar_g=10.0,
            ultra_processed=True,
        ),
    )
    basket = Basket(
        household_id="hh_test",
        lines=[BasketLine(sku=sku, quantity=2)],  # 200g total
    )
    neg = basket.negative_totals()
    # 200g × (400mg/100g) = 800mg sodium
    assert abs(neg.sodium_mg - 800.0) < 0.1
    # 200g × (3g/100g) = 6g sat fat
    assert abs(neg.saturated_fat_g - 6.0) < 0.1
    # 200g × (10g/100g) = 20g added sugar
    assert abs(neg.added_sugar_g - 20.0) < 0.1
    assert neg.ultra_processed_count == 1   # 1 line (not 2 packs)
    assert neg.sodium_missing_lines == 0


def test_negative_totals_tracks_missing_data():
    """Lines with None negatives increment missing counters, not the sum."""
    sku_no_data = SKU(
        sku_id="test_sku_nodata",
        name="No Data SKU",
        brand="Test",
        category=SKUCategory.OTHER,
        pack_size_g=100,
        price_inr=10,
        nutrition=NutritionPer100g(
            calories_kcal=100, protein_g=5, fibre_g=2, iron_mg=1, calcium_mg=50
            # sodium_mg, saturated_fat_g, added_sugar_g all default to None
        ),
    )
    basket = Basket(
        household_id="hh_test",
        lines=[BasketLine(sku=sku_no_data, quantity=1)],
    )
    neg = basket.negative_totals()
    assert neg.sodium_mg == 0.0
    assert neg.sodium_missing_lines == 1
    assert neg.saturated_fat_missing_lines == 1
    assert neg.added_sugar_missing_lines == 1
    assert neg.ultra_processed_count == 0


def test_nutrition_source_enum_on_catalogue():
    """
    Verified items use BRAND_LABEL; IFCT-2017 whole foods use IFCT_2017;
    anything else uses CATEGORY_ESTIMATE.
    """
    oats = get_sku("sku_oats_quaker_1kg")
    toor = get_sku("sku_toor_dal_tata_500g")
    jam = get_sku("sku_jam_kissan_500g")
    assert oats is not None and toor is not None and jam is not None
    assert oats.nutrition.source == NutritionSource.BRAND_LABEL
    assert toor.nutrition.source == NutritionSource.IFCT_2017
    assert jam.nutrition.source == NutritionSource.CATEGORY_ESTIMATE


def test_weekly_targets_includes_extended_nutrients():
    """weekly_targets() now returns non-zero zinc, vitamin_b12 etc. from RDA table."""
    hh = fixture_household()
    targets = hh.weekly_targets()
    assert targets.zinc_mg > 0
    assert targets.magnesium_mg > 0
    assert targets.potassium_mg > 0
    assert targets.vitamin_a_mcg > 0
    assert targets.vitamin_c_mg > 0
    assert targets.folate_mcg > 0
    assert targets.vitamin_b12_mcg > 0


def test_missing_nutrients_report_covers_all_lines():
    """Basket.missing_nutrients_report() returns one tuple per (nutrient, sku)."""
    toor = get_sku("sku_toor_dal_tata_500g")
    oats = get_sku("sku_oats_quaker_1kg")
    assert toor is not None and oats is not None
    basket = Basket(
        household_id="hh",
        lines=[BasketLine(sku=toor, quantity=1), BasketLine(sku=oats, quantity=1)],
    )
    report = basket.missing_nutrients_report()
    # Both are plant foods → at minimum vitamin_b12_mcg missing for both
    assert len(report) >= 2
    nutrients = {nutrient for nutrient, _ in report}
    assert "vitamin_b12_mcg" in nutrients
    skus_with_missing = {sku_id for _, sku_id in report}
    assert "sku_toor_dal_tata_500g" in skus_with_missing


if __name__ == "__main__":
    tests = [
        test_household_excluded_tags_union,
        test_sku_compatibility_filtering,
        test_lactose_free_milk_bypasses_lactose_exclusion,
        test_weekly_targets_aggregation,
        test_nfi_overall_is_minimum_not_average,
        test_basket_nutrition_aggregation,
        test_estimated_provenance_propagates_to_basket,
        test_extended_nutrients_none_treated_as_zero_in_contribution,
        test_missing_positive_nutrients_returns_b12_for_plants,
        test_nfi_overall_unchanged_by_extended_nutrients,
        test_negative_totals_sums_correctly,
        test_negative_totals_tracks_missing_data,
        test_nutrition_source_enum_on_catalogue,
        test_weekly_targets_includes_extended_nutrients,
        test_missing_nutrients_report_covers_all_lines,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
