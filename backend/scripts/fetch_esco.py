"""ESCO таксономиясын ресми ESCO API арқылы жүктеу (CSV жүктемесінің баламасы).

Ресми CSV (https://esco.ec.europa.eu/en/use-esco/download) e-mail арқылы беріледі.
Егер data/esco/ ішінде ресми CSV файлдары болса, бұл скрипт қажет емес.
Нәтиже ресми жүктемемен бірдей бағандары бар үш файл:
  occupations_en.csv, skills_en.csv, occupationSkillRelations_en.csv

Іске қосу:  python -m scripts.fetch_esco
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

API = "https://ec.europa.eu/esco/api"
OUT = Path(__file__).resolve().parents[2] / "data" / "esco"
BATCH = 10
WORKERS = 3


def get(url: str, tries: int = 5) -> dict:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except Exception as exc:  # сеть / 5xx — қайталаймыз
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
            print(f"  retry {attempt + 1}: {exc}", file=sys.stderr)
    raise RuntimeError("unreachable")


def search_all(kind: str) -> list[str]:
    uris: list[str] = []
    first = get(f"{API}/search?type={kind}&language=en&limit=100&offset=0")
    total = first["total"]
    pages = [first]
    offsets = list(range(1, (total + 99) // 100))  # ESCO API-де offset — бет нөмірі

    def page(off: int) -> dict:
        return get(f"{API}/search?type={kind}&language=en&limit=100&offset={off}")

    with ThreadPoolExecutor(WORKERS) as ex:
        pages += list(ex.map(page, offsets))
    for p in pages:
        uris += [r["uri"] for r in p.get("_embedded", {}).get("results", [])]
    print(f"search {kind}: total={total}, received={len(set(uris))}")
    return list(dict.fromkeys(uris))


def fetch_resources(kind: str, uris: list[str]) -> dict[str, dict]:
    batches = [uris[i:i + BATCH] for i in range(0, len(uris), BATCH)]

    def one(batch: list[str]) -> dict:
        q = "&".join("uris=" + urllib.parse.quote(u, safe=":/") for u in batch)
        return get(f"{API}/resource/{kind}?{q}&language=en").get("_embedded", {})

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(WORKERS) as ex:
        for i, res in enumerate(ex.map(one, batches)):
            out.update(res)
            if i % 40 == 0:
                print(f"  {kind}: {len(out)}/{len(uris)}")
    return out


def en(d: dict | None, key: str = "en"):
    return (d or {}).get(key)


def literal(d: dict | None) -> str:
    v = (d or {}).get("en")
    if isinstance(v, dict):
        return v.get("literal", "")
    return v or ""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    occ_uris = search_all("occupation")
    occs = fetch_resources("occupation", occ_uris)

    relations: list[tuple[str, str, str, str]] = []
    skill_uris: set[str] = set()
    with open(OUT / "occupations_en.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["conceptType", "conceptUri", "iscoGroup", "preferredLabel", "altLabels", "description", "code"])
        for uri, o in occs.items():
            links = o.get("_links", {})
            isco = [x.get("code") or x.get("uri", "").split("/")[-1].replace("C", "")
                    for x in links.get("broaderIscoGroup", [])]
            w.writerow(["Occupation", uri, isco[0] if isco else "", en(o.get("preferredLabel")) or o.get("title"),
                        "\n".join(en(o.get("alternativeLabel")) or []), literal(o.get("description")), o.get("code", "")])
            for rel, key in (("essential", "hasEssentialSkill"), ("optional", "hasOptionalSkill")):
                for s in links.get(key, []):
                    stype = (s.get("skillType") or "").split("/")[-1]
                    relations.append((uri, rel, stype, s["uri"]))
                    skill_uris.add(s["uri"])

    with open(OUT / "occupationSkillRelations_en.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["occupationUri", "relationType", "skillType", "skillUri"])
        w.writerows(relations)
    print(f"relations: {len(relations)}; skills linked to occupations: {len(skill_uris)}")

    skill_uris |= set(search_all("skill"))
    skills = fetch_resources("skill", sorted(skill_uris))
    with open(OUT / "skills_en.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["conceptType", "conceptUri", "skillType", "reuseLevel", "preferredLabel", "altLabels", "description"])
        for uri, s in skills.items():
            links = s.get("_links", {})
            stype = [x.get("uri", "").split("/")[-1] for x in links.get("hasSkillType", [])]
            reuse = [x.get("uri", "").split("/")[-1] for x in links.get("hasReuseLevel", [])]
            w.writerow(["KnowledgeSkillCompetence", uri, stype[0] if stype else "", reuse[0] if reuse else "",
                        en(s.get("preferredLabel")) or s.get("title"),
                        "\n".join(en(s.get("alternativeLabel")) or []), literal(s.get("description"))])

    meta = {"source": "ESCO API (ec.europa.eu/esco/api), default version", "fetched": date.today().isoformat(),
            "occupations": len(occs), "skills": len(skills), "relations": len(relations)}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(meta)


if __name__ == "__main__":
    main()
