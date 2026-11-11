"""What Alpha Vantage's plugin attaches to (plugin API 2.2, liminal_libs.sources.apis): Alpha Vantage's API, as its
pages said on 2026-11-11 (the documentation at alphavantage.co/documentation/, one page whose sections and functions
were read that day; the support page's free key and its limit; the premium page's plans).

The user, 2026-11-11: "each plugin should reflect the the API its attached to, and present links that provide
documentation, the plugin interface should more or less contain what it already has, BUT, it should also expose more of
what the API is about". So every part of the API is named (`areas`: the documentation's sections), each said used here
or not, and the functions the plugin calls (`used`) beside the notable ones it does not: on Alpha Vantage a call is a
`function=` of its one query address."""
from __future__ import annotations

from liminal_libs.sources.apis import Api, Area, Call, Link

from .client import API

DOCS = "https://www.alphavantage.co/documentation/"
KEY_PAGE = "https://www.alphavantage.co/support/#api-key"  # where the free key is claimed (the plugin's `signup`)
QUERY = f"{API}/query"
CORE, INTELLIGENCE, FUNDAMENTALS = "Core stock APIs", "Alpha Intelligence", "Fundamental data"


def _at(anchor: str) -> str:
    return f"{DOCS}#{anchor}"


def _fn(function: str) -> str:
    """A call's name: the function on the query address."""
    return f"GET /query?function={function}"


ALPHA_VANTAGE = Api(
    name="Alpha Vantage API",
    maker="Alpha Vantage",
    about=("Alpha Vantage's API answers on one address, a function= parameter choosing the data: stock time series, "
           "quotes and search worldwide, options, Alpha Intelligence (news sentiment, transcripts, insider and "
           "institutional trades), fundamentals, forex, crypto, commodities, economic indicators and 50+ technical "
           "indicators. A free key allows 25 requests a day; premium keys are sold by the requests a minute."),
    kind="query",
    base=QUERY,
    auth=("a free API key, claimed with an email address on its support page, sent as the apikey query parameter (its "
          "only form): the plugin takes it out of every error's text"),
    limits=("free: 25 requests a day (no minute's limit named; the plugin keeps 5 a minute); premium: 75 to 1,200 "
            "requests a minute, no daily limit. The plugin reads a Note or an Information in a 200 answer as a limit "
            "met"),
    costs=("the free key costs nothing; premium a month: 75 requests a minute $49.99, 150 $99.99, 300 $149.99, 600 "
           "$199.99, 1,200 $249.99 (a year's from $499). Premium also unlocks outputsize=full (25+ years a request), "
           "the functions marked premium (intraday and adjusted series, bulk quotes, index data, options, news and "
           "sentiment, company overviews, forex and crypto intraday, VWAP, MACD) and realtime or 15-minute delayed US "
           "data"),
    links=(
        Link("API documentation", DOCS, "docs"),
        Link("Support and the free key's limit", "https://www.alphavantage.co/support/", "limits"),
        Link("Premium plans", "https://www.alphavantage.co/premium/", "pricing"),
        Link("Claim a free API key", KEY_PAGE, "console"),
        Link("Terms of service", "https://www.alphavantage.co/terms_of_service/", "terms"),
    ),
    areas=(
        Area(CORE, "stock time series (intraday to monthly, raw and adjusted), quotes, bulk quotes, ticker search and the "
             "markets' open and close", _at("time-series-data"),
             covered="the daily series (compact: the latest 100 days) of stocks on London, Toronto, TSX Venture, Xetra, "
                     "BSE, Shanghai and Shenzhen; the ticker search for a listing's record"),
        Area("Index data", "the major indices' values and a catalog of others (premium)", _at("index-data")),
        Area("Options data", "realtime and historical options chains (premium), put-call and volume to open interest "
             "ratios", _at("options")),
        Area(INTELLIGENCE, "news and sentiment, earnings call transcripts, top gainers and losers, insider, congress and "
             "institutional trades, analytics", _at("intelligence")),
        Area(FUNDAMENTALS, "company overviews and logos, ETF profiles, dividends and splits, statements, earnings and "
             "their estimates, listing status, the earnings and IPO calendars", _at("fundamentals")),
        Area("Forex (FX)", "exchange rates and intraday to monthly series of currency pairs", _at("fx")),
        Area("Cryptocurrencies", "exchange rates and intraday to monthly series of digital currencies",
             _at("digital-currency")),
        Area("Commodities", "gold and silver, oil, natural gas, metals and crops, a global commodities index",
             _at("commodities")),
        Area("Economic indicators", "real GDP, treasury yields, the federal funds rate, CPI and inflation, retail sales, "
             "durable goods, unemployment, nonfarm payroll", _at("economic-indicators")),
        Area("Technical indicators", "moving averages, oscillators, volatility and volume indicators, Hilbert transforms "
             "(50+), computed by Alpha Vantage", _at("technical-indicators")),
    ),
    calls=(
        Call(_fn("TIME_SERIES_DAILY"), "a stock's raw daily series: the latest 100 days (compact), or 25+ years (full, "
             "premium)", CORE,
             used="a listing's latest 100 trading days (outputsize=compact), once a symbol a run", docs=_at("daily")),
        Call(_fn("SYMBOL_SEARCH"), "tickers matching keywords, ranked by match score", CORE,
             used="a listing's record: its name, type and currency (asked with its suffix, then by its bare code)",
             docs=_at("symbolsearch")),
        Call(_fn("TIME_SERIES_INTRADAY"), "a stock's intraday series (premium)", CORE, docs=_at("intraday")),
        Call(_fn("TIME_SERIES_DAILY_ADJUSTED"), "a stock's daily series adjusted for splits and dividends (premium)",
             CORE, docs=_at("dailyadj")),
        Call(_fn("TIME_SERIES_WEEKLY"), "a stock's weekly series", CORE, docs=_at("weekly")),
        Call(_fn("TIME_SERIES_MONTHLY"), "a stock's monthly series", CORE, docs=_at("monthly")),
        Call(_fn("GLOBAL_QUOTE"), "a stock's latest price and volume", CORE, docs=_at("latestprice")),
        Call(_fn("REALTIME_BULK_QUOTES"), "up to 100 US stocks' realtime quotes at once (premium)", CORE,
             docs=_at("realtime-bulk-quotes")),
        Call(_fn("MARKET_STATUS"), "whether the world's major markets are open", CORE, docs=_at("market-status")),
        Call(_fn("INDEX_DATA"), "a major index's values (premium)", "Index data", docs=_at("index-data")),
        Call(_fn("REALTIME_OPTIONS"), "US options chains now (premium)", "Options data", docs=_at("realtime-options")),
        Call(_fn("HISTORICAL_OPTIONS"), "a symbol's options chain on a past day, with IV and the Greeks (premium)", "Options data",
             docs=_at("historical-options")),
        Call(_fn("NEWS_SENTIMENT"), "live and historical market news with its sentiment (premium)", INTELLIGENCE,
             docs=_at("news-sentiment")),
        Call(_fn("TOP_GAINERS_LOSERS"), "the top 20 gainers, losers and most active US tickers", INTELLIGENCE,
             docs=_at("gainer-loser")),
        Call(_fn("OVERVIEW"), "a company's information, ratios and key metrics (premium)", FUNDAMENTALS,
             docs=_at("company-overview")),
        Call(_fn("LISTING_STATUS"), "the active or delisted US stocks and ETFs, now or on a day in history", FUNDAMENTALS,
             docs=_at("listing-status")),
        Call(_fn("CURRENCY_EXCHANGE_RATE"), "the realtime rate between two fiat currencies", "Forex (FX)",
             docs=_at("currency-exchange")),
        Call(_fn("FX_DAILY"), "a currency pair's daily series", "Forex (FX)", docs=_at("fx-daily")),
        Call(_fn("DIGITAL_CURRENCY_DAILY"), "a digital currency's daily series", "Cryptocurrencies",
             docs=_at("currency-daily")),
        Call(_fn("WTI"), "the West Texas Intermediate crude oil price", "Commodities", docs=_at("wti")),
        Call(_fn("REAL_GDP"), "US real GDP, yearly or quarterly", "Economic indicators", docs=_at("real-gdp")),
        Call(_fn("SMA"), "a simple moving average of a series", "Technical indicators", docs=_at("sma")),
    ),
    verified="2026-11-11",
)

APIS = (ALPHA_VANTAGE,)
