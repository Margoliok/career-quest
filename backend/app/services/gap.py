"""Дағдылар алшақтығы: рөлді қамту көрсеткіші (2) және жетіспейтін дағдының басымдығы (3)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Requirement:
    esco_id: str
    weight: float          # w_s: міндетті = 1, қосымша = 0,5 немесе сарапшы бекіткен
    required_level: int    # l_{r,s}
    label: str = ""
    relation: str = "essential"


@dataclass
class GapItem:
    esco_id: str
    label: str
    weight: float
    required_level: int
    employee_level: int
    priority: float        # p_s
    relation: str


@dataclass
class GapResult:
    coverage: float                      # C(e, r) ∈ [0; 1]
    matched: list[GapItem] = field(default_factory=list)
    missing: list[GapItem] = field(default_factory=list)  # p_s бойынша кему ретімен
    total_weight: float = 0.0


def coverage(employee_levels: dict[str, int], requirements: list[Requirement]) -> float:
    """(2) C(e, r) = Σ w_s · min(l_{e,s} / l_{r,s}, 1) / Σ w_s."""
    total = sum(r.weight for r in requirements)
    if total <= 0:
        return 0.0
    acc = 0.0
    for r in requirements:
        le = employee_levels.get(r.esco_id, 0)
        acc += r.weight * min(le / max(r.required_level, 1), 1.0)
    return acc / total


def priority(weight: float, required_level: int, employee_level: int) -> float:
    """(3) p_s = w_s · max(l_{r,s} − l_{e,s}, 0)."""
    return weight * max(required_level - employee_level, 0)


def compute_gap(employee_levels: dict[str, int], requirements: list[Requirement],
                importance: dict[str, float] | None = None) -> GapResult:
    """importance — тең p_s кезіндегі қосымша рет: дағдыны талап ететін ұйым рөлдерінің саны
    (іргелі дағдылар бірінші). (2)–(3) формулаларының мәніне әсер етпейді."""
    res = GapResult(coverage=coverage(employee_levels, requirements),
                    total_weight=sum(r.weight for r in requirements))
    for r in requirements:
        le = employee_levels.get(r.esco_id, 0)
        item = GapItem(r.esco_id, r.label, r.weight, r.required_level, le,
                       priority(r.weight, r.required_level, le), r.relation)
        (res.missing if item.priority > 0 else res.matched).append(item)
    imp = importance or {}
    res.missing.sort(key=lambda x: (-x.priority, -x.weight, -imp.get(x.esco_id, 0.0), x.label))
    return res
