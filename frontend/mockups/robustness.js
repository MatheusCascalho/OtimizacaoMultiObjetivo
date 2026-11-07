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
    { id: 'name', label: 'Solução', numeric: false },
    { id: 'distance', label: 'Distância', title: 'Distância da rota, em quilômetros' },
    { id: 'co2Kg', label: 'CO2 (kg)', title: 'Emissão de CO2 calculada para a solução, em quilogramas' },
    { id: 'speedEmissionFactor', label: 'Fator de emissão de velocidade', title: 'Média dos fatores de velocidade dos arcos, ponderada pela distância' },
    { id: 'nominal', label: 'Tempo nominal', title: 'Tempo da rota com a matriz nominal, em horas' },
    { id: 'mean', label: 'Média', title: 'Média do tempo simulado, em horas' },
    { id: 'cv', label: 'CV', title: 'Desvio-padrão dividido pela média do tempo simulado' },
    { id: 'frontier', label: 'Na fronteira', title: 'Fração dos cenários em que a solução permanece não dominada' },
    { id: 'regretMean', label: 'Regret médio', title: 'Tempo a mais, em média, em relação à melhor solução do mesmo cenário' },
    { id: 'hypervolume', label: 'Δ hipervolume', title: 'Contribuição média ao hipervolume do conjunto em cada cenário' },
    {
      id: 'minmax',
      label: 'Min-max regret',
      title: 'Pior arrependimento relativo entre distância e tempo. O primeiro percentual usa o regret médio; o segundo, o P95. Menor é melhor.',
    },
  ];

  let panel = null;
  let activeReport = null;
  let tableQuery = '';
  let tableSort = null;

  function canAnalyze({ hasInstance, resultIsDemo, mappedCount, runStatus } = {}) {
    if (!hasInstance || resultIsDemo) return false;
    if (['queued', 'running', 'cancel_requested'].includes(runStatus)) return false;
    return Number(mappedCount) > 0;
  }

  function mapReport(payload, emissionsBySolution = {}) {
    if (!payload || !Array.isArray(payload.solutions) || !payload.solutions.length) return null;
    const solutions = payload.solutions.map((solution, index) => {
      const box = solution && solution.boxplot;
      const emission = solution && emissionsBySolution[solution.solution_id];
      return {
        id: solution.solution_id || `s${index + 1}`,
        name: solutionName(solution.solution_id, index),
        label: solution.label || `S${index + 1}`,
        color: COLORS[index % COLORS.length],
        distance: finite(solution.distance),
        co2Kg: finite(emission && emission.co2_kg),
        speedEmissionFactor: finite(emission && emission.total_speed_emission_factor),
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
        minmax: finite(solution.minmax_regret),
        minmaxP95: finite(solution.minmax_regret_p95),
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

  function tableRows(report, options = {}) {
    return viewSolutions(report, options).map(tableValues);
  }

  function tableValues(solution) {
    return [
      solution.name,
      formatNumber(solution.distance, 2),
      formatNumber(solution.co2Kg, 2),
      formatNumber(solution.speedEmissionFactor, 3),
      formatNumber(solution.nominalTime, 2),
      formatNumber(solution.mean, 2),
      formatNumber(solution.coefficientOfVariation, 3),
      formatPercent(solution.frontier),
      formatNumber(solution.regretMean, 2),
      formatNumber(solution.hypervolume, 3),
      formatMinmax(solution),
    ];
  }

  function viewSolutions(report, options = {}) {
    const query = String(options.query || '').trim().toLowerCase();
    const rows = report.solutions.filter((solution) => tableValues(solution).join(' ').toLowerCase().includes(query));
    const sort = options.sort;
    if (!sort || !COLUMNS.some((column) => column.id === sort.column)) return rows;
    const direction = sort.direction === 'desc' ? -1 : 1;
    return rows.slice().sort((left, right) => compareSolutions(left, right, sort.column, direction));
  }

  function compareSolutions(left, right, column, direction) {
    if (column === 'name') return direction * left.name.localeCompare(right.name, 'pt-BR');
    const leftValue = sortValue(left, column);
    const rightValue = sortValue(right, column);
    if (leftValue == null && rightValue == null) return 0;
    if (leftValue == null) return 1;
    if (rightValue == null) return -1;
    return direction * (leftValue - rightValue);
  }

  function sortValue(solution, column) {
    if (column === 'nominal') return solution.nominalTime;
    if (column === 'cv') return solution.coefficientOfVariation;
    if (column === 'minmax') return solution.minmax;
    return solution[column];
  }

  function formatMinmax(solution) {
    if (solution.minmax == null && solution.minmaxP95 == null) return '—';
    return `${formatPercent(solution.minmax)} · ${formatPercent(solution.minmaxP95)}`;
  }

  function minmaxNote(report) {
    const solutions = report.solutions.filter((solution) => solution.minmax != null);
    if (!solutions.length) return '';
    const best = Math.min(...solutions.map((solution) => solution.minmax));
    const meanNames = solutions.filter((solution) => solution.minmax === best).map((solution) => solution.name);
    const tails = report.solutions.filter((solution) => solution.minmaxP95 != null);
    const bestTail = tails.length ? Math.min(...tails.map((solution) => solution.minmaxP95)) : null;
    const tailNames = tails.filter((solution) => solution.minmaxP95 === bestTail).map((solution) => solution.name);
    const meanText = `Menor min-max regret na média: ${formatNameList(meanNames)} (${formatPercent(best)}).`;
    if (bestTail == null) return meanText;
    return `${meanText} No P95: ${formatNameList(tailNames)} (${formatPercent(bestTail)}).`;
  }

  function formatNameList(names) {
    if (names.length <= 1) return names[0] || '—';
    if (names.length === 2) return `${names[0]} e ${names[1]}`;
    return `${names.slice(0, -1).join(', ')} e ${names[names.length - 1]}`;
  }

  function solutionName(solutionId, index) {
    return solutionId ? `SOL-${solutionId}` : `SOL-${index + 1}`;
  }

  function axisLabel(name, maxChars) {
    const body = name.startsWith('SOL-') ? name.slice(4) : name;
    if (body.length <= maxChars) return body;
    return `${body.slice(0, Math.max(1, maxChars - 1))}…`;
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
    const filter = panel.querySelector('#robustness-filter');
    if (filter) {
      filter.addEventListener('input', () => {
        tableQuery = filter.value;
        if (activeReport) renderTable(activeReport);
      });
    }
    const table = panel.querySelector('#robustness-table');
    if (table) {
      table.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-column]');
        if (!button || !activeReport) return;
        const column = button.dataset.column;
        if (!tableSort || tableSort.column !== column) tableSort = { column, direction: 'asc' };
        else tableSort = { column, direction: tableSort.direction === 'asc' ? 'desc' : 'asc' };
        renderTable(activeReport);
      });
    }
    window.addEventListener('resize', () => {
      if (panel && activeReport && !panel.hidden) drawAll(activeReport);
    });
  }

  function show(payload, emissionsBySolution) {
    const report = mapReport(payload, emissionsBySolution);
    if (!report || !panel) return false;
    activeReport = report;
    tableQuery = '';
    tableSort = null;
    panel.hidden = false;
    const status = panel.querySelector('#robustness-status');
    if (status) status.textContent = describeReport(report);
    const note = panel.querySelector('#robustness-note');
    if (note) {
      note.hidden = !report.note;
      note.textContent = report.note;
    }
    const filter = panel.querySelector('#robustness-filter');
    if (filter) filter.value = '';
    renderWarnings(report);
    renderTable(report);
    const results = panel.querySelector('#robustness-results');
    if (results) results.hidden = false;
    drawWhenReady(report, 0);
    return true;
  }

  function clear() {
    activeReport = null;
    if (!panel) return;
    panel.hidden = true;
    const status = panel.querySelector('#robustness-status');
    if (status) status.textContent = 'A análise ainda não foi executada.';
    tableQuery = '';
    tableSort = null;
    const filter = panel.querySelector('#robustness-filter');
    if (filter) filter.value = '';
    ['#robustness-note', '#robustness-warnings', '#robustness-results']
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
    const table = panel.querySelector('#robustness-table');
    const choice = panel.querySelector('#robustness-minmax');
    if (!table) return;
    const head = table.querySelector('thead');
    const body = table.querySelector('tbody');
    const header = document.createElement('tr');
    COLUMNS.forEach((column) => {
      const cell = document.createElement('th');
      cell.scope = 'col';
      if (column.title) cell.title = column.title;
      const sorted = tableSort && tableSort.column === column.id ? tableSort.direction : null;
      cell.setAttribute('aria-sort', sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : 'none');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'robustness-sort';
      button.dataset.column = column.id;
      const directionName = sorted === 'asc' ? 'decrescente' : 'crescente';
      button.setAttribute('aria-label', `Ordenar por ${column.label.toLowerCase()} em ordem ${directionName}`);
      button.textContent = column.label;
      if (sorted) {
        const mark = document.createElement('span');
        mark.setAttribute('aria-hidden', 'true');
        mark.textContent = sorted === 'asc' ? ' ↑' : ' ↓';
        button.append(mark);
      }
      cell.append(button);
      header.append(cell);
    });
    head.replaceChildren(header);
    const visible = viewSolutions(report, { query: tableQuery, sort: tableSort });
    const best = preferredMinmax(report.solutions);
    body.replaceChildren();
    if (!visible.length) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = COLUMNS.length;
      cell.textContent = 'Nenhuma solução corresponde ao filtro.';
      row.append(cell);
      body.append(row);
    }
    visible.forEach((solution) => {
      const row = document.createElement('tr');
      if (best != null && solution.minmax === best) row.className = 'is-minmax';
      tableValues(solution).forEach((value, index) => {
        const cell = document.createElement(index === 0 ? 'th' : 'td');
        if (index === 0) {
          cell.scope = 'row';
          cell.title = solution.name;
        }
        cell.textContent = value;
        row.append(cell);
      });
      body.append(row);
    });
    if (choice) {
      choice.textContent = minmaxNote(report);
      choice.hidden = !choice.textContent;
    }
  }

  function preferredMinmax(solutions) {
    const values = solutions.map((solution) => solution.minmax).filter((value) => value != null);
    return values.length ? Math.min(...values) : null;
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
      ['robustness-figure-dominance', drawDominance(panel.querySelector('#robustness-dominance'), report)],
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
    const pad = { top: 12, right: 12, bottom: 118, left: 48 };
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
      ctx.font = '10px "IBM Plex Mono", ui-monospace, monospace';
      ctx.save();
      ctx.translate(center, plot.bottom + 8);
      ctx.rotate(-Math.PI / 4);
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(axisLabel(solution.name, fitted.width < 720 ? 8 : 12), 0, 0);
      ctx.restore();
    });
    return 'drawn';
  }

  function drawDominance(canvas, report) {
    if (!report.dominance) return 'unsupported';
    const fitted = fitCanvas(canvas);
    if (!fitted) return 'pending';
    const { ctx, width, height } = fitted;
    const count = report.solutions.length;
    const labelLimit = fitted.width < 720 ? 8 : 12;
    const pad = { top: 12, right: 12, bottom: 108, left: labelLimit > 8 ? 96 : 72 };
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
      ctx.font = '10px "IBM Plex Mono", ui-monospace, monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(axisLabel(report.solutions[rowIndex].name, labelLimit), originX - 6, originY + rowIndex * cell + cell / 2);
    });
    report.solutions.forEach((solution, index) => {
      ctx.save();
      ctx.translate(originX + index * cell + cell / 2, originY + count * cell + 8);
      ctx.rotate(-Math.PI / 4);
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(axisLabel(solution.name, labelLimit), 0, 0);
      ctx.restore();
    });
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
    viewSolutions,
    minmaxNote,
    describeReport,
    inversionNote,
    mount,
    show,
    clear,
    formatNumber,
    formatPercent,
  };
});
