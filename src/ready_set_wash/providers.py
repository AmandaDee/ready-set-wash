import asyncio
import math
import re
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx

from ready_set_wash.config import Settings
from ready_set_wash.domain import Rate


class PriceUnavailable(Exception):
    """An upstream failure safe to report without exposing credentials."""


class PriceProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client
        self._cache: tuple[float, list[Rate]] | None = None
        self._lock = asyncio.Lock()

    async def rates(self, now: datetime) -> list[Rate]:
        if self.settings.mode == "demo":
            base = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
            return [
                Rate(
                    base + timedelta(minutes=30 * i),
                    base + timedelta(minutes=30 * (i + 1)),
                    Decimal(str(round(22 + 14 * math.cos((i - 3) / 5), 2))),
                )
                for i in range(96)
            ]
        async with self._lock:
            if self._cache and time.monotonic() - self._cache[0] < 300:
                return self._cache[1]
            codes = (self.settings.product_code, self.settings.tariff_code)
            if not all(re.fullmatch(r"[A-Za-z0-9-]{1,100}", code) for code in codes):
                raise PriceUnavailable("Invalid tariff configuration")
            url = (
                "https://api.octopus.energy/v1/products/"
                f"{codes[0]}/electricity-tariffs/{codes[1]}/standard-unit-rates/"
            )
            try:
                response = await self.client.get(
                    url,
                    params={
                        "period_from": now.isoformat(),
                        "period_to": (now + timedelta(hours=48)).isoformat(),
                        "page_size": 200,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Invalid price payload")
                if payload.get("next"):
                    raise ValueError("Unexpected pagination")
                rates = [
                    Rate(
                        datetime.fromisoformat(item["valid_from"]),
                        datetime.fromisoformat(item["valid_to"])
                        if item["valid_to"] is not None
                        else now + timedelta(hours=48),
                        Decimal(str(item["value_inc_vat"])),
                    )
                    for item in payload["results"]
                ]
                if not rates:
                    raise ValueError("Empty prices")
            except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
                raise PriceUnavailable(
                    "Octopus prices unavailable. Please try again later."
                ) from exc
            self._cache = (time.monotonic(), rates)
            return rates
