from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Role, Transition, User
from ..security import current_user
from ..services.career import role_requirements
from ..services.esco_search import PgIndex
from .serializers import role_dict

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/system")
def system(_: User = Depends(current_user)):
    s = get_settings()
    return {"llm_enabled": s.llm_enabled, "llm_model": s.openai_model if s.llm_enabled else None,
            "embedding_model": s.embedding_model, "offline_embedding_model": s.offline_embedding_model,
            "alpha": s.alpha, "lambda": s.smoothing_lambda, "tau": s.tau, "offline_tau": s.offline_tau,
            "top_k": s.top_k, "esco_version": "ESCO v1.2.1"}


@router.get("/roles")
def roles(db: Session = Depends(get_db), _: User = Depends(current_user)):
    out = []
    for r in db.scalars(select(Role).order_by(Role.family, Role.grade)):
        d = role_dict(r)
        d["skills_count"] = len(r.skills)
        out.append(d)
    return out


@router.get("/roles/{role_id}")
def role_detail(role_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    r = db.get(Role, role_id)
    if not r:
        raise HTTPException(404, "Role not found")
    d = role_dict(r)
    d["requirements"] = [vars(x) for x in sorted(role_requirements(db, role_id), key=lambda x: (-x.weight, x.label))]
    d["sources"] = {rs.esco_id: rs.source for rs in r.skills}
    return d


@router.get("/transitions")
def transitions(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [{"from": t.from_role_id, "to": t.to_role_id, "count": t.count, "prob": t.prob, "source": t.source}
            for t in db.scalars(select(Transition))]


@router.get("/skills/search")
def skills_search(q: str, k: int = 10, db: Session = Depends(get_db), _: User = Depends(current_user)):
    cands = PgIndex(db).search([q], k)[0]
    return [{"esco_id": c.esco_id, "label": c.label, "matched_label": c.matched_label, "similarity": round(c.sim, 4)}
            for c in cands]
