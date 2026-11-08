const API_BASE_URL = window.PARETOLAB_API_BASE_URL || '/api/v1';
const fallbackProblemTypes = [
  { id: 'tsp-time-distance', name: 'TSP biobjetivo: tempo e distância' },
];
const fallbackAlgorithms = [
  { id: 'neuro-lkh', name: 'NeuroLKH' },
  { id: 'random-heuristic', name: 'RandomHeuristic' },
];
const mockSolutions = [
  { id: '018', cost: 18.4, coverage: 82.6, items: 12, frontier: true },
  { id: '014', cost: 16.8, coverage: 78.1, items: 10, frontier: true },
  { id: '021', cost: 21.2, coverage: 87.3, items: 15, frontier: true },
  { id: '009', cost: 13.6, coverage: 72.4, items: 8, frontier: true },
  { id: '024', cost: 24.7, coverage: 91.2, items: 17, frontier: true },
  { id: '011', cost: 15.1, coverage: 70.5, items: 9, frontier: false },
  { id: '006', cost: 11.4, coverage: 65.8, items: 7, frontier: true },
  { id: '019', cost: 19.3, coverage: 79.4, items: 13, frontier: false },
  { id: '003', cost: 9.8, coverage: 96.0, items: 6, frontier: true },
  { id: '022', cost: 22.8, coverage: 84.9, items: 15, frontier: false },
  { id: '016', cost: 17.2, coverage: 75.6, items: 11, frontier: false },
  { id: '027', cost: 27.1, coverage: 93.6, items: 18, frontier: true },
  { id: '008', cost: 12.8, coverage: 67.7, items: 8, frontier: false },
  { id: '025', cost: 25.3, coverage: 88.4, items: 17, frontier: false },
  { id: '013', cost: 15.8, coverage: 74.2, items: 9, frontier: false },
  { id: '029', cost: 29.5, coverage: 95.1, items: 19, frontier: true },
  { id: '005', cost: 10.7, coverage: 62.3, items: 6, frontier: false },
  { id: '020', cost: 20.1, coverage: 85.4, items: 14, frontier: false },
  { id: '010', cost: 14.4, coverage: 69.8, items: 8, frontier: false },
  { id: '031', cost: 31.7, coverage: 96.2, items: 20, frontier: true },
  { id: '007', cost: 12.1, coverage: 63.5, items: 7, frontier: false },
  { id: '026', cost: 26.4, coverage: 90.1, items: 16, frontier: false },
  { id: '012', cost: 15.4, coverage: 71.2, items: 9, frontier: false },
  { id: '033', cost: 33.2, coverage: 58.0, items: 20, frontier: true },
];

const state = {
  solutions: [...mockSolutions],
  frontiers: [],
  problemTypes: [],
  instances: [],
  instance: null,
  activeRun: null,
  selectedInstanceId: null,
  selectedSolutionId: null,
  resultOffset: 0,
  resultLimit: 200,
  resultTotal: 0,
  tableOffset: 0,
  tablePageSize: 6,
  resultIsDemo: true,
  notifications: [],
  routeGraph: null,
  routeGraphKey: null,
  emissionsBySolution: {},
  emissionRunId: null,
  emissionHeatmapScale: null,
  emissionHeatmapScaleRunId: null,
  routeEmission: null,
  routeEmissionKey: null,
  routeViewMode: 'graph',
  comparedIds: [],
  comparisonEntries: [],
  comparisonIllustrative: false,
  showReferencePoints: true,
  showNormalizedScale: false,
  showDominanceCone: false,
  showApproximateFrontier: false,
  showHypervolume: false,
  showHypervolumeReference: false,
  chartExpanded: false,
  hiddenRounds: new Set(),
  referencePoints: null,
  hypervolume: null,
  hypervolumeRunId: null,
  referenceRunId: null,
  qualityEvolution: null,
  qualityEvolutionError: '',
  qualityExpanded: { 'hv-evolution': false, 'spread-evolution': false },
  qualityHover: { 'hv-evolution': null, 'spread-evolution': null },
  qualityFigures: {},
};

async function fetchJson(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
    credentials: 'same-origin',
  });

  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.error?.message || `Falha na requisição (${response.status})`);
  }
  return payload;
}

function setApiStatus(message, isError = false) {
  const feedback = document.querySelector('#compare-feedback');
  if (!feedback) return;
  feedback.textContent = message;
  feedback.classList.toggle('error', isError);
  if (!isError) {
    window.setTimeout(() => {
      feedback.textContent = '';
      feedback.classList.remove('error');
    }, 2600);
  }
}

function populateProblemTypes(problemTypes = state.problemTypes) {
  const select = document.querySelector('#problem-type');
  if (!select) return;

  const previous = select.value;
  select.replaceChildren(...problemTypes.map((problemType) => {
    const option = document.createElement('option');
    option.value = problemType.id;
    option.textContent = problemType.name;
    return option;
  }));
  if (problemTypes.some((problemType) => problemType.id === previous)) {
    select.value = previous;
  }
  populateAlgorithms(select.value);
}

function renderAlgorithmOptions(algorithms) {
  const select = document.querySelector('#instance-algorithm');
  if (!select) return;
  const available = (algorithms || []).filter((algorithm) => algorithm && algorithm.id);
  const source = available.length ? available : fallbackAlgorithms;
  const preferred = source.some((algorithm) => algorithm.id === 'neuro-lkh')
    ? 'neuro-lkh'
    : source[0].id;
  const previous = select.value;
  const chosen = source.some((algorithm) => algorithm.id === previous) ? previous : preferred;
  select.replaceChildren(...source.map((algorithm) => {
    const option = document.createElement('option');
    option.value = algorithm.id;
    option.textContent = algorithm.name || algorithm.id;
    option.defaultSelected = algorithm.id === preferred;
    option.selected = algorithm.id === chosen;
    return option;
  }));
}

async function populateAlgorithms(problemTypeId) {
  const select = document.querySelector('#instance-algorithm');
  if (!select || !problemTypeId) return;
  try {
    const problemType = await fetchJson(`/problem-types/${problemTypeId}`);
    renderAlgorithmOptions(problemType.algorithms || []);
  } catch (error) {
    renderAlgorithmOptions(fallbackAlgorithms);
  }
}

function openInstanceDialog() {
  populateAlgorithms(document.querySelector('#problem-type').value);
  dialog.showModal();
}

function updateInstanceCount() {
  document.querySelector('#instance-count').textContent = String(state.instances.length).padStart(2, '0');
}

function updateActiveNavigation() {
  const activeHash = window.location.hash || '#instancias';
  document.querySelectorAll('.sidebar .nav-item[href^="#"]').forEach((link) => {
    const active = link.hash === activeHash;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
}

function initializeLocalSettings() {
  const iterationsInput = document.querySelector('#run-iterations');
  try {
    const savedIterations = Number(window.localStorage.getItem('paretolab.runIterations'));
    if (Number.isInteger(savedIterations) && savedIterations >= 1 && savedIterations <= 100000) {
      iterationsInput.value = String(savedIterations);
    }
  } catch {
    iterationsInput.value = '50';
  }
  iterationsInput.addEventListener('change', () => {
    const value = Number(iterationsInput.value);
    if (!Number.isInteger(value) || value < 1 || value > 100000) {
      iterationsInput.setCustomValidity('Informe um número inteiro entre 1 e 100.000.');
      iterationsInput.reportValidity();
      return;
    }
    iterationsInput.setCustomValidity('');
    try {
      window.localStorage.setItem('paretolab.runIterations', String(value));
    } catch {
      setApiStatus('A preferência vale apenas para esta sessão.', true);
    }
  });

  const referenceToggle = document.querySelector('#toggle-reference-points');
  if (referenceToggle && window.ReferencePoints) {
    state.showReferencePoints = ReferencePoints.readShowReferencePoints(window.localStorage);
    referenceToggle.checked = state.showReferencePoints;
    referenceToggle.addEventListener('change', () => {
      state.showReferencePoints = referenceToggle.checked;
      try {
        ReferencePoints.writeShowReferencePoints(window.localStorage, state.showReferencePoints);
      } catch {
        setApiStatus('A preferência vale apenas para esta sessão.', true);
      }
      renderTable();
    });
  }

  [
    ['#toggle-normalized-scale', 'showNormalizedScale', 'NORMALIZE_KEY'],
    ['#toggle-dominance-cone', 'showDominanceCone', 'CONE_KEY'],
    ['#toggle-approximate-frontier', 'showApproximateFrontier', 'APPROXIMATE_FRONTIER_KEY'],
  ].forEach(([selector, stateKey, storageName]) => {
    const toggle = document.querySelector(selector);
    if (!toggle || !window.ReferencePoints) return;
    const storageKey = ReferencePoints[storageName];
    state[stateKey] = ReferencePoints.readPreference(window.localStorage, storageKey, false);
    toggle.checked = state[stateKey];
    toggle.addEventListener('change', () => {
      state[stateKey] = toggle.checked;
      try {
        ReferencePoints.writePreference(window.localStorage, storageKey, state[stateKey]);
      } catch {
        setApiStatus('A preferência vale apenas para esta sessão.', true);
      }
      renderTable();
    });
  });

  const hypervolumeToggle = document.querySelector('#toggle-hypervolume');
  if (hypervolumeToggle && window.Hypervolume) {
    state.showHypervolume = Hypervolume.readShowHypervolume(window.localStorage);
    hypervolumeToggle.checked = state.showHypervolume;
    hypervolumeToggle.addEventListener('change', () => {
      state.showHypervolume = hypervolumeToggle.checked;
      try {
        Hypervolume.writeShowHypervolume(window.localStorage, state.showHypervolume);
      } catch {
        setApiStatus('A preferência vale apenas para esta sessão.', true);
      }
      renderTable();
    });
  }

  const hypervolumeReferenceToggle = document.querySelector('#toggle-hypervolume-reference');
  if (hypervolumeReferenceToggle && window.Hypervolume) {
    state.showHypervolumeReference = Hypervolume.readShowHypervolumeReference(window.localStorage);
    hypervolumeReferenceToggle.checked = state.showHypervolumeReference;
    hypervolumeReferenceToggle.addEventListener('change', () => {
      state.showHypervolumeReference = hypervolumeReferenceToggle.checked;
      try {
        Hypervolume.writeShowHypervolumeReference(window.localStorage, state.showHypervolumeReference);
      } catch {
        setApiStatus('A preferência vale apenas para esta sessão.', true);
      }
      renderTable();
    });
  }

  const expandButton = document.querySelector('#toggle-chart-expand');
  if (expandButton && window.Hypervolume) {
    const applyExpansion = () => {
      const expansion = Hypervolume.chartExpansionState(state.chartExpanded);
      expandButton.textContent = expansion.label;
      expandButton.setAttribute('aria-pressed', expansion.ariaPressed);
      document.querySelector('.chart-panel')?.classList.toggle('is-expanded', expansion.expanded);
    };
    applyExpansion();
    expandButton.addEventListener('click', () => {
      state.chartExpanded = !state.chartExpanded;
      applyExpansion();
      drawChart();
    });
  }

  const showAllRounds = document.querySelector('#show-all-rounds');
  if (showAllRounds) {
    showAllRounds.addEventListener('click', () => {
      state.hiddenRounds = window.RoundFilter ? RoundFilter.showAllRounds() : new Set();
      state.tableOffset = 0;
      renderTable();
    });
  }
}

function clearRobustness() {
  state.robustness = null;
  if (window.Robustness) Robustness.clear();
  if (window.AHP) AHP.clear();
}

function updateAHP(report = state.robustness) {
  if (!window.AHP || !window.Robustness || !report) {
    if (window.AHP) AHP.clear();
    return;
  }
  const mapped = Robustness.mapReport(report, state.emissionsBySolution);
  AHP.setSolutions(mapped ? mapped.solutions : null);
}

function applyInstanceSummary(instance) {
  const instanceName = document.querySelector('#instance-name');
  if (!instanceName) return;

  const label = instance?.name || 'Nenhuma instância selecionada';
  const suffix = instance?.instance_id ? ` / ${instance.instance_id}` : '';
  const suffixElement = document.createElement('span');
  suffixElement.className = 'instance-id';
  suffixElement.textContent = suffix;
  instanceName.replaceChildren(document.createTextNode(label), suffixElement);

  const microLabel = document.querySelector('.micro-label');
  if (microLabel) {
    const problemTypeName = state.problemTypes.find((problemType) => problemType.id === instance?.problem_type_id)?.name || 'PROBLEMA BIOBJETIVO';
    microLabel.textContent = instance?.instance_id
      ? `${problemTypeName.toUpperCase()} · ${instance.node_count || 0} CIDADES`
      : 'TSP BIOBJETIVO · CRIE UMA INSTÂNCIA';
  }

  const runBadge = document.querySelector('.run-badge');
  if (runBadge) {
    const statusLabels = {
      queued: 'Em fila',
      running: 'Em execução',
      cancel_requested: 'Cancelamento solicitado',
      cancelled: 'Cancelada',
      completed: 'Concluída',
      failed: 'Falhou',
    };
    const labelElement = document.createElement('span');
    labelElement.className = 'status-dot';
    runBadge.replaceChildren(labelElement, document.createTextNode(state.activeRun
      ? statusLabels[state.activeRun.status] || state.activeRun.status
      : instance?.instance_id ? 'Pronta para otimização' : 'Sem instância'));
  }

  document.querySelector('#start-run').disabled = !instance?.instance_id || ['queued', 'running', 'cancel_requested'].includes(state.activeRun?.status);
  const robustnessButton = document.querySelector('#robustness-analysis');
  if (robustnessButton && window.Robustness) {
    robustnessButton.disabled = !Robustness.canAnalyze({
      hasInstance: Boolean(instance?.instance_id),
      resultIsDemo: state.resultIsDemo,
      mappedCount: state.resultTotal,
      runStatus: state.activeRun?.status,
    });
  }
  document.querySelector('#cancel-run').hidden = !['queued', 'running', 'cancel_requested'].includes(state.activeRun?.status);
  document.querySelector('.toolbar-date').textContent = state.activeRun?.updated_at
    ? new Date(state.activeRun.updated_at).toLocaleString('pt-BR')
    : instance?.created_at ? new Date(instance.created_at).toLocaleDateString('pt-BR') : 'API conectada';
  document.querySelector('#metric-progress').replaceChildren(
    document.createTextNode(state.activeRun?.progress?.total
      ? `${state.activeRun.progress.completed} / ${state.activeRun.progress.total}`
      : '--'),
    Object.assign(document.createElement('span'), {
      className: 'metric-note',
      textContent: state.activeRun?.progress?.total ? `${state.activeRun.progress.percent}%` : 'sem execução',
    }),
  );
}

async function loadProblemTypes() {
  try {
    const payload = await fetchJson('/problem-types');
    state.problemTypes = payload.problem_types || [];
    populateProblemTypes();
    document.querySelector('#api-connection-state').textContent = 'Conectada';
    return true;
  } catch (error) {
    console.warn('Fallback para catálogo demonstrativo:', error.message);
    state.problemTypes = fallbackProblemTypes;
    populateProblemTypes();
    document.querySelector('#api-connection-state').textContent = 'Indisponível';
    return false;
  }
}

async function loadInstances() {
  try {
    const payload = await fetchJson('/instances?limit=5');
    state.instances = payload.instances || [];
    updateInstanceCount();
    populateInstances();
    if (state.instances.length) {
      state.selectedInstanceId = state.instances[0].instance_id;
      state.instance = await fetchJson(`/instances/${state.selectedInstanceId}`);
      const runsPayload = await fetchJson(`/instances/${state.selectedInstanceId}/runs?limit=1`);
      state.activeRun = runsPayload.runs?.[0] || null;
      applyInstanceSummary(state.instance);
      await loadInputAnalysis('time');
      if (state.activeRun?.status === 'completed') {
        await loadRunResults(state.activeRun.run_id, 0);
      } else if (['queued', 'running', 'cancel_requested'].includes(state.activeRun?.status)) {
        pollRun(state.activeRun.run_id);
      } else {
        state.resultIsDemo = false;
        state.resultTotal = 0;
        state.solutions = [];
        state.frontiers = [];
        clearReferencePoints();
        clearRobustness();
        renderSolutionTiming(null);
        await loadQualityEvolution(state.selectedInstanceId);
        renderTable();
        applyInstanceSummary(state.instance);
      }
      return true;
    }
    state.instance = null;
    state.activeRun = null;
    state.selectedInstanceId = null;
    state.resultIsDemo = false;
    state.resultTotal = 0;
    state.solutions = [];
    state.frontiers = [];
    clearReferencePoints();
    clearRobustness();
    resetQualityEvolution();
    renderSolutionTiming(null);
    updateInstanceCount();
    document.querySelector('#input-preview').hidden = true;
    applyInstanceSummary(null);
    renderTable();
  } catch (error) {
    console.warn('Fallback para instância demonstrativa:', error.message);
    state.instances = [];
    updateInstanceCount();
    state.instance = null;
    state.selectedInstanceId = null;
    state.resultIsDemo = true;
    state.resultTotal = 0;
    state.solutions = [...mockSolutions];
    clearRobustness();
    state.frontiers = [];
    clearReferencePoints();
    resetQualityEvolution();
    renderSolutionTiming(null);
    document.querySelector('#input-preview').hidden = true;
    populateInstances();
    applyInstanceSummary(null);
    return false;
  }

  return false;
}

async function initializeDashboard() {
  await loadProblemTypes();
  await loadInstances();
  await loadNotifications();
  if (state.resultIsDemo) selectSolution(mockSolutions[0].id);
  renderTable();
}

function populateInstances() {
  const selector = document.querySelector('#instance-selector');
  selector.replaceChildren();
  if (!state.instances.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Nenhuma instância';
    selector.append(option);
    selector.disabled = true;
    return;
  }
  selector.disabled = false;
  state.instances.forEach((instance) => {
    const option = document.createElement('option');
    option.value = instance.instance_id;
    option.textContent = instance.name;
    selector.append(option);
  });
  selector.value = state.selectedInstanceId || state.instances[0].instance_id;
}

async function loadInputAnalysis(objective, neighborsPerCity = Number(document.querySelector('#neighbors-per-city').value) || 20) {
  if (!state.selectedInstanceId) return;
  const preview = document.querySelector('#input-preview');
  preview.hidden = false;
  document.querySelectorAll('[data-objective]').forEach((button) => {
    const active = button.dataset.objective === objective;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  try {
    const [graph, matrix] = await Promise.all([
      fetchJson(`/instances/${state.selectedInstanceId}/analysis/input/graph?objective=${objective}&neighbors_per_city=${encodeURIComponent(neighborsPerCity)}`),
      fetchJson(`/instances/${state.selectedInstanceId}/analysis/input/matrix?objective=${objective}`),
    ]);
    drawRouteGraph(graph, document.querySelector('#input-graph'));
    document.querySelector('#preview-objective-label').textContent = graph.objective.name.toUpperCase();
    document.querySelector('#matrix-objective-label').textContent = matrix.objective.name.toUpperCase();
    document.querySelector('#preview-neighbor-count').textContent = `${graph.neighbors_per_city.effective} efetivos`;
    renderMatrix(matrix.matrix);
  } catch (error) {
    preview.hidden = true;
    setApiStatus(`Não foi possível carregar a análise prévia: ${error.message}`, true);
  }
}

function renderMatrix(matrix) {
  const table = document.querySelector('#matrix-table');
  const values = matrix.flat().map(Number);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  document.querySelector('#matrix-size').textContent = `${matrix.length} × ${matrix.length}`;
  document.querySelector('#matrix-scale').textContent = `escala ${minimum.toFixed(2)}–${maximum.toFixed(2)}`;
  const heading = document.createElement('thead');
  const headingRow = document.createElement('tr');
  const corner = document.createElement('th');
  corner.scope = 'col';
  corner.textContent = 'Origem / destino';
  headingRow.append(corner);
  matrix.forEach((_, index) => {
    const cell = document.createElement('th');
    cell.scope = 'col';
    cell.textContent = String(index + 1);
    headingRow.append(cell);
  });
  heading.append(headingRow);
  const body = document.createElement('tbody');
  matrix.forEach((row, rowIndex) => {
    const tableRow = document.createElement('tr');
    const rowHeading = document.createElement('th');
    rowHeading.scope = 'row';
    rowHeading.textContent = String(rowIndex + 1);
    tableRow.append(rowHeading);
    row.forEach((value, columnIndex) => {
      const cell = document.createElement('td');
      const numericValue = Number(value);
      cell.textContent = numericValue.toFixed(2);
      cell.title = `Origem ${rowIndex + 1}, destino ${columnIndex + 1}: ${numericValue}`;
      if (rowIndex === columnIndex) cell.className = 'diagonal';
      else {
        const intensity = maximum === minimum ? 0 : (numericValue - minimum) / (maximum - minimum);
        cell.style.backgroundColor = `rgb(71 119 168 / ${Math.round(10 + intensity * 35)}%)`;
      }
      tableRow.append(cell);
    });
    body.append(tableRow);
  });
  table.replaceChildren(heading, body);
}

let pollingRunId = null;

function mapApiSolution(solution, round = solution.round) {
  return {
    id: solution.solution_id,
    solutionId: solution.solution_id,
    cost: Number(solution.objective_values.distance),
    coverage: Number(solution.objective_values.time),
    frontier: solution.dominance === 'non_dominated',
    route: solution.route,
    round: Number.isInteger(round) ? round : null,
  };
}

function findDisplayedSolution(id) {
  const fromPage = state.solutions.find((item) => item.id === id);
  if (fromPage) return fromPage;
  for (const frontier of state.frontiers) {
    const point = frontier.points.find((item) => item.id === id);
    if (point) return point;
  }
  return null;
}

function setTimingValue(selector, value, note) {
  const node = document.querySelector(selector);
  if (!node) return;
  node.replaceChildren(document.createTextNode(value));
  if (note) {
    node.append(Object.assign(document.createElement('span'), { className: 'metric-note', textContent: note }));
  }
}

function setQualityCoefficient(selector, labelId, text, unavailable, status, accessibleName) {
  const node = document.querySelector(selector);
  if (!node) return;
  if (!unavailable) {
    node.removeAttribute('aria-label');
    node.setAttribute('aria-labelledby', labelId);
    setTimingValue(selector, text || '--');
    return;
  }
  node.removeAttribute('aria-labelledby');
  node.setAttribute('aria-label', accessibleName);
  const visible = document.createElement('span');
  visible.setAttribute('aria-hidden', 'true');
  visible.textContent = text;
  const statusNode = document.createElement('span');
  statusNode.className = 'sr-only';
  statusNode.textContent = status || 'indisponível';
  node.replaceChildren(visible, statusNode);
}

function setHypervolumeCoefficient(view) {
  setQualityCoefficient(
    '#hv-cv',
    'hv-cv-label',
    view ? view.cv : '--',
    Boolean(view && view.cvUnavailable),
    view ? view.cvStatus : '',
    'Coeficiente de variação do hipervolume, indisponível',
  );
}

function setSpreadCoefficient(view) {
  setQualityCoefficient(
    '#spread-cv',
    'spread-cv-label',
    view ? view.spreadCv : '--',
    Boolean(view && view.spreadCvUnavailable),
    view ? view.spreadCvStatus : '',
    'Coeficiente de variação do espalhamento, indisponível',
  );
}

function renderSolutionTiming(timing) {
  const api = window.SolutionTiming;
  const view = api && typeof api.solutionTimingViewOrEmpty === 'function'
    ? api.solutionTimingViewOrEmpty(api, timing)
    : null;
  if (!view) {
    setTimingValue('#timing-mean', '--');
    setTimingValue('#timing-stdev', '--');
    setTimingValue('#timing-slowest', '--');
    setTimingValue('#timing-fastest', '--');
    return;
  }
  setTimingValue('#timing-mean', view.mean);
  setTimingValue('#timing-stdev', view.stdev);
  setTimingValue('#timing-slowest', view.slowest, view.slowestDetail);
  setTimingValue('#timing-fastest', view.fastest, view.fastestDetail);
}

function chartFrontierSolutions() {
  const points = state.frontiers.length
    ? state.frontiers.flatMap((frontier) => frontier.points)
    : state.solutions;
  return filterVisibleRoundSolutions(points);
}

function clearReferencePoints() {
  state.referencePoints = null;
  state.referenceRunId = null;
  state.hypervolume = null;
  state.hypervolumeRunId = null;
  state.hiddenRounds = new Set();
  state.emissionsBySolution = {};
  state.emissionRunId = null;
  state.emissionHeatmapScale = null;
  state.emissionHeatmapScaleRunId = null;
  state.routeEmission = null;
  state.routeEmissionKey = null;
  state.routeViewMode = 'graph';
}

function filterVisibleRoundSolutions(solutions) {
  if (!window.RoundFilter) return solutions || [];
  return RoundFilter.filterSolutions(solutions, state.hiddenRounds);
}

function isSolutionRoundVisible(solution) {
  if (!solution || !window.RoundFilter) return Boolean(solution);
  return RoundFilter.isRoundVisible(solution.round, state.hiddenRounds);
}

function displayedReferencePoints() {
  if (state.referencePoints) return state.referencePoints;
  if (state.resultIsDemo && state.solutions.length && window.ReferencePoints) {
    return ReferencePoints.estimateFromChartSolutions(state.solutions);
  }
  return null;
}

function objectiveDirections() {
  const reference = displayedReferencePoints();
  return (reference && reference.directions) || { cost: 'minimize', coverage: 'minimize' };
}

function unionChartSolutions() {
  const byId = new Map();
  state.solutions.forEach((solution) => byId.set(solution.id, solution));
  state.frontiers.forEach((frontier) => {
    (frontier.points || []).forEach((point) => byId.set(point.id, point));
  });
  return [...byId.values()];
}

function approximateDisplay() {
  if (!state.showApproximateFrontier || !window.ReferencePoints) return null;
  const solutions = filterVisibleRoundSolutions(unionChartSolutions());
  const classified = ReferencePoints.classifyApproximateFrontier(solutions, objectiveDirections());
  return {
    ...classified,
    solutions,
    frontierIds: new Set(classified.frontier.map((item) => item.id)),
  };
}

async function loadRunResults(runId, offset) {
  if (offset === 0) clearRobustness();
  const payload = await fetchJson(`/runs/${runId}/results?limit=${state.resultLimit}&offset=${offset}`);
  state.resultOffset = offset;
  state.tableOffset = 0;
  state.resultTotal = payload.total || 0;
  state.resultIsDemo = false;
  state.solutions = (payload.solutions || []).map((solution) => mapApiSolution(solution));
  state.frontiers = (payload.frontiers || []).map((frontier) => ({
    round: frontier.round,
    points: (frontier.solutions || []).map((solution) => mapApiSolution(solution, frontier.round)),
  }));
  if (state.referenceRunId !== runId) {
    try {
      state.referencePoints = ReferencePoints.mapApiReferencePoints(
        await fetchJson(`/runs/${runId}/reference-points`),
      );
      state.referenceRunId = state.referencePoints ? runId : null;
      if (!state.referencePoints) {
        setApiStatus('A resposta dos pontos de referência não pôde ser lida.', true);
      }
    } catch (error) {
      clearReferencePoints();
      setApiStatus(`Não foi possível calcular os pontos de referência: ${error.message}`, true);
    }
  }
  if (state.hypervolumeRunId !== runId && window.Hypervolume) {
    try {
      state.hypervolume = Hypervolume.mapApiHypervolume(await fetchJson(`/runs/${runId}/hypervolume`));
      state.hypervolumeRunId = state.hypervolume ? runId : null;
      if (!state.hypervolume) {
        setApiStatus('A resposta do hipervolume não pôde ser lida.', true);
      }
    } catch (error) {
      state.hypervolume = null;
      state.hypervolumeRunId = null;
      setApiStatus(`Não foi possível calcular o hipervolume: ${error.message}`, true);
    }
  }
  if (state.emissionRunId !== runId && window.EmissionHeatmap) {
    try {
      const emission = await fetchJson(`/runs/${runId}/emissions`);
      state.emissionsBySolution = EmissionHeatmap.indexBySolution(emission);
      state.emissionRunId = runId;
    } catch (error) {
      state.emissionsBySolution = {};
      state.emissionRunId = null;
      setApiStatus(`Não foi possível calcular a emissão de CO2: ${error.message}`, true);
    }
  }
  selectedId = state.solutions[0]?.id || null;
  state.selectedSolutionId = selectedId;
  document.querySelector('#metric-solutions').replaceChildren(
    document.createTextNode(String(payload.total || 0)),
    Object.assign(document.createElement('span'), { className: 'metric-note', textContent: 'soluções únicas' }),
  );
  document.querySelector('#metric-frontier').replaceChildren(
    document.createTextNode(String(payload.non_dominated || 0)),
    Object.assign(document.createElement('span'), { className: 'metric-note', textContent: 'não dominadas' }),
  );
  renderSolutionTiming(payload.solution_timing);
  applyInstanceSummary(state.instance);
  if (offset === 0 && state.selectedInstanceId) {
    await loadQualityEvolution(state.selectedInstanceId);
    await loadStoredRobustness(runId);
  }
  if (state.solutions.length) selectSolution(selectedId);
  else renderTable();
}

async function loadStoredRobustness(runId) {
  try {
    const report = await fetchJson(`/runs/${runId}/robustness`);
    if (!report) return;
    if (report.run_id !== runId || report.instance_id !== state.selectedInstanceId) {
      throw new Error('O relatório persistido não corresponde à execução selecionada.');
    }
    if (!window.Robustness || !Robustness.show(report, state.emissionsBySolution)) {
      throw new Error('A resposta da análise multicritério não pôde ser lida.');
    }
    state.robustness = report;
    updateAHP(report);
  } catch (error) {
    const panel = document.querySelector('#robustness-panel');
    panel.hidden = false;
    panel.querySelector('#robustness-status').textContent =
      `Não foi possível recuperar a análise persistida: ${error.message}`;
  }
}

async function pollRun(runId) {
  if (pollingRunId === runId) return;
  pollingRunId = runId;

  while (pollingRunId === runId) {
    try {
      const run = await fetchJson(`/runs/${runId}`);
      if (pollingRunId !== runId) return;
      if (state.selectedInstanceId !== run.instance_id) {
        pollingRunId = null;
        return;
      }
      state.activeRun = run;
      applyInstanceSummary(state.instance);
      if (['completed', 'cancelled', 'failed'].includes(run.status)) {
        pollingRunId = null;
        if (run.status === 'completed') {
          await loadRunResults(runId, 0);
          await loadNotifications();
          if (state.referencePoints) {
            setApiStatus('Execução concluída. Resultados disponíveis.');
          }
        } else {
          state.solutions = [];
          state.frontiers = [];
          clearReferencePoints();
          clearRobustness();
          state.resultIsDemo = false;
          state.resultTotal = 0;
          renderSolutionTiming(null);
          renderTable();
          if (run.status === 'failed') setApiStatus(run.error || 'A execução falhou.', true);
        }
        applyInstanceSummary(state.instance);
        return;
      }

      const progress = run.progress;
      if (progress?.total) {
        document.querySelector('#metric-progress').replaceChildren(
          document.createTextNode(`${progress.completed} / ${progress.total}`),
          Object.assign(document.createElement('span'), { className: 'metric-note', textContent: `${progress.percent}%` }),
        );
      }
    } catch (error) {
      pollingRunId = null;
      setApiStatus(`Não foi possível consultar a execução: ${error.message}`, true);
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
  }
}

async function startRun() {
  const button = document.querySelector('#start-run');
  const iterationsInput = document.querySelector('#run-iterations');
  const iterations = Number(iterationsInput.value);
  if (!Number.isInteger(iterations) || iterations < 1 || iterations > 100000) {
    iterationsInput.setCustomValidity('Informe um número inteiro entre 1 e 100.000.');
    iterationsInput.reportValidity();
    return;
  }
  iterationsInput.setCustomValidity('');
  button.disabled = true;
  setApiStatus('Enfileirando otimização...');
  try {
    const response = await fetchJson(`/instances/${state.selectedInstanceId}/runs`, {
      method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}` },
      body: JSON.stringify({ parameters: { iterations } }),
    });
    state.activeRun = response;
    state.solutions = [];
    state.frontiers = [];
    clearReferencePoints();
    clearRobustness();
    state.resultIsDemo = false;
    state.resultTotal = 0;
    document.querySelector('#metric-solutions').replaceChildren(document.createTextNode('--'));
    document.querySelector('#metric-frontier').replaceChildren(document.createTextNode('--'));
    renderSolutionTiming(null);
    renderTable();
    applyInstanceSummary(state.instance);
    setApiStatus('Otimização enfileirada. O progresso será atualizado automaticamente.');
    pollRun(response.run_id);
  } catch (error) {
    button.disabled = false;
    setApiStatus(`Não foi possível iniciar a otimização: ${error.message}`, true);
  }
}

async function runRobustness() {
  const button = document.querySelector('#robustness-analysis');
  const panel = document.querySelector('#robustness-panel');
  if (!state.selectedInstanceId || !button || button.disabled) return;
  button.disabled = true;
  const previousLabel = button.textContent;
  button.textContent = 'Analisando robustez...';
  if (panel) {
    panel.hidden = false;
    const status = panel.querySelector('#robustness-status');
    if (status) status.textContent = 'Gerando perturbações da matriz de tempo e reavaliando as rotas já mapeadas.';
  }
  try {
    const report = await fetchJson(`/instances/${state.selectedInstanceId}/robustness`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    if (!window.Robustness
      || !report.run_id
      || report.run_id !== state.activeRun?.run_id
      || !Robustness.mapReport(report)) {
      if (panel) {
        panel.hidden = false;
        panel.querySelector('#robustness-status').textContent =
          'A resposta da análise não corresponde à última execução selecionada.';
      }
      return;
    }
    state.robustness = report;
    if (!Robustness.show(report, state.emissionsBySolution)) {
      if (panel) {
        panel.hidden = false;
        panel.querySelector('#robustness-status').textContent = 'A resposta da análise não pôde ser lida.';
      }
      return;
    }
    updateAHP(report);
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    panel.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
  } catch (error) {
    if (window.Robustness) Robustness.clear();
    if (panel) {
      panel.hidden = false;
      panel.querySelector('#robustness-status').textContent = `Não foi possível concluir a análise de robustez: ${error.message}`;
    }
  } finally {
    button.textContent = previousLabel;
    applyInstanceSummary(state.instance);
  }
}

async function cancelRun() {
  if (!state.activeRun?.run_id) return;
  const button = document.querySelector('#cancel-run');
  button.disabled = true;
  try {
    const response = await fetchJson(`/runs/${state.activeRun.run_id}/cancel`, { method: 'POST' });
    state.activeRun = response;
    applyInstanceSummary(state.instance);
    setApiStatus('Cancelamento solicitado. Aguardando confirmação do worker.');
    pollRun(response.run_id);
  } catch (error) {
    button.disabled = false;
    setApiStatus(`Não foi possível solicitar cancelamento: ${error.message}`, true);
  }
}

async function loadNotifications() {
  try {
    const payload = await fetchJson('/notifications?limit=50');
    state.notifications = payload.notifications || [];
  } catch (error) {
    state.notifications = [];
    console.warn('Notificações indisponíveis:', error.message);
  }
  const unreadCount = state.notifications.filter((notification) => !notification.is_read).length;
  document.querySelector('#notification-count').textContent = unreadCount;
  document.querySelector('#notifications-button').setAttribute('aria-label', `Notificações, ${unreadCount} não lidas`);
  renderNotifications();
}

function renderNotifications() {
  const list = document.querySelector('#notifications-list');
  list.replaceChildren();
  if (!state.notifications.length) {
    const empty = document.createElement('p');
    empty.className = 'notification-empty';
    empty.textContent = 'Nenhuma notificação disponível.';
    list.append(empty);
    return;
  }

  state.notifications.forEach((notification) => {
    const item = document.createElement('article');
    item.className = `notification-item${notification.is_read ? '' : ' unread'}`;
    const openButton = document.createElement('button');
    openButton.className = 'notification-open';
    openButton.type = 'button';
    const title = document.createElement('strong');
    title.textContent = notification.title;
    const message = document.createElement('span');
    message.textContent = notification.message;
    const date = document.createElement('small');
    date.textContent = new Date(notification.created_at).toLocaleString('pt-BR');
    openButton.append(title, message, date);
    openButton.addEventListener('click', () => openNotification(notification));
    item.append(openButton);
    list.append(item);
  });
}

async function openNotification(notification) {
  pollingRunId = null;
  if (!notification.is_read) {
    await fetchJson(`/notifications/${notification.notification_id}`, { method: 'PATCH' });
    notification.is_read = true;
    await loadNotifications();
  }
  if (notification.instance_id) {
    clearRobustness();
    state.selectedInstanceId = notification.instance_id;
    state.instance = await fetchJson(`/instances/${notification.instance_id}`);
    state.instances = [state.instance, ...state.instances.filter((instance) => instance.instance_id !== notification.instance_id)];
    populateInstances();
    document.querySelector('#instance-selector').value = notification.instance_id;
    state.activeRun = notification.run_id ? await fetchJson(`/runs/${notification.run_id}`) : null;
    applyInstanceSummary(state.instance);
    await loadInputAnalysis('time');
    if (notification.run_id && state.activeRun.status === 'completed') {
      await loadRunResults(notification.run_id, 0);
    } else if (notification.run_id && ['queued', 'running', 'cancel_requested'].includes(state.activeRun?.status)) {
      pollRun(notification.run_id);
    }
  }
  document.querySelector('#notifications-dialog').close();
}

async function uploadMatrix(file, role, problemTypeId) {
  const formData = new FormData();
  formData.append('problem_type_id', problemTypeId);
  formData.append('role', role);
  formData.append('file', file);
  return fetchJson('/uploads', { method: 'POST', body: formData });
}

function validateMatrixFile(file, label) {
  if (!file) throw new Error(`Selecione o arquivo ${label}.`);
  if (!file.name.toLowerCase().endsWith('.csv')) throw new Error(`${label}: selecione um arquivo CSV.`);
  if (file.size > 10 * 1024 * 1024) throw new Error(`${label}: o limite é 10 MiB.`);
}

async function createInstance(event) {
  if (event.submitter?.id !== 'create-instance') return;
  event.preventDefault();
  const submitButton = document.querySelector('#create-instance');
  const errorMessage = document.querySelector('#dialog-error');
  const name = document.querySelector('#instance-title').value.trim();
  const problemTypeId = document.querySelector('#problem-type').value;
  const algorithmId = document.querySelector('#instance-algorithm').value;
  const timeFile = document.querySelector('#time-file-input').files[0];
  const distanceFile = document.querySelector('#distance-file-input').files[0];
  errorMessage.hidden = true;

  try {
    validateMatrixFile(timeFile, 'de tempo');
    validateMatrixFile(distanceFile, 'de distância');
    if (!name) throw new Error('Informe um nome para a instância.');
    if (!algorithmId) throw new Error('Selecione o algoritmo.');
    if (!document.querySelector('#confirm-node-order').checked) {
      throw new Error('Confirme que os arquivos usam a mesma ordem de cidades.');
    }
    submitButton.disabled = true;
    submitButton.textContent = 'Validando matrizes...';
    const [timeUpload, distanceUpload] = await Promise.all([
      uploadMatrix(timeFile, 'time_matrix', problemTypeId),
      uploadMatrix(distanceFile, 'distance_matrix', problemTypeId),
    ]);
    submitButton.textContent = 'Criando instância...';
    const instance = await fetchJson('/instances', {
      method: 'POST',
      body: JSON.stringify({
        problem_type_id: problemTypeId,
        name,
        files: {
          time_matrix: timeUpload.upload_id,
          distance_matrix: distanceUpload.upload_id,
        },
        node_order_confirmed: true,
        configuration: {
          algorithm_id: algorithmId,
          preview: ['weighted_graph', 'matrix_heatmap'],
          result_views: ['pareto_frontier', 'solutions_table', 'route_graph', 'route_csv'],
        },
      }),
    });
    clearRobustness();
    state.instance = instance;
    state.selectedInstanceId = instance.instance_id;
    state.instances = [instance, ...state.instances.filter((item) => item.instance_id !== instance.instance_id)];
    populateInstances();
    state.activeRun = null;
    state.solutions = [];
    state.frontiers = [];
    clearReferencePoints();
    state.resultIsDemo = false;
    renderSolutionTiming(null);
    state.resultOffset = 0;
    applyInstanceSummary(instance);
    await loadInputAnalysis('time');
    renderTable();
    dialog.close();
    document.querySelector('#instance-form').reset();
    const algorithmSelect = document.querySelector('#instance-algorithm');
    if ([...algorithmSelect.options].some((option) => option.value === 'neuro-lkh')) {
      algorithmSelect.value = 'neuro-lkh';
    }
    setApiStatus(`Instância “${name}” criada. As matrizes foram validadas pela API.`);
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.innerHTML = 'Criar instância <span aria-hidden="true">→</span>';
  }
}

async function showSelectedRoute() {
  const solution = state.solutions.find((item) => item.id === state.selectedSolutionId);
  if (!solution?.solutionId || !state.activeRun?.run_id) return;
  const requestKey = `${state.activeRun.run_id}:${solution.solutionId}`;
  try {
    const graph = await fetchJson(`/runs/${state.activeRun.run_id}/solutions/${solution.solutionId}/graph`);
    if (currentRouteKey() !== requestKey) return;
    state.routeGraph = graph;
    state.routeGraphKey = requestKey;
    drawRouteGraph(graph);
    document.querySelector('#expand-route').disabled = false;
    if (document.querySelector('#route-dialog').open) drawExpandedRoute();
    setApiStatus(`Rota da solução ${solution.id}: ${graph.route.join(' → ')}`);
  } catch (error) {
    setApiStatus(`Não foi possível carregar a rota: ${error.message}`, true);
  }
}

function currentRouteKey() {
  const solution = state.solutions.find((item) => item.id === state.selectedSolutionId);
  if (!solution?.solutionId || !state.activeRun?.run_id) return null;
  return `${state.activeRun.run_id}:${solution.solutionId}`;
}

function clearRouteCanvas(routeCanvas = document.querySelector('#route-chart')) {
  const context = routeCanvas.getContext('2d');
  const bounds = routeCanvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(bounds.width, 1);
  const height = Math.max(bounds.height, 1);
  routeCanvas.width = Math.max(1, Math.round(width * ratio));
  routeCanvas.height = Math.max(1, Math.round(height * ratio));
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  if (routeCanvas.id === 'route-chart') {
    routeCanvas.setAttribute('aria-label', 'Gráfico da rota selecionada; selecione Ver rota para carregar os dados');
  }
}

function syncRoutePreview() {
  const expandButton = document.querySelector('#expand-route');
  if (!expandButton) return;
  const key = currentRouteKey();
  if (state.routeGraph && key && key === state.routeGraphKey) {
    expandButton.disabled = false;
    return;
  }
  const hadGraph = Boolean(state.routeGraph || state.routeGraphKey);
  state.routeGraph = null;
  state.routeGraphKey = null;
  expandButton.disabled = true;
  if (hadGraph) clearRouteCanvas();
  state.routeEmission = null;
  state.routeEmissionKey = null;
  resetEmissionToggle();
  const routeDialog = document.querySelector('#route-dialog');
  if (routeDialog?.open) routeDialog.close();
}

const routeView = { zoom: 1, panX: 0, panY: 0 };
const compareView = { zoom: 1, panX: 0, panY: 0 };
const ROUTE_ZOOM_MIN = 0.5;
const ROUTE_ZOOM_MAX = 4;
let routePan = null;
let comparePan = null;
let comparisonHits = [];
let comparisonRequest = 0;

function routeLayout(nodes, width, height, labelAll) {
  const inset = labelAll ? 28 : 18;
  let plotWidth = width - inset * 2;
  let plotHeight = height - inset * 2;
  if (labelAll) {
    plotWidth = Math.max(1, plotWidth);
    plotHeight = Math.max(1, plotHeight);
  }
  const xValues = nodes.map((node) => node.x);
  const yValues = nodes.map((node) => node.y);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const pointFor = (nodeId) => {
    const node = nodes.find((item) => item.id === nodeId);
    if (!node) return null;
    return {
      x: inset + ((node.x - minX) / spanX) * plotWidth,
      y: inset + ((node.y - minY) / spanY) * plotHeight,
    };
  };
  return { pointFor };
}

function drawRouteGraph(graph, routeCanvas = document.querySelector('#route-chart'), view) {
  const zoom = view?.zoom ?? 1;
  const panX = view?.panX ?? 0;
  const panY = view?.panY ?? 0;
  const labelAll = Boolean(view?.labelAll);
  const context = routeCanvas.getContext('2d');
  const bounds = routeCanvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  routeCanvas.width = Math.max(1, Math.round(bounds.width * ratio));
  routeCanvas.height = Math.max(1, Math.round(bounds.height * ratio));
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, bounds.width, bounds.height);

  const nodes = graph.nodes || [];
  if (!nodes.length) {
    context.fillStyle = '#78817b';
    context.font = '10px "DM Sans", sans-serif';
    context.fillText('Layout da instância indisponível', 10, 20);
    return;
  }
  if (zoom !== 1 || panX !== 0 || panY !== 0) {
    context.setTransform(ratio * zoom, 0, 0, ratio * zoom, ratio * panX, ratio * panY);
  }
  const { pointFor } = routeLayout(nodes, bounds.width, bounds.height, labelAll);

  (graph.edges || []).forEach((edge) => {
    const source = pointFor(edge.source);
    const target = pointFor(edge.target);
    if (!source || !target) return;
    context.beginPath();
    context.moveTo(source.x, source.y);
    context.lineTo(target.x, target.y);
    context.strokeStyle = '#6d9779';
    context.lineWidth = labelAll ? 1.75 : 1.4;
    context.stroke();
  });
  nodes.forEach((node) => {
    const point = pointFor(node.id);
    if (!point) return;
    context.beginPath();
    context.arc(point.x, point.y, labelAll ? 4.2 : 3.2, 0, Math.PI * 2);
    context.fillStyle = node.id === graph.route?.[0] ? '#d96545' : '#28624d';
    context.fill();
    if (labelAll || nodes.length <= 40 || node.id === graph.route?.[0] || node.id % 25 === 0) {
      context.fillStyle = '#182b25';
      if (labelAll) {
        context.save();
        context.translate(point.x, point.y);
        context.scale(1 / zoom, 1 / zoom);
        context.font = '12px "IBM Plex Mono", monospace';
        context.fillText(String(node.label ?? node.id), 6, -6);
        context.restore();
      } else {
        context.font = '8px "IBM Plex Mono", monospace';
        context.fillText(String(node.id), point.x + 5, point.y - 4);
      }
    }
  });
  routeCanvas.setAttribute('aria-label', graph.route?.length
    ? `Rota pelas cidades ${graph.route.join(', ')}`
    : 'Grafo de entrada da instância com layout persistido');
}

function updateRouteZoomControls() {
  const percent = `${Math.round(routeView.zoom * 100)}%`;
  document.querySelector('#route-zoom-level').textContent = percent;
  document.querySelector('#route-zoom-out').disabled = routeView.zoom <= ROUTE_ZOOM_MIN + 0.001;
  document.querySelector('#route-zoom-in').disabled = routeView.zoom >= ROUTE_ZOOM_MAX - 0.001;
}

function drawExpandedRoute() {
  const routeDialog = document.querySelector('#route-dialog');
  if (!routeDialog?.open || !state.routeGraph) return;
  const canvas = document.querySelector('#route-viewer-canvas');
  const bounds = canvas.getBoundingClientRect();
  if (bounds.width < 2 || bounds.height < 2) return;
  if (
    state.routeViewMode === 'heatmap'
    && state.routeEmission
    && state.routeEmissionKey === state.routeGraphKey
    && window.EmissionHeatmap
  ) {
    EmissionHeatmap.draw(canvas, {
      heatmap: state.routeEmission.heatmap,
      heatmap_scale: state.emissionHeatmapScaleRunId === state.activeRun?.run_id
        ? state.emissionHeatmapScale
        : null,
      heatmap_message: state.routeEmission.heatmap_message,
      nodes: state.routeGraph.nodes,
      route: state.routeGraph.route,
    }, {
      zoom: routeView.zoom,
      panX: routeView.panX,
      panY: routeView.panY,
    });
    canvas.setAttribute('aria-label', EmissionHeatmap.description(state.routeEmission));
    return;
  }
  drawRouteGraph(state.routeGraph, canvas, {
    zoom: routeView.zoom,
    panX: routeView.panX,
    panY: routeView.panY,
    labelAll: true,
  });
}

function zoomRouteTo(nextZoom, originX, originY) {
  const zoom = Math.min(ROUTE_ZOOM_MAX, Math.max(ROUTE_ZOOM_MIN, nextZoom));
  if (Math.abs(zoom - routeView.zoom) < 0.0001) {
    updateRouteZoomControls();
    return;
  }
  const worldX = (originX - routeView.panX) / routeView.zoom;
  const worldY = (originY - routeView.panY) / routeView.zoom;
  routeView.zoom = zoom;
  routeView.panX = originX - worldX * zoom;
  routeView.panY = originY - worldY * zoom;
  updateRouteZoomControls();
  drawExpandedRoute();
}

function routeViewerCenter() {
  const bounds = document.querySelector('#route-viewer-canvas').getBoundingClientRect();
  return { x: bounds.width / 2, y: bounds.height / 2 };
}

function resetRouteZoom() {
  routeView.zoom = 1;
  routeView.panX = 0;
  routeView.panY = 0;
  updateRouteZoomControls();
  drawExpandedRoute();
}

const ROUTE_VIEWER_HINT = 'Roda do mouse amplia o ponto sob o cursor. Arraste para deslocar o grafo. Zoom de 50% a 400%.';

function resetEmissionToggle() {
  state.routeViewMode = 'graph';
  const button = document.querySelector('#route-emission-heatmap');
  if (button) {
    button.setAttribute('aria-pressed', 'false');
    button.classList.remove('is-active');
    button.disabled = false;
    button.textContent = 'Densidade de CO2 (kg, suavizada)';
  }
  const hint = document.querySelector('#route-viewer-hint');
  if (hint) hint.textContent = ROUTE_VIEWER_HINT;
}

function showStoredEmissionFactor() {
  const summary = document.querySelector('#route-emission-summary');
  if (!summary || !window.EmissionHeatmap) return;
  const solution = state.solutions.find((item) => item.id === state.selectedSolutionId);
  const row = solution?.solutionId ? state.emissionsBySolution[solution.solutionId] : null;
  const text = EmissionHeatmap.summaryText(row);
  summary.classList.remove('is-error');
  summary.hidden = !text;
  summary.textContent = text;
}

function activateEmissionHeatmap() {
  state.routeViewMode = 'heatmap';
  const button = document.querySelector('#route-emission-heatmap');
  button.setAttribute('aria-pressed', 'true');
  button.classList.add('is-active');
  const summary = document.querySelector('#route-emission-summary');
  const text = EmissionHeatmap.summaryText(state.routeEmission);
  summary.classList.remove('is-error');
  summary.hidden = !text;
  summary.textContent = text;
  document.querySelector('#route-viewer-hint').textContent = EmissionHeatmap.heatmapHint(state.routeEmission);
  const solution = state.solutions.find((item) => item.id === state.selectedSolutionId);
  document.querySelector('#route-dialog-title').textContent = solution
    ? `Densidade de CO2 · Solução ${solution.id}`
    : 'Densidade de CO2';
  drawExpandedRoute();
}

function showEmissionError(message) {
  const summary = document.querySelector('#route-emission-summary');
  summary.hidden = false;
  summary.classList.add('is-error');
  summary.textContent = message;
}

async function toggleEmissionHeatmap() {
  const button = document.querySelector('#route-emission-heatmap');
  const solution = state.solutions.find((item) => item.id === state.selectedSolutionId);
  if (state.routeViewMode === 'heatmap') {
    resetEmissionToggle();
    document.querySelector('#route-dialog-title').textContent = solution
      ? `Grafo da rota · Solução ${solution.id}`
      : 'Grafo da rota';
    showStoredEmissionFactor();
    drawExpandedRoute();
    return;
  }
  const key = currentRouteKey();
  if (!solution?.solutionId || !key || !state.activeRun?.run_id) return;
  const runId = state.activeRun.run_id;
  button.disabled = true;
  button.textContent = 'Calculando densidade...';
  try {
    const payload = state.routeEmission && state.routeEmissionKey === key
      ? state.routeEmission
      : await fetchJson(`/runs/${runId}/solutions/${solution.solutionId}/emission`);
    if (currentRouteKey() !== key || !document.querySelector('#route-dialog').open) return;
    state.routeEmission = payload;
    state.routeEmissionKey = key;
    if (solution.solutionId) state.emissionsBySolution[solution.solutionId] = payload;
    if (!payload.heatmap) {
      showEmissionError(payload.heatmap_message || 'A densidade de CO2 não está disponível para esta solução.');
      return;
    }
    let scale = state.emissionHeatmapScaleRunId === runId
      ? state.emissionHeatmapScale
      : null;
    if (!window.EmissionHeatmap.isValidScale(scale)) {
      scale = await fetchJson(`/runs/${runId}/emissions/heatmap-scale`);
      if (!window.EmissionHeatmap.isValidScale(scale)) {
        throw new Error('A resposta da escala comum do heatmap é inválida.');
      }
      state.emissionHeatmapScale = scale;
      state.emissionHeatmapScaleRunId = runId;
    }
    if (currentRouteKey() !== key || !document.querySelector('#route-dialog').open) return;
    activateEmissionHeatmap();
  } catch (error) {
    if (currentRouteKey() === key) showEmissionError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Densidade de CO2 (kg, suavizada)';
  }
}

function openRouteViewer() {
  if (!state.routeGraph || state.routeGraphKey !== currentRouteKey()) return;
  routeView.zoom = 1;
  routeView.panX = 0;
  routeView.panY = 0;
  const solution = state.solutions.find((item) => item.id === state.selectedSolutionId);
  document.querySelector('#route-dialog-title').textContent = solution
    ? `Grafo da rota · Solução ${solution.id}`
    : 'Grafo da rota';
  resetEmissionToggle();
  showStoredEmissionFactor();
  updateRouteZoomControls();
  const routeDialog = document.querySelector('#route-dialog');
  if (!routeDialog.open) routeDialog.showModal();
  document.querySelector('#route-zoom-out').focus();
  window.requestAnimationFrame(drawExpandedRoute);
}

function syncComparisonControls() {
  if (window.SolutionCompare) {
    const known = new Set(unionChartSolutions().map((item) => item.id));
    state.comparedIds = state.comparedIds.filter((id) => known.has(id));
  }
  const button = document.querySelector('#compare-solutions');
  const status = document.querySelector('#compare-selection-status');
  const includeButton = document.querySelector('#toggle-compare-solution');
  const count = state.comparedIds.length;
  if (button && !button.dataset.loading) {
    button.hidden = count < 2;
    button.disabled = false;
    button.textContent = 'Comparar soluções';
  }
  if (status) {
    if (!count || !window.SolutionCompare) {
      status.hidden = true;
      status.textContent = '';
    } else if (count === 1) {
      const style = SolutionCompare.comparisonStyle(0);
      status.hidden = false;
      status.textContent = `1 solução marcada (${style.patternLabel}). Ctrl+clique em outra solução do mapa para comparar.`;
    } else {
      const summary = state.comparedIds.map((id, index) => {
        const style = SolutionCompare.comparisonStyle(index);
        return `Solução ${id}, ${style.patternLabel}`;
      }).join('; ');
      status.hidden = false;
      status.textContent = `${count} soluções na comparação: ${summary}.`;
    }
  }
  if (includeButton) {
    const solution = findDisplayedSolution(selectedId);
    const included = Boolean(solution) && state.comparedIds.includes(solution.id);
    includeButton.disabled = !solution;
    includeButton.textContent = included ? 'Remover da comparação' : 'Incluir na comparação';
    includeButton.setAttribute('aria-pressed', String(included));
  }
}

function toggleComparison(id) {
  const solution = findDisplayedSolution(id);
  if (!solution || !window.SolutionCompare) return;
  const adding = !state.comparedIds.includes(id);
  state.comparedIds = SolutionCompare.toggleComparedId(state.comparedIds, id);
  if (adding) selectSolution(id);
  else renderTable();
}

async function withEdgeWeights(entries) {
  const missing = entries.some((entry) => (entry.graph.edges || []).some((edge) => edge.time == null || edge.distance == null));
  if (!missing || !state.selectedInstanceId) return entries;
  let timeMatrix = null;
  let distanceMatrix = null;
  try {
    [timeMatrix, distanceMatrix] = await Promise.all([
      fetchJson(`/instances/${state.selectedInstanceId}/analysis/input/matrix?objective=time`),
      fetchJson(`/instances/${state.selectedInstanceId}/analysis/input/matrix?objective=distance`),
    ]);
  } catch {
    return entries;
  }
  return entries.map((entry) => ({
    ...entry,
    graph: {
      ...entry.graph,
      edges: (entry.graph.edges || []).map((edge) => ({
        ...edge,
        time: edge.time ?? SolutionCompare.matrixValue(timeMatrix, edge.source, edge.target),
        distance: edge.distance ?? SolutionCompare.matrixValue(distanceMatrix, edge.source, edge.target),
      })),
    },
  }));
}

function renderComparisonSummary() {
  const entries = state.comparisonEntries || [];
  document.querySelector('#compare-dialog-kicker').textContent = state.comparisonIllustrative
    ? 'COMPARAÇÃO · DADOS ILUSTRATIVOS'
    : 'COMPARAÇÃO DE SOLUÇÕES';
  document.querySelector('#compare-dialog-note').textContent = state.comparisonIllustrative
    ? 'Rotas de exemplo do protótipo. O tempo e a distância de cada aresta repartem os totais da solução.'
    : 'Cada solução usa uma cor e um traço. Passe o mouse sobre uma aresta para ler o tempo e a distância daquele arco.';
  const list = document.querySelector('#compare-metrics');
  list.replaceChildren(...entries.map((entry, index) => {
    const style = SolutionCompare.comparisonStyle(index);
    const item = document.createElement('li');
    const swatch = document.createElement('i');
    swatch.className = 'compare-swatch';
    swatch.style.color = style.color;
    swatch.style.borderTopStyle = style.dash.length ? 'dashed' : 'solid';
    swatch.setAttribute('aria-hidden', 'true');
    const name = document.createElement('strong');
    name.textContent = `Solução ${entry.solution.id}`;
    const pattern = document.createElement('span');
    pattern.className = 'sr-only';
    pattern.textContent = style.patternLabel;
    const distance = document.createElement('span');
    distance.textContent = `Distância ${SolutionCompare.formatObjective(entry.solution.cost, 'km')}`;
    const time = document.createElement('span');
    time.textContent = `Tempo ${SolutionCompare.formatObjective(entry.solution.coverage, 'h')}`;
    item.append(swatch, name, pattern, distance, time);
    return item;
  }));
}

function updateCompareZoomControls() {
  const percent = `${Math.round(compareView.zoom * 100)}%`;
  document.querySelector('#compare-zoom-level').textContent = percent;
  document.querySelector('#compare-zoom-out').disabled = compareView.zoom <= ROUTE_ZOOM_MIN + 0.001;
  document.querySelector('#compare-zoom-in').disabled = compareView.zoom >= ROUTE_ZOOM_MAX - 0.001;
}

function drawComparisonGraph() {
  const dialog = document.querySelector('#compare-dialog');
  const canvas = document.querySelector('#compare-canvas');
  if (!dialog?.open || !canvas) return;
  const bounds = canvas.getBoundingClientRect();
  if (bounds.width < 2 || bounds.height < 2) return;
  const context = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const zoom = compareView.zoom;
  const panX = compareView.panX;
  const panY = compareView.panY;
  canvas.width = Math.max(1, Math.round(bounds.width * ratio));
  canvas.height = Math.max(1, Math.round(bounds.height * ratio));
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, bounds.width, bounds.height);
  comparisonHits = [];
  const entries = state.comparisonEntries || [];
  const nodes = entries.reduce((best, entry) => {
    const candidate = entry.graph.nodes || [];
    return candidate.length > best.length ? candidate : best;
  }, []);
  if (!nodes.length) {
    context.fillStyle = '#78817b';
    context.font = '12px "DM Sans", sans-serif';
    context.fillText('Layout da instância indisponível', 16, 28);
    canvas.setAttribute('aria-label', 'Comparação sem layout de cidades');
    return;
  }
  if (zoom !== 1 || panX !== 0 || panY !== 0) {
    context.setTransform(ratio * zoom, 0, 0, ratio * zoom, ratio * panX, ratio * panY);
  }
  const { pointFor } = routeLayout(nodes, bounds.width, bounds.height, true);
  entries.forEach((entry, index) => {
    const style = SolutionCompare.comparisonStyle(index);
    const offset = (index - (entries.length - 1) / 2) * 4;
    context.strokeStyle = style.color;
    context.lineWidth = 2.2;
    context.setLineDash(style.dash);
    (entry.graph.edges || []).forEach((edge) => {
      const source = pointFor(edge.source);
      const target = pointFor(edge.target);
      if (!source || !target) return;
      const shifted = SolutionCompare.offsetSegment(source, target, offset);
      context.beginPath();
      context.moveTo(shifted.source.x, shifted.source.y);
      context.lineTo(shifted.target.x, shifted.target.y);
      context.stroke();
      comparisonHits.push({
        source: shifted.source,
        target: shifted.target,
        time: edge.time,
        distance: edge.distance,
        from: edge.source,
        to: edge.target,
        solution: entry.solution,
      });
    });
  });
  context.setLineDash([]);
  nodes.forEach((node) => {
    const point = pointFor(node.id);
    if (!point) return;
    context.beginPath();
    context.arc(point.x, point.y, 4.2, 0, Math.PI * 2);
    context.fillStyle = '#28624d';
    context.fill();
    context.save();
    context.translate(point.x, point.y);
    context.scale(1 / zoom, 1 / zoom);
    context.fillStyle = '#182b25';
    context.font = '12px "IBM Plex Mono", monospace';
    context.fillText(String(node.label ?? node.id), 6, -6);
    context.restore();
  });
  entries.forEach((entry, index) => {
    const origin = pointFor(entry.graph.route?.[0]);
    if (!origin) return;
    const style = SolutionCompare.comparisonStyle(index);
    context.beginPath();
    context.arc(origin.x, origin.y, 7 + index * 2, 0, Math.PI * 2);
    context.strokeStyle = style.color;
    context.lineWidth = 1.6;
    context.stroke();
  });
  const labels = entries.map((entry) => entry.solution.id).join(', ');
  canvas.setAttribute('aria-label', labels
    ? `Rotas sobrepostas das soluções ${labels}`
    : 'Rotas sobrepostas das soluções selecionadas');
}

function zoomComparisonTo(nextZoom, originX, originY) {
  const zoom = Math.min(ROUTE_ZOOM_MAX, Math.max(ROUTE_ZOOM_MIN, nextZoom));
  if (Math.abs(zoom - compareView.zoom) < 0.0001) {
    updateCompareZoomControls();
    return;
  }
  const worldX = (originX - compareView.panX) / compareView.zoom;
  const worldY = (originY - compareView.panY) / compareView.zoom;
  compareView.zoom = zoom;
  compareView.panX = originX - worldX * zoom;
  compareView.panY = originY - worldY * zoom;
  updateCompareZoomControls();
  drawComparisonGraph();
}

function compareViewerCenter() {
  const bounds = document.querySelector('#compare-canvas').getBoundingClientRect();
  return { x: bounds.width / 2, y: bounds.height / 2 };
}

function resetCompareZoom() {
  compareView.zoom = 1;
  compareView.panX = 0;
  compareView.panY = 0;
  updateCompareZoomControls();
  drawComparisonGraph();
}

function openComparisonDialog() {
  compareView.zoom = 1;
  compareView.panX = 0;
  compareView.panY = 0;
  renderComparisonSummary();
  updateCompareZoomControls();
  const dialog = document.querySelector('#compare-dialog');
  if (!dialog.open) dialog.showModal();
  document.querySelector('#compare-zoom-out').focus();
  window.requestAnimationFrame(drawComparisonGraph);
}

function showComparisonTooltip(hit, screenX, screenY) {
  const tooltip = document.querySelector('#compare-tooltip');
  const stage = document.querySelector('#compare-viewer-stage');
  tooltip.replaceChildren();
  const title = document.createElement('strong');
  title.textContent = `Aresta ${hit.from} → ${hit.to}`;
  const solution = document.createElement('span');
  solution.textContent = `Solução ${hit.solution.id}`;
  const distance = document.createElement('span');
  distance.textContent = `Distância: ${SolutionCompare.formatObjective(hit.distance, 'km')}`;
  const time = document.createElement('span');
  time.textContent = `Tempo: ${SolutionCompare.formatObjective(hit.time, 'h')}`;
  tooltip.append(title, solution, distance, time);
  tooltip.hidden = false;
  tooltip.style.left = `${Math.min(screenX + 12, Math.max(8, stage.clientWidth - 190))}px`;
  tooltip.style.top = `${Math.max(8, Math.min(screenY - 56, stage.clientHeight - 84))}px`;
}

function hoverComparisonEdge(event) {
  const tooltip = document.querySelector('#compare-tooltip');
  if (comparePan || !window.SolutionCompare) {
    tooltip.hidden = true;
    return;
  }
  const canvas = document.querySelector('#compare-canvas');
  const bounds = canvas.getBoundingClientRect();
  const screenX = event.clientX - bounds.left;
  const screenY = event.clientY - bounds.top;
  const hit = SolutionCompare.nearestEdge({
    x: (screenX - compareView.panX) / compareView.zoom,
    y: (screenY - compareView.panY) / compareView.zoom,
  }, comparisonHits, 8 / compareView.zoom);
  if (!hit.edge) {
    tooltip.hidden = true;
    return;
  }
  showComparisonTooltip(hit.edge, screenX, screenY);
}

function endComparePan(event) {
  if (!comparePan || (event && comparePan.id !== event.pointerId)) return;
  comparePan = null;
  document.querySelector('#compare-canvas').classList.remove('is-panning');
}

async function openComparison() {
  if (!window.SolutionCompare || state.comparedIds.length < 2) return;
  const ids = state.comparedIds.slice();
  const requestId = ++comparisonRequest;
  const button = document.querySelector('#compare-solutions');
  button.dataset.loading = '1';
  button.disabled = true;
  button.textContent = 'Carregando rotas...';
  try {
    const entries = await Promise.all(ids.map(async (id) => {
      const solution = findDisplayedSolution(id);
      if (!solution) throw new Error(`A solução ${id} não está mais no mapa.`);
      if (state.resultIsDemo) return { solution, graph: SolutionCompare.illustrativeGraph(solution) };
      if (!solution.solutionId || !state.activeRun?.run_id) {
        throw new Error(`A solução ${solution.id} não tem rota disponível.`);
      }
      const graph = await fetchJson(`/runs/${state.activeRun.run_id}/solutions/${solution.solutionId}/graph`);
      return { solution, graph };
    }));
    if (requestId !== comparisonRequest) return;
    const weighted = state.resultIsDemo ? entries : await withEdgeWeights(entries);
    if (requestId !== comparisonRequest) return;
    state.comparisonEntries = weighted;
    state.comparisonIllustrative = weighted.some((entry) => entry.graph.illustrative);
    openComparisonDialog();
  } catch (error) {
    if (requestId === comparisonRequest) {
      setApiStatus(`Não foi possível comparar as soluções: ${error.message}`, true);
    }
  } finally {
    if (requestId === comparisonRequest) {
      delete button.dataset.loading;
      button.textContent = 'Comparar soluções';
      syncComparisonControls();
    }
  }
}

function endRoutePan(event) {
  if (!routePan || (event && routePan.id !== event.pointerId)) return;
  routePan = null;
  document.querySelector('#route-viewer-canvas').classList.remove('is-panning');
}

async function downloadSelectedRoute() {
  const solution = state.solutions.find((item) => item.id === state.selectedSolutionId);
  if (!solution?.solutionId || !state.activeRun?.run_id) return;
  try {
    const response = await fetch(`${API_BASE_URL}/runs/${state.activeRun.run_id}/solutions/${solution.solutionId}/route.csv`);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload?.error?.message || `Falha na requisição (${response.status})`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `rota-${solution.id}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    setApiStatus(`Não foi possível baixar a rota: ${error.message}`, true);
  }
}

const chart = document.querySelector('#pareto-chart');
const chartContext = chart.getContext('2d');
const tableBody = document.querySelector('#solutions-body');
const tooltip = document.querySelector('#chart-tooltip');
const searchInput = document.querySelector('#solution-search');
let selectedId = '018';
let activeView = 'frontier';
let visibleSolutions = [];
let plottedPoints = [];
let plottedReferences = [];

function renderTable() {
  syncComparisonControls();
  const query = searchInput.value.trim().toLowerCase();
  const approximate = approximateDisplay();
  const source = filterVisibleRoundSolutions(approximate ? approximate.solutions : state.solutions);
  visibleSolutions = source.filter((solution) => {
    const matchesSearch = `${solution.id} ${solution.cost} ${solution.coverage}`.toLowerCase().includes(query);
    const matchesView = Boolean(approximate) || activeView === 'all' || solution.frontier;
    return matchesSearch && matchesView;
  });

  if (state.tableOffset >= visibleSolutions.length && state.tableOffset > 0) {
    state.tableOffset = Math.max(0, Math.floor((visibleSolutions.length - 1) / state.tablePageSize) * state.tablePageSize);
  }
  const pageSolutions = visibleSolutions.slice(state.tableOffset, state.tableOffset + state.tablePageSize);
  tableBody.innerHTML = pageSolutions.map((solution) => {
    const comparedIndex = state.comparedIds.indexOf(solution.id);
    const style = comparedIndex >= 0 && window.SolutionCompare ? SolutionCompare.comparisonStyle(comparedIndex) : null;
    const swatch = style
      ? `<i class="compare-row-swatch" style="border-top-color:${style.color};border-top-style:${style.dash.length ? 'dashed' : 'solid'}" aria-hidden="true"></i>`
      : '';
    return `
    <tr class="${solution.id === selectedId ? 'selected-row' : ''}${style ? ' compared-row' : ''}" data-solution="${solution.id}" tabindex="0" aria-selected="${solution.id === selectedId}">
      <td><span class="table-id">${swatch}SOL-${solution.id}</span></td>
      <td><span class="table-number">${solution.cost.toFixed(2)} km</span></td>
      <td><span class="table-number">${solution.coverage.toFixed(2)} h</span></td>
      <td><span class="status-pill ${(approximate ? approximate.frontierIds.has(solution.id) : solution.frontier) ? 'frontier' : 'dominated'}">${(approximate ? approximate.frontierIds.has(solution.id) : solution.frontier) ? 'Não dominada' : 'Dominada'}</span>${solution.round ? `<span class="round-label">Rodada ${solution.round}</span>` : ''}</td>
      <td class="row-arrow" aria-hidden="true">↗</td>
    </tr>`;
  }).join('');

  const shown = pageSolutions.length;
  const tableSummary = document.querySelector('#table-summary');
  if (approximate && !query) {
    tableSummary.textContent = `Fronteira aproximada · ${approximate.frontier.length} não dominadas e ${approximate.dominated.length} dominadas na união`;
  } else if (!state.solutions.length && !approximate) {
    tableSummary.textContent = state.resultIsDemo
      ? 'Dados ilustrativos do protótipo'
      : state.activeRun?.status === 'completed' ? 'A execução não retornou soluções.' : 'Execute a instância para gerar soluções.';
  } else {
    tableSummary.textContent = query
      ? `Encontradas ${visibleSolutions.length} soluções nesta página`
      : state.resultIsDemo
        ? `Dados ilustrativos · ${visibleSolutions.length} soluções`
        : `Soluções ${state.resultOffset + state.tableOffset + 1}–${state.resultOffset + state.tableOffset + shown} de ${state.resultTotal || visibleSolutions.length}`;
  }
  document.querySelector('.table-count').textContent = visibleSolutions.length;
  document.querySelector('#data-mode-tag').textContent = state.resultIsDemo ? 'DADOS ILUSTRATIVOS' : 'DADOS DA API';
  document.querySelector('#previous-page').disabled = state.tableOffset === 0 && state.resultOffset === 0;
  document.querySelector('#next-page').disabled =
    state.tableOffset + state.tablePageSize >= visibleSolutions.length
    && (state.resultIsDemo || state.resultOffset + state.solutions.length >= state.resultTotal);
  document.querySelector('#page-indicator').textContent = `${Math.floor(state.tableOffset / state.tablePageSize) + 1} / ${Math.max(1, Math.ceil(visibleSolutions.length / state.tablePageSize))}`;
  document.querySelector('#export-csv').disabled = !state.resultIsDemo && !state.solutions.length && !approximate;
  renderRoundFilters();
  drawChart();
  renderReferenceDistance();
  renderHypervolume();
  renderQualityEvolution();
  renderMapModeStatus();
  syncRoutePreview();
}

function drawChart() {
  const bounds = chart.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  chart.width = Math.max(1, Math.round(bounds.width * ratio));
  chart.height = Math.max(1, Math.round(bounds.height * ratio));
  chartContext.setTransform(ratio, 0, 0, ratio, 0, 0);

  const width = bounds.width;
  const height = bounds.height;
  const inset = { left: 39, right: 13, top: 14, bottom: 25 };
  const plotWidth = width - inset.left - inset.right;
  const plotHeight = height - inset.top - inset.bottom;
  const referenceForScale = displayedReferencePoints();
  const scaleActive = Boolean(state.showNormalizedScale && referenceForScale && window.ReferencePoints);
  const referencePoints = state.showReferencePoints ? referenceForScale : null;
  const approximate = approximateDisplay();
  const approximatePoints = approximate ? approximate.frontier : null;
  const selected = findDisplayedSolution(selectedId);
  const selectedVisible = isSolutionRoundVisible(selected) ? selected : null;
  const axisPoint = (point) => (
    scaleActive ? ReferencePoints.normalizeToPercent(point, referenceForScale) : { cost: point.cost, coverage: point.coverage }
  );
  const scalePoints = [];
  const seenScaleIds = new Set();
  (approximate ? approximate.solutions : chartFrontierSolutions().concat(filterVisibleRoundSolutions(state.solutions))).forEach((solution) => {
    if (seenScaleIds.has(solution.id)) return;
    seenScaleIds.add(solution.id);
    scalePoints.push(solution);
  });
  if (referencePoints) scalePoints.push(referencePoints.utopian, referencePoints.antiutopian);
  if (selectedVisible) scalePoints.push(selectedVisible);
  const chartReference = (state.showHypervolume || state.showHypervolumeReference) && window.Hypervolume
    ? Hypervolume.objectiveReferencePoint(displayedReferencePoints())
    : null;
  if (chartReference && Number.isFinite(chartReference.cost) && Number.isFinite(chartReference.coverage)) {
    scalePoints.push(chartReference);
  }
  const axisValues = scalePoints.map(axisPoint);
  const costs = axisValues.map((point) => point.cost);
  const coverages = axisValues.map((point) => point.coverage);
  let minCost = costs.length ? Math.min(...costs) : 0;
  let maxCost = costs.length ? Math.max(...costs) : 1;
  let minCoverage = coverages.length ? Math.min(...coverages) : 0;
  let maxCoverage = coverages.length ? Math.max(...coverages) : 1;
  if (scaleActive) {
    minCost = Math.min(0, minCost);
    maxCost = Math.max(100, maxCost);
    minCoverage = Math.min(0, minCoverage);
    maxCoverage = Math.max(100, maxCoverage);
  }
  const costRange = Math.max(maxCost - minCost, scaleActive ? 1 : 1);
  const coverageRange = Math.max(maxCoverage - minCoverage, 1);
  const costPadding = scaleActive ? 0 : costRange * 0.1;
  const coveragePadding = scaleActive ? 0 : coverageRange * 0.1;
  const formatTick = scaleActive ? (value) => `${Math.round(value)}%` : (value) => value.toFixed(1);
  const normalizedX = (cost) => inset.left + ((cost - (minCost - costPadding)) / (costRange + costPadding * 2)) * plotWidth;
  const normalizedY = (coverage) => inset.top + (((maxCoverage + coveragePadding) - coverage) / (coverageRange + coveragePadding * 2)) * plotHeight;
  const place = (point) => {
    const axis = axisPoint(point);
    return { x: normalizedX(axis.cost), y: normalizedY(axis.coverage) };
  };
  setAxisTitle('#y-axis-title', scaleActive ? 'Tempo (%)' : 'Tempo (h)', '↑');
  setAxisTitle('#x-axis-title', scaleActive ? 'Distância (%)' : 'Distância (km)', '→');
  chart.setAttribute(
    'aria-label',
    [
      scaleActive
        ? 'Gráfico da fronteira de Pareto em percentual do utópico ao nadir.'
        : 'Gráfico da fronteira de Pareto. Cada rodada aparece com uma cor própria. Tempo em horas no eixo vertical e distância em quilômetros no eixo horizontal.',
      referencePoints ? 'A solução utópica e a solução antiutópica também estão marcadas.' : '',
      state.showDominanceCone ? 'O cone de dominância sombreia a região pior ou igual à solução selecionada.' : '',
      approximate ? 'A fronteira aproximada da união está em destaque e as soluções dominadas continuam visíveis.' : '',
      state.showHypervolume ? 'A área do hipervolume de cada rodada está anotada no mapa.' : '',
      state.showHypervolumeReference ? 'A referência do hipervolume está marcada com um círculo e uma cruz.' : '',
    ].filter(Boolean).join(' '),
  );

  chartContext.clearRect(0, 0, width, height);
  chartContext.font = '9px "IBM Plex Mono", monospace';
  chartContext.textBaseline = 'middle';
  chartContext.lineWidth = 1;

  for (let tick = 0; tick <= 4; tick += 1) {
    const value = minCoverage - coveragePadding + ((coverageRange + coveragePadding * 2) * (4 - tick)) / 4;
    const position = inset.top + (plotHeight * tick) / 4;
    chartContext.strokeStyle = '#e9ebe3';
    chartContext.beginPath();
    chartContext.moveTo(inset.left, position);
    chartContext.lineTo(width - inset.right, position);
    chartContext.stroke();
    chartContext.fillStyle = '#89928a';
    chartContext.textAlign = 'right';
    chartContext.fillText(formatTick(value), inset.left - 8, position);
  }

  for (let tick = 0; tick <= 4; tick += 1) {
    const value = minCost - costPadding + ((costRange + costPadding * 2) * tick) / 4;
    const position = inset.left + (plotWidth * tick) / 4;
    chartContext.strokeStyle = '#eff0ea';
    chartContext.beginPath();
    chartContext.moveTo(position, inset.top);
    chartContext.lineTo(position, height - inset.bottom);
    chartContext.stroke();
    chartContext.fillStyle = '#89928a';
    chartContext.textAlign = 'center';
    chartContext.fillText(formatTick(value), position, height - 11);
  }

  const hypervolumeLabels = state.showHypervolume ? shadeHypervolume(place, inset, width, height) : [];
  const series = approximatePoints
    ? [{
      round: null,
      label: 'Fronteira aproximada',
      color: '#28624d',
      dash: [],
      points: approximatePoints.slice().sort((left, right) => left.cost - right.cost || left.coverage - right.coverage),
    }]
    : ParetoFrontierSeries.frontierSeriesFromSolutions(chartFrontierSolutions());
  const multiRound = !approximatePoints && series.some((item) => item.round != null);
  if (selectedVisible && state.showDominanceCone) shadeDominanceCone(place(selectedVisible), directionsWorseToward(scaleActive), inset, width, height);
  ParetoFrontierSeries.strokeFrontierSeries(chartContext, series, (solution) => place(solution));
  renderRoundLegend(series);
  const approximateKey = document.querySelector('#approximate-frontier-key');
  const scaleKey = document.querySelector('#scale-key');
  const coneKey = document.querySelector('#cone-key');
  if (approximate) {
    const singleKey = document.querySelector('#single-frontier-key');
    const dominatedKey = document.querySelector('#dominated-key');
    if (singleKey) singleKey.hidden = true;
    if (dominatedKey) dominatedKey.hidden = false;
  } else {
    const dominatedKey = document.querySelector('#dominated-key');
    if (dominatedKey) dominatedKey.hidden = false;
  }
  if (approximateKey) approximateKey.hidden = !approximatePoints;
  if (scaleKey) scaleKey.hidden = !scaleActive;
  if (coneKey) coneKey.hidden = !(state.showDominanceCone && selectedVisible);
  const hypervolumeKey = document.querySelector('#hypervolume-key');
  if (hypervolumeKey) hypervolumeKey.hidden = !state.showHypervolume || !hypervolumeLabels.length;
  const hypervolumeReferenceKey = document.querySelector('#hypervolume-reference-key');
  const referenceMarkerVisible = Boolean(
    state.showHypervolumeReference
    && chartReference
    && Number.isFinite(chartReference.cost)
    && Number.isFinite(chartReference.coverage),
  );
  if (hypervolumeReferenceKey) hypervolumeReferenceKey.hidden = !referenceMarkerVisible;
  const utopianKey = document.querySelector('#reference-key-utopian');
  const antiutopianKey = document.querySelector('#reference-key-antiutopian');
  if (utopianKey) utopianKey.hidden = !referencePoints;
  if (antiutopianKey) antiutopianKey.hidden = !referencePoints;
  const colorById = new Map();
  series.forEach((item) => {
    item.points.forEach((point) => colorById.set(point.id, item.color));
  });

  plottedPoints = [];
  plottedReferences = [];
  if (referencePoints && selectedVisible?.frontier) {
    const origin = place(selectedVisible);
    [referencePoints.utopian, referencePoints.antiutopian].forEach((anchor) => {
      const target = place(anchor);
      chartContext.beginPath();
      chartContext.moveTo(origin.x, origin.y);
      chartContext.lineTo(target.x, target.y);
      chartContext.setLineDash(anchor.id === 'utopian' ? [2, 3] : [6, 4]);
      chartContext.strokeStyle = '#182b25';
      chartContext.lineWidth = 1;
      chartContext.stroke();
    });
    chartContext.setLineDash([]);
  }
  const frontierPoints = series.flatMap((item) => item.points);
  let pointsToDraw = approximate
    ? approximate.solutions
    : activeView === 'all'
      ? frontierPoints.concat(filterVisibleRoundSolutions(state.solutions).filter((solution) => !solution.frontier && !frontierPoints.some((point) => point.id === solution.id)))
      : frontierPoints;
  if (selectedVisible && state.showDominanceCone && !pointsToDraw.some((point) => point.id === selectedVisible.id)) {
    pointsToDraw = pointsToDraw.concat(selectedVisible);
  }
  if (state.showDominanceCone && selectedVisible && window.ReferencePoints) {
    pointsToDraw = ReferencePoints.visibleUnderCone(
      pointsToDraw,
      selectedVisible,
      referenceForScale || { directions: objectiveDirections() },
      scaleActive,
    );
  }
  pointsToDraw.forEach((solution) => {
    const position = place(solution);
    const px = position.x;
    const py = position.y;
    const isSelected = solution.id === selectedId;
    const isFrontier = approximate ? approximate.frontierIds.has(solution.id) : solution.frontier;
    const seriesColor = colorById.get(solution.id);
    plottedPoints.push({ solution, x: px, y: py });

    chartContext.beginPath();
    chartContext.arc(px, py, isSelected ? 6 : isFrontier ? 4.5 : 3.5, 0, Math.PI * 2);
    if (!multiRound) {
      chartContext.fillStyle = isSelected ? '#d96545' : isFrontier ? '#28624d' : '#fffefa';
    } else if (isFrontier && seriesColor) {
      chartContext.fillStyle = seriesColor;
    } else {
      chartContext.fillStyle = '#fffefa';
    }
    chartContext.fill();
    chartContext.strokeStyle = isFrontier || isSelected ? '#fffefa' : '#a9b5aa';
    chartContext.lineWidth = isSelected ? 2 : 1.2;
    chartContext.stroke();
    if (isSelected) {
      chartContext.beginPath();
      chartContext.arc(px, py, 10, 0, Math.PI * 2);
      chartContext.strokeStyle = multiRound ? 'rgb(24 43 37 / 28%)' : 'rgb(217 101 69 / 27%)';
      chartContext.lineWidth = 4;
      chartContext.stroke();
    }
    const comparedIndex = state.comparedIds.indexOf(solution.id);
    if (comparedIndex >= 0 && window.SolutionCompare) {
      const style = SolutionCompare.comparisonStyle(comparedIndex);
      chartContext.beginPath();
      chartContext.setLineDash(style.dash);
      chartContext.arc(px, py, isSelected ? 14 : 9, 0, Math.PI * 2);
      chartContext.strokeStyle = style.color;
      chartContext.lineWidth = 1.7;
      chartContext.stroke();
      chartContext.setLineDash([]);
    }
  });
  hypervolumeLabels.forEach((label) => {
    drawReferenceLabel(label.text, label.x, label.y, true, width, height, inset);
  });
  if (referenceMarkerVisible) {
    const referencePosition = place(chartReference);
    plottedReferences.push({
      kind: 'hypervolume-reference',
      point: { id: 'hypervolume-reference', label: Hypervolume.REFERENCE_LABEL, ...chartReference },
      x: referencePosition.x,
      y: referencePosition.y,
    });
    drawHypervolumeReferenceMarker(referencePosition.x, referencePosition.y);
    drawReferenceLabel(Hypervolume.REFERENCE_LABEL, referencePosition.x, referencePosition.y, false, width, height, inset);
  }
  if (!referencePoints) return;
  const anchors = [referencePoints.antiutopian, referencePoints.utopian];
  const anchorPositions = anchors.map((anchor) => ({ anchor, ...place(anchor) }));
  const stacked = Math.hypot(
    anchorPositions[0].x - anchorPositions[1].x,
    anchorPositions[0].y - anchorPositions[1].y,
  ) < 14;
  anchorPositions.forEach((item) => {
    plottedReferences.push({ kind: 'reference', point: item.anchor, x: item.x, y: item.y });
    drawReferenceMarker(item.anchor, item.x, item.y);
    const labelY = stacked ? item.y + (item.anchor.id === 'utopian' ? -14 : 14) : item.y;
    drawReferenceLabel(item.anchor.label, item.x, labelY, item.anchor.id === 'utopian' && !stacked, width, height, inset);
  });
}

function setAxisTitle(selector, label, arrow) {
  const node = document.querySelector(selector);
  if (!node) return;
  const mark = document.createElement('span');
  mark.textContent = arrow;
  node.replaceChildren(document.createTextNode(`${label} `), mark);
}

function directionsWorseToward(scaleActive) {
  const directions = objectiveDirections();
  const costIncreases = scaleActive || directions.cost !== 'maximize';
  const coverageIncreases = scaleActive || directions.coverage !== 'maximize';
  return { x: costIncreases ? 1 : -1, y: coverageIncreases ? -1 : 1 };
}

function shadeDominanceCone(origin, signs, inset, width, height) {
  const plotLeft = inset.left;
  const plotRight = width - inset.right;
  const plotTop = inset.top;
  const plotBottom = height - inset.bottom;
  const x0 = signs.x > 0 ? origin.x : plotLeft;
  const x1 = signs.x > 0 ? plotRight : origin.x;
  const y0 = signs.y > 0 ? origin.y : plotTop;
  const y1 = signs.y > 0 ? plotBottom : origin.y;
  if (x1 - x0 < 1 || y1 - y0 < 1) return;
  chartContext.save();
  chartContext.beginPath();
  chartContext.rect(plotLeft, plotTop, plotRight - plotLeft, plotBottom - plotTop);
  chartContext.clip();
  chartContext.fillStyle = 'rgb(24 43 37 / 14%)';
  chartContext.fillRect(x0, y0, x1 - x0, y1 - y0);
  chartContext.beginPath();
  chartContext.rect(x0, y0, x1 - x0, y1 - y0);
  chartContext.clip();
  chartContext.strokeStyle = 'rgb(24 43 37 / 50%)';
  chartContext.lineWidth = 1;
  chartContext.setLineDash([]);
  chartContext.beginPath();
  const span = Math.max(x1 - x0, y1 - y0);
  for (let offset = -span; offset < span; offset += 8) {
    chartContext.moveTo(x0 + offset, y1);
    chartContext.lineTo(x0 + offset + (y1 - y0), y0);
  }
  chartContext.stroke();
  chartContext.restore();
}

function renderMapModeStatus() {
  const scaleStatus = document.querySelector('#scale-status');
  const coneStatus = document.querySelector('#cone-status');
  const hypervolumeStatus = document.querySelector('#hypervolume-status');
  if (scaleStatus) scaleStatus.hidden = !(state.showNormalizedScale && !displayedReferencePoints());
  if (coneStatus) coneStatus.hidden = !(state.showDominanceCone && !isSolutionRoundVisible(findDisplayedSolution(selectedId)));
  if (hypervolumeStatus) hypervolumeStatus.hidden = !(state.showHypervolume && !currentHypervolume());
}

function currentHypervolume() {
  if (!state.resultIsDemo && state.hypervolume) return state.hypervolume;
  if (state.resultIsDemo && window.Hypervolume) {
    return Hypervolume.summarizeChartSolutions(unionChartSolutions(), objectiveDirections());
  }
  return null;
}

function candidatePointsForRound(round) {
  const frontier = state.frontiers.find((item) => item.round === round);
  if (frontier && frontier.points.length) return frontier.points;
  return unionChartSolutions().filter((solution) => (solution.round || 1) === round && solution.frontier);
}

function hypervolumeForChart() {
  const summary = currentHypervolume();
  if (!summary) return null;
  const rounds = window.RoundFilter
    ? RoundFilter.filterHypervolumeRounds(summary.rounds, state.hiddenRounds)
    : summary.rounds;
  return {
    ...summary,
    rounds: rounds.map((round) => ({
      ...round,
      points: filterVisibleRoundSolutions(
        round.points && round.points.length ? round.points : candidatePointsForRound(round.round),
      ),
    })),
  };
}

function shadeHypervolume(place, inset, width, height) {
  const summary = hypervolumeForChart();
  const labels = [];
  if (!summary || !window.ParetoFrontierSeries || !window.Hypervolume) return labels;
  const chartReference = Hypervolume.objectiveReferencePoint(displayedReferencePoints());
  const canDrawArea = Boolean(
    chartReference && Number.isFinite(chartReference.cost) && Number.isFinite(chartReference.coverage),
  );
  const styles = ParetoFrontierSeries.FRONTIER_ROUND_STYLES;
  const directions = objectiveDirections();
  const minimizedCost = (point) => (directions.cost === 'maximize' ? -point.cost : point.cost);
  const minimizedCoverage = (point) => (directions.coverage === 'maximize' ? -point.coverage : point.coverage);
  chartContext.save();
  chartContext.beginPath();
  chartContext.rect(inset.left, inset.top, width - inset.left - inset.right, height - inset.top - inset.bottom);
  chartContext.clip();
  summary.rounds.forEach((round) => {
    const points = (round.points || []).filter((point) => Number.isFinite(point.cost) && Number.isFinite(point.coverage));
    if (!points.length) return;
    const style = styles.find((item) => item.round === round.round) || styles[(Math.max(round.round, 1) - 1) % styles.length];
    const ordered = points.slice().sort((left, right) => (
      minimizedCost(left) - minimizedCost(right) || minimizedCoverage(right) - minimizedCoverage(left)
    ));
    if (canDrawArea) ordered.forEach((point, index) => {
      const current = place(point);
      const nextCost = index === ordered.length - 1 ? chartReference.cost : ordered[index + 1].cost;
      const corner = place({ cost: nextCost, coverage: chartReference.coverage });
      const left = Math.min(current.x, corner.x);
      const top = Math.min(current.y, corner.y);
      const rectWidth = Math.abs(corner.x - current.x);
      const rectHeight = Math.abs(corner.y - current.y);
      if (rectWidth < 1 || rectHeight < 1) return;
      chartContext.save();
      chartContext.beginPath();
      chartContext.rect(left, top, rectWidth, rectHeight);
      chartContext.clip();
      chartContext.fillStyle = 'rgb(24 43 37 / 12%)';
      chartContext.fillRect(left, top, rectWidth, rectHeight);
      chartContext.strokeStyle = 'rgb(24 43 37 / 50%)';
      chartContext.lineWidth = 1;
      chartContext.setLineDash([]);
      chartContext.beginPath();
      const span = Math.max(rectWidth, rectHeight);
      for (let offset = -span; offset < span; offset += 8) {
        chartContext.moveTo(left + offset, top + rectHeight);
        chartContext.lineTo(left + offset + rectHeight, top);
      }
      chartContext.stroke();
      chartContext.restore();
      chartContext.strokeStyle = style.color;
      chartContext.lineWidth = 1.25;
      chartContext.setLineDash(style.dash || []);
      chartContext.strokeRect(left, top, rectWidth, rectHeight);
    });
    chartContext.setLineDash([]);
    const anchor = place(ordered[Math.floor(ordered.length / 2)]);
    labels.push({
      text: `Rodada ${round.round} · HV ${Hypervolume.formatHypervolume(round.hypervolume)}`,
      x: anchor.x,
      y: anchor.y,
    });
  });
  chartContext.restore();
  return labels;
}

function renderHypervolume() {
  const wrap = document.querySelector('#quality-rounds-wrap');
  const table = document.querySelector('#quality-rounds');
  const body = table ? table.querySelector('tbody') : null;
  const note = document.querySelector('#hypervolume-note');
  const summary = currentHypervolume();
  const view = window.Hypervolume ? Hypervolume.hypervolumeView(summary) : null;
  if (!view || !body) {
    setTimingValue('#hv-mean', '--');
    setTimingValue('#hv-stdev', '--');
    setHypervolumeCoefficient(null);
    setTimingValue('#hv-count', '--');
    setTimingValue('#spread-mean', '--');
    setTimingValue('#spread-stdev', '--');
    setSpreadCoefficient(null);
    if (body) body.replaceChildren();
    if (wrap) wrap.hidden = true;
    if (note) note.hidden = true;
    return;
  }
  setTimingValue('#hv-mean', view.mean);
  setTimingValue('#hv-stdev', view.stdev);
  setHypervolumeCoefficient(view);
  setTimingValue('#hv-count', view.meanCount);
  setTimingValue('#spread-mean', view.spreadMean);
  setTimingValue('#spread-stdev', view.spreadStdev);
  setSpreadCoefficient(view);
  const visibleRows = window.RoundFilter
    ? view.rows.filter((row) => RoundFilter.isRoundVisible(row.round, state.hiddenRounds))
    : view.rows;
  if (note) {
    note.hidden = !view.note;
    note.textContent = view.note;
  }
  if (wrap) wrap.hidden = false;
  body.replaceChildren(...visibleRows.map((row) => {
    const line = document.createElement('tr');
    const roundCell = document.createElement('th');
    roundCell.scope = 'row';
    roundCell.textContent = String(row.round);
    line.append(
      roundCell,
      qualityCell(row.hypervolume),
      qualityCell(row.candidateCount),
      qualityCell(row.distance),
      qualityCell(row.spread),
    );
    return line;
  }));
}

function qualityCell(value) {
  const cell = document.createElement('td');
  cell.textContent = value;
  return cell;
}

function resetQualityEvolution() {
  state.qualityEvolution = null;
  state.qualityEvolutionError = '';
}

async function loadQualityEvolution(instanceId) {
  if (!instanceId || state.resultIsDemo || !window.QualityEvolution) {
    resetQualityEvolution();
    return;
  }
  try {
    const payload = await fetchJson(`/instances/${instanceId}/quality-evolution`);
    if (state.selectedInstanceId !== instanceId) return;
    const mapped = QualityEvolution.mapApiQualityEvolution(payload);
    state.qualityEvolution = mapped;
    state.qualityEvolutionError = mapped ? '' : 'A resposta da evolução dos indicadores não pôde ser lida.';
  } catch (error) {
    if (state.selectedInstanceId !== instanceId) return;
    state.qualityEvolution = null;
    state.qualityEvolutionError = error.message;
  }
}

function renderQualityLegendItem(entry) {
  const item = document.createElement('li');
  const swatch = document.createElement('span');
  swatch.className = `quality-evolution-swatch ${entry.dashClass}`;
  swatch.style.color = entry.color;
  swatch.setAttribute('aria-hidden', 'true');
  const marker = document.createElement('span');
  marker.className = `quality-evolution-marker ${entry.markerClass}`;
  marker.style.color = entry.color;
  marker.setAttribute('aria-hidden', 'true');
  const name = document.createElement('span');
  name.textContent = entry.label;
  const assist = document.createElement('span');
  assist.className = 'sr-only';
  assist.textContent = `, ${entry.dashLabel}, ${entry.markerLabel}`;
  item.append(swatch, marker, name, assist);
  return item;
}

function applyQualityExpansion(prefix) {
  const button = document.querySelector(`#${prefix}-expand`);
  const article = document.querySelector(`#${prefix}-figure`);
  const expansion = QualityEvolution.chartExpansionState(state.qualityExpanded[prefix]);
  if (button) {
    button.textContent = expansion.label;
    button.setAttribute('aria-pressed', expansion.ariaPressed);
  }
  article?.classList.toggle('is-expanded', expansion.expanded);
}

function paintQualityFigure(figure, prefix, options = {}) {
  state.qualityFigures[prefix] = figure;
  if (figure.empty && state.qualityExpanded[prefix]) state.qualityExpanded[prefix] = false;
  applyQualityExpansion(prefix);
  const plot = document.querySelector(`#${prefix}-plot`);
  const empty = document.querySelector(`#${prefix}-empty`);
  const legend = document.querySelector(`#${prefix}-legend`);
  const canvas = document.querySelector(`#${prefix}-chart`);
  const tooltip = document.querySelector(`#${prefix}-tooltip`);
  const button = document.querySelector(`#${prefix}-expand`);
  const xTitle = document.querySelector(`#${prefix}-x`);
  const yTitle = document.querySelector(`#${prefix}-y`);
  if (button) button.disabled = Boolean(figure.empty);
  if (xTitle) xTitle.textContent = figure.xLabel;
  if (yTitle) yTitle.textContent = figure.yLabel;
  if (empty) {
    empty.hidden = !figure.empty;
    empty.textContent = figure.emptyMessage;
  }
  if (plot) plot.hidden = figure.empty;
  if (legend && options.legend !== false) {
    legend.hidden = figure.empty || !figure.curves.length;
    legend.replaceChildren(...QualityEvolution.legendEntries(figure).map(renderQualityLegendItem));
  }
  if (figure.empty) {
    if (tooltip) tooltip.hidden = true;
    state.qualityHover[prefix] = null;
    if (canvas) canvas.dataset.hoverKey = '';
    return;
  }
  if (!canvas) return;
  canvas.setAttribute('aria-label', QualityEvolution.figureDescription(figure));
  const bounds = canvas.getBoundingClientRect();
  if (bounds.width < 2 || bounds.height < 2) return;
  const context = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(bounds.width * ratio));
  canvas.height = Math.max(1, Math.round(bounds.height * ratio));
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  QualityEvolution.drawFigure(context, figure, bounds.width, bounds.height, state.qualityHover[prefix]);
}

function showQualityTooltip(prefix, hit, figure, pointer, width) {
  const tooltip = document.querySelector(`#${prefix}-tooltip`);
  if (!tooltip) return;
  const detail = QualityEvolution.hoverDetail(hit, figure);
  if (!detail) {
    tooltip.hidden = true;
    return;
  }
  const title = document.createElement('strong');
  title.textContent = detail.title;
  const lines = detail.lines.map((line) => {
    const span = document.createElement('span');
    span.textContent = line;
    return span;
  });
  tooltip.replaceChildren(title, ...lines);
  tooltip.hidden = false;
  tooltip.style.left = `${Math.min(pointer.x + 12, Math.max(8, width - 188))}px`;
  tooltip.style.top = `${Math.max(3, pointer.y - 52)}px`;
}

function bindQualityChart(prefix) {
  const button = document.querySelector(`#${prefix}-expand`);
  const canvas = document.querySelector(`#${prefix}-chart`);
  if (button) {
    button.addEventListener('click', () => {
      if (button.disabled) return;
      state.qualityExpanded[prefix] = !state.qualityExpanded[prefix];
      const figure = state.qualityFigures[prefix];
      if (figure) paintQualityFigure(figure, prefix);
    });
  }
  if (!canvas) return;
  canvas.addEventListener('pointermove', (event) => {
    const figure = state.qualityFigures[prefix];
    const tooltip = document.querySelector(`#${prefix}-tooltip`);
    if (!figure || figure.empty) {
      if (tooltip) tooltip.hidden = true;
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    const geometry = QualityEvolution.figureGeometry(figure, rect.width, rect.height);
    const hit = QualityEvolution.nearestEvolutionPoint(geometry.points, pointer.x, pointer.y);
    const key = hit ? `${hit.curveIndex}:${hit.pointIndex}` : '';
    if (canvas.dataset.hoverKey !== key) {
      canvas.dataset.hoverKey = key;
      state.qualityHover[prefix] = hit;
      paintQualityFigure(figure, prefix, { legend: false });
    }
    if (!hit) {
      if (tooltip) tooltip.hidden = true;
      return;
    }
    showQualityTooltip(prefix, hit, figure, pointer, rect.width);
  });
  canvas.addEventListener('pointerleave', () => {
    const tooltip = document.querySelector(`#${prefix}-tooltip`);
    if (tooltip) tooltip.hidden = true;
    if (!canvas.dataset.hoverKey) return;
    canvas.dataset.hoverKey = '';
    state.qualityHover[prefix] = null;
    const figure = state.qualityFigures[prefix];
    if (figure && !figure.empty) paintQualityFigure(figure, prefix, { legend: false });
  });
}

function renderQualityEvolution() {
  const section = document.querySelector('#quality-evolution');
  if (!section || !window.QualityEvolution) return;
  const visible = !state.resultIsDemo && Boolean(state.selectedInstanceId);
  section.hidden = !visible;
  if (!visible) return;
  const figures = QualityEvolution.qualityEvolutionFigures(state.qualityEvolution, {
    emptyMessage: state.qualityEvolutionError
      ? 'Não foi possível carregar a evolução dos indicadores.'
      : undefined,
  });
  paintQualityFigure(figures[0], 'hv-evolution');
  paintQualityFigure(figures[1], 'spread-evolution');
}

function drawHypervolumeReferenceMarker(px, py) {
  chartContext.save();
  chartContext.setLineDash([]);
  chartContext.lineWidth = 1.6;
  chartContext.strokeStyle = '#182b25';
  chartContext.fillStyle = '#fffefa';
  chartContext.beginPath();
  chartContext.arc(px, py, 6.5, 0, Math.PI * 2);
  chartContext.fill();
  chartContext.stroke();
  chartContext.beginPath();
  chartContext.moveTo(px - 3.5, py);
  chartContext.lineTo(px + 3.5, py);
  chartContext.moveTo(px, py - 3.5);
  chartContext.lineTo(px, py + 3.5);
  chartContext.stroke();
  chartContext.restore();
}

function drawReferenceMarker(anchor, px, py) {
  chartContext.lineWidth = 1.6;
  chartContext.strokeStyle = '#182b25';
  chartContext.setLineDash([]);
  if (anchor.id === 'utopian') {
    chartContext.beginPath();
    chartContext.moveTo(px, py - 7);
    chartContext.lineTo(px + 7, py);
    chartContext.lineTo(px, py + 7);
    chartContext.lineTo(px - 7, py);
    chartContext.closePath();
    chartContext.fillStyle = '#fffefa';
    chartContext.fill();
    chartContext.stroke();
    return;
  }
  chartContext.fillStyle = '#e5b94f';
  chartContext.fillRect(px - 6, py - 6, 12, 12);
  chartContext.strokeRect(px - 6, py - 6, 12, 12);
  chartContext.beginPath();
  chartContext.moveTo(px - 4, py - 4);
  chartContext.lineTo(px + 4, py + 4);
  chartContext.moveTo(px + 4, py - 4);
  chartContext.lineTo(px - 4, py + 4);
  chartContext.stroke();
}

function drawReferenceLabel(text, px, py, preferRight, width, height, inset) {
  chartContext.font = '9px "IBM Plex Mono", monospace';
  const measured = chartContext.measureText(text).width;
  let align = preferRight ? 'left' : 'right';
  let x = preferRight ? px + 12 : px - 12;
  if (preferRight && x + measured > width - 6) {
    align = 'right';
    x = px - 12;
  } else if (!preferRight && x - measured < inset.left) {
    align = 'left';
    x = px + 12;
  }
  let y = py;
  if (y < inset.top + 8) y = Math.min(height - 8, py + 16);
  if (y > height - 8) y = Math.max(inset.top + 8, py - 16);
  chartContext.textAlign = align;
  chartContext.textBaseline = 'middle';
  chartContext.lineWidth = 3;
  chartContext.strokeStyle = '#fffefa';
  chartContext.strokeText(text, x, y);
  chartContext.fillStyle = '#182b25';
  chartContext.fillText(text, x, y);
}

function renderReferenceDistance() {
  const panel = document.querySelector('#reference-distance');
  if (!panel || !window.ReferencePoints) return;
  const points = state.showReferencePoints ? displayedReferencePoints() : null;
  if (!points) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  document.querySelector('#reference-distance-heading').textContent = points.distanceLabel;
  const measurement = ReferencePoints.measureReferenceDistances(findDisplayedSolution(selectedId), points);
  const values = document.querySelector('#reference-distance-values');
  const note = document.querySelector('#reference-distance-note');
  if (!measurement.eligible) {
    values.hidden = true;
    note.textContent = 'Selecione uma solução da fronteira para medir a distância.';
    return;
  }
  values.hidden = false;
  document.querySelector('#distance-utopian').textContent = ReferencePoints.formatObjectiveDistance(measurement.toUtopian);
  document.querySelector('#distance-antiutopian').textContent = ReferencePoints.formatObjectiveDistance(measurement.toAntiutopian);
  const warning = (points.warnings || []).map((item) => item.message).filter(Boolean).join(' ');
  note.textContent = [points.distanceNote, points.note, warning].filter(Boolean).join(' ');
}

function renderRoundFilters() {
  const bar = document.querySelector('#round-filters');
  const host = document.querySelector('#round-filter-options');
  if (!bar || !host || !window.RoundFilter) return;
  const rounds = RoundFilter.listedRounds(unionChartSolutions(), state.frontiers);
  bar.hidden = rounds.length < 2;
  host.replaceChildren(...rounds.map((round) => {
    const label = document.createElement('label');
    label.className = 'reference-toggle';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = RoundFilter.isRoundVisible(round, state.hiddenRounds);
    input.addEventListener('change', () => {
      if (input.checked) state.hiddenRounds.delete(round);
      else state.hiddenRounds.add(round);
      state.tableOffset = 0;
      renderTable();
    });
    label.append(input, document.createTextNode(`Rodada ${round}`));
    return label;
  }));
}

function renderRoundLegend(series) {
  const legend = document.querySelector('#frontier-round-legend');
  const singleKey = document.querySelector('#single-frontier-key');
  if (!legend || !singleKey) return;
  const multiRound = series.some((item) => item.round != null);
  singleKey.hidden = multiRound;
  legend.hidden = !multiRound;
  legend.replaceChildren();
  if (!multiRound) return;
  series.forEach((item) => {
    const entry = document.createElement('span');
    const swatch = document.createElement('i');
    swatch.className = 'round-swatch';
    swatch.style.color = item.color;
    swatch.style.borderTopStyle = item.dash.length ? 'dashed' : 'solid';
    swatch.setAttribute('aria-hidden', 'true');
    entry.append(swatch, document.createTextNode(item.label));
    legend.append(entry);
  });
}

function selectSolution(id) {
  const solution = findDisplayedSolution(id);
  if (!solution) return;
  selectedId = id;
  state.selectedSolutionId = id;
  document.querySelector('#selected-title').textContent = `Solução ${solution.id}`;
  document.querySelector('#selected-cost').textContent = `${solution.cost.toFixed(2)} km`;
  document.querySelector('#selected-coverage').textContent = `${solution.coverage.toFixed(2)} h`;
  document.querySelector('#selected-items').textContent = solution.route?.length
    ? `${solution.route.length - 1} arcos`
    : `${solution.items} de 20`;
  const emissionNode = document.querySelector('#selected-emission');
  if (emissionNode) {
    const row = solution.solutionId ? state.emissionsBySolution[solution.solutionId] : null;
    emissionNode.textContent = window.EmissionHeatmap
      ? EmissionHeatmap.formatFactor(row && row.total_speed_emission_factor)
      : '--';
  }
  document.querySelector('#view-route').disabled = !solution.solutionId;
  document.querySelector('#download-route').disabled = !solution.solutionId;
  renderTable();
}

function setView(view) {
  activeView = view;
  state.tableOffset = 0;
  document.querySelectorAll('.segment').forEach((button) => {
    const selected = button.dataset.view === view;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-selected', String(selected));
  });
  renderTable();
}

tableBody.addEventListener('click', (event) => {
  const row = event.target.closest('tr[data-solution]');
  if (!row) return;
  if (event.ctrlKey || event.metaKey) {
    toggleComparison(row.dataset.solution);
    return;
  }
  selectSolution(row.dataset.solution);
});

tableBody.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const row = event.target.closest('tr[data-solution]');
  if (!row) return;
  event.preventDefault();
  if (event.ctrlKey || event.metaKey) toggleComparison(row.dataset.solution);
  else selectSolution(row.dataset.solution);
});

document.querySelectorAll('.segment').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));

function nearestChartPoint(pointer, points, limit) {
  return points.reduce((best, point) => {
    const distance = Math.hypot(point.x - pointer.x, point.y - pointer.y);
    return distance < best.distance ? { point, distance } : best;
  }, { point: null, distance: limit });
}

function chartHit(pointer) {
  const solutionHit = nearestChartPoint(pointer, plottedPoints, 18);
  const referenceHit = nearestChartPoint(pointer, plottedReferences, 16);
  if (referenceHit.point && (!solutionHit.point || referenceHit.distance <= solutionHit.distance)) {
    return referenceHit.point;
  }
  return solutionHit.point;
}

chart.addEventListener('pointermove', (event) => {
  const rect = chart.getBoundingClientRect();
  const pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  const hit = chartHit(pointer);

  if (!hit) {
    tooltip.hidden = true;
    return;
  }

  if (hit.kind === 'reference') {
    const { point } = hit;
    tooltip.innerHTML = `<strong>${point.label}</strong><span>Distância: ${point.cost.toFixed(2)} km</span><span>Tempo: ${point.coverage.toFixed(2)} h</span>`;
  } else {
    const { solution } = hit;
    const roundLine = solution.round ? `<span>Rodada ${solution.round}</span>` : '';
    tooltip.innerHTML = `<strong>SOL-${solution.id}</strong><span>Distância: ${solution.cost.toFixed(2)} km</span><span>Tempo: ${solution.coverage.toFixed(2)} h</span>${roundLine}`;
  }
  tooltip.hidden = false;
  tooltip.style.left = `${Math.min(pointer.x + 12, rect.width - 168)}px`;
  tooltip.style.top = `${Math.max(3, pointer.y - 47)}px`;
});

chart.addEventListener('pointerleave', () => { tooltip.hidden = true; });
chart.addEventListener('click', (event) => {
  const rect = chart.getBoundingClientRect();
  const pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  const hit = chartHit(pointer);
  if (!hit || hit.kind === 'reference') return;
  if (event.ctrlKey || event.metaKey) {
    toggleComparison(hit.solution.id);
    return;
  }
  selectSolution(hit.solution.id);
});

document.querySelector('#export-csv').addEventListener('click', () => {
  const header = 'solucao,distancia_km,tempo_h,status,rodada';
  const rows = visibleSolutions.map((solution) => `${solution.id},${solution.cost},${solution.coverage},${solution.frontier ? 'nao_dominada' : 'dominada'},${solution.round || ''}`);
  const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'paretolab-solucoes.csv';
  link.click();
  URL.revokeObjectURL(url);
});

const dialog = document.querySelector('#instance-dialog');
document.querySelectorAll('.sidebar .nav-item[href^="#"]').forEach((link) => {
  link.addEventListener('click', () => {
    document.querySelectorAll('.sidebar .nav-item[href^="#"]').forEach((item) => {
      const active = item === link;
      item.classList.toggle('active', active);
      if (active) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
  });
});
window.addEventListener('hashchange', updateActiveNavigation);
initializeLocalSettings();
updateActiveNavigation();
document.querySelector('#open-modal').addEventListener('click', openInstanceDialog);
document.querySelector('#open-modal-secondary').addEventListener('click', openInstanceDialog);
document.querySelector('#problem-type').addEventListener('change', (event) => {
  populateAlgorithms(event.target.value);
});
document.querySelector('#instance-form').addEventListener('submit', createInstance);
document.querySelector('#start-run').addEventListener('click', startRun);
document.querySelector('#robustness-analysis').addEventListener('click', runRobustness);
document.querySelector('#cancel-run').addEventListener('click', cancelRun);
if (window.Robustness) Robustness.mount(document.querySelector('#robustness-panel'));
if (window.AHP) {
  AHP.mount(
    document.querySelector('#ahp-decision'),
    (judgments) => {
      if (!state.activeRun?.run_id) throw new Error('Não há uma execução selecionada.');
      return fetchJson(`/runs/${state.activeRun.run_id}/ahp`, {
        method: 'POST',
        body: JSON.stringify({ judgments }),
      });
    },
    ({ criterion, rowOffset, columnOffset }) => {
      if (!state.activeRun?.run_id) throw new Error('Não há uma execução selecionada.');
      return fetchJson(`/runs/${state.activeRun.run_id}/ahp/matrices`, {
        method: 'POST',
        body: JSON.stringify({
          criterion,
          row_offset: rowOffset,
          column_offset: columnOffset,
        }),
      });
    },
  );
}
document.querySelector('#toggle-compare-solution').addEventListener('click', () => {
  if (selectedId) toggleComparison(selectedId);
});
document.querySelector('#compare-solutions').addEventListener('click', openComparison);
document.querySelector('#view-route').addEventListener('click', showSelectedRoute);
document.querySelector('#expand-route').addEventListener('click', openRouteViewer);
document.querySelector('#route-emission-heatmap').addEventListener('click', toggleEmissionHeatmap);
document.querySelector('#download-route').addEventListener('click', downloadSelectedRoute);
document.querySelector('#close-route-dialog').addEventListener('click', () => {
  document.querySelector('#route-dialog').close();
});
document.querySelector('#route-dialog').addEventListener('close', () => {
  endRoutePan();
  const expandButton = document.querySelector('#expand-route');
  if (!expandButton.disabled) expandButton.focus();
});
document.querySelector('#route-zoom-out').addEventListener('click', () => {
  const origin = routeViewerCenter();
  zoomRouteTo(routeView.zoom / 1.25, origin.x, origin.y);
});
document.querySelector('#route-zoom-in').addEventListener('click', () => {
  const origin = routeViewerCenter();
  zoomRouteTo(routeView.zoom * 1.25, origin.x, origin.y);
});
document.querySelector('#route-zoom-reset').addEventListener('click', resetRouteZoom);
document.querySelector('#route-viewer-stage').addEventListener('wheel', (event) => {
  const routeDialog = document.querySelector('#route-dialog');
  if (!routeDialog.open) return;
  event.preventDefault();
  let delta = event.deltaY;
  if (event.deltaMode === 1) delta *= 16;
  else if (event.deltaMode === 2) delta *= document.querySelector('#route-viewer-canvas').getBoundingClientRect().height;
  if (!delta) return;
  const bounds = document.querySelector('#route-viewer-canvas').getBoundingClientRect();
  zoomRouteTo(routeView.zoom * Math.exp(-delta * 0.0018), event.clientX - bounds.left, event.clientY - bounds.top);
}, { passive: false });
document.querySelector('#route-viewer-canvas').addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return;
  const canvas = event.currentTarget;
  canvas.setPointerCapture(event.pointerId);
  routePan = { id: event.pointerId, x: event.clientX, y: event.clientY, panX: routeView.panX, panY: routeView.panY };
  canvas.classList.add('is-panning');
});
document.querySelector('#route-viewer-canvas').addEventListener('pointermove', (event) => {
  if (!routePan || routePan.id !== event.pointerId) return;
  routeView.panX = routePan.panX + (event.clientX - routePan.x);
  routeView.panY = routePan.panY + (event.clientY - routePan.y);
  drawExpandedRoute();
});
document.querySelector('#route-viewer-canvas').addEventListener('pointerup', endRoutePan);
document.querySelector('#route-viewer-canvas').addEventListener('pointercancel', endRoutePan);
document.querySelector('#close-compare-dialog').addEventListener('click', () => {
  document.querySelector('#compare-dialog').close();
});
document.querySelector('#compare-dialog').addEventListener('close', () => {
  endComparePan();
  document.querySelector('#compare-tooltip').hidden = true;
  const compareButton = document.querySelector('#compare-solutions');
  const includeButton = document.querySelector('#toggle-compare-solution');
  if (compareButton && !compareButton.hidden) compareButton.focus();
  else if (includeButton && !includeButton.disabled) includeButton.focus();
});
document.querySelector('#compare-zoom-out').addEventListener('click', () => {
  const origin = compareViewerCenter();
  zoomComparisonTo(compareView.zoom / 1.25, origin.x, origin.y);
});
document.querySelector('#compare-zoom-in').addEventListener('click', () => {
  const origin = compareViewerCenter();
  zoomComparisonTo(compareView.zoom * 1.25, origin.x, origin.y);
});
document.querySelector('#compare-zoom-reset').addEventListener('click', resetCompareZoom);
document.querySelector('#compare-viewer-stage').addEventListener('wheel', (event) => {
  const dialog = document.querySelector('#compare-dialog');
  if (!dialog.open) return;
  event.preventDefault();
  let delta = event.deltaY;
  if (event.deltaMode === 1) delta *= 16;
  else if (event.deltaMode === 2) delta *= document.querySelector('#compare-canvas').getBoundingClientRect().height;
  if (!delta) return;
  const bounds = document.querySelector('#compare-canvas').getBoundingClientRect();
  zoomComparisonTo(compareView.zoom * Math.exp(-delta * 0.0018), event.clientX - bounds.left, event.clientY - bounds.top);
}, { passive: false });
document.querySelector('#compare-canvas').addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return;
  const canvas = event.currentTarget;
  canvas.setPointerCapture(event.pointerId);
  comparePan = { id: event.pointerId, x: event.clientX, y: event.clientY, panX: compareView.panX, panY: compareView.panY };
  canvas.classList.add('is-panning');
  document.querySelector('#compare-tooltip').hidden = true;
});
document.querySelector('#compare-canvas').addEventListener('pointermove', (event) => {
  if (comparePan && comparePan.id === event.pointerId) {
    compareView.panX = comparePan.panX + (event.clientX - comparePan.x);
    compareView.panY = comparePan.panY + (event.clientY - comparePan.y);
    drawComparisonGraph();
    return;
  }
  hoverComparisonEdge(event);
});
document.querySelector('#compare-canvas').addEventListener('pointerup', endComparePan);
document.querySelector('#compare-canvas').addEventListener('pointercancel', endComparePan);
document.querySelector('#compare-canvas').addEventListener('pointerleave', () => {
  document.querySelector('#compare-tooltip').hidden = true;
});
document.querySelector('#notifications-button').addEventListener('click', async () => {
  await loadNotifications();
  document.querySelector('#notifications-dialog').showModal();
});
document.querySelector('#close-notifications').addEventListener('click', () => {
  document.querySelector('#notifications-dialog').close();
});
document.querySelector('#previous-page').addEventListener('click', async () => {
  if (state.tableOffset > 0) {
    state.tableOffset = Math.max(0, state.tableOffset - state.tablePageSize);
    renderTable();
    return;
  }
  if (state.activeRun?.run_id && state.resultOffset > 0) {
    const previousOffset = Math.max(0, state.resultOffset - state.resultLimit);
    await loadRunResults(state.activeRun.run_id, previousOffset);
    state.tableOffset = Math.max(0, state.solutions.length - state.tablePageSize);
    renderTable();
  }
});
document.querySelector('#next-page').addEventListener('click', async () => {
  if (state.tableOffset + state.tablePageSize < visibleSolutions.length) {
    state.tableOffset += state.tablePageSize;
    renderTable();
    return;
  }
  if (state.activeRun?.run_id && state.resultOffset + state.solutions.length < state.resultTotal) {
    await loadRunResults(state.activeRun.run_id, state.resultOffset + state.solutions.length);
  }
});
searchInput.addEventListener('input', () => {
  state.tableOffset = 0;
  renderTable();
});
document.querySelector('#instance-selector').addEventListener('change', async (event) => {
  const instanceId = event.target.value;
  if (!instanceId) return;
  pollingRunId = null;
  clearRobustness();
  try {
    state.selectedInstanceId = instanceId;
    state.instance = await fetchJson(`/instances/${instanceId}`);
    const runsPayload = await fetchJson(`/instances/${instanceId}/runs?limit=1`);
    state.activeRun = runsPayload.runs?.[0] || null;
    state.resultOffset = 0;
    state.tableOffset = 0;
    applyInstanceSummary(state.instance);
    await loadInputAnalysis('time');
    state.resultIsDemo = false;
    state.qualityEvolution = null;
    state.qualityEvolutionError = 'Carregando a evolução dos indicadores.';
    renderQualityEvolution();
    if (state.activeRun?.status === 'completed') {
      await loadRunResults(state.activeRun.run_id, 0);
    } else {
      state.solutions = [];
      state.frontiers = [];
      clearReferencePoints();
      state.resultIsDemo = false;
      state.resultTotal = 0;
      renderSolutionTiming(null);
      await loadQualityEvolution(state.selectedInstanceId);
      renderTable();
      applyInstanceSummary(state.instance);
      if (['queued', 'running', 'cancel_requested'].includes(state.activeRun?.status)) pollRun(state.activeRun.run_id);
    }
  } catch (error) {
    setApiStatus(`Não foi possível abrir a instância: ${error.message}`, true);
  }
});
document.querySelectorAll('[data-objective]').forEach((button) => {
  button.addEventListener('click', () => loadInputAnalysis(button.dataset.objective));
});
document.querySelector('#neighbors-per-city').addEventListener('change', (event) => {
  const requested = Number(event.target.value);
  if (!Number.isInteger(requested) || requested < 1) {
    event.target.setCustomValidity('Informe um inteiro maior que zero.');
    event.target.reportValidity();
    return;
  }
  event.target.setCustomValidity('');
  const activeObjective = document.querySelector('[data-objective].active')?.dataset.objective || 'time';
  loadInputAnalysis(activeObjective, requested);
});

const resizeObserver = new ResizeObserver(drawChart);
resizeObserver.observe(chart);
bindQualityChart('hv-evolution');
bindQualityChart('spread-evolution');
const qualityEvolutionSection = document.querySelector('#quality-evolution');
if (qualityEvolutionSection) {
  const qualityResizeObserver = new ResizeObserver(() => {
    if (!qualityEvolutionSection.hidden) renderQualityEvolution();
  });
  qualityResizeObserver.observe(qualityEvolutionSection);
}
const routeResizeObserver = new ResizeObserver(() => {
  if (document.querySelector('#route-dialog').open) drawExpandedRoute();
});
routeResizeObserver.observe(document.querySelector('#route-viewer-stage'));
const compareResizeObserver = new ResizeObserver(() => {
  if (document.querySelector('#compare-dialog').open) drawComparisonGraph();
});
compareResizeObserver.observe(document.querySelector('#compare-viewer-stage'));
initializeDashboard();