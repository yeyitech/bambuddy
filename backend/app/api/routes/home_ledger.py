"""Household purchase review; printer operations are deliberately absent."""
from datetime import date as Date
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, Field
from backend.app.core.auth import RequireAdmin
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.spool import Spool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.services import home_ledger_store as store

router = APIRouter(prefix="/home-ledger", tags=["home-ledger"])

class OrderPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    paid_cny: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    due_cny: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    quantity: int | None = Field(default=None, ge=1, le=100000)
    date: Date | None = None
    order_no: str | None = Field(default=None, max_length=100)
    item: str | None = Field(default=None, min_length=1, max_length=500)
    shop: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)

def paths():
    return settings.base_dir / "home-ledger.sqlite", settings.base_dir / "home-ledger-seed.json"

@router.get("")
async def get_ledger(user=RequireAdmin(), db: AsyncSession = Depends(get_db)):
    result = store.read(*paths())
    from backend.app.services.home_material_accounting import summary
    material = summary(settings.base_dir)
    planned = {}
    for job in material.get("running", []):
        for usage in job["planned_usage"]:
            sid = usage["spool_id"]
            planned[sid] = planned.get(sid, 0) + usage["grams"]
    # Inventory is authoritative after a user adjusts or weighs a spool.
    linked = {s.get("inventory_spool_id") for s in result["data"].get("filament_units", [])}
    linked.discard(None)
    if linked:
        spools = {s.id: s for s in (await db.execute(select(Spool).where(Spool.id.in_(linked)))).scalars()}
        for unit in result["data"].get("filament_units", []):
            spool = spools.get(unit.get("inventory_spool_id"))
            if spool is None:
                continue
            known = spool.label_weight > 0
            unit["pending_print_g"] = round(planned.get(spool.id, 0), 2)
            unit["estimated_remaining_after_pending_g"] = None
            unit["estimated_used_g"] = round(spool.weight_used, 2)
            unit["nominal_g"] = spool.label_weight if known else None
            unit["estimated_remaining_g"] = round(max(0, spool.label_weight - spool.weight_used), 2) if known else None
            if known and unit.get("pending_print_g"):
                unit["estimated_remaining_after_pending_g"] = round(max(0, spool.label_weight - spool.weight_used - unit["pending_print_g"]), 2)
    return result

@router.patch("/orders/{order_id}")
def patch_order(order_id: str, patch: OrderPatch, user=RequireAdmin()):
    changes = patch.model_dump(mode="json", exclude_unset=True, exclude={"revision"})
    for key in ("paid_cny", "due_cny"):
        if key in changes and changes[key] is not None:
            changes[key] = float(changes[key])
    for key in ("item", "shop", "status"):
        if key in changes and changes[key] is None:
            raise HTTPException(422, f"{key} cannot be null")
    try:
        return store.update_order(paths()[0], order_id, changes, patch.revision, user.username)
    except store.ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, "记录不存在") from exc



class WasteMeasurement(BaseModel):
    waste_g: float = Field(ge=0, allow_inf_nan=False)
    note: str = Field(min_length=1, max_length=1000)

@router.get("/material-accounting")
def get_material_accounting(user=RequireAdmin()):
    from backend.app.services.home_material_accounting import summary
    return summary(settings.base_dir)

@router.put("/material-accounting/{run_id}/waste")
def put_material_waste(run_id: int, body: WasteMeasurement, user=RequireAdmin()):
    from backend.app.services.home_material_accounting import record_waste, summary
    try:
        record_waste(settings.base_dir, run_id, body.waste_g, body.note, user.username)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return summary(settings.base_dir)
