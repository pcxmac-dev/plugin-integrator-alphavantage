"""What Alpha Vantage's plugin attaches to (plugin API 2.2, apis.py): a sound card, its functions the ones the plugin
really calls (a recording session answers every request; nothing is sent), and nothing asked to say what it learned
(api_facts). With LIMINAL_VENDOR_PAGES=1, every address on the card is asked once: the one test here that sends
anything (the plugins' page check)."""
from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlparse

import pytest

from liminal_libs.sources import registry
from liminal_libs.sources.apis import dead_links, problems, urls
import plugin_integrator_alphavantage as av
from plugin_integrator_alphavantage.apis import ALPHA_VANTAGE, APIS, KEY_PAGE, QUERY
from plugin_integrator_alphavantage.client import API, SERIES, AlphaVantageClient, AlphaVantageSource

from .conftest import FakeResponse

DAY = date(2026, 11, 10)


class Recording:
    """Answers every request (an empty daily series, a search without matches) and records it with its parameters."""

    def __init__(self):
        self.asked: list[tuple[str, str, dict]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.asked.append(("GET", url, dict(params or {})))
        body = {"Meta Data": {}, SERIES: {}} if (params or {}).get("function") == "TIME_SERIES_DAILY" else {"bestMatches": []}
        return FakeResponse(200, body)


def test_its_card_names_every_function_it_calls_and_none_it_does_not():
    session = Recording()
    source = AlphaVantageSource(AlphaVantageClient("KEY", session=session, sleep=lambda s: None), has_key=True)
    next(source.bar_pages("VOD.L", DAY, DAY, "day"))  # the daily series (compact)
    source.instrument("VOD.L")  # the search: with its suffix, then by its bare code
    assert {u for _, u, _ in session.asked} == {QUERY} == {f"{API}/query"}  # its one address, the card's base
    assert all(p.get("apikey") == "KEY" for _, _, p in session.asked)  # the key as the query parameter, its only form
    made = {f"{m} {urlparse(u).path}?function={p['function']}" for m, u, p in session.asked}
    names = {c.name for c in ALPHA_VANTAGE.calls}
    assert made <= names  # every function it called is a call on the card
    assert made == {c.name for c in ALPHA_VANTAGE.used}  # and every one the card says it calls, it calls
    assert {p["outputsize"] for _, _, p in session.asked if p["function"] == "TIME_SERIES_DAILY"} == {"compact"}


def test_a_sound_card():
    assert APIS == (ALPHA_VANTAGE,) and av.PLUGIN.apis is APIS and problems(APIS, today=DAY) == []
    assert ALPHA_VANTAGE.docs == "https://www.alphavantage.co/documentation/" and ALPHA_VANTAGE.kind == "query"
    assert av.PLUGIN.signup == KEY_PAGE == ALPHA_VANTAGE.link("console")  # where the free key is claimed
    assert {"docs", "limits", "pricing", "console", "terms"} <= {x.kind for x in ALPHA_VANTAGE.links}
    parts = {a.name for a in ALPHA_VANTAGE.areas}
    assert {"Core stock APIs", "Options data", "Alpha Intelligence", "Fundamental data", "Forex (FX)",
            "Cryptocurrencies", "Commodities", "Economic indicators", "Technical indicators"} <= parts
    assert [a.name for a in ALPHA_VANTAGE.covered] == ["Core stock APIs"]
    assert all(c.area in parts for c in ALPHA_VANTAGE.calls)
    assert not [c for c in ALPHA_VANTAGE.calls if c.writes or c.costs]  # it only reads; nothing on it starts a charge
    assert all(u.startswith("https://www.alphavantage.co/") for u in urls(APIS)) and ALPHA_VANTAGE.verified == "2026-11-11"
    assert "25 requests a day" in ALPHA_VANTAGE.limits


def test_it_asks_nothing_to_say_what_it_learned():
    assert av.PLUGIN.api_facts() == {}  # the instance holds no run's state
    p = registry.reload()["alphavantage"]
    assert p.apis == APIS and p.interface()["apis"] == ["Alpha Vantage API"]


@pytest.mark.skipif(os.environ.get("LIMINAL_VENDOR_PAGES") != "1", reason="asks Alpha Vantage's pages (LIMINAL_VENDOR_PAGES=1)")
def test_every_address_on_its_card_answers():
    assert dead_links(APIS) == []
