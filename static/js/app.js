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

function appendMetricLine(container, label, value) {
    const line = createElement("p", "highlight-meta-line");
    const strong = createElement("strong", null, `${label}: `);
    line.appendChild(strong);
    line.append(value);
    container.appendChild(line);
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

function createRiskBadge(level) {
    const normalized = String(level || "Low").toLowerCase();
    const translated = translateDynamic("risk", level || "Low");
    return createElement("span", `risk-pill risk-${normalized}`, translated);
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
    const badge = createRiskBadge(best.risk_level);
    header.append(eyebrow, badge);

    const title = createElement("h3", "highlight-card-title", strategyLabel(best.strategy));
    const subtitle = createElement(
        "p",
        "highlight-card-subtitle",
        trf("js.highlight_summary", {
            strategy: strategyLabel(best.strategy),
            price: formatCurrency(best.price),
        })
    );

    const metrics = createElement("div", "highlight-metrics");
    const metricPrice = createElement("div", "highlight-metric");
    metricPrice.append(
        createElement("span", "metric-label", tr("table.price")),
        createElement("div", "metric-value", formatCurrency(best.price))
    );
    const metricProfit = createElement("div", "highlight-metric");
    metricProfit.append(
        createElement("span", "metric-label", tr("table.profit")),
        createElement("div", "metric-value", formatCurrency(best.profit))
    );
    const metricScore = createElement("div", "highlight-metric");
    metricScore.append(
        createElement("span", "metric-label", tr("table.score")),
        createElement("div", "metric-value", formatNumber(best.balanced_score))
    );
    metrics.append(metricPrice, metricProfit, metricScore);

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
        {
            label: tr("js.best_strategy"),
            value: strategyLabel(best.strategy),
            note: trf("js.balanced_score_note", { score: formatNumber(best.balanced_score) }),
            emphasis: true,
        },
        {
            label: tr("js.recommended_price"),
            value: formatCurrency(best.price),
            note: trf("js.profit_note", { profit: formatCurrency(best.profit) }),
        },
        {
            label: tr("js.expected_margin"),
            value: `${formatNumber(best.profit_margin)}%`,
            note: trf("js.roi_note", { roi: `${formatNumber(best.ROI)}%` }),
        },
        {
            label: tr("js.risk_level"),
            value: translateDynamic("risk", best.risk_level),
            note: trf("js.risk_score_note", { score: best.risk_score }),
        },
    ];

    cards.forEach((card) => {
        const col = createElement("div", "col-md-6 col-xl-3");
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

function renderWhyRecommended(data) {
    const container = document.getElementById("whyRecommended");
    if (!container) {
        return;
    }

    container.replaceChildren();
    const best = data.best_strategy;
    const list = createElement("ul", "explanation-list mb-0");
    const reasons = [
        trf("js.why_reason_score", { score: formatNumber(best.balanced_score) }),
        trf("js.why_reason_financial", {
            profit: formatCurrency(best.profit),
            margin: formatNumber(best.profit_margin),
            roi: formatNumber(best.ROI),
        }),
        trf("js.why_reason_stability", {
            stability_score: formatNumber(best.stability_score || 0),
        }),
    ];

    if (best.comparison_context) {
        reasons.push(
            trf("js.why_reason_comparison", {
                next_strategy: strategyLabel(best.comparison_context.next_best_strategy),
                score_gap: formatNumber(best.comparison_context.score_gap),
            })
        );
    }

    if (best.risk_level === "Low") {
        reasons.push(
            trf("js.why_reason_risk_low", {
                risk_score: best.risk_score,
            })
        );
    } else if (Array.isArray(best.risk_factors) && best.risk_factors.length > 0) {
        reasons.push(
            trf("js.why_reason_risk_watch", {
                factors: best.risk_factors.join(" "),
            })
        );
    }

    reasons.forEach((reason) => {
        list.appendChild(createElement("li", null, reason));
    });

    const breakdown = createElement(
        "p",
        "why-recommended-note mt-3 mb-0",
        trf("js.score_breakdown_note", {
            profit: formatNumber(best.score_breakdown.profit_score),
            margin: formatNumber(best.score_breakdown.margin_score),
            roi: formatNumber(best.score_breakdown.roi_score),
            risk: formatNumber(best.score_breakdown.risk_adjusted_score),
            stability: formatNumber(best.score_breakdown.stability_score),
        })
    );

    container.append(list, breakdown);
}

function renderStrategyTable(strategies) {
    const tbody = document.getElementById("strategyTableBody");
    if (!tbody) {
        return;
    }

    tbody.replaceChildren();
    strategies.forEach((strategy) => {
        const row = createElement(
            "tr",
            strategy.rank === 1 ? "strategy-row-best" : ""
        );

        const rankCell = createElement("td");
        rankCell.appendChild(createElement("span", "rank-pill", `#${strategy.rank}`));
        const strategyCell = createElement("td", "fw-semibold", strategyLabel(strategy.strategy));
        const priceCell = createElement("td", null, formatCurrency(strategy.price));
        const profitCell = createElement("td", null, formatCurrency(strategy.profit));
        const marginCell = createElement("td", null, `${formatNumber(strategy.profit_margin)}%`);
        const roiCell = createElement("td", null, `${formatNumber(strategy.ROI)}%`);
        const riskCell = createElement("td");
        riskCell.appendChild(createRiskBadge(strategy.risk_level));
        const scoreCell = createElement("td", null, formatNumber(strategy.balanced_score));

        row.append(
            rankCell,
            strategyCell,
            priceCell,
            profitCell,
            marginCell,
            roiCell,
            riskCell,
            scoreCell
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
                    backgroundColor: "rgba(15, 118, 110, 0.12)",
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
        const bestStrategy = createElement(
            "p",
            "mb-1",
            `${tr("js.best_strategy")}: ${strategyLabel(scenario.best_strategy)}`
        );
        const price = createElement(
            "p",
            "mb-1",
            `${tr("table.price")}: ${formatCurrency(scenario.price)}`
        );
        const risk = createElement(
            "p",
            "mb-0",
            `${tr("table.risk")}: ${translateDynamic("risk", scenario.risk_level)}`
        );
        card.append(label, profit, bestStrategy, price, risk);
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
            labels: data.labels.map((label) => scenarioLabel(label)),
            datasets: [
                {
                    label: tr("js.chart_profit"),
                    data: data.profits,
                    backgroundColor: ["#dcecf9", "#b9ddf0", "#7cc6d6", "#2c8b97"],
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
        renderWhyRecommended(data);
        renderStrategyTable(data.strategies);
        renderPriceProfitChart(data.price_profit_curve);
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
