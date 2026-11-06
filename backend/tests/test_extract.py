"""Дағдыларды анықтау ережелері: дәлел-фрагмент, глоссарий, деңгей, PII, JSON валидациясы мен қайталау."""
import json
from types import SimpleNamespace

import pytest

from app.llm.provider import LLMError, OpenAIProvider
from app.llm.schemas import EXTRACT_SCHEMA, ExtractOut
from app.services.esco_search import Candidate
from app.services.extract import glossary_extract, heuristic_level, llm_extract
from app.services.parsing import detect_lang, is_evidence_in_text, scrub_pii
from app.services.roles import skill_id


def test_detect_lang():
    assert detect_lang("Деректерді тазалау және SQL сұраныстары") == "kk"
    assert detect_lang("Пишу SQL-запросы и строю дашборды") == "ru"
    assert detect_lang("I write SQL queries") == "en"


def test_scrub_pii():
    t = "Телефон: +7 701 123 45 67\nemail a.b@mail.kz\nЖынысы: әйел\nSQL"
    s = scrub_pii(t)
    assert "701" not in s and "mail.kz" not in s and "әйел" not in s and "SQL" in s


def test_evidence_must_be_substring():
    text = "Аға әріптестің басшылығымен деректерді тазалаймын."
    assert is_evidence_in_text("деректерді   тазалаймын", text)
    assert not is_evidence_in_text("Python тілінде бағдарламалаймын", text)


def test_glossary_and_level():
    found = {s.label for s in glossary_extract("Құралдар: SQL, Power BI, Excel; R тілінде есептеймін")}
    assert {"SQL", "data visualisation software", "use spreadsheets software", "R"} <= found
    assert heuristic_level("SQL негіздерімен таныспын") == 1
    assert heuristic_level("под руководством старшего коллеги") == 2
    assert heuristic_level("самостоятельно веду задачи") == 3
    assert heuristic_level("ко мне обращаются как к эксперту") == 4


class FakeIndex:
    def search(self, phrases, k=None):
        sid = skill_id("perform data cleansing")
        return [[Candidate(sid, "perform data cleansing", "perform data cleansing", 0.95)] for _ in phrases]


class FakeCompletions:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = 0

    def create(self, **kw):
        self.calls += 1
        content = self.contents.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None)


def fake_provider(contents):
    p = object.__new__(OpenAIProvider)
    p.model, p.cache, p.max_retries = "fake", None, 2
    p.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "cache_hits": 0}
    comp = FakeCompletions(contents)
    p.client = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    return p, comp


def test_json_retry_then_success():
    good = json.dumps({"skills": [{"phrase": "тазалау", "skill_en": "perform data cleansing",
                                   "evidence": "деректерді тазалаймын", "level": 3, "confidence": 0.9}]})
    p, comp = fake_provider(["{not json", good])
    out = p.json("x", EXTRACT_SCHEMA, ExtractOut, "s", "u")
    assert comp.calls == 2 and out.skills[0].level == 3


def test_json_retry_exhausted():
    p, comp = fake_provider(["bad", "bad", "bad"])
    with pytest.raises(LLMError):
        p.json("x", EXTRACT_SCHEMA, ExtractOut, "s", "u")
    assert comp.calls == 3  # 1 + 2 қайталау


def test_llm_extract_drops_hallucinated_evidence():
    text = "Мен деректерді тазалаймын және есептер дайындаймын."
    extraction = json.dumps({"skills": [
        {"phrase": "тазалау", "skill_en": "perform data cleansing", "evidence": "деректерді тазалаймын",
         "level": 3, "confidence": 0.9},
        {"phrase": "Python", "skill_en": "Python", "evidence": "Python тілінде жазамын", "level": 3,
         "confidence": 0.9}]})
    rerank = json.dumps({"items": [{"i": 0, "choice": 0, "confidence": 0.9}]})
    p, _ = fake_provider([extraction, rerank])
    res = llm_extract(text, p, FakeIndex(), tau=0.8)
    assert len(res) == 1 and res[0].label == "perform data cleansing" and res[0].status == "auto"
