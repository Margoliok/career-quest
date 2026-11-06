"""ҮТМ-агент оркестраторы: құрал шақыру циклі, қорғау ережелері (guardrails), аудит.

ҮТМ қолжетімсіз болса — ниетті кілт сөздер арқылы анықтайтын офлайн жауап беруші (сол құралдармен).
"""
from __future__ import annotations

import json
import re

from ..llm.provider import prompt
from ..services.career import audit
from ..services.parsing import detect_lang, scrub_pii
from .tools import TOOLS, ToolContext, openai_tool_specs

MAX_STEPS = 6
FORBIDDEN = re.compile(
    r"жалақ|зарплат|оклад|сыйақы|преми|бонус|жұмыстан шығар|уволь|увольн|сокращ|қысқарт|жұмысқа ал|найм|нанять|"
    r"рейтинг сотрудник|кого уволить|кім жақсы|кто лучше|salary|fire|dismiss|hire", re.I)

REFUSAL = {
    "kk": "Кешіріңіз, мен жалақы, жұмысқа алу, жұмыстан шығару немесе қызметкерлерді бағалау туралы шешімдер "
          "шығармаймын. Мен тек дағдыларды, мансап жолын және даму жоспарын талдауға көмектесемін. "
          "Мұндай сұрақтар бойынша басшыңызға немесе HR бөліміне жүгініңіз.",
    "ru": "Извините, я не принимаю решений о зарплате, найме, увольнении или оценке сотрудников. Я помогаю только "
          "с анализом навыков, карьерного пути и плана развития. С такими вопросами обратитесь к руководителю "
          "или в HR.",
}


def _lang(text: str, fallback: str) -> str:
    l = detect_lang(text)
    return l if l in ("kk", "ru") else fallback


def run_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    fn = TOOLS[name][0]
    try:
        res = fn(ctx, **args)
    except TypeError as exc:
        res = {"error": f"bad arguments: {exc}"}
    audit(ctx.db, f"agent:{ctx.user.username}", "tool_call", name, ctx.emp.id, args,
          {"args": args, "ok": "error" not in res})
    ctx.db.commit()
    return res


def chat(ctx: ToolContext, message: str, history: list[dict]) -> dict:
    lang = _lang(message, ctx.lang)
    ctx.lang = lang
    if FORBIDDEN.search(message):
        audit(ctx.db, ctx.user.username, "chat_refused", None, ctx.emp.id, message, {"reason": "forbidden_topic"})
        ctx.db.commit()
        return {"answer": REFUSAL[lang], "tool_calls": [], "mode": "guardrail"}
    if ctx.provider is None:
        return offline_chat(ctx, message, lang)
    msgs = [{"role": "system", "content": prompt("chat_system")}]
    for h in history[-8:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            msgs.append({"role": h["role"], "content": scrub_pii(h["content"])[:2000]})
    msgs.append({"role": "user", "content": scrub_pii(message)})
    calls = []
    for _ in range(MAX_STEPS):
        m = ctx.provider.chat(msgs, openai_tool_specs())
        if not m.tool_calls:
            audit(ctx.db, ctx.user.username, "chat_answer", None, ctx.emp.id, message, {"tools": [c["name"] for c in calls]})
            ctx.db.commit()
            return {"answer": m.content or "", "tool_calls": calls, "mode": "llm"}
        msgs.append({"role": "assistant", "content": m.content or "",
                     "tool_calls": [{"id": tc.id, "type": "function",
                                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                    for tc in m.tool_calls]})
        for tc in m.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            res = run_tool(ctx, name, args) if name in TOOLS else {"error": "unknown tool"}
            calls.append({"name": name, "args": args})
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(res, ensure_ascii=False)[:12000]})
    return {"answer": "…", "tool_calls": calls, "mode": "llm"}


# ---------------- Офлайн жауап беруші ----------------
ROLE_CODES = {"jda": "JDA", "junior": "JDA", "кіші": "JDA", "младш": "JDA", "senior": "SDA", "аға": "SDA",
              "старш": "SDA", "bi": "BI", "data scientist": "DS", "ғалым": "DS", "data engineer": "DE",
              "инженер": "DE", "business analyst": "BA", "бизнес": "BA", "data analyst": "DA", "талдаушы": "DA",
              "аналитик данных": "DA"}


def _detect_role(msg: str) -> str | None:
    low = msg.lower()
    for k in sorted(ROLE_CODES, key=len, reverse=True):
        if k in low:
            return ROLE_CODES[k]
    return None


def offline_chat(ctx: ToolContext, message: str, lang: str) -> dict:
    low = message.lower()
    calls = []

    def call(name, **kw):
        calls.append({"name": name, "args": kw})
        return run_tool(ctx, name, kw)

    kk = lang == "kk"
    if re.search(r"неге|неліктен|почему|зачем|ұсынылд|рекоменд", low):
        r = call("suggest_roles")
        lines = [("Ұсынылған рөлдер (гибридті балл = α·ауысу + (1−α)·дағдылар):" if kk else
                  "Рекомендованные роли (гибридный балл = α·переход + (1−α)·навыки):")]
        for x in r["roles"][:3]:
            t = x["title_kk"] if kk else x["title_ru"]
            lines.append(f"• {t}: {x['score']:.2f} = {x['alpha_part']:.2f} + {x['skill_part']:.2f} "
                         f"({'дағдыларды қамту' if kk else 'покрытие навыков'} {x['coverage']:.0%})")
        lines.append("Бірінші бөлік — осы рөлге ауысудың жиілігі, екіншісі — сіздің дағдыларыңыздың сәйкестігі."
                     if kk else "Первая часть — частота перехода в эту роль, вторая — соответствие ваших навыков.")
        answer = "\n".join(lines)
    elif re.search(r"жоспар|план|ждж|ипр|30|60|90", low):
        r = call("save_idp", role=_detect_role(message))
        if "error" in r:
            answer = "Алдымен мақсатты рөлді таңдаңыз." if kk else "Сначала выберите целевую роль."
        else:
            lines = [f"ЖДЖ жобасы сақталды (нұсқа {r['version']}), басшыға келісуге жіберуге болады:" if kk else
                     f"Черновик ИПР сохранён (версия {r['version']}), его можно отправить руководителю:"]
            lines += [f"• {p['period']} {'күн' if kk else 'дней'}: {', '.join(p['skills'])}" for p in r["items"]]
            answer = "\n".join(lines)
    elif re.search(r"курс|оқу|үйрен|обуч|учить", low):
        from ..services.extract import glossary_extract

        named = [{"esco_id": s.esco_id, "label": s.label} for s in glossary_extract(message)]
        if named:  # пайдаланушы нақты дағдыны атады (мысалы, SQL)
            g = {"missing": named}
        else:
            g = call("compute_gap", role=_detect_role(message))
        ids = [m["esco_id"] for m in g.get("missing", [])[:4]]
        c = call("find_courses", esco_ids=ids) if ids else {"courses": {}}
        lines = [("Сұралған дағды бойынша курстар:" if kk else "Курсы по запрошенному навыку:") if named else
                 ("Жетіспейтін дағдылар бойынша курстар:" if kk else "Курсы по недостающим навыкам:")]
        for m in g.get("missing", [])[:4]:
            cs = c["courses"].get(m["esco_id"], [])
            lines.append(f"• {m['label']}: " + ("; ".join(f"{x['title']} ({x['provider']})" for x in cs)
                                                 or ("каталогта курс жоқ" if kk else "в каталоге нет курса")))
        answer = "\n".join(lines)
    elif re.search(r"жетіспей|алшақ|не хватает|разрыв|gap|үшін не|что нужно|нужно для", low) or _detect_role(message):
        g = call("compute_gap", role=_detect_role(message))
        if "error" in g:
            answer = "Алдымен мақсатты рөлді таңдаңыз." if kk else "Сначала выберите целевую роль."
        else:
            lines = [(f"«{g['role']}» рөлін қамту: {g['coverage']:.0%}. Басымдығы жоғары жетіспейтін дағдылар:" if kk
                      else f"Покрытие роли «{g['role']}»: {g['coverage']:.0%}. Самые приоритетные недостающие навыки:")]
            lines += [f"• {m['label']} — {m['employee_level']} → {m['required_level']} (p_s = {m['priority_p_s']:g})"
                      for m in g["missing"][:5]]
            answer = "\n".join(lines)
    else:
        p = call("get_profile")
        n = len(p["skills"])
        answer = (f"Сәлеметсіз бе! Профиліңізде {n} дағды анықталды. Мен көмектесе аламын:\n"
                  "• «Data Analyst рөліне өту үшін маған не жетіспейді?»\n• «Неге маған бұл рөлдер ұсынылды?»\n"
                  "• «SQL бойынша курстар ұсын» • «30/60/90 күндік жоспар құр»" if kk else
                  f"Здравствуйте! В профиле распознано навыков: {n}. Я могу помочь:\n"
                  "• «Чего мне не хватает для роли Data Analyst?»\n• «Почему мне рекомендованы эти роли?»\n"
                  "• «Подбери курсы» • «Составь план на 30/60/90 дней»")
    audit(ctx.db, ctx.user.username, "chat_answer", None, ctx.emp.id, message,
          {"mode": "offline", "tools": [c["name"] for c in calls]})
    ctx.db.commit()
    return {"answer": answer, "tool_calls": calls, "mode": "offline"}
