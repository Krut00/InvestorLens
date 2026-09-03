from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag


BASE_URL = "https://www.screener.in/company/{ticker}/consolidated/"
SEARCH_URL = "https://www.screener.in/api/company/search/"
PEERS_URL = "https://www.screener.in/api/company/{warehouse_id}/peers/"
TICKER_PATTERN = re.compile(r"^[A-Z0-9&.-]{1,24}$")
CACHE_SCHEMA_VERSION = 3


class ScreenerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObservedValue:
    label: str
    displayed: str
    value: Optional[float]
    values: List[float]
    unit: str
    source_url: str
    source_section: str
    verified: bool


def parse_number(text: str) -> Optional[float]:
    cleaned = text.replace("₹", "").replace(",", "").replace("%", "")
    cleaned = re.sub(r"\bCr\.?\b", "", cleaned, flags=re.IGNORECASE).strip()
    if not cleaned or cleaned in {"-", "--"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    return float(match.group()) if match else None


def infer_unit(text: str) -> str:
    if "%" in text:
        return "%"
    if "Cr" in text:
        return "₹ Cr"
    if "₹" in text:
        return "₹"
    return ""


def normalize_label(text: str) -> str:
    return " ".join(text.replace("+", "").split())


def observed(label: str, displayed: str, source_url: str, section: str) -> ObservedValue:
    normalized_label = normalize_label(label)
    numeric_parts = [float(part) for part in re.findall(r"-?\d+(?:\.\d+)?", displayed.replace(",", ""))]
    value = numeric_parts[0] if numeric_parts else None
    expected_parts = 2 if normalized_label == "High / Low" else 1
    return ObservedValue(
        label=normalized_label,
        displayed=" ".join(displayed.split()),
        value=value,
        values=numeric_parts,
        unit=infer_unit(displayed),
        source_url=source_url,
        source_section=section,
        verified=value is not None and len(numeric_parts) == expected_parts,
    )


def parse_screener_html(html: str, source_url: str) -> Dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    if heading is None:
        raise ScreenerError("Screener page did not contain a company heading.")

    summary: Dict[str, Dict[str, object]] = {}
    for item in soup.select("#top-ratios li"):
        name = item.select_one(".name")
        number = item.select_one(".number")
        if name and number:
            value_container = item.select_one(".value") or number
            metric = observed(name.get_text(" ", strip=True), value_container.get_text(" ", strip=True), f"{source_url}#top", "Summary")
            summary[metric.label] = asdict(metric)

    statements: Dict[str, Dict[str, object]] = {}
    section_names = {
        "profit-loss": "Profit & Loss",
        "balance-sheet": "Balance Sheet",
        "cash-flow": "Cash Flows",
        "ratios": "Ratios",
    }
    for section_id, section_name in section_names.items():
        section = soup.select_one(f"section#{section_id}")
        if section:
            statements[section_name] = parse_statement(section, f"{source_url}#{section_id}", section_name)

    if not summary or not statements:
        raise ScreenerError("Screener page structure was incomplete; no unverified data was returned.")

    industry_links = soup.select("#peers a[href^='/market/']")
    company_info = soup.select_one("#company-info")
    return {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "company": normalize_label(heading.get_text(" ", strip=True)),
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "industry": {
            "name": normalize_label(industry_links[-1].get_text(" ", strip=True)) if industry_links else "Not available",
            "hierarchy": [normalize_label(link.get_text(" ", strip=True)) for link in industry_links],
            "source_url": f"https://www.screener.in{industry_links[-1]['href']}" if industry_links else source_url,
        },
        "warehouse_id": company_info.get("data-warehouse-id") if company_info else None,
        "summary": summary,
        "statements": statements,
    }


def parse_peer_html(html: str, source_url: str, subject_ticker: str) -> Dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    headers = [normalize_label(cell.get_text(" ", strip=True)) for cell in soup.select("th")]
    metric_columns = {
        "P/E": ("pe", "P/E", "x"),
        "Div Yld %": ("dividend_yield", "Dividend yield", "%"),
        "Qtr Profit Var %": ("quarterly_profit_growth", "Quarterly profit growth", "%"),
        "Qtr Sales Var %": ("quarterly_sales_growth", "Quarterly sales growth", "%"),
        "ROCE %": ("roce", "ROCE", "%"),
    }
    peers = []
    for row in soup.select("tr"):
        cells = row.select("td")
        if len(cells) != len(headers):
            continue
        link = cells[1].select_one("a[href*='/company/']")
        ticker_match = re.search(r"/company/([^/]+)/", link.get("href", "") if link else "")
        metrics = {}
        for index, header in enumerate(headers):
            if header in metric_columns:
                key, label, unit = metric_columns[header]
                metrics[key] = {"label": label, "value": parse_number(cells[index].get_text(" ", strip=True)), "unit": unit}
        if metrics:
            peers.append({
                "name": normalize_label(cells[1].get_text(" ", strip=True)),
                "ticker": ticker_match.group(1).upper() if ticker_match else "",
                "is_subject": bool(ticker_match and ticker_match.group(1).upper() == subject_ticker),
                "metrics": metrics,
            })
    return {"source_url": source_url, "peers": peers}


def parse_statement(section: Tag, source_url: str, section_name: str) -> Dict[str, object]:
    table = section.select_one("table")
    if table is None:
        return {"periods": [], "rows": {}}

    headers = [normalize_label(cell.get_text(" ", strip=True)) for cell in table.select("thead th")]
    periods = headers[1:] if len(headers) > 1 else []
    rows: Dict[str, List[Dict[str, object]]] = {}
    for row in table.select("tbody tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        label = normalize_label(cells[0].get_text(" ", strip=True))
        rows[label] = [
            asdict(observed(label, cell.get_text(" ", strip=True), source_url, section_name))
            for cell in cells[1:]
        ]
    return {"periods": periods, "rows": rows}


def _statement_value(data: Dict[str, object], section: str, row: str, period: str) -> Optional[float]:
    statement = data.get("statements", {}).get(section, {})
    periods = statement.get("periods", [])
    try:
        index = periods.index(period)
    except ValueError:
        return None
    points = statement.get("rows", {}).get(row, [])
    return points[index].get("value") if index < len(points) else None


def _equity(data: Dict[str, object], period: str) -> Optional[float]:
    capital = _statement_value(data, "Balance Sheet", "Equity Capital", period)
    reserves = _statement_value(data, "Balance Sheet", "Reserves", period)
    return capital + reserves if capital is not None and reserves is not None else None


def extract_period_peer(data: Dict[str, object], ticker: str, period: str, is_subject: bool = False) -> Optional[Dict[str, object]]:
    profit_loss = data.get("statements", {}).get("Profit & Loss", {})
    periods = profit_loss.get("periods", [])
    if period not in periods:
        return None
    period_index = periods.index(period)
    prior_period = periods[period_index - 1] if period_index > 0 else None
    price = data.get("summary", {}).get("Current Price", {}).get("value")
    eps = _statement_value(data, "Profit & Loss", "EPS in Rs", period)
    profit = _statement_value(data, "Profit & Loss", "Net Profit", period)
    current_equity = _equity(data, period)
    prior_equity = _equity(data, prior_period) if prior_period else None
    average_equity = (current_equity + prior_equity) / 2 if current_equity is not None and prior_equity is not None else current_equity
    pe = price / eps if price is not None and eps is not None and eps > 0 else None
    earnings_yield = eps / price * 100 if price is not None and price > 0 and eps is not None else None
    roe = profit / average_equity * 100 if profit is not None and average_equity is not None and average_equity > 0 else None
    metrics = {
        "pe": {"label": "P/E on annual EPS", "value": round(pe, 2) if pe is not None else None, "unit": "x"},
        "earnings_yield": {"label": "Earnings yield", "value": round(earnings_yield, 2) if earnings_yield is not None else None, "unit": "%"},
        "roe": {"label": "ROE on average equity", "value": round(roe, 2) if roe is not None else None, "unit": "%"},
        "roce": {"label": "ROCE", "value": _statement_value(data, "Ratios", "ROCE %", period), "unit": "%"},
        "opm": {"label": "Operating margin", "value": _statement_value(data, "Profit & Loss", "OPM %", period), "unit": "%"},
    }
    if not any(metric["value"] is not None for metric in metrics.values()):
        return None
    return {
        "name": data.get("company", ticker),
        "ticker": ticker,
        "is_subject": is_subject,
        "accounting_period": period,
        "source_url": data.get("source_url"),
        "metrics": metrics,
    }


class ScreenerClient:
    def __init__(self, cache_dir: Path, cache_seconds: int = 60) -> None:
        self.cache_dir = cache_dir
        self.cache_seconds = cache_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_company(self, ticker: str, refresh: bool = False) -> Dict[str, object]:
        ticker = ticker.strip().upper()
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ScreenerError("Use a valid NSE ticker, for example TCS or HDFCBANK.")

        cache_path = self.cache_dir / f"{ticker}.json"
        if not refresh and cache_path.exists() and time.time() - cache_path.stat().st_mtime < self.cache_seconds:
            with cache_path.open(encoding="utf-8") as cached:
                result = json.load(cached)
                if result.get("cache_schema_version") == CACHE_SCHEMA_VERSION and "period_peer_comparison" in result:
                    return result

        source_url = BASE_URL.format(ticker=ticker)
        try:
            response = requests.get(
                source_url,
                timeout=20,
                headers={"User-Agent": "InvestorLens/0.1 educational dashboard"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ScreenerError(f"Could not fetch Screener data: {exc}") from exc

        result = parse_screener_html(response.text, source_url)
        warehouse_id = result.pop("warehouse_id", None)
        result["peer_comparison"] = {"source_url": source_url, "peers": []}
        if warehouse_id:
            peer_url = PEERS_URL.format(warehouse_id=warehouse_id)
            try:
                peer_response = requests.get(
                    peer_url,
                    timeout=20,
                    headers={"User-Agent": "InvestorLens/0.1 educational dashboard"},
                )
                peer_response.raise_for_status()
                result["peer_comparison"] = parse_peer_html(peer_response.text, peer_url, ticker)
            except requests.RequestException:
                pass
        result["period_peer_comparison"] = self._get_period_peer_comparison(result, ticker)
        with cache_path.open("w", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=True)
        return result

    def _get_period_peer_comparison(self, subject_data: Dict[str, object], subject_ticker: str) -> Dict[str, object]:
        periods = subject_data.get("statements", {}).get("Profit & Loss", {}).get("periods", [])
        annual_periods = [period for period in periods if re.search(r"\b\d{4}\b", str(period))]
        period = annual_periods[-1] if annual_periods else ""
        subject = extract_period_peer(subject_data, subject_ticker, period, True) if period else None
        peers = [peer for peer in subject_data.get("peer_comparison", {}).get("peers", []) if not peer.get("is_subject")]

        def fetch_peer(peer: Dict[str, object]) -> Optional[Dict[str, object]]:
            peer_ticker = str(peer.get("ticker", ""))
            if not TICKER_PATTERN.fullmatch(peer_ticker):
                return None
            source_url = BASE_URL.format(ticker=peer_ticker)
            try:
                response = requests.get(source_url, timeout=20, headers={"User-Agent": "InvestorLens/0.1 educational dashboard"})
                response.raise_for_status()
                return extract_period_peer(parse_screener_html(response.text, source_url), peer_ticker, period)
            except (requests.RequestException, ScreenerError):
                return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            comparables = list(executor.map(fetch_peer, peers[:7]))
        matched = [peer for peer in comparables if peer is not None]
        return {
            "accounting_period": period,
            "price_basis": "Current prices fetched with the report; annual EPS and return inputs use the stated accounting period.",
            "source_url": subject_data.get("peer_comparison", {}).get("source_url", subject_data.get("source_url")),
            "peers": ([subject] if subject else []) + matched,
            "excluded_count": min(len(peers), 7) - len(matched),
        }

    def search_companies(self, query: str) -> List[Dict[str, str]]:
        query = " ".join(query.strip().split())
        if not query or len(query) > 80:
            return []

        try:
            response = requests.get(
                SEARCH_URL,
                params={"q": query},
                timeout=10,
                headers={"User-Agent": "InvestorLens/0.1 educational dashboard"},
            )
            response.raise_for_status()
            matches = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ScreenerError(f"Could not search Screener companies: {exc}") from exc

        results = []
        for match in matches[:10]:
            ticker_match = re.match(r"^/company/([^/]+)/", str(match.get("url", "")))
            if ticker_match and match.get("name"):
                results.append({"name": str(match["name"]), "ticker": ticker_match.group(1).upper()})
        return results
