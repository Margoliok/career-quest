"""Э1. SkillSpan (ағылшын вакансиялары) — дағды/білім фрагменттерін анықтау: span-деңгейіндегі P, R, F1.

Эталон: tags_skill және tags_knowledge (BIO) біріктірілген фрагменттер.
strict — шекаралары дәл сәйкес; loose — кемінде бір ортақ токен.
Тәсілдер (оқытусыз): dictionary — ESCO белгілерінің ең ұзын сәйкестігі; glossary+dictionary;
llm — ҮТМ сөйлемдерден фрагменттерді шығарады (OPENAI_API_KEY болса, --llm, іріктеме --sample).
Ескерту: түпнұсқа мақаладағы нәтижелер SkillSpan-да оқытылған модельдерге тиесілі, тікелей салыстыруға келмейді.
Іске қосу:  python -m scripts.experiments.e1_skillspan [--llm] [--sample 300]
"""
from __future__ import annotations

import argparse
import json
import random
import re

import pandas as pd
from pydantic import BaseModel

from app.config import get_settings
from app.llm.provider import FileCache, get_provider
from app.services.extract import _label_lookup
from app.services.metrics import prf

from .common import reports

SPAN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["i", "spans"],
        "properties": {"i": {"type": "integer"}, "spans": {"type": "array", "items": {"type": "string"}}}}}},
}
SPAN_PROMPT = (
    "You annotate job-posting sentences for skill extraction (SkillSpan guidelines). For every sentence, return the "
    "exact contiguous substrings that are SKILL spans (abilities to perform tasks, incl. soft skills, e.g. 'work "
    "independently', 'communicate with clients') or KNOWLEDGE spans (facts, tools, technologies, certifications, e.g. "
    "'Python', 'Java', 'project management'). Copy spans verbatim, tokens separated by single spaces as given. "
    "Return an empty list when there are none. Output JSON only.")


class SpanItem(BaseModel):
    i: int
    spans: list[str]


class SpanOut(BaseModel):
    items: list[SpanItem]


def load(split: str) -> list[dict]:
    path = get_settings().data_dir / "skillspan" / f"{split}.json"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def bio_spans(tags: list[str]) -> set[tuple[int, int]]:
    out, start = set(), None
    for i, t in enumerate(tags + ["O"]):
        if t.startswith("B") or t == "O":
            if start is not None:
                out.add((start, i))
                start = None
            if t.startswith("B"):
                start = i
        elif t.startswith("I") and start is None:
            start = i
    return out


def gold(s: dict) -> set[tuple[int, int]]:
    return bio_spans(s["tags_skill"]) | bio_spans(s["tags_knowledge"])


def dict_spans(tokens: list[str]) -> set[tuple[int, int]]:
    lookup, max_n = _label_lookup()
    low = [re.sub(r"[^\w+#.]", "", t.lower()) for t in tokens]
    out, i = set(), 0
    while i < len(low):
        hit = 0
        for n in range(min(max_n, len(low) - i), 0, -1):
            key = " ".join(x for x in low[i:i + n] if x)
            if key and key in lookup and low[i] and low[i + n - 1]:
                hit = n
                break
        if hit:
            out.add((i, i + hit))
            i += hit
        else:
            i += 1
    return out


def text_to_spans(tokens: list[str], spans: list[str]) -> set[tuple[int, int]]:
    out = set()
    low = [t.lower() for t in tokens]
    for sp in spans:
        st = sp.lower().split()
        n = len(st)
        if not n:
            continue
        for i in range(len(low) - n + 1):
            if low[i:i + n] == st:
                out.add((i, i + n))
                break
    return out


def score(preds: list[set], golds: list[set]) -> dict:
    tp = fp = fn = 0
    ltp_p = ltp_g = n_p = n_g = 0
    for p, g in zip(preds, golds):
        tp += len(p & g)
        fp += len(p - g)
        fn += len(g - p)
        n_p += len(p)
        n_g += len(g)
        ltp_p += sum(1 for a in p if any(a[0] < b[1] and b[0] < a[1] for b in g))
        ltp_g += sum(1 for b in g if any(a[0] < b[1] and b[0] < a[1] for a in p))
    P, R, F = prf(tp, fp, fn)
    lp = ltp_p / n_p if n_p else 0.0
    lr = ltp_g / n_g if n_g else 0.0
    lf = 2 * lp * lr / (lp + lr) if lp + lr else 0.0
    return {"P": round(P, 4), "R": round(R, 4), "F1": round(F, 4), "P_loose": round(lp, 4), "R_loose": round(lr, 4),
            "F1_loose": round(lf, 4), "gold_spans": n_g, "pred_spans": n_p}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--sample", type=int, default=300)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()
    test = [s for s in load("test") if not all(t.startswith("<") for t in s["tokens"])]
    random.seed(args.seed)
    sample = random.sample(test, min(args.sample, len(test)))
    rows = []
    g_all = [gold(s) for s in test]
    rows.append({"method": "dictionary (ESCO labels)", "subset": f"test (n={len(test)})",
                 **score([dict_spans(s["tokens"]) for s in test], g_all)})
    g_s = [gold(s) for s in sample]
    rows.append({"method": "dictionary (ESCO labels)", "subset": f"sample (n={len(sample)})",
                 **score([dict_spans(s["tokens"]) for s in sample], g_s)})
    if args.llm:
        prov = get_provider(FileCache(reports() / "llm_cache" / "e1.jsonl"))
        if prov is None:
            print("LLM skipped: OPENAI_API_KEY is not set")
        else:
            preds = []
            for st in range(0, len(sample), 20):
                chunk = sample[st:st + 20]
                payload = [{"i": i, "sentence": " ".join(s["tokens"])} for i, s in enumerate(chunk)]
                out = prov.json("skillspan_spans", SPAN_SCHEMA, SpanOut, SPAN_PROMPT, json.dumps(payload))
                by_i = {it.i: it.spans for it in out.items}
                preds += [text_to_spans(s["tokens"], by_i.get(i, [])) for i, s in enumerate(chunk)]
            rows.append({"method": f"LLM zero-shot ({prov.model})", "subset": f"sample (n={len(sample)})",
                         **score(preds, g_s)})
            print("LLM usage:", prov.usage)
    df = pd.DataFrame(rows)
    df.to_csv(reports() / "tables" / "e1_skillspan.csv", index=False, encoding="utf-8-sig")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
