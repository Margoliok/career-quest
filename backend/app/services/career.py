"""Дерекқор деңгейіндегі бизнес-логика: қызметкерді талдау, алшақтық, рөл ұсынымы, курстар, аудит."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..llm.provider import DBCache, get_provider
from ..models import (AuditLog, Course, Document, Employee, EmployeeSkill, Role, RoleSkill, Skill, Transition)
from .esco_search import PgIndex, domain_index
from .extract import STATUS_AUTO, ExtractedSkill, extract_skills
from .gap import GapResult, Requirement, compute_gap
from .parsing import detect_lang
from .recommend import hybrid_scores, smoothed_transition_probs


# ---------------- Аудит ----------------
def audit(db: Session, actor: str, action: str, tool: str | None = None, employee_id: int | None = None,
          payload: object = None, detail: dict | None = None) -> None:
    h = None
    if payload is not None:
        h = hashlib.sha256(json.dumps(payload, ensure_ascii=False, default=str).encode()).hexdigest()
    db.add(AuditLog(actor=actor, action=action, tool=tool, employee_id=employee_id, input_hash=h, detail=detail or {}))


# ---------------- Индекстер ----------------
def catalog_ids(db: Session) -> tuple[str, ...]:
    return tuple(sorted(set(db.scalars(select(RoleSkill.esco_id)).all())))


def catalog_index(db: Session):
    return domain_index(catalog_ids(db))


# ---------------- Талдау ----------------
def analyze_employee(db: Session, emp: Employee, text: str, actor: str, use_llm: bool = True,
                     doc_type: str = "resume", filename: str | None = None) -> dict:
    lang = detect_lang(text)
    db.add(Document(employee_id=emp.id, type=doc_type, lang=lang, text=text, filename=filename))
    provider = get_provider(DBCache(db)) if use_llm else None
    skills: list[ExtractedSkill] = extract_skills(text, PgIndex(db), catalog_index(db), provider, lang=lang)
    existing = {s.esco_id: s for s in db.scalars(select(EmployeeSkill).where(EmployeeSkill.employee_id == emp.id))}
    added = updated = kept = 0
    for s in skills:
        row = existing.get(s.esco_id)
        if row and row.status in ("confirmed", "rejected"):
            kept += 1  # басшының шешімі ЖИ нәтижесінен басым
            continue
        if row is None:
            row = EmployeeSkill(employee_id=emp.id, esco_id=s.esco_id)
            db.add(row)
            added += 1
        else:
            updated += 1
        row.level, row.evidence, row.phrase = s.level, s.evidence, s.phrase
        row.source = "llm" if s.method.startswith("llm") else "offline"
        row.status, row.confidence, row.similarity = s.status, s.confidence, s.similarity
    audit(db, actor, "analyze_profile", "extract_skills", emp.id, text,
          {"lang": lang, "method": "llm" if provider else "offline", "found": len(skills),
           "added": added, "updated": updated, "kept_manager_decisions": kept})
    db.commit()
    return {"lang": lang, "method": "llm" if provider else "offline", "found": len(skills), "added": added,
            "updated": updated, "kept": kept}


def employee_levels(db: Session, employee_id: int) -> dict[str, int]:
    """Алшақтыққа ЖИ анықтаған (auto) және басшы растаған дағдылар кіреді; «расталмаған» мен қабылданбағандары кірмейді."""
    rows = db.scalars(select(EmployeeSkill).where(EmployeeSkill.employee_id == employee_id,
                                                  EmployeeSkill.status.in_([STATUS_AUTO, "confirmed"])))
    return {r.esco_id: r.level for r in rows}


def role_requirements(db: Session, role_id: int) -> list[Requirement]:
    rows = db.execute(select(RoleSkill, Skill.label_en).join(Skill, Skill.esco_id == RoleSkill.esco_id)
                      .where(RoleSkill.role_id == role_id)).all()
    return [Requirement(rs.esco_id, rs.weight, rs.required_level, label, rs.relation) for rs, label in rows]


def skill_importance(db: Session) -> dict[str, float]:
    """Дағдыны талап ететін рөлдер саны (ЖДЖ-дағы тең басымдықтарды реттеу үшін)."""
    out: dict[str, float] = {}
    for sid in db.scalars(select(RoleSkill.esco_id)):
        out[sid] = out.get(sid, 0) + 1
    return out


def gap_for(db: Session, employee_id: int, role_id: int) -> GapResult:
    return compute_gap(employee_levels(db, employee_id), role_requirements(db, role_id), skill_importance(db))


def recommendations(db: Session, emp: Employee, alpha: float | None = None, lam: float | None = None,
                    top: int = 5) -> list[dict]:
    s = get_settings()
    alpha = s.alpha if alpha is None else alpha
    lam = s.smoothing_lambda if lam is None else lam
    roles = {r.id: r for r in db.scalars(select(Role))}
    cur = emp.current_role_id
    cands = [rid for rid in roles if rid != cur]
    counts = {t.to_role_id: t.count for t in db.scalars(select(Transition).where(Transition.from_role_id == cur))} \
        if cur else {}
    p_hat = smoothed_transition_probs(counts, cands, lam)
    levels = employee_levels(db, emp.id)
    cov, gaps = {}, {}
    imp = skill_importance(db)
    for rid in cands:
        g = compute_gap(levels, role_requirements(db, rid), imp)
        cov[rid], gaps[rid] = g.coverage, g
    ranked = hybrid_scores(p_hat, cov, alpha)
    out = []
    for rs in ranked[:top]:
        r = roles[rs.role]
        g = gaps[rs.role]
        out.append({"role_id": r.id, "code": r.code, "title_kk": r.title_kk, "title_ru": r.title_ru,
                    "score": round(rs.score, 4), "p_transition": round(rs.p_transition, 4),
                    "p_normalized": round(rs.p_normalized, 4), "coverage": round(rs.coverage, 4),
                    "alpha_part": round(rs.alpha_part, 4), "skill_part": round(rs.skill_part, 4),
                    "transition_count": counts.get(rs.role, 0.0),
                    "top_missing": [{"esco_id": m.esco_id, "label": m.label, "priority": m.priority}
                                    for m in g.missing[:5]]})
    return out


# ---------------- Курстар ----------------
def find_courses(db: Session, esco_ids: list[str], lang: str = "kk", limit: int = 2) -> dict[str, list[dict]]:
    """Әр дағдыға курстар: дағды сәйкестігі, тіл (қаз/орыс бірінші), тегін курстар бірінші."""
    courses = list(db.scalars(select(Course)))
    pref_lang = {"kk": ["kk", "ru", "en"], "ru": ["ru", "kk", "en"]}.get(lang, ["en", "ru", "kk"])
    out: dict[str, list[dict]] = {}
    for sid in esco_ids:
        hits = [c for c in courses if sid in (c.esco_ids or [])]
        hits.sort(key=lambda c: (pref_lang.index(c.lang) if c.lang in pref_lang else 9, not c.is_free,
                                 len(c.esco_ids or [])))
        out[sid] = [course_dict(c) for c in hits[:limit]]
    return out


def course_dict(c: Course) -> dict:
    return {"id": c.id, "title": c.title, "provider": c.provider, "url": c.url, "lang": c.lang, "level": c.level,
            "duration_h": c.duration_h, "is_free": c.is_free, "esco_ids": c.esco_ids, "description": c.description}


def now() -> datetime:
    return datetime.now(timezone.utc)
