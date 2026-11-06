"""Дерекқорды толтыру: ESCO дағдылары + векторлар, рөлдер, ауысулар, курстар, демо қызметкерлер.

Іске қосу:  python -m scripts.seed [--reset]
Алдын ала: scripts.build_index (ESCO векторлары), scripts.load_karrierewege (приор), scripts.generate_profiles.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import func, insert, select, text

from app.config import get_settings
from app.db import Base, SessionLocal, engine, init_db
from app.models import (Course, Department, Employee, Role, RoleSkill, Skill, SkillLabel, Transition, User)
from app.security import hash_password
from app.services import esco_data
from app.services.career import analyze_employee
from app.services.esco_search import index_path
from app.services.roles import build_requirements, load_case_config

MU = 3.0  # Karrierewege приорының салмағы (жалған бақылаулар саны)
NEXT_GRADE = {"JDA": "DA", "DA": "SDA", "BA": "DA", "BI": "DE", "DE": "DS", "DS": "SDA", "SDA": "DS"}
DEPTS = [("Деректер талдау бөлімі", "Отдел анализа данных", {"analytics", "business"}),
         ("Деректер инженериясы және BI бөлімі", "Отдел инженерии данных и BI", {"bi", "engineering", "data_science"})]


def load_skills(db) -> None:
    if db.scalar(select(func.count()).select_from(Skill)):
        print("skills: already loaded")
        return
    z = np.load(index_path(), allow_pickle=True)
    emb, ids, labels, pref = z["emb"].astype(np.float32), z["esco_ids"], z["labels"], z["is_pref"]
    pref_vec = {str(ids[i]): emb[i] for i in np.where(pref)[0]}
    sk = esco_data.load_skills()
    rows = [dict(esco_id=r.esco_id, label_en=r.label, alt_labels=r.alt_labels, type=r.type,
                 reuse_level=r.reuseLevel, description=r.description, embedding=pref_vec.get(r.esco_id))
            for r in sk.itertuples()]
    for i in range(0, len(rows), 2000):
        db.execute(insert(Skill), rows[i:i + 2000])
    lab_rows = [dict(esco_id=str(ids[i]), label=str(labels[i]), is_preferred=bool(pref[i]), embedding=emb[i])
                for i in range(len(ids))]
    for i in range(0, len(lab_rows), 5000):
        db.execute(insert(SkillLabel), lab_rows[i:i + 5000])
        print(f"  skill_labels {min(i + 5000, len(lab_rows))}/{len(lab_rows)}")
    db.commit()
    print(f"skills: {len(rows)}, labels: {len(lab_rows)}")


def load_roles(db) -> dict[str, Role]:
    cfg = load_case_config()
    roles: dict[str, Role] = {}
    reports, csv_rows = [], []
    for rc in cfg["roles"]:
        reqs, rep = build_requirements(rc, cfg["level_scheme"])
        role = Role(code=rc["code"], esco_occupation_id=rep["esco_occupation_id"],
                    esco_occupation_label=rep["esco_occupation"], title_kk=rc["title_kk"], title_ru=rc["title_ru"],
                    title_en=rc["title_en"], grade=rc["grade"], family=rc["family"],
                    description_kk=rc["description_kk"], description_ru=rc["description_ru"],
                    prof_standard_ref=rc.get("prof_standard_ref", ""))
        role.skills = [RoleSkill(esco_id=r["esco_id"], weight=r["weight"], required_level=r["required_level"],
                                 relation=r["relation"], source=r["source"]) for r in reqs]
        db.add(role)
        roles[rc["code"]] = role
        reports.append(rep)
        csv_rows += [{"role": rc["code"], **r} for r in reqs]
    db.commit()
    out = get_settings().data_dir / "local"
    (out / "roles_report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(csv_rows).to_csv(out / "role_skills_case.csv", index=False, encoding="utf-8-sig")
    print("roles:", {k: len(v.skills) for k, v in roles.items()})
    return roles


def karrierewege_prior(roles: dict[str, Role]) -> dict[tuple[str, str], float]:
    """P_KW(occ(r′) | occ(r)) кейс кәсіптері арасында (Karrierewege train, бірдей кәсіптер біріктірілген)."""
    path = get_settings().cache_dir / "kw_train.csv.gz"
    if not path.exists():
        print("Karrierewege prior skipped (run scripts.load_karrierewege)")
        return {}
    occs = {r.esco_occupation_id for r in roles.values()}
    df = pd.read_csv(path)
    pairs: Counter = Counter()
    for _, g in df[df.occupation_id.isin(occs)].groupby("traj_id"):
        seq = [o for i, o in enumerate(g.occupation_id) if i == 0 or o != g.occupation_id.iloc[i - 1]]
        pairs.update(zip(seq, seq[1:]))
    tot: Counter = Counter()
    for (a, _), n in pairs.items():
        tot[a] += n
    # Лаплас бойынша тегістелген P_KW(b|a): кейс кәсіптері арасындағы бақылаулар өте аз болғандықтан
    prior = {}
    for ca, ra in roles.items():
        a = ra.esco_occupation_id
        others = {r.esco_occupation_id for r in roles.values()} - {a}
        for cb, rb in roles.items():
            b = rb.esco_occupation_id
            if ca != cb and a != b:
                prior[(ca, cb)] = (pairs[(a, b)] + 1) / (tot[a] + len(others))
    print("Karrierewege pairs among case occupations:", dict(pairs))
    return prior


def load_transitions(db, roles: dict[str, Role]) -> None:
    expert = {}
    with (get_settings().data_dir / "local" / "transitions_case.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            expert[(r["from_role"], r["to_role"])] = float(r["count"])
    prior = karrierewege_prior(roles)
    for a in roles:
        for b in roles:
            if a == b:
                continue
            n = expert.get((a, b), 0.0) + MU * prior.get((a, b), 0.0)
            if n <= 0:
                continue
            src = "+".join(x for x, ok in (("expert", (a, b) in expert), ("karrierewege", (a, b) in prior)) if ok)
            db.add(Transition(from_role_id=roles[a].id, to_role_id=roles[b].id, count=round(n, 4), source=src))
    db.commit()
    for a in roles:  # P̂ өрісін λ = 1 бойынша толтыру (көрсету үшін; ұсынымда қайта есептеледі)
        rows = db.scalars(select(Transition).where(Transition.from_role_id == roles[a].id)).all()
        n_r = sum(t.count for t in rows)
        for t in rows:
            t.prob = round((t.count + 1) / (n_r + len(roles) - 1), 4)
    db.commit()
    print("transitions:", db.scalar(select(func.count()).select_from(Transition)))


def load_courses(db) -> None:
    from app.services.roles import skill_id

    path = get_settings().data_dir / "courses" / "catalog.csv"
    n = 0
    for r in csv.DictReader(path.open(encoding="utf-8"), delimiter=";"):
        db.add(Course(title=r["title"], provider=r["provider"], url=r["url"], lang=r["lang"], level=r["level"],
                      esco_ids=[skill_id(x) for x in r["esco_labels"].split("|") if x.strip()],
                      is_free=r["is_free"] == "true", duration_h=float(r["duration_h"]) if r["duration_h"] else None,
                      description=r["description"]))
        n += 1
    db.commit()
    print("courses:", n)


def load_people(db, roles: dict[str, Role], analyze: bool) -> None:
    depts = []
    for kk, ru, _ in DEPTS:
        d = Department(name_kk=kk, name_ru=ru)
        db.add(d)
        depts.append(d)
    db.commit()
    path = get_settings().data_dir / "local" / "profiles.jsonl"
    profiles = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    now = datetime.now(timezone.utc)
    emps = {}
    for p in profiles:
        role = roles[p["role"]]
        dept = depts[0] if role.family in DEPTS[0][2] else depts[1]
        nxt = roles.get(NEXT_GRADE.get(p["role"], ""))
        e = Employee(code=p["profile_id"], department_id=dept.id, current_role_id=role.id,
                     target_role_id=nxt.id if nxt else None, consent_at=now)
        db.add(e)
        emps[p["profile_id"]] = (e, p)
    db.commit()
    pw = hash_password("demo123")
    e1, e2 = emps["E-001"][0], emps["E-002"][0]
    users = [User(username="employee", password_hash=pw, role="employee", display_name="Қызметкер E-001",
                  department_id=e1.department_id, employee_id=e1.id),
             User(username="employee2", password_hash=pw, role="employee", display_name="Сотрудник E-002",
                  department_id=e2.department_id, employee_id=e2.id),
             User(username="manager", password_hash=pw, role="manager", display_name="Бөлім басшысы (талдау)",
                  department_id=depts[0].id),
             User(username="manager2", password_hash=pw, role="manager", display_name="Бөлім басшысы (BI)",
                  department_id=depts[1].id),
             User(username="hr", password_hash=pw, role="hr", display_name="HR / L&D маманы")]
    db.add_all(users)
    db.commit()
    if analyze:
        for code, (e, p) in emps.items():
            r = analyze_employee(db, e, p["text"], actor="seed", use_llm=False, filename=f"{code}.txt")
            print(f"  {code} [{p['lang']}] {p['role']}: {r['found']} skills")
    print("employees:", len(emps), "users:", [u.username for u in users])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="барлық кестелерді қайта құру (ESCO векторларынан басқа)")
    ap.add_argument("--full-reset", action="store_true", help="ESCO векторларымен бірге толық қайта құру")
    ap.add_argument("--no-analyze", action="store_true")
    args = ap.parse_args()
    if args.full_reset:
        Base.metadata.drop_all(engine)
    elif args.reset:
        keep = {"skills", "skill_labels", "llm_cache"}
        Base.metadata.drop_all(engine, tables=[t for n, t in Base.metadata.tables.items() if n not in keep])
    init_db()
    db = SessionLocal()
    try:
        load_skills(db)
        if db.scalar(select(func.count()).select_from(Role)):
            print("case data already loaded (use --reset to reload)")
            return
        roles = load_roles(db)
        load_transitions(db, roles)
        load_courses(db)
        load_people(db, roles, analyze=not args.no_analyze)
        db.execute(text("ANALYZE"))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
