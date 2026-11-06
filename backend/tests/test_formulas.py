"""2.2-бөлімдегі формулаларды қолмен есептелген мысалдармен тексеру."""
import math

import pytest

from app.services.gap import Requirement, compute_gap, coverage, priority
from app.services.metrics import kendall_w, mrr, ndcg_at_k, prf, recall_at_k, sus_score
from app.services.recommend import hybrid_scores, smoothed_transition_probs


def test_coverage_formula_2():
    reqs = [Requirement("a", 1.0, 3), Requirement("b", 1.0, 2), Requirement("c", 0.5, 2)]
    # a: min(2/3,1)=0.667, b: min(3/2,1)=1, c: 0 → (0.667 + 1 + 0) / 2.5
    assert coverage({"a": 2, "b": 3}, reqs) == pytest.approx((2 / 3 + 1) / 2.5)
    assert coverage({}, reqs) == 0
    assert coverage({"a": 4, "b": 4, "c": 4}, reqs) == pytest.approx(1.0)


def test_priority_formula_3_and_order():
    assert priority(1.0, 3, 1) == 2
    assert priority(0.5, 2, 3) == 0
    g = compute_gap({"a": 2}, [Requirement("a", 1, 3, "A"), Requirement("b", 0.5, 2, "B"),
                               Requirement("c", 1, 3, "C"), Requirement("d", 1, 3, "D")],
                    importance={"d": 5})
    assert [m.esco_id for m in g.missing] == ["d", "c", "a", "b"]  # p_s: 3,3,1,1; тең кезде маңыздылық/салмақ


def test_smoothing_formula_4():
    p = smoothed_transition_probs({"x": 3, "y": 1}, ["x", "y", "z"], lam=1.0)
    assert p["x"] == pytest.approx(4 / 7)
    assert p["z"] == pytest.approx(1 / 7)
    assert sum(p.values()) == pytest.approx(1.0)


def test_hybrid_formula_5():
    res = hybrid_scores({"x": 0.6, "y": 0.3}, {"x": 0.2, "y": 0.9}, alpha=0.5)
    sx = 0.5 * 1.0 + 0.5 * 0.2   # P̃ = P̂ / max
    sy = 0.5 * 0.5 + 0.5 * 0.9
    by = {r.role: r for r in res}
    assert by["x"].score == pytest.approx(sx)
    assert by["y"].score == pytest.approx(sy)
    assert res[0].role == "y"
    assert hybrid_scores({"x": 0.6, "y": 0.3}, {"x": 0.2, "y": 0.9}, alpha=1.0)[0].role == "x"


def test_prf_formulas_6_8():
    p, r, f = prf(8, 2, 4)
    assert p == pytest.approx(0.8) and r == pytest.approx(8 / 12)
    assert f == pytest.approx(2 * 0.8 * (8 / 12) / (0.8 + 8 / 12))
    assert prf(0, 0, 0) == (0, 0, 0)


def test_ranking_metrics_9_11():
    ranks = [1, 3, None, 12]
    assert recall_at_k(ranks, 5) == pytest.approx(0.5)
    assert mrr(ranks) == pytest.approx((1 + 1 / 3 + 1 / 12) / 4)
    assert ndcg_at_k(ranks, 10) == pytest.approx((1 + 1 / math.log2(4)) / 4)


def test_sus_formula_12():
    assert sus_score([5, 1] * 5) == 100
    assert sus_score([1, 5] * 5) == 0
    assert sus_score([3] * 10) == 50
    with pytest.raises(ValueError):
        sus_score([3] * 9)


def test_kendall_w():
    assert kendall_w([[1, 2, 3], [1, 2, 3], [1, 2, 3]]) == pytest.approx(1.0)
    assert kendall_w([[1, 2, 3], [3, 2, 1]]) == pytest.approx(0.0)
