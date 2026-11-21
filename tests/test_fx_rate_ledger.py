import importlib.util
import json
import sys
import types
from pathlib import Path


class _Decorators:
    @staticmethod
    def write(function):
        return function

    @staticmethod
    def view(function):
        return function


class _UserError(Exception):
    pass


_fake_genlayer = types.ModuleType("genlayer")
_fake_genlayer.gl = types.SimpleNamespace(
    Contract=object,
    public=_Decorators(),
    vm=types.SimpleNamespace(UserError=_UserError),
)
_fake_genlayer.u256 = int
_fake_genlayer.TreeMap = dict

_contract_path = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "fx_rate_ledger.py"
)

_previous_genlayer = sys.modules.get("genlayer")
sys.modules["genlayer"] = _fake_genlayer

try:
    _spec = importlib.util.spec_from_file_location(
        "fx_rate_ledger_under_test",
        _contract_path,
    )
    _contract = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_contract)
finally:
    if _previous_genlayer is None:
        sys.modules.pop("genlayer", None)
    else:
        sys.modules["genlayer"] = _previous_genlayer


def _rate_response(rate=1.0321, base="EUR", date="2025-01-02"):
    return json.dumps({
        "amount": 1.0,
        "base": base,
        "date": date,
        "rates": {"USD": rate},
    })


def test_clean_currency_trims_and_normalizes_case():
    assert _contract._clean_currency(" eur ", "Base currency") == "EUR"


def test_clean_currency_rejects_invalid_values():
    for value in ("EU", "EURO", "123", ""):
        try:
            _contract._clean_currency(value, "Base currency")
        except _UserError:
            pass
        else:
            raise AssertionError(f"Expected currency to be rejected: {value!r}")


def test_clean_date_accepts_valid_leap_day():
    assert _contract._clean_date("2024-02-29") == "2024-02-29"


def test_clean_date_rejects_invalid_dates():
    for value in ("2023-02-29", "2025-13-01", "2025-04-31", "2025/01/02"):
        try:
            _contract._clean_date(value)
        except _UserError:
            pass
        else:
            raise AssertionError(f"Expected date to be rejected: {value!r}")


def test_normalize_rate_formats_positive_rate():
    assert _contract._normalize_rate(1.0321) == "1.0321"
    assert _contract._normalize_rate(2) == "2"


def test_normalize_rate_rejects_invalid_values():
    for value in (0, -1, True, "1.2", None):
        assert _contract._normalize_rate(value) is None


def test_extract_rate_reads_valid_response():
    result = _contract._extract_rate(
        _rate_response(),
        "EUR",
        "USD",
        "2025-01-02",
    )

    assert result == {
        "status": "OK",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "requested_date": "2025-01-02",
        "effective_date": "2025-01-02",
        "rate": "1.0321",
    }


def test_extract_rate_reports_missing_quote_currency():
    payload = {
        "amount": 1.0,
        "base": "EUR",
        "date": "2025-01-02",
        "rates": {"GBP": 0.84},
    }

    result = _contract._extract_rate(
        json.dumps(payload),
        "EUR",
        "USD",
        "2025-01-02",
    )

    assert result == {
        "status": "NO_RATE",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "requested_date": "2025-01-02",
        "effective_date": "2025-01-02",
    }


def test_extract_rate_rejects_mismatched_base_currency():
    assert _contract._extract_rate(
        _rate_response(base="GBP"),
        "EUR",
        "USD",
        "2025-01-02",
    ) is None


def test_extract_rate_rejects_malformed_json():
    assert _contract._extract_rate(
        "{not valid json",
        "EUR",
        "USD",
        "2025-01-02",
    ) is None


def test_extract_rate_rejects_non_positive_rate():
    assert _contract._extract_rate(
        _rate_response(rate=-1),
        "EUR",
        "USD",
        "2025-01-02",
    ) is None


def test_extract_rate_rejects_oversized_response():
    assert _contract._extract_rate(
        "x" * 8001,
        "EUR",
        "USD",
        "2025-01-02",
    ) is None
