"""Дағдыларды анықтау конвейері (6-сурет).

Үш тәсіл:
  dictionary — базалық тәсіл: ESCO белгілерімен (preferred + alt) сөздік сәйкестік;
  offline    — ҮТМ-сіз: сөйлемдер/фразалар → көптілді эмбеддинг → ESCO top-k → τ шегі;
  llm        — ұсынылған тәсіл: ҮТМ → JSON (фраза, дәлел, деңгей) → эмбеддинг → top-20 → ҮТМ реранкинг → τ.
Әр дағдының мәтіннен алынған дәлел-фрагменті және ESCO ID-і болуы міндетті.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from ..config import get_settings
from ..llm.provider import LANG_NAMES, OpenAIProvider, prompt
from ..llm.schemas import EXTRACT_SCHEMA, RERANK_SCHEMA, ExtractOut, RerankOut
from . import esco_data
from .parsing import clauses, detect_lang, is_evidence_in_text, normalize_ws, scrub_pii, sub_phrases

STATUS_AUTO = "auto"              # ҮТМ/модель анықтады, ұқсастық ≥ τ (басшы растауын күтеді)
STATUS_UNVERIFIED = "unverified"  # «расталмаған»: ұқсастық < τ немесе сенімділік төмен


@dataclass
class ExtractedSkill:
    esco_id: str
    label: str
    phrase: str
    evidence: str
    level: int
    confidence: float
    similarity: float
    status: str
    method: str
    candidates: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------- Деңгей эвристикасы (офлайн режим үшін рубрика) ----------------
LEVEL_CUES = {
    4: ["эксперт", "сарапшы", "ментор", "тәлімгер", "үйретемін", "оқытамын", "обучаю", "наставни", "жетекшілік",
        "руковож", "архитектур", "басқарамын", "әдістеме", "методик", "lead", "mentor", "expert",
        "тренинг өткіз", "провожу тренинг"],
    1: ["таныс", "знаком", "негіздер", "основы", "базовые знания", "оқып жүрмін", "изучаю", "осваива", "меңгеріп жүр",
        "курс өттім", "курс оқыдым", "онлайн-курс", "прошел курс", "прошла курс", "прошёл", "үйреніп жүрмін",
        "начальн", "basic knowledge", "familiar"],
    2: ["басшылықпен", "басшылығ", "көмегімен", "көмекпен", "бақылауым", "под руководством", "с помощью",
        "под контролем", "қатыстым", "участвовал", "базалық", "assist", "under supervision", "бірге орындадым"],
    3: ["өз бетімше", "дербес жұмыс", "самостоятельн", "уверенн", "сенімді", "тұрақты қолданамын", "регулярно",
        "жауаптымын", "отвечаю за", "толық циклін", "полный цикл", "independent", "own"],
}

_YEARS = re.compile(r"(\d+)\s*(жыл|лет|года|год|years?)", re.I)


def heuristic_level(clause: str) -> int:
    low = clause.lower()
    for lvl in (4, 1, 2, 3):  # алдымен айқын шеткі белгілер (рубрика бойынша)
        if any(c in low for c in LEVEL_CUES[lvl]):
            return lvl
    m = _YEARS.search(low)
    if m and int(m.group(1)) >= 3:
        return 3
    return 2


# ---------------- Базалық тәсіл: сөздік ----------------
_TOKEN = re.compile(r"[\w+#.]+", re.U)


@lru_cache
def _label_lookup() -> tuple[dict[str, tuple[str, str]], int]:
    """normalized label -> (esco_id, preferred label); ұзындығы 3-тен аз белгілер шу болмас үшін алынбайды."""
    lookup: dict[str, tuple[str, str]] = {}
    max_len = 1
    for row in esco_data.load_skills().itertuples():
        for lab in [row.label, *row.alt_labels]:
            key = " ".join(_TOKEN.findall(lab.lower()))
            if len(key) < 3 and key not in {"r", "c"}:
                continue
            lookup.setdefault(key, (row.esco_id, row.label))
            max_len = max(max_len, len(key.split()))
    return lookup, min(max_len, 8)


def dictionary_extract(text: str) -> list[ExtractedSkill]:
    lookup, max_n = _label_lookup()
    out: dict[str, ExtractedSkill] = {}
    for clause in clauses(text):
        toks = _TOKEN.findall(clause.lower())
        i = 0
        while i < len(toks):
            hit = None
            for n in range(min(max_n, len(toks) - i), 0, -1):  # ең ұзын сәйкестік
                key = " ".join(toks[i:i + n])
                if key in lookup:
                    hit = (n, *lookup[key], key)
                    break
            if hit:
                n, eid, label, key = hit
                if eid not in out:
                    out[eid] = ExtractedSkill(eid, label, key, clause, heuristic_level(clause), 1.0, 1.0,
                                              STATUS_AUTO, "dictionary")
                i += n
            else:
                i += 1
    return list(out.values())


# ---------------- Құралдар глоссарийі (тілге тәуелсіз: құрал атаулары аударылмайды) ----------------
@lru_cache
def _glossary() -> list[tuple[re.Pattern, str, str]]:
    import csv

    from .roles import skill_id

    path = get_settings().data_dir / "local" / "tool_glossary.csv"
    out = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pat = re.compile(r"(?<![\w-])" + re.escape(r["term"]) + r"(?![\w])", re.I)
            out.append((pat, skill_id(r["esco_label"]), r["esco_label"]))
    # R тілі — тек бас латын әрпі, бөлек сөз ретінде
    out.append((re.compile(r"(?<![\w/-])R(?![\w/+-])"), skill_id("R"), "R"))
    return out


def glossary_extract(text: str) -> list[ExtractedSkill]:
    found: dict[str, ExtractedSkill] = {}
    for clause in clauses(text):
        for pat, sid, label in _glossary():
            m = pat.search(clause)
            if m and sid not in found:
                found[sid] = ExtractedSkill(sid, label, m.group(0), clause, heuristic_level(clause), 1.0, 1.0,
                                            STATUS_AUTO, "glossary")
    return list(found.values())


# ---------------- Офлайн тәсіл: каталог бойынша эмбеддинг + τ + глоссарий ----------------
def offline_extract(text: str, index, tau: float | None = None, k: int = 5, use_glossary: bool = True
                    ) -> list[ExtractedSkill]:
    tau = get_settings().offline_tau if tau is None else tau
    items: list[tuple[str, str]] = []  # (phrase, evidence clause)
    for clause in clauses(text):
        subs = sub_phrases(clause)
        phrases = list(dict.fromkeys(([clause] if len(subs) <= 1 else []) + subs))
        items += [(p, clause) for p in phrases if len(p) <= 200]
    if not items:
        return []
    results = index.search([p for p, _ in items], k)
    best: dict[str, ExtractedSkill] = {}
    for (phrase, clause), cands in zip(items, results):
        if not cands:
            continue
        top = cands[0]
        if top.sim < tau:
            continue
        prev = best.get(top.esco_id)
        if prev is None or top.sim > prev.similarity:
            best[top.esco_id] = ExtractedSkill(
                top.esco_id, top.label, phrase, clause, heuristic_level(clause), round(top.sim, 4),
                round(top.sim, 4), STATUS_AUTO, "offline",
                [{"esco_id": c.esco_id, "label": c.label, "sim": round(c.sim, 4)} for c in cands[:5]])
    if use_glossary:
        for g in glossary_extract(text):
            best.setdefault(g.esco_id, g)
    return sorted(best.values(), key=lambda s: -s.similarity)


# ---------------- Ұсынылған тәсіл: ҮТМ + эмбеддинг + реранкинг ----------------
def _skill_desc(esco_id: str) -> str:
    sk = _skills_by_id().get(esco_id)
    return (sk or {}).get("description", "")[:160]


@lru_cache
def _skills_by_id() -> dict[str, dict]:
    return {r["esco_id"]: r for r in esco_data.load_skills().to_dict("records")}


def llm_extract(text: str, provider: OpenAIProvider, index, tau: float | None = None, k: int | None = None,
                lang: str | None = None, rerank: bool = True) -> list[ExtractedSkill]:
    s = get_settings()
    tau = s.tau if tau is None else tau
    k = k or s.top_k
    clean = scrub_pii(text)
    lang = lang or detect_lang(clean)

    def check_evidence(obj: ExtractOut) -> None:
        bad = [it.evidence for it in obj.skills if not is_evidence_in_text(it.evidence, clean)]
        if len(bad) > max(2, len(obj.skills) // 3):  # тым көп ойдан шығарылған дәлел — қайта сұраймыз
            raise ValueError(f"{len(bad)} evidence quotes are not exact substrings of the text, e.g. {bad[:2]}")

    # (а) ҮТМ экстракциясы
    ext = provider.json("skill_extraction", EXTRACT_SCHEMA, ExtractOut, prompt("extract_system"),
                        prompt("extract_user").format(lang=LANG_NAMES.get(lang, lang), text=clean),
                        validate=check_evidence)
    items = [it for it in ext.skills if is_evidence_in_text(it.evidence, clean)]  # дәлелсіз дағды алынып тасталады
    if not items:
        return []
    # (б–в) эмбеддинг және ESCO top-k
    queries = [f"{it.skill_en}" if it.skill_en else it.phrase for it in items]
    cands = index.search(queries, k)
    choices: dict[int, tuple[int, float]] = {}
    # (г) ҮТМ реранкинг
    if rerank:
        for start in range(0, len(items), 12):
            chunk = list(range(start, min(start + 12, len(items))))
            payload = [{"i": i, "phrase": items[i].phrase, "skill_en": items[i].skill_en,
                        "evidence": items[i].evidence,
                        "candidates": [{"idx": j, "label": c.label, "description": _skill_desc(c.esco_id)}
                                       for j, c in enumerate(cands[i])]} for i in chunk]
            rr = provider.json("skill_rerank", RERANK_SCHEMA, RerankOut, prompt("rerank_system"),
                               json.dumps(payload, ensure_ascii=False))
            for it in rr.items:
                if it.i in chunk:
                    choices[it.i] = (it.choice, it.confidence)
    out: dict[str, ExtractedSkill] = {}
    for i, it in enumerate(items):
        if not cands[i]:
            continue
        choice, rconf = choices.get(i, (0, it.confidence))
        if choice < 0 or choice >= len(cands[i]):
            continue  # ESCO-да сәйкес ұғым жоқ
        c = cands[i][choice]
        # (д) τ шегі: төмен болса «расталмаған»
        status = STATUS_AUTO if c.sim >= tau else STATUS_UNVERIFIED
        conf = round(min(it.confidence, rconf), 3)
        prev = out.get(c.esco_id)
        if prev is None or conf > prev.confidence:
            out[c.esco_id] = ExtractedSkill(
                c.esco_id, c.label, it.phrase, it.evidence, it.level, conf, round(c.sim, 4), status,
                "llm" if rerank else "llm_norerank",
                [{"esco_id": x.esco_id, "label": x.label, "sim": round(x.sim, 4)} for x in cands[i][:5]])
    return list(out.values())


def extract_skills(text: str, full_index, catalog_index, provider: OpenAIProvider | None = None,
                   lang: str | None = None) -> list[ExtractedSkill]:
    """Жүйедегі негізгі кіру нүктесі: ҮТМ бар болса — ұсынылған тәсіл (толық ESCO), болмаса — офлайн (каталог)."""
    if provider is not None:
        return llm_extract(text, provider, full_index, lang=lang)
    return offline_extract(text, catalog_index)


def same_text(a: str, b: str) -> bool:
    return normalize_ws(a) == normalize_ws(b)
