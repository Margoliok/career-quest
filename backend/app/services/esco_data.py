"""ESCO CSV файлдарын оқу (ресми жүктеме немесе scripts/fetch_esco.py нәтижесі)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import get_settings


def esco_dir() -> Path:
    return get_settings().data_dir / "esco"


def _split_alt(v) -> list[str]:
    if not isinstance(v, str) or not v.strip():
        return []
    return [x.strip() for x in v.split("\n") if x.strip()]


def _norm_type(v: str) -> str:
    v = (v or "").lower()
    if "knowledge" in v:
        return "knowledge"
    if "language" in v:
        return "language"
    return "skill/competence"


@lru_cache
def load_skills() -> pd.DataFrame:
    df = pd.read_csv(esco_dir() / "skills_en.csv", dtype=str).fillna("")
    df = df.rename(columns={"conceptUri": "esco_id", "preferredLabel": "label"})
    df["alt_labels"] = df["altLabels"].map(_split_alt)
    df["type"] = df["skillType"].map(_norm_type)
    df["description"] = df.get("description", "")
    return df[["esco_id", "label", "alt_labels", "type", "reuseLevel", "description"]].drop_duplicates("esco_id")


@lru_cache
def load_occupations() -> pd.DataFrame:
    df = pd.read_csv(esco_dir() / "occupations_en.csv", dtype=str).fillna("")
    df = df.rename(columns={"conceptUri": "esco_id", "preferredLabel": "label"})
    df["alt_labels"] = df["altLabels"].map(_split_alt)
    return df[["esco_id", "label", "alt_labels", "code", "description"]].drop_duplicates("esco_id")


@lru_cache
def load_relations() -> pd.DataFrame:
    df = pd.read_csv(esco_dir() / "occupationSkillRelations_en.csv", dtype=str).fillna("")
    df = df.rename(columns={"occupationUri": "occupation_id", "skillUri": "esco_id", "relationType": "relation"})
    df["relation"] = df["relation"].str.lower().map(lambda r: "essential" if r.startswith("ess") else "optional")
    return df[["occupation_id", "relation", "esco_id"]].drop_duplicates()


def occupation_by_label(label: str) -> dict | None:
    occ = load_occupations()
    hit = occ[occ["label"].str.lower() == label.lower()]
    return None if hit.empty else hit.iloc[0].to_dict()


def skill_by_label(label: str) -> dict | None:
    sk = load_skills()
    hit = sk[sk["label"].str.lower() == label.lower()]
    return None if hit.empty else hit.iloc[0].to_dict()
