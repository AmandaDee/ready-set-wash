from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ready_set_wash.domain import Rate, cost_at, optimise

NOW = datetime(2026, 10, 1, 9, tzinfo=UTC)


def rates(values):
    return [
        Rate(NOW + timedelta(minutes=30 * i), NOW + timedelta(minutes=30 * (i + 1)), Decimal(v))
        for i, v in enumerate(values)
    ]


def test_cheapest_window_and_comparison():
    plan = optimise(
        rates([30, 30, 10, 10, 10, 40]), NOW, NOW + timedelta(hours=3), 90, Decimal(".8")
    )
    assert plan.start == NOW + timedelta(hours=1)
    assert plan.cost == Decimal("8")
    assert plan.now_cost == Decimal("18.67")


def test_partial_intervals_and_negative_prices():
    assert cost_at(rates([30, -10]), NOW + timedelta(minutes=15), 30, Decimal("1")) == 10
    plan = optimise(rates([30, -10, -10, 20]), NOW, NOW + timedelta(hours=2), 45, Decimal("1"))
    assert plan.cost == -10
    assert plan.start == NOW + timedelta(minutes=30)


def test_finish_boundary_can_be_optimal():
    plan = optimise(rates([30, 20, 10]), NOW, NOW + timedelta(minutes=80), 45, Decimal("1"))
    assert plan.end == NOW + timedelta(minutes=80)


def test_ties_choose_earliest_and_unsorted_rates():
    plan = optimise(
        list(reversed(rates([10] * 4))), NOW, NOW + timedelta(hours=2), 30, Decimal("1")
    )
    assert plan.start == NOW


def test_gap_never_fabricates_prices():
    data = rates([20, 20, 10, 10])[1:]
    plan = optimise(data, NOW, NOW + timedelta(hours=2), 30, Decimal("1"))
    assert plan.now_cost is None
    with pytest.raises(ValueError, match="incomplete"):
        cost_at([data[0], data[2]], NOW + timedelta(minutes=30), 90, Decimal("1"))


@pytest.mark.parametrize(
    "minutes,kwh", [(14, "1"), (241, "1"), (90, "0"), (90, "11"), (90, "NaN"), (90, "Infinity")]
)
def test_invalid_cycle(minutes, kwh):
    with pytest.raises(ValueError, match="Duration"):
        optimise(rates([10] * 4), NOW, NOW + timedelta(hours=2), minutes, Decimal(kwh))


@pytest.mark.parametrize("deadline", [NOW, NOW - timedelta(seconds=1), NOW + timedelta(hours=49)])
def test_invalid_deadline(deadline):
    with pytest.raises(ValueError, match="Deadline"):
        optimise(rates([10] * 4), NOW, deadline, 30, Decimal("1"))


def test_no_window_and_overlaps_and_naive_dates():
    with pytest.raises(ValueError, match="No complete"):
        optimise(rates([10]), NOW, NOW + timedelta(hours=2), 90, Decimal("1"))
    with pytest.raises(ValueError, match="Overlapping"):
        optimise(rates([10]) * 2, NOW, NOW + timedelta(hours=2), 30, Decimal("1"))
    with pytest.raises(ValueError, match="timezone"):
        optimise([], NOW.replace(tzinfo=None), NOW, 30, Decimal("1"))
    with pytest.raises(ValueError, match="timezone"):
        Rate(NOW.replace(tzinfo=None), NOW, Decimal(10))
    with pytest.raises(ValueError, match="Invalid"):
        Rate(NOW, NOW, Decimal(10))
    with pytest.raises(ValueError, match="Invalid"):
        Rate(NOW, NOW + timedelta(minutes=30), Decimal("NaN"))


def test_dst_uses_elapsed_time():
    london = ZoneInfo("Europe/London")
    start = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    data = [Rate(start, start + timedelta(hours=4), Decimal(10))]
    plan = optimise(
        data,
        start.astimezone(london),
        (start + timedelta(hours=3)).astimezone(london),
        90,
        Decimal(1),
    )
    assert plan.end - plan.start == timedelta(minutes=90)


def test_against_brute_force_minute_reference():
    data = rates([25, -5, 17, 12, 37, 8, 2, 18])
    for minutes in [15, 45, 75, 120]:
        plan = optimise(
            data, NOW + timedelta(minutes=7), NOW + timedelta(minutes=233), minutes, Decimal(".8")
        )
        expected = min(
            cost_at(data, NOW + timedelta(minutes=i), minutes, Decimal(".8"))
            for i in range(7, 234 - minutes)
        )
        assert plan.cost == expected.quantize(Decimal("0.01"))
