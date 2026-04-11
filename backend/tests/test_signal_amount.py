"""
Tests für BRUNO-FIX-08: Signal Pipeline Sanity.
"""
import pytest
from app.services.composite_scorer import CompositeSignal


def test_to_signal_dict_amount_from_sizing():
    """to_signal_dict muss echte Position aus sizing übernehmen, nicht 0.0."""
    signal = CompositeSignal()
    signal.direction = "long"
    signal.composite_score = 35.0
    signal.price = 100_000.0
    signal.sizing = {
        "position_size_btc": 0.0085,
        "sizing_valid": True,
    }
    
    result = signal.to_signal_dict("BTCUSDT")
    
    assert result["amount"] == 0.0085, f"amount should be from sizing, got {result['amount']}"
    assert result["side"] == "buy"


def test_to_signal_dict_amount_zero_when_no_sizing():
    """Ohne sizing → amount = 0.0 (Sentinel für Drop)."""
    signal = CompositeSignal()
    signal.direction = "long"
    signal.composite_score = 35.0
    
    result = signal.to_signal_dict("BTCUSDT")
    assert result["amount"] == 0.0


def test_short_signal_amount():
    """Short signal: amount aus sizing, side='sell'."""
    signal = CompositeSignal()
    signal.direction = "short"
    signal.sizing = {"position_size_btc": 0.012, "sizing_valid": True}
    
    result = signal.to_signal_dict()
    assert result["amount"] == 0.012
    assert result["side"] == "sell"
