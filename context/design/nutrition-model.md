# Design: Nutrition Model

**Files:** `pantrypilot/pantrypilot/models.py` — `NutritionPer100g`, `NutrientTargets`, `NFIBreakdown`, `_RDA_DAILY_REFERENCE`

---

## Purpose

Define what "nutritional adequacy" means for an Indian household. This includes: which nutrients to track, what the weekly targets are for different household members, how to score a basket against those targets, and how to communicate confidence in the underlying data.

---

## Nutrients tracked in v1

Five nutrients: **calories, protein, fibre, iron, calcium**.

This is a deliberate subset, not the full picture. Rationale:

- Enough to show the optimizer earning its keep on a realistic constraint (calcium is genuinely hard for a dairy-excluded household).
- Avoids faking a 30-nutrient model where most values would be category averages anyway.
- A meaningful improvement on the zero nutritional consideration in a standard grocery basket.

Nutrients not tracked in v1 (with upgrade notes):
- **Vitamin B12**: critical for vegetarians; needs brand-level supplement data
- **Vitamin D**: almost entirely sun-derived; food contribution marginal
- **Omega-3**: relevant but IFCT coverage is poor; would increase estimated-flag rate
- **Zinc**: tracked in ICMR-NIN but IFCT values have wide variance for Indian foods

---

## ICMR-NIN 2020 RDA reference

Source: *Nutrient Requirements for Indians*, ICMR-NIN, 2020. The authoritative Indian nutrition reference.

**V1 implementation covers five age/sex bands:**

| Band | Key |
|---|---|
| Adult male (19–59) | `("male", "adult")` |
| Adult female (19–59) | `("female", "adult")` |
| Child 4–6 | `("male"/"female", "child_4_6")` |
| Senior male (≥60) | `("male", "senior")` |
| Senior female (≥60) | `("female", "senior")` |

**Activity multiplier** applies to calories only, not micronutrients:
- Sedentary: 1.0×
- Moderate: 1.2×
- Heavy: 1.5×

**V1 simplifications** (documented, not hidden):
- No pregnancy or lactation bands (would require explicit `Member` fields)
- No granular age bands (7–9, 10–12, 13–15, etc.) — the child_4_6 band is used for all under-7
- Ages 7–18 fall to the adult band, which slightly overestimates requirements for younger children
- No separate obesity/underweight adjustment

---

## NFI — Nutrition Fit Index

### Per-nutrient coverage

```
coverage(n) = min(100%, 100 × actual(n) / target(n))
```

Coverage is capped at 100% per nutrient. Exceeding the protein target does not compensate for missing calcium.

### Overall NFI

```
NFI_overall = min(coverage(n) for all n)
```

**Why minimum, not average:** A basket with 100% protein and 30% calcium is a 30% basket, not a 65% basket. The minimum surfaces the gap. Averaging would hide it and the household would not know they have a calcium problem. This is a deliberate, documented product decision — it is less flattering but more honest.

### Estimation flag

```
NFI.contains_estimated = any(line.sku.nutrition.is_estimated for line in basket.lines)
```

If any line in the basket uses estimated nutrition values, the entire NFI score is badged as estimated. A basket cannot be claimed to be "exactly 94% of your iron target" if the iron values come from a category average.

---

## Nutrition provenance

Every `NutritionPer100g` carries:

```python
is_estimated: bool = True
source: str = "IFCT-2017 category average"
```

**`is_estimated = True`** (default): values come from IFCT-2017 category averages (e.g. "toor dal generic"). Accurate to within 10–20% for most nutrients for mainstream products.

**`is_estimated = False`**: values come from a specific product's packaging label (e.g. Quaker Oats, Amul Toned Milk). Accurate to within label rounding.

In demo output, estimated items are prefixed with `~`. The intent is to make the limitation visible rather than presenting a false precision.

### The SKU-to-nutrition mapping problem

This is the acknowledged v1 risk. In production, the Instamart MCP catalogue returns product names and brands, not structured nutrition data. Mapping from "Tata Sampann Toor Dal 500g" to its IFCT entry is a lookup problem with several failure modes:

- Brand formulations differ from IFCT averages (fortified products, processing differences)
- New products have no IFCT entry at all
- Pack size affects nutrition (per-100g is fine; per-pack is derived from it)

V2 approach: OCR of packaging labels at catalogue ingestion time, structured against Open Food Facts India database, falling back to IFCT category averages with `is_estimated = True`.

---

## Food databases

| Database | Coverage | Accuracy | Notes |
|---|---|---|---|
| IFCT-2017 | Good for Indian staples | Category-level | Primary v1 source |
| USDA FCD | Broad but US-centric | Generally good | Fallback for non-Indian items |
| Open Food Facts | Brand-level | Label-accurate | Sparse India coverage today |

---

## For future contributors

**Adding a nutrient**: Add field to `NutritionPer100g` and `NutrientTargets`. Add entries to all five bands in `_RDA_DAILY_REFERENCE`. Extend `NFIBreakdown` with a new `_pct` field and update `compute()` to include it in the `min()`. Update all fixture nutrition values. Add to `NUTRIENTS` in `optimizer.py`.

**Adding an age band** (e.g. child 7–9): Add a new `_RDA_DAILY_REFERENCE` key like `("male", "child_7_9")`, update `_age_band()` to route to it. Existing tests won't break — the Sharma household's child (Aarav, 5) stays on `child_4_6`.

**Pregnancy/lactation**: Requires an explicit `Member` field (e.g. `life_stage: LifeStage = LifeStage.NORMAL`). The RDA lookup in `Member.daily_rda()` would incorporate life stage alongside sex and age band.
