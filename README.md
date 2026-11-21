# FXRateLedger

FXRateLedger is a GenLayer Intelligent Contract that records a dated reference exchange rate for a selected currency pair.

It stores the source data on-chain. It is not a live trading or payment service.

## How it works

1. The caller provides a base currency, quote currency, and requested date.
2. The contract retrieves the rate from the Frankfurter API.
3. Independent evaluations compare the currencies, dates, and normalized rate.
4. The contract stores the result, source URL, and response SHA-256 on-chain.

## Possible results

- `RECORDED`: A rate was found and stored.
- `NO_RATE`: The source did not return a rate for the selected pair and date.
- `SOURCE_UNAVAILABLE`: The API could not be reached.
- `UNCLEAR`: The response could not be reliably interpreted.

## Contract interface

### `record_rate(base_currency, quote_currency, requested_date)`

Fetches and stores a rate. The function returns the record ID.

Example inputs:

    base_currency: EUR
    quote_currency: USD
    requested_date: 2025-01-02

### `get_record(record_id)`

Returns the stored record as a JSON string.

### `get_record_count()`

Returns the number of stored records.

## Data source

Frankfurter API:

`https://api.frankfurter.app/{date}?from={base_currency}&to={quote_currency}`

Frankfurter provides dated reference rates. Rates may not be available for every currency or date.

## Deployment and live check

- Contract address: [`0x0f3036e844425E034bf74270F91d37B79cA24527`](https://explorer-studio.genlayer.com/address/0x0f3036e844425E034bf74270F91d37B79cA24527)
- Deployment transaction: [`0xebfd1e893bdcaf89d80b61cd6e5ed2268e472aa50eca42b81ed0ec7d92d5ea6a`](https://explorer-studio.genlayer.com/tx/0xebfd1e893bdcaf89d80b61cd6e5ed2268e472aa50eca42b81ed0ec7d92d5ea6a)
- Live rate transaction: [`0x017d11aedfa80c4f7f7aa4671e90ca7b1686ef7216e5c137dc22ca6b39a26afe`](https://explorer-studio.genlayer.com/tx/0x017d11aedfa80c4f7f7aa4671e90ca7b1686ef7216e5c137dc22ca6b39a26afe)

The live example recorded a rate of `1.0321` for `EUR` to `USD` on `2025-01-02`. The record ID is `0`, and its source response SHA-256 is `194c38362924571d5ef104b75c76a3413452437a427a8627c7e85d46416b7884`.

## Run local tests

    python -m pip install -r requirements-dev.txt
    python -m pytest -q

## Disclaimer

This is a dated reference exchange rate, not a live trading quote. This project is informational and is not financial advice.
