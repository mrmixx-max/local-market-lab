"""CSV importers — tolerant parsing, per-row error reports, provenance."""
from __future__ import annotations

import csv
from pathlib import Path

from packages.core.dates import parse_date


def _read_rows(path: str | Path) -> tuple[list[str], list[dict]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    with p.open(encoding="utf-8-sig", newline="") as f:
        sample = f.readline()
        delim = ";" if sample.count(";") > sample.count(",") else ","
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delim)
        return reader.fieldnames or [], list(reader)


def _pick(row: dict, candidates: list[str]) -> str | None:
    lowered = {k.strip().lower(): v for k, v in row.items()}
    for c in candidates:
        if c in lowered and lowered[c] not in (None, ""):
            return lowered[c]
    return None


def import_transactions(ws, path: str | Path, portfolio: str,
                        default_currency: str = "EUR") -> dict:
    """Import transactions CSV.

    Columns (any common alias): date/datum, symbol/ticker, type/art (buy|sell|
    dividend|fee|deposit|withdrawal), quantity/menge/stück, price/kurs, fees/gebühren.
    """
    _, rows = _read_rows(path)
    inserted, errors = 0, []
    TYPE_MAP = {"buy": "buy", "kauf": "buy", "sell": "sell", "verkauf": "sell",
                "dividend": "dividend", "dividende": "dividend",
                "fee": "fee", "gebühr": "fee", "gebuhr": "fee",
                "deposit": "deposit", "einzahlung": "deposit",
                "withdrawal": "withdrawal", "auszahlung": "withdrawal"}
    for i, row in enumerate(rows, start=2):
        try:
            raw_type = (_pick(row, ["type", "art", "typ"]) or "").strip().lower()
            txn_type = TYPE_MAP.get(raw_type)
            if txn_type is None:
                raise ValueError(f"unknown txn type {raw_type!r}")
            symbol = (_pick(row, ["symbol", "ticker"]) or "").strip().upper()
            if symbol == "" and txn_type in ("deposit", "withdrawal"):
                symbol = "CASH"          # pseudo-instrument for cash movements
            if not symbol:
                raise ValueError("missing symbol")
            ws.ensure_instrument(symbol, currency=default_currency)
            date_iso = parse_date(_pick(row, ["date", "datum"]))
            qty = float((_pick(row, ["quantity", "menge", "stück", "stueck"]) or "0").replace(",", "."))
            price = float((_pick(row, ["price", "kurs"]) or "0").replace(",", "."))
            fees_raw = _pick(row, ["fees", "gebühren", "gebuhren"])
            fees = float(fees_raw.replace(",", ".")) if fees_raw else 0.0
            if qty < 0 or price < 0:
                raise ValueError("negative quantity/price")
            ws.add_transaction({
                "portfolio": portfolio, "symbol": symbol, "txn_type": txn_type,
                "date": date_iso, "quantity": qty, "price": price,
                "fees": fees, "currency": default_currency, "note": "",
            })
            inserted += 1
        except Exception as exc:
            errors.append({"line": i, "error": str(exc), "raw": row})
    return {"file": str(path), "portfolio": portfolio,
            "inserted": inserted, "errors": errors}


def import_prices(ws, path: str | Path, symbol: str,
                  source: str = "user-csv") -> dict:
    """Import price CSV [date, close] (+ optional volume). Upsert semantics."""
    _, rows = _read_rows(path)
    if not ws.has_instrument(symbol):
        ws.ensure_instrument(symbol)
    upserted, skipped = 0, []
    for i, row in enumerate(rows, start=2):
        try:
            d = parse_date(_pick(row, ["date", "datum"]))
            close = float((_pick(row, ["close", "schluss", "preis"]) or "").replace(",", "."))
            vol_raw = _pick(row, ["volume", "volumen"])
            vol = float(vol_raw.replace(",", ".")) if vol_raw else None
            ws.upsert_price(symbol, d, close, vol, source=source)
            upserted += 1
        except Exception as exc:
            skipped.append({"line": i, "error": str(exc)})
    ws.commit_prices()
    return {"file": str(path), "symbol": symbol.upper(),
            "upserted": upserted, "skipped": len(skipped), "errors": skipped[:10]}


def import_corporate_actions(ws, path: str | Path) -> dict:
    """Import corporate actions CSV.

    Columns: symbol, action ('split'|'cash_dividend'), date,
             ratio (splits) OR amount_per_share (dividends).
    """
    from packages.domain.entities import CorporateAction
    _, rows = _read_rows(path)
    inserted, errors = 0, []
    for i, row in enumerate(rows, start=2):
        try:
            ca = CorporateAction(
                symbol=(_pick(row, ["symbol", "ticker"]) or "").strip().upper(),
                action=(_pick(row, ["action", "art"]) or "").strip().lower(),
                date=parse_date(_pick(row, ["date", "datum"])),
                ratio=float(r) if (r := (_pick(row, ["ratio"])) or "").replace(",", ".") else None,
                amount_per_share=float(a) if (a := (_pick(row, ["amount_per_share", "betrag"])) or "").replace(",", ".") else None,
                currency=(_pick(row, ["currency", "währung", "waehrung"]) or "EUR").strip().upper(),
            )
            ws.ensure_instrument(ca.symbol)
            ws.add_corporate_action({
                "symbol": ca.symbol, "action": ca.action, "date": ca.date,
                "ratio": ca.ratio, "amount_per_share": ca.amount_per_share,
                "currency": ca.currency,
            })
            inserted += 1
        except Exception as exc:
            errors.append({"line": i, "error": str(exc)})
    return {"file": str(path), "inserted": inserted, "errors": errors}
