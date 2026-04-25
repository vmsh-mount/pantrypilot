"""
Tests for the planner loop (step 3).

These tests verify pipeline wiring, not optimization logic. The optimizer's
correctness is already covered by test_optimizer.py. Tests here focus on:
  - Do the five stages connect and produce the right status?
  - Does pantry state update correctly after placement?
  - Does declining the prompt prevent an order?
  - Does dietary safety hold end-to-end through the full cycle?

Run from the pantrypilot/ project root:
    python3 tests/test_planner.py
"""

import dataclasses
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from fixtures.household import fixture_household, fixture_pantry
from fixtures.instamart_catalogue import fixture_catalogue
from pantrypilot.mcp_client import MockInstamartClient
from pantrypilot.planner import InMemoryPantryStore, PantryPilotAgent


def _make_agent(pantry=None):
    hh = fixture_household()
    agent = PantryPilotAgent(
        mcp=MockInstamartClient(catalogue=fixture_catalogue()),
        pantry_store=InMemoryPantryStore(
            {hh.household_id: pantry if pantry is not None else fixture_pantry()}
        ),
    )
    return agent, hh


def test_full_cycle_returns_placed():
    agent, hh = _make_agent()
    result = agent.run_weekly_cycle(hh, auto_confirm=True)
    assert result.status == "PLACED", f"Expected PLACED, got {result.status}"
    assert result.order_id is not None
    assert result.order_id.startswith("MOCK-")
    assert result.error is None


def test_optimization_result_always_present():
    """PlannerResult.optimization is populated regardless of confirm/place outcome."""
    agent, hh = _make_agent()
    result = agent.run_weekly_cycle(hh, auto_confirm=True)
    assert result.optimization is not None
    assert result.optimization.basket is not None
    assert result.optimization.status == "OPTIMAL"


def test_no_incompatible_skus_in_placed_order():
    """Dietary safety must hold end-to-end — no forbidden item reaches the MCP client."""
    agent, hh = _make_agent()
    result = agent.run_weekly_cycle(hh, auto_confirm=True)
    excluded = hh.excluded_tags()
    for line in result.optimization.basket.lines:
        violations = line.sku.ingredient_tags & excluded
        assert not violations, (
            f"{line.sku.sku_id} in placed order contains excluded tags: {violations}"
        )


def test_pantry_updated_after_successful_placement():
    """Each ordered item must increment pantry stock by (quantity × pack_size_g)."""
    hh = fixture_household()
    store = InMemoryPantryStore({hh.household_id: fixture_pantry()})
    agent = PantryPilotAgent(
        mcp=MockInstamartClient(catalogue=fixture_catalogue()),
        pantry_store=store,
    )

    before = {item.sku_id: item.quantity_g for item in store.load(hh.household_id)}
    result = agent.run_weekly_cycle(hh, auto_confirm=True)
    after  = {item.sku_id: item.quantity_g for item in store.load(hh.household_id)}

    assert result.status == "PLACED"
    for line in result.optimization.basket.lines:
        expected_added = line.sku.pack_size_g * line.quantity
        before_qty = before.get(line.sku.sku_id, 0)
        after_qty  = after.get(line.sku.sku_id, 0)
        assert after_qty == before_qty + expected_added, (
            f"{line.sku.sku_id}: expected {before_qty + expected_added:.0f} g "
            f"in pantry after order, got {after_qty:.0f} g"
        )


def test_declined_does_not_place_order():
    """Responding 'n' at the confirm prompt must return DECLINED without placing."""
    hh = fixture_household()
    store = InMemoryPantryStore({hh.household_id: fixture_pantry()})
    agent = PantryPilotAgent(
        mcp=MockInstamartClient(catalogue=fixture_catalogue()),
        pantry_store=store,
    )
    before = {item.sku_id: item.quantity_g for item in store.load(hh.household_id)}

    with patch("builtins.input", return_value="n"):
        result = agent.run_weekly_cycle(hh, auto_confirm=False)

    assert result.status == "DECLINED"
    assert result.order_id is None

    after = {item.sku_id: item.quantity_g for item in store.load(hh.household_id)}
    assert before == after, "Pantry must not change when the order is declined"


def test_confirmed_via_prompt_places_order():
    """Responding 'y' at the prompt must proceed to placement."""
    agent, hh = _make_agent()
    with patch("builtins.input", return_value="y"):
        result = agent.run_weekly_cycle(hh, auto_confirm=False)
    assert result.status == "PLACED"
    assert result.order_id is not None


def test_empty_pantry_cycle_completes():
    """Cycle must complete even when the household has no pantry stock at all."""
    agent, hh = _make_agent(pantry=[])
    result = agent.run_weekly_cycle(hh, auto_confirm=True)
    assert result.status == "PLACED"
    assert result.optimization.basket.lines, "Basket should not be empty"


def test_cycle_time_under_200ms():
    """Full cycle including optimizer solve must complete in under 200 ms."""
    agent, hh = _make_agent()
    result = agent.run_weekly_cycle(hh, auto_confirm=True)
    assert result.cycle_time_ms < 200, (
        f"Cycle took {result.cycle_time_ms:.0f} ms — expected < 200 ms"
    )


def test_zero_budget_cycle_completes_gracefully():
    """
    Zero-budget household: optimizer returns OPTIMAL with an empty basket
    (buying nothing is always feasible). The cycle should complete without
    raising an exception.
    """
    hh = dataclasses.replace(fixture_household(), weekly_budget_inr=0)
    agent = PantryPilotAgent(
        mcp=MockInstamartClient(catalogue=fixture_catalogue()),
        pantry_store=InMemoryPantryStore({hh.household_id: []}),
    )
    result = agent.run_weekly_cycle(hh, auto_confirm=True)
    assert result.status in ("PLACED", "INFEASIBLE")
    if result.status == "PLACED":
        assert result.optimization.basket.lines == []


if __name__ == "__main__":
    tests = [
        test_full_cycle_returns_placed,
        test_optimization_result_always_present,
        test_no_incompatible_skus_in_placed_order,
        test_pantry_updated_after_successful_placement,
        test_declined_does_not_place_order,
        test_confirmed_via_prompt_places_order,
        test_empty_pantry_cycle_completes,
        test_cycle_time_under_200ms,
        test_zero_budget_cycle_completes_gracefully,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
