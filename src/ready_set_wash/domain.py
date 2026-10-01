from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

DEFAULT_CYCLE_KWH = Decimal("0.8")


@dataclass(frozen=True)
class Rate:
    start: datetime
    end: datetime
    pence: Decimal

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Rates must have timezone-aware timestamps")
        if self.end <= self.start or not self.pence.is_finite():
            raise ValueError("Invalid rate interval")


@dataclass(frozen=True)
class Plan:
    start: datetime
    end: datetime
    cost: Decimal
    now_cost: Decimal | None


def cost_at(rates: list[Rate], start: datetime, minutes: int, kwh: Decimal) -> Decimal:
    """Integrate a constant-power cycle over contiguous rates; never bridge a gap."""
    end = start + timedelta(minutes=minutes)
    cursor = start
    total = Decimal(0)
    for rate in rates:
        left, right = max(cursor, rate.start), min(end, rate.end)
        if right <= left:
            continue
        if left > cursor:
            raise ValueError("Price data is incomplete for this window")
        fraction = Decimal(str((right - left).total_seconds())) / Decimal(minutes * 60)
        total += rate.pence * kwh * fraction
        cursor = right
        if cursor == end:
            return total
    raise ValueError("Price data is incomplete for this window")


def optimise(
    rates: list[Rate], now: datetime, deadline: datetime, minutes: int, kwh: Decimal
) -> Plan:
    if now.tzinfo is None or deadline.tzinfo is None:
        raise ValueError("Use timezone-aware timestamps")
    now, deadline = now.astimezone(UTC), deadline.astimezone(UTC)
    if not 15 <= minutes <= 240 or not kwh.is_finite() or not Decimal("0.05") <= kwh <= 10:
        raise ValueError("Duration must be 15–240 minutes and energy 0.05–10 kWh")
    if deadline <= now or deadline - now > timedelta(hours=48):
        raise ValueError("Deadline must be in the next 48 hours")
    rates = sorted(rates, key=lambda r: r.start)
    if any(a.end > b.start for a, b in zip(rates, rates[1:], strict=False)):
        raise ValueError("Overlapping price intervals")
    duration = timedelta(minutes=minutes)
    # The optimum of a piecewise linear cost occurs at a tariff boundary at
    # either end of the cycle, or at a constraint boundary.
    candidates = {now, deadline - duration}
    for rate in rates:
        candidates.update((rate.start, rate.start - duration, rate.end - duration))
    choices: list[tuple[Decimal, datetime]] = []
    for start in sorted(candidates):
        if start < now or start + duration > deadline:
            continue
        try:
            choices.append((cost_at(rates, start, minutes, kwh), start))
        except ValueError:
            continue
    if not choices:
        raise ValueError("No complete price window fits. Try an earlier deadline or shorter cycle.")
    cost, start = min(choices)
    try:
        now_cost = cost_at(rates, now, minutes, kwh)
    except ValueError:
        now_cost = None
    return Plan(
        start,
        start + duration,
        cost.quantize(Decimal("0.01")),
        now_cost.quantize(Decimal("0.01")) if now_cost is not None else None,
    )
