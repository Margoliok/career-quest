"""Э5. ЖДЖ сапасын сарапшылық бағалауға арналған соқыр (blind) сауалнама жасау.

Әр профиль үшін екі жоспар: A/B ретімен кездейсоқ араластырылады —
  baseline: контекстсіз ҮТМ (тек түйіндеме мәтіні мен мақсатты рөл атауы);
  career_quest: жүйенің ЖДЖ-сы (алшақтық, p_s, ESCO, курстар каталогы — RAG; ҮТМ болса LLM мәтіні).
Шығыс: reports/forms/e5_plans.md (сарапшыларға), e5_ratings_template.csv (толтыруға), e5_key.json (кілт, сарапшыларға берілмейді).
ҮТМ кілті болмаса baseline жасалмайды — скрипт тоқтайды (сандар ойдан құрастырылмайды).
Іске қосу:  python -m scripts.experiments.e5_expert_forms --n 10
"""
from __future__ import annotations

import argparse
import csv
import json
import random

from app.db import SessionLocal
from app.llm.provider import LANG_NAMES, FileCache, get_provider, prompt
from app.llm.schemas import IDP_FREE_SCHEMA, IDPFreeOut
from app.models import Document, Employee
from app.services.idp import build_plan

from .common import reports

CRITERIA = [("relevance", "Сәйкестік / Релевантность"), ("feasibility", "Орындалуы / Выполнимость"),
            ("clarity", "Түсіндірменің айқындығы / Понятность объяснения")]


def render_cq(plan: dict) -> str:
    lines = [plan["summary"], "", plan["explanation"], ""]
    for ph in plan["phases"]:
        lines.append(f"**{ph['period']} күн / дней**")
        for it in ph["items"]:
            cs = "; ".join(f"{c['title']} ({c['provider']})" for c in it["courses"]) or "—"
            lines.append(f"- {it['skill']} ({it['from_level']}→{it['to_level']}): {it['practice']} "
                         f"Критерий: {it['success_criteria']} Курстар: {cs}")
    return "\n".join(lines)


def render_free(p: IDPFreeOut) -> str:
    lines = [p.summary, ""]
    for ph in p.phases:
        lines.append(f"**{ph.period} күн / дней**")
        lines += [f"- {it.skill}: {it.learning}. {it.practice} Критерий: {it.success_criteria}" for it in ph.items]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()
    prov = get_provider(FileCache(reports() / "llm_cache" / "e5.jsonl"))
    if prov is None:
        raise SystemExit("E5 needs OPENAI_API_KEY (baseline = LLM without context). Nothing was generated.")
    rng = random.Random(args.seed)
    db = SessionLocal()
    emps = [e for e in db.query(Employee).order_by(Employee.code).all() if e.target_role_id]
    emps = rng.sample(emps, min(args.n, len(emps)))
    md, key, rows = ["# Э5. Жеке даму жоспарларын сараптау / Экспертиза ИПР", ""], {}, []
    for e in emps:
        doc = db.query(Document).filter(Document.employee_id == e.id).order_by(Document.uploaded_at.desc()).first()
        lang = doc.lang if doc and doc.lang in ("kk", "ru") else "kk"
        cq = render_cq(build_plan(db, e, e.target_role, lang, prov))
        free = prov.json("idp_free", IDP_FREE_SCHEMA, IDPFreeOut,
                         prompt("idp_free_system").format(lang_name=LANG_NAMES[lang]),
                         f"Target role: {e.target_role.title_en}\n\nResume:\n{doc.text if doc else ''}")
        plans = [("career_quest", cq), ("baseline", render_free(free))]
        rng.shuffle(plans)
        key[e.code] = {"A": plans[0][0], "B": plans[1][0]}
        md += [f"## {e.code} → {e.target_role.title_en}", "", "### A", plans[0][1], "", "### B", plans[1][1], ""]
        for v in ("A", "B"):
            rows.append({"expert": "", "profile": e.code, "variant": v, **{c: "" for c, _ in CRITERIA}, "comment": ""})
    out = reports() / "forms"
    out.mkdir(parents=True, exist_ok=True)
    (out / "e5_plans.md").write_text("\n".join(md), encoding="utf-8")
    (out / "e5_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    with (out / "e5_ratings_template.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print("forms →", out, "| usage:", prov.usage)


if __name__ == "__main__":
    main()
