from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm.provider import DBCache, get_provider
from ..models import IDP, Role, User
from ..security import current_user, get_employee_checked, require_roles
from ..services.career import audit
from ..services.idp import build_plan, save_idp
from .serializers import idp_dict

router = APIRouter(prefix="/api/idp", tags=["idp"])


class NewIDP(BaseModel):
    employee_id: int
    role_id: int | None = None
    lang: str = "kk"
    use_llm: bool = True


@router.post("")
def create(body: NewIDP, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, body.employee_id)
    role = db.get(Role, body.role_id or e.target_role_id or 0)
    if not role:
        raise HTTPException(400, "Мақсатты рөл таңдалмаған / Целевая роль не выбрана")
    provider = get_provider(DBCache(db)) if body.use_llm else None
    plan = build_plan(db, e, role, body.lang if body.lang in ("kk", "ru") else "kk", provider)
    return idp_dict(save_idp(db, e, role, plan, user.id, user.username))


@router.get("")
def list_idp(employee_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    rows = db.scalars(select(IDP).where(IDP.employee_id == e.id).order_by(IDP.version.desc())).all()
    return [idp_dict(i) for i in rows]


def _get(db: Session, user: User, idp_id: int) -> IDP:
    i = db.get(IDP, idp_id)
    if not i:
        raise HTTPException(404, "IDP not found")
    get_employee_checked(db, user, i.employee_id)
    return i


@router.get("/{idp_id}")
def get_one(idp_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return idp_dict(_get(db, user, idp_id))


@router.post("/{idp_id}/submit")
def submit(idp_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    i = _get(db, user, idp_id)
    if i.status not in ("draft", "returned"):
        raise HTTPException(400, f"Status is {i.status}")
    i.status = "submitted"
    audit(db, user.username, "submit_idp", None, i.employee_id, detail={"idp_id": i.id, "version": i.version})
    db.commit()
    return idp_dict(i)


class Decision(BaseModel):
    decision: str  # approved | returned
    comment: str = ""


@router.patch("/{idp_id}/approve")
def approve(idp_id: int, body: Decision, db: Session = Depends(get_db),
            user: User = Depends(require_roles("manager"))):
    i = _get(db, user, idp_id)
    if body.decision not in ("approved", "returned"):
        raise HTTPException(400, "decision must be approved|returned")
    if i.status != "submitted":
        raise HTTPException(400, "Тек жіберілген ЖДЖ келісіледі / Согласовать можно только отправленный ИПР")
    i.status = body.decision
    i.manager_comment = body.comment
    i.approved_by = user.id if body.decision == "approved" else None
    audit(db, user.username, f"idp_{body.decision}", None, i.employee_id,
          detail={"idp_id": i.id, "version": i.version, "comment": body.comment})
    db.commit()
    return idp_dict(i)
