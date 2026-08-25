"""Report builders — artifact-driven, methodology and limitations mandatory."""

from __future__ import annotations

from packages.artifacts.manifest import load_json
from packages.compliance.guard import (
    RESEARCH_DISCLAIMER,
    SCENARIO_DISCLAIMER,
    assert_clean,
)


def portfolio_report(ws, valuation: dict) -> str:
    lines = [
        f"# Portfolio Report — {valuation['portfolio']}",
        "",
        f"- Reporting currency: **{valuation['reporting_currency']}**",
        f"- As of: **{valuation['as_of'] or 'latest available'}**",
        f"- Total value: **{valuation['total_value']:,.2f}**",
        f"- Total cost: **{valuation['total_cost']:,.2f}**",
        f"- Unrealized P/L: **{valuation['unrealized_pl']:+,.2f}**",
        "",
        "## Positions",
        "",
        "| Symbol | Qty | Avg Cost | Last | Value | P/L | P/L % | CCY |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in valuation["positions"]:
        lines.append(
            f"| {p['symbol']} | {p['quantity']} | {p['avg_cost']} | {p['last_price']} "
            f"| {p['value']:,.2f} | {p['pl']:+,.2f} | {p['pl_pct']}% | {p['currency']} |"
        )
    if valuation["incomplete_fx"]:
        lines += [
            "",
            f"> ⚠ INCOMPLETE: missing FX rates for "
            f"{[x['symbol'] for x in valuation['incomplete_fx']]} — excluded from totals.",
        ]
    if valuation["missing_prices"]:
        lines += [
            "",
            f"> ⚠ MISSING PRICES for {valuation['missing_prices']} — excluded.",
        ]
    lines += ["", "---", "", RESEARCH_DISCLAIMER, ""]
    return assert_clean("\n".join(lines))


def backtest_report(result: dict, manifest: dict) -> str:
    m = result["metrics"]
    b = result["benchmark_metrics"]
    a = result["assumptions"]
    lines = [
        f"# Backtest Report — {result['strategy']}",
        "",
        f"- Artifact: `{manifest['artifact_id']}` · created {manifest['created_at'][:10]}",
        f"- Symbols: {', '.join(result['symbols'])}",
        f"- Period: {result['dates'][0]} → {result['dates'][-1]} ({len(result['dates'])-1} trading days)",  # noqa: E501
        "",
        "## Assumptions (explicit)",
        "",
        f"- Fees: {a['fees_bps']} bps per trade · Slippage: {a['slippage_bps']} bps",
        f"- Start value: {a['start_value']} · Trades executed: {result['trades']} "
        f"(turnover {result['turnover']:,.0f})",
        "",
        "## Results",
        "",
        "| Metric | Strategy | Benchmark (equal-weight B&H) |",
        "|---|---|---|",
        f"| Total return | {m['total_return_pct']}% | {b['total_return_pct']}% |",
        f"| CAGR | {m['cagr_pct']}% | {b['cagr_pct']}% |",
        f"| Volatility | {m['volatility_pct']}% | {b['volatility_pct']}% |",
        f"| Max drawdown | {m['max_drawdown_pct']}% | {b['max_drawdown_pct']}% |",
        f"| Sharpe | {m['sharpe']} | {b['sharpe']} |",
        f"| Sortino | {m['sortino']} | {b['sortino']} |",
        f"| Calmar | {m['calmar']} | {b['calmar']} |",
        "",
        "## Methodology",
        "",
        "- Daily closes, aligned on common dates across symbols.",
        "- Trades executed at same-day close with configured fees/slippage.",
        "- Benchmark: equal-weight buy-and-hold index of the same symbols.",
        "- Annualization: 252 trading days on daily returns.",
        "",
        "## Limitations",
        "",
        "- Single realized price path; no regime or tail modeling beyond the sample.",
        "- Possible survivorship bias if delisted instruments are absent from data.",
        "- Same-day close execution understates real-world friction.",
        "",
        "## Data lineage",
        "",
        f"```json\n{load_json(manifest['data_snapshot'])}\n```",
        "",
        "---",
        "",
        RESEARCH_DISCLAIMER,
        "",
    ]
    return assert_clean("\n".join(lines))


def scenario_report(result_summary: dict, manifest: dict) -> str:
    s = result_summary
    lines = (
        [
            f"# Scenario Report — {s['method']}",
            "",
            f"- Artifact: `{manifest['artifact_id']}` · seed: `{manifest['seed']}`",
            f"- Runs: **{s['runs']}** · Horizon: **{s['horizon_days']} trading days (~1y)**",
            "",
            "## Distribution of terminal values (start = 1.00)",
            "",
            "| Percentile | Terminal value |",
            "|---|---|",
            f"| P05 | {s['p05']} |",
            f"| P25 | {s['p25']} |",
            f"| Median | {s['median']} |",
            f"| P75 | {s['p75']} |",
            f"| P95 | {s['p95']} |",
            "",
            f"- Probability of loss (end < start): **{s['prob_loss_pct']}%**",
            "",
            "## Methodology",
            "",
            "- Resampling from the historical daily-return distribution of the input series.",
            "- Seeded RNG — the run is reproducible given identical inputs.",
            "",
            "## Limitations",
            "",
        ]
        + [f"- {lim}" for lim in s.get("limitations", [])]
        + [
            "",
            "---",
            "",
            SCENARIO_DISCLAIMER,
            "",
            RESEARCH_DISCLAIMER,
            "",
        ]
    )
    return assert_clean("\n".join(lines))
