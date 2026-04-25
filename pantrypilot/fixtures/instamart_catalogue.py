"""
Mock Instamart catalogue.

In production this comes from the Instamart MCP catalogue tool. Here it's
a hand-curated list of ~30 SKUs that:

  1. Covers the categories a vegetarian Bengaluru household actually buys.
  2. Includes deliberate dietary tripwires (onion-garlic masala, potato
     chips, paneer) so the dietary-filter step has real work to do for
     the Jain MIL in the fixture household.
  3. Includes multiple protein sources at meaningfully different
     cost-per-gram-of-protein, so the optimizer's budget-vs-nutrition
     trade-off is visible.

Nutrition values: most are tagged is_estimated=True with source noted as
IFCT-2017 category averages. A few "verified" items use packaging label
data and are marked is_estimated=False — these are the items where we'd
have done the work to confirm a specific brand-pack. This split lets us
demonstrate the 'estimated badge' UX honestly.

Prices reflect rough Bengaluru Instamart range as of early 2026; not
intended to be exact.
"""

from pantrypilot.models import NutritionPer100g, NutritionSource, SKU, SKUCategory


# Helper for readability
def _nutr(
    cal: float,
    prot: float,
    fib: float,
    iron: float,
    cal_mg: float,
    *,
    estimated: bool = True,
    source: NutritionSource = NutritionSource.CATEGORY_ESTIMATE,
) -> NutritionPer100g:
    return NutritionPer100g(
        calories_kcal=cal,
        protein_g=prot,
        fibre_g=fib,
        iron_mg=iron,
        calcium_mg=cal_mg,
        is_estimated=estimated,
        source=source,
    )


CATALOGUE: list[SKU] = [
    # -- Grains (most household has stocked already; included so optimizer
    #    can prove it knows how to skip them) --
    SKU(
        sku_id="sku_atta_aashirvaad_5kg",
        name="Aashirvaad Whole Wheat Atta 5kg",
        brand="Aashirvaad",
        category=SKUCategory.GRAIN,
        pack_size_g=5000,
        price_inr=295,
        ingredient_tags={"wheat", "grain"},
        nutrition=_nutr(346, 12.1, 11.0, 4.9, 39),
    ),
    SKU(
        sku_id="sku_basmati_indiagate_1kg",
        name="India Gate Basmati Rice 1kg",
        brand="India Gate",
        category=SKUCategory.GRAIN,
        pack_size_g=1000,
        price_inr=180,
        ingredient_tags={"rice", "grain"},
        nutrition=_nutr(345, 7.1, 1.3, 0.8, 10),
    ),
    SKU(
        sku_id="sku_oats_quaker_1kg",
        name="Quaker Oats 1kg",
        brand="Quaker",
        category=SKUCategory.GRAIN,
        pack_size_g=1000,
        price_inr=329,
        ingredient_tags={"oats", "grain"},
        nutrition=_nutr(
            389, 16.9, 10.6, 4.7, 54, estimated=False, source=NutritionSource.BRAND_LABEL
        ),
    ),
    # -- Pulses (key protein source, multiple price points) --
    SKU(
        sku_id="sku_toor_dal_tata_500g",
        name="Tata Sampann Toor Dal 500g",
        brand="Tata Sampann",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=98,
        ingredient_tags={"pulse"},
        nutrition=_nutr(343, 22.3, 15.0, 3.9, 73),
    ),
    SKU(
        sku_id="sku_moong_dal_tata_500g",
        name="Tata Sampann Moong Dal 500g",
        brand="Tata Sampann",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=89,
        ingredient_tags={"pulse"},
        nutrition=_nutr(347, 24.0, 16.3, 4.4, 75),
    ),
    SKU(
        sku_id="sku_chana_dal_24mantra_500g",
        name="24 Mantra Organic Chana Dal 500g",
        brand="24 Mantra",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=110,
        ingredient_tags={"pulse"},
        nutrition=_nutr(364, 22.5, 12.0, 7.2, 105),
    ),
    SKU(
        sku_id="sku_rajma_organicindia_500g",
        name="Organic India Rajma 500g",
        brand="Organic India",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=145,
        ingredient_tags={"pulse"},
        nutrition=_nutr(346, 22.9, 15.2, 8.2, 143),
    ),
    SKU(
        sku_id="sku_chickpeas_fortune_500g",
        name="Fortune Kabuli Chana 500g",
        brand="Fortune",
        category=SKUCategory.PULSE,
        pack_size_g=500,
        price_inr=85,
        ingredient_tags={"pulse"},
        nutrition=_nutr(364, 19.3, 17.0, 4.3, 105),
    ),
    # -- Dairy (lactose-free split is important for fixture household) --
    SKU(
        sku_id="sku_milk_amul_1l",
        name="Amul Toned Milk 1L",
        brand="Amul",
        category=SKUCategory.DAIRY,
        pack_size_g=1000,
        price_inr=58,
        ingredient_tags={"dairy"},
        nutrition=_nutr(
            58, 3.3, 0, 0.1, 120, estimated=False, source=NutritionSource.BRAND_LABEL
        ),
    ),
    SKU(
        sku_id="sku_milk_lactose_free_1l",
        name="Heritage Lactose-Free Milk 1L",
        brand="Heritage",
        category=SKUCategory.DAIRY,
        pack_size_g=1000,
        price_inr=95,
        ingredient_tags={"dairy_lactose_free"},  # NOT tagged "dairy" -> bypasses lactose exclusion
        nutrition=_nutr(60, 3.3, 0, 0.1, 125),
    ),
    SKU(
        sku_id="sku_paneer_milky_mist_200g",
        name="Milky Mist Paneer 200g",
        brand="Milky Mist",
        category=SKUCategory.DAIRY,
        pack_size_g=200,
        price_inr=99,
        ingredient_tags={"dairy"},
        nutrition=_nutr(265, 18.3, 0, 0.2, 208),
    ),
    SKU(
        sku_id="sku_curd_nandini_400g",
        name="Nandini Curd 400g",
        brand="Nandini",
        category=SKUCategory.DAIRY,
        pack_size_g=400,
        price_inr=42,
        ingredient_tags={"dairy"},
        nutrition=_nutr(60, 3.1, 0, 0.1, 121),
    ),
    SKU(
        sku_id="sku_tofu_urbanplatter_400g",
        name="Urban Platter Tofu 400g",
        brand="Urban Platter",
        category=SKUCategory.DAIRY,  # category mapping is approximate
        pack_size_g=400,
        price_inr=180,
        ingredient_tags={"soy"},
        nutrition=_nutr(76, 8.1, 0.3, 1.6, 350),
    ),
    # -- Vegetables (Jain-restricted MIL means roots/onion/garlic excluded) --
    SKU(
        sku_id="sku_palak_500g",
        name="Fresh Palak (Spinach) 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=45,
        ingredient_tags={"leafy_green"},
        nutrition=_nutr(23, 2.9, 2.2, 2.7, 99),
    ),
    SKU(
        sku_id="sku_methi_250g",
        name="Fresh Methi 250g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=250,
        price_inr=35,
        ingredient_tags={"leafy_green"},
        nutrition=_nutr(49, 4.4, 1.1, 1.9, 176),
    ),
    SKU(
        sku_id="sku_bhindi_500g",
        name="Fresh Bhindi 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=55,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(33, 1.9, 3.2, 0.6, 82),
    ),
    SKU(
        sku_id="sku_tomato_1kg",
        name="Fresh Tomato 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=40,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(18, 0.9, 1.2, 0.3, 10),
    ),
    SKU(
        sku_id="sku_cauliflower_1kg",
        name="Fresh Cauliflower 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=50,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(25, 1.9, 2.0, 0.4, 22),
    ),
    SKU(
        sku_id="sku_lauki_500g",
        name="Fresh Lauki 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=30,
        ingredient_tags={"vegetable"},
        nutrition=_nutr(15, 0.6, 0.5, 0.2, 26),
    ),
    # -- Jain-INCOMPATIBLE produce (must be filtered out for fixture household) --
    SKU(
        sku_id="sku_onion_1kg",
        name="Fresh Onion 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=35,
        ingredient_tags={"onion", "vegetable"},
        nutrition=_nutr(40, 1.1, 1.7, 0.2, 23),
    ),
    SKU(
        sku_id="sku_potato_1kg",
        name="Fresh Potato 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=1000,
        price_inr=32,
        ingredient_tags={"potato", "vegetable"},
        nutrition=_nutr(77, 2.0, 2.2, 0.8, 12),
    ),
    SKU(
        sku_id="sku_carrot_500g",
        name="Fresh Carrot 500g",
        brand="Fresho",
        category=SKUCategory.PRODUCE_VEG,
        pack_size_g=500,
        price_inr=40,
        ingredient_tags={"carrot", "vegetable"},
        nutrition=_nutr(41, 0.9, 2.8, 0.3, 33),
    ),
    # -- Fruit --
    SKU(
        sku_id="sku_banana_1kg",
        name="Fresh Banana 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=1000,
        price_inr=60,
        ingredient_tags={"fruit"},
        nutrition=_nutr(89, 1.1, 2.6, 0.3, 5),
    ),
    SKU(
        sku_id="sku_apple_1kg",
        name="Fresh Apple 1kg",
        brand="Fresho",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=1000,
        price_inr=180,
        ingredient_tags={"fruit"},
        nutrition=_nutr(52, 0.3, 2.4, 0.1, 6),
    ),
    SKU(
        sku_id="sku_dates_lions_500g",
        name="Lion Dates 500g",
        brand="Lion",
        category=SKUCategory.PRODUCE_FRUIT,
        pack_size_g=500,
        price_inr=210,
        ingredient_tags={"fruit"},
        nutrition=_nutr(282, 2.5, 8.0, 1.0, 39),
    ),
    # -- Oils & fats --
    SKU(
        sku_id="sku_oil_fortune_1l",
        name="Fortune Sunflower Oil 1L",
        brand="Fortune",
        category=SKUCategory.OIL,
        pack_size_g=900,
        price_inr=160,
        ingredient_tags={"oil"},
        nutrition=_nutr(900, 0, 0, 0, 0),
    ),
    SKU(
        sku_id="sku_ghee_amul_500ml",
        name="Amul Ghee 500ml",
        brand="Amul",
        category=SKUCategory.OIL,
        pack_size_g=460,
        price_inr=320,
        ingredient_tags={"dairy", "oil"},
        nutrition=_nutr(900, 0, 0, 0, 0),
    ),
    # -- Spices / Jain-incompatible processed --
    SKU(
        sku_id="sku_masala_everest_kitchenking",
        name="Everest Kitchen King Masala 100g",
        brand="Everest",
        category=SKUCategory.SPICE,
        pack_size_g=100,
        price_inr=70,
        ingredient_tags={"onion", "garlic", "spice"},
        nutrition=_nutr(280, 12, 25, 12, 200),
    ),
    SKU(
        sku_id="sku_haldi_tata_200g",
        name="Tata Sampann Haldi Powder 200g",
        brand="Tata Sampann",
        category=SKUCategory.SPICE,
        pack_size_g=200,
        price_inr=85,
        ingredient_tags={"spice"},
        nutrition=_nutr(354, 7.8, 21, 41, 183),
    ),
    # -- Snacks (peanut tripwire for the kid's allergy) --
    SKU(
        sku_id="sku_peanut_chikki_200g",
        name="Peanut Chikki 200g",
        brand="Haldiram",
        category=SKUCategory.OTHER,
        pack_size_g=200,
        price_inr=80,
        ingredient_tags={"peanut"},
        nutrition=_nutr(520, 14, 5, 2, 60),
    ),
    SKU(
        sku_id="sku_chips_lays_potato",
        name="Lay's Classic Salted 90g",
        brand="Lay's",
        category=SKUCategory.OTHER,
        pack_size_g=90,
        price_inr=30,
        ingredient_tags={"potato"},  # Jain-incompatible
        nutrition=_nutr(536, 6, 4, 1.5, 30),
    ),
]


def fixture_catalogue() -> list[SKU]:
    return CATALOGUE


def get_sku(sku_id: str) -> SKU | None:
    for sku in CATALOGUE:
        if sku.sku_id == sku_id:
            return sku
    return None
