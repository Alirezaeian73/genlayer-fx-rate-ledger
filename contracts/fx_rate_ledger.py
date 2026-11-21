# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import hashlib
import json
import re


MAX_RESPONSE_LENGTH = 8000


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _clean_currency(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise gl.vm.UserError(field_name + " must be text")

    currency = value.strip().upper()
    if re.fullmatch(r"[A-Z]{3}", currency) is None:
        raise gl.vm.UserError(
            field_name + " must be a three-letter currency code, such as EUR"
        )
    return currency


def _clean_date(value: str) -> str:
    if not isinstance(value, str):
        raise gl.vm.UserError("Date must be text in YYYY-MM-DD format")

    date_text = value.strip()
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", date_text)
    if match is None:
        raise gl.vm.UserError("Use date format YYYY-MM-DD")

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    if year < 1999 or year > 2100 or month < 1 or month > 12:
        raise gl.vm.UserError("Date is outside the supported range")

    days_in_month = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    maximum_day = days_in_month[month - 1]
    leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    if month == 2 and leap_year:
        maximum_day = 29
    if day < 1 or day > maximum_day:
        raise gl.vm.UserError("Date is not a valid calendar date")

    return date_text


def _normalize_rate(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None

    rate_text = format(float(value), ".15f").rstrip("0").rstrip(".")
    if not rate_text:
        return None
    return rate_text


def _extract_rate(
    payload_text: str,
    base_currency: str,
    quote_currency: str,
    requested_date: str,
):
    if (
        not isinstance(payload_text, str)
        or not payload_text.strip()
        or len(payload_text) > MAX_RESPONSE_LENGTH
    ):
        return None

    try:
        payload = json.loads(payload_text)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    returned_base = payload.get("base")
    effective_date = payload.get("date")
    rates = payload.get("rates")

    if returned_base != base_currency:
        return None
    if not isinstance(effective_date, str):
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", effective_date) is None:
        return None
    if not isinstance(rates, dict):
        return None

    if quote_currency not in rates:
        return {
            "status": "NO_RATE",
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "requested_date": requested_date,
            "effective_date": effective_date,
        }

    rate_text = _normalize_rate(rates.get(quote_currency))
    if rate_text is None:
        return None

    return {
        "status": "OK",
        "base_currency": base_currency,
        "quote_currency": quote_currency,
        "requested_date": requested_date,
        "effective_date": effective_date,
        "rate": rate_text,
    }


class FXRateLedger(gl.Contract):
    record_count: u256
    records: TreeMap[u256, str]

    def __init__(self):
        self.record_count = 0
        self.records = TreeMap()

    @gl.public.write
    def record_rate(
        self,
        base_currency: str,
        quote_currency: str,
        requested_date: str,
    ) -> u256:
        base_currency = _clean_currency(base_currency, "Base currency")
        quote_currency = _clean_currency(quote_currency, "Quote currency")
        requested_date = _clean_date(requested_date)

        if base_currency == quote_currency:
            raise gl.vm.UserError("Choose two different currencies")

        source_url = (
            "https://api.frankfurter.app/"
            + requested_date
            + "?from="
            + base_currency
            + "&to="
            + quote_currency
        )

        def evaluate_source() -> str:
            try:
                response = gl.nondet.web.get(source_url)
                response_text = response.body.decode("utf-8")
            except Exception:
                return _json({"status": "SOURCE_UNAVAILABLE"})

            result = _extract_rate(
                response_text,
                base_currency,
                quote_currency,
                requested_date,
            )
            if result is None:
                return _json({"status": "EXTRACTION_UNCLEAR"})

            if result.get("status") == "OK":
                result["source_sha256"] = hashlib.sha256(
                    response_text.encode("utf-8")
                ).hexdigest()

            return _json(result)

        principle = (
            "Independently inspect the returned Frankfurter JSON. Both results must "
            "agree on status. For status OK, require exact agreement on base currency, "
            "quote currency, requested date, effective date, and normalized rate. "
            "For NO_RATE, require agreement on both currencies, requested date, and "
            "effective date. Ignore source hash differences only when all required "
            "rate facts agree. Do not infer or invent a rate."
        )

        consensus_output = gl.eq_principle.prompt_comparative(
            evaluate_source,
            principle=principle,
        )

        try:
            if isinstance(consensus_output, str):
                observed = json.loads(consensus_output)
            elif isinstance(consensus_output, dict):
                observed = consensus_output
            else:
                observed = {"status": "EXTRACTION_UNCLEAR"}
        except Exception:
            observed = {"status": "EXTRACTION_UNCLEAR"}

        status = "UNCLEAR"
        effective_date = ""
        rate = ""
        source_sha256 = ""

        if isinstance(observed, dict):
            observed_status = observed.get("status")

            if observed_status == "SOURCE_UNAVAILABLE":
                status = "SOURCE_UNAVAILABLE"

            elif (
                observed_status == "NO_RATE"
                and observed.get("base_currency") == base_currency
                and observed.get("quote_currency") == quote_currency
                and observed.get("requested_date") == requested_date
            ):
                status = "NO_RATE"
                effective_date = observed.get("effective_date", "")

            elif (
                observed_status == "OK"
                and observed.get("base_currency") == base_currency
                and observed.get("quote_currency") == quote_currency
                and observed.get("requested_date") == requested_date
                and isinstance(observed.get("effective_date"), str)
            ):
                observed_rate = observed.get("rate")
                if (
                    isinstance(observed_rate, str)
                    and re.fullmatch(r"\d+(?:\.\d+)?", observed_rate)
                    is not None
                    and float(observed_rate) > 0
                ):
                    status = "RECORDED"
                    effective_date = observed.get("effective_date", "")
                    rate = observed_rate
                    source_sha256 = observed.get("source_sha256", "")

        record_id = self.record_count
        record = {
            "id": int(record_id),
            "status": status,
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "requested_date": requested_date,
            "effective_date": effective_date,
            "rate": rate,
            "source_name": "Frankfurter",
            "source_url": source_url,
            "source_sha256": source_sha256,
            "notice": (
                "This is a dated reference exchange rate, not a live trading quote. "
                "Frankfurter data may not cover every currency or date. This record "
                "is informational and is not financial advice."
            ),
        }

        self.records[record_id] = _json(record)
        self.record_count += 1
        return record_id

    @gl.public.view
    def get_record(self, record_id: u256) -> str:
        return self.records.get(record_id, "")

    @gl.public.view
    def get_record_count(self) -> u256:
        return self.record_count
