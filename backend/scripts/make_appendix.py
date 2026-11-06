"""Дипломның 1–3 қосымшаларын жасау (reports/appendix/*.md) — бастапқы кодтан автоматты түрде.

1-қосымша: агент құралдары (Кесте Қ1.1), промпттар (Листинг Қ1.1), JSON-схемалар (Листинг Қ1.2).
2-қосымша: extract.py, gap.py, recommend.py листингтері (Қ2.1–Қ2.3).
3-қосымша: сарапшылық бағалау сауалнамасы (Кесте Қ3.1), SUS сауалнамасы қазақ тілінде (Кесте Қ3.2).
Іске қосу:  python -m scripts.make_appendix
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from app.agent.tools import TOOLS
from app.config import ROOT, get_settings
from app.llm import schemas

APP = ROOT / "backend" / "app"

SUS_KK = [
    "Мен бұл жүйені жиі қолданғым келеді деп ойлаймын.",
    "Жүйе қажетсіз күрделі деп ойлаймын.",
    "Жүйені пайдалану оңай деп ойлаймын.",
    "Бұл жүйені пайдалану үшін маған техникалық маманның көмегі қажет болады.",
    "Жүйенің әртүрлі функциялары жақсы біріктірілген.",
    "Жүйеде сәйкессіздіктер тым көп.",
    "Көпшілік бұл жүйені тез үйреніп алады деп ойлаймын.",
    "Жүйені пайдалану өте ыңғайсыз.",
    "Жүйені пайдалану кезінде өзімді сенімді сезіндім.",
    "Жүйемен жұмыс істей бастау үшін көп нәрсені үйренуім керек болды.",
]
EXPERT_KK = [
    ("Сәйкестік", "Жоспардағы дағдылар қызметкердің мақсатты рөліне және қазіргі деңгейіне сәйкес келеді"),
    ("Орындалуы", "Жоспар 30/60/90 күн ішінде жұмыстан қол үзбей орындауға болатындай нақты"),
    ("Түсіндірменің айқындығы", "Неге дәл осы дағдылар мен рет таңдалғаны түсінікті"),
]


def tool_rows() -> list[tuple[str, str, str]]:
    outputs = {
        "get_profile": "Профиль: ағымдағы/мақсатты рөл, дағдылар (ESCO ID, деңгей, мәртебе)",
        "extract_skills": "Талдау нәтижесі: табылған/қосылған/жаңартылған дағдылар саны",
        "search_esco": "top-k ESCO дағдылары (ID, атауы, ұқсастық)",
        "compute_gap": "C(e,r), жетіспейтін дағдылар тізімі (p_s бойынша)",
        "suggest_roles": "Рөлдер рейтингі және α·P̃, (1−α)·C құрамдас бөліктері",
        "find_courses": "Курстар (атауы, провайдер, тіл, сілтеме)",
        "save_idp": "ЖДЖ нұсқасы, мәртебесі (draft), кезеңдер",
    }
    rows = []
    for name, (_, _desc, props) in TOOLS.items():
        inp = ", ".join(props.keys()) or "— (employee_id сессиядан)"
        rows.append((f"`{name}`", inp, outputs[name]))
    return rows


def appendix1() -> str:
    p = APP / "llm" / "prompts"
    out = ["# 1-қосымша. ҮТМ промпттары және агент құралдарының JSON-схемалары", "",
           "**Кесте Қ1.1 – Агент құралдарының кіріс/шығыс параметрлері**", "",
           "| Құрал | Кіріс | Шығыс |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in tool_rows()]
    out += ["", "Ескерту – автор құрастырған (backend/app/agent/tools.py).", ""]
    for i, name in enumerate(["extract_system", "extract_user", "rerank_system", "idp_system", "chat_system"], 1):
        out += [f"**Листинг Қ1.1.{i} – `{name}.txt` промпты**", "", "```text", (p / f"{name}.txt").read_text(encoding="utf-8").strip(), "```", ""]
    for i, (nm, sch) in enumerate([("EXTRACT_SCHEMA", schemas.EXTRACT_SCHEMA), ("RERANK_SCHEMA", schemas.RERANK_SCHEMA),
                                   ("IDP_TEXT_SCHEMA", schemas.IDP_TEXT_SCHEMA)], 1):
        out += [f"**Листинг Қ1.2.{i} – {nm} (OpenAI structured outputs, strict)**", "", "```json",
                json.dumps(sch, ensure_ascii=False, indent=2), "```", ""]
    out += ["Тексеру ережелері: дәлел-фрагмент мәтіннің ішінде болуы тиіс (әйтпесе дағды алынып тасталады); "
            "JSON схемаға сәйкес келмесе — ең көбі 2 рет қайта сұрау; ұқсастық τ-дан төмен болса — «расталмаған».", ""]
    return "\n".join(out)


def appendix2() -> str:
    out = ["# 2-қосымша. Бағдарлама кодының негізгі фрагменттері", ""]
    for i, f in enumerate(["services/extract.py", "services/gap.py", "services/recommend.py"], 1):
        out += [f"**Листинг Қ2.{i} – {Path(f).name}**", "", "```python", (APP / f).read_text(encoding="utf-8").strip(), "```", ""]
    return "\n".join(out)


def appendix3() -> str:
    out = ["# 3-қосымша. Сауалнамалар", "", "**Кесте Қ3.1 – Жеке даму жоспарын сарапшылық бағалау сауалнамасы**", "",
           "Нұсқаулық: әр профиль үшін A және B жоспарларын (қай жоспарды жүйе жасағаны көрсетілмейді) төмендегі "
           "өлшемдер бойынша 1-ден 5-ке дейін бағалаңыз (1 — мүлдем сәйкес емес, 5 — толық сәйкес).", "",
           "| № | Өлшем | Сипаттамасы | Балл (1–5) |", "|---|---|---|---|"]
    out += [f"| {i} | {a} | {b} | |" for i, (a, b) in enumerate(EXPERT_KK, 1)]
    out += ["", "Ескерту – автор құрастырған.", "", "**Кесте Қ3.2 – SUS сауалнамасы (қазақ тілінде)**", "",
            "Әр тұжырымға келісу деңгейін белгілеңіз: 1 — мүлдем келіспеймін … 5 — толық келісемін.", "",
            "| № | Тұжырым | 1 | 2 | 3 | 4 | 5 |", "|---|---|---|---|---|---|---|"]
    out += [f"| {i} | {q} | | | | | |" for i, q in enumerate(SUS_KK, 1)]
    out += ["", "Ескерту – Brooke (1996) SUS шкаласының автор жасаған қазақша аудармасы; есептеу (12) формула бойынша.", ""]
    return "\n".join(out)


def main() -> None:
    d = get_settings().reports_dir / "appendix"
    d.mkdir(parents=True, exist_ok=True)
    (d / "appendix1_prompts_schemas.md").write_text(appendix1(), encoding="utf-8")
    (d / "appendix2_code.md").write_text(appendix2(), encoding="utf-8")
    (d / "appendix3_forms.md").write_text(appendix3(), encoding="utf-8")
    forms = get_settings().reports_dir / "forms"
    forms.mkdir(parents=True, exist_ok=True)
    with (forms / "sus_answers_template.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["group", "respondent", *[f"q{i}" for i in range(1, 11)]])
        w.writerow(["employee", "R01", *[""] * 10])
    print("appendix →", d)


if __name__ == "__main__":
    main()
