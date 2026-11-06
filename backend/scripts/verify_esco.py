"""data/esco/ ішіндегі CSV-ді ресми ESCO API-мен кездейсоқ іріктеме бойынша салыстыру.

Әр таңдалған кәсіп үшін міндетті/қосымша дағдылар жиыны API-дегімен салыстырылады.
Нәтиже data/esco/meta.json файлына жазылады (дипломның 2.1-бөлімі үшін: нұсқа мен тексеру).
Іске қосу:  python -m scripts.verify_esco --n 30
"""
from __future__ import annotations

import argparse
import json
import random
import urllib.parse
import urllib.request
from datetime import date

from app.services import esco_data

API = "https://ec.europa.eu/esco/api"


def api_occupation(uri: str) -> dict:
    url = f"{API}/resource/occupation?uri={urllib.parse.quote(uri, safe=':/')}&language=en&selectedVersion=v1.2.1"
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    occ = esco_data.load_occupations()
    rel = esco_data.load_relations()
    random.seed(args.seed)
    sample = random.sample(list(occ["esco_id"]), args.n)
    must = esco_data.occupation_by_label("data analyst")
    if must and must["esco_id"] not in sample:
        sample[0] = must["esco_id"]
    exact, rows = 0, []
    for uri in sample:
        o = api_occupation(uri)
        links = o.get("_links", {})
        api_ess = {x["uri"] for x in links.get("hasEssentialSkill", [])}
        api_opt = {x["uri"] for x in links.get("hasOptionalSkill", [])}
        r = rel[rel["occupation_id"] == uri]
        csv_ess = set(r[r.relation == "essential"].esco_id)
        csv_opt = set(r[r.relation == "optional"].esco_id)
        jac = len((api_ess | api_opt) & (csv_ess | csv_opt)) / max(len(api_ess | api_opt | csv_ess | csv_opt), 1)
        same = api_ess == csv_ess and api_opt == csv_opt
        exact += same
        label = o.get("preferredLabel", {}).get("en", o.get("title"))
        rows.append({"occupation": label, "api_ess": len(api_ess), "csv_ess": len(csv_ess),
                     "api_opt": len(api_opt), "csv_opt": len(csv_opt), "jaccard": round(jac, 3), "exact": same})
        print(f"{label[:45]:45s} ess {len(api_ess):3d}/{len(csv_ess):3d} opt {len(api_opt):3d}/{len(csv_opt):3d} "
              f"J={jac:.3f} {'OK' if same else 'DIFF'}")
    meta_path = esco_data.esco_dir() / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.update({
        "version": meta.get("version", "ESCO v1.2.1 classification, CSV (en)"),
        "skills": int(len(esco_data.load_skills())), "occupations": int(len(occ)), "relations": int(len(rel)),
        "verification": {"date": date.today().isoformat(), "method": "random sample vs official ESCO API",
                         "n": args.n, "exact_match": exact,
                         "mean_jaccard": round(sum(r["jaccard"] for r in rows) / len(rows), 4), "rows": rows},
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"exact {exact}/{args.n}; mean Jaccard {meta['verification']['mean_jaccard']}")


if __name__ == "__main__":
    main()
