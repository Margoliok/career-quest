"""Бағалау метрикалары: (6)–(8) P, R, F1; (9)–(11) Recall@k, MRR, NDCG@k; (12) SUS; Kendall W."""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0          # (6)
    r = tp / (tp + fn) if tp + fn else 0.0          # (7)
    f1 = 2 * p * r / (p + r) if p + r else 0.0      # (8)
    return p, r, f1


def set_prf(pred: Iterable, gold: Iterable) -> tuple[int, int, int]:
    pred, gold = set(pred), set(gold)
    return len(pred & gold), len(pred - gold), len(gold - pred)


def rank_of(ranked: Sequence, target) -> int | None:
    """1-ден басталатын орын; табылмаса None."""
    try:
        return list(ranked).index(target) + 1
    except ValueError:
        return None


def recall_at_k(ranks: Sequence[int | None], k: int) -> float:
    """(9) Recall@k = |{u : r*_u ∈ top-k(u)}| / |U|."""
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks) if ranks else 0.0


def mrr(ranks: Sequence[int | None]) -> float:
    """(10) MRR = (1/|U|) Σ 1/rank_u (табылмаса 0)."""
    return sum(1.0 / r for r in ranks if r) / len(ranks) if ranks else 0.0


def ndcg_at_k(ranks: Sequence[int | None], k: int) -> float:
    """(11) NDCG@k, бір дұрыс жауап: DCG = 1/log2(rank+1), IDCG = 1."""
    if not ranks:
        return 0.0
    return sum(1.0 / math.log2(r + 1) for r in ranks if r is not None and r <= k) / len(ranks)


def sus_score(answers: Sequence[int]) -> float:
    """(12) SUS = 2,5 · [Σ_{тақ i}(x_i − 1) + Σ_{жұп i}(5 − x_i)], i = 1…10, x_i ∈ {1..5}."""
    if len(answers) != 10 or any(not 1 <= a <= 5 for a in answers):
        raise ValueError("SUS: 10 жауап қажет, әрқайсысы 1..5")
    odd = sum(answers[i] - 1 for i in range(0, 10, 2))
    even = sum(5 - answers[i] for i in range(1, 10, 2))
    return 2.5 * (odd + even)


def kendall_w(ratings: Sequence[Sequence[float]]) -> float:
    """Кендаллдың сәйкестік коэффициенті W (m сарапшы × n нысан), байланысқан рангтерге түзетумен."""
    m = len(ratings)
    n = len(ratings[0]) if m else 0
    if m < 2 or n < 2:
        return float("nan")
    rank_rows, ties = [], 0.0
    for row in ratings:
        order = sorted(range(n), key=lambda i: row[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and row[order[j + 1]] == row[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for t in range(i, j + 1):
                ranks[order[t]] = avg
            size = j - i + 1
            ties += size ** 3 - size
            i = j + 1
        rank_rows.append(ranks)
    sums = [sum(r[i] for r in rank_rows) for i in range(n)]
    mean = sum(sums) / n
    s = sum((x - mean) ** 2 for x in sums)
    denom = m ** 2 * (n ** 3 - n) - m * ties
    return 12 * s / denom if denom else float("nan")
