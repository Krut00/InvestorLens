from __future__ import annotations

from statistics import median
from typing import Dict, List, Optional, Tuple


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def higher_is_better(value: Optional[float], poor: float, strong: float, points: float) -> float:
    if value is None:
        return points * 0.4
    return points * clamp((value - poor) / (strong - poor), 0, 1)


def lower_is_better(value: Optional[float], strong: float, poor: float, points: float) -> float:
    if value is None:
        return points * 0.4
    return points * (1 - clamp((value - strong) / (poor - strong), 0, 1))


def divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    ratio = divide(current, abs(previous) if previous else previous)
    return (ratio - 1) * 100 if ratio is not None else None


def cagr(values: List[Tuple[str, Optional[float]]], years: int = 5) -> Optional[float]:
    points = [value for _, value in values if value is not None and value > 0][-years:]
    if len(points) < 2:
        return None
    return ((points[-1] / points[0]) ** (1 / (len(points) - 1)) - 1) * 100


def percent(value: Optional[float]) -> str:
    return "not available" if value is None else f"{value:.1f}%"


def multiple(value: Optional[float]) -> str:
    return "not available" if value is None else f"{value:.2f}x"


def summary_value(data: Dict[str, object], label: str) -> Optional[float]:
    metric = data.get("summary", {}).get(label, {})
    return metric.get("value")


def annual_series(data: Dict[str, object], section: str, row: str) -> List[Tuple[str, Optional[float]]]:
    statement = data.get("statements", {}).get(section, {})
    periods = statement.get("periods", [])
    values = statement.get("rows", {}).get(row, [])
    return [
        (period, point.get("value"))
        for period, point in zip(periods, values)
        if str(period).startswith("Mar ")
    ]


def latest(data: Dict[str, object], section: str, row: str, offset: int = 0) -> Optional[float]:
    values = annual_series(data, section, row)
    index = len(values) - 1 - offset
    return values[index][1] if index >= 0 else None


def calculate_peer_benchmarks(data: Dict[str, object]) -> Dict[str, object]:
    peer_data = data.get("period_peer_comparison", {})
    peers = peer_data.get("peers", [])
    subject = next((peer for peer in peers if peer.get("is_subject")), None)
    comparables = [peer for peer in peers if not peer.get("is_subject")]
    comparisons = []
    for key in ("pe", "earnings_yield", "roe", "roce", "opm"):
        company_metric = (subject or {}).get("metrics", {}).get(key, {})
        company_value = company_metric.get("value")
        peer_values = [peer.get("metrics", {}).get(key, {}).get("value") for peer in comparables]
        peer_values = [value for value in peer_values if value is not None]
        if company_value is None or not peer_values:
            continue
        benchmark = median(peer_values)
        difference = company_value - benchmark
        difference_percent = divide(difference, abs(benchmark))
        relative = (difference_percent or 0) * 100
        lower_is_favorable = key == "pe"
        if abs(relative) < 10:
            assessment, signal = "In line", "neutral"
        elif (relative < 0) == lower_is_favorable:
            assessment, signal = ("Discount" if lower_is_favorable else "Above peers"), "positive"
        else:
            assessment, signal = ("Premium" if lower_is_favorable else "Below peers"), "caution"
        comparisons.append({
            "key": key,
            "label": company_metric.get("label", key),
            "unit": company_metric.get("unit", ""),
            "company": round(company_value, 2),
            "peer_median": round(benchmark, 2),
            "difference_percent": round(relative, 1),
            "assessment": assessment,
            "signal": signal,
        })
    industry = data.get("industry", {})
    return {
        "industry": industry.get("name", "Not available"),
        "hierarchy": industry.get("hierarchy", []),
        "industry_url": industry.get("source_url", data.get("source_url")),
        "source_url": peer_data.get("source_url", data.get("source_url")),
        "sample_size": len(comparables),
        "accounting_period": peer_data.get("accounting_period", "Not available"),
        "price_basis": peer_data.get("price_basis", ""),
        "excluded_count": peer_data.get("excluded_count", 0),
        "methodology": "Benchmark is the median of direct Screener peers with the exact same accounting period, excluding the company. P/E and earnings yield use current prices with same-period annual EPS; return ratios use same-period financial statements.",
        "comparisons": comparisons,
    }


def calculate_analysis(data: Dict[str, object]) -> Dict[str, object]:
    sales = latest(data, "Profit & Loss", "Sales")
    prior_sales = latest(data, "Profit & Loss", "Sales", 1)
    profit = latest(data, "Profit & Loss", "Net Profit")
    prior_profit = latest(data, "Profit & Loss", "Net Profit", 1)
    operating_profit = latest(data, "Profit & Loss", "Operating Profit")
    opm = latest(data, "Profit & Loss", "OPM %")
    prior_opm = latest(data, "Profit & Loss", "OPM %", 1)
    interest = latest(data, "Profit & Loss", "Interest")
    other_income = latest(data, "Profit & Loss", "Other Income")
    pbt = latest(data, "Profit & Loss", "Profit before tax")
    eps = latest(data, "Profit & Loss", "EPS in Rs")
    prior_eps = latest(data, "Profit & Loss", "EPS in Rs", 1)
    cfo = latest(data, "Cash Flows", "Cash from Operating Activity")
    prior_cfo = latest(data, "Cash Flows", "Cash from Operating Activity", 1)
    assets = latest(data, "Balance Sheet", "Total Assets")
    prior_assets = latest(data, "Balance Sheet", "Total Assets", 1)
    equity = (latest(data, "Balance Sheet", "Equity Capital") or 0) + (latest(data, "Balance Sheet", "Reserves") or 0)
    borrowings = latest(data, "Balance Sheet", "Borrowings")
    prior_borrowings = latest(data, "Balance Sheet", "Borrowings", 1)
    debtor_days = latest(data, "Ratios", "Debtor Days")
    prior_debtor_days = latest(data, "Ratios", "Debtor Days", 1)

    sales_growth = growth(sales, prior_sales)
    profit_growth = growth(profit, prior_profit)
    eps_growth = growth(eps, prior_eps)
    cfo_growth = growth(cfo, prior_cfo)
    debt_growth = growth(borrowings, prior_borrowings)
    cash_conversion = divide(cfo, profit)
    npm = (divide(profit, sales) or 0) * 100
    asset_turnover = divide(sales, ((assets or 0) + (prior_assets or assets or 0)) / 2)
    equity_multiplier = divide(assets, equity)
    debt_equity = divide(borrowings, equity)
    interest_cover = divide(operating_profit, interest)
    other_income_share = (divide(other_income, pbt) or 0) * 100
    pe = summary_value(data, "Stock P/E")
    roe = summary_value(data, "ROE")
    roce = summary_value(data, "ROCE")
    dividend_yield = summary_value(data, "Dividend Yield")
    price = summary_value(data, "Current Price")
    book_value = summary_value(data, "Book Value")
    price_to_book = divide(price, book_value)
    peg = divide(pe, max(profit_growth or 0, 0.1))
    sales_cagr = cagr(annual_series(data, "Profit & Loss", "Sales"))
    profit_cagr = cagr(annual_series(data, "Profit & Loss", "Net Profit"))
    cfo_cagr = cagr(annual_series(data, "Cash Flows", "Cash from Operating Activity"))
    peer_benchmarks = calculate_peer_benchmarks(data)

    module_inputs = [
        ("Financial performance", 15, higher_is_better(sales_growth, 0, 15, 6) + higher_is_better(profit_growth, 0, 15, 6) + higher_is_better((opm or 0) - (prior_opm or opm or 0), -2, 2, 3)),
        ("Profitability & efficiency", 15, higher_is_better(roe, 8, 25, 4) + higher_is_better(roce, 10, 30, 5) + higher_is_better(opm, 8, 25, 3) + higher_is_better(asset_turnover, 0.4, 1.5, 3)),
        ("Cash flow & earnings quality", 15, higher_is_better(cash_conversion, 0.5, 1.1, 8) + higher_is_better(cfo_growth, -10, 15, 4) + lower_is_better((profit_growth or 0) - (cfo_growth or 0), 0, 25, 3)),
        ("DuPont analysis", 10, higher_is_better(npm, 4, 15, 4) + higher_is_better(asset_turnover, 0.4, 1.5, 3) + lower_is_better(equity_multiplier, 1.2, 3.0, 3)),
        ("Leverage", 10, lower_is_better(debt_equity, 0.2, 2, 4) + higher_is_better(interest_cover, 2, 10, 3) + lower_is_better(debt_growth, 0, 30, 3)),
        ("Growth quality", 10, higher_is_better(sales_growth, 0, 15, 3) + higher_is_better(profit_growth, 0, 18, 4) + higher_is_better(eps_growth, 0, 18, 3)),
        ("Valuation", 15, lower_is_better(pe, 15, 50, 5) + lower_is_better(peg, 0.8, 2.5, 4) + lower_is_better(price_to_book, 2, 8, 3) + higher_is_better(dividend_yield, 0, 3, 3)),
        ("Governance & red flags", 10, higher_is_better(cash_conversion, 0.5, 1, 4) + lower_is_better(other_income_share, 5, 30, 3) + lower_is_better((debtor_days or 0) - (prior_debtor_days or debtor_days or 0), 0, 30, 3)),
    ]
    modules = [
        {"name": name, "score": round(clamp(score, 0, maximum), 1), "max": maximum}
        for name, maximum, score in module_inputs
    ]
    total = round(sum(module["score"] for module in modules))
    if total >= 80:
        decision, tone = "Fundamentally strong", "positive"
    elif total >= 65:
        decision, tone = "Watchlist", "watch"
    elif total >= 50:
        decision, tone = "Caution", "caution"
    else:
        decision, tone = "High fundamental risk", "negative"

    metrics = {
        "sales_growth": sales_growth,
        "profit_growth": profit_growth,
        "eps_growth": eps_growth,
        "cfo_growth": cfo_growth,
        "cash_conversion": cash_conversion,
        "npm": npm,
        "opm": opm,
        "asset_turnover": asset_turnover,
        "equity_multiplier": equity_multiplier,
        "debt_equity": debt_equity,
        "interest_cover": interest_cover,
        "other_income_share": other_income_share,
        "debtor_days": debtor_days,
        "pe": pe,
        "peg": peg,
        "price_to_book": price_to_book,
        "roe": roe,
        "roce": roce,
    }
    strengths: List[str] = []
    risks: List[str] = []
    if (roce or 0) >= 20:
        strengths.append(f"ROCE is strong at {roce:.1f}%.")
    if (cash_conversion or 0) >= 0.9:
        strengths.append(f"Operating cash supports profit at {cash_conversion:.2f}x.")
    if (debt_equity or 99) <= 0.5:
        strengths.append(f"Debt-to-equity is controlled at {debt_equity:.2f}x.")
    if (cash_conversion or 0) < 0.8:
        risks.append(f"Cash conversion is weak at {(cash_conversion or 0):.2f}x.")
    if (profit_growth or 0) - (cfo_growth or 0) > 15:
        risks.append("Profit growth is materially ahead of operating cash growth.")
    if other_income_share > 20:
        risks.append(f"Other income contributes {other_income_share:.1f}% of pre-tax profit.")
    if (peg or 0) > 2:
        risks.append(f"Valuation is demanding relative to current profit growth (PEG {peg:.2f}).")

    peer_strengths = [item for item in peer_benchmarks["comparisons"] if item["signal"] == "positive"]
    peer_warnings = [item for item in peer_benchmarks["comparisons"] if item["signal"] == "caution"]

    if total >= 80:
        stance = "Favorable, subject to valuation discipline"
        action = "The model supports further due diligence or phased accumulation rather than an automatic purchase."
        wait_window = "No mandatory waiting period. Recheck after the next reported result before increasing exposure."
    elif total >= 65:
        stance = "Watchlist; wait for confirmation"
        action = "The business quality is investable enough to monitor, but the evidence is not uniformly strong enough for an unconditional entry."
        wait_window = "Wait for the next 1-2 reported results, roughly 3-6 months, and act only if the confirmation triggers improve."
    elif total >= 50:
        stance = "Cautious; defer new exposure"
        action = "The current balance of growth, cash quality, leverage, and valuation does not provide a strong margin of safety."
        wait_window = "Wait for at least 2 reported results, roughly 6-12 months, unless the financial triggers improve sooner."
    else:
        stance = "Avoid pending material repair"
        action = "The model does not support new exposure until operating and balance-sheet evidence changes materially."
        wait_window = "Do not use time alone as the trigger. Reassess after 2-4 reported results and only after the stated repair conditions are met."

    confirmations = [
        f"Sales growth should remain positive and move above 8%; latest is {percent(sales_growth)}.",
        f"Profit growth should reach or exceed sales growth without margin deterioration; latest profit growth is {percent(profit_growth)}.",
        f"Operating cash flow should cover at least 90% of net profit; latest coverage is {multiple(cash_conversion)}.",
        f"Debt-to-equity should remain below 0.50x; latest is {multiple(debt_equity)}.",
    ]
    invalidations = [
        "Two consecutive reporting periods of declining sales or operating margin would weaken the operating thesis.",
        "Cash conversion below 0.80x or profit growth materially ahead of cash growth would raise accrual-quality risk.",
        "Debt-to-equity above 1.00x or interest cover below 3.00x would invalidate the current balance-sheet comfort.",
        "A rising valuation multiple alongside slowing profit growth would reduce the margin of safety.",
    ]
    business_insights = {
        "stance": stance,
        "action": action,
        "wait_window": wait_window,
        "confidence": "Medium" if total >= 50 else "Low",
        "executive_summary": [
            f"The rules-based fundamental score is {total}/100, placing the company in the '{decision}' category.",
            f"Over the available five-year window, sales compounded at {percent(sales_cagr)}, net profit at {percent(profit_cagr)}, and operating cash flow at {percent(cfo_cagr)}.",
            f"Current return metrics are ROE {percent(roe)} and ROCE {percent(roce)}, while operating cash conversion is {multiple(cash_conversion)}.",
            "This view evaluates reported financial evidence. It does not assess management guidance, industry structure, news, competitive positioning, or an investor's personal risk tolerance.",
        ],
        "dimensions": [
            {
                "title": "Growth engine and operating momentum",
                "rating": "Strong" if (sales_cagr or 0) >= 10 and (profit_cagr or 0) >= 10 else "Mixed" if (sales_cagr or 0) > 0 else "Weak",
                "analysis": f"Five-year sales CAGR is {percent(sales_cagr)} versus profit CAGR of {percent(profit_cagr)}. The latest annual movement is sales {percent(sales_growth)} and profit {percent(profit_growth)}. Operating margin is {percent(opm)}, compared with {percent(prior_opm)} in the prior year. Profit growing faster than sales can indicate operating leverage, while the reverse suggests margin or non-operating pressure.",
            },
            {
                "title": "Profitability and capital efficiency",
                "rating": "Strong" if (roce or 0) >= 20 else "Adequate" if (roce or 0) >= 12 else "Weak",
                "analysis": f"ROCE of {percent(roce)} and ROE of {percent(roe)} indicate how effectively the company converts capital into reported earnings. The DuPont components are net margin {percent(npm)}, asset turnover {multiple(asset_turnover)}, and equity multiplier {multiple(equity_multiplier)}. A lower equity multiplier means returns rely less on financial leverage.",
            },
            {
                "title": "Cash flow and earnings quality",
                "rating": "Strong" if (cash_conversion or 0) >= 1 else "Adequate" if (cash_conversion or 0) >= 0.8 else "Weak",
                "analysis": f"Operating cash flow equals {multiple(cash_conversion)} of net profit. Five-year operating cash CAGR is {percent(cfo_cagr)}, while the latest cash-flow growth is {percent(cfo_growth)} against profit growth of {percent(profit_growth)}. Persistent profit growth without matching cash growth can signal working-capital absorption or aggressive accruals and requires statement-level review.",
            },
            {
                "title": "Balance-sheet resilience",
                "rating": "Strong" if (debt_equity or 99) <= 0.5 and (interest_cover or 0) >= 5 else "Watch" if (debt_equity or 99) <= 1 else "Weak",
                "analysis": f"Debt-to-equity is {multiple(debt_equity)} and operating profit covers interest {multiple(interest_cover)}. Latest debt growth is {percent(debt_growth)}. The current structure appears more resilient when borrowing remains controlled and interest coverage stays comfortably above cyclical stress levels.",
            },
            {
                "title": "Working capital and accounting signals",
                "rating": "Stable" if (debtor_days or 999) <= 90 else "Watch",
                "analysis": f"Debtor days are {debtor_days:.0f} days" if debtor_days is not None else "Debtor-day data is not available.",
                "detail": f"The prior period was {prior_debtor_days:.0f} days. Other income contributes {percent(other_income_share)} of pre-tax profit. Rising collection periods or greater dependence on non-operating income can reduce the reliability of headline earnings." if prior_debtor_days is not None else f"Other income contributes {percent(other_income_share)} of pre-tax profit.",
            },
            {
                "title": "Valuation and expectations",
                "rating": "Attractive" if (peg or 99) <= 1.2 else "Balanced" if (peg or 99) <= 2 else "Demanding",
                "analysis": f"The stock trades at {multiple(pe)} earnings, {multiple(price_to_book)} book value, and a growth-adjusted PE of {multiple(peg)} using latest annual profit growth. Dividend yield is {percent(dividend_yield)}. These are context indicators, not intrinsic-value estimates; sector economics and normalized growth must be assessed before concluding that a multiple is cheap or expensive.",
            },
        ],
        "why_choose": strengths + [
            f"Five-year sales and profit compounding are {percent(sales_cagr)} and {percent(profit_cagr)}, respectively.",
            f"Interest coverage of {multiple(interest_cover)} provides a reported buffer against financing stress.",
        ] + [f"{item['label']} is favorable versus the peer median ({item['assessment'].lower()})." for item in peer_strengths],
        "why_not": risks + [
            f"Latest sales growth of {percent(sales_growth)} may not justify the current earnings multiple without sustained execution.",
            "The analysis excludes qualitative moat, customer concentration, management quality, regulation, and industry-cycle evidence.",
        ] + [f"{item['label']} is unfavorable versus the peer median ({item['assessment'].lower()})." for item in peer_warnings],
        "industry_comparison": peer_benchmarks,
        "confirmations": confirmations,
        "invalidations": invalidations,
        "research_gaps": [
            "Read the latest annual report, auditor notes, contingent liabilities, related-party disclosures, and management commentary.",
            "Review peer accounting policies and one-off items that can reduce comparability even within the same reporting period.",
            "Check revenue concentration, segment economics, order pipeline, competitive position, and industry-cycle sensitivity.",
            "Validate promoter pledging, share dilution, capital allocation, acquisitions, and regulatory or litigation exposure.",
        ],
        "disclaimer": "General research support only, based on public Screener figures. It is not personalized investment advice, a price target, or a prediction. Waiting periods are review windows, not guarantees.",
    }

    return {
        "score": total,
        "decision": decision,
        "tone": tone,
        "modules": modules,
        "metrics": {key: round(value, 2) if value is not None else None for key, value in metrics.items()},
        "strengths": strengths[:3] or ["No major model strength cleared its threshold."],
        "risks": risks[:3] or ["No major accounting warning cleared its threshold."],
        "methodology": "Rules-based accounting model; not a prediction or investment recommendation.",
        "business_insights": business_insights,
    }