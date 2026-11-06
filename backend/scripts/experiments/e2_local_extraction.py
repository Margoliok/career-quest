"""Э2. Жергілікті (қаз/орыс) профильдерде дағдыларды анықтау: P, R, F1 (6)–(8), деңгей дәлдігі.

Тәсілдер:
  dictionary            — базалық: ESCO белгілерімен сөздік сәйкестік (толық ESCO)
  glossary              — тек құралдар глоссарийі
  emb_full_e5-small     — толық ESCO бойынша эмбеддинг (каталогсыз), e5-small
  offline_<model>       — ұйым каталогы бойынша эмбеддинг + глоссарий (e5-small / e5-base / bge-m3)
  llm / llm_norerank    — ұсынылған тәсіл (OPENAI_API_KEY болса ғана)
τ dev жиында F1 бойынша таңдалады, нәтиже test жиында есептеледі.
Іске қосу:  python -m scripts.experiments.e2_local_extraction [--llm] [--models ...]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from app.llm.provider import FileCache, get_provider
from app.services.esco_search import domain_index, numpy_index
from app.services.extract import dictionary_extract, glossary_extract, llm_extract, offline_extract

from .common import aggregate, catalog_ids, load_profiles, reports, score_profile

TAU_GRID = [round(x, 3) for x in np.arange(0.50, 0.96, 0.01)]


def run_with_tau(raw: list[list[dict]], profiles: list[dict], tau: float) -> list[dict]:
    out = []
    for preds, p in zip(raw, profiles):
        keep = [x for x in preds if x["similarity"] >= tau or x["method"] in ("glossary", "dictionary")]
        out.append(score_profile(keep, p["gold"]))
    return out


def evaluate(name: str, raw_all: list[list[dict]], profiles: list[dict], tune: bool, rows: list, curves: dict):
    dev = [i for i, p in enumerate(profiles) if p["split"] == "dev"]
    test = [i for i, p in enumerate(profiles) if p["split"] == "test"]
    tau = None
    if tune:
        f1s = []
        for t in TAU_GRID:
            f1s.append(aggregate(run_with_tau([raw_all[i] for i in dev], [profiles[i] for i in dev], t))["F1"])
        tau = TAU_GRID[int(np.argmax(f1s))]
        curves[name] = {"tau": TAU_GRID, "dev_f1": f1s}
    t = tau if tau is not None else 0.0
    for subset, langs in (("all", ("kk", "ru")), ("kk", ("kk",)), ("ru", ("ru",))):
        idx = [i for i in test if profiles[i]["lang"] in langs]
        agg = aggregate(run_with_tau([raw_all[i] for i in idx], [profiles[i] for i in idx], t))
        rows.append({"method": name, "lang": subset, "tau": tau, **agg})
    print(f"{name:28s} τ={tau}  " + "  ".join(f"{r['lang']}: F1={r['F1']:.3f}" for r in rows[-3:]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["intfloat/multilingual-e5-small", "intfloat/multilingual-e5-base",
                                                    "BAAI/bge-m3"])
    ap.add_argument("--llm", action="store_true", help="ҮТМ тәсілдерін де іске қосу (токен жұмсалады)")
    args = ap.parse_args()
    profiles = load_profiles()
    cat = catalog_ids()
    rows: list[dict] = []
    curves: dict = {}
    print(f"profiles: {len(profiles)} (test={sum(p['split'] == 'test' for p in profiles)}), catalogue skills: {len(cat)}")

    evaluate("dictionary", [[s.to_dict() for s in dictionary_extract(p["text"])] for p in profiles], profiles,
             False, rows, curves)
    evaluate("glossary", [[s.to_dict() for s in glossary_extract(p["text"])] for p in profiles], profiles,
             False, rows, curves)
    full = numpy_index()
    evaluate("emb_full_e5-small", [[s.to_dict() for s in offline_extract(p["text"], full, tau=0.0, use_glossary=False)]
                                   for p in profiles], profiles, True, rows, curves)
    for m in args.models:
        ix = domain_index(cat, m)
        slug = m.split("/")[-1]
        raw = [[s.to_dict() for s in offline_extract(p["text"], ix, tau=0.0, use_glossary=False)] for p in profiles]
        evaluate(f"catalog_{slug}", raw, profiles, True, rows, curves)
        raw_g = [[s.to_dict() for s in offline_extract(p["text"], ix, tau=0.0, use_glossary=True)] for p in profiles]
        evaluate(f"offline_{slug}", raw_g, profiles, True, rows, curves)

    if args.llm:
        cache = FileCache(reports() / "llm_cache" / "e2.jsonl")
        prov = get_provider(cache)
        if prov is None:
            print("LLM skipped: OPENAI_API_KEY is not set")
        else:
            for rerank in (False, True):
                raw = [[s.to_dict() for s in llm_extract(p["text"], prov, full, tau=0.0, rerank=rerank)]
                       for p in profiles]
                evaluate("llm" if rerank else "llm_norerank", raw, profiles, True, rows, curves)
            print("LLM usage:", prov.usage)

    out = reports()
    df = pd.DataFrame(rows)
    df.to_csv(out / "tables" / "e2_local_extraction.csv", index=False, encoding="utf-8-sig")
    (out / "tables" / "e2_tau_curves.json").write_text(json.dumps(curves, indent=1), encoding="utf-8")
    print(df[df.lang == "all"].to_string(index=False))


if __name__ == "__main__":
    main()
