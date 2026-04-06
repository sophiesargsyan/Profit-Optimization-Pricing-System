# PricePilot

PricePilot is a local web-based diploma project for e-commerce pricing and financial management decision support. It helps analyze product prices, compare pricing strategies, evaluate financial KPIs, simulate scenarios, optimize prices, and generate explainable recommendations in a browser-based Flask application.

## Project Summary

The project is designed for diploma thesis presentation and local demonstration. It combines:

- pricing strategy comparison
- financial KPI calculation
- scenario-based analysis
- explainable recommendation logic
- multilingual user interface

The system is intentionally simple to run and explain:

- no database
- no authentication
- no deployment configuration
- no paid external services

## Main Features

- Product pricing analysis through a structured web form
- Pricing strategies: Cost-Plus, Competitive, Demand-Based, Inventory-Based, Target-Margin, and AI Recommended
- Financial KPIs including revenue, profit, margin, ROI, contribution margin, break-even units, and risk
- Grid-search price optimization with a price-profit curve
- Scenario comparison across `LOW`, `NORMAL`, `HIGH`, and `PROMO`
- Explainable recommendation output suitable for academic defense
- Dashboard page with a demonstration KPI overview
- Multilingual interface in English, Armenian, and Russian

## Technologies

- Python
- Flask
- HTML
- CSS
- JavaScript
- Bootstrap 5
- Chart.js
- JSON-based translations

## Supported Languages

- English: `en`
- Armenian: `hy`
- Russian: `ru`

Language can be changed through the UI language switcher or with a query parameter such as:

```text
http://127.0.0.1:5000/analyze?lang=hy
```

The selected language is saved in the Flask session. If a language is not supported, the app falls back to English.

## Pricing Engine Overview

The decision engine in `pricing_engine.py` is designed to be realistic but easy to explain during a defense:

- Demand is influenced by price elasticity, competitor pricing, marketing budget, and scenario adjustments.
- Each pricing strategy is evaluated using financial KPIs and operational risk factors.
- The final recommendation uses a balanced score instead of raw profit only.
- Risk evaluation considers margin pressure, break-even feasibility, return rate, sales strength, and aggressive discount dependence.
- The optimizer uses grid search and compares candidate prices using the same balanced logic as the named strategies.

## Folder Structure

```text
pricing-diploma-system/
├── app.py
├── pricing_engine.py
├── requirements.txt
├── README.md
├── .gitignore
├── translations/
│   ├── en.json
│   ├── hy.json
│   └── ru.json
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── analyze.html
│   ├── dashboard.html
│   └── about.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
└── tests/
    └── test_pricepilot.py
```

## Installation

1. Create a virtual environment:

```bash
python3 -m venv .venv
```

2. Activate it:

```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run Locally

From the project root:

```bash
python3 app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Run Tests

The project includes a lightweight built-in test suite based on `unittest`.

Run:

```bash
python3 -m unittest discover -s tests
```

## Suggested Demo Flow

For a clean diploma defense demonstration:

1. Open the home page and briefly describe the system purpose.
2. Switch the UI language to show multilingual support.
3. Open the Analyze page and run the example product analysis.
4. Explain the recommended strategy, KPI summary, and risk level.
5. Show scenario comparison and the price-profit curve.
6. Open the Dashboard page to summarize the system modules.
7. Open the About page to explain the thesis scope and technologies.

## Notes

- The project is local-only by design.
- The UI and API are kept simple for presentation and academic explanation.
- Translations are implemented without external i18n libraries to keep the architecture easy to understand.
