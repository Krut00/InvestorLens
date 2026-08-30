from investorlens.report import _statement_rows


def test_statement_rows_support_non_march_year_ends_and_percentage_points():
    statement = {
        "periods": ["Dec 2024", "Dec 2025", "TTM"],
        "rows": {
            "Sales": [
                {"value": 100, "displayed": "100", "unit": ""},
                {"value": 120, "displayed": "120", "unit": ""},
                {"value": 125, "displayed": "125", "unit": ""},
            ],
            "OPM %": [
                {"value": 20, "displayed": "20%", "unit": "%"},
                {"value": 18, "displayed": "18%", "unit": "%"},
                {"value": 19, "displayed": "19%", "unit": "%"},
            ],
        },
    }

    rows = _statement_rows(statement)

    assert rows[0]["latest_period"] == "Dec 2025"
    assert rows[0]["change_display"] == "+20.0%"
    assert rows[1]["change_display"] == "-2.0 pp"


def test_statement_rows_do_not_show_growth_for_negative_values():
    statement = {
        "periods": ["Mar 2024", "Mar 2025"],
        "rows": {
            "Net Cash Flow": [
                {"value": -10, "displayed": "-10", "unit": ""},
                {"value": 5, "displayed": "5", "unit": ""},
            ],
        },
    }

    row = _statement_rows(statement)[0]

    assert row["change_display"] == "N/M"
    assert "misleading" in row["interpretation"]