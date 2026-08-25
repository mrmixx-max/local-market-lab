"""Unit tests for pure technical indicator functions."""

import pytest

from packages.marketdata.indicators import bollinger, ema, macd, rsi, sma


class TestSMA:
    def test_basic(self):
        result = sma([1, 2, 3, 4, 5], period=3)
        assert result["indicator"] == "sma"
        assert result["period"] == 3
        assert result["values"] == [None, None, 2.0, 3.0, 4.0]

    def test_period_1_equals_input(self):
        data = [10.0, 20.0, 30.0]
        result = sma(data, period=1)
        assert result["values"] == data

    def test_invalid_period_zero(self):
        with pytest.raises(ValueError, match="positive integer"):
            sma([1, 2, 3], period=0)

    def test_invalid_period_float(self):
        with pytest.raises(ValueError, match="positive integer"):
            sma([1, 2, 3], period=2.5)

    def test_too_short(self):
        with pytest.raises(ValueError, match=">= 3"):
            sma([1, 2], period=3)

    def test_nan_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            sma([1, 2, float("nan")], period=3)

    def test_inf_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            sma([1, 2, float("inf")], period=3)


class TestEMA:
    def test_basic(self):
        result = ema([1, 2, 3, 4, 5], period=3)
        assert result["indicator"] == "ema"
        assert result["values"][0] is None
        assert result["values"][1] is None
        # seed = SMA of first 3 = 2.0
        assert result["values"][2] == 2.0

    def test_invalid_period(self):
        with pytest.raises(ValueError, match="positive integer"):
            ema([1, 2, 3], period=-1)

    def test_too_short(self):
        with pytest.raises(ValueError, match=">= 5"):
            ema([1, 2, 3, 4], period=5)


class TestRSI:
    def test_all_up(self):
        # monotonically increasing -> RSI should be 100
        data = list(range(1, 21))
        result = rsi(data, period=14)
        assert result["indicator"] == "rsi"
        assert result["values"][-1] == 100.0

    def test_all_down(self):
        data = list(range(20, 0, -1))
        result = rsi(data, period=14)
        assert result["values"][-1] == 0.0

    def test_length(self):
        data = list(range(1, 21))
        result = rsi(data, period=14)
        assert len(result["values"]) == len(data)

    def test_invalid_period(self):
        with pytest.raises(ValueError, match="positive integer"):
            rsi(list(range(20)), period=0)

    def test_too_short(self):
        with pytest.raises(ValueError, match=">= 15"):
            rsi(list(range(14)), period=14)


class TestMACD:
    def test_structure(self):
        data = [100 + i * 0.5 + (i % 3) for i in range(50)]
        result = macd(data, fast=12, slow=26, signal=9)
        assert result["indicator"] == "macd"
        assert "macd" in result["values"]
        assert "signal" in result["values"]
        assert "histogram" in result["values"]
        assert len(result["values"]["macd"]) == len(data)

    def test_fast_ge_slow_rejected(self):
        with pytest.raises(ValueError, match="fast must be < slow"):
            macd(list(range(50)), fast=26, slow=12)

    def test_invalid_params(self):
        with pytest.raises(ValueError, match="positive integers"):
            macd(list(range(50)), fast=0, slow=26, signal=9)


class TestBollinger:
    def test_structure(self):
        data = [100.0 + i * 0.1 for i in range(30)]
        result = bollinger(data, period=20, std_dev=2.0)
        assert result["indicator"] == "bollinger"
        assert "middle" in result["values"]
        assert "upper" in result["values"]
        assert "lower" in result["values"]
        assert len(result["values"]["middle"]) == len(data)

    def test_upper_ge_middle(self):
        data = [100.0 + i * 0.1 for i in range(30)]
        result = bollinger(data, period=20, std_dev=2.0)
        vals = result["values"]
        for u, m in zip(vals["upper"], vals["middle"]):
            if u is not None and m is not None:
                assert u >= m

    def test_lower_le_middle(self):
        data = [100.0 + i * 0.1 for i in range(30)]
        result = bollinger(data, period=20, std_dev=2.0)
        vals = result["values"]
        for lo, mid in zip(vals["lower"], vals["middle"]):
            if lo is not None and mid is not None:
                assert lo <= mid

    def test_invalid_period(self):
        with pytest.raises(ValueError, match=">= 2"):
            bollinger(list(range(30)), period=1)

    def test_invalid_std(self):
        with pytest.raises(ValueError, match="positive"):
            bollinger(list(range(30)), period=20, std_dev=-1.0)
