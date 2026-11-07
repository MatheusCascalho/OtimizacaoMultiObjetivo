(function robustness(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.Robustness = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function robustnessFactory() {
  const COLORS = ['#28624d', '#d96545', '#4777a8', '#e5b94f', '#6e4b86', '#3d7a6a', '#b4533a', '#2f5578'];
  const INK = '#182b25';
  const MUTED = '#818b81';
  const GRID = '#e4e1d6';
  const NOMINAL = '#d96545';

  const COLUMNS = [
    { id: 'label', label: 'Solução' },
    { id: 'distance', label: 'Distância' },
    { id: 'nominal', label: 'Tempo nominal' },
    { id: 'mean', label: 'Média' },
    { id: 'cv', label: 'CV' },
    { id: 'p95', label: 'P95' },
    { id: 'cvar', label: 'CVaR 95%' },
    { id: 'violation', label: 'P(prazo)' },
    { id: 'win', label: 'Melhor tempo' },
    { id: 'frontier', label: 'Na fronteira' },
    { id: 'regretMean', label: 'Regret médio' },
    { id: 'regretP95', label: 'Regret P95' },
    { id: 'hypervolume', label: 'Δ hipervolume' },
  ];

  let panel = null;
  let activeReport = null;

  function canAnalyze({ hasInstance, resultIsDemo, mappedCount, runStatus } = {}) {
    if (!hasInstance || resultIsDemo) return false;
    if (['queued', 'running', 'cancel_requested'].includes(runStatus)) return false;
    return Number(mappedCount) > 0;
  }

  function mapReport(payload) {
    if (!payload || !Array.isArray(payload.solutions) || !payload.solutions.length) return null;
    const solutions = payload.solutions.map((solution, index) => {
      const box = solution && solution.boxplot;
      return {
        id: solution.solution_id || `s${index + 1}`,
        label: solution.label || `S${index + 1}`,
        color: COLORS[index % COLORS.length],
        distance: finite(solution.distance),
        nominalTime: finite(solution.nominal_time),
        mean: finite(solution.mean),
        coefficientOfVariation: finite(solution.coefficient_of_variation),
        p95: finite(solution.p95),
        cvar: finite(solution.cvar),
        violation: finite(solution.violation_probability),
        win: finite(solution.win_frequency),
        frontier: finite(solution.pareto_probability),
        regretMean: finite(solution.regret_mean),
        regretP95: finite(solution.regret_p95),
        hypervolume: finite(solution.hypervolume_contribution),
        rankFrequencies: Array.isArray(solution.rank_frequencies)
          ? solution.rank_frequencies.map(finite)
          : [],
        boxplot: box ? {
          min: finite(box.min),
          q1: finite(box.q1),
          median: finite(box.median),
          q3: finite(box.q3),
          max: finite(box.max),
          nominal: finite(box.nominal),
        } : null,
        criticalArcs: Array.isArray(solution.critical_arcs) ? solution.critical_arcs.map((arc) => ({
          source: arc.source,
          target: arc.target,
          nominalTime: finite(arc.nominal_time),
          varianceShare: finite(arc.variance_share),
          correlation: finite(arc.correlation),
        })) : [],
      };
    });
    if (solutions.some((solution) => solution.distance == null || solution.nominalTime == null)) return null;
    const dominance = squareMatrix(payload.dominance, solutions.length);
    const cloud = payload.cloud && Array.isArray(payload.cloud.times)
      ? payload.cloud.times.filter((row) => Array.isArray(row) && row.length === solutions.length)
      : [];
    return {
      parameters: payload.parameters || {},
      note: typeof payload.note === 'string' ? payload.note : '',
      warnings: Array.isArray(payload.warnings) ? payload.warnings.filter((item) => typeof item === 'string') : [],
      hypervolume: payload.hypervolume || null,
      solutions,
      dominance,
      cloud,
      sensitivity: mapSensitivity(payload.sensitivity, solutions.length),
    };
  }

  function tableRows(report) {
    return report.solutions.map((solution) => [
      solution.label,
      formatNumber(solution.distance, 2),
      formatNumber(solution.nominalTime, 2),
      formatNumber(solution.mean, 2),
      formatNumber(solution.coefficientOfVariation, 3),
      formatNumber(solution.p95, 2),
      formatNumber(solution.cvar, 2),
      formatPercent(solution.violation),
      formatPercent(solution.win),
      formatPercent(solution.frontier),
      formatNumber(solution.regretMean, 2),
      formatNumber(solution.regretP95, 2),
      formatNumber(solution.hypervolume, 3),
    ]);
  }

  function describeReport(report) {
    const parameters = report.parameters || {};
    const region = parameters.region_method === 'kmeans_midpoint'
      ? `${formatInteger(parameters.region_count)} regiões pelos pontos médios dos arcos`
      : 'uma região comum a todos os arcos';
    const convention = parameters.convention === 'median'
      ? 'mediana igual ao tempo nominal'
      : 'média igual ao tempo nominal';
    return [
      `${formatInteger(parameters.scenarios)} cenários`,
      `semente ${parameters.seed}`,
      `CV ${formatNumber(parameters.cv, 2)}`,
      `ρ ${formatNumber(parameters.rho, 2)}`,
      `ρ₀ ${formatNumber(parameters.rho0, 2)}`,
      convention,
      region,
    ].join(' · ');
  }

  function inversionNote(report) {
    const sensitivity = report.sensitivity;
    if (!sensitivity) return '';
    if (sensitivity.rankingInversionCv == null) {
      return 'Na grade de CV, a ordem pela média do tempo permanece igual à ordem nominal.';
    }
    return `A ordem pela média do tempo deixa de coincidir com a ordem nominal a partir de CV ${formatNumber(sensitivity.rankingInversionCv, 2)}.`;
  }

  function mount(nextPanel) {
    panel = nextPanel;
    window.addEventListener('resize', () => {
      if (panel && activeReport && !panel.hidden) drawAll(activeReport);
    });
  }

  function show(payload) {
    const report = mapReport(payload);
    if (!report || !panel) return false;
    activeReport = report;
    panel.hidden = false;
    const status = panel.querySelector('#robustness-status');
    if (status) status.textContent = describeReport(report);
    const note = panel.querySelector('#robustness-note');
    if (note) {
      const extra = [report.note, inversionNote(report)].filter(Boolean).join(' ');
      note.hidden = !extra;
      note.textContent = extra;
    }
    renderWarnings(report);
    renderTable(report);
    renderArcs(report);
    renderLegend(report);
    const charts = panel.querySelector('#robustness-charts');
    if (charts) charts.hidden = false;
    drawWhenReady(report, 0);
    return true;
  }

  function clear() {
    activeReport = null;
    if (!panel) return;
    panel.hidden = true;
    const status = panel.querySelector('#robustness-status');
    if (status) status.textContent = 'A análise ainda não foi executada.';
    ['#robustness-note', '#robustness-warnings', '#robustness-table-wrap', '#robustness-arcs-wrap', '#robustness-legend', '#robustness-charts']
      .forEach((selector) => {
        const element = panel.querySelector(selector);
        if (element) element.hidden = true;
      });
  }

  function renderWarnings(report) {
    const list = panel.querySelector('#robustness-warnings');
    if (!list) return;
    list.replaceChildren();
    report.warnings.forEach((warning) => {
      const item = document.createElement('li');
      item.textContent = warning;
      list.append(item);
    });
    list.hidden = !report.warnings.length;
  }

  function renderTable(report) {
    const wrap = panel.querySelector('#robustness-table-wrap');
    const table = panel.querySelector('#robustness-table');
    if (!wrap || !table) return;
    const body = table.querySelector('tbody');
    body.replaceChildren();
    tableRows(report).forEach((values) => {
      const row = document.createElement('tr');
      values.forEach((value, index) => {
        const cell = document.createElement(index === 0 ? 'th' : 'td');
        if (index === 0) cell.scope = 'row';
        cell.textContent = value;
        row.append(cell);
      });
      body.append(row);
    });
    wrap.hidden = false;
  }

  function renderArcs(report) {
    const wrap = panel.querySelector('#robustness-arcs-wrap');
    const table = panel.querySelector('#robustness-arcs');
    if (!wrap || !table) return;
    const body = table.querySelector('tbody');
    body.replaceChildren();
    report.solutions.forEach((solution) => {
      solution.criticalArcs.forEach((arc) => {
        const row = document.createElement('tr');
        [solution.label, `${arc.source} → ${arc.target}`, formatNumber(arc.nominalTime, 2), formatPercent(arc.varianceShare), formatNumber(arc.correlation, 3)]
          .forEach((value, index) => {
            const cell = document.createElement(index === 0 ? 'th' : 'td');
            if (index === 0) cell.scope = 'row';
            cell.textContent = value;
            row.append(cell);
          });
        body.append(row);
      });
    });
    wrap.hidden = !body.children.length;
  }

  function renderLegend(report) {
    const list = panel.querySelector('#robustness-legend');
    if (!list) return;
    list.replaceChildren();
    report.solutions.forEach((solution) => {
      const item = document.createElement('li');
      const swatch = document.createElement('span');
      swatch.className = 'robustness-swatch';
      swatch.style.background = solution.color;
      item.append(swatch, document.createTextNode(solution.label));
      list.append(item);
    });
    list.hidden = false;
  }

  function drawWhenReady(report, attempt) {
    const drew = drawAll(report);
    if (!drew && attempt < 5) {
      window.requestAnimationFrame(() => drawWhenReady(report, attempt + 1));
    }
  }

  function drawAll(report) {
    const states = [
      ['robustness-figure-box', drawBoxplot(panel.querySelector('#robustness-box'), report)],
      ['robustness-figure-cloud', drawCloud(panel.querySelector('#robustness-cloud'), report)],
      ['robustness-figure-ranks', drawRanks(panel.querySelector('#robustness-ranks'), report)],
      ['robustness-figure-dominance', drawDominance(panel.querySelector('#robustness-dominance'), report)],
      ['robustness-figure-cv-p95', drawSensitivity(panel.querySelector('#robustness-cv-p95'), report, 'p95', 'CV', 'P95 do tempo')],
      ['robustness-figure-cv-pi', drawSensitivity(panel.querySelector('#robustness-cv-pi'), report, 'pareto', 'CV', 'Probabilidade na fronteira')],
      ['robustness-figure-rho', drawRho(panel.querySelector('#robustness-rho-pi'), report)],
    ];
    states.forEach(([id, state]) => toggleFigure(id, state));
    return states.some(([, state]) => state === 'pending');
  }

  function toggleFigure(id, state) {
    const figure = panel.querySelector(`#${id}`);
    if (figure) figure.hidden = state === 'unsupported';
  }

  function drawBoxplot(canvas, report) {
    const usable = report.solutions.every((solution) => solution.boxplot && solution.boxplot.min != null && solution.boxplot.max != null);
    if (!usable) return 'unsupported';
    const fitted = fitCanvas(canvas);
    if (!fitted) return 'pending';
    const { ctx, width, height } = fitted;
    const values = report.solutions.flatMap((solution) => [solution.boxplot.min, solution.boxplot.max, solution.boxplot.nominal]);
    const scale = scaleFrom(values);
    const pad = { top: 16, right: 12, bottom: report.solutions.length > 8 ? 48 : 32, left: 52 };
    const plot = plotBox(width, height, pad);
    drawYAxis(ctx, plot, scale, formatNumber);
    const slot = plot.width / report.solutions.length;
    report.solutions.forEach((solution, index) => {
      const box = solution.boxplot;
      const center = plot.left + slot * (index + 0.5);
      const boxWidth = Math.max(8, Math.min(26, slot * 0.46));
      const y = (value) => yAt(plot, scale, value);
      ctx.strokeStyle = solution.color;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(center, y(box.min));
      ctx.lineTo(center, y(box.max));
      ctx.stroke();
      ctx.fillStyle = solution.color;
      [box.min, box.max].forEach((value) => {
        ctx.fillRect(center - boxWidth / 4, y(value), boxWidth / 2, 1.4);
      });
      ctx.fillStyle = withAlpha(solution.color, 0.22);
      ctx.fillRect(center - boxWidth / 2, y(box.q3), boxWidth, Math.max(1, y(box.q1) - y(box.q3)));
      ctx.strokeRect(center - boxWidth / 2, y(box.q3), boxWidth, Math.max(1, y(box.q1) - y(box.q3)));
      ctx.beginPath();
      ctx.moveTo(center - boxWidth / 2, y(box.median));
      ctx.lineTo(center + boxWidth / 2, y(box.median));
      ctx.stroke();
      diamond(ctx, center, y(box.nominal), 4.5, NOMINAL);
      ctx.fillStyle = MUTED;
      ctx.font = '11px "IBM Plex Mono", ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(solution.label, center, plot.bottom + 16);
    });
    return 'drawn';
  }

  function drawCloud(canvas, report) {
    if (!report.cloud.length) return 'unsupported';
    const fitted = fitCanvas(canvas);
    if (!fitted) return 'pending';
    const { ctx, width, height } = fitted;
    const pad = { top: 16, right: 12, bottom: 32, left: 52 };
    const plot = plotBox(width, height, pad);
    const xs = report.solutions.map((solution) => solution.distance);
    const ys = report.cloud.flat().map(Number).filter(Number.isFinite);
    report.solutions.forEach((solution) => ys.push(solution.nominalTime));
    const xScale = scaleFrom(xs);
    const yScale = scaleFrom(ys);
    drawYAxis(ctx, plot, yScale, formatNumber);
    drawXAxis(ctx, plot, xScale, formatNumber, xs);
    report.cloud.forEach((row) => {
      report.solutions.forEach((solution, index) => {
        const time = finite(row[index]);
        if (time == null) return;
        ctx.fillStyle = withAlpha(solution.color, 0.28);
        ctx.beginPath();
        ctx.arc(xAt(plot, xScale, solution.distance), yAt(plot, yScale, time), 2.4, 0, Math.PI * 2);
        ctx.fill();
      });
    });
    report.solutions.forEach((solution) => {
      diamond(ctx, xAt(plot, xScale, solution.distance), yAt(plot, yScale, solution.nominalTime), 5, solution.color);
    });
    return 'drawn';
  }

  function drawRanks(canvas, report) {
    const ready = report.solutions.every((solution) => solution.rankFrequencies.length === report.solutions.length);
    if (!ready) return 'unsupported';
    const fitted = fitCanvas(canvas);
    if (!fitted) return 'pending';
    const { ctx, width, height } = fitted;
    const pad = { top: 16, right: 12, bottom: 32, left: 52 };
    const plot = plotBox(width, height, pad);
    const scale = { min: 0, max: 1 };
    drawYAxis(ctx, plot, scale, (value) => formatPercent(value));
    const slot = plot.width / report.solutions.length;
    report.solutions.forEach((solution, index) => {
      const left = plot.left + slot * index + slot * 0.22;
      const barWidth = slot * 0.56;
      let cursor = 0;
      solution.rankFrequencies.forEach((frequency, rank) => {
        if (!frequency) return;
        const top = yAt(plot, scale, cursor + frequency);
        const bottom = yAt(plot, scale, cursor);
        ctx.fillStyle = rankColor(rank, report.solutions.length);
        ctx.fillRect(left, top, barWidth, Math.max(1, bottom - top));
        cursor += frequency;
      });
      ctx.fillStyle = MUTED;
      ctx.font = '11px "IBM Plex Mono", ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(solution.label, left + barWidth / 2, plot.bottom + 16);
    });
    return 'drawn';
  }

  function drawDominance(canvas, report) {
    if (!report.dominance) return 'unsupported';
    const fitted = fitCanvas(canvas);
    if (!fitted) return 'pending';
    const { ctx, width, height } = fitted;
    const count = report.solutions.length;
    const pad = { top: 16, right: 12, bottom: 32, left: 36 };
    const plot = plotBox(width, height, pad);
    const cell = Math.min(plot.width / count, plot.height / count);
    const originX = plot.left + (plot.width - cell * count) / 2;
    const originY = plot.top + (plot.height - cell * count) / 2;
    report.dominance.forEach((row, rowIndex) => {
      row.forEach((value, columnIndex) => {
        const intensity = Math.max(0, Math.min(1, Number(value) || 0));
        ctx.fillStyle = mixColor(intensity);
        ctx.fillRect(originX + columnIndex * cell, originY + rowIndex * cell, cell - 1, cell - 1);
        if (cell >= 28 && count <= 12) {
          ctx.fillStyle = intensity > 0.62 ? '#fffefa' : INK;
          ctx.font = '10px "IBM Plex Mono", ui-monospace, monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(formatPercent(intensity), originX + columnIndex * cell + cell / 2, originY + rowIndex * cell + cell / 2);
          ctx.textBaseline = 'alphabetic';
        }
      });
      ctx.fillStyle = MUTED;
      ctx.font = '11px "IBM Plex Mono", ui-monospace, monospace';
      ctx.textAlign = 'right';
      ctx.fillText(report.solutions[rowIndex].label, originX - 4, originY + rowIndex * cell + cell / 2 + 3);
    });
    ctx.textAlign = 'center';
    report.solutions.forEach((solution, index) => {
      ctx.fillText(solution.label, originX + index * cell + cell / 2, originY + count * cell + 14);
    });
    return 'drawn';
  }

  function drawSensitivity(canvas, report, metric, xLabel, yLabel) {
    const points = report.sensitivity && report.sensitivity.byCv;
    if (!points || points.length < 2) return 'unsupported';
    const field = metric === 'pareto' ? 'paretoProbability' : 'p95';
    return drawLines(canvas, points.map((point) => point.cv), report.solutions.map((solution, index) => ({
      color: solution.color,
      values: points.map((point) => point[field][index]),
    })), xLabel, yLabel, metric === 'pareto');
  }

  function drawRho(canvas, report) {
    const points = report.sensitivity && report.sensitivity.byRho;
    if (!points || points.length < 2) return 'unsupported';
    return drawLines(canvas, points.map((point) => point.rho), report.solutions.map((solution, index) => ({
      color: solution.color,
      values: points.map((point) => point.paretoProbability[index]),
    })), 'ρ', 'Probabilidade na fronteira', true);
  }

  function drawLines(canvas, xValues, series, xLabel, yLabel, unitInterval) {
    const yValues = series.flatMap((item) => item.values).filter((value) => value != null);
    if (!yValues.length) return 'unsupported';
    const fitted = fitCanvas(canvas);
    if (!fitted) return 'pending';
    const { ctx, width, height } = fitted;
    const pad = { top: 16, right: 12, bottom: 36, left: 56 };
    const plot = plotBox(width, height, pad);
    const xScale = scaleFrom(xValues);
    const yScale = unitInterval ? { min: 0, max: 1 } : scaleFrom(yValues);
    drawYAxis(ctx, plot, yScale, unitInterval ? formatPercent : formatNumber);
    drawXAxis(ctx, plot, xScale, (value) => formatNumber(value, 2), xValues);
    ctx.fillStyle = MUTED;
    ctx.font = '11px "DM Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(xLabel, plot.left + plot.width / 2, height - 6);
    series.forEach((item) => {
      ctx.strokeStyle = item.color;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      let started = false;
      item.values.forEach((value, index) => {
        if (value == null) return;
        const x = xAt(plot, xScale, xValues[index]);
        const y = yAt(plot, yScale, value);
        if (!started) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        started = true;
      });
      ctx.stroke();
      item.values.forEach((value, index) => {
        if (value == null) return;
        ctx.fillStyle = item.color;
        ctx.beginPath();
        ctx.arc(xAt(plot, xScale, xValues[index]), yAt(plot, yScale, value), 3, 0, Math.PI * 2);
        ctx.fill();
      });
    });
    ctx.save();
    ctx.translate(14, plot.top + plot.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = MUTED;
    ctx.textAlign = 'center';
    ctx.fillText(yLabel, 0, 0);
    ctx.restore();
    return 'drawn';
  }

  function fitCanvas(canvas) {
    if (!canvas || typeof canvas.getContext !== 'function' || typeof canvas.getBoundingClientRect !== 'function') return null;
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return null;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * ratio);
    canvas.height = Math.round(rect.height * ratio);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    return { ctx, width: rect.width, height: rect.height };
  }

  function plotBox(width, height, pad) {
    return {
      left: pad.left,
      top: pad.top,
      width: Math.max(1, width - pad.left - pad.right),
      height: Math.max(1, height - pad.top - pad.bottom),
      bottom: height - pad.bottom,
    };
  }

  function scaleFrom(values) {
    const finiteValues = values.map(Number).filter(Number.isFinite);
    let min = Math.min(...finiteValues);
    let max = Math.max(...finiteValues);
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
    if (min === max) {
      min -= 1;
      max += 1;
    }
    const slack = (max - min) * 0.08;
    return { min: min - slack, max: max + slack };
  }

  function yAt(plot, scale, value) {
    return plot.top + (scale.max - value) / (scale.max - scale.min) * plot.height;
  }

  function xAt(plot, scale, value) {
    return plot.left + (value - scale.min) / (scale.max - scale.min) * plot.width;
  }

  function drawYAxis(ctx, plot, scale, format) {
    ctx.strokeStyle = GRID;
    ctx.fillStyle = MUTED;
    ctx.font = '10px "IBM Plex Mono", ui-monospace, monospace';
    ctx.textAlign = 'right';
    ctx.lineWidth = 1;
    for (let tick = 0; tick < 4; tick += 1) {
      const value = scale.min + (scale.max - scale.min) * tick / 3;
      const y = yAt(plot, scale, value);
      ctx.beginPath();
      ctx.moveTo(plot.left, y);
      ctx.lineTo(plot.left + plot.width, y);
      ctx.stroke();
      ctx.fillText(format(value, 2), plot.left - 6, y + 3);
    }
  }

  function drawXAxis(ctx, plot, scale, format, ticks) {
    ctx.strokeStyle = INK;
    ctx.beginPath();
    ctx.moveTo(plot.left, plot.bottom);
    ctx.lineTo(plot.left + plot.width, plot.bottom);
    ctx.stroke();
    ctx.fillStyle = MUTED;
    ctx.font = '10px "IBM Plex Mono", ui-monospace, monospace';
    ctx.textAlign = 'center';
    const marks = ticks && ticks.length
      ? [...new Set(ticks.map((value) => finite(value)).filter((value) => value != null))]
      : [scale.min, (scale.min + scale.max) / 2, scale.max];
    marks.forEach((value) => {
      const x = xAt(plot, scale, value);
      if (x < plot.left - 8 || x > plot.left + plot.width + 8) return;
      ctx.fillText(format(value, 2), x, plot.bottom + 14);
    });
  }

  function diamond(ctx, x, y, radius, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, y - radius);
    ctx.lineTo(x + radius, y);
    ctx.lineTo(x, y + radius);
    ctx.lineTo(x - radius, y);
    ctx.closePath();
    ctx.fill();
  }

  function rankColor(rank, count) {
    if (count <= 1) return COLORS[0];
    const ratio = rank / (count - 1);
    return mix(COLORS[0], COLORS[1], ratio);
  }

  function mixColor(intensity) {
    return mix('#f5f4ee', '#28624d', intensity);
  }

  function mix(from, to, ratio) {
    const start = hex(from);
    const end = hex(to);
    const channels = start.map((channel, index) => Math.round(channel + (end[index] - channel) * ratio));
    return `rgb(${channels.join(', ')})`;
  }

  function hex(value) {
    return [1, 3, 5].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
  }

  function withAlpha(color, alpha) {
    const channels = hex(color);
    return `rgba(${channels.join(', ')}, ${alpha})`;
  }

  function mapSensitivity(sensitivity, count) {
    if (!sensitivity) return null;
    const byCv = (sensitivity.by_cv || []).map((point) => mapSensitivityPoint(point, count)).filter(Boolean);
    const byRho = (sensitivity.by_rho || []).map((point) => mapSensitivityPoint(point, count)).filter(Boolean);
    if (!byCv.length && !byRho.length) return null;
    return {
      byCv,
      byRho,
      rankingInversionCv: finite(sensitivity.ranking_inversion_cv),
      frontierLossCv: finite(sensitivity.frontier_loss_cv),
    };
  }

  function mapSensitivityPoint(point, count) {
    if (!point) return null;
    const pareto = (point.pareto_probability || []).map(finite);
    const p95 = (point.p95 || []).map(finite);
    if (pareto.length !== count || p95.length !== count) return null;
    return { cv: finite(point.cv), rho: finite(point.rho), paretoProbability: pareto, p95 };
  }

  function squareMatrix(matrix, count) {
    if (!Array.isArray(matrix) || matrix.length !== count) return null;
    const rows = matrix.map((row) => (Array.isArray(row) ? row.map(finite) : null));
    if (rows.some((row) => !row || row.length !== count || row.some((value) => value == null))) return null;
    return rows;
  }

  function finite(value) {
    if (value == null || typeof value === 'boolean') return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  }

  function formatNumber(value, digits = 2) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    return Number(value).toLocaleString('pt-BR', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
  }

  function formatPercent(value) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    return `${(Number(value) * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;
  }

  function formatInteger(value) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    return Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  }

  return {
    COLUMNS,
    canAnalyze,
    mapReport,
    tableRows,
    describeReport,
    inversionNote,
    mount,
    show,
    clear,
    formatNumber,
    formatPercent,
  };
});
