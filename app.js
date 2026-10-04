// Empty string = same-origin requests. The FastAPI backend now serves this
// page directly at http://127.0.0.1:8000/, so relative paths just work.
// If you ever go back to serving the frontend from a separate static
// server, set this to "http://127.0.0.1:8000" again.
const API_BASE = "";

// ===== Auth guard =====
const token = localStorage.getItem("access_token");
if (!token) {
  window.location.href = "login.html";
}

async function authFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("access_token");
    window.location.href = "login.html";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    throw new Error(`Request failed: ${path} (${res.status})`);
  }
  return res.json();
}

function fmtMoney(n) {
  return "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
}
function fmtPct(n, withSign = false) {
  const s = Number(n).toFixed(2) + "%";
  return withSign && n > 0 ? "+" + s : s;
}
function setText(field, text) {
  const el = document.querySelector(`[data-field="${field}"]`);
  if (el) el.textContent = text;
}

// ===== Section navigation =====
const navItems = document.querySelectorAll(".nav-item");
const views = document.querySelectorAll(".view");
const pageTitle = document.getElementById("pageTitle");

const TITLES = {
  dashboard: "Dashboard",
  portfolio: "Portfolio",
  optimize: "Optimize",
  rebalance: "Rebalance",
  risk: "Risk Analysis",
  ask: "Ask",
};

const SECTION_LOADERS = {
  dashboard: loadDashboard,
  portfolio: loadPortfolio,
  risk: loadRisk,
};
const loadedSections = new Set();

navItems.forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.section;

    navItems.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    views.forEach((v) => v.classList.remove("active"));
    document.getElementById(`view-${target}`).classList.add("active");

    pageTitle.textContent = TITLES[target];

    if (!loadedSections.has(target) && SECTION_LOADERS[target]) {
      loadedSections.add(target);
      SECTION_LOADERS[target]().catch((err) => console.error(err));
    }
  });
});

// ===== Ask (RAG) =====
document.getElementById("askForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("askInput");
  const question = input.value.trim();
  if (!question) return;

  const btn = document.getElementById("askSubmitBtn");
  const resultPanel = document.getElementById("askResultPanel");
  const answerEl = document.querySelector('[data-field="ask-answer"]');
  const sourcesEl = document.querySelector('[data-field="ask-sources"]');

  btn.disabled = true;
  btn.textContent = "Thinking...";
  resultPanel.style.display = "block";
  answerEl.textContent = "";
  sourcesEl.innerHTML = "";

  try {
    const result = await authFetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    answerEl.textContent = result.answer;
    sourcesEl.innerHTML = result.sources.map((s) => `
      <div class="ask-source-row">
        <span class="wc-label">${s.ticker}</span>
        <span class="ask-source-text">${s.text}</span>
      </div>`).join("");
  } catch (err) {
    console.error(err);
    answerEl.textContent = "Something went wrong. Check that the API server is running.";
  } finally {
    btn.disabled = false;
    btn.textContent = "Ask";
  }
});


// ===== Logout =====
document.getElementById("logoutBtn").addEventListener("click", () => {
  localStorage.removeItem("access_token");
  window.location.href = "login.html";
});

// ===== Dashboard =====
async function loadDashboard() {
  const d = await authFetch("/api/dashboard");

  setText("total-value", fmtMoney(d.totalValue));
  setText("total-value-delta", fmtPct(d.totalValueDeltaPct, true) + " today");
  document.querySelector('[data-field="total-value-delta"]').classList.add(d.totalValueDeltaPct >= 0 ? "up" : "down");

  setText("pnl", (d.pnl >= 0 ? "+" : "") + fmtMoney(d.pnl));
  document.querySelector('[data-field="pnl"]').classList.add(d.pnl >= 0 ? "up" : "down");
  setText("pnl-delta", fmtPct(d.pnlPct, true) + " all-time");

  setText("return-ytd", fmtPct(d.returnYtdPct, true));
  document.querySelector('[data-field="return-ytd"]').classList.add(d.returnYtdPct >= 0 ? "up" : "down");
  setText("return-benchmark", `vs ${fmtPct(d.benchmarkYtdPct, true)} benchmark`);

  setText("volatility", fmtPct(d.volatilityPct));
  setText("volatility-note", "252d realized");

  setText("drawdown", fmtPct(d.maxDrawdownPct));
  setText("drawdown-note", d.drawdownWindow);

  renderLineChart(document.getElementById("chart-value"), d.valueSeries);
  renderDrawdownChart(document.getElementById("chart-drawdown"), d.drawdownSeries);
}

// ===== Portfolio =====
async function loadPortfolio() {
  const p = await authFetch("/api/portfolio/holdings");

  setText("cash-balance", fmtMoney(p.cashBalance));

  const tbody = document.querySelector('[data-field="holdings-body"]');
  tbody.innerHTML = p.holdings.map((h) => `
    <tr>
      <td>${h.ticker}</td>
      <td>${h.name}</td>
      <td>${h.assetClass}</td>
      <td>${h.qty}</td>
      <td>$${h.price.toFixed(2)}</td>
      <td>${fmtMoney(h.marketValue)}</td>
      <td>${h.currentWeightPct.toFixed(2)}%</td>
      <td>${h.targetWeightPct.toFixed(2)}%</td>
    </tr>`).join("");

  renderDonut(
    document.getElementById("chart-allocation"),
    p.allocationByAssetClass.map((a) => ({ label: a.assetClass, value: a.value, weightPct: a.weightPct }))
  );

  renderWeightCompare(document.getElementById("chart-weights"), p.holdings);
}

// ===== Optimize =====
document.getElementById("runOptimizeBtn")?.addEventListener("click", async (e) => {
  const btn = e.target;
  btn.disabled = true;
  btn.textContent = "Running...";
  try {
    const payload = {
      portfolio: document.getElementById("opt-portfolio").value,
      risk_profile: document.getElementById("opt-risk-profile").value,
      method: document.getElementById("opt-method").value,
      min_weight: Number(document.getElementById("c-min-weight").value),
      max_weight: Number(document.getElementById("c-max-weight").value),
      max_sector_exposure: Number(document.getElementById("c-max-sector").value),
      target_volatility: Number(document.getElementById("c-target-vol").value) || null,
      long_only: document.getElementById("c-long-only").checked,
      cash_buffer: document.getElementById("c-cash-buffer").checked,
    };

    const result = await authFetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    renderScatter(document.getElementById("chart-frontier"), result.frontier);

    const panel = document.getElementById("chart-frontier").closest(".panel");
    let summary = panel.querySelector(".opt-summary");
    if (!summary) {
      summary = document.createElement("div");
      summary.className = "opt-summary panel-note";
      panel.insertBefore(summary, document.getElementById("chart-frontier"));
    }
    summary.innerHTML = `<strong>${result.method}</strong> — expected return ${result.expectedReturnPct}%,
      volatility ${result.expectedVolatilityPct}%, Sharpe ${result.sharpeRatio}.
      Target weights are cached for the Rebalance tab.`;
  } catch (err) {
    console.error(err);
    alert("Optimization failed. Check that the API server is running.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Optimization";
  }
});

// ===== Rebalance =====
document.getElementById("applyRebalanceBtn")?.addEventListener("click", async (e) => {
  const btn = e.target;
  btn.disabled = true;
  btn.textContent = "Generating...";
  try {
    const result = await authFetch("/api/rebalance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_last_optimization: true }),
    });

    const tbody = document.querySelector('[data-field="rebalance-body"]');
    tbody.innerHTML = result.holdings.map((r) => `
      <tr>
        <td>${r.ticker}</td>
        <td class="action-${r.action.toLowerCase()}">${r.action}</td>
        <td>${r.currentWeightPct.toFixed(2)}%</td>
        <td>${r.targetWeightPct.toFixed(2)}%</td>
        <td>${r.deltaWeightPct >= 0 ? "+" : ""}${r.deltaWeightPct.toFixed(2)}%</td>
        <td>${r.estShares}</td>
        <td>${r.estValue >= 0 ? "+" : ""}${fmtMoney(r.estValue)}</td>
      </tr>`).join("");

    setText("turnover", fmtPct(result.turnoverPct));
    setText("txn-cost", fmtMoney(result.estimatedCost));
    setText("trade-count", result.tradeCount);

    renderWeightCompare(document.getElementById("chart-rebalance"), result.holdings.map(h => ({
      ticker: h.ticker, currentWeightPct: h.currentWeightPct, targetWeightPct: h.targetWeightPct,
    })));
  } catch (err) {
    console.error(err);
    alert("Rebalance plan failed. Run an optimization first, and check the API server is running.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Rebalance Plan";
  }
});

// ===== Risk Analysis =====
async function loadRisk() {
  const r = await authFetch("/api/risk");

  setText("risk-volatility", fmtPct(r.volatilityPct));
  setText("risk-var", fmtPct(r.var95Pct));
  setText("risk-cvar", fmtPct(r.cvar95Pct));

  renderHeatmap(
    document.getElementById("chart-correlation"),
    r.correlationMatrix.tickers,
    r.correlationMatrix.matrix
  );

  renderBarList(document.getElementById("chart-vol-contrib"), r.volatilityContribution);

  renderHistogram(document.getElementById("chart-var-dist"), r.returnDistribution, {
    varLine: r.var95Pct,
    cvarLine: r.cvar95Pct,
  });
}

async function askPortfolio(question) {
  return authFetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}


// ===== Initial load =====
loadDashboard().catch((err) => console.error(err));
loadedSections.add("dashboard");