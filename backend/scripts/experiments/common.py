"""Эксперименттерге ортақ көмекші функциялар."""
from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.services.metrics import prf
from app.services.roles import build_requirements, load_case_config


def reports() -> Path:
    p = get_settings().reports_dir
    for sub in ("tables", "figures"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p


def load_profiles(split: str | None = None) -> list[dict]:
    path = get_settings().data_dir / "local" / "profiles.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if split is None or r["split"] == split]


def catalog_ids() -> tuple[str, ...]:
    cfg = load_case_config()
    ids: set[str] = set()
    for r in cfg["roles"]:
        ids |= {x["esco_id"] for x in build_requirements(r, cfg["level_scheme"])[0]}
    return tuple(sorted(ids))


def score_profile(pred: list[dict], gold: list[dict]) -> dict:
    """Эталон элементінде бірнеше қабылданатын ESCO ID болуы мүмкін.

    TP — болжаммен табылған эталон элементтері; FN — табылмағандары;
    FP — ешбір эталон элементіне сәйкес келмейтін болжамдар.
    """
    gold_ids = set().union(*[set(g["ids"]) for g in gold]) if gold else set()
    tp = fn = 0
    lvl_pairs = []
    for g in gold:
        hit = next((p for p in pred if p["esco_id"] in g["ids"]), None)
        if hit:
            tp += 1
            if g.get("level") and hit.get("level"):
                lvl_pairs.append((g["level"], hit["level"]))
        else:
            fn += 1
    fp = sum(1 for p in pred if p["esco_id"] not in gold_ids)
    return {"tp": tp, "fp": fp, "fn": fn, "levels": lvl_pairs}


def aggregate(scores: list[dict]) -> dict:
    tp = sum(s["tp"] for s in scores)
    fp = sum(s["fp"] for s in scores)
    fn = sum(s["fn"] for s in scores)
    p, r, f1 = prf(tp, fp, fn)
    lv = [pair for s in scores for pair in s["levels"]]
    acc = sum(1 for g, q in lv if g == q) / len(lv) if lv else float("nan")
    mae = sum(abs(g - q) for g, q in lv) / len(lv) if lv else float("nan")
    return {"P": round(p, 4), "R": round(r, 4), "F1": round(f1, 4), "TP": tp, "FP": fp, "FN": fn,
            "level_acc": round(acc, 4), "level_mae": round(mae, 4), "n_level": len(lv)}
