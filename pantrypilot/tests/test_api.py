"""
Tests for the FastAPI surface (step 4).

Uses FastAPI's TestClient (backed by httpx). No live server needed.
Each test creates a fresh TestClient so the lifespan re-initialises app
state — pantry store, session dict, and household registry all start clean.

Run from the pantrypilot/ project root:
    python3 tests/test_api.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from pantrypilot.api import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cycle(client: TestClient, household_id: str = "hh_demo_001") -> dict:
    resp = client.post("/cycle", json={"household_id": household_id})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /household
# ---------------------------------------------------------------------------


def test_get_household_returns_sharma():
    with TestClient(app) as client:
        resp = client.get("/household/hh_demo_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["household_id"] == "hh_demo_001"
        assert len(data["members"]) == 4


def test_unknown_household_returns_404():
    with TestClient(app) as client:
        resp = client.get("/household/unknown_hh")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /catalogue
# ---------------------------------------------------------------------------


def test_catalogue_filters_incompatible_skus():
    with TestClient(app) as client:
        resp = client.get("/catalogue", params={"household_id": "hh_demo_001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_skus"] == 31
        assert data["compatible_skus"] == 21
        assert data["filtered_out"] == 10
        assert data["powered_by"] == "Swiggy Instamart"
        assert len(data["skus"]) == 21


def test_catalogue_unknown_household_returns_404():
    with TestClient(app) as client:
        resp = client.get("/catalogue", params={"household_id": "nope"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /cycle
# ---------------------------------------------------------------------------


def test_cycle_returns_ready_to_confirm():
    with TestClient(app) as client:
        data = _cycle(client)
        assert data["status"] == "READY_TO_CONFIRM"
        assert "session_id" in data
        assert len(data["session_id"]) == 36  # uuid4


def test_cycle_basket_has_no_incompatible_skus():
    """Dietary safety must hold end-to-end through the API."""
    with TestClient(app) as client:
        data = _cycle(client)
        # Tags that must never appear in a Sharma basket
        forbidden_tags = {
            "dairy", "peanut", "onion", "garlic", "potato",
            "ginger", "carrot", "radish", "beetroot", "sweet_potato",
        }
        for line in data["basket"]:
            assert not set(line.get("tags", [])) & forbidden_tags, (
                f"{line['sku_id']} contains a forbidden tag"
            )
        # Spot check: none of the well-known incompatible sku_ids present
        sku_ids = {line["sku_id"] for line in data["basket"]}
        incompatible = {
            "sku_onion_1kg", "sku_milk_amul_1l", "sku_peanut_chikki_200g",
            "sku_paneer_milky_mist_200g", "sku_curd_nandini_400g",
        }
        assert not sku_ids & incompatible, f"Incompatible SKUs found: {sku_ids & incompatible}"


def test_cycle_response_has_powered_by():
    with TestClient(app) as client:
        data = _cycle(client)
        assert data["powered_by"] == "Swiggy Instamart"


def test_basket_lines_have_reason():
    with TestClient(app) as client:
        data = _cycle(client)
        assert data["basket"], "Basket should not be empty"
        for line in data["basket"]:
            assert line["reason"], (
                f"Line {line['sku_id']} has an empty reason string"
            )


def test_cycle_unknown_household_returns_404():
    with TestClient(app) as client:
        resp = client.post("/cycle", json={"household_id": "unknown"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /cycle/{session_id}/confirm
# ---------------------------------------------------------------------------


def test_confirm_places_order():
    with TestClient(app) as client:
        cycle = _cycle(client)
        session_id = cycle["session_id"]
        resp = client.post(
            f"/cycle/{session_id}/confirm", json={"action": "confirm"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PLACED"
        assert data["order_id"] is not None
        assert data["order_id"].startswith("MOCK-")
        assert data["powered_by"] == "Swiggy Instamart"


def test_cancel_returns_cancelled():
    with TestClient(app) as client:
        cycle = _cycle(client)
        session_id = cycle["session_id"]
        resp = client.post(
            f"/cycle/{session_id}/confirm", json={"action": "cancel"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "CANCELLED"
        assert data["order_id"] is None


def test_confirm_session_not_reusable():
    """A session_id must not be usable a second time."""
    with TestClient(app) as client:
        cycle = _cycle(client)
        session_id = cycle["session_id"]
        client.post(f"/cycle/{session_id}/confirm", json={"action": "confirm"})
        resp = client.post(
            f"/cycle/{session_id}/confirm", json={"action": "confirm"}
        )
        assert resp.status_code == 404


def test_expired_session_returns_410():
    with TestClient(app) as client:
        cycle = _cycle(client)
        session_id = cycle["session_id"]
        # Force the session to look expired
        app.state.sessions[session_id].ttl_seconds = 0
        resp = client.post(
            f"/cycle/{session_id}/confirm", json={"action": "confirm"}
        )
        assert resp.status_code == 410


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    tests = [
        test_get_household_returns_sharma,
        test_unknown_household_returns_404,
        test_catalogue_filters_incompatible_skus,
        test_catalogue_unknown_household_returns_404,
        test_cycle_returns_ready_to_confirm,
        test_cycle_basket_has_no_incompatible_skus,
        test_cycle_response_has_powered_by,
        test_basket_lines_have_reason,
        test_cycle_unknown_household_returns_404,
        test_confirm_places_order,
        test_cancel_returns_cancelled,
        test_confirm_session_not_reusable,
        test_expired_session_returns_410,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
