// Minimal chart helpers — no external chart library, pure SVG/CSS.
// Colors pulled from CSS custom properties so it matches the light theme.

const cssVar = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function svgEl(viewBox) {
  // No inline width/height here on purpose — style.css sizes `.chart-placeholder svg`
  // explicitly (100% x 228px). Inline styles would win over that CSS and can
  // resolve to 0 height against an auto-height parent. "xMidYMid meet" keeps
  // lines, dots and rotated axis labels from stretching out of shape.
  return `<svg viewBox="${viewBox}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">`;
}

// ---- Line chart (e.g. portfolio value over time) ----
function renderLineChart(container, series, { valueSuffix = "" } = {}) {
  if (!series || series.length < 2) return;
  const W = 600, H = 220, PAD = 24;
  const values = series.map((d) => d.value);
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;

  const points = series.map((d, i) => {
    const x = PAD + (i / (series.length - 1)) * (W - PAD * 2);
    const y = H - PAD - ((d.value - min) / range) * (H - PAD * 2);
    return [x, y];
  });

  const linePath = points.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const areaPath = linePath + ` L${points[points.length - 1][0]},${H - PAD} L${points[0][0]},${H - PAD} Z`;

  const accent = cssVar("--accent") || "#3E6483";
  const first = series[0].value, last = series[series.length - 1].value;
  const up = last >= first;
  const lineColor = up ? (cssVar("--up") || "#1E8A57") : (cssVar("--down") || "#C13B3B");

  container.innerHTML = `
    ${svgEl(`0 0 ${W} ${H}`)}
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${lineColor}" stop-opacity="0.18"/>
          <stop offset="100%" stop-color="${lineColor}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="${areaPath}" fill="url(#areaGrad)" stroke="none"/>
      <path d="${linePath}" fill="none" stroke="${lineColor}" stroke-width="2"/>
    </svg>`;
}

// ---- Area chart for drawdown (values are negative/zero) ----
function renderDrawdownChart(container, series) {
  if (!series || series.length < 2) return;
  const W = 600, H = 220, PAD = 20;
  const values = series.map((d) => d.value);
  const min = Math.min(...values, 0);
  const range = Math.abs(min) || 1;

  const zeroY = PAD;
  const points = series.map((d, i) => {
    const x = PAD + (i / (series.length - 1)) * (W - PAD * 2);
    const y = zeroY + (Math.abs(d.value) / range) * (H - PAD * 2);
    return [x, y];
  });

  const linePath = points.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const areaPath = `M${points[0][0]},${zeroY} ` + linePath.slice(linePath.indexOf(" ") + 1) +
    ` L${points[points.length - 1][0]},${zeroY} Z`;

  const down = cssVar("--down") || "#C13B3B";

  container.innerHTML = `
    ${svgEl(`0 0 ${W} ${H}`)}
      <line x1="${PAD}" y1="${zeroY}" x2="${W - PAD}" y2="${zeroY}" stroke="${cssVar('--border') || '#DDE1E7'}" stroke-width="1"/>
      <path d="${areaPath}" fill="${down}" fill-opacity="0.12" stroke="none"/>
      <path d="${linePath}" fill="none" stroke="${down}" stroke-width="2"/>
    </svg>`;
}

// ---- Donut chart (allocation by asset class) ----
function renderDonut(container, data) {
  // data: [{label, value, weightPct}]
  const palette = ["#3E6483", "#6E9BBE", "#8FB3CC", "#B7D0E0", "#D7E4EC", "#9AA5B1", "#C7CDD5"];
  const total = data.reduce((s, d) => s + d.value, 0);
  let cumulative = 0;

  const R = 70, CX = 90, CY = 90, STROKE = 26;
  const circumference = 2 * Math.PI * R;

  const segments = data.map((d, i) => {
    const frac = d.value / total;
    const dash = frac * circumference;
    const gap = circumference - dash;
    const offset = circumference * 0.25 - cumulative * circumference; // start at top
    cumulative += frac;
    return `<circle cx="${CX}" cy="${CY}" r="${R}" fill="none" stroke="${palette[i % palette.length]}"
      stroke-width="${STROKE}" stroke-dasharray="${dash} ${gap}" stroke-dashoffset="${offset}"
      transform="rotate(-90 ${CX} ${CY})" />`;
  }).join("");

  const legend = data.map((d, i) => `
    <div class="legend-row">
      <span class="legend-dot" style="background:${palette[i % palette.length]}"></span>
      <span class="legend-label">${d.label}</span>
      <span class="legend-value">${d.weightPct.toFixed(1)}%</span>
    </div>`).join("");

  container.innerHTML = `
    <div class="donut-wrap">
      <svg viewBox="0 0 180 180">${segments}</svg>
      <div class="legend-col">${legend}</div>
    </div>`;
}

// ---- Horizontal bar comparison (current vs target weight) ----
function renderWeightCompare(container, rows) {
  // rows: [{ticker, currentWeightPct, targetWeightPct}]
  const accent = cssVar("--accent") || "#3E6483";
  const dim = cssVar("--text-faint") || "#98A2B3";
  const maxVal = Math.max(...rows.map((r) => Math.max(r.currentWeightPct, r.targetWeightPct)), 1);

  container.innerHTML = `<div class="weight-compare">` + rows.map((r) => `
    <div class="wc-row">
      <div class="wc-label">${r.ticker}</div>
      <div class="wc-bars">
        <div class="wc-bar-track">
          <div class="wc-bar current" style="width:${(r.currentWeightPct / maxVal) * 100}%"></div>
        </div>
        <div class="wc-bar-track">
          <div class="wc-bar target" style="width:${(r.targetWeightPct / maxVal) * 100}%"></div>
        </div>
      </div>
      <div class="wc-values">${r.currentWeightPct.toFixed(1)}% / ${r.targetWeightPct.toFixed(1)}%</div>
    </div>`).join("") + `
    <div class="wc-legend">
      <span><i class="dot current"></i>Current</span>
      <span><i class="dot target"></i>Target</span>
    </div>
    </div>`;
}

// ---- Scatter plot (efficient frontier) ----
function renderScatter(container, points, { xLabel = "Volatility %", yLabel = "Return %" } = {}) {
  if (!points || points.length === 0) return;
  const W = 600, H = 240, PAD = 36;
  const xs = points.map((p) => p.volatilityPct), ys = points.map((p) => p.returnPct);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const xRange = xMax - xMin || 1, yRange = yMax - yMin || 1;

  const accent = cssVar("--accent") || "#3E6483";

  const toXY = (p) => [
    PAD + ((p.volatilityPct - xMin) / xRange) * (W - PAD * 2),
    H - PAD - ((p.returnPct - yMin) / yRange) * (H - PAD * 2),
  ];

  const pathPoints = points.map(toXY);
  const linePath = pathPoints.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const dots = pathPoints.map(([x, y]) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${accent}"/>`).join("");

  container.innerHTML = `
    ${svgEl(`0 0 ${W} ${H}`)}
      <line x1="${PAD}" y1="${H - PAD}" x2="${W - PAD}" y2="${H - PAD}" stroke="${cssVar('--border') || '#DDE1E7'}"/>
      <line x1="${PAD}" y1="${PAD}" x2="${PAD}" y2="${H - PAD}" stroke="${cssVar('--border') || '#DDE1E7'}"/>
      <path d="${linePath}" fill="none" stroke="${accent}" stroke-width="1.5" stroke-opacity="0.5"/>
      ${dots}
      <text x="${W / 2}" y="${H - 6}" text-anchor="middle" font-size="11" fill="${cssVar('--text-dim') || '#667085'}">${xLabel}</text>
      <text x="12" y="${H / 2}" text-anchor="middle" font-size="11" fill="${cssVar('--text-dim') || '#667085'}" transform="rotate(-90 12 ${H / 2})">${yLabel}</text>
    </svg>`;
}

// ---- Correlation heatmap ----
function renderHeatmap(container, tickers, matrix) {
  const n = tickers.length;
  // Cell size no longer shrinks to force-fit every ticker into one screen —
  // .heatmap-scroll lets wide matrices scroll horizontally instead, so
  // labels always keep enough room to avoid overlapping each other.
  const cell = n <= 6 ? 46 : n <= 10 ? 38 : 34;
  const labelW = 46;
  const W = labelW + cell * n, H = labelW + cell * n;

  const colorFor = (v) => {
    // -1 -> down color, 0 -> near white, 1 -> accent
    if (v >= 0) {
      const t = v; // 0..1
      return `rgba(62,100,131,${0.08 + t * 0.75})`;
    }
    const t = -v;
    return `rgba(193,59,59,${0.08 + t * 0.6})`;
  };

  let cells = "";
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const v = matrix[i][j];
      const x = labelW + j * cell, y = labelW + i * cell;
      cells += `<rect x="${x}" y="${y}" width="${cell}" height="${cell}" fill="${colorFor(v)}" stroke="#fff" stroke-width="1"/>`;
      if (cell >= 34) {
        cells += `<text x="${x + cell / 2}" y="${y + cell / 2 + 4}" text-anchor="middle" font-size="9.5" fill="#1B222C">${v.toFixed(2)}</text>`;
      }
    }
  }
  let rowLabels = tickers.map((t, i) => `<text x="${labelW - 6}" y="${labelW + i * cell + cell / 2 + 4}" text-anchor="end" font-size="10.5" fill="#667085">${t}</text>`).join("");
  let colLabels = tickers.map((t, j) => `<text x="${labelW + j * cell + cell / 2}" y="${labelW - 8}" text-anchor="middle" font-size="10.5" fill="#667085">${t}</text>`).join("");

  container.innerHTML = `
    <div class="heatmap-scroll">
      <svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">
        ${cells}${rowLabels}${colLabels}
      </svg>
    </div>`;
}

// ---- Simple bar list (volatility contribution) ----
function renderBarList(container, rows, { key = "contributionPct", labelKey = "ticker" } = {}) {
  const maxVal = Math.max(...rows.map((r) => Math.abs(r[key])), 1);
  container.innerHTML = `<div class="bar-list">` + rows.map((r) => `
    <div class="bl-row">
      <div class="bl-label">${r[labelKey]}</div>
      <div class="bl-track"><div class="bl-fill" style="width:${(Math.abs(r[key]) / maxVal) * 100}%"></div></div>
      <div class="bl-value">${r[key].toFixed(2)}%</div>
    </div>`).join("") + `</div>`;
}

// ---- Histogram (VaR/CVaR return distribution) ----
function renderHistogram(container, bins, { varLine, cvarLine } = {}) {
  if (!bins || bins.length === 0) return;
  const W = 600, H = 220, PAD = 24;
  const counts = bins.map((b) => b.count);
  const maxCount = Math.max(...counts, 1);
  const barW = (W - PAD * 2) / bins.length;
  const accent = cssVar("--accent") || "#3E6483";
  const down = cssVar("--down") || "#C13B3B";

  const minEdge = bins[0].binStart, maxEdge = bins[bins.length - 1].binEnd;
  const xFor = (val) => PAD + ((val - minEdge) / (maxEdge - minEdge)) * (W - PAD * 2);

  const bars = bins.map((b, i) => {
    const h = (b.count / maxCount) * (H - PAD * 2);
    const x = PAD + i * barW;
    const y = H - PAD - h;
    const isLoss = b.binStart < 0;
    return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(barW - 1).toFixed(1)}" height="${h.toFixed(1)}"
      fill="${isLoss ? down : accent}" fill-opacity="0.55"/>`;
  }).join("");

  let markers = "";
  if (varLine !== undefined) {
    const x = xFor(varLine);
    markers += `<line x1="${x}" y1="${PAD}" x2="${x}" y2="${H - PAD}" stroke="${down}" stroke-width="1.5" stroke-dasharray="4 3"/>
      <text x="${x}" y="${PAD - 6}" text-anchor="middle" font-size="10" fill="${down}">VaR</text>`;
  }
  if (cvarLine !== undefined) {
    const x = xFor(cvarLine);
    markers += `<line x1="${x}" y1="${PAD}" x2="${x}" y2="${H - PAD}" stroke="#8B4B4B" stroke-width="1.5" stroke-dasharray="2 3"/>
      <text x="${x}" y="${PAD - 6}" text-anchor="middle" font-size="10" fill="#8B4B4B">CVaR</text>`;
  }

  container.innerHTML = `
    ${svgEl(`0 0 ${W} ${H}`)}
      <line x1="${PAD}" y1="${H - PAD}" x2="${W - PAD}" y2="${H - PAD}" stroke="${cssVar('--border') || '#DDE1E7'}"/>
      ${bars}${markers}
    </svg>`;
}