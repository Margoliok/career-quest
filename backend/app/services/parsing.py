"""Түйіндемені өңдеу: мәтінді алу, тілді анықтау, бөлімдерге бөлу, сезімтал деректерді жасыру."""
from __future__ import annotations

import io
import re

KK_LETTERS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
CYR = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]")
LAT = re.compile(r"[A-Za-z]")


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if name.endswith(".docx"):
        import docx

        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    for enc in ("utf-8", "utf-16", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def detect_lang(text: str) -> str:
    """kk — қазақ әріптері кездессе, ru — кириллица басым болса, әйтпесе en."""
    if not text:
        return "en"
    kk = sum(ch in KK_LETTERS for ch in text)
    cyr = len(CYR.findall(text))
    lat = len(LAT.findall(text))
    if cyr and kk / max(cyr, 1) > 0.01:
        return "kk"
    if cyr > lat * 0.5:
        return "ru"
    return "en"


# Сезімтал атрибуттар ҮТМ-ге берілмейді (ҚР «Дербес деректер және оларды қорғау туралы» Заңы)
_PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?<!\d)(\+?7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)"), "[телефон]"),
    (re.compile(r"(?<!\d)\d{12}(?!\d)"), "[ЖСН]"),
    (re.compile(r"(?im)^\s*(туған (күні|жылы)|дата рождения|год рождения|жасы|возраст|жынысы|пол|ұлты|"
                r"национальность|отбасылық жағдайы|семейное положение|денсаулығы|здоровье|дін|религия)\s*[:\-–].*$"),
     "[жасырылды]"),
]


def scrub_pii(text: str) -> str:
    for pat, repl in _PII_PATTERNS:
        text = pat.sub(repl, text)
    return text


SECTION_HEADERS = {
    "experience": ["жұмыс тәжірибесі", "тәжірибе", "опыт работы", "опыт", "experience"],
    "education": ["білімі", "білім", "образование", "education"],
    "skills": ["дағдылар", "дағдылары", "навыки", "ключевые навыки", "skills"],
    "projects": ["жобалар", "проекты", "projects"],
}


def segment(text: str) -> dict[str, str]:
    """Түйіндемені бөлімдерге бөлу (тақырып жолдары бойынша)."""
    current, out = "summary", {"summary": []}
    for line in text.splitlines():
        low = line.strip().lower().rstrip(":")
        hit = next((k for k, v in SECTION_HEADERS.items() if low in v), None)
        if hit:
            current = hit
            out.setdefault(current, [])
            continue
        out.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in out.items() if "\n".join(v).strip()}


_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+|\s+[•·▪●-]\s+|^\s*[•·▪●-]\s*", re.M)


def clauses(text: str) -> list[str]:
    """Сөйлемдер мен тізім элементтері (дәлел-фрагмент ретінде қолданылады)."""
    parts = [p.strip(" \t•·▪●-–") for p in _SENT_SPLIT.split(text) if p and p.strip()]
    return [p for p in parts if len(p) >= 3]


_SUB_SPLIT = re.compile(r",|;|\s+және\s+|\s+и\s+|\s+and\s+|\s+сондай-ақ\s+|\s+а также\s+|\(|\)|:")


def sub_phrases(clause: str) -> list[str]:
    """Сөйлем ішіндегі тізімделген дағдыларды бөлек фразаларға бөлу."""
    subs = [s.strip(" .") for s in _SUB_SPLIT.split(clause)]
    return [s for s in subs if len(s) >= 2]


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def is_evidence_in_text(evidence: str, text: str) -> bool:
    """ҮТМ ойдан шығармауы үшін дәлел-фрагмент мәтіннің ішінде болуы тиіс."""
    ev = normalize_ws(evidence)
    return bool(ev) and ev in normalize_ws(text)
