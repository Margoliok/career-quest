from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agent.orchestrator import chat
from ..agent.tools import ToolContext
from ..db import get_db
from ..llm.provider import DBCache, get_provider
from ..models import User
from ..security import current_user, get_employee_checked

router = APIRouter(prefix="/api", tags=["chat"])


class ChatBody(BaseModel):
    message: str
    employee_id: int | None = None
    history: list[dict] = []
    lang: str = "kk"


@router.post("/chat")
def post_chat(body: ChatBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    eid = body.employee_id or user.employee_id
    if not eid:
        raise HTTPException(400, "employee_id is required")
    emp = get_employee_checked(db, user, eid)
    ctx = ToolContext(db=db, user=user, emp=emp, lang=body.lang, provider=get_provider(DBCache(db)))
    return chat(ctx, body.message[:2000], body.history)
