"""Household purchase review; printer operations are deliberately absent."""
from datetime import date as Date
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.app.core.auth import RequireAdmin
from backend.app.core.config import settings
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
def get_ledger(user=RequireAdmin()):
    return store.read(*paths())

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
