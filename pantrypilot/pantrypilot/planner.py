"""
PantryPilot weekly planner loop — Step 3.

Wires the five pipeline stages into a single callable cycle:

    Sense → Plan → Optimize → Confirm → Place

All dependencies (MCP client, pantry store) are injected into PantryPilotAgent
at construction. Swapping MockInstamartClient for SwiggyInstamartClient and
InMemoryPantryStore for PostgresPantryStore in step 4 requires no changes here.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pantrypilot.mcp_client import InstamartClient, PlaceResult
from pantrypilot.models import (
    Basket,
    Household,
    NutrientTargets,
    PantryItem,
    SKU,
)
from pantrypilot.optimizer import OptimizationResult, optimise_basket


# ---------------------------------------------------------------------------
# Intermediate result types
# ---------------------------------------------------------------------------


@dataclass
class SenseResult:
    catalogue: list[SKU]
    pantry: list[PantryItem]


@dataclass
class PlanResult:
    compatible_skus: list[SKU]
    weekly_targets: NutrientTargets
    excluded_tags: set[str]
    excluded_count: int


@dataclass
class ConfirmResult:
    confirmed: bool
    basket: Basket | None
    reason: str   # "confirmed" | "auto-confirmed" | "declined"


@dataclass
class PlannerResult:
    """Full outcome of one weekly cycle."""

    household_id: str
    status: str              # "PLACED" | "DECLINED" | "INFEASIBLE" | "ERROR"
    optimization: OptimizationResult
    order_id: str | None
    error: str | None
    cycle_time_ms: float


# ---------------------------------------------------------------------------
# Pantry store
# ---------------------------------------------------------------------------


class PantryStore(Protocol):
    def load(self, household_id: str) -> list[PantryItem]: ...
    def save(self, household_id: str, items: list[PantryItem]) -> None: ...


class InMemoryPantryStore:
    """
    In-memory pantry store for step 3.

    Initial state is seeded at construction. Replaced by PostgresPantryStore
    in step 4 — the planner calls the same load/save interface either way.
    """

    def __init__(self, initial: dict[str, list[PantryItem]] | None = None) -> None:
        self._data: dict[str, list[PantryItem]] = {}
        if initial:
            for hh_id, items in initial.items():
                self._data[hh_id] = list(items)

    def load(self, household_id: str) -> list[PantryItem]:
        return list(self._data.get(household_id, []))

    def save(self, household_id: str, items: list[PantryItem]) -> None:
        self._data[household_id] = list(items)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_order_to_pantry(
    current: list[PantryItem],
    basket: Basket,
) -> list[PantryItem]:
    """
    Return an updated pantry list reflecting a completed order.

    Each ordered pack adds pack_size_g grams. Items already in pantry are
    incremented; new items are added. Items not in the basket are unchanged.

    No consumption model: pantry only grows here. Weekly consumption is a v2
    item that requires per-SKU usage-rate estimation.
    """
    stock = {item.sku_id: item.quantity_g for item in current}
    today = date.today()
    for line in basket.lines:
        added_g = line.sku.pack_size_g * line.quantity
        stock[line.sku.sku_id] = stock.get(line.sku.sku_id, 0) + added_g
    return [
        PantryItem(sku_id=sid, quantity_g=qty, last_updated=today)
        for sid, qty in stock.items()
    ]


def _print_confirm_summary(
    household: Household,
    result: OptimizationResult,
) -> None:
    nfi = result.nfi
    print()
    print("=" * 60)
    print("  PantryPilot — Weekly Basket  (Powered by Swiggy Instamart)")
    print("=" * 60)
    print(f"  Household  : {household.name}")
    print(f"  Spend      : ₹{result.budget_used_inr:.0f} of ₹{result.budget_total_inr:.0f}")
    print(f"  Solved in  : {result.solve_time_ms:.1f} ms")

    print("\n  ── Basket ─────────────────────────────────────────────")
    for line in sorted(result.basket.lines, key=lambda l: -l.total_price_inr()):
        est = "~" if line.sku.nutrition.is_estimated else " "
        print(f"  {est}{line.quantity:2d}×  {line.sku.name:<42s}  ₹{line.total_price_inr():>5.0f}")

    print("\n  ── Nutrition Fit Index (pantry + basket) ──────────────")
    rows = [
        ("Calories", nfi.calories_pct),
        ("Protein",  nfi.protein_pct),
        ("Fibre",    nfi.fibre_pct),
        ("Iron",     nfi.iron_pct),
        ("Calcium",  nfi.calcium_pct),
    ]
    for label, pct in rows:
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        binding = nfi.overall_pct < 100.0 and label.lower() == result.binding_nutrient
        marker = " ← binding" if binding else ""
        print(f"  {label:<10s}  {bar}  {pct:5.1f}%{marker}")
    est_note = " *" if nfi.contains_estimated else ""
    print(f"  {'─' * 52}")
    print(f"  Overall NFI  {nfi.overall_pct:.1f}%{est_note}")
    if nfi.contains_estimated:
        print("  * contains estimated nutrition values — see SKU provenance")

    if result.pantry_topup or result.overstocked_skipped:
        print("\n  ── Pantry decisions ───────────────────────────────────")
        for sid in result.pantry_topup:
            print(f"    +  {sid}  (low stock → topped up)")
        for sid in result.overstocked_skipped:
            print(f"    -  {sid}  (well-stocked → skipped)")
    print()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PantryPilotAgent:
    """
    Runs the weekly Sense → Plan → Optimize → Confirm → Place cycle.

    Inject MockInstamartClient + InMemoryPantryStore for the demo and tests.
    Inject SwiggyInstamartClient + PostgresPantryStore for production (step 4).
    """

    def __init__(self, mcp: InstamartClient, pantry_store: PantryStore) -> None:
        self._mcp = mcp
        self._pantry_store = pantry_store

    def run_weekly_cycle(
        self,
        household: Household,
        *,
        auto_confirm: bool = False,
    ) -> PlannerResult:
        """
        Execute one full weekly cycle for the given household.

        auto_confirm=False (demo default): prints the basket summary and waits
        for a [Y/n] prompt before placing the order.
        auto_confirm=True (test default): skips the prompt and confirms immediately.
        """
        t0 = time.perf_counter()

        sense  = self._sense(household)
        plan   = self._plan(household, sense)
        opt    = self._optimize(household, plan, sense.pantry)

        if opt.status not in ("OPTIMAL", "FEASIBLE"):
            return PlannerResult(
                household_id=household.household_id,
                status="INFEASIBLE",
                optimization=opt,
                order_id=None,
                error=f"Optimizer returned {opt.status}",
                cycle_time_ms=(time.perf_counter() - t0) * 1000,
            )

        confirm = self._confirm(household, opt, auto=auto_confirm)

        if not confirm.confirmed:
            return PlannerResult(
                household_id=household.household_id,
                status="DECLINED",
                optimization=opt,
                order_id=None,
                error=None,
                cycle_time_ms=(time.perf_counter() - t0) * 1000,
            )

        place = self._place(household, confirm)
        return PlannerResult(
            household_id=household.household_id,
            status=place.status,
            optimization=opt,
            order_id=place.order_id,
            error=place.error,
            cycle_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def plan_cycle(self, household: Household) -> OptimizationResult:
        """Stages 1–3 only. Returns OptimizationResult without confirming or placing."""
        sense = self._sense(household)
        plan  = self._plan(household, sense)
        return self._optimize(household, plan, sense.pantry)

    def place_confirmed(self, household: Household, opt: OptimizationResult) -> PlaceResult:
        """Stage 5 only. Called after the user has confirmed via the API."""
        confirm = ConfirmResult(confirmed=True, basket=opt.basket, reason="confirmed")
        return self._place(household, confirm)

    # ── Stages ────────────────────────────────────────────────────────────────

    def _sense(self, household: Household) -> SenseResult:
        catalogue = self._mcp.get_catalogue(household.pincode)
        pantry    = self._pantry_store.load(household.household_id)
        return SenseResult(catalogue=catalogue, pantry=pantry)

    def _plan(self, household: Household, sense: SenseResult) -> PlanResult:
        excluded   = household.excluded_tags()
        compatible = [
            s for s in sense.catalogue
            if s.is_compatible_with(household) and s.in_stock
        ]
        return PlanResult(
            compatible_skus=compatible,
            weekly_targets=household.weekly_targets(),
            excluded_tags=excluded,
            excluded_count=len(sense.catalogue) - len(compatible),
        )

    def _optimize(
        self,
        household: Household,
        plan: PlanResult,
        pantry: list[PantryItem],
    ) -> OptimizationResult:
        return optimise_basket(household, plan.compatible_skus, pantry)

    def _confirm(
        self,
        household: Household,
        result: OptimizationResult,
        *,
        auto: bool,
    ) -> ConfirmResult:
        if auto:
            return ConfirmResult(
                confirmed=True,
                basket=result.basket,
                reason="auto-confirmed",
            )

        _print_confirm_summary(household, result)

        try:
            choice = input("Confirm this basket? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "n"

        confirmed = choice in ("", "y", "yes")
        return ConfirmResult(
            confirmed=confirmed,
            basket=result.basket if confirmed else None,
            reason="confirmed" if confirmed else "declined",
        )

    def _place(self, household: Household, confirm: ConfirmResult) -> PlaceResult:
        result = self._mcp.place_order(confirm.basket)
        if result.status == "PLACED":
            current = self._pantry_store.load(household.household_id)
            updated = _apply_order_to_pantry(current, confirm.basket)
            self._pantry_store.save(household.household_id, updated)
        return result


# ---------------------------------------------------------------------------
# Demo entry point
# ---------------------------------------------------------------------------


def _demo() -> None:
    from fixtures.household import fixture_household, fixture_pantry
    from fixtures.instamart_catalogue import fixture_catalogue
    from pantrypilot.mcp_client import MockInstamartClient

    hh = fixture_household()

    agent = PantryPilotAgent(
        mcp=MockInstamartClient(catalogue=fixture_catalogue()),
        pantry_store=InMemoryPantryStore({hh.household_id: fixture_pantry()}),
    )

    result = agent.run_weekly_cycle(hh, auto_confirm=False)

    print(f"  Status    : {result.status}")
    if result.order_id:
        print(f"  Order ID  : {result.order_id}")
    print(f"  Cycle     : {result.cycle_time_ms:.1f} ms total")
    if result.error:
        print(f"  Error     : {result.error}")
    print()


if __name__ == "__main__":
    _demo()
