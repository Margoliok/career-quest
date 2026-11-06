"""Толтырылған сауалнамаларды есептеу: Э5 сарапшылық бағалау (15-кесте) және SUS (16-кесте, (12) формула).

Кіріс:
  reports/forms/e5_ratings.csv — сарапшылар толтырған (expert;profile;variant;relevance;feasibility;clarity;comment)
  reports/forms/e5_key.json    — A/B кілті
  reports/forms/sus_answers.csv — group;respondent;q1..q10 (1–5)
Шығыс: reports/tables/table15_expert.csv, table16_sus.csv
Іске қосу:  python -m scripts.experiments.score_forms
"""
from __future__ import annotations

import json
import statistics as st

import pandas as pd

from app.services.metrics import kendall_w, sus_score

from .common import reports

CRIT = ["relevance", "feasibility", "clarity"]


def expert() -> None:
    f = reports() / "forms"
    if not (f / "e5_ratings.csv").exists():
        print("e5_ratings.csv not found — skip Table 15")
        return
    key = json.loads((f / "e5_key.json").read_text(encoding="utf-8"))
    df = pd.read_csv(f / "e5_ratings.csv", sep=";")
    df["system"] = [key[p][v] for p, v in zip(df.profile, df.variant)]
    rows = []
    for c in CRIT:
        a = df[df.system == "baseline"][c].astype(float)
        b = df[df.system == "career_quest"][c].astype(float)
        # сарапшылар келісімі: Career Quest жоспарлары бойынша Кендалл W
        piv = df[df.system == "career_quest"].pivot_table(index="expert", columns="profile", values=c)
        w = kendall_w(piv.dropna(axis=1).values.tolist()) if len(piv) > 1 else float("nan")
        rows.append({"criterion": c, "baseline_LLM_no_RAG": round(a.mean(), 2), "career_quest": round(b.mean(), 2),
                     "difference": round(b.mean() - a.mean(), 2), "kendall_W": round(w, 3),
                     "n_ratings": int(len(b))})
    out = pd.DataFrame(rows)
    out.to_csv(reports() / "tables" / "table15_expert.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))


def sus() -> None:
    f = reports() / "forms" / "sus_answers.csv"
    if not f.exists():
        print("sus_answers.csv not found — skip Table 16")
        return
    df = pd.read_csv(f, sep=";")
    df["SUS"] = [sus_score([int(r[f"q{i}"]) for i in range(1, 11)]) for _, r in df.iterrows()]
    rows = [{"group": g, "n": len(x), "SUS_mean": round(x.SUS.mean(), 1),
             "SUS_sd": round(st.stdev(x.SUS), 1) if len(x) > 1 else 0.0} for g, x in df.groupby("group")]
    rows.append({"group": "all", "n": len(df), "SUS_mean": round(df.SUS.mean(), 1),
                 "SUS_sd": round(st.stdev(df.SUS), 1) if len(df) > 1 else 0.0})
    out = pd.DataFrame(rows)
    out.to_csv(reports() / "tables" / "table16_sus.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))


if __name__ == "__main__":
    expert()
    sus()
