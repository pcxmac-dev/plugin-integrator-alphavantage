"""The Alpha Vantage plugin, run against the library installed beside it: its tickers mapped to Alpha
Vantage's suffixes and back, its daily answer read once a run, the limits it says in a 200 raised as what
they are, a listing's record from the search, its exchanges, the key kept out of every error, and the app
loading it from this package with its own version and facts."""
from __future__ import annotations

from datetime import date, datetime
from importlib.metadata import version

import pytest
import requests

from liminal_lib import composite, freshness, killswitch
from liminal_lib.collector import history_floor
from liminal_lib.config import load_settings
from liminal_lib.errors import BudgetExhausted, NotEntitled, RateLimited, SourceError
from liminal_lib.sources import feed_profiles, is_archive, markets, provider, rate_window, registry, supports
from liminal_lib.sources.archive import ET, ms
from liminal_lib.symbols import resolve

import liminal_plugin_alphavantage as av
from liminal_plugin_alphavantage import PER_DAY, PER_RUN, TIER
from liminal_plugin_alphavantage.client import (CACHE_SECONDS, SERIES, SUFFIXES, AlphaVantageClient, AlphaVantageSource,
                                                av_symbol, read_daily, scrubbed, stored_ticker)

from .conftest import FakeResponse, FakeSession

KEYS = {"ALPHAVANTAGE_API_KEY": "k"}
# answers shaped like the documented ones (prices and volumes as strings, newest day first)
DAILY = {
    "Meta Data": {"1. Information": "Daily Prices (open, high, low, close) and Volumes", "2. Symbol": "VOD.LON",
                  "3. Last Refreshed": "2026-10-30", "4. Output Size": "Compact", "5. Time Zone": "US/Eastern"},
    SERIES: {
        "2026-10-30": {"1. open": "92.2000", "2. high": "93.1000", "3. low": "91.8000", "4. close": "92.9000", "5. volume": "41235678"},
        "2026-10-29": {"1. open": "91.6000", "2. high": "92.4000", "3. low": "91.0000", "4. close": "92.1000", "5. volume": "38120044"},
        "2026-10-28": {"1. open": "90.9000", "2. high": "91.9000", "3. low": "90.5000", "4. close": "91.5000", "5. volume": "35902311"},
    },
}
SEARCH = {"bestMatches": [
    {"1. symbol": "VOD", "2. name": "Vodafone Group Public Limited Company", "3. type": "Equity", "4. region": "United States",
     "5. marketOpen": "09:30", "6. marketClose": "16:00", "7. timezone": "UTC-04", "8. currency": "USD", "9. matchScore": "1.0000"},
    {"1. symbol": "VOD.LON", "2. name": "Vodafone Group Plc", "3. type": "Equity", "4. region": "United Kingdom",
     "5. marketOpen": "08:00", "6. marketClose": "16:30", "7. timezone": "UTC+01", "8. currency": "GBX", "9. matchScore": "0.8571"},
]}
NOTE = {"Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute and 25 calls per "
                "day. Please visit https://www.alphavantage.co/premium/ if you would like to target a higher API call frequency."}
DAY_SPENT = {"Information": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day. Please "
                            "subscribe to any of the premium plans at https://www.alphavantage.co/premium/ to instantly remove "
                            "all daily rate limits."}
PREMIUM = {"Information": "Thank you for using Alpha Vantage! This is a premium endpoint. You may subscribe to any of the "
                          "premium plans at https://www.alphavantage.co/premium/ to instantly unlock all premium endpoints"}
BAD_CALL = {"Error Message": "Invalid API call. Please retry or visit the documentation "
                             "(https://www.alphavantage.co/documentation/) for TIME_SERIES_DAILY."}
WINDOW = (date(2026, 10, 1), date(2026, 10, 31), "day")


def _source(*bodies, key="k", now=None):
    session = FakeSession([FakeResponse(200, b) for b in bodies])
    client = AlphaVantageClient(key, session=session, sleep=lambda s: None)
    return AlphaVantageSource(client, has_key=bool(key), **({"now": now} if now else {})), session


def test_a_london_listing_is_asked_under_alpha_vantages_suffix_and_read_once_a_run():
    clock = [1000.0]
    src, session = _source(DAILY, DAILY, now=lambda: clock[0])
    bars = next(src.bar_pages("VOD.L", date(2026, 10, 29), date(2026, 10, 30), "day"))
    assert [b["c"] for b in bars] == [92.1, 92.9] and bars[0]["t"] == ms(datetime(2026, 10, 29, tzinfo=ET))  # oldest first
    assert bars[1] == {"t": ms(datetime(2026, 10, 30, tzinfo=ET)), "o": 92.2, "h": 93.1, "l": 91.8, "c": 92.9, "v": 41235678.0,
                       "vw": None, "n": None}
    url, params, headers = session.calls[0]
    assert url == "https://www.alphavantage.co/query"
    assert params == {"function": "TIME_SERIES_DAILY", "symbol": "VOD.LON", "outputsize": "compact", "apikey": "k"}
    assert "Authorization" not in headers and headers["User-Agent"].startswith("liminal/")
    newest = next(src.bar_pages("VOD.L", *WINDOW, descending=True, limit=1))
    assert [b["t"] for b in newest] == [ms(datetime(2026, 10, 30, tzinfo=ET))] and len(session.calls) == 1  # kept: one request a run
    assert next(src.bar_pages("VOD.L", date(2026, 11, 1), date(2026, 11, 2), "day")) == []  # days it has not (a weekend): no data
    clock[0] += CACHE_SECONDS
    assert len(next(src.bar_pages("VOD.L", *WINDOW))) == 3 and len(session.calls) == 2  # a later run asks again
    assert src.covers("VOD.L") and src.covers("600519.SS") and not src.covers("AAPL") and src.requests_made == 2
    assert len(read_daily({"2026-10-30": {"1. open": "x"}, "bad": {}, "2026-10-29": DAILY[SERIES]["2026-10-29"], "2026-10-27": "?"})) == 1


def test_every_documented_suffix_is_mapped_both_ways():
    pairs = [("VOD.L", "VOD.LON", "XLON"), ("SHOP.TO", "SHOP.TRT", "XTSE"), ("GPV.V", "GPV.TRV", "XTSX"),
             ("SAP.DE", "SAP.DEX", "XETR"), ("RELIANCE.BO", "RELIANCE.BSE", "XBOM"), ("600519.SS", "600519.SHH", "XSHG"),
             ("000001.SZ", "000001.SHZ", "XSHE")]
    for stored, symbol, mic in pairs:
        assert av_symbol(stored) == (symbol, mic) and av_symbol(stored.lower()) == (symbol, mic)
        assert stored_ticker(symbol) == (stored, mic) and stored_ticker(symbol.lower()) == (stored, mic)
    assert {mic for _, _, mic in pairs} == set(SUFFIXES) == av.PLUGIN.exchanges
    for other in ("AAPL", "BRK.B", "7203.T", "MC.PA", "RELIANCE.NS", "VOD", "VOD.LON"):
        assert av_symbol(other) is None, other  # not stored names on an exchange carried
    assert stored_ticker("IBM") is None and stored_ticker("VOD.FRK") is None and stored_ticker("VOD.L") is None


def test_what_it_does_not_serve_is_refused_before_any_request():
    src, session = _source()
    for ticker, timespan in (("VOD.L", "minute"), ("VOD.L", "hour"), ("AAPL", "day"), ("7203.T", "day"), ("BRK.B", "day")):
        with pytest.raises(NotEntitled):
            next(src.bar_pages(ticker, date(2026, 10, 1), date(2026, 10, 2), timespan))
    assert src.serves("stock") and src.resolutions("stock") == ("day",) and not src.serves("fx")
    keyless, keyless_session = _source(key=None)
    assert not keyless.serves("stock") and keyless.resolutions("stock") == () and keyless.resolutions("fx") == ()
    with pytest.raises(NotEntitled):
        next(keyless.bar_pages("VOD.L", date(2026, 10, 1), date(2026, 10, 2), "day"))
    with pytest.raises(NotEntitled):
        keyless.instrument("VOD.L")
    with pytest.raises(NotEntitled):
        keyless.client.query("SYMBOL_SEARCH", "VOD.LON", keywords="VOD.LON")
    assert session.calls == [] and keyless_session.calls == []


def test_a_limit_said_in_a_200_is_raised_as_what_it_is_never_as_empty_bars():
    unreadable = {"Meta Data": {}, SERIES: {"2026-10-30": {"close": "1"}}}  # a series of days in another form
    src, session = _source(NOTE, DAY_SPENT, PREMIUM, BAD_CALL, {"Meta Data": {}}, unreadable, [], DAILY)
    with pytest.raises(RateLimited) as e:
        next(src.bar_pages("VOD.L", *WINDOW))
    assert e.value.status == 429 and e.value.retry_after == 60.0 and "5 calls per minute" in e.value.message
    assert killswitch.is_refusal(e.value, e.value.status)  # the feed is killed for a while, not asked 24 times more
    with pytest.raises(BudgetExhausted, match="25 requests per day"):
        next(src.bar_pages("VOD.L", *WINDOW))  # the run stops, no strike
    with pytest.raises(BudgetExhausted, match="premium endpoint"):
        next(src.bar_pages("VOD.L", *WINDOW))
    with pytest.raises(SourceError, match="Invalid API call") as e:
        next(src.bar_pages("VOD.L", *WINDOW))
    assert e.value.status == 200 and not killswitch.is_refusal(e.value, e.value.status)  # the symbol's own error, not the server's
    with pytest.raises(SourceError, match="format changed"):
        next(src.bar_pages("VOD.L", *WINDOW))  # no series in it
    with pytest.raises(SourceError, match="could be read"):
        next(src.bar_pages("VOD.L", *WINDOW))
    with pytest.raises(SourceError, match="not an object"):
        next(src.bar_pages("VOD.L", *WINDOW))  # a list
    assert len(next(src.bar_pages("VOD.L", *WINDOW))) == 3 and len(session.calls) == 8  # nothing that failed was kept
    assert next(_source({"Meta Data": {}, SERIES: {}})[0].bar_pages("VOD.L", *WINDOW)) == []  # a series with no day: no data


def test_a_listings_record_comes_from_one_search_and_names_its_exchange():
    src, session = _source(SEARCH)
    inst = src.instrument("VOD.L", resolve_exchange=False)  # as the weekly listing check asks
    assert session.calls[0][1] == {"function": "SYMBOL_SEARCH", "keywords": "VOD.LON", "apikey": "k"} and len(session.calls) == 1
    assert inst.ticker == "VOD.L" and inst.name == "Vodafone Group Plc" and inst.kind == "stock" and inst.active
    assert inst.currency == "GBX" and inst.list_date is None and inst.figi is None  # pence; no listing date, no FIGI
    assert (inst.primary_exchange.mic, inst.primary_exchange.name, inst.primary_exchange.country.code) == (
        "XLON", "London Stock Exchange", "GB")
    assert inst.details["4. region"] == "United Kingdom"
    assert inst.describe() == "VOD.L (stock, Vodafone Group Plc) on London Stock Exchange"
    # the symbol itself among the matches, not the best match (VOD on Nasdaq); the bare code asked when the
    # suffixed keyword finds no match that is it
    us_only = {"bestMatches": SEARCH["bestMatches"][:1]}
    src, session = _source(us_only, {"bestMatches": SEARCH["bestMatches"][1:]})
    assert src.instrument("VOD.L").name == "Vodafone Group Plc" and [c[1]["keywords"] for c in session.calls] == ["VOD.LON", "VOD"]
    src, session = _source(us_only, {"bestMatches": []})
    gone = src.instrument("VOD.L")
    assert not gone.active and gone.name is None and gone.ticker == "VOD.L" and gone.currency == "GBP"
    assert gone.primary_exchange.mic == "XLON" and gone.details["search"] == "VOD.LON" and len(session.calls) == 2
    etf = {"bestMatches": [{"1. symbol": "ISF.LON", "2. name": "iShares Core FTSE 100 UCITS ETF", "3. type": "ETF",
                            "4. region": "United Kingdom", "8. currency": "GBX"}]}
    assert _source(etf)[0].instrument("ISF.L").kind == "etf"
    shanghai = {"bestMatches": [{"1. symbol": "600519.SHH", "2. name": "Kweichow Moutai Co Ltd", "3. type": "Equity",
                                 "4. region": "Shanghai", "8. currency": "CNY"}]}
    inst = _source(shanghai)[0].instrument("600519.SS")
    assert (inst.ticker, inst.primary_exchange.mic, inst.currency, inst.primary_exchange.country.code) == ("600519.SS", "XSHG", "CNY", "CN")
    toronto = {"bestMatches": [{"1. symbol": "shop.trt", "2. name": "Shopify Inc", "3. type": "Equity", "4. region": "Toronto"}]}
    inst = _source(toronto)[0].instrument("SHOP.TO")
    assert (inst.ticker, inst.primary_exchange.mic, inst.currency) == ("SHOP.TO", "XTSE", "CAD")  # the exchange's currency when unsaid
    with pytest.raises(NotImplementedError):
        _source()[0].instrument("AAPL")  # a US stock's identity is the whole-market feeds'
    with pytest.raises(NotImplementedError):
        _source()[0].instrument("7203.T")


def test_its_exchanges_are_the_seven_with_a_suffix_of_alpha_vantages_and_it_lists_none():
    src, session = _source()
    rows = src.exchanges()
    assert [(e.id, e.mic, e.acronym, e.country.code) for e in rows] == [
        (1, "XBOM", "BSE", "IN"), (2, "XETR", "DEX", "DE"), (3, "XLON", "LON", "GB"), (4, "XSHE", "SHZ", "CN"),
        (5, "XSHG", "SHH", "CN"), (6, "XTSE", "TRT", "CA"), (7, "XTSX", "TRV", "CA")]
    assert [e.name for e in rows] == ["BSE", "Xetra", "London Stock Exchange", "Shenzhen Stock Exchange", "Shanghai Stock Exchange",
                                      "Toronto Stock Exchange", "TSX Venture Exchange"]
    assert all(e.source == "alphavantage" and e.type == "exchange" for e in rows)
    assert rows[2].timezone == "Europe/London" and rows[0].timezone == "Asia/Kolkata"
    for mic in ("XLON", "xlon", "XNAS", "XTKS"):
        with pytest.raises(NotImplementedError):
            src.listings(mic)  # no directory of an exchange abroad: the refresh skips this feed
    assert session.calls == []


class FailingSession:
    """Every request fails on the way, as requests reports it: the URL asked, the key in it, in the error."""

    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        raise requests.ConnectionError("HTTPSConnectionPool(host='www.alphavantage.co', port=443): Max retries exceeded with "
                                       f"url: /query?function=TIME_SERIES_DAILY&symbol=VOD.LON&outputsize=compact&apikey={params['apikey']}")


def test_the_key_never_shows_in_an_error():
    session = FailingSession()
    src = AlphaVantageSource(AlphaVantageClient("SECRET123", session=session, sleep=lambda s: None), has_key=True)
    with pytest.raises(SourceError) as e:
        next(src.bar_pages("VOD.L", *WINDOW))
    assert "SECRET123" not in str(e.value) and "SECRET123" not in e.value.message and "apikey=***" in e.value.message
    assert e.value.__cause__ is None and e.value.__suppress_context__  # the connection error behind it (the URL in it) is not chained
    assert e.value.status == 0 and session.calls == 5 and src.requests_made == 5  # tried again as any outage, then given up
    kept = scrubbed(RateLimited(429, "slow down, SECRET123", 7.0), "SECRET123")
    assert isinstance(kept, RateLimited) and kept.retry_after == 7.0 and kept.message == "slow down, ***" and kept.status == 429
    clean = SourceError(500, "down")
    assert scrubbed(clean, "SECRET123") is clean
    assert isinstance(scrubbed(NotEntitled(403, "no SECRET123"), "SECRET123"), NotEntitled)


def test_the_app_loads_it_from_this_package_with_its_own_version():
    registry.reload()
    assert av.PLUGIN.name == "alphavantage" and not hasattr(av, "PLUGINS")
    p = registry.get("alphavantage")
    assert p is not None, dict(registry.errors())
    assert p.origin in {"package: liminal-plugin-alphavantage (liminal_plugin_alphavantage)",
                        "plugins/liminal-plugin-alphavantage (liminal_plugin_alphavantage)"}  # its package, or its checkout in the workspace's plugin directory
    assert p.version == version("liminal-plugin-alphavantage") and p.api == "1.12" and av.PLUGIN.version == ""
    assert registry.api_refusal(p.api) is None
    assert not [why for where, why in registry.errors() if "alphavantage" in where or "alphavantage" in why]
    row = {r["name"]: r for r in registry.menu()}["alphavantage"]
    assert (row["version"], row["api"], row["archive"], row["assets"]) == (version("liminal-plugin-alphavantage"), "1.12", False, ["stock"])
    assert [k["name"] for k in row["keys"]] == ["ALPHAVANTAGE_API_KEY"] and row["keys"][0]["secret"] and "alphavantage.co" in row["signup"]
    assert registry.plugin_feeds("alphavantage") == ["alphavantage"] and registry.plugin_of("alphavantage") == "alphavantage"
    assert "ALPHAVANTAGE_API_KEY" in registry.variables()


def test_it_keeps_its_facts(monkeypatch):
    registry.reload()
    s = load_settings(env=KEYS, env_file=None)
    view = s.for_source("alphavantage")
    assert (view.tier, view.max_requests_per_run, view.max_requests_per_day) == (TIER, PER_RUN, PER_DAY) == (TIER, 25, 25)
    assert (TIER.name, TIER.requests_per_minute, TIER.history_years, TIER.history_days) == ("alphavantage-free", 5, None, 100)
    assert rate_window("alphavantage", s) == (5, 62.0)
    assert not is_archive("alphavantage") and markets("alphavantage", s) == {"stock": "alphavantage"}
    p = provider("alphavantage")
    assert p.exchanges == {"XLON", "XTSE", "XTSX", "XETR", "XBOM", "XSHG", "XSHE"} and p.kind == "vendor" and p.bulk_resolution == "day"
    assert p.request_bars("day") == 100 and p.resolutions_for(view.tier, "stock") == ("day",) and p.resolutions_for(view.tier, "fx") == ()
    for text in ("VOD.L", "LSE:VOD", "VOD::XLON", "SHOP.TO", "TSX:SHOP", "GPV.V", "SAP.DE", "XETRA:SAP", "RELIANCE.BO",
                 "600519.SS", "000001.SZ"):
        assert supports("alphavantage", resolve(text)), text
    for text in ("AAPL", "BRK.B", "SPCX::NASDAQ", "7203.T", "RELIANCE.NS", "MC.PA", "0700.HK", "EURUSD", "I:VIX", "VX1!", "BTCUSD"):
        assert not supports("alphavantage", resolve(text)), text
    assert history_floor(view.tier, date(2026, 11, 2)) == date(2026, 7, 25)  # the latest 100 days: what compact gives
    assert freshness.plan_delay(view.tier, "stock").kind == "eod"
    assert composite.feed_kind("alphavantage", "stock") == "vendor"
    profile = feed_profiles(s)["alphavantage"]
    assert profile.assets == frozenset({"stock"}) and profile.venues == {"stock": "alphavantage"} and profile.capacity == 25.0
    assert p.keys_set(s) and feed_profiles(load_settings(env={}, env_file=None))["alphavantage"].assets == frozenset()  # no key: nothing
    assert not p.keys_set(load_settings(env={"ALPHAVANTAGE_API_KEY": "  "}, env_file=None))
    assert av.api_key(load_settings(env={"ALPHAVANTAGE_API_KEY": " k\n"}, env_file=None)) == "k"  # pasted with a newline
    held = []
    monkeypatch.setattr(av, "limiter", lambda name, st, key: held.append(("window", name, key)))
    monkeypatch.setattr(av, "machine_caps", lambda client, name, st, key: held.append(("day", name, key)) or client)
    source = av.build(s, 5)
    assert held == [("window", "alphavantage", "k"), ("day", "alphavantage", "k")]  # the window and the day's cap under its name and key
    assert source.name == "alphavantage" and source.has_key and source.client.key == "k" and source.client.request_budget == 5
    assert source.client.base_url == "https://www.alphavantage.co" and not source.archival
    assert not av.build(load_settings(env={}, env_file=None), 5).has_key
    report = p.report(profile, date(2026, 11, 2), s)
    assert report.plan == "alphavantage-free" and report.keys_set and report.limits.per_day == 25 and report.limits.rate == (5, 62.0)
    assert [(c.asset, c.resolution, c.market, str(c.since), c.per_request) for c in report.capabilities] == [
        ("stock", "day", "alphavantage", "2026-07-25", 100)]
    assert report.kind == "vendor" and not report.notes  # not an archive
