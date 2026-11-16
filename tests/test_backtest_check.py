"""Tests for the pre-registered Stage 4 backtest accounting."""
import numpy as np
import pytest

from src.backtest_check import (
    block_bootstrap_mean_diff,
    delay_positions,
    equity_curve,
    positions_from_threshold,
    strategy_metrics,
)


def test_cost_charged_exactly_on_each_position_change():
    # flat -> long -> flat -> long: three changes, each charged 1%.
    eq, net = equity_curve([1, 0, 1], [0.0, 0.0, 0.0], cost=0.01)
    assert eq[-1] == pytest.approx(0.99 ** 3)
    assert np.allclose(net, -0.01)
    assert eq[0] == 1.0


def test_cost_is_charged_before_the_day_return():
    # Enter at the close, pay 1%, then earn 10%; exit next close, pay 1%.
    eq, _ = equity_curve([1, 0], [0.10, 0.0], cost=0.01)
    assert eq[-1] == pytest.approx(1.10 * 0.99 * 0.99)


def test_flat_to_flat_charges_nothing():
    eq, net = equity_curve([0, 0, 0], [0.5, -0.5, 0.2], cost=0.01)
    assert np.allclose(eq, 1.0)
    assert np.allclose(net, 0.0)


def test_one_entry_charges_once():
    eq, _ = equity_curve([1, 1, 1], [0.0, 0.0, 0.0], cost=0.02)
    assert eq[-1] == pytest.approx(0.98)


def test_position_at_t_uses_only_prediction_at_t():
    pred = np.array([1.0, 2.0, 3.0, 4.0])
    p = positions_from_threshold(pred, 2.5)
    assert np.array_equal(p, [0, 0, 1, 1])
    # A future prediction cannot change an earlier position.
    changed = pred.copy()
    changed[2:] = -100.0
    p2 = positions_from_threshold(changed, 2.5)
    assert np.array_equal(p2[:2], p[:2])
    assert np.array_equal(p2, [0, 0, 0, 0])


def test_s0_equity_is_compounded_product_of_daily_returns():
    r = np.array([0.01, -0.02, 0.03, 0.0])
    eq, _ = equity_curve(np.ones(len(r)), r, cost=0.0)
    assert np.allclose(eq[1:], np.cumprod(1.0 + r))
    assert eq[-1] == pytest.approx(np.prod(1.0 + r))


def test_delay_shifts_position_by_exactly_one_day():
    p = np.array([1.0, 0.0, 1.0, 1.0, 0.0])
    assert np.array_equal(delay_positions(p, 1), [0.0, 1.0, 0.0, 1.0, 1.0])
    assert np.array_equal(delay_positions(p, 2), [0.0, 0.0, 1.0, 0.0, 1.0])
    assert np.array_equal(delay_positions(np.zeros(4), 1), np.zeros(4))


def test_metrics_count_entry_and_share_long():
    r = np.zeros(3)
    p = np.array([1.0, 1.0, 0.0])
    eq, net = equity_curve(p, r, cost=0.0)
    m = strategy_metrics(p, eq, net)
    assert m["position_changes"] == 2
    assert m["share_long"] == pytest.approx(2.0 / 3.0)
    assert m["equity_multiple"] == pytest.approx(1.0)
    assert m["max_drawdown"] == pytest.approx(0.0)


def test_bootstrap_ci_is_ordered_and_detects_positive_mean():
    d = np.full(210, 0.001)
    out = block_bootstrap_mean_diff(d)
    assert out["ci_low"] <= out["mean_diff"] <= out["ci_high"]
    assert out["ci_low"] > 0
