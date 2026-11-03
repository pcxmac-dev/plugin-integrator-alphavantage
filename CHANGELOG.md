# Changelog

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
query parameter and is taken out of any error's text. Plugin API 1.12, liminal-lib 1.2.0 or later.
