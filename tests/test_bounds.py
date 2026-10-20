import numpy as np
import pytest

from harmfloor import bounds as b


@pytest.mark.parametrize("n,q", [(1, 1), (8, 1), (8, 3), (64, 64), (64, 17)])
def test_selection_weights_are_a_distribution(n, q):
    w = b.selection_weights(n, q)
    assert w.shape == (n,)
    assert w.min() >= 0
    assert w.sum() == pytest.approx(1.0)


def test_selection_weights_edge_cases():
    assert b.selection_weights(10, 1) == pytest.approx(np.full(10, 0.1))
    assert b.selection_weights(10, 10) == pytest.approx(np.eye(10)[0])
    with pytest.raises(ValueError):
        b.selection_weights(4, 5)


def test_best_of_q_matches_monte_carlo():
    rng = np.random.default_rng(1)
    risk, harm = rng.random(16), rng.integers(0, 2, 16)
    qs = [1, 3, 8]
    exact = b.best_of_q_harm(risk, harm, qs)
    for q, e in zip(qs, exact):
        draws = [harm[min(rng.choice(16, q, replace=False), key=lambda i: risk[i])] for _ in range(40_000)]
        assert np.mean(draws) == pytest.approx(e, abs=0.01)


def test_q1_is_the_unfiltered_rate_and_ties_are_averaged():
    harm = np.array([1, 0, 1, 0])
    assert b.best_of_q_harm(np.random.rand(4), harm, [1])[0] == pytest.approx(0.5)
    # all risks tied: the filter cannot separate, so every budget returns the base rate
    assert b.best_of_q_harm(np.zeros(4), harm, [1, 2, 4]) == pytest.approx([0.5, 0.5, 0.5])


def test_tau_turns_high_risk_selections_into_refusals():
    risk, harm = np.array([0.9, 0.95]), np.array([1, 1])
    assert b.best_of_q_harm(risk, harm, [2], tau=0.5)[0] == 0
    assert b.best_of_q_refusal(risk, [2], tau=0.5)[0] == 1
    benign = [np.array([0.1, 0.2]), np.array([0.6, 0.7])]
    tau = b.calibrate_tau(benign, q=2, max_fpr=0.5)
    assert np.mean([b.best_of_q_refusal(r, [2], tau)[0] for r in benign]) <= 0.5


def test_blind_spot_gives_a_positive_floor():
    """A harmful sample the guard ranks safest is what best-of-q converges to."""
    risk = np.array([0.0, *np.linspace(0.5, 1.0, 31)])
    harm = np.array([1, *([0] * 15 + [1] * 16)])
    curve = b.best_of_q_harm(risk, harm, [1, 32])
    assert curve[0] == pytest.approx(17 / 32)
    assert curve[1] == pytest.approx(1.0)  # q = n always returns the min-risk sample


def test_fit_recovers_parameters_and_detects_no_floor():
    qs = np.array([1, 2, 4, 8, 16, 32, 64])
    fit = b.fit_floor(qs, b.floor_model(qs, 0.08, 0.3, 0.7))
    assert (fit.L, fit.A, fit.alpha) == pytest.approx((0.08, 0.3, 0.7), abs=1e-3)
    assert fit.sse_zero_floor > 100 * max(fit.sse, 1e-12)
    no_floor = b.fit_floor(qs, b.floor_model(qs, 0.0, 0.4, 0.8))
    assert no_floor.L == pytest.approx(0.0, abs=1e-3)


def test_judge_correction():
    # judge with 10% false positives sees 0.10 on a truly harmless set
    assert b.correct_for_judge_error(0.10, sensitivity=0.9, specificity=0.9) == pytest.approx(0.0)
    assert b.correct_for_judge_error(0.5, 1.0, 1.0) == pytest.approx(0.5)
    assert b.judge_accuracy([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx((1.0, 2 / 3))


def _synthetic_cell(n_prompts=120, n=64, floor_share=0.25, seed=0):
    """Prompts where a fraction carry a harmful completion the guard scores as safest."""
    rng = np.random.default_rng(seed)
    pools = []
    for i in range(n_prompts):
        risk = rng.random(n)
        harm = (rng.random(n) < 0.4).astype(int)
        risk[harm == 1] += 0.5  # the guard mostly separates harmful samples ...
        if i < floor_share * n_prompts:  # ... except on blind-spot prompts
            j = rng.choice(np.flatnonzero(harm)) if harm.any() else 0
            harm[j], risk[j] = 1, -1.0
        pools.append((risk, harm))
    return pools


def test_estimate_bounds_end_to_end():
    qs = [1, 2, 4, 8, 16, 32, 64]
    ceilings, curves = b.pool_curves(_synthetic_cell(), qs)
    est = b.estimate_bounds(ceilings, curves, qs, n_boot=200)
    assert est.ceiling == pytest.approx(ceilings.mean())
    assert est.rho[-1] == pytest.approx(0.25, abs=0.02)  # q = n hits exactly the blind-spot share
    assert est.floor_is_positive
    assert est.floor_ci[0] <= est.floor <= est.floor_ci[1]

    clean = b.pool_curves(_synthetic_cell(floor_share=0.0), qs)
    est0 = b.estimate_bounds(*clean, qs, n_boot=200)
    assert est0.rho[-1] < 0.01
    assert not est0.floor_is_positive


def test_estimate_bounds_with_judge_validation_and_clusters():
    qs = [1, 4, 16, 64]
    ceilings, curves = b.pool_curves(_synthetic_cell(), qs)
    clusters = [f"intent-{i // 2}" for i in range(len(ceilings))]
    judge, human = [1] * 45 + [0] * 50 + [1] * 5, [1] * 50 + [0] * 50
    est = b.estimate_bounds(ceilings, curves, qs, clusters=clusters, judge_validation=(judge, human), n_boot=100)
    assert est.ceiling_ci[0] <= est.ceiling <= est.ceiling_ci[1]


def test_extrapolation_check():
    qs = np.array([1, 2, 4, 8, 16, 32, 64, 128, 256])
    out = b.extrapolation_check(qs, b.floor_model(qs, 0.05, 0.3, 0.6), q_fit_max=64)
    assert out["predicted"] == pytest.approx(out["observed"], abs=1e-3)


def test_decomposition_adds_up():
    d = b.BoundDecomposition(ceiling=0.52, observed=0.22, floor=0.15)
    assert d.removed + d.reducible + d.irreducible == pytest.approx(d.ceiling)
    assert d.position == pytest.approx(0.07 / 0.37)
    assert b.BoundDecomposition(0.2, 0.3, 0.1).removed < 0  # defense made it worse: kept signed


def test_boundary_floor_is_not_called_positive():
    """Regression: L lands at ~1e-9, not 0, on the boundary; that must not count as a floor."""
    rng = np.random.default_rng(3)
    qs = np.array([1, 4, 16, 64])
    rho = b.floor_model(qs, 0.0, 0.3, 0.4) + rng.normal(0, 0.01, 4)
    Ls = [b.fit_floor(qs, np.clip(rho + rng.normal(0, 0.03, 4), 0, 1)).L for _ in range(200)]
    assert np.mean(np.asarray(Ls) < b.ZERO_TOL) > 0.2
    est = b.BoundEstimate(0.5, (0.4, 0.6), rho, b.fit_floor(qs, rho), (1e-9, 0.1), (0.05, 0.1), 0.4)
    assert not est.floor_is_positive
