let priceProfitChart;
let scenarioChart;

const I18N = window.pricePilotI18n || {};
const DEFAULT_FORMAT_CONFIG = {
    currencyCode: "USD",
    currencySymbol: "USD",
    currencySpaceBetween: true,
    emptyDisplay: "—",
    defaultCurrencyDigits: 2,
    defaultPercentDigits: 1,
};
const FORMAT_CONFIG = window.pricePilotFormatting || DEFAULT_FORMAT_CONFIG;
const NUMBER_LOCALE = "en-US";

function tr(key, fallback = "") {
    return I18N[key] ?? fallback ?? key;
}

function trf(key, values = {}, fallback = "") {
    const template = tr(key, fallback || key);
    return template.replace(/\{(\w+)\}/g, (_, name) => values[name] ?? `{${name}}`);
}

function translateDynamic(prefix, value) {
    return tr(`${prefix}.${value}`, value);
}

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) {
        element.className = className;
    }
    if (text !== undefined) {
        element.textContent = text;
    }
    return element;
}

function isEmptyValue(value) {
    return value === null || value === undefined || value === "";
}

function formatNumber(value, digits = 2) {
    if (isEmptyValue(value)) {
        return FORMAT_CONFIG.emptyDisplay;
    }

    const amount = Number(value);
    return new Intl.NumberFormat(NUMBER_LOCALE, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    }).format(amount);
}

function formatPercent(value, digits = FORMAT_CONFIG.defaultPercentDigits ?? 1) {
    if (isEmptyValue(value)) {
        return FORMAT_CONFIG.emptyDisplay;
    }
    return `${formatNumber(value, digits)}%`;
}

function formatCurrency(value, digits = FORMAT_CONFIG.defaultCurrencyDigits ?? 2) {
    if (isEmptyValue(value)) {
        return FORMAT_CONFIG.emptyDisplay;
    }

    const amount = Number(value);
    const absoluteAmount = formatNumber(Math.abs(amount), digits);
    const symbol = FORMAT_CONFIG.currencySymbol || FORMAT_CONFIG.currencyCode || "USD";
    const body = FORMAT_CONFIG.currencySpaceBetween ? `${symbol} ${absoluteAmount}` : `${symbol}${absoluteAmount}`;
    return amount < 0 ? `-${body}` : body;
}

function formatSignedCurrency(value) {
    if (isEmptyValue(value)) {
        return FORMAT_CONFIG.emptyDisplay;
    }

    const amount = Number(value);
    if (amount > 0) {
        return `+${formatCurrency(amount)}`;
    }
    if (amount < 0) {
        return `-${formatCurrency(Math.abs(amount))}`;
    }
    return formatCurrency(0);
}

function createConfidenceBadge(level) {
    const normalized = String(level || "Low").toLowerCase();
    const translated = translateDynamic("confidence", level || "Low");
    return createElement("span", `confidence-pill confidence-${normalized}`, translated);
}

function strategyLabel(name) {
    return translateDynamic("strategy", name);
}

function scenarioLabel(code) {
    return translateDynamic("scenario", code);
}

function riskLabel(level) {
    return translateDynamic("risk", level || "Medium");
}

function formatCompetitorPosition(gap) {
    const numericGap = Number(gap ?? 0);
    const absoluteGap = formatNumber(Math.abs(numericGap), 1);
    if (numericGap > 0.5) {
        return trf("position.below_competitor", { gap: absoluteGap }, "{gap}% below competitor reference");
    }
    if (numericGap < -0.5) {
        return trf("position.above_competitor", { gap: absoluteGap }, "{gap}% above competitor reference");
    }
    return tr("position.near_competitor", "Near competitor reference");
}

async function postJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    const json = await response.json();
    if (!response.ok || !json.success) {
        throw new Error(json.error || tr("js.request_failed", "Request failed."));
    }

    return json.data;
}

function formPayload(form) {
    return Object.fromEntries(new FormData(form).entries());
}

function setAlert(message = "") {
    const alert = document.getElementById("formAlert");
    if (!alert) {
        return;
    }

    if (!message) {
        alert.classList.add("d-none");
        alert.textContent = "";
        return;
    }

    alert.textContent = message;
    alert.classList.remove("d-none");
}

function setStatus(message, muted = false) {
    const status = document.getElementById("analysisStatus");
    if (!status) {
        return;
    }
    status.textContent = message;
    status.classList.toggle("text-muted", muted);
}

function setConfidenceBadge(level) {
    const target = document.getElementById("analysisConfidence");
    if (!target) {
        return;
    }
    target.textContent = trf("js.confidence_status", {
        confidence: translateDynamic("confidence", level || "Low"),
    });
}

function recommendationPrimaryReason(strategyName) {
    if (strategyName === "Current Price") {
        return tr(
            "js.recommendation_reason_current",
            "Current price already offers the strongest balance of return and risk."
        );
    }

    if (strategyName === "Competitive Parity") {
        return tr(
            "js.recommendation_reason_parity",
            "Aligned close to the market reference to stay competitive without over-discounting."
        );
    }

    return tr(
        "js.recommendation_reason_profit",
        "Optimized for maximum profit under the current demand outlook."
    );
}

function recommendationMarketReason(gap) {
    const numericGap = Number(gap ?? 0);
    if (numericGap > 0.5) {
        return tr(
            "js.recommendation_position_below",
            "Positioned below competitor reference to support sales volume."
        );
    }

    if (numericGap < -0.5) {
        return tr(
            "js.recommendation_position_above",
            "Positioned above competitor reference to protect margin where demand stays resilient."
        );
    }

    return tr(
        "js.recommendation_position_near",
        "Positioned near competitor reference to balance conversion and margin."
    );
}

function recommendationRiskReason(level, scenario) {
    const scenarioName = scenarioLabel(scenario);
    const normalized = String(level || "Medium").toLowerCase();

    if (normalized === "low") {
        return trf(
            "js.recommendation_risk_low",
            { scenario: scenarioName },
            "Low execution risk under the current {scenario} scenario."
        );
    }

    if (normalized === "high") {
        return trf(
            "js.recommendation_risk_high",
            { scenario: scenarioName },
            "Higher execution risk, so rollout should be monitored in the current {scenario} scenario."
        );
    }

    return trf(
        "js.recommendation_risk_medium",
        { scenario: scenarioName },
        "Moderate execution risk under the current {scenario} scenario."
    );
}

function buildRecommendationBullets(data) {
    const best = data.best_strategy;
    return [
        recommendationPrimaryReason(best.strategy),
        recommendationMarketReason(best.price_gap_vs_competitor),
        recommendationRiskReason(best.risk_level, data.product.scenario),
    ];
}

function selectStrategyComparisonRows(strategies) {
    const strategyMap = new Map(strategies.map((strategy) => [strategy.strategy, strategy]));
    return [
        "Profit Optimal",
        "Current Price",
        "Competitive Parity",
    ]
        .map((strategyName) => strategyMap.get(strategyName))
        .filter(Boolean);
}

function setScenarioComparisonVisible(isVisible) {
    const card = document.getElementById("scenarioComparisonCard");
    if (!card) {
        return;
    }
    card.hidden = !isVisible;
}

function setAnalysisResultsVisible(isVisible) {
    const shell = document.getElementById("analysisResultsShell");
    if (!shell) {
        return;
    }
    shell.hidden = !isVisible;
}

function renderBestStrategyHighlight(data) {
    const container = document.getElementById("bestStrategyHighlight");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const best = data.best_strategy;
    const currentProfit = Number(data.current_option?.profit ?? NaN);
    const profitChange = Number.isNaN(currentProfit) ? null : best.profit - currentProfit;
    const card = createElement("div", "highlight-card");
    const header = createElement("div", "highlight-card-header");
    const eyebrow = createElement("span", "metric-label", tr("js.highlight_label"));
    const confidenceBadge = createConfidenceBadge(data.overall_confidence.level);
    header.append(eyebrow, confidenceBadge);

    const title = createElement("h3", "highlight-card-title", formatCurrency(best.price));
    const subtitle = createElement(
        "p",
        "highlight-card-subtitle",
        trf("js.highlight_summary", {
            strategy: strategyLabel(best.strategy),
            scenario: scenarioLabel(data.product.scenario),
        })
    );

    const comparison = createElement("div", "highlight-metric recommendation-impact");
    const comparisonValue = createElement(
        "div",
        `metric-value${profitChange > 0 ? " text-success" : profitChange < 0 ? " text-danger" : ""}`,
        profitChange === null ? tr("js.profit_change_pending", "Pending") : formatSignedCurrency(profitChange)
    );
    comparison.append(
        createElement("span", "metric-label", tr("js.profit_change")),
        comparisonValue
    );

    const summaryList = createElement("ul", "explanation-list mt-3 mb-0");
    buildRecommendationBullets(data).forEach((bullet) => {
        summaryList.appendChild(createElement("li", null, bullet));
    });

    card.append(header, title, subtitle, comparison, summaryList);
    container.appendChild(card);
}

function renderFinancialImpact(data) {
    const container = document.getElementById("financialImpactGrid");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const best = data.best_strategy;
    const cards = [
        {
            label: tr("table.expected_revenue"),
            value: formatCurrency(best.revenue),
        },
        {
            label: tr("table.total_cost", tr("js.total_cost", "Projected total cost")),
            value: formatCurrency(best.total_cost),
        },
        {
            label: tr("table.expected_profit"),
            value: formatCurrency(best.profit),
            emphasis: true,
        },
    ];

    cards.forEach((card) => {
        const col = createElement("div", "col-md-6 col-xl-4");
        const wrapper = createElement(
            "div",
            `metric-card summary-card${card.emphasis ? " summary-card-primary" : ""}`
        );
        wrapper.append(
            createElement("span", "metric-label", card.label),
            createElement("div", "metric-value", card.value)
        );
        col.appendChild(wrapper);
        container.appendChild(col);
    });
}

function renderAdvancedMetrics(data) {
    const container = document.getElementById("advancedMetricGrid");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const best = data.best_strategy;
    const cards = [
        {
            label: tr("table.margin"),
            value: formatPercent(best.profit_margin),
        },
        {
            label: tr("table.expected_demand"),
            value: formatNumber(best.demand, 0),
        },
        {
            label: tr("js.market_position"),
            value: formatCompetitorPosition(best.price_gap_vs_competitor),
            compact: true,
        },
        {
            label: tr("js.risk_level"),
            value: riskLabel(best.risk_level),
        },
    ];

    cards.forEach((card) => {
        const col = createElement("div", "col-md-6 col-xl-3");
        const wrapper = createElement("div", "metric-card summary-card");
        wrapper.append(
            createElement("span", "metric-label", card.label),
            createElement(
                "div",
                `metric-value${card.compact ? " metric-value-compact" : ""}`,
                card.value
            )
        );
        col.appendChild(wrapper);
        container.appendChild(col);
    });
}

function renderAssumptions(data) {
    const container = document.getElementById("assumptionGrid");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const cards = data.explanation.assumption_cards || [];
    if (cards.length === 0) {
        container.appendChild(createElement("div", "empty-panel", tr("analyze.empty_assumptions")));
        return;
    }

    cards.forEach((item) => {
        const card = createElement("div", "assumption-card");
        card.append(
            createElement("span", "metric-label", item.label),
            createElement("h3", null, item.value),
            createElement("p", "mb-2", item.source)
        );
        card.appendChild(createConfidenceBadge(item.confidence));
        container.appendChild(card);
    });
}

function renderStrategyTable(strategies, bestStrategyName) {
    const tbody = document.getElementById("strategyTableBody");
    if (!tbody) {
        return;
    }

    tbody.replaceChildren();
    const rows = selectStrategyComparisonRows(strategies);

    rows.forEach((strategy) => {
        const row = createElement("tr", strategy.strategy === bestStrategyName ? "strategy-row-best" : "");
        const optionCell = createElement("td", "fw-semibold", strategyLabel(strategy.strategy));
        const priceCell = createElement("td", "table-number", formatCurrency(strategy.price));
        const revenueCell = createElement("td", "table-number", formatCurrency(strategy.revenue));
        const costCell = createElement("td", "table-number", formatCurrency(strategy.total_cost));
        const profitCell = createElement("td", "table-number", formatCurrency(strategy.profit));

        row.append(
            optionCell,
            priceCell,
            revenueCell,
            costCell,
            profitCell,
        );
        tbody.appendChild(row);
    });
}

function renderPriceProfitChart(curve) {
    const canvas = document.getElementById("priceProfitChart");
    if (!canvas) {
        return;
    }

    if (priceProfitChart) {
        priceProfitChart.destroy();
    }

    priceProfitChart = new Chart(canvas, {
        type: "line",
        data: {
            labels: curve.map((point) => point.price),
            datasets: [
                {
                    label: tr("js.chart_profit"),
                    data: curve.map((point) => point.profit),
                    borderColor: "#0f172a",
                    backgroundColor: "rgba(11, 121, 138, 0.14)",
                    tension: 0.32,
                    fill: true,
                    pointRadius: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: tr("js.chart_price"),
                    },
                },
                y: {
                    title: {
                        display: true,
                        text: tr("js.chart_profit"),
                    },
                },
            },
        },
    });
}

function renderScenarioSummary(data) {
    const container = document.getElementById("scenarioSummary");
    const winning = document.getElementById("winningScenario");
    if (!container || !winning) {
        return;
    }

    winning.textContent = trf("js.winning_scenario", {
        scenario: scenarioLabel(data.winning_scenario),
    });
    container.replaceChildren();

    data.scenarios.forEach((scenario) => {
        const col = createElement("div", "col-md-6 col-xl-3");
        const card = createElement("div", "scenario-mini-card");
        const label = createElement("span", "metric-label", scenarioLabel(scenario.scenario));
        const profit = createElement("h3", null, formatCurrency(scenario.profit));
        const bestStrategy = createElement("p", "mb-1", `${tr("table.option")}: ${strategyLabel(scenario.best_strategy)}`);
        const price = createElement("p", "mb-1", `${tr("table.price")}: ${formatCurrency(scenario.price)}`);
        const demand = createElement("p", "mb-2", `${tr("table.expected_demand")}: ${formatNumber(scenario.demand, 0)}`);
        card.append(label, profit, bestStrategy, price, demand);
        card.appendChild(createConfidenceBadge(scenario.confidence_level));
        col.appendChild(card);
        container.appendChild(col);
    });
}

function renderScenarioChart(data) {
    const canvas = document.getElementById("scenarioChart");
    if (!canvas) {
        return;
    }

    if (scenarioChart) {
        scenarioChart.destroy();
    }

    scenarioChart = new Chart(canvas, {
        type: "bar",
        data: {
            labels: data.scenarios.map((item) => scenarioLabel(item.scenario)),
            datasets: [
                {
                    label: tr("js.chart_profit"),
                    data: data.scenarios.map((item) => item.profit),
                    backgroundColor: ["#dbeaf4", "#b7d6e6", "#6fb2bf", "#1d6f7a"],
                    borderRadius: 10,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    title: {
                        display: true,
                        text: tr("js.chart_profit"),
                    },
                },
            },
        },
    });
}

function setLoading(isLoading) {
    const analyzeBtn = document.getElementById("analyzeBtn");
    const scenarioBtn = document.getElementById("scenarioCompareBtn");
    if (!analyzeBtn) {
        return;
    }

    analyzeBtn.disabled = isLoading;
    if (scenarioBtn) {
        scenarioBtn.disabled = isLoading;
    }
    analyzeBtn.textContent = isLoading ? tr("js.analyzing") : tr("analyze.run_full_analysis");
}

async function runAnalysis(form, options = {}) {
    setAlert("");
    setAnalysisResultsVisible(false);
    setScenarioComparisonVisible(false);
    setLoading(true);
    setStatus(tr("js.running_analysis"));

    try {
        const payload = formPayload(form);
        const data = await postJson("/api/analyze", {
            ...payload,
            save_history: options.saveHistory !== false,
        });
        setAnalysisResultsVisible(true);
        renderBestStrategyHighlight(data);
        renderFinancialImpact(data);
        renderAdvancedMetrics(data);
        renderAssumptions(data);
        renderStrategyTable(data.strategies, data.best_strategy.strategy);
        renderPriceProfitChart(data.price_profit_curve);
        setConfidenceBadge(data.overall_confidence.level);
        setStatus(
            trf("js.best_strategy_status", {
                strategy: strategyLabel(data.best_strategy.strategy),
            })
        );
    } catch (error) {
        setAnalysisResultsVisible(false);
        setAlert(error.message);
        setStatus(tr("js.analysis_failed"), true);
    } finally {
        setLoading(false);
    }
}

async function runScenarioComparison(form) {
    setAlert("");
    setStatus(tr("js.comparing_scenarios"));

    try {
        const payload = formPayload(form);
        const data = await postJson("/api/scenario-compare", payload);
        setScenarioComparisonVisible(true);
        renderScenarioSummary(data);
        renderScenarioChart(data);
        setStatus(
            trf("js.scenario_complete", {
                scenario: scenarioLabel(data.winning_scenario),
            })
        );
    } catch (error) {
        setAlert(error.message);
        setStatus(tr("js.scenario_failed"), true);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("analysisForm");
    if (!form) {
        return;
    }

    const advancedPanel = document.querySelector(".analysis-advanced-fields");
    const advancedToggleText = document.querySelector(".analysis-advanced-toggle-text");
    if (advancedPanel && advancedToggleText) {
        const syncAdvancedToggleText = () => {
            advancedToggleText.textContent = advancedPanel.open
                ? advancedToggleText.dataset.openLabel
                : advancedToggleText.dataset.closedLabel;
        };

        syncAdvancedToggleText();
        advancedPanel.addEventListener("toggle", syncAdvancedToggleText);
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await runAnalysis(form, { saveHistory: true });
    });

    const scenarioButton = document.getElementById("scenarioCompareBtn");
    if (scenarioButton) {
        scenarioButton.addEventListener("click", async () => {
            await runScenarioComparison(form);
        });
    }
});
