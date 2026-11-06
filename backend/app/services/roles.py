"""Рөл профилін құру: ESCO кәсібі + сарапшы түзетулері + O*NET технологиялары → role_skills."""
from __future__ import annotations

import csv
import json
from functools import lru_cache

from ..config import get_settings
from . import esco_data


def load_case_config() -> dict:
    return json.loads((get_settings().data_dir / "local" / "roles_case.json").read_text(encoding="utf-8"))


@lru_cache
def _skill_ids() -> dict[str, str]:
    out: dict[str, str] = {}
    for r in esco_data.load_skills().itertuples():
        out.setdefault(r.label.lower(), r.esco_id)
    return out


def skill_id(label: str) -> str:
    sid = _skill_ids().get(label.lower())
    if not sid:
        raise KeyError(f"ESCO skill label not found: {label!r}")
    return sid


@lru_cache
def onet_mapping() -> dict[str, str]:
    path = get_settings().data_dir / "onet" / "onet_to_esco.csv"
    with path.open(encoding="utf-8") as f:
        return {r["onet_example"]: r["esco_label"] for r in csv.DictReader(f)}


def onet_in_demand(soc_codes: list[str]) -> list[str]:
    """O*NET Technology Skills: 'In Demand' = Y белгісі бар технологиялар."""
    path = get_settings().data_dir / "onet" / "Technology Skills.txt"
    if not soc_codes or not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["O*NET-SOC Code"] in soc_codes and r.get("In Demand") == "Y":
                out.append(r["Example"])
    return list(dict.fromkeys(out))


def build_requirements(role: dict, scheme: dict) -> tuple[list[dict], dict]:
    """Рөл талаптарының тізімі және есеп (не алынды/қосылды — дипломдағы сарапшылық бейімдеу үшін)."""
    s = get_settings()
    occ = esco_data.occupation_by_label(role["esco_occupation"])
    if not occ:
        raise KeyError(f"ESCO occupation not found: {role['esco_occupation']}")
    levels = scheme[str(role["grade"])]
    rel = esco_data.load_relations()
    rel = rel[rel.occupation_id == occ["esco_id"]]
    labels = dict(zip(esco_data.load_skills().esco_id, esco_data.load_skills().label))
    excl = {skill_id(x) for x in role.get("essential_exclude", [])}
    incl = {skill_id(x) for x in role.get("optional_include", [])}
    reqs: dict[str, dict] = {}
    for r in rel.itertuples():
        if r.relation == "essential" and r.esco_id not in excl:
            reqs[r.esco_id] = dict(esco_id=r.esco_id, label=labels.get(r.esco_id, ""), weight=s.weight_essential,
                                   required_level=levels["essential"], relation="essential", source="esco")
    for sid in incl:
        if sid not in reqs:
            reqs[sid] = dict(esco_id=sid, label=labels.get(sid, ""), weight=s.weight_optional,
                             required_level=levels["optional"], relation="optional", source="esco")
    onet_added, onet_unmapped = [], []
    for tech in onet_in_demand(role.get("onet_soc", [])):
        lab = onet_mapping().get(tech)
        if not lab:
            onet_unmapped.append(tech)
            continue
        sid = skill_id(lab)
        if sid not in reqs:
            reqs[sid] = dict(esco_id=sid, label=labels.get(sid, ""), weight=s.weight_optional,
                             required_level=levels["optional"], relation="optional", source="onet")
            onet_added.append(f"{tech} → {lab}")
    for ex in role.get("extra", []):
        sid = skill_id(ex["label"])
        reqs[sid] = dict(esco_id=sid, label=labels.get(sid, ""), weight=float(ex["weight"]),
                         required_level=int(ex["level"]), relation="expert", source="expert")
    report = {"role": role["code"], "esco_occupation": occ["label"], "esco_occupation_id": occ["esco_id"],
              "esco_essential_total": int((rel.relation == "essential").sum()),
              "esco_optional_total": int((rel.relation == "optional").sum()),
              "essential_excluded": len(excl), "optional_included": len(incl),
              "onet_added": onet_added, "onet_unmapped": onet_unmapped,
              "expert_added": [e["label"] for e in role.get("extra", [])], "requirements": len(reqs)}
    return list(reqs.values()), report
