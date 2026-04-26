"""
PantryPilot Web — household creation form + basket view.

Separate FastAPI app from the JSON API (pantrypilot.api).  Serves HTML via
Jinja2 templates with Pico.css.  All state is in-memory (no Postgres).

Routes:
  GET  /              → redirect to /household/new
  GET  /household/new → multi-member form
  POST /household     → validate + build Household, redirect to basket
  GET  /household/{id}/basket → run optimizer, render basket page

Start with:
  uvicorn pantrypilot.web.app:app --port 8001 --reload
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

# Allow running as __main__ from project root
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from fixtures.instamart_catalogue import fixture_catalogue
from pantrypilot.models import (
    ActivityLevel,
    Allergy,
    DietaryPattern,
    Household,
    Member,
    Sex,
)
from pantrypilot.mcp_client import MockInstamartClient
from pantrypilot.planner import InMemoryPantryStore, PantryPilotAgent
from pantrypilot.optimizer import optimise_basket

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(title="PantryPilot Web")

# In-memory household store: id → Household
_households: dict[str, Household] = {}

_CATALOGUE = fixture_catalogue()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_household(form: dict) -> Household:
    """Parse raw form data into a Household domain object."""
    name = form.get("household_name", "My Household").strip() or "My Household"
    pincode = form.get("pincode", "000000").strip() or "000000"
    budget = int(form.get("weekly_budget", 2000) or 2000)

    members: list[Member] = []
    i = 0
    while True:
        mname = form.get(f"member_name_{i}")
        if mname is None:
            break
        mname = mname.strip() or f"Member {i + 1}"
        age = int(form.get(f"member_age_{i}", 30) or 30)
        sex = Sex(form.get(f"member_sex_{i}", "male"))
        weight = float(form.get(f"member_weight_{i}", 60) or 60)
        activity = ActivityLevel(form.get(f"member_activity_{i}", "moderate"))

        # Multi-select dietary patterns
        dp_raw = form.getlist(f"member_dietary_{i}") if hasattr(form, "getlist") else (
            form.get(f"member_dietary_{i}", "vegetarian")
            if isinstance(form.get(f"member_dietary_{i}"), str)
            else form.get(f"member_dietary_{i}", ["vegetarian"])
        )
        if isinstance(dp_raw, str):
            dp_raw = [dp_raw]
        patterns = [DietaryPattern(p) for p in dp_raw if p]

        # Multi-select allergies
        allergy_raw = form.getlist(f"member_allergy_{i}") if hasattr(form, "getlist") else (
            form.get(f"member_allergy_{i}", [])
            if not isinstance(form.get(f"member_allergy_{i}"), str)
            else [form.get(f"member_allergy_{i}")]
        )
        if isinstance(allergy_raw, str):
            allergy_raw = [allergy_raw]
        allergies = [Allergy(a) for a in allergy_raw if a]

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


def _negative_ceilings(weekly_targets):
    """Return weekly upper-limit ceilings for negative nutrients."""
    # WHO sodium: 2000 mg/day
    sodium_ceiling = 2000.0 * 7 * len_members_approx(weekly_targets)
    # Sat fat: 10% of total weekly calories / 9 kcal/g
    sat_fat_ceiling = (weekly_targets.calories_kcal * 0.10) / 9.0
    # Added sugar: 25 g/day (adults), WHO free sugar <10% energy
    added_sugar_ceiling = 25.0 * 7 * 2  # rough 2-person adult equivalent

    return {
        "sodium_mg": 2000.0 * 7,           # per person × 7 days; show household-level context
        "saturated_fat_g": sat_fat_ceiling,
        "added_sugar_g": added_sugar_ceiling,
    }


def len_members_approx(targets) -> int:
    return 1   # ceilings are per-person; the UI shows absolute household total vs guideline


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/household/new", status_code=302)


@app.get("/household/new", response_class=HTMLResponse)
def get_new_household(request: Request):
    return templates.TemplateResponse(request, "household_form.html")


@app.post("/household", response_class=RedirectResponse)
async def post_household(request: Request):
    form_data = await request.form()
    form = dict(form_data)
    # Reconstruct multi-value keys (dietary patterns, allergies)
    form["_multi"] = form_data
    hh = _build_household_from_form(form_data)
    _households[hh.household_id] = hh
    return RedirectResponse(url=f"/household/{hh.household_id}/basket", status_code=303)


def _build_household_from_form(form_data) -> Household:
    """Parse ImmutableMultiDict (FastAPI form) into a Household."""
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
    pantry: list = []  # no pantry for user-created households (first run)

    t0 = time.time()
    result = optimise_basket(hh, compatible, pantry)
    solve_ms = round((time.time() - t0) * 1000)

    targets = hh.weekly_targets()
    neg = result.basket.negative_totals()
    missing_report = result.basket.missing_nutrients_report()

    # Sat-fat ceiling: 10% of weekly calories / 9 kcal/g
    sat_fat_ceiling = (targets.calories_kcal * 0.10) / 9.0
    # WHO sodium ceiling: 2000 mg/day per person × members × 7 days
    sodium_ceiling = 2000.0 * len(hh.members) * 7
    # Added sugar ceiling: 25 g/day × adults(≥18) × 7, or 50 g for household
    adults = sum(1 for m in hh.members if m.age >= 18)
    added_sugar_ceiling = max(25.0 * adults * 7, 50.0)

    # Compute extended pct bars from NFI (display only)
    ext_nutrients = [
        ("Zinc",       result.nfi.zinc_pct,       "zinc_mg"),
        ("Magnesium",  result.nfi.magnesium_pct,  "magnesium_mg"),
        ("Potassium",  result.nfi.potassium_pct,  "potassium_mg"),
        ("Vitamin A",  result.nfi.vitamin_a_pct,  "vitamin_a_mcg"),
        ("Vitamin C",  result.nfi.vitamin_c_pct,  "vitamin_c_mg"),
        ("Folate",     result.nfi.folate_pct,      "folate_mcg"),
        ("Vitamin B12", result.nfi.vitamin_b12_pct, "vitamin_b12_mcg"),
    ]

    # Group missing nutrients: nutrient → [sku_ids]
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
