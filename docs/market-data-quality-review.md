# Market Data Quality Review — Local Market Lab v0.9.0

**Audit:** 2026-08-24 · Agent 2 (Marktdaten & Datenqualität)  
**Scope:** Yahoo/Alpha Vantage Adapter, SQLite Cache, Quality Layer, FX Policy  
**Method:** Static code review + test coverage analysis

---

## Executive Summary

| Component | Status | Score |
|-----------|--------|-------|
| Yahoo Adapter | 🟡 WARN | 6.5/10 |
| Alpha Vantage Adapter | 🟡 WARN | 7.0/10 |
| SQLite Cache | 🟡 WARN | 6.0/10 |
| Quality Checks | 🟢 PASS | 8.0/10 |
| FX Policy | 🟢 PASS | 8.5/10 |
| Series/Alignment | 🟡 WARN | 6.5/10 |
| Domain Entities | 🟢 PASS | 8.0/10 |
| **Overall** | **🟡 WARN** | **7.0/10** |

---

## 1. Yahoo Adapter (`packages/marketdata/yahoo_adapter.py`)

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| Y-01 | 🔴 HIGH | **Currency detection hardcoded to USD** — `_detect_currency()` always returns `"USD"` regardless of actual instrument currency (line 104). Silent data corruption for non-US stocks (e.g., `IWDA.AS` is USD-denominated by Yahoo but `VOLV.B` is SEK). | FAIL |
| Y-02 | 🟡 MED | **No symbol validation** — accepts any string without format checking. Invalid symbols fail only at network time with unclear errors. | WARN |
| Y-03 | 🟡 MED | **No retry/backoff** — `_download()` has zero retry logic. Transient network failures crash the caller. | WARN |
| Y-04 | 🟡 MED | **Adjusted prices not documented** — uses `auto_adjust=True` (line 87) but no flag on PriceSeries indicates adjusted vs unadjusted. | WARN |
| Y-05 | 🟢 LOW | **Timezone stripping** — `idx.date()` converts pandas Timestamp to naive date. Correct for daily data but undocumented. | INFO |
| Y-06 | 🟡 MED | **Volume type mismatch** — `int(row["Volume"])` could fail on NaN (pandas returns float NaN for missing). No `pd.notna()` guard. | WARN |
| Y-07 | 🟢 LOW | **No offline introspection** — no way to see what symbols are cached without attempting fetch. | INFO |

### Stille Korrekturen
- `auto_adjust=True` ändert historische Prices retroaktiv bei Splits/Dividenden — **keine Warnung für den Nutzer**, dass Prices adjusted sind.
- `_from_cached()` hardcoded `"USD"` (line 111) — Original-Währung geht bei Cache-Hit verloren.

### Tests
- ✅ Offline-Modus mit Cache wird testetest_marketdata.py:121-138)
- ✅ Import-Fehler ohne yfinance
- ❌ Kein Retry-Verhalten testbar
- ❌ Keine Currency-Mismatch-Detektion

**Verdict: 🟡 WARN**

---

## 2. Alpha Vantage Adapter (`packages/marketdata/alpha_vantage_adapter.py`)

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| A-01 | 🟢 GOOD | **Exponential backoff on 429** — `_request_with_retry()` with `RETRY_BASE_DELAY * (2 ** attempt)` (lines 118-122). | PASS |
| A-02 | 🔴 HIGH | **Currency hardcoded to USD** — line 78 always sets `"USD"`. Same issue as Yahoo. | FAIL |
| A-03 | 🟡 MED | **No symbol validation** — same as Yahoo. | WARN |
| A-04 | 🟡 MED | **Missing key check is good but late** — raises in `__init__`, but `_from_cached()` also hardcodes USD. | WARN |
| A-05 | 🟡 MED | **No jitter on retry** — fixed exponential delay susceptible to thundering herd. | WARN |
| A-06 | 🟡 MED | **API key exposed in URL** — `apikey={self.api_key}` in query string (line 84). Logged by proxies. | WARN |
| A-07 | 🟢 LOW | **Only daily data** — no intraday support unlike Yahoo. | INFO |
| A-08 | 🟡 MED | **No adjusted flag** — uses `"5. adjusted close"` (line 96) but no metadata that this is split-adjusted. | WARN |

### Unterschied zu Yahoo
- Alpha Vantage verwendet **TIME_SERIES_DAILY_ADJUSTED** → adjusted close
- Yahoo verwendet **auto_adjust=True** → ebenfalls adjusted
- **Kein Consistency-Check** zwischen den Sources möglich (gleiches Symbol, unterschiedliche adjusted values)

### Tests
- ✅ Rate-Limit-Fehler wird geworfen
- ✅ Fehlender API Key wird erkannt
- ✅ Offline-Modus
- ❌ Retry-Backoff nicht gemockt/verifiziert
- ❌ Currency hardcoded nicht getestet

**Verdict: 🟡 WARN**

---

## 3. SQLite Cache (`packages/marketdata/cache.py`)

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| C-01 | 🔴 HIGH | **No cache versioning** — kein Schema-Versionierung. Format-Änderungen (neue Felder in bars) führen zu stillen Cache-Korruptionen. | FAIL |
| C-02 | 🟡 MED | **No WAL mode** — `sqlite3.connect()` ohne `PRAGMA journal_mode=WAL`. Concurrent reads block writes. | WARN |
| C-03 | 🟡 MED | **Corruption crashes** — `json.loads()` in `get()`/`get_offline()` wirft bei korrupten Daten uncaught `JSONDecodeError`. Test bestätigt das (test_cache_behavior.py:126). | WARN |
| C-04 | 🟡 MED | **No size limits** — Cache kann unbegrenzt wachsen. TTL löscht nicht automatisch. | WARN |
| C-05 | 🟢 GOOD | **Offline fallback** — `get_offline()` returns expired entries (line 91-96). | PASS |
| C-06 | 🟢 GOOD | **Quality status stored** — `quality_status` column für Cache-Invalidierung bei Quality-Fehlern. | PASS |
| C-07 | 🟡 MED | **No cache introspection** — `stats()` zeigt nur counts. Keine Liste der gecachten Symbole. | WARN |
| C-08 | 🟢 LOW | **Key format** — `source:SYMBOL:interval`. Gut für Uniqueness, aber ohne Versionierung. | INFO |

### Cache-Probleme im Detail

**C-01: Missing Schema Version:**
```python
# Aktuell: kein Versions-Check
# Risiko: Code-Update ändert bar-Format, alter Cache hat alte Keys
# Lösung: schema_version in DB, Auto-Migration oder Invalidierung
```

**C-03: Corruption Handling:**
```python
# Zeile 77: json.loads(row["data"]) — crashed bei korrupten Daten
# Sollte sein: try/except mit graceful None + invalidation
```

### Tests
- ✅ TTL-Expiry
- ✅ Offline-Fallback
- ✅ Invalidation
- ❌ Kein Test für JSON-Corruption Recovery
- ❌ Kein Test für concurrent access
- ❌ Kein Test für cache size limits

**Verdict: 🟡 WARN**

---

## 4. Quality Checks (`packages/quality/checks.py`)

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| Q-01 | 🟢 GOOD | **Comprehensive coverage** — missing data, splits, FX, timestamps, outliers. | PASS |
| Q-02 | 🟢 GOOD | **Weekend-aware gaps** — `check_missing_data()` zählt nur Business-Days (line 46-48). | PASS |
| Q-03 | 🟢 GOOD | **No silent fixes** — Issues reported, never interpolated. | PASS |
| Q-04 | 🟢 GOOD | **Score calculation** — transparente Penalties für verschiedene Issue-Typen. | PASS |
| Q-05 | 🟡 MED | **No adjusted-price verification** — kein Check ob Prices adjusted vs raw sind. | WARN |
| Q-06 | 🟢 GOOD | **Stale check uses UTC** — `datetime.now(timezone.utc).date()` korrekt. | PASS |
| Q-07 | 🟡 MED | **Non-monotonic check buggy** — line 97: `if prev and d <= prev and dupes == 0` — dupes==0 check means duplicate detection disables ordering check if ANY duplicate was already found. | WARN |
| Q-08 | 🟢 LOW | **Outlier threshold** — z_threshold=4.0 is conservative (good for financial data). | INFO |

### Q-07 Bug Detail:
```python
# Zeile 97: Logik-Fehler
if prev and d <= prev and dupes == 0:
    issues.append(f"non-monotonic: ...")
# Problem: dupes wird für GESAMTE Series gezählt
# Wenn 1 Duplicate gefunden → dupes > 0 → ordering check komplett deaktiviert
```

### Tests
- ✅ Alle individuellen Checks getestet
- ✅ Composite Report
- ✅ Edge cases (weekends, gaps, duplicates, outliers)
- ❌ Non-monotonic check Bug nicht getestet
- ❌ Adjusted vs unadjusted nicht geprüft

**Verdict: 🟢 PASS**

---

## 5. FX Policy (`packages/marketdata/fx.py`)

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| F-01 | 🟢 GOOD | **No silent 1:1** — `convert()` returns None for unknown rates. | PASS |
| F-02 | 🟢 GOOD | **Explicit error on require** — `require()` raises KeyError with helpful message. | PASS |
| F-03 | 🟢 GOOD | **Positive rate validation** — `set_rate()` rejects zero/negative (line 21-23). | PASS |
| F-04 | 🟡 MED | **No historical FX** — `date_iso` parameter accepted but ignored. No time-varying rates. | WARN |
| F-05 | 🟢 LOW | **Case insensitive** — currencies normalized to uppercase. | PASS |

### Tests
- ✅ Missing rates return None
- ✅ require() raises KeyError
- ✅ Zero/negative rates rejected
- ✅ Multi-currency scenarios
- ✅ Integration with portfolio engine

**Verdict: 🟢 PASS**

---

## 6. Series & Alignment (`packages/marketdata/series.py`)

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| S-01 | 🟡 MED | **aligned_closes silently drops dates** — dates not in ALL series are excluded without warning. Could hide data availability issues. | WARN |
| S-02 | 🟡 MED | **No timezone on dates** — all dates are naive ISO strings. Ambiguous for international markets. | WARN |
| S-03 | 🟢 GOOD | **MissingPriceError explicit** — clear error when symbol has no data (line 19-22). | PASS |
| S-04 | 🟢 LOW | **series_quality descriptive** — reports gaps without interpolation. | PASS |

### Tests
- ✅ MissingPriceError raised
- ✅ series_quality reports gaps
- ❌ aligned_closes keine Warnung bei dropped dates

**Verdict: 🟡 WARN**

---

## 7. Domain Entities (`packages/domain/entities.py`)

### Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| D-01 | 🟢 GOOD | **Instrument validates uppercase** — `__post_init__` enforces uppercase symbol (line 41-42). | PASS |
| D-02 | 🟢 GOOD | **QualityReport embedded** — structured format with all relevant fields. | PASS |
| D-03 | 🟡 MED | **PriceBar volume type** — `volume: float | None` but adapters cast to `int`. Type inconsistency. | WARN |
| D-04 | 🟢 GOOD | **Transaction validation** — non-negative quantity/price/fees enforced. | PASS |

### Tests
- ✅ PriceBar.to_ohlcv() format
- ✅ Instrument validation
- ✅ QualityReport.to_dict()

**Verdict: 🟢 PASS**

---

## 8. Adapter Inconsistency (Yahoo vs Alpha Vantage vs adapters.py)

### Duplicate Implementation Problem

Es existieren **TWO** YahooAdapter/AlphaVantageAdapter Implementationen:

| File | Yahoo | Alpha Vantage |
|------|-------|---------------|
| `packages/marketdata/yahoo_adapter.py` | ✅ Mit Cache-Integration | ❌ Nicht vorhanden (separate Datei) |
| `packages/marketdata/alpha_vantage_adapter.py` | ❌ Nicht vorhanden | ✅ Mit Retry/Backoff |
| `packages/marketdata/adapters.py` | ✅ Ohne Cache, mit FetchResult | ✅ Ohne Retry, mit FetchResult |

**Probleme:**
1. **Inkonsistente Features:**
   - `yahoo_adapter.py` hat Cache-Integration
   - `adapters.py` Yahoo hat `FetchResult` aber KEIN Cache
   - `alpha_vantage_adapter.py` hat Retry/Backoff
   - `adapters.py` Alpha Vantage hat KEIN Retry

2. **Unterschiedliche Currency-Handhabung:**
   - `yahoo_adapter.py` → hardcoded USD
   - `adapters.py` → hardcoded EUR (Zeile 100, 138)
   - `alpha_vantage_adapter.py` → hardcoded USD

3. **Verschiedene Interfaces:**
   - `yahoo_adapter.py` gibt `PriceSeries` zurück
   - `adapters.py` gibt `FetchResult` (PriceSeries + DataSource) zurück

**Empfehlung:** Vereinheitlichung. Eine Adapter-Implementierung mit Cache + Retry + FetchResult.

---

## 9. Kritische Lücken (Prioritized)

### 🔴 P0 — Sofort beheben

1. **Cache-Versionierung fehlt** → Stille Corruption bei Updates
   - Fix: `schema_version` Tabelle, Auto-Invalidierung bei Versions-Mismatch

2. **Currency Detection korrupt** → Non-US-Werte werden als USD gespeichert
   - Fix: Currency vom Adapter mitliefern (aus ticker.info oder symbol-suffix)

3. **Adapter-Duplikate** → Inkonsistentes Verhalten je nach Import-Pfad
   - Fix: Eine Implementierung, gemeinsame Basisklasse

### 🟡 P1 — Kurzfristig

4. **Retry/Backoff nur bei Alpha Vantage** → Yahoo crash bei transienten Fehlern
5. **Non-monotonic check Bug** → Dupes deaktivieren ordering check
6. **Cache-Corruption Crash** → `json.loads` ohne try/except
7. **adjusted flag fehlt** → Keine Unterscheidung adjusted/unadjusted

### 🟢 P2 — Mittelfristig

8. **API Key in URL** → Sollte in Header oder POST body
9. **Cache Size Limits** → TTL löscht nicht, `stats()` zeigt kein Wachstum
10. **Historical FX** → `date_iso` parameter unused
11. **Symbol Validation** → Format-Check vor Netzwerk-Call

---

## 10. Test Coverage Matrix

| Feature | Unit Test | Integration Test | Missing |
|---------|-----------|------------------|---------|
| Cache TTL | ✅ | ✅ | |
| Cache Offline | ✅ | ✅ | |
| Cache Corruption | ✅ (acknowledged) | | Recovery logic |
| Cache Versioning | | | ❌ No test |
| Quality Missing Data | ✅ | ✅ | |
| Quality Splits | ✅ | ✅ | |
| Quality FX | ✅ | ✅ | |
| Quality Timestamps | ✅ | ✅ | |
| FX Policy | ✅ | ✅ | |
| Yahoo Offline | ✅ | | Network retry |
| AV Retry/Backoff | | | ❌ No test |
| Symbol Validation | | | ❌ No test |
| Adjusted Prices | | | ❌ No test |
| Aligned Closes | | | ⚠️ Partial |

---

## Zusammenfassung

**Stärken:**
- FX-Policy: Explizite Fehler, kein silent 1:1
- Quality Checks: Gut deckend, weekend-aware, score-based
- Cache-Design: Offline-Fallback, quality-status tracking
- Test Coverage: Solide Basis für Cache/Quality/FX

**Schwächen:**
- Currency Detection: Hardcoded, silently wrong
- Cache: Keine Versionierung, keine Größenbegrenzung
- Adapter-Duplikate: Zwei Implementationen mit verschiedenen Features
- Retry: Nur bei Alpha Vantage
- Adjusted Prices: Nicht dokumentiert/flagged

**Nächste Schritte:**
1. Cache-Versionierung implementieren
2-3. Adapter-Duplikate zusammenführen, Currency Detection reparieren
4. Retry/Backoff vereinheitlichen
5. adjusted/unadjusted Flag auf PriceSeries
