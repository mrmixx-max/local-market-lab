"""Compliance: disclaimers and language guard.

The language guard blocks signal/advice phrasing in reports — per concept
this is a product feature, not a footnote.
"""

from __future__ import annotations

import re

RESEARCH_DISCLAIMER = (
    "Local Market Lab is a research and analysis tool. It does not provide "
    "investment advice, trading signals, or recommendations to buy or sell any "
    "financial instrument. Historical results and simulations are not reliable "
    "indicators of future performance. All outputs depend on data quality, "
    "model assumptions, and user configuration."
)

SCENARIO_DISCLAIMER = (
    "Scenario outputs are sensitivity explorations under explicit assumptions. "
    "They are not forecasts. Percentile outcomes describe the simulated "
    "distribution, which is derived entirely from historical data."
)

WARN_PROFILES = {
    "research-only-v1": RESEARCH_DISCLAIMER,
    "crypto-risk-v1": RESEARCH_DISCLAIMER
    + " Crypto assets are highly volatile and can lose most or all of their value.",
}

# phrases that must never appear in generated output
BLOCKED_PATTERNS = [
    r"\bkaufsignal(e|en)?\b",
    r"\bverkaufssignal(e|en)?\b",
    r"\bbuy signal\b",
    r"\bsell signal\b",
    r"\bgarantiert(e|er|es)?\b",
    r"\bguaranteed?\b",
    r"\bsichere rendite\b",
    r"\bsafe return\b",
    r"\bbeste anlage\b",
    r"\bbest investment\b",
    r"\bempfehlung:\s*(kaufen|verkaufen)\b",
    r"\brecommend (buying|selling)\b",
]


def check_language(text: str) -> dict:
    """Scan report text for forbidden advice-like phrasing."""
    hits = []
    lowered = text.lower()
    for pat in BLOCKED_PATTERNS:
        for m in re.finditer(pat, lowered):
            hits.append({"phrase": m.group(0), "pattern": pat})
    return {"clean": not hits, "violations": hits}


def assert_clean(text: str) -> str:
    """Raise when the text violates the language guard; else return it."""
    result = check_language(text)
    if not result["clean"]:
        raise ValueError(f"language guard violation: {result['violations']}")
    return text
