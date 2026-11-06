"""ҮТМ жауаптарының JSON-схемалары (OpenAI structured outputs, strict) және pydantic валидациясы.

Схемалар 1-қосымшада (Листинг Қ1.2) келтіріледі.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# ---------- 1. Дағдыларды анықтау ----------
EXTRACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["skills"],
    "properties": {
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["phrase", "skill_en", "evidence", "level", "confidence"],
                "properties": {
                    "phrase": {"type": "string", "description": "skill as written in the text (original language)"},
                    "skill_en": {"type": "string", "description": "short normalized English name of the skill"},
                    "evidence": {"type": "string", "description": "exact quote from the text proving the skill"},
                    "level": {"type": "integer", "enum": [1, 2, 3, 4]},
                    "confidence": {"type": "number"},
                },
            },
        }
    },
}


class ExtractedItem(BaseModel):
    phrase: str
    skill_en: str
    evidence: str
    level: int = Field(ge=1, le=4)
    confidence: float = Field(ge=0, le=1)


class ExtractOut(BaseModel):
    skills: list[ExtractedItem]


# ---------- 2. Үміткерлерді қайта рейтингтеу ----------
RERANK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["i", "choice", "confidence"],
                "properties": {
                    "i": {"type": "integer", "description": "index of the phrase"},
                    "choice": {"type": "integer", "description": "index of the best candidate, -1 if none fits"},
                    "confidence": {"type": "number"},
                },
            },
        }
    },
}


class RerankItem(BaseModel):
    i: int
    choice: int
    confidence: float = Field(ge=0, le=1)


class RerankOut(BaseModel):
    items: list[RerankItem]


# ---------- 3. ЖДЖ мәтіні (жоспардың құрылымы алдын ала анықталған, ҮТМ тек түсіндірме жазады) ----------
IDP_TEXT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "items", "explanation"],
    "properties": {
        "summary": {"type": "string"},
        "explanation": {"type": "string", "description": "why these skills and this order; cite skill ids"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["esco_id", "practice", "success_criteria"],
                "properties": {
                    "esco_id": {"type": "string"},
                    "practice": {"type": "string", "description": "concrete on-the-job task"},
                    "success_criteria": {"type": "string"},
                },
            },
        },
    },
}


class IDPTextItem(BaseModel):
    esco_id: str
    practice: str
    success_criteria: str


class IDPTextOut(BaseModel):
    summary: str
    explanation: str
    items: list[IDPTextItem]


# ---------- 4. Контекстсіз ЖДЖ (Э5 базалық тәсілі) ----------
IDP_FREE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "phases"],
    "properties": {
        "summary": {"type": "string"},
        "phases": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["period", "items"],
                "properties": {
                    "period": {"type": "integer", "enum": [30, 60, 90]},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["skill", "learning", "practice", "success_criteria"],
                            "properties": {
                                "skill": {"type": "string"},
                                "learning": {"type": "string"},
                                "practice": {"type": "string"},
                                "success_criteria": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}


class FreeItem(BaseModel):
    skill: str
    learning: str
    practice: str
    success_criteria: str


class FreePhase(BaseModel):
    period: int
    items: list[FreeItem]

    @field_validator("period")
    @classmethod
    def _p(cls, v: int) -> int:
        if v not in (30, 60, 90):
            raise ValueError("period must be 30/60/90")
        return v


class IDPFreeOut(BaseModel):
    summary: str
    phases: list[FreePhase]
