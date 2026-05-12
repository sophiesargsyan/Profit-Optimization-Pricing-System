# PricePilot

PricePilot is an automated pricing strategy and financial management system developed as a diploma project for e-commerce businesses.

The platform helps small and medium-sized business owners analyze pricing decisions, estimate demand and profitability, simulate multiple pricing scenarios, and manage financial planning through a unified web-based system.

The project combines pricing analytics, demand modeling, profit optimization, and smart budget planning to support data-driven business decisions.

---

# Project Goal

The main goal of PricePilot is to improve profitability in electronic business environments by combining:

- pricing strategy analysis,
- demand sensitivity evaluation,
- profit optimization,
- financial planning,
- and automated decision support tools.

The system was developed as part of the diploma thesis:

> "Study of Profit Maximization Methods in Electronic Business and Development of an Automated Pricing Strategy and Financial Management System"

---

# Main Features

## Pricing Analysis Module

The pricing engine allows users to:

- analyze a product using multiple pricing strategies,
- evaluate projected profit and revenue,
- estimate demand changes,
- calculate contribution margin,
- simulate pricing scenarios,
- compare competitor pricing,
- identify optimal price points,
- evaluate break-even conditions,
- and generate business-oriented pricing recommendations.

### Supported Pricing Strategies

- Cost-Plus Pricing
- Competitive Pricing
- Demand-Based Pricing
- Value-Based Pricing
- Dynamic Pricing

---

## Financial Management Module

The Smart Budget Planner helps businesses:

- plan monthly budgets,
- distribute financial resources,
- estimate fixed and variable costs,
- evaluate operational sustainability,
- support financial forecasting,
- and improve financial decision-making.

The module generates automated financial recommendations based on:

- organization type,
- revenue forecast,
- operating costs,
- employee count,
- and business goals.

---

# System Capabilities

- Automated pricing analysis
- Demand and profitability modeling
- Scenario simulation
- Financial planning
- Portfolio management
- Historical analysis tracking
- Multi-language support
- Export functionality
- Responsive user interface
- Data-driven decision support

---

# Technologies Used

## Backend

- Python
- Flask

## Frontend

- HTML5
- CSS3
- JavaScript
- Bootstrap 5

## Data & Visualization

- Chart.js
- JSON-based storage

## Localization

- Armenian
- English
- Russian

---

# Project Structure

```text
pricing-diploma-system/
├── app.py
├── pricing_engine.py
├── budget_planner.py
├── financial_formatting.py
├── export_service.py
├── history_storage.py
├── portfolio_storage.py
├── workspace_service.py
├── product_defaults.py
├── data_repository.py
├── translations/
├── templates/
├── static/
├── data/
├── tests/
├── requirements.txt
└── README.md
```

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/sophiesargsyan/Profit-Optimization-Pricing-System.git
```

## 2. Open the Project

```bash
cd Profit-Optimization-Pricing-System
```

## 3. Create a Virtual Environment

```bash
python3 -m venv .venv
```

## 4. Activate the Environment

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

## 5. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Run the Application

```bash
python3 app.py
```

Open in browser:

```text
http://127.0.0.1:5000
```

---

# Run Tests

```bash
python3 -m unittest discover -s tests
```

---

# Data Storage

The project uses lightweight JSON-based storage.

Main storage files:

- `data/history.json`
- `data/portfolio.json`
- `data/finance.json`

These files are automatically created during the first application run.

---

# Academic Context

This project was developed as a diploma thesis at the National Polytechnic University of Armenia.

The system combines theoretical economic models with practical software implementation, including:

- demand analysis,
- pricing elasticity,
- profit optimization,
- break-even analysis,
- financial planning,
- and automated business decision support.

---

# Future Improvements

Planned future enhancements include:

- AI-assisted forecasting
- Machine learning demand prediction
- Real-time competitor monitoring
- Database integration
- Advanced analytics dashboards
- Cloud deployment improvements
- Role-based authentication
- Business intelligence reporting

---

# Author

Sofi Sargsyan

Information Systems Specialist

GitHub: https://github.com/sophiesargsyan

LinkedIn: https://www.linkedin.com/in/sophiesargsyan

---

# License

This project was developed for educational and research purposes.

All rights reserved © 2026 PricePilot.