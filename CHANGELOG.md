# Changelog

## 0.2.0 (2026-11-03)

Renamed `plugin-integrator-alphavantage` (the package `plugin_integrator_alphavantage`; it was `liminal-plugin-alphavantage`) on 2026-11-03: the naming by system (plugins are `plugin-<app>-<name>`), on liminal-libs 1.4.0 (`liminal_libs`, the library renamed with it).

The plugin is a class on plugin API 2.0 (the class contract, liminal-libs 1.3.0; the user: "all the plugins under
liminal should basically follow inheritance/oop paradigm"): `PLUGIN` is an instance of `AlphaVantagePlugin`, a
`FeedPlugin`, what it declares its class attributes (its key, its exchanges, its free plan and caps ...) and what
it does its methods (`build`, `has_keys`, `rate`, `markets`). It declares its plan's publication delay itself
(`delays`: `alphavantage-free`, end of day; the library's row stays). Every fact, limit and string is as in 1.0.0.
Its version is the release's, 0.2.0, as every Liminal plugin's on `release/0.2.0`; requires liminal-libs 1.3.0.

## 1.0.0 (2026-11-02)

The first release (the user, 2026-11-02: "if new sources, create a new plugin"): one feed, `alphavantage`, the
daily bars of stocks listed outside the US on the exchanges Alpha Vantage names by a ticker suffix of its own:
London (XLON, `VOD.L` asked as `VOD.LON`), Toronto (XTSE, `SHOP.TO` as `SHOP.TRT`), TSX Venture (XTSX, `.V` as
`.TRV`), Xetra (XETR, `SAP.DE` as `SAP.DEX`), BSE (XBOM, `.BO` as `.BSE`), Shanghai (XSHG, `600519.SS` as
`600519.SHH`) and Shenzhen (XSHE, `000001.SZ` as `000001.SHZ`); stocks only. `TIME_SERIES_DAILY` with
`outputsize=compact` (the latest 100 trading days, raw as traded) in one request a symbol, the stored series
growing by the new days of each run (not an archive); the free key's limits (25 requests a day, 5 a minute)
kept on the machine; a "Note" or an "Information" in a 200 raised as the limit it is (never as empty bars), an
"Error Message" as the symbol's own error. A listing's record (name, type, currency, its exchange) from
`SYMBOL_SEARCH`, one request at the weekly listing check. The key `ALPHAVANTAGE_API_KEY` goes as the `apikey`
query parameter and is taken out of any error's text. Plugin API 1.12, liminal-libs 1.2.0 or later.
