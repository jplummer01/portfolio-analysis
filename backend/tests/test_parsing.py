"""Tests for parsing tools."""

import json

import pytest

from src.tools.parsing import parse_csv, parse_json, parse_paste, parse_symbols


class TestParseSymbols:
    def test_known_symbols(self):
        funds, warnings = parse_symbols(["SPY", "QQQ"])
        assert len(funds) == 2
        assert funds[0].symbol == "SPY"
        assert funds[1].symbol == "QQQ"
        assert len(funds[0].holdings) > 0
        assert len(warnings) == 0

    def test_unknown_symbol(self):
        funds, warnings = parse_symbols(["UNKNOWN_FUND"])
        assert len(funds) == 1
        assert funds[0].symbol == "UNKNOWN_FUND"
        assert len(funds[0].holdings) == 0
        assert len(warnings) == 1

    def test_case_insensitive(self):
        funds, _ = parse_symbols(["spy", "qqq"])
        assert funds[0].symbol == "SPY"
        assert funds[1].symbol == "QQQ"

    def test_whitespace_handling(self):
        funds, _ = parse_symbols(["  SPY  ", " QQQ"])
        assert funds[0].symbol == "SPY"
        assert funds[1].symbol == "QQQ"

    def test_empty_input(self):
        funds, warnings = parse_symbols([])
        assert len(funds) == 0
        assert len(warnings) == 0

    def test_blank_strings_ignored(self):
        funds, _ = parse_symbols(["", "  ", "SPY"])
        assert len(funds) == 1
        assert funds[0].symbol == "SPY"


class TestParsePaste:
    def test_newline_separated(self):
        funds, _ = parse_paste("SPY\nQQQ\nVTI")
        assert len(funds) == 3

    def test_comma_separated(self):
        funds, _ = parse_paste("SPY, QQQ, VTI")
        assert len(funds) == 3

    def test_tab_separated(self):
        funds, _ = parse_paste("SPY\tQQQ\tVTI")
        assert len(funds) == 3

    def test_comments_ignored(self):
        funds, _ = parse_paste("# my funds\nSPY\nQQQ")
        assert len(funds) == 2

    def test_mixed_format(self):
        funds, _ = parse_paste("SPY, QQQ\nVTI\nARKK, SCHD")
        assert len(funds) == 5


class TestParseCsv:
    def test_simple_format(self):
        content = b"symbol\nSPY\nQQQ\nVTI"
        funds, _ = parse_csv(content)
        assert len(funds) == 3

    def test_detailed_format(self):
        content = b"fund_symbol,ticker,weight\nTEST,AAPL,0.5\nTEST,MSFT,0.3\nTEST,GOOGL,0.2"
        funds, warnings = parse_csv(content)
        assert len(funds) == 1
        assert funds[0].symbol == "TEST"
        assert len(funds[0].holdings) == 3

    def test_detailed_multiple_funds(self):
        content = b"fund_symbol,ticker,weight\nFUND1,AAPL,0.6\nFUND1,MSFT,0.4\nFUND2,GOOGL,0.5\nFUND2,AMZN,0.5"
        funds, _ = parse_csv(content)
        assert len(funds) == 2


class TestParseJson:
    def test_array_of_symbols(self):
        content = json.dumps(["SPY", "QQQ", "VTI"]).encode()
        funds, _ = parse_json(content)
        assert len(funds) == 3

    def test_array_of_objects(self):
        data = [
            {
                "symbol": "TEST",
                "holdings": [
                    {"ticker": "AAPL", "weight": 0.5},
                    {"ticker": "MSFT", "weight": 0.5},
                ],
            }
        ]
        content = json.dumps(data).encode()
        funds, _ = parse_json(content)
        assert len(funds) == 1
        assert funds[0].symbol == "TEST"
        assert len(funds[0].holdings) == 2

    def test_object_with_symbols_key(self):
        content = json.dumps({"symbols": ["SPY", "QQQ"]}).encode()
        funds, _ = parse_json(content)
        assert len(funds) == 2

    def test_object_with_funds_key(self):
        data = {
            "funds": [
                {
                    "symbol": "TEST",
                    "holdings": [{"ticker": "AAPL", "weight": 1.0}],
                }
            ]
        }
        content = json.dumps(data).encode()
        funds, _ = parse_json(content)
        assert len(funds) == 1

    def test_unrecognized_format(self):
        content = json.dumps({"foo": "bar"}).encode()
        funds, warnings = parse_json(content)
        assert len(funds) == 0
        assert len(warnings) > 0
