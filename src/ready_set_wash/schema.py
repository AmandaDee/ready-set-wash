from datetime import UTC, datetime
from typing import Any

import strawberry
from strawberry.extensions import MaxAliasesLimiter, MaxTokensLimiter, QueryDepthLimiter
from strawberry.types import Info

from ready_set_wash.domain import DEFAULT_CYCLE_KWH, optimise
from ready_set_wash.providers import PriceProvider, PriceUnavailable


@strawberry.type
class Price:
    start: datetime
    end: datetime
    pence_per_kwh: float


@strawberry.type
class WashPlan:
    start: datetime
    end: datetime
    cost_pence: float
    now_cost_pence: float | None
    savings_pence: float | None


@strawberry.type
class Dashboard:
    mode: str
    prices: list[Price]
    plan: WashPlan


@strawberry.type
class Query:
    @strawberry.field
    async def dashboard(
        self,
        info: Info[dict[str, Any], None],
        deadline: datetime,
        duration_minutes: int = 90,
    ) -> Dashboard:
        provider: PriceProvider = info.context["provider"]
        now: datetime = info.context["now"]
        try:
            rates = await provider.rates(now)
            plan = optimise(rates, now, deadline, duration_minutes, DEFAULT_CYCLE_KWH)
        except (ValueError, PriceUnavailable) as exc:
            raise ValueError(str(exc)) from None
        return Dashboard(
            mode=provider.settings.mode,
            prices=[Price(start=r.start, end=r.end, pence_per_kwh=float(r.pence)) for r in rates],
            plan=WashPlan(
                start=plan.start.astimezone(UTC),
                end=plan.end.astimezone(UTC),
                cost_pence=float(plan.cost),
                now_cost_pence=float(plan.now_cost) if plan.now_cost is not None else None,
                savings_pence=float(plan.now_cost - plan.cost)
                if plan.now_cost is not None
                else None,
            ),
        )


schema = strawberry.Schema(
    query=Query,
    extensions=[
        lambda: QueryDepthLimiter(max_depth=5),
        lambda: MaxAliasesLimiter(max_alias_count=3),
        lambda: MaxTokensLimiter(max_token_count=500),
    ],
)
