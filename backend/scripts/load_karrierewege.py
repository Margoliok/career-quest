"""Karrierewege деректерін дайындау: мансап жолдары → ESCO кәсіптерінің тізбегі.

Кіріс: HuggingFace ElenaSenger/Karrierewege архивтері (train/validation/test), KW_DIR қалтасында.
Шығыс (data/processed/):
  kw_<split>.csv.gz — traj_id, order, occupation_id (ESCO URI);
  kw_meta.json      — көлемі, ESCO-мен сәйкестендіру үлесі.
Іске қосу:  python -m scripts.load_karrierewege --kw-dir C:/Users/<user>/career-quest-cache/karrierewege
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.services import esco_data

HF = "https://huggingface.co/datasets/ElenaSenger/Karrierewege/resolve/main/"
FILES = {"train": "karierrewege_train.zip", "validation": "karierrewege_validation.zip",
         "test": "karierrewege_test.zip"}


def ensure(kw_dir: Path, name: str) -> Path:
    path = kw_dir / name
    if not path.exists():
        kw_dir.mkdir(parents=True, exist_ok=True)
        print("downloading", name)
        urllib.request.urlretrieve(HF + name, path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kw-dir", default=os.environ.get("KW_DIR", str(get_settings().data_dir / "karrierewege")))
    args = ap.parse_args()
    kw_dir = Path(args.kw_dir)
    out_dir = get_settings().cache_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    occ = esco_data.load_occupations()
    by_label: dict[str, str] = {}
    for r in occ.itertuples():
        by_label.setdefault(r.label.lower(), r.esco_id)
        for a in r.alt_labels:
            by_label.setdefault(a.lower(), r.esco_id)

    meta = {"source": "ElenaSenger/Karrierewege (HuggingFace)", "splits": {}}
    for split, fname in FILES.items():
        z = zipfile.ZipFile(ensure(kw_dir, fname))
        df = pd.read_csv(z.open(z.namelist()[0]), usecols=["_id", "experience_order", "preferredLabel_en"])
        df["occupation_id"] = df["preferredLabel_en"].str.lower().map(by_label)
        matched = df["occupation_id"].notna().mean()
        unmatched = df.loc[df.occupation_id.isna(), "preferredLabel_en"].value_counts().head(10).to_dict()
        df = df.dropna(subset=["occupation_id"]).rename(columns={"_id": "traj_id", "experience_order": "order"})
        df = df.sort_values(["traj_id", "order"])[["traj_id", "order", "occupation_id"]]
        df.to_csv(out_dir / f"kw_{split}.csv.gz", index=False)
        meta["splits"][split] = {"rows": int(len(df)), "trajectories": int(df.traj_id.nunique()),
                                 "occupations": int(df.occupation_id.nunique()),
                                 "label_match_rate": round(float(matched), 5), "top_unmatched": unmatched}
        print(split, meta["splits"][split])
    (out_dir / "kw_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
