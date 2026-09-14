from unittest.mock import Mock, patch

from app import create_app


def test_index_and_cached_company_api():
    app = create_app()
    test_client = app.test_client()

    assert test_client.get("/").status_code == 200
    response = test_client.get("/api/company/TCS")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["company"] == "Tata Consultancy Services Ltd"
    assert len(payload["analysis"]["modules"]) == 8
    index = test_client.get("/").get_data(as_text=True)
    assert "Compare Companies" in index
    assert 'id="comparison-form"' in index
    assert 'aria-controls="compare-left-suggestions"' in index
    assert 'aria-controls="compare-right-suggestions"' in index


def test_invalid_ticker_is_rejected():
    response = create_app().test_client().get("/api/company/not%20valid")
    assert response.status_code == 422


def test_analyst_report_download_contains_statement_analysis():
    response = create_app().test_client().get("/api/company/TCS/report")
    pdf = response.get_data()

    assert response.status_code == 200
    assert response.content_type == "application/pdf"
    assert response.headers["Content-Disposition"] == 'attachment; filename="TCS-analyst-report.pdf"'
    assert pdf.startswith(b"%PDF-")
    assert pdf.endswith(b"%%EOF\n")
    assert pdf.count(b"/Type /Page") >= 5


@patch("investorlens.screener.requests.get")
def test_company_search_returns_names_and_tickers(get):
    response = Mock()
    response.json.return_value = [
        {"id": 1, "name": "Tata Steel Ltd", "url": "/company/TATASTEEL/consolidated/"},
        {"id": 2, "name": "Tata Elxsi Ltd", "url": "/company/TATAELXSI/"},
    ]
    get.return_value = response

    result = create_app().test_client().get("/api/companies?q=tata")

    assert result.status_code == 200
    assert result.get_json() == [
        {"name": "Tata Steel Ltd", "ticker": "TATASTEEL"},
        {"name": "Tata Elxsi Ltd", "ticker": "TATAELXSI"},
    ]
    get.assert_called_once_with(
        "https://www.screener.in/api/company/search/",
        params={"q": "tata"},
        timeout=10,
        headers={"User-Agent": "InvestorLens/0.1 educational dashboard"},
    )