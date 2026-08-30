from pathlib import Path

from investorlens.analytics import calculate_analysis
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
    comparison = insights["industry_comparison"]
    assert comparison["industry"] == "Computers - Software & Consulting"
    assert comparison["sample_size"] >= 5
    assert comparison["accounting_period"].startswith("Mar ")
    assert {item["key"] for item in comparison["comparisons"]} == {
        "pe", "earnings_yield", "roe", "roce", "opm"
    }