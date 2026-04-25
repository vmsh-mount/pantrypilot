# Design: Domain Model

**File:** `pantrypilot/pantrypilot/models.py`

---

## Purpose

Defines the core types that flow through the entire pipeline: household configuration, nutritional targets, SKU catalogue entries, pantry state, basket construction, and the NFI score. Everything downstream — the optimizer, the planner, the API — depends on these types.

---

## Type inventory

| Type | Role |
|---|---|
| `Member` | Person with age, sex, activity, dietary patterns, allergies |
| `Household` | Container: members + weekly budget + pincode |
| `NutritionPer100g` | Five nutrients + provenance flags |
| `NutrientTargets` | Summed weekly targets; supports `+` and `scale()` |
| `SKU` | Instamart product with ingredient tags and nutrition |
| `PantryItem` | Current stock for one SKU, in grams |
| `BasketLine` | One line in an order: SKU + pack count |
| `Basket` | Collection of lines with cost and nutrition methods |
| `NFIBreakdown` | Per-nutrient % coverage and overall (min) score |

---

## Design decisions

### Stdlib dataclasses, not pydantic

The domain layer doesn't touch JSON or HTTP. Pydantic's value — runtime validation and schema generation — only becomes relevant at the FastAPI boundary (step 4). Using stdlib dataclasses keeps the core logic dependency-free and trivially testable.

When step 4 adds FastAPI, pydantic models live in the API layer and convert to/from domain types at the boundary. The domain types stay unchanged.

### Ingredient tags as `set[str]`, not enums

Tags like `"dairy"`, `"onion"`, `"peanut"` are string sets on `SKU.ingredient_tags`. This was a deliberate choice over enums:

- It allows `"dairy_lactose_free"` as a distinct tag that bypasses the `"dairy"` exclusion. An enum would require an explicit allow-list entry for every dietary bypass.
- The tag vocabulary is defined by the catalogue, not by the domain model. New tags just work without schema changes.
- The tradeoff: tag consistency is a runtime concern. If a catalogue entry uses `"onions"` instead of `"onion"`, the filter silently passes. The catalogue is the single source of truth — typos there break filtering.

### Strictest-wins household exclusion

`Household.excluded_tags()` takes the union of all member exclusions. If Kamala (Jain) excludes onions, the whole household basket excludes onions — even if the other three members have no objection.

**Why:** It's the only approach that is never incorrect. A "members vote" model could produce a basket containing ingredients some members genuinely cannot eat.

**The acknowledged cost:** A household where one member is Jain and three are not cannot have the agent suggest onion-based dishes for the non-Jain members. The basket is overcautious. For v1 where the basket is a single shared order, this is the right call.

**V2 upgrade path:** Per-member consumption shares. Each `Member` gets a `consumption_share` (default 1/N). The optimizer evaluates SKU compatibility per-member and weights nutrition contributions by share. This path is documented in the `Household.excluded_tags()` docstring.

### Weekly targets = sum of individual daily RDAs × 7

The household target is not a "household RDA" concept — it's the arithmetic sum of each member's individual daily requirements multiplied by seven. This matters because:

- A family of four has very different targets than four individuals: Aarav (5yo) contributes much less than Kamala (62F, 1200mg Ca/day).
- Per-member aggregation is honest about who needs what. The optimizer then finds a basket that collectively covers all of them.
- Activity level scales calories only. Micronutrient RDAs don't vary with activity in the ICMR-NIN 2020 tables.

---

## Implementation notes

**`_age_band(age)`** maps an integer age to an RDA table key (`"child_4_6"`, `"adult"`, `"senior"`). Ages 0–6 use the child band; ≥60 uses senior; everything else is adult. This is an explicit v1 simplification — the real ICMR-NIN tables have more granular bands, but the five we have cover the Sharma household.

**`Member.excluded_tags()`** is the per-member version of the household union. It iterates `dietary_patterns` and `allergies`, looking each up in the appropriate constant (`JAIN_EXCLUDED_TAGS`, `ALLERGY_EXCLUDED_TAGS`, etc.). Both the dietary-pattern and allergy constants are defined at module level and imported nowhere else.

**`SKU.is_compatible_with(household)`** is a one-liner: `self.ingredient_tags.isdisjoint(household.excluded_tags())`. This is the hot path for pre-filtering the catalogue before optimization.

**`BasketLine.nutrition_contribution()`** normalises by dividing by 100g: `per_100g × (pack_size_g × quantity) / 100`. The result is a `NutrientTargets` that can be summed with `+`.

---

## For future contributors

**Adding a new dietary pattern** (e.g. Sattvic): add a variant to `DietaryPattern`, define `SATTVIC_EXCLUDED_TAGS` at module level, and handle it in `Member.excluded_tags()`. Update the fixture catalogue with appropriate tags on affected SKUs. Add a test to `test_models.py` covering the new exclusion.

**Adding a new allergen**: add a variant to `Allergy`, add it to `ALLERGY_EXCLUDED_TAGS` with the relevant tag set, add a test.

**Adding nutrients** (v2): add fields to `NutritionPer100g` and `NutrientTargets`, extend `_RDA_DAILY_REFERENCE` entries, update `NFIBreakdown.compute()` to include the new nutrient in the `min()` call. The optimizer picks up new nutrients automatically via the `NUTRIENTS` list in `optimizer.py`.

**Pydantic boundary**: When FastAPI is added (step 4), define `HouseholdRequest`, `BasketResponse`, etc. as pydantic models. Convert from/to domain types at the route handler level. Never put pydantic in `models.py`.
