"""
Mock Instamart catalogue — ~67 SKUs.

In production this comes from the Instamart MCP catalogue tool. Here it's
a hand-curated list that:

  1. Covers the categories a vegetarian Bengaluru household actually buys.
  2. Includes deliberate dietary tripwires (onion-garlic masala, potato
     chips, paneer) so the dietary-filter step has real work to do for
     the Jain MIL in the fixture household.
  3. Includes multiple protein sources at meaningfully different
     cost-per-gram-of-protein, so the optimizer's budget-vs-nutrition
     trade-off is visible.
  4. NEW in v2: micronutrient-dense additions (ragi, sesame, amla, etc.)
     that exercise the extended 12-nutrient model.
  5. NEW in v2: high-sodium and high-added-sugar items that are COMPATIBLE
     with the Sharma household (no onion/garlic/dairy/nuts) so the optimizer
     faces real tension between nutritional density and negative nutrients.
  6. NEW in v2: ultra-processed items, both compatible (trackers for the
     negative panel) and incompatible (Maggi, frozen momos).

Nutrition values: IFCT-2017 for unbranded Indian whole foods; BRAND_LABEL
for a handful of branded packs where we have verified label data; elsewhere
CATEGORY_ESTIMATE. None for nutrients that are unknown (not zero).

Prices reflect rough Bengaluru Instamart range as of early 2026.

Compatible SKUs for hh_demo_001 (Sharmas): 54
Filtered-out SKUs for hh_demo_001: 13
Total: 67
"""

from typing import Optional

from pantrypilot.models import NutritionPer100g, NutritionSource, SKU, SKUCategory

_CE = NutritionSource.CATEGORY_ESTIMATE
_IF = NutritionSource.IFCT_2017
_BL = NutritionSource.BRAND_LABEL


def _nutr(
    cal: float,
    prot: float,
    fib: float,
    iron: float,
    cal_mg: float,
    *,
    # Extended positives (None = data gap, not zero)
    zinc: Optional[float] = None,
    mag: Optional[float] = None,
    pot: Optional[float] = None,
    vita: Optional[float] = None,      # Retinol Activity Equivalents (mcg)
    vitc: Optional[float] = None,      # mg
    fol: Optional[float] = None,       # Dietary Folate Equivalents (mcg)
    b12: Optional[float] = None,       # mcg
    # Negatives (None = data gap)
    sodium: Optional[float] = None,
    sat_fat: Optional[float] = None,
    sugar: Optional[float] = None,
    ultra: bool = False,
    # Provenance
    estimated: bool = True,
    source: NutritionSource = _CE,
) -> NutritionPer100g:
    return NutritionPer100g(
        calories_kcal=cal,
        protein_g=prot,
        fibre_g=fib,
        iron_mg=iron,
        calcium_mg=cal_mg,
        zinc_mg=zinc,
        magnesium_mg=mag,
        potassium_mg=pot,
        vitamin_a_mcg=vita,
        vitamin_c_mg=vitc,
        folate_mcg=fol,
        vitamin_b12_mcg=b12,
        sodium_mg=sodium,
        saturated_fat_g=sat_fat,
        added_sugar_g=sugar,
        ultra_processed=ultra,
        is_estimated=estimated,
        source=source,
    )


CATALOGUE: list[SKU] = [

    # ── Grains ────────────────────────────────────────────────────────────
    # Most are stocked already; included so the optimizer can prove it knows
    # when to skip (pantry-offset means diminishing marginal NFI return).

    SKU(
        sku_id="sku_atta_aashirvaad_5kg",
        name="Aashirvaad Whole Wheat Atta 5kg",
        brand="Aashirvaad",
        category=SKUCategory.GRAIN,
        pack_size_g=5000,
        price_inr=295,
        ingredient_tags={"wheat", "grain"},
        nutrition=_nutr(346, 12.1, 11.0, 4.9, 39,
                        zinc=2.7, mag=138, pot=190, sodium=2,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_basmati_indiagate_1kg",
        name="India Gate Basmati Rice 1kg",
        brand="India Gate",
        category=SKUCategory.GRAIN,
        pack_size_g=1000,
        price_inr=180,
        ingredient_tags={"rice", "grain"},
        nutrition=_nutr(345, 7.1, 1.3, 0.8, 10,
                        zinc=1.1, mag=25, pot=115, sodium=5,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_oats_quaker_1kg",
        name="Quaker Oats 1kg",
        brand="Quaker",
        category=SKUCategory.GRAIN,
        pack_size_g=1000,
        price_inr=329,
        ingredient_tags={"oats", "grain"},
        nutrition=_nutr(389, 16.9, 10.6, 4.7, 54,
                        zinc=3.97, mag=138, pot=429, sodium=2,
                        estimated=False, source=_BL),
    ),
    SKU(
        sku_id="sku_ragi_flour_500g",
        name="Fresho Ragi Flour 500g",
        brand="Fresho",
        category=SKUCategory.GRAIN,
        pack_size_g=500,
        price_inr=90,
        ingredient_tags={"grain", "ragi"},
        # Ragi is the highest calcium whole grain; key for dairy-excluded households
        nutrition=_nutr(328, 7.3, 11.5, 3.9, 344,
                        zinc=2.3, mag=137, pot=408, vita=0, vitc=0, sodium=10,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_ragi_fortified_atta_1kg",
        name="Aashirvaad Ragi Fortified Atta 1kg",
        brand="Aashirvaad",
        category=SKUCategory.GRAIN,
        pack_size_g=1000,
        price_inr=85,
        ingredient_tags={"wheat", "grain", "ragi"},
        # Iron-fortified blend — label data from manufacturer
        nutrition=_nutr(340, 11.5, 12.0, 13.5, 150,
                        zinc=2.5, mag=140, sodium=5,
                        estimated=False, source=_BL),
    ),
    SKU(
        sku_id="sku_jowar_flour_500g",
        name="Fresho Jowar (Sorghum) Flour 500g",
        brand="Fresho",
        category=SKUCategory.GRAIN,
        pack_size_g=500,
        price_inr=65,
        ingredient_tags={"grain", "jowar"},
        nutrition=_nutr(349, 10.4, 9.7, 4.1, 25,
                        zinc=1.7, mag=150, pot=350, sodium=6,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_amaranth_250g",
        name="Rajgira (Amaranth) Grain 250g",
        brand="Organic India",
        category=SKUCategory.GRAIN,
        pack_size_g=250,
        price_inr=110,
        ingredient_tags={"grain", "amaranth"},
        # Rajgira is Jain-approved fasting grain; calcium+iron+protein dense
        nutrition=_nutr(371, 14.0, 7.0, 8.7, 215,
                        zinc=2.9, mag=248, pot=508, sodium=4,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_poha_500g",
        name="Fresho Thick Poha 500g",
        brand="Fresho",
        category=SKUCategory.GRAIN,
        pack_size_g=500,
        price_inr=55,
        ingredient_tags={"grain", "rice"},
        nutrition=_nutr(356, 6.6, 2.0, 11.0, 15,
                        zinc=1.0, mag=70, pot=200, sodium=8,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_brown_rice_1kg",
        name="Fresho Brown Rice 1kg",
        brand="Fresho",
        category=SKUCategory.GRAIN,
        pack_size_g=1000,
        price_inr=140,
        ingredient_tags={"grain", "rice"},
        nutrition=_nutr(345, 7.5, 3.5, 1.8, 23,
                        zinc=1.8, mag=143, pot=220, sodium=7,
                        estimated=True, source=_IF),
    ),

    # ── Pulses ────────────────────────────────────────────────────────────

    SKU(
        sku_id="sku_toor_dal_tata_500g",
        name="Tata Sampann Toor Dal 500g",
        brand="Tata Sampann",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=98,
        ingredient_tags={"pulse"},
        nutrition=_nutr(343, 22.3, 15.0, 3.9, 73,
                        zinc=3.1, mag=150, pot=600, sodium=17,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_moong_dal_tata_500g",
        name="Tata Sampann Moong Dal 500g",
        brand="Tata Sampann",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=89,
        ingredient_tags={"pulse"},
        nutrition=_nutr(347, 24.0, 16.3, 4.4, 75,
                        zinc=3.0, mag=166, pot=655, sodium=15,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_chana_dal_24mantra_500g",
        name="24 Mantra Organic Chana Dal 500g",
        brand="24 Mantra",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=110,
        ingredient_tags={"pulse"},
        nutrition=_nutr(364, 22.5, 12.0, 7.2, 105,
                        zinc=3.2, mag=140, pot=480, fol=170, sodium=24,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_rajma_organicindia_500g",
        name="Organic India Rajma 500g",
        brand="Organic India",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=145,
        ingredient_tags={"pulse"},
        nutrition=_nutr(346, 22.9, 15.2, 8.2, 143,
                        zinc=2.8, mag=120, pot=970, fol=130, sodium=24,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_chickpeas_fortune_500g",
        name="Fortune Kabuli Chana 500g",
        brand="Fortune",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=85,
        ingredient_tags={"pulse"},
        nutrition=_nutr(364, 19.3, 17.0, 4.3, 105,
                        zinc=3.4, mag=115, pot=875, fol=172, vitc=1.3, sodium=24,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_masoor_dal_500g",
        name="Tata Sampann Masoor Dal 500g",
        brand="Tata Sampann",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=92,
        ingredient_tags={"pulse"},
        nutrition=_nutr(340, 24.9, 10.6, 7.6, 68,
                        zinc=3.3, mag=122, pot=700, fol=479, sodium=6,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_urad_dal_500g",
        name="Tata Sampann Urad Dal 500g",
        brand="Tata Sampann",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=105,
        ingredient_tags={"pulse"},
        nutrition=_nutr(347, 25.2, 18.9, 9.1, 138,
                        zinc=3.7, mag=150, pot=740, fol=216, sodium=38,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_soya_chunks_nutrela_200g",
        name="Nutrela Soya Chunks 200g",
        brand="Nutrela",
        category=SKUCategory.PULSE,
        pack_size_g=200,
        price_inr=55,
        ingredient_tags={"soy"},
        # Nutrela label: protein 52g, iron 9mg, calcium 350mg per 100g
        nutrition=_nutr(345, 52.0, 13.0, 9.0, 350,
                        zinc=2.5, mag=80, pot=1050, sodium=50,
                        estimated=False, source=_BL),
    ),
    SKU(
        sku_id="sku_roasted_chana_200g",
        name="Haldiram Roasted Chana 200g",
        brand="Haldiram",
        category=SKUCategory.PULSE,
        pack_size_g=200,
        price_inr=45,
        ingredient_tags={"pulse"},
        nutrition=_nutr(369, 22.0, 17.0, 5.8, 100,
                        zinc=2.5, mag=110, pot=700, sodium=300, sat_fat=1.5,
                        estimated=True, source=_CE),
    ),

    # ── Seeds ─────────────────────────────────────────────────────────────
    # Micronutrient-dense; small pack sizes but high nutritional intensity.

    SKU(
        sku_id="sku_sesame_seeds_250g",
        name="Fresho White Sesame Seeds 250g",
        brand="Fresho",
        category=SKUCategory.OTHER,
        pack_size_g=250,
        price_inr=80,
        ingredient_tags={"seed"},
        # Sesame: highest calcium in plant foods; very high iron and zinc
        nutrition=_nutr(573, 17.7, 11.8, 14.5, 975,
                        zinc=7.75, mag=346, pot=406, vitc=0, sodium=11, sat_fat=7.0,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_pumpkin_seeds_100g",
        name="Urban Platter Pumpkin Seeds 100g",
        brand="Urban Platter",
        category=SKUCategory.OTHER,
        pack_size_g=100,
        price_inr=120,
        ingredient_tags={"seed"},
        nutrition=_nutr(446, 18.6, 6.0, 8.1, 55,
                        zinc=7.5, mag=550, pot=919, sodium=7,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_flaxseed_250g",
        name="Fresho Flaxseed 250g",
        brand="Fresho",
        category=SKUCategory.OTHER,
        pack_size_g=250,
        price_inr=70,
        ingredient_tags={"seed"},
        nutrition=_nutr(534, 18.3, 27.3, 5.7, 255,
                        zinc=4.3, mag=392, pot=813, sodium=30, sat_fat=3.7,
                        estimated=True, source=_IF),
    ),

    # ── Dairy (lactose-free split is key for fixture household) ───────────

    SKU(
        sku_id="sku_milk_amul_1l",
        name="Amul Toned Milk 1L",
        brand="Amul",
        category=SKUCategory.DAIRY,
        pack_size_g=1000,
        price_inr=58,
        ingredient_tags={"dairy"},
        nutrition=_nutr(58, 3.3, 0, 0.1, 120,
                        b12=0.4, sodium=44, sat_fat=1.6,
                        estimated=False, source=_BL),
    ),
    SKU(
        sku_id="sku_milk_lactose_free_1l",
        name="Heritage Lactose-Free Milk 1L",
        brand="Heritage",
        category=SKUCategory.DAIRY,
        pack_size_g=1000,
        price_inr=95,
        ingredient_tags={"dairy_lactose_free"},  # NOT "dairy" → passes lactose exclusion
        nutrition=_nutr(60, 3.3, 0, 0.1, 125,
                        b12=0.4, sodium=44, sat_fat=1.6,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_paneer_milky_mist_200g",
        name="Milky Mist Paneer 200g",
        brand="Milky Mist",
        category=SKUCategory.DAIRY,
        pack_size_g=200,
        price_inr=99,
        ingredient_tags={"dairy"},
        nutrition=_nutr(265, 18.3, 0, 0.2, 208,
                        b12=0.8, sodium=30, sat_fat=11.0,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_curd_nandini_400g",
        name="Nandini Curd 400g",
        brand="Nandini",
        category=SKUCategory.DAIRY,
        pack_size_g=400,
        price_inr=42,
        ingredient_tags={"dairy"},
        nutrition=_nutr(60, 3.1, 0, 0.1, 121,
                        b12=0.4, sodium=36, sat_fat=1.7,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_paneer_lactose_free_200g",
        name="Akshayakalpa Lactose-Free Paneer 200g",
        brand="Akshayakalpa",
        category=SKUCategory.DAIRY,
        pack_size_g=200,
        price_inr=120,
        ingredient_tags={"dairy_lactose_free"},
        nutrition=_nutr(265, 18.3, 0, 0.2, 208,
                        b12=0.8, sodium=30, sat_fat=11.0,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_curd_lactose_free_400g",
        name="Akshayakalpa Lactose-Free Curd 400g",
        brand="Akshayakalpa",
        category=SKUCategory.DAIRY,
        pack_size_g=400,
        price_inr=75,
        ingredient_tags={"dairy_lactose_free"},
        nutrition=_nutr(60, 3.1, 0, 0.1, 121,
                        b12=0.4, sodium=36, sat_fat=1.7,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_tofu_urbanplatter_400g",
        name="Urban Platter Tofu 400g",
        brand="Urban Platter",
        category=SKUCategory.DAIRY,
        pack_size_g=400,
        price_inr=180,
        ingredient_tags={"soy"},
        nutrition=_nutr(76, 8.1, 0.3, 1.6, 350,
                        zinc=0.8, mag=30, pot=121, sodium=17, sat_fat=1.0,
                        estimated=True, source=_CE),
    ),

    # B12-fortified soy milk (key for vegetarians who exclude dairy)
    SKU(
        sku_id="sku_soy_milk_b12_1l",
        name="Sofit B12 Fortified Soy Milk 1L",
        brand="Sofit",
        category=SKUCategory.DAIRY,
        pack_size_g=1000,
        price_inr=130,
        ingredient_tags={"soy"},
        # Fortified at ~0.38 mcg B12 per 100ml (1 serving = 200ml ≈ 0.76mcg)
        nutrition=_nutr(33, 2.8, 0.4, 0.3, 120,
                        b12=0.38, sodium=52, sat_fat=0.5,
                        estimated=False, source=_BL),
    ),

    # ── Nutritional yeast (B12, zinc, folate — vegan staple) ─────────────
    SKU(
        sku_id="sku_nutritional_yeast_100g",
        name="Urban Platter Nutritional Yeast 100g",
        brand="Urban Platter",
        category=SKUCategory.OTHER,
        pack_size_g=100,
        price_inr=250,
        ingredient_tags={"yeast"},
        # B12 varies widely by brand (unfortified ~2mcg, fortified up to 20mcg).
        # Using category estimate for unfortified nutritional yeast.
        nutrition=_nutr(325, 50.0, 26.0, 6.0, 50,
                        zinc=9.9, mag=231, pot=2390, fol=2340, b12=2.0,
                        sodium=80,
                        estimated=True, source=_CE),
    ),

    # ── Vegetables ────────────────────────────────────────────────────────

    SKU(
        sku_id="sku_palak_500g",
        name="Fresh Palak (Spinach) 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=45,
        ingredient_tags={"leafy_green"},
        nutrition=_nutr(23, 2.9, 2.2, 2.7, 99,
                        zinc=0.5, mag=58, pot=558, vita=469, vitc=28, fol=194, sodium=79,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_methi_250g",
        name="Fresh Methi 250g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=250,
        price_inr=35,
        ingredient_tags={"leafy_green"},
        nutrition=_nutr(49, 4.4, 1.1, 1.9, 176,
                        zinc=1.1, mag=51, pot=770, vita=395, vitc=220, fol=57, sodium=76,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_bhindi_500g",
        name="Fresh Bhindi 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=55,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(33, 1.9, 3.2, 0.6, 82,
                        zinc=0.4, mag=57, pot=299, vita=36, vitc=13, fol=60, sodium=8,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_tomato_1kg",
        name="Fresh Tomato 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=40,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(18, 0.9, 1.2, 0.3, 10,
                        zinc=0.2, mag=11, pot=237, vita=42, vitc=27, fol=15, sodium=5,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_cauliflower_1kg",
        name="Fresh Cauliflower 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=50,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(25, 1.9, 2.0, 0.4, 22,
                        zinc=0.3, mag=15, pot=299, vitc=47, fol=57, sodium=30,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_lauki_500g",
        name="Fresh Lauki 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=30,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(15, 0.6, 0.5, 0.2, 26,
                        zinc=0.1, mag=11, pot=150, vitc=7, sodium=2,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_drumstick_500g",
        name="Fresh Drumstick (Moringa Pods) 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=50,
        ingredient_tags={"vegetable"},
        # Drumstick pods: very high vit C and moderate calcium; Jain-compatible
        nutrition=_nutr(26, 2.5, 4.8, 0.2, 30,
                        zinc=0.5, mag=45, pot=461, vitc=141, vita=25, sodium=42,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_green_peas_frozen_500g",
        name="McCain Frozen Green Peas 500g",
        brand="McCain",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=95,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(81, 5.4, 5.5, 1.5, 43,
                        zinc=1.2, mag=33, pot=244, vitc=40, fol=65, sodium=5,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_capsicum_red_500g",
        name="Fresh Red Capsicum 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=90,
        ingredient_tags={"vegetable"},
        # Red capsicum is the highest vit C common vegetable after amla
        nutrition=_nutr(31, 1.0, 2.1, 0.5, 7,
                        zinc=0.3, mag=10, pot=211, vita=26, vitc=127, fol=46, sodium=4,
                        estimated=True, source=_IF),
    ),
    # ── Jain-INCOMPATIBLE produce ──────────────────────────────────────────
    SKU(
        sku_id="sku_onion_1kg",
        name="Fresh Onion 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=35,
        ingredient_tags={"onion", "vegetable"},
        nutrition=_nutr(40, 1.1, 1.7, 0.2, 23,
                        vitc=7, fol=15, mag=10, pot=157, sodium=4,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_potato_1kg",
        name="Fresh Potato 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=32,
        ingredient_tags={"potato", "vegetable"},
        nutrition=_nutr(77, 2.0, 2.2, 0.8, 12,
                        vitc=17, pot=422, mag=23, sodium=6,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_carrot_500g",
        name="Fresh Carrot 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=40,
        ingredient_tags={"carrot", "vegetable"},
        nutrition=_nutr(41, 0.9, 2.8, 0.3, 33,
                        vita=835, vitc=3, mag=12, pot=320, sodium=69,
                        estimated=True, source=_IF),
    ),

    # ── Fruit ─────────────────────────────────────────────────────────────

    SKU(
        sku_id="sku_banana_1kg",
        name="Fresh Banana 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=1000,
        price_inr=60,
        ingredient_tags={"fruit"},
        nutrition=_nutr(89, 1.1, 2.6, 0.3, 5,
                        zinc=0.2, mag=27, pot=358, vitc=8.7, fol=20, sodium=1,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_apple_1kg",
        name="Fresh Apple 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=1000,
        price_inr=180,
        ingredient_tags={"fruit"},
        nutrition=_nutr(52, 0.3, 2.4, 0.1, 6,
                        mag=5, pot=107, vitc=6, fol=3, sodium=1,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_dates_lions_500g",
        name="Lion Dates 500g",
        brand="Lion",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=500,
        price_inr=210,
        ingredient_tags={"fruit"},
        nutrition=_nutr(282, 2.5, 8.0, 1.0, 39,
                        mag=54, pot=696, fol=15, sodium=1, sugar=66.5,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_guava_500g",
        name="Fresh Guava 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=500,
        price_inr=55,
        ingredient_tags={"fruit"},
        # Guava has among the highest vit C of common fruits
        nutrition=_nutr(68, 2.6, 5.4, 0.3, 18,
                        zinc=0.23, mag=22, pot=417, vita=31, vitc=228, fol=49, sodium=2,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_papaya_1kg",
        name="Fresh Papaya 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=1000,
        price_inr=70,
        ingredient_tags={"fruit"},
        nutrition=_nutr(32, 0.5, 1.8, 0.5, 17,
                        mag=20, pot=182, vita=47, vitc=62, fol=37, sodium=8,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_amla_250g",
        name="Fresh Amla (Indian Gooseberry) 250g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=250,
        price_inr=60,
        ingredient_tags={"fruit"},
        # Amla: highest natural vit C source (~600mg/100g); Jain-compatible
        nutrition=_nutr(44, 0.9, 3.4, 1.2, 50,
                        mag=10, pot=198, vita=9, vitc=600, fol=6, sodium=1,
                        estimated=True, source=_IF),
    ),
    SKU(
        sku_id="sku_dried_apricots_200g",
        name="Lion Dried Apricots 200g",
        brand="Lion",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=200,
        price_inr=180,
        ingredient_tags={"fruit"},
        nutrition=_nutr(241, 3.4, 7.3, 2.7, 55,
                        zinc=0.4, mag=32, pot=1160, vita=180, fol=10, sodium=10, sugar=53.0,
                        estimated=True, source=_IF),
    ),

    # ── Oils & fats ───────────────────────────────────────────────────────

    SKU(
        sku_id="sku_oil_fortune_1l",
        name="Fortune Sunflower Oil 1L",
        brand="Fortune",
        category=SKUCategory.OIL,
        pack_size_g=900,
        price_inr=160,
        ingredient_tags={"oil"},
        nutrition=_nutr(900, 0, 0, 0, 0, sat_fat=10.5, sodium=0,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_ghee_amul_500ml",
        name="Amul Ghee 500ml",
        brand="Amul",
        category=SKUCategory.OIL,
        pack_size_g=460,
        price_inr=320,
        ingredient_tags={"dairy", "oil"},
        nutrition=_nutr(900, 0, 0, 0, 0, sat_fat=62.0, sodium=12,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_coconut_oil_500ml",
        name="Parachute Coconut Oil 500ml",
        brand="Parachute",
        category=SKUCategory.OIL,
        pack_size_g=460,
        price_inr=230,
        ingredient_tags={"oil"},
        # Coconut oil is ~87% saturated fat — explicitly tracked as negative
        nutrition=_nutr(900, 0, 0, 0, 0, sat_fat=86.5, sodium=0,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_mustard_oil_500ml",
        name="Dhara Cold Pressed Mustard Oil 500ml",
        brand="Dhara",
        category=SKUCategory.OIL,
        pack_size_g=460,
        price_inr=145,
        ingredient_tags={"oil"},
        nutrition=_nutr(900, 0, 0, 0, 0, sat_fat=11.6, sodium=0,
                        estimated=True, source=_CE),
    ),

    # ── Spices ────────────────────────────────────────────────────────────

    SKU(
        sku_id="sku_masala_everest_kitchenking",
        name="Everest Kitchen King Masala 100g",
        brand="Everest",
        category=SKUCategory.SPICE,
        pack_size_g=100,
        price_inr=70,
        ingredient_tags={"onion", "garlic", "spice"},
        nutrition=_nutr(280, 12, 25, 12, 200, sodium=2200,
                        ultra=False, estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_haldi_tata_200g",
        name="Tata Sampann Haldi Powder 200g",
        brand="Tata Sampann",
        category=SKUCategory.SPICE,
        pack_size_g=200,
        price_inr=85,
        ingredient_tags={"spice"},
        nutrition=_nutr(354, 7.8, 21, 41, 183, sodium=38,
                        estimated=True, source=_IF),
    ),

    # ── High-sodium COMPATIBLE tripwires ──────────────────────────────────
    # These have NO onion/garlic/nuts/dairy tags → pass all Sharma filters.
    # They give the negative-nutrient panel real content to display.

    SKU(
        sku_id="sku_papad_lijjat_200g",
        name="Lijjat Plain Urad Papad 200g",
        brand="Lijjat",
        category=SKUCategory.OTHER,
        pack_size_g=200,
        price_inr=60,
        ingredient_tags={"pulse"},   # plain urad — no onion/garlic
        # High sodium per 100g (dried); ~5g portion = ~45mg sodium per papad
        nutrition=_nutr(350, 26.0, 6.0, 8.0, 100,
                        sodium=900, sat_fat=1.5,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_sev_plain_200g",
        name="Haldiram Plain Sev 200g",
        brand="Haldiram",
        category=SKUCategory.OTHER,
        pack_size_g=200,
        price_inr=55,
        ingredient_tags={"grain"},   # besan, no onion — Jain-safe
        nutrition=_nutr(550, 14.0, 8.0, 4.0, 40,
                        sodium=750, sat_fat=8.0,
                        ultra=True, estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_makhana_salted_100g",
        name="Salted Makhana Fox Nuts 100g",
        brand="Farmley",
        category=SKUCategory.OTHER,
        pack_size_g=100,
        price_inr=80,
        ingredient_tags={"grain"},   # lotus seed, Jain-safe
        nutrition=_nutr(347, 9.7, 14.5, 1.3, 60,
                        mag=67, pot=500, sodium=400,
                        estimated=True, source=_CE),
    ),

    # ── Added-sugar + ultra-processed COMPATIBLE ──────────────────────────
    # Optimizer must see the tension: nutrition value vs negative nutrients.

    SKU(
        sku_id="sku_cornflakes_kelloggs_500g",
        name="Kellogg's Corn Flakes 500g",
        brand="Kellogg's",
        category=SKUCategory.GRAIN,
        pack_size_g=500,
        price_inr=230,
        ingredient_tags={"grain"},
        # Iron-fortified (8.3mg/100g); but high sodium and added sugar
        nutrition=_nutr(356, 6.8, 1.2, 8.3, 3,
                        sodium=650, sugar=7.0, sat_fat=0.4,
                        ultra=True, estimated=False, source=_BL),
    ),
    SKU(
        sku_id="sku_fruit_juice_tropicana_1l",
        name="Tropicana Mixed Fruit Juice 1L",
        brand="Tropicana",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=1000,
        price_inr=130,
        ingredient_tags={"fruit"},
        nutrition=_nutr(46, 0.4, 0.2, 0.1, 8,
                        vitc=40, sodium=6, sugar=9.0,
                        ultra=True, estimated=False, source=_BL),
    ),
    SKU(
        sku_id="sku_crackers_britannia_200g",
        name="Britannia 50-50 Crackers 200g",
        brand="Britannia",
        category=SKUCategory.OTHER,
        pack_size_g=200,
        price_inr=50,
        ingredient_tags={"wheat", "grain"},   # no dairy in this variant
        nutrition=_nutr(462, 8.5, 2.5, 3.5, 25,
                        sodium=380, sugar=5.0, sat_fat=5.0,
                        ultra=True, estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_jam_kissan_500g",
        name="Kissan Mixed Fruit Jam 500g",
        brand="Kissan",
        category=SKUCategory.OTHER,
        pack_size_g=500,
        price_inr=120,
        ingredient_tags={"fruit"},
        nutrition=_nutr(260, 0.5, 0.5, 0.5, 10,
                        sodium=35, sugar=55.0,
                        ultra=True, estimated=True, source=_CE),
    ),

    # ── Snacks (existing allergy tripwires) ───────────────────────────────

    SKU(
        sku_id="sku_peanut_chikki_200g",
        name="Peanut Chikki 200g",
        brand="Haldiram",
        category=SKUCategory.OTHER,
        pack_size_g=200,
        price_inr=80,
        ingredient_tags={"peanut"},
        nutrition=_nutr(520, 14, 5, 2, 60, sodium=70, sugar=28.0,
                        estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_chips_lays_potato",
        name="Lay's Classic Salted 90g",
        brand="Lay's",
        category=SKUCategory.OTHER,
        pack_size_g=90,
        price_inr=30,
        ingredient_tags={"potato"},   # Jain-incompatible
        nutrition=_nutr(536, 6, 4, 1.5, 30,
                        sodium=530, sat_fat=3.4,
                        ultra=True, estimated=True, source=_CE),
    ),

    # ── Jain-INCOMPATIBLE ultra-processed ─────────────────────────────────
    # All three have onion and/or garlic tags → filtered out for hh_demo_001.
    # They demonstrate the dietary-filter working on processed foods.

    SKU(
        sku_id="sku_instant_noodles_maggi_70g",
        name="Maggi 2-Minute Noodles 70g",
        brand="Maggi",
        category=SKUCategory.OTHER,
        pack_size_g=70,
        price_inr=14,
        ingredient_tags={"onion", "garlic", "wheat"},
        nutrition=_nutr(400, 10.0, 2.0, 3.8, 25,
                        sodium=1570, sat_fat=8.0, sugar=1.0,
                        ultra=True, estimated=False, source=_BL),
    ),
    SKU(
        sku_id="sku_rte_dal_makhani_300g",
        name="MTR Ready to Eat Dal Makhani 300g",
        brand="MTR",
        category=SKUCategory.OTHER,
        pack_size_g=300,
        price_inr=120,
        ingredient_tags={"onion", "garlic", "dairy"},
        nutrition=_nutr(118, 4.5, 3.5, 2.1, 85,
                        sodium=680, sat_fat=5.0,
                        ultra=True, estimated=True, source=_CE),
    ),
    SKU(
        sku_id="sku_frozen_momos_veg_200g",
        name="McCain Veg Momos 200g",
        brand="McCain",
        category=SKUCategory.OTHER,
        pack_size_g=200,
        price_inr=130,
        ingredient_tags={"onion", "garlic", "wheat"},
        nutrition=_nutr(180, 5.0, 2.0, 1.0, 30,
                        sodium=580, sat_fat=2.5,
                        ultra=True, estimated=True, source=_CE),
    ),
]


def fixture_catalogue() -> list[SKU]:
    return CATALOGUE


def get_sku(sku_id: str) -> SKU | None:
    for sku in CATALOGUE:
        if sku.sku_id == sku_id:
            return sku
    return None
