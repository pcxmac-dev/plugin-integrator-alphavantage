"""Alpha Vantage's client and source (alphavantage.co): a stock listed abroad's latest 100 trading days from
TIME_SERIES_DAILY in one request on a free key, its record from SYMBOL_SEARCH, the key as the `apikey` query
parameter (Alpha Vantage's only form) and kept out of every error, the limits it says in a 200 raised as what
they are."""
from __future__ import annotations

import time
from datetime import date, datetime
from typing import Callable, Iterator, Mapping

from liminal_libs.errors import BudgetExhausted, NotEntitled, RateLimited, SourceError
from liminal_libs.models import ETF, Exchange, Instrument, Stock, country, exchange_name, listing_ticker, suffix_mic, venue
from liminal_libs.sources.archive import ET, Archive, bounds, ms
from liminal_libs.sources.http import PublicClient

API = "https://www.alphavantage.co"
KEY = "ALPHAVANTAGE_API_KEY"  # a free alphavantage.co key, a user environment variable (the app's Plugins view)
# The exchanges abroad Alpha Vantage names by a suffix of its own on the ticker (its documentation's sample
# tickers, read 2026-11-02: TSCO.LON, SHOP.TRT, GPV.TRV, MBG.DEX, RELIANCE.BSE, 600104.SHH, 000002.SHZ), by MIC.
# A listing is stored under the library's suffix (VOD.L, SHOP.TO, GPV.V, SAP.DE, RELIANCE.BO, 600519.SS,
# 000001.SZ: models.VENUES) and asked for under Alpha Vantage's.
SUFFIXES = {"XLON": "LON", "XTSE": "TRT", "XTSX": "TRV", "XETR": "DEX", "XBOM": "BSE", "XSHG": "SHH", "XSHE": "SHZ"}
MICS = {suffix: mic for mic, suffix in SUFFIXES.items()}
IDS = {mic: i for i, mic in enumerate(sorted(SUFFIXES), 1)}  # the feed's own exchange ids (Exchange.id)
# the currency a listing's prices are in when its record does not say (London's says GBX: pence)
CURRENCIES = {"XLON": "GBP", "XTSE": "CAD", "XTSX": "CAD", "XETR": "EUR", "XBOM": "INR", "XSHG": "CNY", "XSHE": "CNY"}
SERIES = "Time Series (Daily)"  # the daily answer's series, by date, each day "1. open" ... "5. volume" as strings
NOTE_WAIT = 60.0  # the wait a "Note" (the minute's limit met) asks for: the minute over
CACHE_SECONDS = 600  # a symbol's answer serves every window asked in this long: one request a symbol a run


def av_symbol(ticker: str) -> tuple[str, str] | None:
    """(Alpha Vantage's symbol, the MIC) of a stored listing on an exchange carried here: VOD.L ->
    (VOD.LON, XLON), 600519.SS -> (600519.SHH, XSHG); None for anything else (AAPL and BRK.B, the US;
    7203.T, Tokyo, which Alpha Vantage has no suffix for here)."""
    base, dot, tail = ticker.strip().upper().rpartition(".")
    mic = suffix_mic(tail) if base and dot else None
    return (f"{base}.{SUFFIXES[mic]}", mic) if mic in SUFFIXES else None


def stored_ticker(symbol: str) -> tuple[str, str] | None:
    """(the stored name, the MIC) of one of Alpha Vantage's symbols on an exchange carried here:
    TSCO.LON -> (TSCO.L, XLON); None for another (IBM; VOD.FRK, Frankfurt)."""
    base, dot, tail = symbol.strip().upper().rpartition(".")
    mic = MICS.get(tail) if base and dot else None
    return (listing_ticker(base, mic), mic) if mic else None


def exchange_row(source: str, mic: str) -> Exchange:
    """An exchange carried, by the library's name, Alpha Vantage's suffix as its acronym."""
    v = venue(mic)
    return Exchange(source, IDS[mic], exchange_name(mic) or mic, country(v.country if v else None), mic=mic,
                    acronym=SUFFIXES[mic], type="exchange")


def checked(body, what: str) -> dict:
    """An answer's body, or the error it carries in a 200 (Alpha Vantage answers 200 to everything): a
    "Note" (the minute's limit met) is a RateLimited, an "Information" (the day's requests spent, or a
    premium endpoint asked) a BudgetExhausted, an "Error Message" (a symbol it has not, a bad call) the
    symbol's own SourceError (status 200: not the server failing); never an empty answer, which the sync
    would read as no data and mark the span done."""
    if not isinstance(body, dict):
        raise SourceError(200, f"Alpha Vantage: not an object in the answer for {what} ({str(body)[:120]})")
    note = body.get("Note")
    if note:
        raise RateLimited(429, f"Alpha Vantage: {str(note)[:200]}", NOTE_WAIT)
    info = body.get("Information")
    if info:
        raise BudgetExhausted(f"Alpha Vantage: {str(info)[:200]}")
    error = body.get("Error Message")
    if error:
        raise SourceError(200, f"Alpha Vantage: {str(error)[:200]} ({what})")
    return body


def unkeyed(body, key: str | None):
    """An answer with the key taken out of its words (the top level's text: Note, Information, message), before
    anything of it can become an error's message: a vendor's own words about a limit can repeat the key it was asked
    with (the review of 2026-11-21, item 26: the scrub covered only errors of the transport)."""
    if not key or not isinstance(body, dict):
        return body
    return {k: (v.replace(key, "<key>") if isinstance(v, str) else v) for k, v in body.items()}


def scrubbed(e: SourceError, key: str) -> SourceError:
    """The error with the key taken out of its text (a failed connection's error repeats the URL asked,
    the apikey parameter in it); the same error when it is clean."""
    if key not in e.message:
        return e
    message = e.message.replace(key, "***")
    if isinstance(e, RateLimited):
        return RateLimited(e.status, message, e.retry_after)
    return type(e)(e.status, message)


def read_daily(series: Mapping[str, Mapping[str, str]]) -> list[dict]:
    """The daily series' days as day bars, oldest first, each stamped at midnight US/Eastern of its date
    (the local trading date: the library's rule for a listing abroad, as for a US stock), its prices and
    volume read from Alpha Vantage's strings; a day that cannot be read is left out."""
    bars = []
    for day, row in series.items():
        try:
            d = date.fromisoformat(str(day)[:10])
            o, h, l, c = (float(row[k]) for k in ("1. open", "2. high", "3. low", "4. close"))
            v = float(row.get("5. volume") or 0)
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        bars.append({"t": ms(datetime(d.year, d.month, d.day, tzinfo=ET)), "o": o, "h": h, "l": l, "c": c, "v": v,
                     "vw": None, "n": None})
    bars.sort(key=lambda b: b["t"])
    return bars


class AlphaVantageClient(PublicClient):
    """Alpha Vantage's client: one host, the key as the `apikey` query parameter of every request (its only
    form), the key taken out of any error's text (scrubbed). Built with the feed's limiter and caps by the
    plugin's build (registry.limiter, machine_caps)."""

    def __init__(self, key: str | None, rate_limiter=None, session=None, sleep: Callable[[float], None] = time.sleep,
                 request_budget: int | None = None):
        super().__init__(API, rate_limiter=rate_limiter, session=session, sleep=sleep, request_budget=request_budget)
        self.key = key  # never written anywhere: not in a log, an error or a reference record

    def query(self, function: str, what: str, **params) -> dict:
        """One request of `function` with `params` (the key added): its answer, checked (checked); `what`
        names the symbol asked in an error."""
        if not self.key:
            raise NotEntitled(401, f"{KEY} not set; nothing sent")
        try:
            body = self.get("/query", {"function": function, **params, "apikey": self.key})
        except SourceError as e:
            raise scrubbed(e, self.key) from None  # the cause (a connection error) names the URL, the key in it
        return checked(unkeyed(body, self.key), what)


class AlphaVantageSource(Archive):
    """Stocks listed abroad from Alpha Vantage on a free key: TIME_SERIES_DAILY with outputsize=compact,
    the latest 100 trading days (raw, as traded: the adjusted series is a premium plan's), one request a
    symbol answering every window asked of it in a run; the stored series grows by the new days each run
    (not an archive: archival False). Day bars are stamped at midnight US/Eastern of the local trading
    date. A listing's record comes from SYMBOL_SEARCH (one request): its name, type and currency."""

    name = "alphavantage"
    assets = ("stock",)
    archival = False  # live: the new days keep coming

    def __init__(self, client: AlphaVantageClient, has_key: bool, now: Callable[[], float] = time.monotonic):
        super().__init__(client)
        self.has_key = has_key
        self.now = now
        self._daily: dict[str, tuple[float, list[dict]]] = {}  # symbol -> (when asked, its bars)

    def serves(self, asset: str) -> bool:
        return asset == "stock" and self.has_key

    def resolutions(self, asset: str) -> tuple[str, ...]:
        return ("day",) if self.serves(asset) else ()

    def covers(self, ticker: str) -> bool:
        return av_symbol(ticker) is not None

    def exchanges(self) -> list[Exchange]:
        """The exchanges carried (plugin API 1.12), by the library's names, in MIC order."""
        return [exchange_row(self.name, mic) for mic in sorted(SUFFIXES)]

    def listings(self, exchange: str) -> list[dict]:
        """None: Alpha Vantage lists no exchange abroad (its LISTING_STATUS is the US market's), so the
        directory refresh skips this feed; a listing is watched by its stored name (VOD.L) and its record
        found by the search (instrument)."""
        mic = exchange.strip().upper()
        if mic not in SUFFIXES:
            raise NotImplementedError(f"{self.name} carries no listings on {mic}")
        raise NotImplementedError(f"Alpha Vantage lists no exchange abroad: a listing on {mic} is watched by its "
                                  "name (VOD.L) and its record found by SYMBOL_SEARCH")

    def days(self, symbol: str) -> list[dict]:
        """A symbol's latest 100 trading days, oldest first (one request, kept CACHE_SECONDS for the windows
        the sync asks next: a symbol's gaps come one by one). An answer without the series, or one no day
        of which can be read, is an error, never an empty history."""
        kept = self._daily.get(symbol)
        if kept is not None and self.now() - kept[0] < CACHE_SECONDS:
            return kept[1]
        body = self.client.query("TIME_SERIES_DAILY", symbol, symbol=symbol, outputsize="compact")
        series = body.get(SERIES)
        if not isinstance(series, dict):
            raise SourceError(200, f"Alpha Vantage: no '{SERIES}' in the answer for {symbol} (it holds: "
                                   f"{', '.join(map(str, list(body)[:4])) or 'nothing'}); format changed?")
        bars = read_daily(series)
        if series and not bars:
            raise SourceError(200, f"Alpha Vantage: none of the {len(series)} days of {symbol} could be read; format changed?")
        self._daily[symbol] = (self.now(), bars)
        return bars

    def bar_pages(self, ticker, start, end, timespan, multiplier=1, descending=False, asset="stock",
                  limit: int | None = None) -> Iterator[list[dict]]:
        if not self.has_key:
            raise NotEntitled(401, f"{KEY} not set; nothing sent")
        if timespan != "day":
            raise NotEntitled(0, "Alpha Vantage serves daily bars here")
        found = av_symbol(ticker)
        if found is None:
            raise NotEntitled(0, f"Alpha Vantage carries no listing named {ticker} here (its exchanges: "
                                 f"{', '.join(sorted(SUFFIXES))})")
        a, b = bounds(start, end, ET)
        bars = [x for x in self.days(found[0]) if a <= x["t"] < b]
        bars.sort(key=lambda x: -x["t"] if descending else x["t"])
        yield bars[:limit] if limit else bars

    def search(self, symbol: str) -> tuple[dict | None, list[dict]]:
        """SYMBOL_SEARCH's match of the symbol itself (not its best match: VOD.LON's is VOD on Nasdaq),
        asked by the symbol with its suffix, then, when no match is it, by its bare code (the search is a
        full-text one; that a suffixed keyword matches is believed, confirmed by the first real request).
        (the match, every match of the last search)."""
        matches: list[dict] = []
        for keywords in (symbol, symbol.rpartition(".")[0]):
            body = self.client.query("SYMBOL_SEARCH", symbol, keywords=keywords)
            matches = [m for m in (body.get("bestMatches") or []) if isinstance(m, dict)]
            for m in matches:
                if str(m.get("1. symbol") or "").strip().upper() == symbol:
                    return m, matches
        return None, matches

    def instrument(self, ticker: str, resolve_exchange: bool = True) -> Instrument:
        """A listing's record from the search (one request, two when the suffixed keyword finds nothing):
        its name, its kind (an ETF's record is one), its currency (London's in pence, GBX) and its exchange
        (the one its stored name carries). No listing date nor FIGI: Alpha Vantage gives none. A symbol the
        search does not find is inactive here (its own status, no delisting date: the library notes it and
        asks again in a week, the fill goes on)."""
        if not self.has_key:
            raise NotEntitled(401, f"{KEY} not set; nothing sent")
        found = av_symbol(ticker)
        if found is None:
            raise NotImplementedError(f"alphavantage has no reference data for {ticker}: not on an exchange it carries")
        symbol, mic = found
        stored = listing_ticker(symbol.rpartition(".")[0], mic)
        exchange = exchange_row(self.name, mic)
        match, matches = self.search(symbol)
        if match is None:
            return Stock(ticker=stored, name=None, primary_exchange=exchange, currency=CURRENCIES[mic], active=False,
                         details={"search": symbol, "bestMatches": matches})
        kind = ETF if str(match.get("3. type") or "").strip().lower() == "etf" else Stock
        return kind(ticker=stored, name=str(match.get("2. name") or "").strip() or None, primary_exchange=exchange,
                    currency=str(match.get("8. currency") or "").strip().upper() or CURRENCIES[mic], list_date=None,
                    details=dict(match))
