import os
from pathlib import Path

from flask import Flask, jsonify, make_response, render_template, request

from investorlens.analytics import calculate_analysis
from investorlens.report import build_analyst_report, render_analyst_pdf
from investorlens.screener import ScreenerClient, ScreenerError


def create_app() -> Flask:
    app = Flask(__name__)
    client = ScreenerClient(Path(app.instance_path) / "cache")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/company/<ticker>")
    def company(ticker: str):
        try:
            data = client.get_company(ticker, refresh=request.args.get("refresh") == "1")
            data["analysis"] = calculate_analysis(data)
            return jsonify(data)
        except ScreenerError as exc:
            return jsonify({"error": str(exc)}), 422

    @app.get("/api/company/<ticker>/report")
    def company_report(ticker: str):
        try:
            data = client.get_company(ticker, refresh=request.args.get("refresh") == "1")
            analysis = calculate_analysis(data)
            report = build_analyst_report(data, analysis, ticker.upper())
            response = make_response(render_analyst_pdf(report))
            response.headers["Content-Disposition"] = f'attachment; filename="{ticker.upper()}-analyst-report.pdf"'
            response.headers["Content-Type"] = "application/pdf"
            return response
        except ScreenerError as exc:
            return jsonify({"error": str(exc)}), 422

    @app.get("/api/companies")
    def companies():
        try:
            return jsonify(client.search_companies(request.args.get("q", "")))
        except ScreenerError as exc:
            return jsonify({"error": str(exc)}), 502

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5051")), debug=True)