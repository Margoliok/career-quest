"""Курстар каталогын тексеру: сілтемелердің қолжетімділігі және ESCO белгілерінің бар-жоғы.

Кіріс: data/courses/catalog_source.csv (';' бөлгіш). Шығыс: data/courses/catalog.csv —
тек тексеруден өткен жазбалар (ішкі курстардың сілтемесі болмайды), verified_at бағанымен.
Іске қосу:  python -m scripts.verify_courses
"""
from __future__ import annotations

import csv
import urllib.request
from datetime import date

from app.config import get_settings
from app.services.roles import skill_id

UA = {"User-Agent": "Mozilla/5.0 (CareerQuest link checker)"}


def check(url: str) -> int:
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main() -> None:
    d = get_settings().data_dir / "courses"
    rows = list(csv.DictReader((d / "catalog_source.csv").open(encoding="utf-8"), delimiter=";"))
    ok_rows = []
    for r in rows:
        labels = [x.strip() for x in r["esco_labels"].split("|") if x.strip()]
        for lab in labels:
            skill_id(lab)  # белгі ESCO-да болмаса — KeyError
        status = check(r["url"]) if r["url"] else 200
        # кейбір сайттар боттарға 403 қайтарады — оларды қолмен тексеру үшін белгілейміз
        r["link_status"] = str(status)
        r["verified_at"] = date.today().isoformat()
        flag = "OK" if status == 200 else ("CHECK" if status in (401, 403, 429) else "FAIL")
        print(f"{flag:5s} {status:3d} {r['provider'][:18]:18s} {r['title'][:50]}")
        if flag != "FAIL":
            ok_rows.append(r)
    with (d / "catalog.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ok_rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(ok_rows)
    print(f"kept {len(ok_rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
