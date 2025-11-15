/* global Plotly */

const plotColors = {
  primary: "#1f77b4",
  secondary: "#ff7f0e",
  success: "#2ca02c",
  danger: "#d62728",
  accent: "#9467bd",
};

const basePlotLayout = {
  font: {
    family: '"Segoe UI","Helvetica Neue",Arial,sans-serif',
    size: 11,
    color: "#212529",
  },
  paper_bgcolor: "#ffffff",
  plot_bgcolor: "#ffffff",
  autosize: true,
  height: 360,
};

async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status}`);
  }
  return res.json();
}

async function fetchJsonl(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status}`);
  }
  const text = await res.text();
  const lines = text.split(/\r?\n/);
  const rows = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      rows.push(JSON.parse(trimmed));
    } catch (err) {
      // Skip malformed lines but keep console hint for debugging.
      // eslint-disable-next-line no-console
      console.warn("Failed to parse JSONL line", err);
    }
  }
  return rows;
}

function formatPercent(value, fractionDigits = 1) {
  if (value == null) return "–";
  const pct = (value * 100).toFixed(fractionDigits);
  return `${pct}%`;
}

function formatMs(value) {
  if (value == null) return "–";
  return `${value.toLocaleString("en-US")} ms`;
}

function formatBytes(value) {
  if (value == null) return "–";
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const idx = Math.min(Math.floor(Math.log10(value) / 3), units.length - 1);
  const scaled = value / 10 ** (idx * 3);
  return `${scaled.toFixed(1)} ${units[idx]}`;
}

function safeNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function aggregateCounts(items, keyFn) {
  const counts = new Map();
  for (const item of items) {
    const key = keyFn(item);
    if (!key) continue;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

function renderSnapshot(summary, stats) {
  const total = summary.total_urls ?? stats.length;
  const successRate = summary.success_rate ?? 0;
  const httpErrorRate = summary.http_error_rate ?? 0;
  const timeoutRate = summary.timeout_rate ?? 0;
  const captchaRate = summary.captcha_rate ?? 0;
  const robotsRate = summary.robots_block_rate ?? 0;
  const httpxShare = summary.httpx_share ?? 0;
  const playwrightShare = summary.playwright_share ?? 0;

  const metaTotal = document.getElementById("meta-total-urls");
  const metaSuccess = document.getElementById("meta-success-rate");
  const metaMethod = document.getElementById("meta-method-share");
  const tldrText = document.getElementById("tldr-text");

  if (metaTotal) metaTotal.textContent = total.toLocaleString("en-US");
  if (metaSuccess) metaSuccess.textContent = formatPercent(successRate);
  if (metaMethod) {
    metaMethod.textContent = `${formatPercent(httpxShare, 0)} HTTP / ${formatPercent(
      playwrightShare,
      0,
    )} browser`;
  }

  const cardSuccess = document.getElementById("card-success");
  const cardFailures = document.getElementById("card-failures");
  const cardBlockers = document.getElementById("card-blockers");
  const cardLatency = document.getElementById("card-latency");
  const cardContent = document.getElementById("card-content");

  const blockerRate = captchaRate + robotsRate;
  const otherErrorRate = httpErrorRate + timeoutRate;

  if (cardSuccess) {
    cardSuccess.textContent = `${formatPercent(successRate)} success`;
  }
  if (cardFailures) {
    cardFailures.textContent = `${formatPercent(blockerRate)} blocked · ${formatPercent(
      otherErrorRate,
    )} other failures`;
  }

  if (cardBlockers) {
    cardBlockers.textContent = `${formatPercent(robotsRate)} robots · ${formatPercent(
      captchaRate,
    )} CAPTCHA · ${formatPercent(httpErrorRate)} HTTP errors`;
  }

  const p95Http = safeNumber(summary.p95_latency_httpx_ms);
  const p95Browser = safeNumber(summary.p95_latency_playwright_ms);
  if (cardLatency) {
    if (p95Http == null && p95Browser == null) {
      cardLatency.textContent = "–";
    } else {
      const parts = [];
      if (p95Http != null) parts.push(`HTTP P95 ${formatMs(p95Http)}`);
      if (p95Browser != null) parts.push(`Playwright P95 ${formatMs(p95Browser)}`);
      cardLatency.textContent = parts.join(" · ");
    }
  }

  const avgHttpBytes = safeNumber(summary.avg_content_len_httpx);
  const avgBrowserBytes = safeNumber(summary.avg_content_len_playwright);
  if (cardContent) {
    const chunks = [];
    if (avgHttpBytes != null) chunks.push(`HTTP ~${formatBytes(avgHttpBytes)}`);
    if (avgBrowserBytes != null) {
      chunks.push(`Playwright ~${formatBytes(avgBrowserBytes)}`);
    }
    if (chunks.length === 0) {
      cardContent.textContent = "–";
    } else {
      cardContent.textContent = chunks.join(" · ");
    }
  }

  if (tldrText) {
    const successPct = formatPercent(successRate);
    const robotsPct = formatPercent(robotsRate);
    const captchaPct = formatPercent(captchaRate);
    const httpErrorPct = formatPercent(httpErrorRate);
    const httpShare = formatPercent(httpxShare, 0);
    const browserShare = formatPercent(playwrightShare, 0);
    tldrText.textContent =
      `Run over ${total.toLocaleString("en-US")} URLs: ` +
      `${successPct} success, ${robotsPct} robots, ${captchaPct} CAPTCHA, and ${httpErrorPct} HTTP errors. ` +
      `HTTP handles ~${httpShare} of URLs; only ~${browserShare} need a browser, ` +
      `keeping latency and proxy cost under control.`;
  }
}

function renderStatusChart(stats) {
  const counts = aggregateCounts(stats, (r) => r.status);
  const labels = Array.from(counts.keys());
  const values = Array.from(counts.values());

  if (!labels.length) return;

  const data = [
    {
      type: "bar",
      x: labels,
      y: values,
      text: values.map((v) => v.toLocaleString("en-US")),
      textposition: "outside",
      marker: { color: plotColors.primary },
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 40, r: 10, b: 60 },
    yaxis: { title: "Count", automargin: true },
    xaxis: { title: "Status", automargin: true },
  };

  Plotly.newPlot("chart-status", data, layout, { displayModeBar: false });
}

function renderBlockTypesChart(stats) {
  const counts = aggregateCounts(stats, (r) => r.block_type || null);
  const labels = Array.from(counts.keys());
  const values = Array.from(counts.values());
  if (!labels.length) return;

  const data = [
    {
      type: "bar",
      x: labels,
      y: values,
      marker: { color: plotColors.secondary },
      text: values.map((v) => v.toLocaleString("en-US")),
      textposition: "outside",
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 40, r: 10, b: 60 },
    yaxis: { title: "Blocked URLs", automargin: true },
    xaxis: { title: "Block type", automargin: true },
  };

  Plotly.newPlot("chart-block-types", data, layout, { displayModeBar: false });
}

function renderCaptchaVendorsChart(stats) {
  const vendorCounts = aggregateCounts(
    stats.filter((r) => r.captcha_detected || r.block_type === "captcha"),
    (r) => r.block_vendor || null,
  );
  const labels = Array.from(vendorCounts.keys());
  const values = Array.from(vendorCounts.values());
  if (!labels.length) return;

  const data = [
    {
      type: "bar",
      x: labels,
      y: values,
      marker: { color: plotColors.accent },
      text: values.map((v) => v.toLocaleString("en-US")),
      textposition: "outside",
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 60, l: 40, r: 10, b: 60 },
    yaxis: { title: "CAPTCHA hits", automargin: true },
    xaxis: { title: "Vendor", automargin: true },
  };

  Plotly.newPlot("chart-captcha-vendors", data, layout, {
    displayModeBar: false,
  });
}

function renderMethodShare(summary, stats) {
  const total = summary.total_urls ?? stats.length;
  if (!total) return;

  const httpxShare = summary.httpx_share ?? 0;
  const playwrightShare = summary.playwright_share ?? 0;
  const httpxCount = Math.round(total * httpxShare);
  const playwrightCount = Math.round(total * playwrightShare);

  const labels = ["HTTPX", "Playwright"];
  const values = [httpxCount, playwrightCount];

  const data = [
    {
      type: "pie",
      labels,
      values,
      hole: 0.55,
      marker: {
        colors: ["#38bdf8", "#fb923c"],
      },
      textinfo: "label+percent",
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 20, r: 20, b: 20 },
    showlegend: false,
  };

  Plotly.newPlot("chart-method-share", data, layout, { displayModeBar: false });
}

function renderLatencyHist(stats) {
  const filtered = stats.filter((r) => r.latency_ms != null);
  if (!filtered.length) return;

  const httpx = filtered.filter((r) => r.method === "httpx");
  const playwright = filtered.filter((r) => r.method === "playwright");

  const data = [];
  if (httpx.length) {
    data.push({
      type: "histogram",
      x: httpx.map((r) => r.latency_ms),
      name: "HTTPX",
      marker: { color: plotColors.primary },
      opacity: 0.75,
      nbinsx: 40,
    });
  }
  if (playwright.length) {
    data.push({
      type: "histogram",
      x: playwright.map((r) => r.latency_ms),
      name: "Playwright",
      marker: { color: plotColors.secondary },
      opacity: 0.75,
      nbinsx: 40,
    });
  }

  const layout = {
    ...basePlotLayout,
    barmode: "overlay",
    margin: { t: 30, l: 50, r: 10, b: 60 },
    xaxis: { title: "Latency (ms)", automargin: true },
    yaxis: { title: "Count", automargin: true },
    legend: { orientation: "h", x: 0, y: 1.1 },
  };

  Plotly.newPlot("chart-latency-hist", data, layout, { displayModeBar: false });
}

function renderLatencySummary(summary) {
  const rows = [];
  const pairs = [
    ["HTTPX", "p50_latency_httpx_ms", "p95_latency_httpx_ms"],
    ["Playwright", "p50_latency_playwright_ms", "p95_latency_playwright_ms"],
  ];

  for (const [label, p50Key, p95Key] of pairs) {
    const p50 = safeNumber(summary[p50Key]);
    const p95 = safeNumber(summary[p95Key]);
    if (p50 != null) {
      rows.push({ method: label, metric: "P50", latency_ms: p50 });
    }
    if (p95 != null) {
      rows.push({ method: label, metric: "P95", latency_ms: p95 });
    }
  }

  if (!rows.length) return;

  const data = [
    {
      type: "bar",
      x: rows.map((r) => r.method),
      y: rows.map((r) => r.latency_ms),
      marker: {
        color: rows.map((r) =>
          r.metric === "P50" ? plotColors.success : plotColors.secondary,
        ),
      },
      text: rows.map((r) => `${r.metric} ${formatMs(r.latency_ms)}`),
      textposition: "outside",
      hovertext: rows.map((r) => `${r.metric} ${r.method}`),
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 60, r: 10, b: 60 },
    xaxis: { title: "Method", automargin: true },
    yaxis: { title: "Latency (ms)", automargin: true },
  };

  Plotly.newPlot("chart-latency-summary", data, layout, {
    displayModeBar: false,
  });
}

function renderContentLenHist(stats) {
  const filtered = stats.filter(
    (r) =>
      r.content_len != null &&
      r.content_len > 0,
  );
  console.log('renderContentLenHist: filtered count =', filtered.length);
  if (!filtered.length) return;

  const httpxValues = filtered
    .filter((r) => r.method === "httpx")
    .map((r) => r.content_len);
  const playwrightValues = filtered
    .filter((r) => r.method === "playwright")
    .map((r) => r.content_len);

  console.log('httpxValues:', httpxValues.length, 'playwrightValues:', playwrightValues.length);

  const data = [];
  if (httpxValues.length) {
    data.push({
      type: "histogram",
      x: httpxValues,
      name: "HTTPX",
      marker: { color: plotColors.primary },
      opacity: 0.75,
    });
  }
  if (playwrightValues.length) {
    data.push({
      type: "histogram",
      x: playwrightValues,
      name: "Playwright",
      marker: { color: plotColors.secondary },
      opacity: 0.75,
    });
  }

  console.log('data traces:', data.length);
  if (!data.length) return;

  const layout = {
    ...basePlotLayout,
    barmode: "overlay",
    margin: { t: 30, l: 60, r: 10, b: 60 },
    xaxis: {
      title: "Content length (bytes)",
      automargin: true,
    },
    yaxis: { title: "Count", automargin: true },
    legend: { orientation: "h", x: 0, y: 1.1 },
  };

  const config = { displayModeBar: false };
  
  // Add nbins to control histogram buckets
  data.forEach(trace => {
    trace.nbinsx = 30;
  });

  console.log('Calling Plotly.newPlot with', data.length, 'traces');
  Plotly.newPlot("chart-content-len", data, layout, config);
}

function renderContentByStatus(stats) {
  const byStatus = new Map();

  for (const r of stats) {
    if (r.content_len == null || r.content_len <= 0) continue;
    const key = r.status || "unknown";
    const arr = byStatus.get(key) ?? [];
    arr.push(r.content_len);
    byStatus.set(key, arr);
  }

  if (!byStatus.size) return;

  const statuses = Array.from(byStatus.keys());
  const medians = statuses.map((status) => {
    const values = byStatus.get(status).slice().sort((a, b) => a - b);
    const mid = Math.floor(values.length / 2);
    return values.length % 2 === 0
      ? (values[mid - 1] + values[mid]) / 2
      : values[mid];
  });

  const data = [
    {
      type: "bar",
      x: statuses,
      y: medians,
      marker: { color: plotColors.success },
      text: medians.map((v) => formatBytes(v)),
      textposition: "outside",
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 60, r: 10, b: 80 },
    xaxis: { title: "Status", automargin: true },
    yaxis: {
      title: "Median content length (bytes, log scale)",
      type: "log",
      automargin: true,
    },
  };

  Plotly.newPlot("chart-content-by-status", data, layout, {
    displayModeBar: false,
  });
}

function renderHttpStatusChart(stats) {
  const errorRows = stats.filter(
    (r) => r.status === "http_error" && r.http_status != null,
  );
  if (!errorRows.length) return;

  const counts = aggregateCounts(errorRows, (r) => String(r.http_status));
  const labels = Array.from(counts.keys()).sort(
    (a, b) => Number(a) - Number(b),
  );
  const values = labels.map((k) => counts.get(k));

  const data = [
    {
      type: "bar",
      x: labels,
      y: values,
      marker: { color: plotColors.danger },
      text: values.map((v) => v.toString()),
      textposition: "outside",
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 50, r: 10, b: 60 },
    xaxis: { title: "HTTP status code", automargin: true },
    yaxis: { title: "Error count", automargin: true },
  };

  Plotly.newPlot("chart-http-status", data, layout, { displayModeBar: false });
}

function renderRetriesChart(stats) {
  const counts = aggregateCounts(stats, (r) =>
    typeof r.retries === "number" ? String(r.retries) : null,
  );
  if (!counts.size) return;
  const labels = Array.from(counts.keys()).sort(
    (a, b) => Number(a) - Number(b),
  );
  const values = labels.map((k) => counts.get(k));

  const data = [
    {
      type: "bar",
      x: labels,
      y: values,
      marker: { color: plotColors.accent },
      text: values.map((v) => v.toString()),
      textposition: "outside",
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 50, r: 10, b: 60 },
    xaxis: { title: "Retries", automargin: true },
    yaxis: { title: "URL count", automargin: true },
  };

  Plotly.newPlot("chart-retries", data, layout, { displayModeBar: false });
}

function renderErrorDomainsChart(stats) {
  const errorRows = stats.filter((r) => r.status === "http_error");
  if (!errorRows.length) return;

  const counts = aggregateCounts(errorRows, (r) => r.domain || null);
  const entries = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  if (!entries.length) return;

  const labels = entries.map(([domain]) => domain);
  const values = entries.map(([, value]) => value);

  const data = [
    {
      type: "bar",
      x: values,
      y: labels,
      orientation: "h",
      marker: { color: plotColors.danger },
      text: values.map((v) => v.toString()),
      textposition: "outside",
    },
  ];

  const layout = {
    ...basePlotLayout,
    margin: { t: 30, l: 120, r: 10, b: 40 },
    xaxis: { title: "HTTP error count", automargin: true },
    yaxis: { automargin: true },
  };

  Plotly.newPlot("chart-error-domains", data, layout, {
    displayModeBar: false,
  });
}

function renderStageMixChart(stats) {
  const counts = aggregateCounts(stats, (r) => {
    const method = r.method || "unknown";
    const stage = r.stage || "unknown";
    return `${method}:${stage}`;
  });
  if (!counts.size) return;

  const entries = Array.from(counts.entries());
  const methods = Array.from(
    new Set(entries.map(([key]) => key.split(":")[0])),
  );
  const stages = Array.from(
    new Set(entries.map(([key]) => key.split(":")[1])),
  );

  const x = [];
  const y = [];
  const text = [];

  for (const method of methods) {
    for (const stage of stages) {
      const key = `${method}:${stage}`;
      const value = counts.get(key) ?? 0;
      x.push(`${method} / ${stage}`);
      y.push(value);
      text.push(value.toString());
    }
  }

  const data = [
    {
      type: "bar",
      x,
      y,
      marker: { color: plotColors.primary },
      text,
      textposition: "outside",
    },
  ];

  const layout = {
    margin: { t: 30, l: 50, r: 10, b: 80 },
    xaxis: { title: "Method / stage", automargin: true },
    yaxis: { title: "URL count", automargin: true },
  };

  Plotly.newPlot("chart-stage-mix", data, layout, { displayModeBar: false });
}

async function main() {
  try {
    const [summary, stats] = await Promise.all([
      fetchJson("data/run_summary.json"),
      fetchJsonl("data/stats.jsonl"),
    ]);

    renderSnapshot(summary, stats);
    renderStatusChart(stats);
    renderBlockTypesChart(stats);
    renderCaptchaVendorsChart(stats);

    renderMethodShare(summary, stats);
    renderLatencyHist(stats);
    renderLatencySummary(summary);

    renderContentLenHist(stats);
    renderContentByStatus(stats);

    renderHttpStatusChart(stats);
    renderRetriesChart(stats);
    renderErrorDomainsChart(stats);

    renderStageMixChart(stats);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error(error);
    const tldrText = document.getElementById("tldr-text");
    if (tldrText) {
      tldrText.textContent =
        "Failed to load stats. Ensure data/run_summary.json and data/stats.jsonl exist and open this page via a local web server (not file://).";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof Plotly === "undefined") {
    // Plotly loaded with defer; wait a tick.
    setTimeout(main, 50);
  } else {
    main();
  }
});
