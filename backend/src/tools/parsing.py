"""Parsing tools for fund data ingestion."""

import csv
import io
import json
import re

from src.api.models.ingest import FundInput, Holding
from src.data.stub_holdings import STUB_HOLDINGS


def parse_symbols(symbols: list[str]) -> tuple[list[FundInput], list[str]]:
    """Parse fund symbols and return fund data from stub holdings.

    Returns:
        Tuple of (funds, warnings)
    """
    funds: list[FundInput] = []
    warnings: list[str] = []

    for symbol in symbols:
        clean = symbol.strip().upper()
        if not clean:
            continue

        if clean in STUB_HOLDINGS:
            holdings = [
                Holding(ticker=ticker, weight=weight)
                for ticker, weight in STUB_HOLDINGS[clean].items()
            ]
            funds.append(FundInput(symbol=clean, holdings=holdings))
        else:
            funds.append(FundInput(symbol=clean, holdings=[]))
            warnings.append(f"No holdings data available for {clean}")

    return funds, warnings


def parse_paste(text: str) -> tuple[list[FundInput], list[str]]:
    """Parse pasted text containing fund symbols (one per line or comma-separated).

    Supports formats:
    - One symbol per line
    - Comma-separated symbols
    - Tab-separated symbols

    Returns:
        Tuple of (funds, warnings)
    """
    symbols: list[str] = []

    # Split by newlines first, then by commas/tabs within each line
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split by comma or tab
        parts = re.split(r"[,\t]+", line)
        for part in parts:
            cleaned = part.strip().upper()
            if cleaned and re.match(r"^[A-Z0-9.]+$", cleaned):
                symbols.append(cleaned)

    return parse_symbols(symbols)


def parse_csv(content: bytes) -> tuple[list[FundInput], list[str]]:
    """Parse CSV file content.

    Supports two formats:
    1. Simple: one column of symbols
    2. Detailed: columns for fund_symbol, ticker, weight

    Returns:
        Tuple of (funds, warnings)
    """
    warnings: list[str] = []
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    fieldnames = reader.fieldnames or []
    normalized_fields = [f.strip().lower() for f in fieldnames]

    # Detailed format: fund_symbol, ticker, weight
    if "ticker" in normalized_fields and "weight" in normalized_fields:
        fund_symbol_col = None
        for i, f in enumerate(normalized_fields):
            if f in ("fund_symbol", "fund", "symbol"):
                fund_symbol_col = fieldnames[i]
                break

        ticker_col = fieldnames[normalized_fields.index("ticker")]
        weight_col = fieldnames[normalized_fields.index("weight")]

        funds_dict: dict[str, list[Holding]] = {}
        for row in reader:
            symbol = (
                row.get(fund_symbol_col, "UNKNOWN").strip().upper()
                if fund_symbol_col
                else "UNKNOWN"
            )
            ticker = row.get(ticker_col, "").strip().upper()
            try:
                weight = float(row.get(weight_col, "0"))
            except ValueError:
                warnings.append(f"Invalid weight for {ticker} in {symbol}")
                continue

            if ticker:
                if symbol not in funds_dict:
                    funds_dict[symbol] = []
                funds_dict[symbol].append(Holding(ticker=ticker, weight=weight))

        funds = [
            FundInput(symbol=sym, holdings=holdings)
            for sym, holdings in funds_dict.items()
        ]
        return funds, warnings

    # Simple format: first column is symbols
    symbols: list[str] = []
    # Use DictReader rows (header already consumed)
    reader2 = csv.DictReader(io.StringIO(text))
    first_col = (reader2.fieldnames or [None])[0]
    if first_col:
        for row in reader2:
            val = row.get(first_col, "").strip().upper()
            if val and re.match(r"^[A-Z0-9.]+$", val):
                symbols.append(val)

    return parse_symbols(symbols)


def parse_json(content: bytes) -> tuple[list[FundInput], list[str]]:
    """Parse JSON file content.

    Supports formats:
    1. Array of symbols: ["SPY", "QQQ"]
    2. Array of objects: [{"symbol": "SPY", "holdings": [...]}]
    3. Object with symbols key: {"symbols": ["SPY", "QQQ"]}
    4. Object with funds key: {"funds": [{"symbol": "SPY", ...}]}

    Returns:
        Tuple of (funds, warnings)
    """
    warnings: list[str] = []
    data = json.loads(content.decode("utf-8"))

    # Array of strings (symbols)
    if isinstance(data, list) and all(isinstance(item, str) for item in data):
        return parse_symbols(data)

    # Array of objects
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        funds: list[FundInput] = []
        for item in data:
            symbol = item.get("symbol", "").strip().upper()
            if not symbol:
                continue
            holdings_data = item.get("holdings", [])
            holdings = [
                Holding(
                    ticker=h.get("ticker", "").strip().upper(),
                    weight=float(h.get("weight", 0)),
                )
                for h in holdings_data
                if h.get("ticker")
            ]
            if holdings:
                funds.append(FundInput(symbol=symbol, holdings=holdings))
            else:
                # Fall back to stub data
                result, w = parse_symbols([symbol])
                funds.extend(result)
                warnings.extend(w)
        return funds, warnings

    # Object with "symbols" key
    if isinstance(data, dict) and "symbols" in data:
        return parse_symbols(data["symbols"])

    # Object with "funds" key
    if isinstance(data, dict) and "funds" in data:
        return parse_json(json.dumps(data["funds"]).encode("utf-8"))

    warnings.append("Unrecognized JSON format")
    return [], warnings
