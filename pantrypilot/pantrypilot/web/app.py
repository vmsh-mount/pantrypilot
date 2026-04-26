"""
PantryPilot Web — household creation form + Swiggy-style plan page.

HTML routes:
  GET  /                           → redirect to /household/new
  GET  /household/new              → multi-member household form
  POST /household                  → save household, redirect to /plan
  GET  /household/{id}/plan        → Swiggy-style SPA (HOUSEHOLD_ID injected)
  GET  /household/{id}/basket      → server-rendered basket (legacy/tests)

JSON API (consumed by plan.html JS):
  GET  /api/household/{id}             → household JSON
  GET  /api/catalogue?household_id=... → filtered catalogue JSON
  POST /api/cycle                      → run optimizer, return basket+NFI
  POST /api/cycle/{sid}/confirm        → confirm or cancel pending basket

Start with:
  uvicorn pantrypilot.web.app:app --port 8001 --reload
"""

from __future__ import annotations

import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from fixtures.instamart_catalogue import fixture_catalogue
from pantrypilot.models import (
    ActivityLevel,
    Allergy,
    DietaryPattern,
    Household,
    Member,
    PantryItem,
    Sex,
)
from pantrypilot.optimizer import OptimizationResult, optimise_basket

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(title="PantryPilot Web")

_households: dict[str, Household] = {}
_pantries: dict[str, list[PantryItem]] = {}
_sessions: dict[str, "_Session"] = {}
_CATALOGUE = fixture_catalogue()
_CATALOGUE_BY_ID = {s.sku_id: s for s in _CATALOGUE}

# Common pantry SKUs shown in the form (label, sku_id, default_g)
PANTRY_FORM_ITEMS = [
    ("Atta / wheat flour",    "sku_atta_aashirvaad_5kg",     0),
    ("Basmati rice",          "sku_basmati_indiagate_1kg",   0),
    ("Toor dal",              "sku_toor_dal_tata_500g",      0),
    ("Moong dal",             "sku_moong_dal_tata_500g",     0),
    ("Cooking oil",           "sku_oil_fortune_1l",          0),
    ("Oats",                  "sku_oats_quaker_1kg",         0),
    ("Palak / spinach",       "sku_palak_500g",              0),
    ("Tomatoes",              "sku_tomato_1kg",              0),
]


@dataclass
class _Session:
    household_id: str
    opt: OptimizationResult
    created_at: float = field(default_factory=time.time)
    ttl: int = 14400

    def expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CycleRequest(BaseModel):
    household_id: str


class ConfirmRequest(BaseModel):
    action: str  # "confirm" | "cancel"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_household_from_form(form_data) -> Household:
    name = (form_data.get("household_name") or "My Household").strip()
    pincode = (form_data.get("pincode") or "000000").strip()
    budget = int(form_data.get("weekly_budget") or 2000)

    members: list[Member] = []
    i = 0
    while True:
        mname = form_data.get(f"member_name_{i}")
        if mname is None:
            break
        mname = mname.strip() or f"Member {i + 1}"
        age = int(form_data.get(f"member_age_{i}") or 30)
        sex = Sex(form_data.get(f"member_sex_{i}") or "male")
        weight = float(form_data.get(f"member_weight_{i}") or 60)
        activity = ActivityLevel(form_data.get(f"member_activity_{i}") or "moderate")

        patterns = [
            DietaryPattern(v)
            for v in form_data.getlist(f"member_dietary_{i}")
            if v
        ]
        allergies = [
            Allergy(v)
            for v in form_data.getlist(f"member_allergy_{i}")
            if v
        ]

        members.append(Member(
            name=mname,
            age=age,
            sex=sex,
            weight_kg=weight,
            activity=activity,
            dietary_patterns=patterns or [DietaryPattern.VEGETARIAN],
            allergies=allergies,
        ))
        i += 1

    if not members:
        members = [Member(
            name="Member 1", age=30, sex=Sex.MALE, weight_kg=65,
            activity=ActivityLevel.MODERATE,
            dietary_patterns=[DietaryPattern.VEGETARIAN],
        )]

    hh_id = f"hh_{uuid.uuid4().hex[:8]}"
    return Household(
        household_id=hh_id,
        name=name,
        members=members,
        weekly_budget_inr=budget,
        pincode=pincode,
    )


def _hh_dict(hh: Household) -> dict:
    return {
        "household_id": hh.household_id,
        "name": hh.name,
        "weekly_budget_inr": hh.weekly_budget_inr,
        "pincode": hh.pincode,
        "members": [
            {
                "name": m.name,
                "age": m.age,
                "dietary_patterns": [p.value for p in m.dietary_patterns],
                "allergies": [a.value for a in m.allergies],
            }
            for m in hh.members
        ],
        "powered_by": "Swiggy Instamart",
    }


def _alternatives(line_sku_id: str, compatible: list, basket_sku_ids: set, n: int = 2) -> list:
    """Top-n compatible SKUs not in basket, ranked by same food category proximity."""
    basket_sku = _CATALOGUE_BY_ID.get(line_sku_id)
    if basket_sku is None:
        return []
    # Score by tag overlap with the basket item (same category = higher score)
    candidates = [
        s for s in compatible
        if s.sku_id not in basket_sku_ids and s.sku_id != line_sku_id
    ]
    def score(s):
        overlap = len(set(s.ingredient_tags) & set(basket_sku.ingredient_tags))
        # Prefer similar price range
        price_diff = abs(s.price_inr - basket_sku.price_inr)
        return (overlap, -price_diff)
    candidates.sort(key=score, reverse=True)
    return [
        {
            "sku_id": s.sku_id,
            "name": s.name,
            "brand": s.brand,
            "price_inr": s.price_inr,
            "pack_size_g": s.pack_size_g,
            "reason": f"Similar option · ₹{s.price_inr:.0f}",
        }
        for s in candidates[:n]
    ]


def _cycle_dict(session_id: str, hh: Household, opt: OptimizationResult,
               filtered_out: int, ttl: int, compatible: list) -> dict:
    confirm_before = datetime.fromtimestamp(
        time.time() + ttl, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    targets = hh.weekly_targets()
    neg = opt.basket.negative_totals()
    adults = sum(1 for m in hh.members if m.age >= 18)
    basket_ids = {line.sku.sku_id for line in opt.basket.lines}
    return {
        "session_id": session_id,
        "household_id": hh.household_id,
        "status": "READY_TO_CONFIRM",
        "basket": [
            {
                "sku_id": line.sku.sku_id,
                "name": line.sku.name,
                "brand": line.sku.brand,
                "quantity": line.quantity,
                "pack_size_g": line.sku.pack_size_g,
                "price_inr": line.sku.price_inr,
                "total_price_inr": line.total_price_inr(),
                "nutrition_estimated": line.sku.nutrition.is_estimated,
                "reason": line.reason,
                "alternatives": _alternatives(line.sku.sku_id, compatible, basket_ids),
            }
            for line in opt.basket.lines
        ],
        "nfi": {
            "calories_pct": opt.nfi.calories_pct,
            "protein_pct": opt.nfi.protein_pct,
            "fibre_pct": opt.nfi.fibre_pct,
            "iron_pct": opt.nfi.iron_pct,
            "calcium_pct": opt.nfi.calcium_pct,
            "overall_pct": opt.nfi.overall_pct,
            "contains_estimated": opt.nfi.contains_estimated,
            # Extended (display only)
            "zinc_pct": opt.nfi.zinc_pct,
            "magnesium_pct": opt.nfi.magnesium_pct,
            "potassium_pct": opt.nfi.potassium_pct,
            "vitamin_a_pct": opt.nfi.vitamin_a_pct,
            "vitamin_c_pct": opt.nfi.vitamin_c_pct,
            "folate_pct": opt.nfi.folate_pct,
            "vitamin_b12_pct": opt.nfi.vitamin_b12_pct,
        },
        "negatives": {
            "sodium_mg": neg.sodium_mg,
            "saturated_fat_g": neg.saturated_fat_g,
            "added_sugar_g": neg.added_sugar_g,
            "ultra_processed_count": neg.ultra_processed_count,
        },
        "neg_ceilings": {
            "sodium_mg": 2000.0 * len(hh.members) * 7,
            "saturated_fat_g": (targets.calories_kcal * 0.10) / 9.0,
            "added_sugar_g": max(25.0 * adults * 7, 50.0),
        },
        "budget_used_inr": opt.budget_used_inr,
        "budget_total_inr": opt.budget_total_inr,
        "binding_nutrient": opt.binding_nutrient,
        "overstocked_skipped": opt.overstocked_skipped,
        "pantry_topup": opt.pantry_topup,
        "skus_filtered_out": filtered_out,
        "solve_time_ms": opt.solve_time_ms,
        "confirm_before": confirm_before,
        "powered_by": "Swiggy Instamart",
    }


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/household/new", status_code=302)


@app.get("/household/new", response_class=HTMLResponse)
def get_new_household(request: Request):
    return templates.TemplateResponse(request, "household_form.html", {"pantry_items": PANTRY_FORM_ITEMS})


@app.post("/household", response_class=RedirectResponse)
async def post_household(request: Request):
    from datetime import date
    form_data = await request.form()
    hh = _build_household_from_form(form_data)
    _households[hh.household_id] = hh
    today = date.today()
    pantry = [
        PantryItem(sku_id=sku_id, quantity_g=float(form_data.get(f"pantry_{sku_id}", 0) or 0), last_updated=today)
        for _, sku_id, _ in PANTRY_FORM_ITEMS
        if float(form_data.get(f"pantry_{sku_id}", 0) or 0) > 0
    ]
    _pantries[hh.household_id] = pantry
    return RedirectResponse(url=f"/household/{hh.household_id}/plan", status_code=303)


@app.get("/household/{household_id}/plan", response_class=HTMLResponse)
def get_plan(request: Request, household_id: str):
    hh = _households.get(household_id)
    if hh is None:
        return templates.TemplateResponse(
            request, "error.html",
            {"message": f"Household '{household_id}' not found."},
            status_code=404,
        )
    return templates.TemplateResponse(request, "plan.html", {"household_id": household_id})


@app.get("/household/{household_id}/basket", response_class=HTMLResponse)
def get_basket(request: Request, household_id: str):
    hh = _households.get(household_id)
    if hh is None:
        return templates.TemplateResponse(
            request, "error.html",
            {"message": f"Household '{household_id}' not found."},
            status_code=404,
        )

    compatible = [s for s in _CATALOGUE if s.is_compatible_with(hh)]
    t0 = time.time()
    result = optimise_basket(hh, compatible, [])
    solve_ms = round((time.time() - t0) * 1000)

    targets = hh.weekly_targets()
    neg = result.basket.negative_totals()
    missing_report = result.basket.missing_nutrients_report()

    sat_fat_ceiling = (targets.calories_kcal * 0.10) / 9.0
    sodium_ceiling = 2000.0 * len(hh.members) * 7
    adults = sum(1 for m in hh.members if m.age >= 18)
    added_sugar_ceiling = max(25.0 * adults * 7, 50.0)

    ext_nutrients = [
        ("Zinc",       result.nfi.zinc_pct,       "zinc_mg"),
        ("Magnesium",  result.nfi.magnesium_pct,  "magnesium_mg"),
        ("Potassium",  result.nfi.potassium_pct,  "potassium_mg"),
        ("Vitamin A",  result.nfi.vitamin_a_pct,  "vitamin_a_mcg"),
        ("Vitamin C",  result.nfi.vitamin_c_pct,  "vitamin_c_mg"),
        ("Folate",     result.nfi.folate_pct,      "folate_mcg"),
        ("Vitamin B12", result.nfi.vitamin_b12_pct, "vitamin_b12_mcg"),
    ]

    missing_by_nutrient: dict[str, list[str]] = {}
    for attr, sku_id in missing_report:
        missing_by_nutrient.setdefault(attr, []).append(sku_id)

    return templates.TemplateResponse(request, "basket.html", {
        "hh": hh,
        "result": result,
        "targets": targets,
        "neg": neg,
        "sat_fat_ceiling": sat_fat_ceiling,
        "sodium_ceiling": sodium_ceiling,
        "added_sugar_ceiling": added_sugar_ceiling,
        "ext_nutrients": ext_nutrients,
        "missing_by_nutrient": missing_by_nutrient,
        "total_skus": len(_CATALOGUE),
        "compatible_skus": len(compatible),
        "filtered_out": len(_CATALOGUE) - len(compatible),
        "solve_ms": solve_ms,
    })


# ---------------------------------------------------------------------------
# JSON API routes (consumed by plan.html JS)
# ---------------------------------------------------------------------------


@app.get("/api/household/{household_id}")
def api_get_household(household_id: str):
    hh = _households.get(household_id)
    if hh is None:
        return JSONResponse({"detail": f"Household '{household_id}' not found"}, status_code=404)
    return JSONResponse(_hh_dict(hh))


@app.get("/api/catalogue")
def api_get_catalogue(household_id: str = Query(...)):
    hh = _households.get(household_id)
    if hh is None:
        return JSONResponse({"detail": f"Household '{household_id}' not found"}, status_code=404)
    compatible = [s for s in _CATALOGUE if s.is_compatible_with(hh)]
    return JSONResponse({
        "household_id": household_id,
        "total_skus": len(_CATALOGUE),
        "compatible_skus": len(compatible),
        "filtered_out": len(_CATALOGUE) - len(compatible),
        "skus": [
            {
                "sku_id": s.sku_id,
                "name": s.name,
                "brand": s.brand,
                "price_inr": s.price_inr,
                "pack_size_g": s.pack_size_g,
                "tags": sorted(s.ingredient_tags),
            }
            for s in compatible
        ],
        "powered_by": "Swiggy Instamart",
    })


@app.post("/api/cycle")
async def api_post_cycle(body: CycleRequest):
    hh = _households.get(body.household_id)
    if hh is None:
        return JSONResponse({"detail": f"Household '{body.household_id}' not found"}, status_code=404)

    compatible = [s for s in _CATALOGUE if s.is_compatible_with(hh)]
    pantry = _pantries.get(body.household_id, [])
    opt = optimise_basket(hh, compatible, pantry)
    filtered_out = len(_CATALOGUE) - len(compatible)

    sid = f"sid_{uuid.uuid4().hex[:12]}"
    ttl = 14400
    _sessions[sid] = _Session(household_id=hh.household_id, opt=opt, ttl=ttl)

    return JSONResponse(_cycle_dict(sid, hh, opt, filtered_out, ttl, compatible))


@app.post("/api/cycle/{session_id}/confirm")
async def api_post_confirm(session_id: str, body: ConfirmRequest):
    session = _sessions.get(session_id)
    if session is None:
        return JSONResponse({"detail": "Session not found"}, status_code=404)
    if session.expired():
        del _sessions[session_id]
        return JSONResponse({"detail": "Session expired"}, status_code=410)

    del _sessions[session_id]

    if body.action == "cancel":
        return JSONResponse({
            "session_id": session_id,
            "status": "CANCELLED",
            "order_id": None,
            "powered_by": "Swiggy Instamart",
        })

    order_id = f"SWG-{uuid.uuid4().hex[:8].upper()}"
    return JSONResponse({
        "session_id": session_id,
        "status": "PLACED",
        "order_id": order_id,
        "powered_by": "Swiggy Instamart",
    })
