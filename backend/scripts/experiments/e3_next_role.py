"""Э3–Э4. Karrierewege деректерінде келесі кәсіпті болжау: Recall@5/10, MRR, NDCG@10 (9)–(11).

Есептің қойылымы: мансап жолындағы қатар келген бірдей кәсіптер біріктіріледі; соңғы (басқа) кәсіп —
болжанатын келесі қадам, алдыңғылары — тарих, соңғы алдыңғы — ағымдағы рөл r.
Тәсілдер:
  popularity    — train жиынындағы ең танымал мақсатты кәсіп (бағыт үшін)
  transitions   — α = 1: тек тегістелген ауысу ықтималдығы P̂(r′|r), (4) («ең жиі ауысу»)
  skills        — α = 0: тек дағдыларды қамту C(e, r′), (2) (e — тарихтағы кәсіптердің ESCO дағдылары)
  hybrid        — (5): α · P̃ + (1 − α) · C, α мен λ validation жиынында таңдалады (Э4 абляциясы)
Іске қосу:  python -m scripts.experiments.e3_next_role [--val-sample 15000]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from scipy import sparse

from app.config import get_settings
from app.services import esco_data

from .common import reports

ALPHAS = [round(a, 2) for a in np.arange(0.0, 1.0001, 0.05)]
LAMBDAS = [0.01, 0.1, 1.0]


def load_split(name: str) -> pd.DataFrame:
    return pd.read_csv(get_settings().cache_dir / f"kw_{name}.csv.gz")


def collapse(df: pd.DataFrame) -> list[list[str]]:
    seqs = []
    for _, g in df.groupby("traj_id", sort=False):
        seq = []
        for o in g.sort_values("order").occupation_id:
            if not seq or seq[-1] != o:
                seq.append(o)
        seqs.append(seq)
    return seqs


class Model:
    def __init__(self, train_seqs: list[list[str]]):
        rel = esco_data.load_relations()
        occ_ids = sorted(set(esco_data.load_occupations().esco_id) | set(rel.occupation_id))
        self.occ = {o: i for i, o in enumerate(occ_ids)}
        skills = sorted(set(rel.esco_id))
        self.sk = {s: i for i, s in enumerate(skills)}
        s = get_settings()
        w = np.where(rel.relation == "essential", s.weight_essential, s.weight_optional)
        rows = rel.occupation_id.map(self.occ).to_numpy()
        cols = rel.esco_id.map(self.sk).to_numpy()
        self.W = sparse.csr_matrix((w, (rows, cols)), shape=(len(self.occ), len(self.sk)))
        self.wsum = np.asarray(self.W.sum(axis=1)).ravel()
        self.wsum[self.wsum == 0] = 1.0
        self.occ_skills = sparse.csr_matrix((np.ones_like(w), (rows, cols)), shape=self.W.shape)
        # n(r → r′): train жиынындағы ауысулар (бірдей кәсіпке «ауысу» есептелмейді)
        fr, to = [], []
        for seq in train_seqs:
            for a, b in zip(seq, seq[1:]):
                if a in self.occ and b in self.occ:
                    fr.append(self.occ[a])
                    to.append(self.occ[b])
        n = len(self.occ)
        self.N = sparse.csr_matrix((np.ones(len(fr)), (fr, to)), shape=(n, n))
        self.n_from = np.asarray(self.N.sum(axis=1)).ravel()
        self.popularity = np.asarray(self.N.sum(axis=0)).ravel()
        self.n_transitions = len(fr)

    def cases(self, seqs: list[list[str]]):
        cur, tgt, hist = [], [], []
        for seq in seqs:
            seq = [o for o in seq if o in self.occ]
            if len(seq) < 2:
                continue
            cur.append(self.occ[seq[-2]])
            tgt.append(self.occ[seq[-1]])
            hist.append([self.occ[o] for o in seq[:-1]])
        return np.array(cur), np.array(tgt), hist

    def coverage(self, hist_batch: list[list[int]]) -> np.ndarray:
        """(2) C(e, r′) барлық кәсіптер үшін; деңгейлер екілік (бар/жоқ), талап деңгейі 1."""
        rows, cols = [], []
        for i, h in enumerate(hist_batch):
            idx = np.unique(self.occ_skills[h].indices)
            rows += [i] * len(idx)
            cols += idx.tolist()
        X = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(hist_batch), len(self.sk)))
        return np.asarray((X @ self.W.T).todense()) / self.wsum[None, :]

    def p_hat(self, cur_batch: np.ndarray, lam: float) -> np.ndarray:
        """(4) P̂(r′|r) = (n(r→r′) + λ) / (n(r) + λ|R|), R — r-ден басқа барлық кәсіптер."""
        n_r = self.n_from[cur_batch][:, None]
        counts = np.asarray(self.N[cur_batch].todense())
        R = len(self.occ) - 1
        return (counts + lam) / (n_r + lam * R)


def ranks_for(scores: np.ndarray, cur: np.ndarray, tgt: np.ndarray, pop: np.ndarray) -> np.ndarray:
    scores = scores.copy()
    scores[np.arange(len(cur)), cur] = -np.inf  # ағымдағы рөл үміткер емес
    st = scores[np.arange(len(tgt)), tgt][:, None]
    pt = pop[tgt][:, None]
    better = (scores > st + 1e-12) | ((np.abs(scores - st) <= 1e-12) & (pop[None, :] > pt))
    return 1 + better.sum(axis=1)


def metrics(r: np.ndarray) -> dict:
    return {"Recall@5": float(np.mean(r <= 5)), "Recall@10": float(np.mean(r <= 10)),
            "MRR": float(np.mean(1.0 / r)),
            "NDCG@10": float(np.mean(np.where(r <= 10, 1.0 / np.log2(r + 1), 0.0)))}


def evaluate(model: Model, cur, tgt, hist, alphas, lam, batch=1500) -> dict[float, np.ndarray]:
    out = {a: [] for a in alphas}
    for s in range(0, len(cur), batch):
        c, t, h = cur[s:s + batch], tgt[s:s + batch], hist[s:s + batch]
        C = model.coverage(h)
        P = model.p_hat(c, lam)
        P[np.arange(len(c)), c] = 0
        Pn = P / P.max(axis=1, keepdims=True)
        for a in alphas:
            out[a].append(ranks_for(a * Pn + (1 - a) * C, c, t, model.popularity))
    return {a: np.concatenate(v) for a, v in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-sample", type=int, default=15000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    print("loading Karrierewege …")
    train = collapse(load_split("train"))
    val = collapse(load_split("validation"))
    test = collapse(load_split("test"))
    model = Model(train)
    vc, vt, vh = model.cases(val)
    if len(vc) > args.val_sample:
        idx = rng.choice(len(vc), args.val_sample, replace=False)
        vc, vt, vh = vc[idx], vt[idx], [vh[i] for i in idx]
    tc, tt, th = model.cases(test)
    print(f"occupations={len(model.occ)} skills={len(model.sk)} train transitions={model.n_transitions} "
          f"val cases={len(vc)} test cases={len(tc)}")

    # Э4: α және λ бойынша абляция (validation)
    grid = {}
    for lam in LAMBDAS:
        res = evaluate(model, vc, vt, vh, ALPHAS, lam)
        grid[lam] = {a: metrics(r) for a, r in res.items()}
        best = max(grid[lam], key=lambda a: grid[lam][a]["MRR"])
        print(f"λ={lam}: best α={best} val MRR={grid[lam][best]['MRR']:.4f} R@10={grid[lam][best]['Recall@10']:.4f}")
    lam_best = max(LAMBDAS, key=lambda l: max(m["MRR"] for m in grid[l].values()))
    a_best = max(grid[lam_best], key=lambda a: grid[lam_best][a]["MRR"])

    res = evaluate(model, tc, tt, th, [1.0, 0.0, a_best], lam_best)
    pop_scores_rank = []
    for s in range(0, len(tc), 5000):
        c, t = tc[s:s + 5000], tt[s:s + 5000]
        sc = np.repeat(model.popularity[None, :].astype(float), len(c), axis=0)
        pop_scores_rank.append(ranks_for(sc, c, t, model.popularity))
    rows = [
        {"method": "popularity (ең танымал кәсіп)", **metrics(np.concatenate(pop_scores_rank))},
        {"method": "transitions only, α=1 (ең жиі ауысу)", **metrics(res[1.0])},
        {"method": "skills only, α=0 (дағдылар ұқсастығы)", **metrics(res[0.0])},
        {"method": f"hybrid, α={a_best}, λ={lam_best}", **metrics(res[a_best])},
    ]
    df = pd.DataFrame(rows)
    out = reports()
    df.round(4).to_csv(out / "tables" / "e3_next_role.csv", index=False, encoding="utf-8-sig")
    (out / "tables" / "e4_alpha_ablation.json").write_text(json.dumps(
        {"lambda_best": lam_best, "alpha_best": a_best, "val_cases": int(len(vc)), "test_cases": int(len(tc)),
         "grid": {str(l): {str(a): m for a, m in g.items()} for l, g in grid.items()}}, indent=1), encoding="utf-8")
    print(df.round(4).to_string(index=False))
    s = get_settings()
    print(f"(config α={s.alpha}, λ={s.smoothing_lambda}; dataset best α={a_best}, λ={lam_best}; "
          f"chance R@10≈{10 / (len(model.occ) - 1):.4f})")


if __name__ == "__main__":
    main()
