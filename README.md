# plugin-integrator-alphavantage

Alpha Vantage for [Liminal](https://github.com/pcxmac-dev/liminal-charts): the daily bars of stocks listed
outside the US on the exchanges Alpha Vantage names by a ticker suffix of its own, on a free key
(`ALPHAVANTAGE_API_KEY`). One feed, `alphavantage`, stocks only:

| exchange | MIC | stored as (the library's name) | asked of Alpha Vantage as |
|---|---|---|---|
| London Stock Exchange | XLON | `VOD.L` | `VOD.LON` |
| Toronto Stock Exchange | XTSE | `SHOP.TO` | `SHOP.TRT` |
| TSX Venture Exchange | XTSX | `GPV.V` | `GPV.TRV` |
| Xetra | XETR | `SAP.DE` | `SAP.DEX` |
| BSE (Bombay) | XBOM | `RELIANCE.BO` | `RELIANCE.BSE` |
| Shanghai Stock Exchange | XSHG | `600519.SS` | `600519.SHH` |
| Shenzhen Stock Exchange | XSHE | `000001.SZ` | `000001.SHZ` |

`LSE:VOD`, `VOD::XLON` and `VOD.L` mean the same listing. Each symbol's bars come from `TIME_SERIES_DAILY`
with `outputsize=compact`: the latest 100 trading days in one request, raw as traded (no split or dividend
adjustment: the adjusted series is a premium plan's). The feed is live, not an archive: each run adds the new
days, so the stored series grows past the 100 over time. The whole history (`outputsize=full`) is a premium
plan's and is never asked for. Day bars are stamped at midnight New York of the local trading date, like every
stock's; the days are the exchange's own (every weekday, until the library carries its holidays).

A listing's record (its name, whether it is an ETF, its currency: London's in pence, GBX) comes from
`SYMBOL_SEARCH`, one request at the weekly listing check. Alpha Vantage lists no exchange abroad, so the
directory does not list these exchanges' stocks: a symbol is watched by its name.

A Liminal provider plugin released on its own. The app finds it through the entry point group
`liminal.providers` and lists it on the Plugins view and in `liminal-charts plugins` as
`package: plugin-integrator-alphavantage`, with this package's version.

## Its API

It attaches to Alpha Vantage's API, one address (`https://www.alphavantage.co/query`) whose `function=` parameter
chooses the data, the key sent as the `apikey` parameter. The card on its page in every app (`apis`, plugin API 2.2:
`src/plugin_integrator_alphavantage/apis.py`, read from Alpha Vantage's pages on 2026-11-11) says what the API is,
its limits and prices, every section of its documentation and every function called here:

- Documentation: <https://www.alphavantage.co/documentation/>
- Support and the free key's limit (25 requests a day): <https://www.alphavantage.co/support/>
- Premium plans (75 to 1,200 requests a minute, no daily limit): <https://www.alphavantage.co/premium/>
- Claim a free key: <https://www.alphavantage.co/support/#api-key>

Used here: `TIME_SERIES_DAILY` (compact) and `SYMBOL_SEARCH`, of the core stock APIs. Not used: the other time
series and quotes, index data, options, Alpha Intelligence, fundamentals, forex, crypto, commodities, economic and
technical indicators. Alpha Vantage publishes no status page.

## Install

Into the app's environment, from the app's folder:

```powershell
.venv\Scripts\python.exe -m pip install "plugin-integrator-alphavantage @ git+https://github.com/pcxmac-dev/plugin-integrator-alphavantage@v0.3.0"
```

or with the app's plugins (`pip install -e ".[plugins]"` in liminal-charts). The app loads it on its next
start.

## The key

`ALPHAVANTAGE_API_KEY`: a free key, claimed at alphavantage.co/support/#api-key with an email address. Save
it from the Plugins view or with the app's `tools/set-key.ps1` (it is read from your user environment
variables only, never written to a file). It goes to Alpha Vantage as the `apikey` query parameter, its only
form, and is taken out of any error's text. Without it the feed serves nothing and sends nothing.

## Limits

The free key allows 25 requests a day (Alpha Vantage's published limit, 2026-11-02); the plugin keeps that as
its daily cap for the whole machine, and 5 requests a minute. A watched symbol costs one request a run for its
new days and one a week for its listing check, so one key keeps about twenty symbols up to date daily. A
"Note" (the minute's limit) stops the run and rests the feed for a while; an "Information" (the day's requests
spent, or a premium endpoint) stops the run until the next; neither is ever taken for empty bars.

## Compatibility

It is written for plugin API 2.2, the class contract (`PLUGIN`, an instance of `AlphaVantagePlugin`, a
`FeedPlugin`: the exchanges a feed carries, `exchanges`, its plan's publication delay, `delays`, and what it
attaches to, `apis`; liminal-libs 1.49.0 or later). An app offering 2.2 or a later 2.x loads it; an app offering
an older 2.x, or another major, leaves it out and says why on the Plugins view.

## Develop

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install "liminal-libs @ git+https://github.com/pcxmac-dev/liminal-libs@main"
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
```

Tests never send requests (a fake session answers with bodies shaped like the documented ones) and never
read your keys. One test asks every address on the API's card, only with `LIMINAL_VENDOR_PAGES=1` set.
