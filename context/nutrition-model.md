# Nutrition Model

## Overview

PantryPilot tracks **12 positive nutrients** and **4 negative nutrients** per SKU, mapped to ICMR-NIN 2020 recommended dietary allowances (RDAs) per household member.

## Positive nutrients

### Core 5 — optimizer constraints

These enter the CP-SAT objective. The basket must meet ≥ 80% of weekly household targets for the optimizer to consider a solution feasible (soft constraint via maximising the minimum coverage).

| Field | Unit | Notes |
|-------|------|-------|
| `calories_kcal` | kcal | From ICMR-NIN PAL × BMR |
| `protein_g` | g | 0.83 g/kg body weight (ICMR-NIN) |
| `dietary_fibre_g` | g | 40 g/day adult |
| `iron_mg` | mg | Higher for premenopausal women (21 mg vs 17 mg) |
| `calcium_mg` | mg | 1000 mg/day adults; 800 mg children |

### Extended 7 — display only

These are shown in the plan page's "Extended nutrients" grid. They do **not** affect the optimizer objective or the overall NFI score.

| Field | Unit | Adult RDA (ICMR-NIN 2020) |
|-------|------|---------------------------|
| `zinc_mg` | mg | 12 mg (M) / 10 mg (F) |
| `magnesium_mg` | mg | 340 mg (M) / 310 mg (F) |
| `potassium_mg` | mg | 3750 mg |
| `vitamin_a_mcg` | µg RAE | 800–1000 µg |
| `vitamin_c_mg` | mg | 80 mg (M) / 65 mg (F) |
| `folate_mcg` | µg DFE | 200 µg |
| `vitamin_b12_mcg` | µg | 2.2 µg |

`None` = data gap (source not available). Displayed as "? data gap". Never treated as zero.

## Negative nutrients — watch limits

Shown in the "Watch — limit these" panel. Bars turn amber at 90%, red at 100% of ceiling.

| Field | Ceiling | Source |
|-------|---------|--------|
| `sodium_mg` | 2000 mg/person/day × members × 7 | WHO 2012 |
| `saturated_fat_g` | 10% of weekly household kcal ÷ 9 | ICMR-NIN |
| `added_sugar_g` | 25 g/person/day × adults × 7 | WHO free-sugar guideline |
| `ultra_processed` | bool flag | Count shown; no hard ceiling |

## Nutrition source provenance

Every SKU's nutrition data carries a `NutritionSource` enum:

| Value | Meaning |
|-------|---------|
| `IFCT_2017` | Indian Food Composition Tables 2017 — highest confidence |
| `BRAND_LABEL` | Manufacturer's declared values |
| `CATEGORY_ESTIMATE` | Category-average estimate — lowest confidence |

Displayed as badges in the server-rendered basket page.

## RDA table coverage

`Member.daily_rda()` resolves all 12 fields from a lookup keyed by `(sex, age_band)`:

| Age band | Notes |
|----------|-------|
| child (< 10) | Lower targets across all nutrients |
| adolescent (10–17) | Higher iron for females |
| adult (18–59) | Standard ICMR-NIN adult values |
| senior (≥ 60) | Slightly reduced calorie targets |

Weekly household target = sum of `daily_rda() × 7` across all members.
