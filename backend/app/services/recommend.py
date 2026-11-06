"""Келесі рөлді гибридті ұсыну: тегістелген ауысу ықтималдығы (4) және гибридті балл (5)."""
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass


def smoothed_transition_probs(counts: Mapping[Hashable, float], candidates: Iterable[Hashable],
                              lam: float = 1.0) -> dict[Hashable, float]:
    """(4) P̂(r′ | r) = (n(r → r′) + λ) / (n(r) + λ·|R|).

    counts — ағымдағы r рөлінен шыққан ауысулар саны {r′: n(r → r′)};
    candidates — R жиыны (мақсатты рөлдер, r-дің өзінсіз).
    """
    cands = list(candidates)
    if not cands:
        return {}
    n_r = sum(counts.get(c, 0.0) for c in cands)
    denom = n_r + lam * len(cands)
    if denom <= 0:
        return {c: 1.0 / len(cands) for c in cands}
    return {c: (counts.get(c, 0.0) + lam) / denom for c in cands}


@dataclass
class RoleScore:
    role: Hashable
    score: float
    p_transition: float      # P̂(r′|r)
    p_normalized: float      # max бойынша нормаланған P̂ (α компонентіне кіреді)
    coverage: float          # C(e, r′)
    alpha_part: float        # α · P̃
    skill_part: float        # (1 − α) · C


def hybrid_scores(p_hat: Mapping[Hashable, float], cov: Mapping[Hashable, float], alpha: float,
                  normalize: bool = True, tie_break: Mapping[Hashable, float] | None = None) -> list[RoleScore]:
    """(5) Score(r′ | e, r) = α · P̂(r′ | r) + (1 − α) · C(e, r′).

    normalize=True: P̂ ең үлкен мәнге бөлінеді, сонда екі компонент те [0; 1] аралығында болады
    және α коэффициентін түсіндіру оңай (кандидаттар көп болғанда P̂ өте кіші болады).
    """
    roles = list(cov.keys() | p_hat.keys())
    pmax = max((p_hat.get(r, 0.0) for r in roles), default=0.0) or 1.0
    out: list[RoleScore] = []
    for r in roles:
        p = p_hat.get(r, 0.0)
        pn = p / pmax if normalize else p
        c = cov.get(r, 0.0)
        a, s = alpha * pn, (1 - alpha) * c
        out.append(RoleScore(r, a + s, p, pn, c, a, s))
    tb = tie_break or {}
    out.sort(key=lambda x: (-x.score, -tb.get(x.role, 0.0), str(x.role)))
    return out
