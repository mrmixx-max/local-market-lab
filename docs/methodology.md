# Methodology

## Ratios and annualization

All ratios in Local Market Lab assume **252 trading days per year** and **daily returns**
(`r_t = close_t / close_{t-1} - 1`).

| Ratio | Formula | Notes |
|---|---|---|
| CAGR | `(end/start)^(1/years) - 1` | `years = (n-1)/252` |
| Volatility | `std(returns, ddof=1) * sqrt(252)` | sample stdev |
| Sharpe | `(mean_excess * 252) / (std * sqrt(252))` | MAR = 0 |
| Sortino | `(mean_excess * 252) / (downside_dev * sqrt(252))` | downside vs 0 |
| Calmar | `abs(CAGR) / MaxDrawdown` | 0.0 when MDD=0 |
| MaxDrawdown | `max((peak - trough) / peak)` | positive fraction |

## Backtest mechanics

- Aligned closes across symbols (intersection of dates; no forward-fill).
- Trade execution at same-day close.
- Fees + slippage deducted per trade as `|trade_value| * (fees_bps + slippage_bps) / 10000`.
- Benchmark: equal-weight buy-and-hold index of the same symbols (start = 100).

## Scenario methods

| Method | Description | When to use |
|---|---|---|
| `monte-carlo-iid` | Resample daily returns with replacement | Sensitivity check |
| `block-bootstrap-20d` | Resample contiguous 20-day blocks | Preserve short-range autocorrelation |
| `historical-replay` | Single realized path, drawdown windows | What already happened |

All scenario runs are **seeded** and record their method + data lineage.
They are **not forecasts** — this is stated explicitly in every report.

## Known limitations

- Survivorship bias possible if delisted instruments are absent.
- Same-day close execution underestimates real-world friction.
- Past distribution ≠ future distribution (stated on every scenario report).
- FX conversion requires explicit rates; no rate → INCOMPLETE marker (never silent 1:1).
