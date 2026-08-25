"""API tests for v1.0 P1.2 rebalancing order endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client(monkeypatch):
    import apps.api.main as api_main

    return TestClient(api_main.app)


def test_explicit_orders_below_minimum(monkeypatch):
    c = _client(monkeypatch)
    body = {
        "positions": {
            "A": {"quantity": 50, "price": 100.0},
            "B": {"quantity": 50, "price": 100.0},
        },
        "target_weights": {"A": 0.55, "B": 0.45},
        "cash": 0,
        "default_min_order_value": 1500.0,
    }
    r = c.post("/api/v1/rebalance/orders", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["orders_skipped_below_minimum"] >= 1
    assert any(p["below_minimum"] for p in d["proposals"])
    assert d["disclaimer"]


def test_explicit_orders_normal(monkeypatch):
    c = _client(monkeypatch)
    body = {
        "positions": {
            "A": {"quantity": 0, "price": 10.0},
            "B": {"quantity": 0, "price": 10.0},
        },
        "target_weights": {"A": 0.5, "B": 0.5},
        "cash": 2000,
        "default_min_order_value": 0.0,
    }
    r = c.post("/api/v1/rebalance/orders", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["cost_benefit_status"] in ("worthwhile", "marginal", "not_worthwhile")
    assert d["cash_after"] <= d["cash_before"] + 1e-6


def test_invalid_negative_min_returns_422(monkeypatch):
    c = _client(monkeypatch)
    body = {
        "positions": {"A": {"quantity": 10, "price": 10.0}},
        "target_weights": {"A": 1.0},
        "cash": 0,
        "default_min_order_value": -5.0,
    }
    r = c.post("/api/v1/rebalance/orders", json=body)
    assert r.status_code == 422


def test_missing_fields_400(monkeypatch):
    c = _client(monkeypatch)
    r = c.post(
        "/api/v1/rebalance/orders",
        json={"positions": {"A": {"quantity": 1, "price": 1}}},
    )
    assert r.status_code == 400


def test_reproducibility_via_api(monkeypatch):
    c = _client(monkeypatch)
    body = {
        "positions": {
            "A": {"quantity": 10, "price": 10.0},
            "B": {"quantity": 5, "price": 20.0},
        },
        "target_weights": {"A": 0.4, "B": 0.6},
        "cash": 500,
        "default_min_order_value": 0.0,
    }
    r1 = c.post("/api/v1/rebalance/orders", json=body).json()
    r2 = c.post("/api/v1/rebalance/orders", json=body).json()
    assert r1["run_id"] == r2["run_id"]
    assert r1["data_hash"] == r2["data_hash"]
