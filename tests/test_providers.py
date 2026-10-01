import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from ready_set_wash.config import Settings
from ready_set_wash.providers import PriceProvider, PriceUnavailable

NOW = datetime(2026, 10, 1, 9, tzinfo=UTC)
PAYLOAD = {
    "next": None,
    "results": [
        {
            "valid_from": "2026-10-01T09:00:00Z",
            "valid_to": "2026-10-01T09:30:00Z",
            "value_inc_vat": -2.5,
        }
    ],
}


def test_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "READY_SET_WASH_OCTOPUS_API_KEY=supersecret\nREADY_SET_WASH_MODE=demo\n"
    )
    settings = Settings()
    assert settings.octopus_api_key.get_secret_value() == "supersecret"
    assert "supersecret" not in repr(settings)
    with pytest.raises(ValidationError):
        Settings(mode="live")


def test_demo():
    async def run():
        async with httpx.AsyncClient(trust_env=False) as client:
            result = await PriceProvider(Settings(), client).rates(NOW)
            assert len(result) == 96
            assert all(r.end > r.start for r in result)

    asyncio.run(run())


def test_live_request_cache_and_expiry():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "api.octopus.energy"
        assert "authorization" not in request.headers
        return httpx.Response(200, json=PAYLOAD)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = PriceProvider(
                Settings(mode="live", product_code="PRODUCT", tariff_code="TARIFF"), client
            )
            with patch("ready_set_wash.providers.time.monotonic", return_value=100):
                result = await provider.rates(NOW)
                assert (await provider.rates(NOW)) is result
            with patch("ready_set_wash.providers.time.monotonic", return_value=500):
                await provider.rates(NOW)
            assert result[0].pence == -2.5
            assert len(calls) == 2

    asyncio.run(run())


@pytest.mark.parametrize(
    "payload",
    [
        {"results": []},
        {"next": "https://evil.test"},
        {},
        {"results": [{"valid_from": "bad"}]},
        {"results": None},
    ],
)
def test_malformed_upstream(payload):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
        ) as client:
            provider = PriceProvider(
                Settings(mode="live", product_code="P", tariff_code="T"), client
            )
            with pytest.raises(PriceUnavailable, match="unavailable"):
                await provider.rates(NOW)

    asyncio.run(run())


@pytest.mark.parametrize("status", [429, 500, 404, 302])
def test_http_failures(status):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(status))
        ) as client:
            with pytest.raises(PriceUnavailable):
                await PriceProvider(
                    Settings(mode="live", product_code="P", tariff_code="T"), client
                ).rates(NOW)

    asyncio.run(run())


def test_timeout_and_unsafe_code():
    async def run():
        def timeout(request):
            raise httpx.ReadTimeout("secret upstream details")

        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
            with pytest.raises(PriceUnavailable) as error:
                await PriceProvider(
                    Settings(mode="live", product_code="P", tariff_code="T"), client
                ).rates(NOW)
            assert "secret" not in str(error.value)
            with pytest.raises(PriceUnavailable, match="configuration"):
                await PriceProvider(
                    Settings(mode="live", product_code="../evil", tariff_code="T"), client
                ).rates(NOW)

    asyncio.run(run())


def test_open_ended_rate():
    payload = {"results": [{**PAYLOAD["results"][0], "valid_to": None}]}

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
        ) as client:
            result = await PriceProvider(
                Settings(mode="live", product_code="P", tariff_code="T"), client
            ).rates(NOW)
            assert result[0].end > NOW

    asyncio.run(run())


@pytest.mark.parametrize(
    "payload", [[], {"results": [{**PAYLOAD["results"][0], "value_inc_vat": "bad"}]}]
)
def test_invalid_payload_and_decimal(payload):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
        ) as client:
            with pytest.raises(PriceUnavailable):
                await PriceProvider(
                    Settings(mode="live", product_code="P", tariff_code="T"), client
                ).rates(NOW)

    asyncio.run(run())
