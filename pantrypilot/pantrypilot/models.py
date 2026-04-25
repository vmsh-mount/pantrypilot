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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


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
    Per-100g nutrition. Five nutrients in v1: enough to show the optimizer
    earning its keep without faking a 30-nutrient model.

    is_estimated: True when values came from category averages (e.g. "toor
    dal generic") rather than a verified per-brand source. Surfaces as an
    'estimated' badge in user UI and in the Swiggy demo.
    """

    calories_kcal: float
    protein_g: float
    fibre_g: float
    iron_mg: float
    calcium_mg: float
    is_estimated: bool = True
    source: str = "IFCT-2017 category average"


@dataclass
class NutrientTargets:
    """Weekly household nutrient targets, summed across members × 7."""

    calories_kcal: float
    protein_g: float
    fibre_g: float
    iron_mg: float
    calcium_mg: float

    def __add__(self, other: "NutrientTargets") -> "NutrientTargets":
        return NutrientTargets(
            calories_kcal=self.calories_kcal + other.calories_kcal,
            protein_g=self.protein_g + other.protein_g,
            fibre_g=self.fibre_g + other.fibre_g,
            iron_mg=self.iron_mg + other.iron_mg,
            calcium_mg=self.calcium_mg + other.calcium_mg,
        )

    def scale(self, factor: float) -> "NutrientTargets":
        return NutrientTargets(
            calories_kcal=self.calories_kcal * factor,
            protein_g=self.protein_g * factor,
            fibre_g=self.fibre_g * factor,
            iron_mg=self.iron_mg * factor,
            calcium_mg=self.calcium_mg * factor,
        )


# ICMR-NIN 2020 RDA reference values, simplified.
# Source: ICMR-NIN "Nutrient Requirements for Indians" (2020).
#
# CAVEAT for reviewers: this is a pragmatic v1 mapping. Real RDA tables
# have many more granular bands (pregnancy, lactation, age >60, activity
# tiers, etc.). Documented as a v1 simplification, not hidden.
_RDA_DAILY_REFERENCE = {
    ("male", "adult"): {
        "calories_kcal": 2110,
        "protein_g": 54,
        "fibre_g": 40,
        "iron_mg": 19,
        "calcium_mg": 1000,
    },
    ("female", "adult"): {
        "calories_kcal": 1660,
        "protein_g": 46,
        "fibre_g": 30,
        "iron_mg": 29,
        "calcium_mg": 1000,
    },
    ("male", "child_4_6"): {
        "calories_kcal": 1360,
        "protein_g": 20,
        "fibre_g": 22,
        "iron_mg": 11,
        "calcium_mg": 550,
    },
    ("female", "child_4_6"): {
        "calories_kcal": 1360,
        "protein_g": 20,
        "fibre_g": 22,
        "iron_mg": 11,
        "calcium_mg": 550,
    },
    ("female", "senior"): {
        "calories_kcal": 1500,
        "protein_g": 46,
        "fibre_g": 30,
        "iron_mg": 13,
        "calcium_mg": 1200,
    },
    ("male", "senior"): {
        "calories_kcal": 1900,
        "protein_g": 54,
        "fibre_g": 40,
        "iron_mg": 17,
        "calcium_mg": 1200,
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
        g = self.total_grams()
        n = self.sku.nutrition
        factor = g / 100.0
        return NutrientTargets(
            calories_kcal=n.calories_kcal * factor,
            protein_g=n.protein_g * factor,
            fibre_g=n.fibre_g * factor,
            iron_mg=n.iron_mg * factor,
            calcium_mg=n.calcium_mg * factor,
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


@dataclass
class NFIBreakdown:
    """
    Nutrition Fit Index — % of weekly target met, per nutrient and overall.
    Capped at 100 per nutrient (over-shooting protein doesn't compensate
    for missing iron). Overall is the *minimum* across nutrients, not the
    average — a basket with 100% protein and 30% iron is a 30% basket.
    This is a deliberate design choice: we surface the weakest nutrient,
    not paper over it.
    """

    protein_pct: float
    fibre_pct: float
    iron_pct: float
    calcium_pct: float
    calories_pct: float
    overall_pct: float
    contains_estimated: bool

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
        )
