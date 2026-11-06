"""GitHub Pages демосы үшін snapshot.json экспорттау (нақты API жауаптары, TestClient арқылы).

Іске қосу (толтырылған ДҚ қажет):  python -m scripts.export_demo
Шығыс: frontend/public/demo/snapshot.json
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.agent.orchestrator import REFUSAL
from app.config import ROOT
from app.db import SessionLocal
from app.main import app
from app.models import Employee, Role
from app.services.career import skill_importance
from app.services.idp import build_plan, save_idp

SUGGEST = {
    "kk": ["Data Analyst рөліне өту үшін маған не жетіспейді?", "Неге маған бұл рөлдер ұсынылды?",
           "SQL бойынша курстар ұсын", "30/60/90 күндік даму жоспарын құр"],
    "ru": ["Чего мне не хватает для роли Data Analyst?", "Почему мне рекомендованы эти роли?",
           "Подбери курсы по SQL", "Составь план развития на 30/60/90 дней"],
}
FALLBACK = {
    "kk": "Демо режимде ассистент алдын ала есептелген үлгі сұрақтарға жауап береді. Толық нұсқада (backend + ҮТМ) "
          "кез келген сұраққа жүйе құралдары арқылы жауап беріледі. Үлгі сұрақтардың бірін таңдаңыз.",
    "ru": "В демо-режиме ассистент отвечает на заранее рассчитанные примеры вопросов. В полной версии (backend + LLM) "
          "ответ на любой вопрос строится через инструменты системы. Выберите один из примеров.",
}


def main() -> None:
    c = TestClient(app)

    def login(u):
        r = c.post("/api/auth/login", data={"username": u, "password": "demo123"}).json()
        return {"Authorization": f"Bearer {r['access_token']}"}, r["user"]

    hh, _ = login("hr")
    users = []
    for u in ("employee", "employee2", "manager", "manager2", "hr"):
        users.append(login(u)[1])
    db = SessionLocal()
    snap: dict = {"users": users}
    snap["system"] = c.get("/api/system", headers=hh).json()
    snap["departments"] = c.get("/api/hr/departments", headers=hh).json()
    snap["roles"] = []
    for r in c.get("/api/roles", headers=hh).json():
        d = c.get(f"/api/roles/{r['id']}", headers=hh).json()
        snap["roles"].append(d)
    snap["transitions"] = c.get("/api/transitions", headers=hh).json()
    snap["courses"] = c.get("/api/hr/courses", headers=hh).json()
    snap["importance"] = skill_importance(db)

    demo_emps = [u["employee_id"] for u in users if u["employee_id"]]
    # Басшыға келісуге жіберілген ЖДЖ (E-001) және жоба (E-002)
    for eid, lang, submit in ((demo_emps[0], "kk", True), (demo_emps[1], "ru", False)):
        e = db.get(Employee, eid)
        idp = save_idp(db, e, e.target_role, build_plan(db, e, e.target_role, lang, None), None, "export_demo")
        if submit:
            idp.status = "submitted"
            db.commit()
    # Чат: алдын ала есептелген жауаптар
    snap["chat"] = {"qa": {}, "refusal": REFUSAL, "fallback": FALLBACK}
    for u in ("employee", "employee2"):
        h, me = login(u)
        snap["chat"]["qa"][me["employee_id"]] = {}
        for lang, qs in SUGGEST.items():
            snap["chat"]["qa"][me["employee_id"]][lang] = [
                {"q": q, "a": c.post("/api/chat", headers=h, json={"message": q, "lang": lang}).json()} for q in qs]
    # Барлық рөлдер үшін ЖДЖ (демода мақсатты рөлді өзгерткенде)
    snap["idps"] = {}
    for eid in demo_emps:
        e = db.get(Employee, eid)
        snap["idps"][eid] = {}
        for r in db.query(Role).all():
            snap["idps"][eid][r.id] = {lang: build_plan(db, e, r, lang, None) for lang in ("kk", "ru")}
    emps = c.get("/api/employees", headers=hh).json()
    snap["employees"], snap["skills"], snap["idp_list"], snap["analysis"] = [], {}, [], {}
    for e in emps:
        p = c.get(f"/api/profiles/{e['id']}", headers=hh).json()
        if e["id"] not in demo_emps:
            p["latest_text"] = p.get("latest_text")
        snap["employees"].append(p)
        snap["skills"][e["id"]] = c.get(f"/api/profiles/{e['id']}/skills", headers=hh).json()
        snap["idp_list"] += c.get(f"/api/idp?employee_id={e['id']}", headers=hh).json()
        snap["analysis"][e["id"]] = {"found": len(snap["skills"][e["id"]]), "added": 0, "updated": 0, "kept": 0,
                                     "lang": (p.get("documents") or [{}])[0].get("lang", "kk")}
    labels = {}
    for r in snap["roles"]:
        for q in r["requirements"]:
            labels[q["esco_id"]] = q["label"]
    for sk in snap["skills"].values():
        for s in sk:
            labels[s["esco_id"]] = s["label"]
    snap["catalog"] = sorted([{"esco_id": k, "label": v} for k, v in labels.items()], key=lambda x: x["label"])
    snap["audit"] = c.get("/api/hr/audit?limit=80", headers=hh).json()
    db.close()
    path = ROOT / "frontend" / "public" / "demo" / "snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"snapshot → {path} ({path.stat().st_size / 1e6:.2f} MB); employees={len(emps)}")


if __name__ == "__main__":
    main()
