"""Shared adapter base — cache, retry, currency detection, FX policy.

Consolidates the duplicated logic from yahoo_adapter.py and
alpha_vantage_adapter.py:

- Cache key includes provider, symbol, interval, period, currency,
  adjusted-flag and CACHE_SCHEMA_VERSION. Old/incompatible entries are
  never silently reused.
- Currency is detected per-provider and attached to every series; a
  missing rate in the FxPolicy yields an explicit INCOMPLETE state —
  never a silent 1:1 conversion.
- Retry with exponential backoff on transient HTTP errors.

Provider-specific logic stays in the concrete adapters.
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request

from packages.domain.entities import PriceBar, PriceSeries
from packages.marketdata.cache import MarketDataCache

log = logging.getLogger(__name__)

#: Bump when the cached payload shape changes. Entries written under an
#: older schema version can never be returned to the caller.
CACHE_SCHEMA_VERSION = "2"

# Currencies quoted with symbol suffix on Yahoo (e.g. BTC-EUR -> EUR).
_SUFFIX_CURRENCIES = (
    "EUR",
    "USD",
    "GBP",
    "CHF",
    "JPY",
    "CAD",
    "AUD",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "CZK",
    "TRY",
)


def detect_currency(symbol: str) -> str:
    """Best-effort trading currency for a ticker symbol.

    Returns 'unknown' (never a guess presented as fact) when the symbol
    does not carry an explicit currency marker. Callers must treat the
    series as incomplete-currency and surface that in metadata.
    """
    s = symbol.upper()
    # explicit quote suffix: BTC-EUR, SAP.DE (Xetra = EUR), IWDA.AS (AMS = EUR)
    if "-" in s:
        tail = s.rsplit("-", 1)[1]
        if tail in _SUFFIX_CURRENCIES:
            return tail
    if s.endswith(".DE") or s.endswith(".AS") or s.endswith(".PA") or s.endswith(".MI"):
        return "EUR"
    if s.endswith(".L"):
        return "GBp"  # London quotes in pence
    if s.endswith(".SW"):
        return "CHF"
    if s.endswith(".T"):
        return "JPY"
    return "unknown"


class AdapterError(RuntimeError):
    """Raised when a provider fails after retries."""


class RateLimitError(AdapterError):
    """Provider rate limit hit and retries exhausted."""


class BaseAdapter:
    """Shared plumbing: versioned cache, retry/backoff, currency handling."""

    SOURCE_NAME: str = "unknown"
    DEFAULT_INTERVAL: str = "1d"
    #: Whether prices are split/dividend-adjusted by this provider.
    ADJUSTED_BY_DEFAULT: bool = True

    def __init__(
        self,
        cache: MarketDataCache | None = None,
        cache_path: str = "~/.local-market-lab/cache/market.db",
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
    ):
        self.cache = cache or MarketDataCache(cache_path)
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    # ---------- cache ----------

    def cache_key_parts(
        self,
        symbol: str,
        interval: str,
        currency: str,
        adjusted: bool,
        period: str = "",
    ) -> dict:
        return {
            "provider": self.SOURCE_NAME,
            "symbol": symbol.upper(),
            "interval": interval,
            "period": period or "default",
            "currency": currency.upper(),
            "adjusted": bool(adjusted),
            "schema": CACHE_SCHEMA_VERSION,
        }

    def _cache_get(self, parts: dict):
        """Return cached bars only when the full versioned key matches."""
        flat = "|".join(f"{k}={v}" for k, v in sorted(parts.items()))
        data = self.cache.get_versioned(flat)
        if data is not None:
            log.info("cache HIT %s", flat)
        else:
            log.info("cache MISS %s", flat)
        return data

    def _cache_put(self, parts: dict, bars: list[PriceBar]) -> None:
        flat = "|".join(f"{k}={v}" for k, v in sorted(parts.items()))
        self.cache.put_versioned(flat, [b.__dict__ for b in bars])

    # ---------- retry ----------

    def request_with_retry(
        self, url: str, headers: dict | None = None, timeout: int = 30
    ) -> bytes:
        """GET with exponential backoff. Raises RateLimitError/AdapterError."""
        hdrs = {"User-Agent": "LocalMarketLab/0.9.1"}
        if headers:
            hdrs.update(headers)
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 429:
                    delay = self.retry_base_delay * (2**attempt)
                    log.warning(
                        "rate limited, retry in %.0fs (%d/%d)",
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    time.sleep(delay)
                    continue
                raise AdapterError(f"provider HTTP error {exc.code}") from exc
            except urllib.error.URLError as exc:
                last_exc = exc
                delay = self.retry_base_delay * (2**attempt)
                log.warning(
                    "network error, retry in %.0fs (%d/%d)",
                    delay,
                    attempt + 1,
                    self.max_retries,
                )
                time.sleep(delay)
        raise RateLimitError(
            f"provider failed after {self.max_retries} attempts: {last_exc}"
        )

    # ---------- helpers ----------

    @staticmethod
    def bars_from_dicts(data: list[dict]) -> list[PriceBar]:
        return [PriceBar(d["date"], d["close"], d.get("volume")) for d in data]

    def make_series(
        self, symbol: str, bars: list[PriceBar], currency: str
    ) -> PriceSeries:
        """Build a PriceSeries; unknown currency stays 'unknown' — the
        FxPolicy will report it as INCOMPLETE at conversion time."""
        return PriceSeries(symbol.upper(), currency.upper(), bars).sorted()
