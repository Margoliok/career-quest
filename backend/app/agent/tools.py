"""ҮТМ-агент құралдары (1-қосымша, Кесте Қ1.1).

Құралдар ағымдағы пайдаланушының рұқсаты шегінде ғана орындалады: employee_id сессиядан алынады,
модель басқа қызметкердің деректеріне қол жеткізе алмайды.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Document, Employee, EmployeeSkill, Role, Skill, User
from ..services import career
from ..services.esco_search import PgIndex
from ..services.idp import build_plan, save_idp


@dataclass
class ToolContext:
    db: Session
    user: User
    emp: Employee
    lang: str
    provider: object | None = None


def _role(db: Session, code_or_id) -> Role | None:
    if code_or_id is None:
        return None
    if isinstance(code_or_id, int) or str(code_or_id).isdigit():
        return db.get(Role, int(code_or_id))
    return db.scalar(select(Role).where(Role.code == str(code_or_id).upper()))


def get_profile(ctx: ToolContext) -> dict:
    e = ctx.emp
    rows = ctx.db.execute(select(EmployeeSkill, Skill.label_en).join(Skill)
                          .where(EmployeeSkill.employee_id == e.id)).all()
    return {"employee_code": e.code,
            "current_role": e.current_role.title_en if e.current_role else None,
            "target_role": e.target_role.title_en if e.target_role else None,
            "skills": [{"esco_id": s.esco_id, "label": lab, "level": s.level, "status": s.status}
                       for s, lab in rows if s.status != "rejected"]}


def extract_skills(ctx: ToolContext) -> dict:
    doc = ctx.db.scalar(select(Document).where(Document.employee_id == ctx.emp.id)
                        .order_by(Document.uploaded_at.desc()))
    if not doc:
        return {"error": "no resume uploaded"}
    return career.analyze_employee(ctx.db, ctx.emp, doc.text, actor=f"agent:{ctx.user.username}",
                                   use_llm=ctx.provider is not None)


def search_esco(ctx: ToolContext, phrase: str, k: int = 5) -> dict:
    cands = PgIndex(ctx.db).search([phrase], k)[0]
    return {"phrase": phrase, "candidates": [{"esco_id": c.esco_id, "label": c.label, "similarity": round(c.sim, 3)}
                                             for c in cands]}


def compute_gap(ctx: ToolContext, role: str | None = None) -> dict:
    r = _role(ctx.db, role) or ctx.emp.target_role
    if not r:
        return {"error": "target role is not selected"}
    g = career.gap_for(ctx.db, ctx.emp.id, r.id)
    return {"role": r.title_en, "role_code": r.code, "coverage": round(g.coverage, 3),
            "missing": [{"esco_id": m.esco_id, "label": m.label, "priority_p_s": m.priority,
                         "employee_level": m.employee_level, "required_level": m.required_level,
                         "relation": m.relation} for m in g.missing[:10]],
            "matched_count": len(g.matched), "missing_count": len(g.missing)}


def suggest_roles(ctx: ToolContext, alpha: float | None = None) -> dict:
    recs = career.recommendations(ctx.db, ctx.emp, alpha=alpha)
    return {"formula": "Score = α·P̃(r′|r) + (1−α)·C(e,r′)", "alpha": alpha,
            "roles": [{k: r[k] for k in ("code", "title_kk", "title_ru", "score", "alpha_part", "skill_part",
                                         "coverage", "p_transition")} for r in recs]}


def find_courses(ctx: ToolContext, esco_ids: list[str]) -> dict:
    return {"courses": career.find_courses(ctx.db, esco_ids[:10], ctx.lang)}


def save_idp_tool(ctx: ToolContext, role: str | None = None) -> dict:
    r = _role(ctx.db, role) or ctx.emp.target_role
    if not r:
        return {"error": "target role is not selected"}
    plan = build_plan(ctx.db, ctx.emp, r, ctx.lang, ctx.provider)
    idp = save_idp(ctx.db, ctx.emp, r, plan, ctx.user.id, f"agent:{ctx.user.username}")
    return {"idp_id": idp.id, "version": idp.version, "status": idp.status,
            "items": [{"period": p["period"], "skills": [i["skill"] for i in p["items"]]} for p in plan["phases"]]}


TOOLS = {
    "get_profile": (get_profile, "Get the employee profile: current/target role and recognised skills.", {}),
    "extract_skills": (extract_skills, "Re-run skill extraction on the latest uploaded resume.", {}),
    "search_esco": (search_esco, "Find ESCO skills for a phrase (vector search).",
                    {"phrase": {"type": "string"}, "k": {"type": "integer"}}),
    "compute_gap": (compute_gap, "Compute skill coverage C(e,r) and missing skills sorted by priority p_s "
                                 "for a role code (JDA, DA, SDA, BI, DS, DE, BA) or the target role.",
                    {"role": {"type": "string"}}),
    "suggest_roles": (suggest_roles, "Rank next roles with the hybrid score and its components.",
                      {"alpha": {"type": "number"}}),
    "find_courses": (find_courses, "Find courses in the catalogue for ESCO skill ids.",
                     {"esco_ids": {"type": "array", "items": {"type": "string"}}}),
    "save_idp": (save_idp_tool, "Create and save a 30/60/90 IDP draft for a role (sent to the manager for approval).",
                 {"role": {"type": "string"}}),
}


def openai_tool_specs() -> list[dict]:
    specs = []
    for name, (_, desc, props) in TOOLS.items():
        req = ["phrase"] if name == "search_esco" else (["esco_ids"] if name == "find_courses" else [])
        specs.append({"type": "function", "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}})
    return specs
