"""
Fixture household for demo and tests.

Composition rationale: this household is *deliberately* hard to cater to —
it forces the optimizer to handle every dietary axis we care about in v1
in a single test case.

  - Ramesh (38, M, moderate activity) — vegetarian
  - Priya (35, F, moderate activity) — vegetarian, lactose intolerant
  - Aarav (5, M, moderate activity) — vegetarian, peanut allergy
  - Kamala (62, F, sedentary) — vegetarian + Jain (no onion/garlic/roots)

Combined exclusions:
  - meat, fish, egg (vegetarian)
  - dairy lines must have lactose-free alternatives or be split
  - peanut excluded throughout (kid allergy)
  - onion, garlic, potato, ginger, carrot, etc. (MIL is Jain)

If the optimizer can build a balanced weekly basket for this household,
it will work for almost any real Bengaluru household.
"""

from datetime import date

from pantrypilot.models import (
    ActivityLevel,
    Allergy,
    DietaryPattern,
    Household,
    Member,
    PantryItem,
    Sex,
)


def fixture_household() -> Household:
    return Household(
        household_id="hh_demo_001",
        name="The Sharmas (demo household)",
        pincode="560001",
        weekly_budget_inr=2500,
        members=[
            Member(
                name="Ramesh Sharma",
                age=38,
                sex=Sex.MALE,
                weight_kg=72,
                activity=ActivityLevel.MODERATE,
                dietary_patterns=[DietaryPattern.VEGETARIAN],
                allergies=[],
            ),
            Member(
                name="Priya Sharma",
                age=35,
                sex=Sex.FEMALE,
                weight_kg=58,
                activity=ActivityLevel.MODERATE,
                dietary_patterns=[DietaryPattern.VEGETARIAN],
                allergies=[Allergy.LACTOSE],
            ),
            Member(
                name="Aarav Sharma",
                age=5,
                sex=Sex.MALE,
                weight_kg=18,
                activity=ActivityLevel.MODERATE,
                dietary_patterns=[DietaryPattern.VEGETARIAN],
                allergies=[Allergy.NUTS],
            ),
            Member(
                name="Kamala Sharma",
                age=62,
                sex=Sex.FEMALE,
                weight_kg=60,
                activity=ActivityLevel.SEDENTARY,
                dietary_patterns=[DietaryPattern.VEGETARIAN, DietaryPattern.JAIN],
                allergies=[],
            ),
        ],
    )


def fixture_pantry() -> list[PantryItem]:
    """
    A partially-stocked pantry — forces the optimizer to NOT re-order items
    the household already has plenty of, and to top up items that are low.
    """
    today = date.today()
    return [
        # Plenty of these — should NOT appear in this week's basket:
        PantryItem(sku_id="sku_atta_aashirvaad_5kg", quantity_g=4200, last_updated=today),
        PantryItem(sku_id="sku_basmati_indiagate_1kg", quantity_g=850, last_updated=today),
        PantryItem(sku_id="sku_oil_fortune_1l", quantity_g=720, last_updated=today),
        # Running low — basket SHOULD top up:
        PantryItem(sku_id="sku_toor_dal_tata_500g", quantity_g=80, last_updated=today),
        PantryItem(sku_id="sku_milk_lactose_free_1l", quantity_g=200, last_updated=today),
        # Empty — basket should restock if compatible:
        PantryItem(sku_id="sku_paneer_milky_mist_200g", quantity_g=0, last_updated=today),
    ]
