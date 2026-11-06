from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, Course, Department, Employee, EmployeeSkill, Role, RoleSkill, Skill, User
from ..security import current_user, require_roles
from ..services.career import audit, course_dict, gap_for

router = APIRouter(prefix="/api/hr", tags=["hr"])


@router.get("/departments")
def departments(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"id": d.id, "name_kk": d.name_kk, "name_ru": d.name_ru} for d in db.scalars(select(Department))]


class RoleSkillIn(BaseModel):
    esco_id: str
    weight: float = Field(ge=0, le=2)
    required_level: int = Field(ge=1, le=4)
    relation: str = "expert"


@router.put("/roles/{role_id}/skills")
def put_role_skills(role_id: int, items: list[RoleSkillIn], db: Session = Depends(get_db),
                    user: User = Depends(require_roles("hr"))):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    old = {rs.esco_id: rs for rs in role.skills}
    db.execute(delete(RoleSkill).where(RoleSkill.role_id == role_id))
    for it in items:
        if not db.get(Skill, it.esco_id):
            raise HTTPException(400, f"Unknown ESCO id {it.esco_id}")
        src = old[it.esco_id].source if it.esco_id in old and old[it.esco_id].weight == it.weight \
            and old[it.esco_id].required_level == it.required_level else "expert"
        db.add(RoleSkill(role_id=role_id, esco_id=it.esco_id, weight=it.weight, required_level=it.required_level,
                         relation=it.relation, source=src))
    audit(db, user.username, "edit_role_profile", detail={"role": role.code, "skills": len(items)})
    db.commit()
    return {"ok": True, "skills": len(items)}


class CourseIn(BaseModel):
    title: str
    provider: str
    url: str = ""
    lang: str = "kk"
    level: str = ""
    esco_ids: list[str] = []
    duration_h: float | None = None
    is_free: bool = True
    description: str = ""


@router.get("/courses")
def courses(db: Session = Depends(get_db), _: User = Depends(current_user)):
    labels = dict(db.execute(select(Skill.esco_id, Skill.label_en)).all())
    out = []
    for c in db.scalars(select(Course).order_by(Course.provider, Course.title)):
        d = course_dict(c)
        d["skills"] = [labels.get(x, x) for x in c.esco_ids or []]
        out.append(d)
    return out


@router.post("/courses")
def add_course(body: CourseIn, db: Session = Depends(get_db), user: User = Depends(require_roles("hr"))):
    c = Course(**body.model_dump())
    db.add(c)
    audit(db, user.username, "add_course", detail={"title": body.title})
    db.commit()
    return course_dict(c)


@router.delete("/courses/{course_id}")
def del_course(course_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("hr"))):
    c = db.get(Course, course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    db.delete(c)
    audit(db, user.username, "delete_course", detail={"title": c.title})
    db.commit()
    return {"ok": True}


@router.get("/heatmap")
def heatmap(department_id: int | None = None, top: int = 20, db: Session = Depends(get_db),
            user: User = Depends(require_roles("hr", "manager"))):
    """Бөлімнің жиынтық дағдылар картасы: қызметкерлер × ең жиі талап етілетін дағдылар (деңгейлер)."""
    if user.role == "manager":
        department_id = user.department_id
    q = select(Employee).order_by(Employee.code)
    if department_id:
        q = q.where(Employee.department_id == department_id)
    emps = db.scalars(q).all()
    role_ids = {e.current_role_id for e in emps} | {e.target_role_id for e in emps}
    role_w: dict[str, float] = {}
    for rs in db.scalars(select(RoleSkill).where(RoleSkill.role_id.in_([r for r in role_ids if r]))):
        role_w[rs.esco_id] = role_w.get(rs.esco_id, 0) + rs.weight
    lv = {}
    holders: dict[str, int] = {}
    for s in db.scalars(select(EmployeeSkill).where(EmployeeSkill.employee_id.in_([e.id for e in emps]),
                                                    EmployeeSkill.status.in_(["auto", "confirmed"]))):
        lv[(s.employee_id, s.esco_id)] = s.level
        holders[s.esco_id] = holders.get(s.esco_id, 0) + 1
    # бағандар: бөлімде жиі кездесетін дағдылар, содан кейін рөлдерде маңызды дағдылар
    cand = set(holders) | set(role_w)
    skills = sorted(cand, key=lambda s: (-holders.get(s, 0), -role_w.get(s, 0), s))[:top]
    labels = dict(db.execute(select(Skill.esco_id, Skill.label_en).where(Skill.esco_id.in_(skills))).all())
    rows = []
    for e in emps:
        rows.append({"employee_id": e.id, "code": e.code, "role": e.current_role.code if e.current_role else None,
                     "levels": [lv.get((e.id, s), 0) for s in skills],
                     "target_coverage": round(gap_for(db, e.id, e.target_role_id).coverage, 3)
                     if e.target_role_id else None})
    avg = [round(sum(r["levels"][i] for r in rows) / max(len(rows), 1), 2) for i in range(len(skills))]
    return {"skills": [{"esco_id": s, "label": labels.get(s, s)} for s in skills], "rows": rows, "avg": avg}


@router.get("/audit")
def audit_log(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(require_roles("hr"))):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 1000)))
    return [{"id": a.id, "actor": a.actor, "action": a.action, "tool": a.tool, "employee_id": a.employee_id,
             "input_hash": a.input_hash, "detail": a.detail, "created_at": a.created_at.isoformat()} for a in rows]


@router.get("/export.csv")
def export(db: Session = Depends(get_db), _: User = Depends(require_roles("hr"))):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["employee", "current_role", "target_role", "target_coverage", "esco_id", "skill", "level", "status",
                "source"])
    for e in db.scalars(select(Employee).order_by(Employee.code)):
        cov = round(gap_for(db, e.id, e.target_role_id).coverage, 3) if e.target_role_id else ""
        for s, lab in db.execute(select(EmployeeSkill, Skill.label_en).join(Skill)
                                 .where(EmployeeSkill.employee_id == e.id)).all():
            w.writerow([e.code, e.current_role.code if e.current_role else "",
                        e.target_role.code if e.target_role else "", cov, s.esco_id, lab, s.level, s.status, s.source])
    data = "﻿" + buf.getvalue()
    return StreamingResponse(iter([data]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=career_quest_skills.csv"})
