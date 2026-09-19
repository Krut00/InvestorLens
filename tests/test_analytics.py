from pathlib import Path

from investorlens.analytics import cagr, calculate_analysis
from investorlens.screener import ScreenerClient


def test_live_cached_tcs_analysis_has_eight_bounded_modules():
    data = ScreenerClient(Path("instance/cache")).get_company("TCS")
    analysis = calculate_analysis(data)

    assert len(analysis["modules"]) == 8
    assert 0 <= analysis["score"] <= 100
    assert all(0 <= module["score"] <= module["max"] for module in analysis["modules"])
    assert analysis["metrics"]["cash_conversion"] is not None
    insights = analysis["business_insights"]
    assert len(insights["dimensions"]) == 6
    assert len(insights["confirmations"]) == 4
    assert len(insights["invalidations"]) == 4
    assert "reported result" in insights["wait_window"]
    assert analysis["metrics"]["debtor_days_watch"] is True
    assert analysis["metrics"]["other_income_watch"] is True
    assert 1.5 < analysis["metrics"]["peg"] < 1.8
    assert all(item.startswith(("✓ Met", "✗ Not met")) for item in insights["confirmations"])
    comparison = insights["industry_comparison"]
    assert comparison["industry"] == "Computers - Software & Consulting"
    assert comparison["sample_size"] >= 5
    assert comparison["accounting_period"].startswith("Mar ")
    assert {item["key"] for item in comparison["comparisons"]} == {
        "pe", "earnings_yield", "roe", "roce", "opm"
    }


def test_five_year_cagr_uses_six_annual_observations():
    values = [(f"Mar {year}", value) for year, value in zip(range(2021, 2027), [100, 110, 121, 133.1, 146.41, 161.051])]

    assert round(cagr(values), 1) == 10.0
    assert cagr(values[1:]) is None