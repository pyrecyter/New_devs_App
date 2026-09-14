from decimal import Decimal

import pytest

from app.services.reservations import format_money, quantize_money


def test_sub_cent_seed_split_quantizes_to_exact_dollars():
    total = Decimal("333.333") + Decimal("333.333") + Decimal("333.334")
    assert total == Decimal("1000.000")
    assert format_money(total) == "1000.00"


def test_timezone_boundary_amount_keeps_two_decimals():
    assert format_money(Decimal("2250.000")) == "2250.00"
    assert format_money(Decimal("1250.000")) == "1250.00"


def test_quantize_rejects_float_input():
    with pytest.raises(TypeError):
        quantize_money(1000.00)


def test_none_and_zero_format_consistently():
    assert format_money(None) == "0.00"
    assert format_money(Decimal("0")) == "0.00"
