"""Жеке даму жоспары (ЖДЖ) 30/60/90 күн.

Жоспардың құрылымын жүйе анықтайды: дағдылар (3) басымдық p_s бойынша, мақсатты деңгейлер,
курстар каталогынан RAG арқылы табылған курстар. ҮТМ (бар болса) тек түсіндірме мәтінін,
практикалық тапсырма мен табыс критерийін жазады және тек берілген esco_id-лерді қолдана алады.
"""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..llm.provider import LANG_NAMES, LLMError, OpenAIProvider, prompt
from ..llm.schemas import IDP_TEXT_SCHEMA, IDPTextOut
from ..models import IDP, Employee, Role, Skill
from .career import audit, find_courses, gap_for

PER_PHASE = 3
LEVEL_NAMES = {
    "kk": {0: "жоқ", 1: "таныс", 2: "басшылықпен орындайды", 3: "өз бетінше орындайды", 4: "сарапшы"},
    "ru": {0: "нет", 1: "знаком", 2: "выполняет под руководством", 3: "выполняет самостоятельно", 4: "эксперт"},
}
DISCLAIMER = {
    "kk": "Бұл жоспар — ЖИ ұсынымы. Соңғы шешімді қызметкер мен басшы қабылдайды; жоспар жалақы, жұмысқа алу "
          "немесе жұмыстан шығару туралы шешімдерге негіз бола алмайды.",
    "ru": "Этот план — рекомендация ИИ. Окончательное решение принимают сотрудник и руководитель; план не является "
          "основанием для решений о зарплате, найме или увольнении.",
}


def _offline_text(lang: str, role_title: str, coverage: float, items: list[dict]) -> dict:
    ln = LEVEL_NAMES[lang]
    top = ", ".join(f"«{i['skill']}» (p_s = {i['priority']:g})" for i in items[:3])
    if lang == "kk":
        summary = (f"Мақсатты рөл: {role_title}. Қазіргі қамту көрсеткіші C = {coverage:.0%}. Жоспар {len(items)} "
                   f"дағдыны 30/60/90 күндік кезеңдерге бөледі.")
        expl = (f"Дағдылар реті басымдық бойынша анықталды: p_s = w_s · (l_r − l_e). Ең басым дағдылар: {top}. "
                f"Міндетті дағдылардың салмағы жоғары (w = 1), сондықтан олар алғашқы кезеңдерге қойылды.")
    else:
        summary = (f"Целевая роль: {role_title}. Текущее покрытие C = {coverage:.0%}. План распределяет {len(items)} "
                   f"навыков по этапам 30/60/90 дней.")
        expl = (f"Порядок навыков определён по приоритету p_s = w_s · (l_r − l_e). Наиболее приоритетные: {top}. "
                f"Обязательные навыки имеют больший вес (w = 1), поэтому стоят в первых этапах.")
    texts = {}
    for i in items:
        if lang == "kk":
            practice = (f"Ағымдағы жұмыс міндеттерінің бірінде «{i['skill']}» дағдысын қолданып, нәтижені "
                        f"(есеп, код немесе құжат) басшыға көрсету.")
            crit = (f"Басшы «{i['skill']}» дағдысын {i['to_level']}-деңгейде ({ln[i['to_level']]}) растайды.")
        else:
            practice = (f"Применить навык «{i['skill']}» в одной из текущих рабочих задач и показать результат "
                        f"(отчёт, код или документ) руководителю.")
            crit = f"Руководитель подтверждает навык «{i['skill']}» на уровне {i['to_level']} ({ln[i['to_level']]})."
        texts[i["esco_id"]] = {"practice": practice, "success_criteria": crit}
    return {"summary": summary, "explanation": expl, "items": texts}


def _llm_text(provider: OpenAIProvider, lang: str, role: Role, coverage: float, items: list[dict]) -> dict:
    allowed = {i["esco_id"] for i in items}
    ctx = {"target_role": role.title_en, "coverage": round(coverage, 3),
           "items": [{k: i[k] for k in ("esco_id", "skill", "skill_description", "from_level", "to_level",
                                        "priority", "relation", "period")} |
                     {"courses": [{"title": c["title"], "provider": c["provider"]} for c in i["courses"]]}
                     for i in items]}

    def check(obj: IDPTextOut) -> None:
        bad = [x.esco_id for x in obj.items if x.esco_id not in allowed]
        if bad:
            raise ValueError(f"unknown esco_id in items: {bad[:3]}")

    out = provider.json("idp_text", IDP_TEXT_SCHEMA, IDPTextOut,
                        prompt("idp_system").format(lang_name=LANG_NAMES.get(lang, lang)),
                        json.dumps(ctx, ensure_ascii=False), validate=check)
    return {"summary": out.summary, "explanation": out.explanation,
            "items": {x.esco_id: {"practice": x.practice, "success_criteria": x.success_criteria} for x in out.items}}


def build_plan(db: Session, emp: Employee, role: Role, lang: str, provider: OpenAIProvider | None) -> dict:
    gap = gap_for(db, emp.id, role.id)
    missing = gap.missing[: PER_PHASE * 3]
    descs = dict(db.execute(select(Skill.esco_id, Skill.description)
                            .where(Skill.esco_id.in_([m.esco_id for m in missing]))).all())
    courses = find_courses(db, [m.esco_id for m in missing], lang)
    items = []
    for n, m in enumerate(missing):
        items.append({"esco_id": m.esco_id, "skill": m.label, "skill_description": (descs.get(m.esco_id) or "")[:300],
                      "priority": round(m.priority, 2), "weight": m.weight, "relation": m.relation,
                      "from_level": m.employee_level, "to_level": m.required_level,
                      "period": 30 * (n // PER_PHASE + 1), "courses": courses.get(m.esco_id, [])})
    title = role.title_kk if lang == "kk" else role.title_ru
    generator = "offline"
    text = None
    if provider is not None and items:
        try:
            text = _llm_text(provider, lang, role, gap.coverage, items)
            generator = "llm"
        except LLMError:
            text = None
    if text is None:
        text = _offline_text(lang, title, gap.coverage, items)
    for i in items:
        i.update(text["items"].get(i["esco_id"], {"practice": "", "success_criteria": ""}))
    phases = [{"period": p, "items": [i for i in items if i["period"] == p]} for p in (30, 60, 90)]
    return {"target_role": {"id": role.id, "code": role.code, "title_kk": role.title_kk, "title_ru": role.title_ru},
            "lang": lang, "coverage_before": round(gap.coverage, 4), "summary": text["summary"],
            "explanation": text["explanation"], "phases": [p for p in phases if p["items"]],
            "later": [{"esco_id": m.esco_id, "skill": m.label, "priority": m.priority}
                      for m in gap.missing[PER_PHASE * 3:]],
            "generator": generator, "disclaimer": DISCLAIMER.get(lang, DISCLAIMER["ru"])}


def save_idp(db: Session, emp: Employee, role: Role, plan: dict, user_id: int | None, actor: str) -> IDP:
    ver = (db.scalar(select(func.max(IDP.version)).where(IDP.employee_id == emp.id)) or 0) + 1
    idp = IDP(employee_id=emp.id, target_role_id=role.id, version=ver, status="draft", plan_json=plan,
              generator=plan["generator"], created_by=user_id)
    db.add(idp)
    audit(db, actor, "create_idp", "save_idp", emp.id, plan,
          {"version": ver, "generator": plan["generator"], "target_role": role.code,
           "items": sum(len(p["items"]) for p in plan["phases"])})
    db.commit()
    db.refresh(idp)
    return idp
