# InvestorLens

InvestorLens is a local, accounting-based stock analysis dashboard. It fetches consolidated public company pages from Screener.in, calculates an explainable 100-point fundamental score, and retains Screener's exact displayed text beside every normalized value.

## Run locally

```bash
cd /Users/krut/Projects/investorlens-screener
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5051` and enter an NSE ticker such as `TCS`, `INFY`, or `HDFCBANK`.

## Verification model

- Data is fetched server-side from the company's consolidated Screener page.
- Responses are cached locally for 15 minutes to avoid unnecessary requests.
- Every observation stores its numeric value, exact displayed text, unit, section, source URL, and fetch timestamp.
- The Source audit view compares normalized values with Screener's displayed values and links to the relevant page section.
- Incomplete or changed page structures are rejected instead of silently returning partial, unverified data.

A `Matched` result confirms that the displayed text was parsed reproducibly. It does not independently certify the underlying financial statement data.

## Score

The rules-based score covers financial performance, profitability and efficiency, cash flow and earnings quality, DuPont analysis, leverage, growth quality, valuation, and accounting red flags. Calculations use annual consolidated statement values, excluding TTM columns where annual comparability matters.

## Business Insights

The Business Insights tab converts the same Screener-sourced evidence into a structured research brief. It includes five-year growth direction, profitability and capital efficiency, earnings quality, balance-sheet resilience, accounting signals, valuation context, reasons to consider or defer the company, confirmation triggers, thesis-break warnings, and an analyst due-diligence checklist.

Suggested waiting periods are review windows tied to future reported results and measurable conditions. Time passing by itself is never treated as a buy signal. The report does not cover management quality, competitive advantage, sector outlook, news, regulation, or personal suitability; those remain explicit research gaps.

This is decision support, not investment advice or a return prediction.

## Screener usage boundary

Screener's published terms permit personal, non-commercial transitory viewing and restrict copying, public display, redistribution, and commercial use. This project is configured as a local academic tool and attributes/link-backs every source observation. Do not publicly deploy, redistribute cached data, or use commercially without written permission from Screener/Mittal Analytics. Review the current terms before each deployment decision: https://www.screener.in/guides/terms/

## Tests

```bash
python -m pytest -q
```