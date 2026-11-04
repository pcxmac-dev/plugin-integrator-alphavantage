"""Alpha Vantage (alphavantage.co) for Liminal: daily bars of stocks listed outside the US on the exchanges
Alpha Vantage names by a ticker suffix of its own (London, Toronto, TSX Venture, Xetra, BSE, Shanghai,
Shenzhen), on a free key: TIME_SERIES_DAILY with outputsize=compact, the latest 100 trading days in one
request, the stored series growing by the new days of each run. Stocks only (the plan's decision,
2026-11-02: Twelve Data is the FX addition).

A Liminal plugin released on its own, registered under the entry point group `liminal.providers` as
`alphavantage` (PLUGIN: one feed, an instance of `AlphaVantagePlugin` on the class contract, plugin API 2.0,
liminal-lib 1.3.0: liminal_lib.sources.plugin.FeedPlugin; what it declares its class attributes, what it does
its methods). It relies on the contract (`exchanges`: a listing abroad comes to it and to no US feed; `delays`:
its plan's publication delay) and nothing of the app outside it; its version is this distribution's
(pyproject.toml), so the instance's version is left empty.

Checked against the documentation page (https://www.alphavantage.co/documentation/, read 2026-11-02, no key
sent): TIME_SERIES_DAILY takes function, symbol, outputsize (compact, the default, "returns only the latest
100 data points"; full, "the full-length time series of 25+ years", "available to premium keys"), datatype
and apikey; its sample tickers abroad are TSCO.LON (London), SHOP.TRT (Toronto), GPV.TRV (TSX Venture),
MBG.DEX (Xetra), RELIANCE.BSE (BSE), 600104.SHH (Shanghai) and 000002.SHZ (Shenzhen); SYMBOL_SEARCH takes
keywords, datatype and apikey ("a full text search" ranked by match scores). The support page
(https://www.alphavantage.co/support/, read 2026-11-02) gives the free key "25 API requests per day" and
names no limit a minute: the 5 a minute of the free key's earlier terms is kept, inside anything it has.
What the page shows only through its live examples was not confirmed (no request went to the keyed API):
the answers' keys ("Meta Data"; "Time Series (Daily)" by date, each day "1. open", "2. high", "3. low",
"4. close", "5. volume" as strings; "bestMatches" with "1. symbol", "2. name", "3. type", "4. region",
"8. currency", "9. matchScore"), the messages a 200 carries ("Note", "Information", "Error Message"), and
whether SYMBOL_SEARCH matches a keyword with the suffix on (the bare code is asked next when it does not):
the first real requests confirm them."""
from __future__ import annotations

from liminal_lib.config import Tier
from liminal_lib.freshness import Delay
from liminal_lib.sources.registry import FeedPlugin, KeyVar, limiter, machine_caps
from .client import API, KEY, SUFFIXES, AlphaVantageClient, AlphaVantageSource, av_symbol, stored_ticker  # noqa: F401

NAME = "alphavantage"
# Its free plan and caps: 25 requests a day (the support page, 2026-11-02), 5 a minute kept; compact gives
# the latest 100 trading days, so the history floor is 100 days back (collector.history_floor); the plan's
# publication delay is end of day under this name (freshness.PLAN_DELAYS["alphavantage-free"]).
TIER = Tier("alphavantage-free", requests_per_minute=5, history_years=None, history_days=100)
PER_RUN, PER_DAY = 25, 25
RATE = (5, 62.0)  # the window kept: 5 requests in 62 seconds (a couple of seconds inside the minute)


def api_key(settings) -> str | None:
    """The Alpha Vantage key among the settings' plugin variables (Settings.env), spaces around it taken
    off (one pasted with a newline would make every request fail), or None."""
    return (settings.env.get(KEY) or "").strip() or None


class AlphaVantagePlugin(FeedPlugin):
    """The feed as a class (plugin API 2.0): what it declares its class attributes, what it does its methods
    (`build`: its source on a keyed client; `has_keys`, `rate`, `markets`), the rest the contract's defaults."""

    api = "2.0"  # the contract it needs (the class contract: exchanges, delays); its version: the distribution's
    name = NAME
    title = "Alpha Vantage"
    assets = frozenset({"stock"})
    order = 120
    about = ("daily bars of stocks on London, Toronto, TSX Venture, Xetra, BSE, Shanghai and Shenzhen, "
             "the latest 100 days a request (a free key)")
    keys = (KeyVar(KEY, hint="the free key alphavantage.co sent you"),)
    signup = "alphavantage.co/support/#api-key: a free key, claimed with an email address"
    exchanges = frozenset(SUFFIXES)  # XLON, XTSE, XTSX, XETR, XBOM, XSHG, XSHE: the ones with a suffix of its own
    archival = False
    tier = TIER
    per_run, per_day = PER_RUN, PER_DAY
    limits = ("free: 25 requests a day (the latest 100 days a request; the whole history, outputsize=full, "
              "is a premium plan's)")
    kind = "vendor"
    provides = {"stock": ("day",)}
    per_request = {"day": 100}  # one request: the latest 100 trading days
    bulk_resolution = "day"
    missing_keys_note = "key not set: Alpha Vantage's daily bars come with ALPHAVANTAGE_API_KEY (a free key)"
    # when its data is published (the library's freshness.PLAN_DELAYS row for alphavantage-free, declared here
    # too): a day's bar once the exchange's session is over, end of day
    delays = {"alphavantage-free": {"stock": Delay("eod")}}

    def build(self, settings, request_budget):
        key = api_key(settings)
        client = AlphaVantageClient(key, request_budget=request_budget, rate_limiter=limiter(self.name, settings, key))
        return AlphaVantageSource(machine_caps(client, self.name, settings, key), has_key=bool(key))

    def has_keys(self, settings):
        return bool(api_key(settings))

    def rate(self, settings):
        return RATE

    def markets(self, settings):
        return {"stock": self.name}


PLUGIN = AlphaVantagePlugin()
