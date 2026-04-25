
"""
PantryPilot FastAPI surface — Step 4.

Endpoints:
    GET  /household/{household_id}        — household profile (Loom intro)
    GET  /catalogue?household_id=...      — filtered SKU list (shows dietary filter step)
    POST /cycle                           — Sense → Plan → Optimize; returns basket + session_id
    POST /cycle/{session_id}/confirm      — confirm or cancel a pending basket

Session store: in-memory dict with 4-hour TTL.
Step 5 upgrade path: replace the dict with Redis SET key value EX 14400.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

_STATIC = Path(__file__).parent / "static"

from pantrypilot.mcp_client import MockInstamartClient
from pantrypilot.models import Household
from pantrypilot.optimizer import OptimizationResult
from pantrypilot.planner import InMemoryPantryStore, PantryPilotAgent

from fixtures.household import fixture_household, fixture_pantry
from fixtures.instamart_catalogue import fixture_catalogue


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------


@dataclass
class PendingSession:
    household_id: str
    optimization: OptimizationResult
    created_at: float
    ttl_seconds: int = 14400  # 4 hours

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    hh = fixture_household()
    app.state.agent = PantryPilotAgent(
        mcp=MockInstamartClient(catalogue=fixture_catalogue()),
        pantry_store=InMemoryPantryStore({hh.household_id: fixture_pantry()}),
    )
    app.state.sessions: dict[str, PendingSession] = {}
    app.state.households: dict[str, Household] = {hh.household_id: hh}
    yield


app = FastAPI(title="PantryPilot", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CycleRequest(BaseModel):
    household_id: str = "hh_demo_001"


class ConfirmRequest(BaseModel):
    action: Literal["confirm", "cancel"]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MemberResponse(BaseModel):
    name: str
    age: int
    dietary_patterns: list[str]
    allergies: list[str]


class HouseholdResponse(BaseModel):
    household_id: str
    name: str
    weekly_budget_inr: int
    pincode: str
    members: list[MemberResponse]
    powered_by: str = "Swiggy Instamart"


class CatalogueSkuResponse(BaseModel):
    sku_id: str
    name: str
    brand: str
    price_inr: float
    pack_size_g: float
    tags: list[str]


class CatalogueResponse(BaseModel):
    household_id: str
    total_skus: int
    compatible_skus: int
    filtered_out: int
    skus: list[CatalogueSkuResponse]
    powered_by: str = "Swiggy Instamart"


class BasketLineResponse(BaseModel):
    sku_id: str
    name: str
    brand: str
    quantity: int
    pack_size_g: float
    price_inr: float
    total_price_inr: float
    nutrition_estimated: bool
    reason: str


class NFIResponse(BaseModel):
    calories_pct: float
    protein_pct: float
    fibre_pct: float
    iron_pct: float
    calcium_pct: float
    overall_pct: float
    contains_estimated: bool


class CycleResponse(BaseModel):
    session_id: str
    household_id: str
    status: str
    basket: list[BasketLineResponse]
    nfi: NFIResponse
    budget_used_inr: float
    budget_total_inr: float
    binding_nutrient: str
    overstocked_skipped: list[str]
    pantry_topup: list[str]
    skus_filtered_out: int
    solve_time_ms: float
    confirm_before: str
    powered_by: str = "Swiggy Instamart"


class ConfirmResponse(BaseModel):
    session_id: str
    status: str
    order_id: str | None
    powered_by: str = "Swiggy Instamart"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _household_response(hh: Household) -> HouseholdResponse:
    return HouseholdResponse(
        household_id=hh.household_id,
        name=hh.name,
        weekly_budget_inr=hh.weekly_budget_inr,
        pincode=hh.pincode,
        members=[
            MemberResponse(
                name=m.name,
                age=m.age,
                dietary_patterns=[p.value for p in m.dietary_patterns],
                allergies=[a.value for a in m.allergies],
            )
            for m in hh.members
        ],
    )


def _cycle_response(
    session_id: str,
    household_id: str,
    opt: OptimizationResult,
    skus_filtered_out: int,
    ttl_seconds: int,
) -> CycleResponse:
    confirm_before = datetime.fromtimestamp(
        time.time() + ttl_seconds, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return CycleResponse(
        session_id=session_id,
        household_id=household_id,
        status="READY_TO_CONFIRM",
        basket=[
            BasketLineResponse(
                sku_id=line.sku.sku_id,
                name=line.sku.name,
                brand=line.sku.brand,
                quantity=line.quantity,
                pack_size_g=line.sku.pack_size_g,
                price_inr=line.sku.price_inr,
                total_price_inr=line.total_price_inr(),
                nutrition_estimated=line.sku.nutrition.is_estimated,
                reason=line.reason,
            )
            for line in opt.basket.lines
        ],
        nfi=NFIResponse(
            calories_pct=opt.nfi.calories_pct,
            protein_pct=opt.nfi.protein_pct,
            fibre_pct=opt.nfi.fibre_pct,
            iron_pct=opt.nfi.iron_pct,
            calcium_pct=opt.nfi.calcium_pct,
            overall_pct=opt.nfi.overall_pct,
            contains_estimated=opt.nfi.contains_estimated,
        ),
        budget_used_inr=opt.budget_used_inr,
        budget_total_inr=opt.budget_total_inr,
        binding_nutrient=opt.binding_nutrient,
        overstocked_skipped=opt.overstocked_skipped,
        pantry_topup=opt.pantry_topup,
        skus_filtered_out=skus_filtered_out,
        solve_time_ms=opt.solve_time_ms,
        confirm_before=confirm_before,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def get_ui() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


@app.get("/household/{household_id}", response_model=HouseholdResponse)
def get_household(household_id: str, request: Request) -> HouseholdResponse:
    hh = request.app.state.households.get(household_id)
    if hh is None:
        raise HTTPException(status_code=404, detail=f"Household '{household_id}' not found")
    return _household_response(hh)


@app.get("/catalogue", response_model=CatalogueResponse)
def get_catalogue(
    request: Request, household_id: str = Query(...)
) -> CatalogueResponse:
    hh = request.app.state.households.get(household_id)
    if hh is None:
        raise HTTPException(status_code=404, detail=f"Household '{household_id}' not found")
    agent: PantryPilotAgent = request.app.state.agent
    all_skus = agent._mcp.get_catalogue(hh.pincode)
    compatible = [s for s in all_skus if s.is_compatible_with(hh) and s.in_stock]
    return CatalogueResponse(
        household_id=household_id,
        total_skus=len(all_skus),
        compatible_skus=len(compatible),
        filtered_out=len(all_skus) - len(compatible),
        skus=[
            CatalogueSkuResponse(
                sku_id=s.sku_id,
                name=s.name,
                brand=s.brand,
                price_inr=s.price_inr,
                pack_size_g=s.pack_size_g,
                tags=sorted(s.ingredient_tags),
            )
            for s in compatible
        ],
    )


@app.post("/cycle", response_model=CycleResponse)
def post_cycle(body: CycleRequest, request: Request) -> CycleResponse:
    hh = request.app.state.households.get(body.household_id)
    if hh is None:
        raise HTTPException(status_code=404, detail=f"Household '{body.household_id}' not found")

    agent: PantryPilotAgent = request.app.state.agent
    all_skus = agent._mcp.get_catalogue(hh.pincode)
    compatible_count = sum(1 for s in all_skus if s.is_compatible_with(hh) and s.in_stock)

    opt = agent.plan_cycle(hh)

    session_id = str(uuid.uuid4())
    ttl = 14400
    request.app.state.sessions[session_id] = PendingSession(
        household_id=hh.household_id,
        optimization=opt,
        created_at=time.time(),
        ttl_seconds=ttl,
    )

    return _cycle_response(
        session_id, hh.household_id, opt,
        len(all_skus) - compatible_count, ttl,
    )


@app.post("/cycle/{session_id}/confirm", response_model=ConfirmResponse)
def post_confirm(
    session_id: str, body: ConfirmRequest, request: Request
) -> ConfirmResponse:
    sessions: dict[str, PendingSession] = request.app.state.sessions
    session = sessions.get(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.is_expired():
        del sessions[session_id]
        raise HTTPException(status_code=410, detail="Session expired")

    del sessions[session_id]  # no replay — key is gone whether confirm or cancel

    if body.action == "cancel":
        return ConfirmResponse(session_id=session_id, status="CANCELLED", order_id=None)

    hh: Household = request.app.state.households[session.household_id]
    agent: PantryPilotAgent = request.app.state.agent
    place = agent.place_confirmed(hh, session.optimization)
    return ConfirmResponse(
        session_id=session_id, status=place.status, order_id=place.order_id
    )
