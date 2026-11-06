"""Синтетикалық қызметкер профильдерін генерациялау (қаз/орыс) — үлгілер негізінде, ҮТМ-сіз.

Эталондық белгілеу (ESCO ID + деңгей) профиль құрастырылған кезде белгілі, сондықтан оны
ҮТМ жасамайды (2.1-бөлімдегі әдіснамалық тұзақ: ҮТМ өз жасаған деректерін бағаламауы тиіс).
Шығыс: data/local/profiles.jsonl, data/local/annotation_template.csv
Іске қосу:  python -m scripts.generate_profiles --n 48 --seed 2026
"""
from __future__ import annotations

import argparse
import csv
import json
import random

from app.config import get_settings
from app.services.roles import load_case_config, skill_id

from .lexicon import FRAMES, GRADE_LEVELS, LEX, NOISE, PII, ROLE_SKILLS, TOOLS

TOOL_GOLD = {"SQL": "SQL", "Excel": "use spreadsheets software", "Power BI": "data visualisation software",
             "Tableau": "data visualisation software", "Python": "Python (computer programming)",
             "pandas": "Python (computer programming)", "scikit-learn": "machine learning", "PyTorch": "deep learning",
             "Airflow": "data extraction, transformation and loading tools", "PostgreSQL": "PostgreSQL",
             "Git": "tools for software configuration management", "AWS": "cloud technologies"}

HEAD = {
    "kk": {"code": "Қызметкер коды", "pos": "Лауазымы", "years": "Жалпы тәжірибесі", "y": "жыл",
           "exp": "Жұмыс тәжірибесі:", "tools": "Құралдар", "edu": "Білімі: бакалавр, {y} ж.",
           "hob": "Қызығушылықтары:", "job": "{a}–{b} жж.: «{c}» компаниясы, {t}"},
    "ru": {"code": "Код сотрудника", "pos": "Должность", "years": "Общий опыт, лет", "y": "",
           "exp": "Опыт работы:", "tools": "Инструменты", "edu": "Образование: бакалавр, {y} г.",
           "hob": "Интересы:", "job": "{a}–{b} гг.: компания «{c}», {t}"},
}
COMPANIES = ["Дала Дата", "Сарыарқа Телеком", "Нұр Ритейл", "Астана Логистик", "Qazaq Fintech", "Есіл Энерго"]


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def make_profile(i: int, role: dict, lang: str, rng: random.Random, all_ids: set[str]) -> dict:
    code = role["code"]
    h = HEAD[lang]
    keys = ROLE_SKILLS[code][:]
    rng.shuffle(keys)
    keys = keys[: rng.randint(6, min(10, len(keys)))]
    lo, hi = GRADE_LEVELS[code]
    gold: dict[str, dict] = {}
    sentences = []
    for key in keys:
        e = LEX[key]
        lvl = max(1, min(4, rng.choice([lo, hi, hi]) + rng.choice([0, 0, 0, -1, 1])))
        frame = rng.choice(FRAMES[lang][lvl])
        np_ = rng.choice(e[f"{lang}_np"])
        vp = rng.choice(e[f"{lang}_vp"])
        sentences.append(cap(frame.format(np=np_, vp=vp)) + ".")
        ids = [skill_id(x) for x in e["gold"]]
        gold[key] = {"key": key, "ids": ids, "labels": e["gold"], "level": lvl}
        if "{vp}" in frame:
            for extra in e.get("extra_gold", []):
                gold[f"{key}+{extra}"] = {"key": f"{key}+{extra}", "ids": [skill_id(extra)], "labels": [extra],
                                          "level": None}
    tools = rng.sample(TOOLS[code], k=min(len(TOOLS[code]), rng.randint(2, 4)))
    for t in tools:
        sid = skill_id(TOOL_GOLD[t])
        if not any(sid in g["ids"] for g in gold.values()):
            gold[f"tool:{t}"] = {"key": f"tool:{t}", "ids": [sid], "labels": [TOOL_GOLD[t]], "level": None}
    for g in gold.values():
        if not any(x in all_ids for x in g["ids"]):  # кемінде бір нұсқа каталогта болуы тиіс
            raise ValueError(f"gold skill not in the role catalogue: {g['labels']}")
    years = rng.randint(1, 9) if code not in ("JDA",) else rng.randint(0, 2)
    start = 2026 - years
    title = role[f"title_{lang}"]
    pii = [p.format(year=rng.randint(1985, 2003), d=rng.randint(0, 8), n3=rng.randint(100, 999),
                    n2=rng.randint(10, 99), n2b=rng.randint(10, 99),
                    g=("әйел" if lang == "kk" else "женский") if rng.random() < .5 else ("ер" if lang == "kk" else "мужской"))
           for p in PII[lang]]
    lines = [f"{h['code']}: E-{i:03d}", f"{h['pos']}: {title}", f"{h['years']}: {years} {h['y']}".rstrip(), *pii, "",
             h["exp"], h["job"].format(a=start, b=2026, c=rng.choice(COMPANIES), t=title)]
    lines += [f"• {s}" for s in sentences]
    lines += ["", f"{h['tools']}: {', '.join(tools)}", h["edu"].format(y=start - rng.randint(0, 2)),
              f"{h['hob']} {' '.join(rng.sample(NOISE[lang], 2))}"]
    return {"profile_id": f"E-{i:03d}", "lang": lang, "role": code, "text": "\n".join(lines),
            "gold": list(gold.values())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--dev", type=int, default=12)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    cfg = load_case_config()
    from app.services.roles import build_requirements

    all_ids = set()
    for r in cfg["roles"]:
        all_ids |= {x["esco_id"] for x in build_requirements(r, cfg["level_scheme"])[0]}
    roles = cfg["roles"]
    profiles = []
    for i in range(1, args.n + 1):
        lang = "kk" if i % 2 else "ru"
        role = roles[(i - 1) // 2 % len(roles)]
        p = make_profile(i, role, lang, rng, all_ids)
        profiles.append(p)
    idx = list(range(len(profiles)))
    rng.shuffle(idx)
    dev = set()
    for lang in ("kk", "ru"):
        dev |= set([j for j in idx if profiles[j]["lang"] == lang][: args.dev // 2])
    for j, p in enumerate(profiles):
        p["split"] = "dev" if j in dev else "test"
    out = get_settings().data_dir / "local"
    with (out / "profiles.jsonl").open("w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with (out / "annotation_template.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["profile_id", "lang", "evidence_fragment", "esco_id", "esco_label", "level_1_4", "annotator",
                    "comment"])
        w.writerow(["R-001", "kk", "«мәтіннен дәлме-дәл үзінді»", "http://data.europa.eu/esco/skill/...",
                    "perform data cleansing", "3", "A1", ""])
    n_gold = sum(len(p["gold"]) for p in profiles)
    print(f"profiles={len(profiles)} (dev={len(dev)}), gold items={n_gold}, "
          f"avg={n_gold / len(profiles):.1f}; saved to {out / 'profiles.jsonl'}")
    print(profiles[0]["text"])
    print(profiles[1]["text"])


if __name__ == "__main__":
    main()
