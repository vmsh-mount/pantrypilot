"""
Swiggy Instamart MCP client interface and mock implementation.

The InstamartClient Protocol defines the two operations PantryPilot needs.
MockInstamartClient is injected in tests and the step-3 demo; the real
SwiggyInstamartClient (step 4) will implement the same Protocol with live
Swiggy MCP tool calls behind per-user OAuth, so no planner code changes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from pantrypilot.models import Basket, SKU


@dataclass
class PlaceResult:
    """
    Returned by InstamartClient.place_order().

    status values:
      PLACED         — order accepted
      PRICE_CHANGED  — one or more prices changed since catalogue fetch
      OUT_OF_STOCK   — one or more items unavailable at placement time
      ERROR          — unexpected failure; see error field

    PRICE_CHANGED and OUT_OF_STOCK are not triggered by the mock. They are
    defined here so the planner can handle them without code changes in step 4.
    """

    order_id: str | None
    status: str
    error: str | None = None


class InstamartClient(Protocol):
    """
    Minimal Instamart interface for v1.

    Two methods only — exactly what the planner needs. Step 4 may extend
    with get_delivery_slots() when slot selection is added to the UX.

    Platform constraints (Swiggy Builders program rules):
    - Calls are server-side only, never from the browser
    - Each call is scoped to the authenticated user's OAuth token
    - Catalogue responses must not be cached across runs
    - No speculative queries outside the active user's basket cycle
    """

    def get_catalogue(self, pincode: str) -> list[SKU]:
        """Return current in-stock SKUs with live prices for the given pincode."""
        ...

    def place_order(self, basket: Basket) -> PlaceResult:
        """Submit a confirmed basket as an Instamart order."""
        ...


class MockInstamartClient:
    """
    Deterministic stand-in for the real Swiggy Instamart MCP client.

    The catalogue is injected at construction — not hard-coded — so any
    test can supply whatever SKU list it needs.

    place_order() always succeeds with a synthetic order ID. It does not
    simulate price changes, out-of-stock, or partial fulfilment; those
    scenarios require integration tests against a staging MCP environment.
    """

    def __init__(self, catalogue: list[SKU]) -> None:
        self._catalogue = catalogue

    def get_catalogue(self, pincode: str) -> list[SKU]:
        return list(self._catalogue)

    def place_order(self, basket: Basket) -> PlaceResult:
        order_id = f"MOCK-{basket.household_id}-{int(time.time() * 1000)}"
        return PlaceResult(order_id=order_id, status="PLACED")
