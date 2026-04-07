# PricePilot

PricePilot is a pricing analytics and profit optimization web app for e-commerce teams. It helps founders, operators, and pricing analysts compare pricing strategies, estimate profit impact, review risk, and manage pricing decisions across a product portfolio.

## What It Does

- Analyze a single product with six pricing strategies
- Surface projected revenue, profit, margin, ROI, and break-even metrics
- Compare outcomes across `LOW`, `NORMAL`, `HIGH`, and `PROMO` market scenarios
- Keep a portfolio of products with saved pricing assumptions
- Review decision history and export portfolio or history data
- Explain recommended pricing moves in clear business language

## Product Areas

- `/` Landing page with product positioning and value messaging
- `/analyze` Pricing decision engine for single-product analysis
- `/portfolio` Multi-product pricing management view
- `/dashboard` Executive overview of strategy, scenario, and risk signals
- `/about` Product overview and capability summary

## Stack

- Python
- Flask
- HTML
- CSS
- JavaScript
- Bootstrap 5
- Chart.js
- JSON-based storage and translations

## Data Model

- Portfolio data is stored in `data/portfolio.json`
- Analysis history is stored in `data/history.json`
- Files are created automatically on first run
- The app seeds a starter portfolio so the portfolio and dashboard pages have immediate data

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

```bash
python3 -m unittest discover -s tests
```

## Project Structure

```text
project-root/
├── app.py
├── export_service.py
├── history_storage.py
├── portfolio_storage.py
├── product_defaults.py
├── pricing_engine.py
├── storage_utils.py
├── workspace_service.py
├── requirements.txt
├── README.md
├── translations/
├── templates/
├── static/
└── tests/
```
