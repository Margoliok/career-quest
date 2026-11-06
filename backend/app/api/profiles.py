from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import IDP, Document, Employee, EmployeeSkill, Role, Skill, User
from ..security import current_user, get_employee_checked, require_roles
from ..services import career
from ..services.parsing import extract_text
from .serializers import employee_dict

router = APIRouter(prefix="/api", tags=["profiles"])


@router.get("/employees")
def list_employees(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Employee).order_by(Employee.code)
    if user.role == "manager":
        q = q.where(Employee.department_id == user.department_id)
    elif user.role == "employee":
        q = q.where(Employee.id == user.employee_id)
    emps = db.scalars(q).all()
    counts = dict(db.execute(select(EmployeeSkill.employee_id, func.count()).group_by(EmployeeSkill.employee_id)).all())
    confirmed = dict(db.execute(select(EmployeeSkill.employee_id, func.count())
                                .where(EmployeeSkill.status == "confirmed").group_by(EmployeeSkill.employee_id)).all())
    last_idp = {}
    for i in db.scalars(select(IDP).order_by(IDP.version)):
        last_idp[i.employee_id] = i.status
    out = []
    for e in emps:
        d = employee_dict(e)
        d.update(skills=counts.get(e.id, 0), confirmed=confirmed.get(e.id, 0), idp_status=last_idp.get(e.id))
        if e.target_role_id:
            d["target_coverage"] = round(career.gap_for(db, e.id, e.target_role_id).coverage, 4)
        out.append(d)
    return out


class NewProfile(BaseModel):
    code: str
    department_id: int
    current_role_id: int | None = None
    target_role_id: int | None = None
    consent: bool = Field(description="Дербес деректерді өңдеуге келісім")


@router.post("/profiles")
def create_profile(body: NewProfile, db: Session = Depends(get_db), user: User = Depends(require_roles("hr"))):
    if not body.consent:
        raise HTTPException(400, "Дербес деректерді өңдеуге келісім қажет / Требуется согласие на обработку данных")
    e = Employee(code=body.code, department_id=body.department_id, current_role_id=body.current_role_id,
                 target_role_id=body.target_role_id, consent_at=career.now())
    db.add(e)
    career.audit(db, user.username, "create_profile", detail={"code": body.code})
    db.commit()
    db.refresh(e)
    return employee_dict(e)


@router.get("/profiles/{employee_id}")
def get_profile(employee_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    d = employee_dict(e)
    docs = db.scalars(select(Document).where(Document.employee_id == e.id).order_by(Document.uploaded_at.desc())).all()
    d["documents"] = [{"id": x.id, "type": x.type, "lang": x.lang, "filename": x.filename,
                       "uploaded_at": x.uploaded_at.isoformat(), "chars": len(x.text)} for x in docs]
    d["latest_text"] = docs[0].text if docs else None
    return d


@router.post("/profiles/{employee_id}/analyze")
async def analyze(employee_id: int, file: UploadFile | None = File(None), text: str | None = Form(None),
                  use_llm: bool = Form(True), db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    if not e.consent_at:
        raise HTTPException(400, "Дербес деректерді өңдеуге келісім жоқ / Нет согласия на обработку данных")
    filename = None
    if file is not None:
        filename = file.filename
        text = extract_text(file.filename or "", await file.read())
    if not text or len(text.strip()) < 20:
        raise HTTPException(400, "Мәтін тым қысқа / Текст слишком короткий")
    return career.analyze_employee(db, e, text[:30000], actor=user.username, use_llm=use_llm, filename=filename)


@router.get("/profiles/{employee_id}/skills")
def skills(employee_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    rows = db.execute(select(EmployeeSkill, Skill).join(Skill).where(EmployeeSkill.employee_id == e.id)
                      .order_by(EmployeeSkill.level.desc(), Skill.label_en)).all()
    return [{"esco_id": s.esco_id, "label": sk.label_en, "type": sk.type, "description": sk.description[:300],
             "level": s.level, "evidence": s.evidence, "phrase": s.phrase, "source": s.source, "status": s.status,
             "confidence": s.confidence, "similarity": s.similarity,
             "confirmed_by": s.confirmed_by} for s, sk in rows]


class SkillPatch(BaseModel):
    esco_id: str
    level: int | None = Field(None, ge=1, le=4)
    status: str | None = None  # confirmed | rejected (басшы); self (қызметкердің өзін-өзі бағалауы)


@router.patch("/profiles/{employee_id}/skills")
def patch_skill(employee_id: int, body: SkillPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    row = db.scalar(select(EmployeeSkill).where(EmployeeSkill.employee_id == e.id,
                                                EmployeeSkill.esco_id == body.esco_id))
    if row is None:
        if not db.get(Skill, body.esco_id):
            raise HTTPException(404, "ESCO skill not found")
        row = EmployeeSkill(employee_id=e.id, esco_id=body.esco_id, level=body.level or 2, source="self",
                            status="auto", evidence="")
        db.add(row)
    if user.role == "manager":
        if body.level:
            row.level = body.level
        if body.status in ("confirmed", "rejected"):
            row.status = body.status
            row.confirmed_by = user.id
            if row.source != "self":
                row.source = row.source if body.level is None else "manager"
    elif user.role == "employee":
        if body.status in ("confirmed", "rejected"):
            raise HTTPException(403, "Дағдыны тек басшы растай алады / Подтверждать навык может только руководитель")
        if body.level:
            row.level = body.level
            row.source = "self"
            if row.status == "confirmed":
                row.status = "auto"  # өзгертілген деңгейді басшы қайта растауы тиіс
    else:
        raise HTTPException(403, "HR cannot edit individual skills")
    career.audit(db, user.username, "edit_skill", None, e.id, body.model_dump(), body.model_dump())
    db.commit()
    return {"ok": True, "level": row.level, "status": row.status}


class TargetBody(BaseModel):
    role_id: int


@router.put("/profiles/{employee_id}/target-role")
def set_target(employee_id: int, body: TargetBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    if not db.get(Role, body.role_id):
        raise HTTPException(404, "Role not found")
    e.target_role_id = body.role_id
    career.audit(db, user.username, "set_target_role", None, e.id, detail={"role_id": body.role_id})
    db.commit()
    return employee_dict(e)


@router.get("/profiles/{employee_id}/gap")
def gap(employee_id: int, role: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    rid = role or e.target_role_id
    if not rid:
        raise HTTPException(400, "Мақсатты рөл таңдалмаған / Целевая роль не выбрана")
    g = career.gap_for(db, e.id, rid)
    career.audit(db, user.username, "compute_gap", "compute_gap", e.id, detail={"role_id": rid,
                                                                                "coverage": round(g.coverage, 4)})
    db.commit()
    return {"role_id": rid, "coverage": round(g.coverage, 4), "total_weight": g.total_weight,
            "matched": [vars(x) for x in g.matched], "missing": [vars(x) for x in g.missing]}


@router.get("/profiles/{employee_id}/recommendations")
def recs(employee_id: int, alpha: float | None = None, top: int = 6, db: Session = Depends(get_db),
         user: User = Depends(current_user)):
    e = get_employee_checked(db, user, employee_id)
    if alpha is not None and not 0 <= alpha <= 1:
        raise HTTPException(400, "alpha ∈ [0; 1]")
    out = career.recommendations(db, e, alpha=alpha, top=top)
    career.audit(db, user.username, "suggest_roles", "suggest_roles", e.id,
                 detail={"alpha": alpha, "top": [r["code"] for r in out[:3]]})
    db.commit()
    return {"alpha": alpha if alpha is not None else career.get_settings().alpha, "current_role_id": e.current_role_id,
            "roles": out}
