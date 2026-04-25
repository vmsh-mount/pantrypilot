"""
PantryPilot domain models.

Implementation note: stdlib dataclasses, not pydantic. The domain layer
doesn't need runtime JSON validation — the FastAPI layer (step 4) will
add pydantic models at the API boundary if useful. Keeping the domain
pure-stdlib makes it trivially testable and removes a dependency the
core logic doesn't actually use.

Design notes:
- Nutrition values carry an `is_estimated` flag. SKU -> nutrition mapping
  for Indian groceries is a genuine v1 risk; we mark provenance honestly
  rather than pretending IFCT covers every brand-pack on Instamart.
- Jain dietary preference is a constraint *set*, not a boolean. Excluded
  ingredients live in DIETARY_EXCLUSIONS so the optimizer can reason about
  them per-SKU.
- Pantry inventory uses grams as the canonical unit. SKU pack sizes get
  normalized at ingestion time.
- Extended nutrients (zinc, magnesium, etc.) use Optional[float] = None.
  None means "data not available", NOT zero. A zero value is an accurate
  measurement; None is a gap we are honest about rather than papering over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    MODERATE = "moderate"
    HEAVY = "heavy"


class DietaryPattern(str, Enum):
    """
    Stacking semantics: a household member can be VEGETARIAN + JAIN, or
    VEGAN + JAIN. We resolve the union of exclusions at constraint time.
    """

    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    EGGETARIAN = "eggetarian"
    NON_VEG = "non_veg"
    JAIN = "jain"


class Allergy(str, Enum):
    LACTOSE = "lactose"
    GLUTEN = "gluten"
    NUTS = "nuts"
    SOY = "soy"


class SKUCategory(str, Enum):
    GRAIN = "grain"
    PULSE = "pulse"
    DAIRY = "dairy"
    PRODUCE_VEG = "produce_veg"
    PRODUCE_FRUIT = "produce_fruit"
    OIL = "oil"
    SPICE = "spice"
    OTHER = "other"


class NutritionSource(str, Enum):
    """Provenance of per-100g nutrition values for a SKU."""

    IFCT_2017 = "IFCT_2017"           # Indian Food Composition Tables 2017 (per-ingredient)
    BRAND_LABEL = "brand_label"       # Verified from branded pack label
    CATEGORY_ESTIMATE = "category_estimate"  # Generic category average — lowest confidence


# ---------------------------------------------------------------------------
# Constants — dietary exclusions and ICMR-NIN RDAs
# ---------------------------------------------------------------------------

JAIN_EXCLUDED_TAGS = {
    "onion",
    "garlic",
    "potato",
    "ginger",
    "carrot",
    "radish",
    "beetroot",
    "sweet_potato",
}

VEGAN_EXCLUDED_TAGS = {"dairy", "egg", "honey", "meat", "fish"}
VEGETARIAN_EXCLUDED_TAGS = {"meat", "fish", "egg"}
EGGETARIAN_EXCLUDED_TAGS = {"meat", "fish"}

ALLERGY_EXCLUDED_TAGS = {
    Allergy.LACTOSE: {"dairy"},
    Allergy.GLUTEN: {"wheat", "barley"},
    Allergy.NUTS: {"peanut", "almond", "cashew", "walnut"},
    Allergy.SOY: {"soy"},
}


# ---------------------------------------------------------------------------
# Nutrition
# ---------------------------------------------------------------------------


@dataclass
class NutritionPer100g:
    """
    Per-100g nutrition. Five core nutrients drive the CP-SAT optimizer.
    Seven extended positives and four negatives are for display only in v1.

    None = unknown (NOT zero). A SKU with sodium_mg=None has unknown sodium
    content. The UI surfaces a data-gap warning, not a zero reading.

    Sources of truth, in order of confidence:
      BRAND_LABEL      — copied from branded pack label
      IFCT_2017        — Indian Food Composition Tables 2017
      CATEGORY_ESTIMATE — generic category average; flag in UI
    """

    # Core positives (required; these five drive the optimizer)
    calories_kcal: float
    protein_g: float
    fibre_g: float
    iron_mg: float
    calcium_mg: float

    # Extended positives (None = data gap, not zero)
    zinc_mg: Optional[float] = None
    magnesium_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    vitamin_a_mcg: Optional[float] = None   # Retinol Activity Equivalents
    vitamin_c_mg: Optional[float] = None
    folate_mcg: Optional[float] = None      # Dietary Folate Equivalents
    vitamin_b12_mcg: Optional[float] = None

    # Negatives (None = data gap)
    sodium_mg: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    added_sugar_g: Optional[float] = None
    ultra_processed: bool = False

    # Provenance
    is_estimated: bool = True
    source: NutritionSource = NutritionSource.CATEGORY_ESTIMATE


# Attribute names for the seven extended positive nutrients, in display order.
# Used by BasketLine.missing_positive_nutrients() and NFIBreakdown.
_EXTENDED_POSITIVE_ATTRS: list[str] = [
    "zinc_mg",
    "magnesium_mg",
    "potassium_mg",
    "vitamin_a_mcg",
    "vitamin_c_mg",
    "folate_mcg",
    "vitamin_b12_mcg",
]


@dataclass
class NegativeTotals:
    """
    Weekly basket totals for negative nutrients. For display only — the
    optimizer does not penalise negatives in v1 (display-first approach).
    """

    sodium_mg: float
    saturated_fat_g: float
    added_sugar_g: float
    ultra_processed_count: int       # number of basket lines with ultra_processed=True
    sodium_missing_lines: int        # lines where sodium_mg was None
    saturated_fat_missing_lines: int
    added_sugar_missing_lines: int


@dataclass
class NutrientTargets:
    """Weekly household nutrient targets, summed across members × 7."""

    # Core (required positional args; the optimizer reads these)
    calories_kcal: float
    protein_g: float
    fibre_g: float
    iron_mg: float
    calcium_mg: float

    # Extended (default 0.0 for backward compat with positional constructor calls)
    zinc_mg: float = 0.0
    magnesium_mg: float = 0.0
    potassium_mg: float = 0.0
    vitamin_a_mcg: float = 0.0
    vitamin_c_mg: float = 0.0
    folate_mcg: float = 0.0
    vitamin_b12_mcg: float = 0.0

    def __add__(self, other: "NutrientTargets") -> "NutrientTargets":
        return NutrientTargets(
            calories_kcal=self.calories_kcal + other.calories_kcal,
            protein_g=self.protein_g + other.protein_g,
            fibre_g=self.fibre_g + other.fibre_g,
            iron_mg=self.iron_mg + other.iron_mg,
            calcium_mg=self.calcium_mg + other.calcium_mg,
            zinc_mg=self.zinc_mg + other.zinc_mg,
            magnesium_mg=self.magnesium_mg + other.magnesium_mg,
            potassium_mg=self.potassium_mg + other.potassium_mg,
            vitamin_a_mcg=self.vitamin_a_mcg + other.vitamin_a_mcg,
            vitamin_c_mg=self.vitamin_c_mg + other.vitamin_c_mg,
            folate_mcg=self.folate_mcg + other.folate_mcg,
            vitamin_b12_mcg=self.vitamin_b12_mcg + other.vitamin_b12_mcg,
        )

    def scale(self, factor: float) -> "NutrientTargets":
        return NutrientTargets(
            calories_kcal=self.calories_kcal * factor,
            protein_g=self.protein_g * factor,
            fibre_g=self.fibre_g * factor,
            iron_mg=self.iron_mg * factor,
            calcium_mg=self.calcium_mg * factor,
            zinc_mg=self.zinc_mg * factor,
            magnesium_mg=self.magnesium_mg * factor,
            potassium_mg=self.potassium_mg * factor,
            vitamin_a_mcg=self.vitamin_a_mcg * factor,
            vitamin_c_mg=self.vitamin_c_mg * factor,
            folate_mcg=self.folate_mcg * factor,
            vitamin_b12_mcg=self.vitamin_b12_mcg * factor,
        )


# ICMR-NIN 2020 RDA reference values.
# Source: ICMR-NIN "Nutrient Requirements for Indians" (2020).
#
# CAVEAT for reviewers: pragmatic v1 mapping. Real tables have more bands
# (pregnancy, lactation, activity tiers, etc.). Documented simplification.
_RDA_DAILY_REFERENCE = {
    ("male", "adult"): {
        "calories_kcal": 2110,
        "protein_g": 54,
        "fibre_g": 40,
        "iron_mg": 19,
        "calcium_mg": 1000,
        "zinc_mg": 12.0,
        "magnesium_mg": 340.0,
        "potassium_mg": 3750.0,
        "vitamin_a_mcg": 800.0,
        "vitamin_c_mg": 80.0,
        "folate_mcg": 200.0,
        "vitamin_b12_mcg": 2.2,
    },
    ("female", "adult"): {
        "calories_kcal": 1660,
        "protein_g": 46,
        "fibre_g": 30,
        "iron_mg": 29,
        "calcium_mg": 1000,
        "zinc_mg": 10.0,
        "magnesium_mg": 310.0,
        "potassium_mg": 3750.0,
        "vitamin_a_mcg": 600.0,
        "vitamin_c_mg": 65.0,
        "folate_mcg": 200.0,
        "vitamin_b12_mcg": 2.2,
    },
    ("male", "child_4_6"): {
        "calories_kcal": 1360,
        "protein_g": 20,
        "fibre_g": 22,
        "iron_mg": 11,
        "calcium_mg": 550,
        "zinc_mg": 5.0,
        "magnesium_mg": 120.0,
        "potassium_mg": 1500.0,
        "vitamin_a_mcg": 400.0,
        "vitamin_c_mg": 40.0,
        "folate_mcg": 80.0,
        "vitamin_b12_mcg": 0.9,
    },
    ("female", "child_4_6"): {
        "calories_kcal": 1360,
        "protein_g": 20,
        "fibre_g": 22,
        "iron_mg": 11,
        "calcium_mg": 550,
        "zinc_mg": 5.0,
        "magnesium_mg": 120.0,
        "potassium_mg": 1500.0,
        "vitamin_a_mcg": 400.0,
        "vitamin_c_mg": 40.0,
        "folate_mcg": 80.0,
        "vitamin_b12_mcg": 0.9,
    },
    ("female", "senior"): {
        "calories_kcal": 1500,
        "protein_g": 46,
        "fibre_g": 30,
        "iron_mg": 13,
        "calcium_mg": 1200,
        "zinc_mg": 10.0,
        "magnesium_mg": 310.0,
        "potassium_mg": 3750.0,
        "vitamin_a_mcg": 600.0,
        "vitamin_c_mg": 65.0,
        "folate_mcg": 200.0,
        "vitamin_b12_mcg": 2.4,
    },
    ("male", "senior"): {
        "calories_kcal": 1900,
        "protein_g": 54,
        "fibre_g": 40,
        "iron_mg": 17,
        "calcium_mg": 1200,
        "zinc_mg": 12.0,
        "magnesium_mg": 340.0,
        "potassium_mg": 3750.0,
        "vitamin_a_mcg": 800.0,
        "vitamin_c_mg": 80.0,
        "folate_mcg": 200.0,
        "vitamin_b12_mcg": 2.4,
    },
}

_ACTIVITY_MULTIPLIER = {
    ActivityLevel.SEDENTARY: 1.0,
    ActivityLevel.MODERATE: 1.2,
    ActivityLevel.HEAVY: 1.5,
}


def _age_band(age: int) -> str:
    if age <= 6:
        return "child_4_6"
    if age >= 60:
        return "senior"
    return "adult"


# ---------------------------------------------------------------------------
# Household
# ---------------------------------------------------------------------------


@dataclass
class Member:
    name: str
    age: int
    sex: Sex
    weight_kg: float
    activity: ActivityLevel
    dietary_patterns: list[DietaryPattern]
    allergies: list[Allergy] = field(default_factory=list)

    def daily_rda(self) -> NutrientTargets:
        band = _age_band(self.age)
        key = (self.sex.value, band)
        ref = _RDA_DAILY_REFERENCE.get(key)
        if ref is None:
            ref = _RDA_DAILY_REFERENCE[(self.sex.value, "adult")]
        mult = _ACTIVITY_MULTIPLIER[self.activity]
        # Only calories scale strongly with activity; micronutrients don't.
        return NutrientTargets(
            calories_kcal=ref["calories_kcal"] * mult,
            protein_g=ref["protein_g"],
            fibre_g=ref["fibre_g"],
            iron_mg=ref["iron_mg"],
            calcium_mg=ref["calcium_mg"],
            zinc_mg=ref["zinc_mg"],
            magnesium_mg=ref["magnesium_mg"],
            potassium_mg=ref["potassium_mg"],
            vitamin_a_mcg=ref["vitamin_a_mcg"],
            vitamin_c_mg=ref["vitamin_c_mg"],
            folate_mcg=ref["folate_mcg"],
            vitamin_b12_mcg=ref["vitamin_b12_mcg"],
        )

    def excluded_tags(self) -> set[str]:
        """Union of ingredient tags this member cannot eat."""
        excluded: set[str] = set()
        for pattern in self.dietary_patterns:
            if pattern == DietaryPattern.JAIN:
                excluded |= JAIN_EXCLUDED_TAGS
            elif pattern == DietaryPattern.VEGAN:
                excluded |= VEGAN_EXCLUDED_TAGS
            elif pattern == DietaryPattern.VEGETARIAN:
                excluded |= VEGETARIAN_EXCLUDED_TAGS
            elif pattern == DietaryPattern.EGGETARIAN:
                excluded |= EGGETARIAN_EXCLUDED_TAGS
        for allergy in self.allergies:
            excluded |= ALLERGY_EXCLUDED_TAGS.get(allergy, set())
        return excluded


@dataclass
class Household:
    household_id: str
    name: str
    members: list[Member]
    weekly_budget_inr: int
    pincode: str

    def weekly_targets(self) -> NutrientTargets:
        """Sum daily RDAs across members, ×7 for the week."""
        total = NutrientTargets(0, 0, 0, 0, 0)
        for m in self.members:
            total = total + m.daily_rda()
        return total.scale(7.0)

    def excluded_tags(self) -> set[str]:
        """
        Household excludes any tag any member excludes (strictest wins).

        v1 SIMPLIFICATION (intentional, documented for reviewers):
        In a real household, if Priya is lactose-intolerant but Ramesh
        isn't, the basket might still contain regular milk for Ramesh
        AND lactose-free milk for Priya. The right model is per-member
        consumption shares with per-member feasibility.

        We chose strictest-wins for v1 because:
          (a) it never produces an incorrect basket — at worst it's
              overly cautious;
          (b) it cuts the constraint surface roughly in half for the
              optimizer;
          (c) the upgrade path (per-member shares) is clean and additive.

        v2 design: each Member gets a `consumption_share` (default 1/N),
        SKUs get evaluated per-member, and the basket's per-member
        nutrition contribution is weighted by share.
        """
        result: set[str] = set()
        for m in self.members:
            result |= m.excluded_tags()
        return result


# ---------------------------------------------------------------------------
# Pantry
# ---------------------------------------------------------------------------


@dataclass
class PantryItem:
    """
    Current pantry stock for a household. Quantity in grams (or ml-as-grams
    for liquids; v1 doesn't separate density). Decremented by an estimated
    weekly consumption model post-order.
    """

    sku_id: str
    quantity_g: float
    last_updated: date


# ---------------------------------------------------------------------------
# SKU
# ---------------------------------------------------------------------------


@dataclass
class SKU:
    """
    A single Instamart product. In production, sourced from the MCP
    catalogue tool; in the demo, mocked from fixtures/instamart_catalogue.py.
    """

    sku_id: str
    name: str
    brand: str
    category: SKUCategory
    pack_size_g: float
    price_inr: float
    nutrition: NutritionPer100g
    in_stock: bool = True
    ingredient_tags: set[str] = field(default_factory=set)

    def is_compatible_with(self, household: Household) -> bool:
        return self.ingredient_tags.isdisjoint(household.excluded_tags())

    def price_per_100g(self) -> float:
        return self.price_inr * 100.0 / self.pack_size_g


# ---------------------------------------------------------------------------
# Basket
# ---------------------------------------------------------------------------


@dataclass
class BasketLine:
    sku: SKU
    quantity: int  # number of packs
    reason: str = ""  # per-item optimizer explanation (set post-solve)

    def total_price_inr(self) -> float:
        return self.sku.price_inr * self.quantity

    def total_grams(self) -> float:
        return self.sku.pack_size_g * self.quantity

    def nutrition_contribution(self) -> NutrientTargets:
        """
        Contribution to weekly NutrientTargets from this basket line.
        Extended nutrients with None values contribute 0.0 (data gap,
        not a true zero). Use missing_positive_nutrients() to identify gaps.
        """
        g = self.total_grams()
        n = self.sku.nutrition
        factor = g / 100.0
        return NutrientTargets(
            calories_kcal=n.calories_kcal * factor,
            protein_g=n.protein_g * factor,
            fibre_g=n.fibre_g * factor,
            iron_mg=n.iron_mg * factor,
            calcium_mg=n.calcium_mg * factor,
            zinc_mg=(n.zinc_mg or 0.0) * factor,
            magnesium_mg=(n.magnesium_mg or 0.0) * factor,
            potassium_mg=(n.potassium_mg or 0.0) * factor,
            vitamin_a_mcg=(n.vitamin_a_mcg or 0.0) * factor,
            vitamin_c_mg=(n.vitamin_c_mg or 0.0) * factor,
            folate_mcg=(n.folate_mcg or 0.0) * factor,
            vitamin_b12_mcg=(n.vitamin_b12_mcg or 0.0) * factor,
        )

    def missing_positive_nutrients(self) -> list[str]:
        """Returns extended nutrient attribute names where the SKU has None values."""
        n = self.sku.nutrition
        return [attr for attr in _EXTENDED_POSITIVE_ATTRS if getattr(n, attr) is None]

    def negative_contribution(self) -> tuple[float, float, float, bool]:
        """Returns (sodium_mg, saturated_fat_g, added_sugar_g, ultra_processed) per line."""
        g = self.total_grams()
        n = self.sku.nutrition
        factor = g / 100.0
        return (
            (n.sodium_mg or 0.0) * factor,
            (n.saturated_fat_g or 0.0) * factor,
            (n.added_sugar_g or 0.0) * factor,
            n.ultra_processed,
        )


@dataclass
class Basket:
    household_id: str
    lines: list[BasketLine]

    def total_price_inr(self) -> float:
        return sum(line.total_price_inr() for line in self.lines)

    def total_nutrition(self) -> NutrientTargets:
        total = NutrientTargets(0, 0, 0, 0, 0)
        for line in self.lines:
            total = total + line.nutrition_contribution()
        return total

    def has_estimated_nutrition(self) -> bool:
        """If any line has estimated nutrition, the NFI score must be badged."""
        return any(line.sku.nutrition.is_estimated for line in self.lines)

    def negative_totals(self) -> NegativeTotals:
        """Aggregate negative nutrients across all basket lines."""
        sodium = saturated_fat = added_sugar = 0.0
        up_count = na_sodium = na_sat = na_sugar = 0
        for line in self.lines:
            n = line.sku.nutrition
            g = line.total_grams()
            factor = g / 100.0
            if n.sodium_mg is None:
                na_sodium += 1
            else:
                sodium += n.sodium_mg * factor
            if n.saturated_fat_g is None:
                na_sat += 1
            else:
                saturated_fat += n.saturated_fat_g * factor
            if n.added_sugar_g is None:
                na_sugar += 1
            else:
                added_sugar += n.added_sugar_g * factor
            if n.ultra_processed:
                up_count += 1
        return NegativeTotals(
            sodium_mg=sodium,
            saturated_fat_g=saturated_fat,
            added_sugar_g=added_sugar,
            ultra_processed_count=up_count,
            sodium_missing_lines=na_sodium,
            saturated_fat_missing_lines=na_sat,
            added_sugar_missing_lines=na_sugar,
        )

    def missing_nutrients_report(self) -> list[tuple[str, str]]:
        """Returns (nutrient_attr, sku_id) pairs where extended nutrition is unknown."""
        result: list[tuple[str, str]] = []
        for line in self.lines:
            for attr in line.missing_positive_nutrients():
                result.append((attr, line.sku.sku_id))
        return result


@dataclass
class NFIBreakdown:
    """
    Nutrition Fit Index — % of weekly target met, per nutrient and overall.
    Capped at 100 per nutrient (over-shooting protein doesn't compensate
    for missing iron). Overall is the *minimum* across the core five
    nutrients, not the average — a basket with 100% protein and 30% iron
    is a 30% basket. This surfaces the weakest nutrient, not papers over it.

    Extended nutrient pcts are informational; they do NOT affect overall_pct.
    overall_pct = min(protein, fibre, iron, calcium, calories) only.
    """

    # Core five (drive overall_pct)
    protein_pct: float
    fibre_pct: float
    iron_pct: float
    calcium_pct: float
    calories_pct: float
    overall_pct: float
    contains_estimated: bool

    # Extended positives (display only; default 0.0)
    zinc_pct: float = 0.0
    magnesium_pct: float = 0.0
    potassium_pct: float = 0.0
    vitamin_a_pct: float = 0.0
    vitamin_c_pct: float = 0.0
    folate_pct: float = 0.0
    vitamin_b12_pct: float = 0.0

    @classmethod
    def compute(
        cls,
        basket_nutrition: NutrientTargets,
        target: NutrientTargets,
        estimated: bool,
    ) -> "NFIBreakdown":
        def pct(actual: float, goal: float) -> float:
            if goal == 0:
                return 100.0
            return min(100.0, 100.0 * actual / goal)

        protein = pct(basket_nutrition.protein_g, target.protein_g)
        fibre = pct(basket_nutrition.fibre_g, target.fibre_g)
        iron = pct(basket_nutrition.iron_mg, target.iron_mg)
        calcium = pct(basket_nutrition.calcium_mg, target.calcium_mg)
        calories = pct(basket_nutrition.calories_kcal, target.calories_kcal)
        return cls(
            protein_pct=protein,
            fibre_pct=fibre,
            iron_pct=iron,
            calcium_pct=calcium,
            calories_pct=calories,
            overall_pct=min(protein, fibre, iron, calcium, calories),
            contains_estimated=estimated,
            zinc_pct=pct(basket_nutrition.zinc_mg, target.zinc_mg),
            magnesium_pct=pct(basket_nutrition.magnesium_mg, target.magnesium_mg),
            potassium_pct=pct(basket_nutrition.potassium_mg, target.potassium_mg),
            vitamin_a_pct=pct(basket_nutrition.vitamin_a_mcg, target.vitamin_a_mcg),
            vitamin_c_pct=pct(basket_nutrition.vitamin_c_mg, target.vitamin_c_mg),
            folate_pct=pct(basket_nutrition.folate_mcg, target.folate_mcg),
            vitamin_b12_pct=pct(basket_nutrition.vitamin_b12_mcg, target.vitamin_b12_mcg),
        )
