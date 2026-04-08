let priceProfitChart;
let scenarioChart;

const I18N = window.pricePilotI18n || {};
const CURRENT_LANG = window.pricePilotLang || "en";
const LOCALE_MAP = {
    en: "en-US",
    hy: "hy-AM",
    ru: "ru-RU",
};
const CURRENT_LOCALE = LOCALE_MAP[CURRENT_LANG] || "en-US";

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

function formatCurrency(value) {
    const amount = Number(value ?? 0);
    return new Intl.NumberFormat(CURRENT_LOCALE, {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
    }).format(amount);
}

function formatNumber(value, digits = 2) {
    const amount = Number(value ?? 0);
    return amount.toLocaleString(CURRENT_LOCALE, {
        minimumFractionDigits: 0,
        maximumFractionDigits: digits,
    });
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

function renderBestStrategyHighlight(data) {
    const container = document.getElementById("bestStrategyHighlight");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const best = data.best_strategy;
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
            demand: formatNumber(best.demand, 0),
            profit: formatCurrency(best.profit),
        })
    );

    const metrics = createElement("div", "highlight-metrics");
    const revenueMetric = createElement("div", "highlight-metric");
    revenueMetric.append(
        createElement("span", "metric-label", tr("table.expected_revenue")),
        createElement("div", "metric-value", formatCurrency(best.revenue))
    );
    const profitMetric = createElement("div", "highlight-metric");
    profitMetric.append(
        createElement("span", "metric-label", tr("table.expected_profit")),
        createElement("div", "metric-value", formatCurrency(best.profit))
    );
    const marginMetric = createElement("div", "highlight-metric");
    marginMetric.append(
        createElement("span", "metric-label", tr("table.margin")),
        createElement("div", "metric-value", `${formatNumber(best.profit_margin)}%`)
    );
    metrics.append(revenueMetric, profitMetric, marginMetric);

    card.append(header, title, subtitle, metrics);
    container.appendChild(card);
}

function renderSummaryCards(data) {
    const container = document.getElementById("analysisSummary");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const best = data.best_strategy;
    const cards = [
        { label: tr("js.recommended_price"), value: formatCurrency(best.price), note: strategyLabel(best.strategy), emphasis: true },
        { label: tr("table.expected_demand"), value: formatNumber(best.demand, 0), note: tr("js.units_note", "Projected units") },
        { label: tr("table.expected_revenue"), value: formatCurrency(best.revenue), note: tr("js.revenue_note", "Projected monthly revenue") },
        { label: tr("table.expected_profit"), value: formatCurrency(best.profit), note: tr("js.profit_note_short", "Projected monthly profit") },
        { label: tr("table.margin"), value: `${formatNumber(best.profit_margin)}%`, note: trf("js.target_margin_note", { margin: `${formatNumber(best.target_margin)}%` }) },
        { label: tr("table.confidence"), value: translateDynamic("confidence", data.overall_confidence.level), note: trf("js.confidence_note", { score: formatNumber(data.overall_confidence.score) }) },
    ];

    cards.forEach((card) => {
        const col = createElement("div", "col-md-6 col-xl-4");
        const wrapper = createElement(
            "div",
            `metric-card summary-card${card.emphasis ? " summary-card-primary" : ""}`
        );
        wrapper.append(
            createElement("span", "metric-label", card.label),
            createElement("div", "metric-value", card.value),
            createElement("p", "metric-note", card.note)
        );
        col.appendChild(wrapper);
        container.appendChild(col);
    });
}

function renderExplanation(data) {
    const block = document.getElementById("explanationBlock");
    const scenarioBadge = document.getElementById("scenarioLabel");
    if (!block || !scenarioBadge) {
        return;
    }

    block.replaceChildren();
    scenarioBadge.textContent = trf("js.scenario_prefix", {
        scenario: scenarioLabel(data.product.scenario),
    });

    block.append(
        createElement("h4", "mb-2", data.explanation.title),
        createElement("p", "text-muted mb-3", data.explanation.summary)
    );

    const detailList = createElement("ul", "explanation-list mb-0");
    data.explanation.details.forEach((detail) => {
        detailList.appendChild(createElement("li", null, detail));
    });
    block.appendChild(detailList);

    if (data.explanation.caution) {
        block.appendChild(createElement("div", "alert alert-warning mt-3 mb-0", data.explanation.caution));
    }
}

function renderAssumptions(data) {
    const container = document.getElementById("assumptionGrid");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const cards = data.explanation.assumption_cards || [];
    if (cards.length === 0) {
        container.appendChild(createElement("div", "empty-state", tr("analyze.empty_assumptions")));
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

function renderWhyRecommended(data) {
    const container = document.getElementById("whyRecommended");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const reasons = data.explanation.why_recommended || [];
    if (reasons.length === 0) {
        container.textContent = tr("analyze.empty_recommendation_reason");
        return;
    }

    const list = createElement("ul", "explanation-list mb-0");
    reasons.forEach((reason) => {
        list.appendChild(createElement("li", null, reason));
    });
    container.appendChild(list);
}

function renderStrategyTable(strategies) {
    const tbody = document.getElementById("strategyTableBody");
    if (!tbody) {
        return;
    }

    tbody.replaceChildren();
    strategies.forEach((strategy) => {
        const row = createElement("tr", strategy.rank === 1 ? "strategy-row-best" : "");
        const rankCell = createElement("td");
        rankCell.appendChild(createElement("span", "rank-pill", `#${strategy.rank}`));

        const optionCell = createElement("td", "fw-semibold", strategyLabel(strategy.strategy));
        const priceCell = createElement("td", null, formatCurrency(strategy.price));
        const demandCell = createElement("td", null, formatNumber(strategy.demand, 0));
        const revenueCell = createElement("td", null, formatCurrency(strategy.revenue));
        const profitCell = createElement("td", null, formatCurrency(strategy.profit));
        const marginCell = createElement("td", null, `${formatNumber(strategy.profit_margin)}%`);
        const confidenceCell = createElement("td");
        confidenceCell.appendChild(createConfidenceBadge(strategy.confidence_level));

        row.append(
            rankCell,
            optionCell,
            priceCell,
            demandCell,
            revenueCell,
            profitCell,
            marginCell,
            confidenceCell
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
    if (!analyzeBtn || !scenarioBtn) {
        return;
    }

    analyzeBtn.disabled = isLoading;
    scenarioBtn.disabled = isLoading;
    analyzeBtn.textContent = isLoading ? tr("js.analyzing") : tr("analyze.run_full_analysis");
}

async function runAnalysis(form, options = {}) {
    setAlert("");
    setLoading(true);
    setStatus(tr("js.running_analysis"));

    try {
        const payload = formPayload(form);
        const data = await postJson("/api/analyze", {
            ...payload,
            save_history: options.saveHistory !== false,
        });
        renderBestStrategyHighlight(data);
        renderSummaryCards(data);
        renderExplanation(data);
        renderAssumptions(data);
        renderWhyRecommended(data);
        renderStrategyTable(data.strategies);
        renderPriceProfitChart(data.price_profit_curve);
        setConfidenceBadge(data.overall_confidence.level);
        setStatus(
            trf("js.best_strategy_status", {
                strategy: strategyLabel(data.best_strategy.strategy),
            })
        );
    } catch (error) {
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

    runAnalysis(form, { saveHistory: false });
});
