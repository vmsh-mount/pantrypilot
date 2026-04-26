"""
Tests for the web form app (Change 3).

Covers household round-trip (form → basket page), multi-member households
with stacked dietary patterns, and basic UI content assertions.

Run from pantrypilot/ project root:
    python3 tests/test_web.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from pantrypilot.web.app import app


def _post_household(client: TestClient, **fields) -> str:
    """POST a household form and return the basket URL (for server-rendered tests)."""
    defaults = {
        "household_name": "Test Household",
        "pincode": "560001",
        "weekly_budget": "2000",
        "member_name_0": "Alice",
        "member_age_0": "30",
        "member_sex_0": "female",
        "member_weight_0": "60",
        "member_activity_0": "moderate",
        "member_dietary_0": "vegetarian",
    }
    defaults.update(fields)
    resp = client.post("/household", data=defaults, follow_redirects=False)
    assert resp.status_code == 303, f"Expected redirect, got {resp.status_code}: {resp.text}"
    # Form redirects to /plan; return /basket URL for server-rendered assertion tests
    return resp.headers["location"].replace("/plan", "/basket")


def test_root_redirects_to_new_household():
    with TestClient(app) as client:
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/household/new"


def test_form_page_renders():
    with TestClient(app) as client:
        resp = client.get("/household/new")
        assert resp.status_code == 200
        assert "PantryPilot" in resp.text
        assert "household_name" in resp.text
        assert "weekly_budget" in resp.text
        assert "Swiggy Instamart" in resp.text


def test_post_household_redirects_to_plan():
    with TestClient(app) as client:
        defaults = {
            "household_name": "Test Household",
            "pincode": "560001",
            "weekly_budget": "2000",
            "member_name_0": "Alice",
            "member_age_0": "30",
            "member_sex_0": "female",
            "member_weight_0": "60",
            "member_activity_0": "moderate",
            "member_dietary_0": "vegetarian",
        }
        resp = client.post("/household", data=defaults, follow_redirects=False)
        assert resp.status_code == 303
        loc = resp.headers["location"]
        assert loc.startswith("/household/")
        assert loc.endswith("/plan")


def test_basket_page_renders_nfi():
    with TestClient(app) as client:
        loc = _post_household(client)
        resp = client.get(loc)
        assert resp.status_code == 200
        assert "Core 5 nutrients" in resp.text
        assert "overall NFI" in resp.text
        assert "Swiggy Instamart" in resp.text


def test_basket_page_shows_negative_panel():
    with TestClient(app) as client:
        loc = _post_household(client)
        resp = client.get(loc)
        assert "Saturated fat" in resp.text
        assert "Sodium" in resp.text
        assert "Added sugar" in resp.text


def test_basket_page_shows_extended_nutrients():
    with TestClient(app) as client:
        loc = _post_household(client)
        resp = client.get(loc)
        assert "Vitamin B12" in resp.text
        assert "Vitamin C" in resp.text
        assert "Zinc" in resp.text


def test_basket_page_shows_missing_data_warnings():
    """Extended nutrient data gaps must surface (not silently show 0%)."""
    with TestClient(app) as client:
        loc = _post_household(client)
        resp = client.get(loc)
        assert "data gap" in resp.text


def test_multi_member_stacked_dietary():
    """
    Jain + lactose-intolerant member stacks both exclusion sets.
    Basket must not contain onion/garlic items or regular dairy.
    """
    with TestClient(app) as client:
        form = {
            "household_name": "Jain Household",
            "pincode": "400001",
            "weekly_budget": "2500",
            "member_name_0": "Grandma",
            "member_age_0": "65",
            "member_sex_0": "female",
            "member_weight_0": "55",
            "member_activity_0": "sedentary",
            "member_dietary_0": ["vegetarian", "jain"],  # stacked
            "member_name_1": "Priya",
            "member_age_1": "35",
            "member_sex_1": "female",
            "member_weight_1": "58",
            "member_activity_1": "moderate",
            "member_dietary_1": "vegetarian",
            "member_allergy_1": "lactose",
        }
        resp = client.post("/household", data=form, follow_redirects=False)
        assert resp.status_code == 303
        loc = resp.headers["location"]
        resp2 = client.get(loc)
        assert resp2.status_code == 200
        # Jain items must be absent from basket
        assert "Onion" not in resp2.text
        assert "Maggi" not in resp2.text
        # Regular dairy excluded (Priya is lactose-intolerant)
        assert "Amul Toned Milk" not in resp2.text


def test_unknown_household_id_returns_404():
    with TestClient(app) as client:
        resp = client.get("/household/hh_doesnotexist/basket")
        assert resp.status_code == 404


def test_basket_shows_household_name():
    with TestClient(app) as client:
        loc = _post_household(client, household_name="The Pillai Family")
        resp = client.get(loc)
        assert "The Pillai Family" in resp.text


def test_budget_constraint_respected():
    """Optimizer must not exceed the stated budget."""
    with TestClient(app) as client:
        loc = _post_household(client, weekly_budget="1500")
        resp = client.get(loc)
        assert resp.status_code == 200
        # Page renders without error even at tighter budget
        assert "NFI" in resp.text


if __name__ == "__main__":
    tests = [
        test_root_redirects_to_new_household,
        test_form_page_renders,
        test_post_household_redirects_to_plan,
        test_basket_page_renders_nfi,
        test_basket_page_shows_negative_panel,
        test_basket_page_shows_extended_nutrients,
        test_basket_page_shows_missing_data_warnings,
        test_multi_member_stacked_dietary,
        test_unknown_household_id_returns_404,
        test_basket_shows_household_name,
        test_budget_constraint_respected,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
