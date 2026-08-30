from investorlens.screener import ScreenerError, extract_period_peer, parse_number, parse_peer_html, parse_screener_html


HTML = """
<html><body>
<h1>Tata Consultancy Services Ltd</h1>
<ul id="top-ratios">
  <li><span class="name">Market Cap</span><span class="number">₹ 8,47,356 Cr.</span></li>
  <li><span class="name">ROCE</span><span class="number">63.0 %</span></li>
</ul>
<section id="profit-loss"><table>
  <thead><tr><th></th><th>Mar 2024</th><th>Mar 2025</th></tr></thead>
  <tbody><tr><td>Sales +</td><td>240,893</td><td>255,324</td></tr></tbody>
</table></section>
</body></html>
"""


def test_parse_number_preserves_negative_and_decimal_values():
    assert parse_number("₹ -1,234.50 Cr.") == -1234.5
    assert parse_number("63.0 %") == 63.0


def test_parse_visible_values_and_verification_metadata():
    result = parse_screener_html(HTML, "https://www.screener.in/company/TCS/consolidated/")
    market_cap = result["summary"]["Market Cap"]
    sales = result["statements"]["Profit & Loss"]["rows"]["Sales"]

    assert result["company"] == "Tata Consultancy Services Ltd"
    assert market_cap["displayed"] == "₹ 8,47,356 Cr."
    assert market_cap["value"] == 847356.0
    assert market_cap["verified"] is True
    assert [point["value"] for point in sales] == [240893.0, 255324.0]


def test_high_low_pair_preserves_both_values_and_is_verified():
    html = HTML.replace("ROCE", "High / Low").replace("63.0 %", "₹ 3,350 / 1,976")
    result = parse_screener_html(html, "https://www.screener.in/company/TCS/consolidated/")

    high_low = result["summary"]["High / Low"]
    assert high_low["value"] == 3350.0
    assert high_low["values"] == [3350.0, 1976.0]
    assert high_low["verified"] is True


def test_unexpected_multi_number_scalar_is_still_reviewed():
    html = HTML.replace("63.0 %", "63.0 / 51.8 %")
    result = parse_screener_html(html, "https://www.screener.in/company/TCS/consolidated/")

    assert result["summary"]["ROCE"]["verified"] is False


def test_rejects_pages_without_required_source_sections():
    try:
        parse_screener_html("<h1>Blocked</h1>", "https://www.screener.in/")
    except ScreenerError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("Expected incomplete pages to be rejected")


def test_parses_peer_metrics_and_identifies_subject():
    html = """
    <table><tr><th>S.No.</th><th>Name</th><th>P/E</th><th>Div Yld %</th><th>Qtr Profit Var %</th><th>Qtr Sales Var %</th><th>ROCE %</th></tr>
    <tr><td>1.</td><td><a href="/company/TCS/consolidated/">TCS</a></td><td>15.78</td><td>2.73</td><td>8.45</td><td>13.93</td><td>63.03</td></tr>
    <tr><td>2.</td><td><a href="/company/INFY/consolidated/">Infosys</a></td><td>14.89</td><td>4.20</td><td>12.25</td><td>14.03</td><td>39.95</td></tr></table>
    """
    result = parse_peer_html(html, "https://www.screener.in/api/company/1/peers/", "TCS")

    assert len(result["peers"]) == 2
    assert result["peers"][0]["is_subject"] is True
    assert result["peers"][1]["metrics"]["roce"]["value"] == 39.95


def test_extracts_peer_ratios_for_the_exact_accounting_period():
    data = {
        "company": "Example Ltd",
        "source_url": "https://www.screener.in/company/EXAMPLE/consolidated/",
        "summary": {"Current Price": {"value": 240}},
        "statements": {
            "Profit & Loss": {
                "periods": ["Mar 2024", "Mar 2025", "TTM"],
                "rows": {
                    "EPS in Rs": [{"value": 10}, {"value": 12}, {"value": 13}],
                    "Net Profit": [{"value": 90}, {"value": 120}, {"value": 130}],
                    "OPM %": [{"value": 18}, {"value": 20}, {"value": 21}],
                },
            },
            "Balance Sheet": {
                "periods": ["Mar 2024", "Mar 2025"],
                "rows": {
                    "Equity Capital": [{"value": 100}, {"value": 100}],
                    "Reserves": [{"value": 800}, {"value": 1000}],
                },
            },
            "Ratios": {"periods": ["Mar 2024", "Mar 2025"], "rows": {"ROCE %": [{"value": 17}, {"value": 19}]}},
        },
    }

    peer = extract_period_peer(data, "EXAMPLE", "Mar 2025")

    assert peer["accounting_period"] == "Mar 2025"
    assert peer["metrics"]["pe"]["value"] == 20
    assert peer["metrics"]["earnings_yield"]["value"] == 5
    assert peer["metrics"]["roe"]["value"] == 12
    assert peer["metrics"]["roce"]["value"] == 19
    assert extract_period_peer(data, "EXAMPLE", "Dec 2025") is None