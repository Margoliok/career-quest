"""Диплом суреттері мен нәтижелер файлын жасау (reports/figures, frontend/public/results.json).

5-сурет — ESCO-дағы «data analyst» кәсібі мен дағдылары; 6-сурет — дағдыларды анықтау конвейері;
11-сурет — Э2 F1 (тәсілдер × тілдер); Э4 — α абляциясы; 12-сурет — E-001 үшін ұсынылған мансап жолы.
Тек нақты эксперимент нәтижелері қолданылады (reports/tables).
Іске қосу:  python -m scripts.make_figures
"""
from __future__ import annotations

import json
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from app.config import ROOT, get_settings  # noqa: E402
from app.services import esco_data  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "figure.dpi": 150})
BLUE, AMBER, GREY = "#1d4e89", "#e9a420", "#8fb6e6"


def out(name: str):
    p = get_settings().reports_dir / "figures"
    p.mkdir(parents=True, exist_ok=True)
    return p / name


def fig5_esco_graph() -> None:
    occ = esco_data.occupation_by_label("data analyst")
    rel = esco_data.load_relations()
    rel = rel[rel.occupation_id == occ["esco_id"]]
    labels = dict(zip(esco_data.load_skills().esco_id, esco_data.load_skills().label))
    ess = [labels[x] for x in rel[rel.relation == "essential"].esco_id][:14]
    opt = [labels[x] for x in rel[rel.relation == "optional"].esco_id][:10]
    G = nx.Graph()
    G.add_node("data analyst")
    for s in ess + opt:
        G.add_edge("data analyst", s)
    pos = {"data analyst": (0, 0)}
    import math
    for i, s in enumerate(ess):
        a = 2 * math.pi * i / len(ess)
        pos[s] = (1.5 * math.cos(a), 1.5 * math.sin(a))
    for i, s in enumerate(opt):
        a = 2 * math.pi * (i + 0.5) / len(opt)
        pos[s] = (2.9 * math.cos(a), 2.9 * math.sin(a))
    fig, ax = plt.subplots(figsize=(11, 9))
    nx.draw_networkx_edges(G, pos, edgelist=[("data analyst", s) for s in ess], edge_color=BLUE, width=1.6, ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=[("data analyst", s) for s in opt], edge_color=AMBER, width=1.0,
                           style="dashed", ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=["data analyst"], node_color=BLUE, node_size=2600, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=ess, node_color="#dbe8f7", node_size=300, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=opt, node_color="#fdf1dc", node_size=200, ax=ax)
    nx.draw_networkx_labels(G, pos, labels={"data analyst": "data analyst\n(ESCO 2511.3)"}, font_color="white",
                            font_weight="bold", ax=ax)
    for s in ess + opt:
        x, y = pos[s]
        ax.text(x, y - 0.17, "\n".join(textwrap.wrap(s, 22)), ha="center", va="top", fontsize=7.5)
    ax.plot([], [], color=BLUE, label=f"essential (міндетті): {len(rel[rel.relation == 'essential'])}, суретте 14")
    ax.plot([], [], color=AMBER, ls="--", label=f"optional (қосымша): {len(rel[rel.relation == 'optional'])}, суретте 10")
    ax.legend(loc="lower left")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out("fig05_esco_data_analyst.png"))
    plt.close(fig)


def fig6_pipeline() -> None:
    steps = ["Түйіндеме\n(қаз/орыс/ағылш.)", "PII сүзгісі,\nтілді анықтау", "ҮТМ экстракциясы\nJSON: фраза, дәлел,\nдеңгей 1–4",
             "Көптілді эмбеддинг\n(multilingual-e5)", "ESCO top-20\n(pgvector, cos)", "ҮТМ реранкинг",
             "τ шегі:\nрасталған / расталмаған", "Басшы растауы\n(human-in-the-loop)"]
    fig, ax = plt.subplots(figsize=(13, 2.8))
    for i, s in enumerate(steps):
        x = i * 1.62
        ax.add_patch(FancyBboxPatch((x, 0), 1.35, 1.2, boxstyle="round,pad=0.05", fc="#dbe8f7" if i % 7 else "#fdf1dc",
                                    ec=BLUE, lw=1.2))
        ax.text(x + 0.675, 0.6, s, ha="center", va="center", fontsize=8.3)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + 1.6, 0.6), xytext=(x + 1.4, 0.6), arrowprops=dict(arrowstyle="->", color=BLUE))
    ax.text(0, -0.35, "Офлайн тәсіл: ҮТМ қадамдарының орнына — ұйым каталогы бойынша эмбеддинг (bge-m3) + құралдар глоссарийі",
            fontsize=8.3, color="#5b6678")
    ax.set_xlim(-0.1, len(steps) * 1.62)
    ax.set_ylim(-0.5, 1.4)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out("fig06_extraction_pipeline.png"))
    plt.close(fig)


def fig11_e2() -> list[dict]:
    path = get_settings().reports_dir / "tables" / "e2_local_extraction.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    keep = [m for m in df.method.unique() if not m.startswith("catalog_multilingual-e5")]
    d = df[df.method.isin(keep)]
    piv = d.pivot(index="method", columns="lang", values="F1").reindex(keep)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    piv[["kk", "ru", "all"]].plot.bar(ax=ax, color=[AMBER, GREY, BLUE], width=0.75)
    ax.set_ylabel("F1 (test)")
    ax.set_xlabel("")
    ax.set_ylim(0, 1)
    ax.legend(["қазақ", "орыс", "барлығы"])
    ax.set_xticklabels([textwrap.fill(x, 16) for x in piv.index], rotation=0, fontsize=8)
    for c in ax.containers:
        ax.bar_label(c, fmt="%.2f", fontsize=7)
    ax.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig(out("fig11_e2_f1.png"))
    plt.close(fig)
    return df.to_dict("records")


def fig_e4() -> dict | None:
    path = get_settings().reports_dir / "tables" / "e4_alpha_ablation.json"
    if not path.exists():
        return None
    j = json.loads(path.read_text(encoding="utf-8"))
    g = j["grid"][str(j["lambda_best"])]
    curve = [{"alpha": float(a), **{k: round(v, 4) for k, v in m.items()}} for a, m in g.items()]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    xs = [c["alpha"] for c in curve]
    ax.plot(xs, [c["MRR"] for c in curve], color=BLUE, lw=2, label="MRR")
    ax.plot(xs, [c["Recall@10"] for c in curve], color=AMBER, lw=2, label="Recall@10")
    ax.plot(xs, [c["NDCG@10"] for c in curve], color=GREY, lw=2, label="NDCG@10")
    ax.axvline(j["alpha_best"], ls=":", color="k")
    ax.text(j["alpha_best"], ax.get_ylim()[1] * 0.95, f" α*={j['alpha_best']}", fontsize=9)
    ax.set_xlabel("α (ауысу статистикасының салмағы)")
    ax.set_ylabel(f"validation (n={j['val_cases']})")
    ax.grid(alpha=.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out("fig_e4_alpha.png"))
    plt.close(fig)
    return {**{k: j[k] for k in ("lambda_best", "alpha_best", "val_cases", "test_cases")}, "curve": curve}


def fig12_case() -> None:
    from app.db import SessionLocal
    from app.models import Employee
    from app.services.career import recommendations

    db = SessionLocal()
    try:
        e = db.query(Employee).filter(Employee.code == "E-001").one()
        recs = recommendations(db, e, top=5)
        cur = e.current_role.title_kk
    finally:
        db.close()
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.add_patch(FancyBboxPatch((0, 2.2), 2.6, 1.1, boxstyle="round,pad=0.08", fc=BLUE, ec=BLUE))
    ax.text(1.3, 2.75, "\n".join(textwrap.wrap(cur, 24)), color="white", ha="center", va="center", fontweight="bold")
    mx = max(r["score"] for r in recs)
    for i, r in enumerate(recs):
        y = 4.6 - i * 1.15
        ax.annotate("", xy=(4.6, y + 0.4), xytext=(2.7, 2.75),
                    arrowprops=dict(arrowstyle="->", lw=1 + 4 * r["score"] / mx, color=AMBER if i == 0 else BLUE,
                                    alpha=0.9 if i == 0 else 0.5, connectionstyle="arc3,rad=0.0"))
        ax.add_patch(FancyBboxPatch((4.65, y), 6.9, 0.85, boxstyle="round,pad=0.05",
                                    fc="#fdf1dc" if i == 0 else "#f0f3f8", ec=AMBER if i == 0 else "#dde3ec"))
        miss = ", ".join(m["label"] for m in r["top_missing"][:3])
        ax.text(4.8, y + 0.58, f"{i + 1}. {r['title_kk']}   Score = {r['score']:.2f} "
                               f"(= {r['alpha_part']:.2f} + {r['skill_part']:.2f})", fontsize=9.5, fontweight="bold")
        ax.text(4.8, y + 0.2, f"P̂ = {r['p_transition']:.3f}; C = {r['coverage']:.0%}; жетіспейді: {miss}", fontsize=8.3,
                color="#5b6678")
    ax.set_xlim(-0.2, 11.8)
    ax.set_ylim(-0.4, 5.6)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out("fig12_case_career_path.png"))
    plt.close(fig)


def main() -> None:
    fig5_esco_graph()
    fig6_pipeline()
    e2 = fig11_e2()
    e4 = fig_e4()
    try:
        fig12_case()
    except Exception as exc:  # ДҚ қолжетімсіз болса
        print("fig12 skipped:", exc)
    t = get_settings().reports_dir / "tables"
    res = {"e2": e2, "e4": e4,
           "e3": pd.read_csv(t / "e3_next_role.csv").to_dict("records") if (t / "e3_next_role.csv").exists() else [],
           "e1": pd.read_csv(t / "e1_skillspan.csv").to_dict("records") if (t / "e1_skillspan.csv").exists() else []}
    pub = ROOT / "frontend" / "public" / "results.json"
    pub.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("figures →", out(""), "| results →", pub)


if __name__ == "__main__":
    main()
