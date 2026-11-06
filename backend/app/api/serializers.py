from __future__ import annotations

from ..models import IDP, Employee, Role, User


def role_dict(r: Role | None) -> dict | None:
    if r is None:
        return None
    return {"id": r.id, "code": r.code, "title_kk": r.title_kk, "title_ru": r.title_ru, "title_en": r.title_en,
            "grade": r.grade, "family": r.family, "esco_occupation_id": r.esco_occupation_id,
            "esco_occupation_label": r.esco_occupation_label, "description_kk": r.description_kk,
            "description_ru": r.description_ru, "prof_standard_ref": r.prof_standard_ref}


def employee_dict(e: Employee) -> dict:
    return {"id": e.id, "code": e.code, "department_id": e.department_id,
            "department_kk": e.department.name_kk if e.department else None,
            "department_ru": e.department.name_ru if e.department else None,
            "current_role": role_dict(e.current_role), "target_role": role_dict(e.target_role),
            "consent_at": e.consent_at.isoformat() if e.consent_at else None}


def user_dict(u: User) -> dict:
    return {"id": u.id, "username": u.username, "role": u.role, "display_name": u.display_name,
            "department_id": u.department_id, "employee_id": u.employee_id}


def idp_dict(i: IDP) -> dict:
    return {"id": i.id, "employee_id": i.employee_id, "target_role_id": i.target_role_id, "version": i.version,
            "status": i.status, "plan": i.plan_json, "generator": i.generator, "manager_comment": i.manager_comment,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "updated_at": i.updated_at.isoformat() if i.updated_at else None}
