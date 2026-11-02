const timeMatrix = [
  [0, 18, 24, 35, 29, 22],
  [18, 0, 12, 31, 26, 19],
  [24, 12, 0, 27, 16, 23],
  [35, 31, 27, 0, 20, 22],
  [29, 26, 16, 20, 0, 27],
  [22, 19, 23, 22, 27, 0],
];
const distanceMatrix = [
  [0, 9, 14, 22, 18, 12],
  [9, 0, 6, 19, 15, 11],
  [14, 6, 0, 16, 8, 13],
  [22, 19, 16, 0, 12, 14],
  [18, 15, 8, 12, 0, 17],
  [12, 11, 13, 14, 17, 0],
];
const nodeLabels = ['A', 'B', 'C', 'D', 'E', 'F'];
const cityCoordinates = Object.freeze({
  A: Object.freeze({ x: 92, y: 124 }),
  B: Object.freeze({ x: 201, y: 49 }),
  C: Object.freeze({ x: 205, y: 201 }),
  D: Object.freeze({ x: 340, y: 78 }),
  E: Object.freeze({ x: 340, y: 174 }),
  F: Object.freeze({ x: 450, y: 126 }),
});
const solutions = [
  { id: '01', time: 42, distance: 31, route: ['A', 'B', 'D', 'F', 'E', 'C', 'A'] },
  { id: '02', time: 50, distance: 38, route: ['A', 'C', 'E', 'D', 'F', 'B', 'A'] },
  { id: '03', time: 58, distance: 45, route: ['A', 'B', 'C', 'E', 'F', 'D', 'A'] },
  { id: '04', time: 67, distance: 52, route: ['A', 'D', 'B', 'F', 'E', 'C', 'A'] },
  { id: '05', time: 76, distance: 59, route: ['A', 'C', 'B', 'D', 'E', 'F', 'A'] },
];
const svgNamespace = 'http://www.w3.org/2000/svg';

const dialog = document.querySelector('#instance-wizard');
const form = document.querySelector('#wizard-form');
const solutionDialog = document.querySelector('#solution-dialog');
const startButton = document.querySelector('#start-optimization');
const cancelButton = document.querySelector('#cancel-optimization');
const resultsButton = document.querySelector('#view-results');
const resultsPanel = document.querySelector('#results-panel');
const notificationButton = document.querySelector('#notifications-button');
const notificationPanel = document.querySelector('#notification-panel');
let currentStep = 1;
let matrixKind = 'time';
let runTimer = null;
let toastTimer = null;
let runState = 'ready';
let instanceName = 'TSP — Belo Horizonte';
let instanceLayoutCoordinates = { ...cityCoordinates };
let graphNeighborLimit = 20;

function svgElement(tag, attributes = {}, text = '') {
  const element = document.createElementNS(svgNamespace, tag);
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, String(value)));
  if (text) element.textContent = text;
  return element;
}

function renderGraph(svg, edges, { showWeights = false, directed = false } = {}) {
  svg.replaceChildren();
  const title = svgElement('title', {}, directed
    ? 'Grafo contendo somente os arcos da solução selecionada'
    : 'Grafo ilustrativo das conexões da matriz de tempo');
  svg.append(title);
  const edgeLayer = svgElement('g', { class: directed ? 'solution-edges' : 'network-edges' });
  const labelLayer = svgElement('g', { class: 'edge-labels' });
  const nodeLayer = svgElement('g', { class: directed ? 'solution-nodes' : 'network-nodes' });
  const nodeLabelLayer = svgElement('g', { class: 'node-labels' });

  if (directed || showWeights) {
    const defs = svgElement('defs');
    const markerId = directed ? 'route-arrow' : 'input-arrow';
    const marker = svgElement('marker', {
      id: markerId,
      viewBox: '0 0 10 10',
      refX: 8,
      refY: 5,
      markerWidth: 5,
      markerHeight: 5,
      orient: 'auto-start-reverse',
    });
    marker.append(svgElement('path', {
      d: 'M 0 0 L 10 5 L 0 10 z',
      class: directed ? 'route-arrowhead' : 'input-arrowhead',
    }));
    defs.append(marker);
    svg.append(defs);
  }

  edges.forEach(({ from, to, weight }, index) => {
    const start = instanceLayoutCoordinates[from];
    const end = instanceLayoutCoordinates[to];
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy);
    const inset = directed ? 21 : 0;
    const lineStart = {
      x: start.x + (dx / length) * inset,
      y: start.y + (dy / length) * inset,
    };
    const lineEnd = {
      x: end.x - (dx / length) * inset,
      y: end.y - (dy / length) * inset,
    };
    const edgeAttributes = directed
      ? { 'marker-end': 'url(#route-arrow)', 'aria-label': `${from} para ${to}` }
      : showWeights
        ? {
          ...(edges[index].forward ? { 'marker-end': 'url(#input-arrow)' } : {}),
          ...(edges[index].reverse ? { 'marker-start': 'url(#input-arrow)' } : {}),
          'aria-label': `${from} para ${to}`,
        }
        : {};
    edgeLayer.append(svgElement('path', {
      d: `M${lineStart.x} ${lineStart.y} L${lineEnd.x} ${lineEnd.y}`,
      ...edgeAttributes,
    }));

    if (showWeights) {
      const offset = index % 2 === 0 ? -5 : 8;
      const label = edges[index].forward && edges[index].reverse && edges[index].forwardWeight !== edges[index].reverseWeight
        ? `${edges[index].forwardWeight}/${edges[index].reverseWeight}`
        : String(weight);
      labelLayer.append(svgElement('text', {
        x: (start.x + end.x) / 2,
        y: (start.y + end.y) / 2 + offset,
      }, label));
    }
  });

  nodeLabels.forEach((city) => {
    const { x, y } = instanceLayoutCoordinates[city];
    nodeLayer.append(svgElement('circle', { cx: x, cy: y, r: 18 }));
    nodeLabelLayer.append(svgElement('text', { x, y: y + 4 }, city));
  });

  svg.append(edgeLayer);
  if (showWeights) svg.append(labelLayer);
  svg.append(nodeLayer, nodeLabelLayer);
}

function getNearestNeighborEdges(matrix, count) {
  const selectedEdges = new Map();
  const neighborCount = Math.min(count, Math.max(0, matrix.length - 1));

  matrix.forEach((row, sourceIndex) => {
    const nearest = row
      .map((weight, targetIndex) => ({ targetIndex, weight }))
      .filter(({ targetIndex, weight }) => targetIndex !== sourceIndex && Number.isFinite(weight))
      .sort((left, right) => left.weight - right.weight || left.targetIndex - right.targetIndex)
      .slice(0, neighborCount);

    nearest.forEach(({ targetIndex, weight }) => {
      const fromIndex = Math.min(sourceIndex, targetIndex);
      const toIndex = Math.max(sourceIndex, targetIndex);
      const key = `${fromIndex}-${toIndex}`;
      const edge = selectedEdges.get(key) ?? {
        from: nodeLabels[fromIndex],
        to: nodeLabels[toIndex],
        forward: false,
        reverse: false,
      };
      if (sourceIndex === fromIndex) {
        edge.forward = true;
        edge.forwardWeight = weight;
      } else {
        edge.reverse = true;
        edge.reverseWeight = weight;
      }
      edge.weight = edge.forwardWeight ?? edge.reverseWeight;
      selectedEdges.set(key, edge);
    });
  });

  return [...selectedEdges.values()];
}

function renderInputGraph() {
  const edgeCountInput = document.querySelector('#neighbor-limit');
  const edgeCountStatus = document.querySelector('#neighbor-limit-status');
  const availableNeighbors = Math.max(0, timeMatrix.length - 1);
  const displayedNeighbors = Math.min(graphNeighborLimit, availableNeighbors);
  edgeCountStatus.textContent = `Exibindo até ${displayedNeighbors} de ${graphNeighborLimit} solicitados por cidade; ${availableNeighbors} vizinhos disponíveis nesta matriz.`;
  document.querySelector('#input-graph').setAttribute(
    'aria-label',
    `Grafo ilustrativo de arcos dos até ${displayedNeighbors} vizinhos mais próximos por cidade, ordenados por tempo`,
  );
  renderGraph(
    document.querySelector('#input-graph'),
    getNearestNeighborEdges(timeMatrix, graphNeighborLimit),
    { showWeights: true },
  );
}

function renderSolutionsTable() {
  const body = document.querySelector('#solutions-body');
  body.replaceChildren(...solutions.map((solution) => {
    const row = document.createElement('tr');
    const cells = [
      `Sol. ${solution.id}`,
      String(solution.time),
      String(solution.distance),
    ];
    cells.forEach((value) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.append(cell);
    });
    const statusCell = document.createElement('td');
    const status = document.createElement('span');
    status.className = 'status-pill';
    status.textContent = 'Não dominada';
    statusCell.append(status);
    row.append(statusCell);

    const actions = document.createElement('td');
    actions.className = 'solution-actions';
    [
      { action: 'view', label: 'Ver solução' },
      { action: 'download', label: 'Baixar resultado' },
    ].forEach(({ action, label }) => {
      const button = document.createElement('button');
      button.className = 'table-action';
      button.type = 'button';
      button.dataset.action = action;
      button.dataset.solutionId = solution.id;
      button.textContent = label;
      button.setAttribute('aria-label', `${label}: solução ${solution.id}`);
      actions.append(button);
    });
    row.append(actions);
    return row;
  }));
}

function showSolution(solution) {
  document.querySelector('#solution-dialog-title').textContent = `Solução ${solution.id}`;
  document.querySelector('#solution-route-description').textContent =
    `Rota: ${solution.route.join(' → ')} · ciclo com retorno à origem.`;
  document.querySelector('#solution-objectives').textContent =
    `Tempo ${solution.time} min · Distância ${solution.distance} km`;
  const routeEdges = solution.route.slice(0, -1).map((from, index) => ({
    from,
    to: solution.route[index + 1],
  }));
  renderGraph(document.querySelector('#solution-graph'), routeEdges, { directed: true });
  solutionDialog.showModal();
}

function downloadSolution(solution) {
  const rows = [
    ['ordem', 'cidade'],
    ...solution.route.map((city, index) => [String(index + 1), city]),
  ];
  const csv = rows.map((row) => row.map((field) => `"${field.replaceAll('"', '""')}"`).join(',')).join('\r\n');
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `solucao-${solution.id}.csv`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderHeatmap(kind) {
  matrixKind = kind;
  const matrix = kind === 'time' ? timeMatrix : distanceMatrix;
  const unit = kind === 'time' ? 'min' : 'km';
  const values = matrix.flat().filter((value) => value > 0);
  const maximum = Math.max(...values);
  const heatmap = document.querySelector('#heatmap');
  heatmap.replaceChildren();

  const corner = document.createElement('span');
  corner.className = 'heatmap-cell header';
  corner.setAttribute('aria-hidden', 'true');
  heatmap.append(corner);

  nodeLabels.forEach((label) => {
    const header = document.createElement('span');
    header.className = 'heatmap-cell header';
    header.textContent = label;
    header.setAttribute('aria-hidden', 'true');
    heatmap.append(header);
  });

  matrix.forEach((row, rowIndex) => {
    const rowHeader = document.createElement('span');
    rowHeader.className = 'heatmap-cell header';
    rowHeader.textContent = nodeLabels[rowIndex];
    rowHeader.setAttribute('aria-hidden', 'true');
    heatmap.append(rowHeader);

    row.forEach((value, columnIndex) => {
      const cell = document.createElement('span');
      cell.className = `heatmap-cell${rowIndex === columnIndex ? ' diagonal' : ''}`;
      cell.textContent = String(value);
      cell.title = `${nodeLabels[rowIndex]} → ${nodeLabels[columnIndex]}: ${value} ${unit}`;
      cell.setAttribute('aria-label', `${nodeLabels[rowIndex]} para ${nodeLabels[columnIndex]}: ${value} ${unit}`);
      if (rowIndex !== columnIndex) {
        const intensity = 0.1 + (value / maximum) * 0.78;
        cell.style.backgroundColor = `rgba(40, 98, 77, ${intensity})`;
        if (intensity > 0.56) cell.style.color = '#fffefa';
      }
      heatmap.append(cell);
    });
  });

  document.querySelector('#matrix-view').setAttribute('aria-labelledby', `${kind}-tab`);
  document.querySelector('#matrix-view').setAttribute('aria-label', `Heatmap ilustrativo da matriz de ${kind === 'time' ? 'tempo' : 'distância'}`);
  document.querySelectorAll('.matrix-tab').forEach((tab) => {
    const selected = tab.dataset.matrix === kind;
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-selected', String(selected));
  });
}

function setRunState(state, message = '') {
  runState = state;
  const labels = {
    ready: ['Pronta para otimização', 'Não iniciada'],
    running: ['Em execução · demonstração', 'Em execução'],
    canceled: ['Cancelada · demonstração', 'Cancelada'],
    completed: ['Concluída · demonstração', 'Concluída'],
  };
  const [label, metricLabel] = labels[state];
  document.querySelector('#run-status').textContent = label;
  document.querySelector('#metric-status').textContent = metricLabel;
  document.querySelector('#run-badge').classList.toggle('is-running', state === 'running');
  document.querySelector('#run-badge').classList.toggle('is-canceled', state === 'canceled');
  const dot = document.querySelector('#run-badge .status-dot');
  dot.classList.toggle('running', state === 'running');
  dot.classList.toggle('failed', false);
  startButton.hidden = state === 'running';
  cancelButton.hidden = state !== 'running';
  resultsButton.disabled = state !== 'completed';

  const messageBox = document.querySelector('#execution-message');
  messageBox.hidden = !message;
  messageBox.classList.toggle('success', state === 'completed');
  messageBox.classList.toggle('canceled', state === 'canceled');
  messageBox.textContent = message;
  document.querySelector('#overview-status').textContent = label;
}

function showToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.hidden = true; }, 3200);
}

function showStep(step) {
  currentStep = step;
  document.querySelector('#step-one').hidden = step !== 1;
  document.querySelector('#step-two').hidden = step !== 2;
  document.querySelector('#step-label').textContent = `· ETAPA ${step} DE 2`;
  document.querySelector('#wizard-title').textContent = step === 1 ? 'Dados do problema' : 'Análises e algoritmo';
  document.querySelector('#back-step').hidden = step === 1;
  document.querySelector('#next-step').hidden = step !== 1;
  document.querySelector('#create-instance').hidden = step !== 2;
  document.querySelectorAll('.step-dot').forEach((dot, index) => dot.classList.toggle('current', index < step));
  document.querySelector('#step-one-error').hidden = true;
  document.querySelector('#step-two-error').hidden = true;
}

function openWizard() {
  form.reset();
  document.querySelector('#instance-title').value = 'TSP — Belo Horizonte (teste)';
  document.querySelector('#sample-files').checked = true;
  document.querySelector('#time-file-name').textContent = 'Matriz de tempo · exemplo';
  document.querySelector('#distance-file-name').textContent = 'Matriz de distância · exemplo';
  showStep(1);
  dialog.showModal();
}

function setPage(page) {
  const views = {
    instances: document.querySelector('#dashboard-view'),
    overview: document.querySelector('#overview-view'),
    models: document.querySelector('#models-view'),
  };
  Object.entries(views).forEach(([name, view]) => { view.hidden = name !== page; });
  document.querySelectorAll('.nav-item').forEach((button) => {
    const active = button.dataset.page === page;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  document.querySelector('#breadcrumb-current').textContent = page === 'instances' ? 'Instâncias' : page === 'overview' ? 'Visão geral' : 'Modelos';
}

function updateInstance(name, previewOptions, resultOptions, files, algorithm) {
  window.clearTimeout(runTimer);
  runTimer = null;
  instanceLayoutCoordinates = Object.fromEntries(
    Object.entries(cityCoordinates).map(([city, coordinates]) => [city, { ...coordinates }]),
    );
    renderInputGraph();
  instanceName = name;
  document.querySelector('#instance-name').textContent = '';
  const title = document.createElement('span');
  title.textContent = name;
  const id = document.createElement('span');
  id.className = 'instance-id';
  id.textContent = '/ nova instância';
  document.querySelector('#instance-name').append(title, ' ', id);
  document.querySelector('#overview-instance').textContent = name;
  document.querySelector('#run-time').textContent = 'Criada agora';
  document.querySelector('#problem-label').textContent = 'TSP · TEMPO VS. DISTÂNCIA · DADOS ILUSTRATIVOS';
  document.querySelector('#graph-analysis').hidden = !previewOptions.includes('graph');
  document.querySelector('#matrix-analysis').hidden = !previewOptions.includes('heatmap');
  document.querySelector('.analysis-grid').classList.toggle('single-view', previewOptions.length === 1);
  const previewMetric = document.querySelector('.metric-strip .metric:nth-child(3) .metric-value');
  const previewNote = document.createElement('span');
  previewNote.className = 'metric-note';
  previewNote.textContent = previewOptions.length === 1 ? 'visualização' : 'visualizações';
  previewMetric.replaceChildren(String(previewOptions.length), ' ', previewNote);
  document.querySelector('#pareto-analysis').hidden = !resultOptions.includes('pareto');
  document.querySelector('#solutions-table').hidden = !resultOptions.includes('table');
  document.querySelector('#instance-files').textContent = files.join(' · ');
  document.querySelector('#instance-algorithm').textContent = `${algorithm} · exemplo`;
  document.querySelector('#notification-count').hidden = true;
  document.querySelector('#notifications-button').setAttribute('aria-label', 'Notificações, nenhuma não lida');
  document.querySelector('#notification-empty').hidden = false;
  document.querySelector('#notification-item').hidden = true;
  resultsPanel.hidden = true;
  setRunState('ready');
}

document.querySelector('#open-wizard').addEventListener('click', openWizard);
document.querySelector('#close-wizard').addEventListener('click', () => dialog.close());
document.querySelector('#cancel-wizard').addEventListener('click', () => dialog.close());
document.querySelector('#close-solution').addEventListener('click', () => solutionDialog.close());
document.querySelector('#neighbor-limit').addEventListener('change', (event) => {
  const input = event.currentTarget;
  const value = Number(input.value);
  if (!Number.isSafeInteger(value) || value < 1) {
    input.value = String(graphNeighborLimit);
    return;
  }
  graphNeighborLimit = value;
  renderInputGraph();
});
document.querySelector('#solutions-body').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action][data-solution-id]');
  if (!button) return;
  const solution = solutions.find((item) => item.id === button.dataset.solutionId);
  if (!solution) return;
  if (button.dataset.action === 'view') showSolution(solution);
  if (button.dataset.action === 'download') downloadSolution(solution);
});
document.querySelector('#next-step').addEventListener('click', () => {
  const name = document.querySelector('#instance-title');
  const sampleFiles = document.querySelector('#sample-files').checked;
  const timeFile = document.querySelector('#time-file').files[0];
  const distanceFile = document.querySelector('#distance-file').files[0];
  const error = document.querySelector('#step-one-error');
  if (!name.value.trim()) {
    error.textContent = 'Informe um nome para a instância.';
    error.hidden = false;
    name.focus();
    return;
  }
  if (!sampleFiles && (!timeFile || !distanceFile)) {
    error.textContent = 'Selecione os dois arquivos CSV ou use os arquivos de exemplo do protótipo.';
    error.hidden = false;
    return;
  }
  showStep(2);
  document.querySelector('#step-two').querySelector('input[type="checkbox"]').focus();
});

document.querySelector('#back-step').addEventListener('click', () => showStep(1));
form.addEventListener('submit', (event) => {
  event.preventDefault();
  const previews = [...form.querySelectorAll('input[name="preview"]:checked')].map((input) => input.value);
  const analyses = [...form.querySelectorAll('input[name="results"]:checked')].map((input) => input.value);
  const error = document.querySelector('#step-two-error');
  if (!previews.length || !analyses.length || !form.querySelector('input[name="algorithm"]:checked')) {
    error.textContent = 'Selecione ao menos uma visualização em cada etapa e um algoritmo.';
    error.hidden = false;
    return;
  }
  const name = document.querySelector('#instance-title').value.trim();
  const fileNames = document.querySelector('#sample-files').checked
    ? ['tempo.csv (exemplo)', 'distancia.csv (exemplo)']
    : [document.querySelector('#time-file').files[0].name, document.querySelector('#distance-file').files[0].name];
  const algorithm = form.querySelector('input[name="algorithm"]:checked').value === 'epsilon' ? 'ε-restrição' : '';
  updateInstance(name, previews, analyses, fileNames, algorithm);
  dialog.close();
  setPage('instances');
  showToast('Instância criada no protótipo. Nenhum dado foi enviado.');
});

['time', 'distance'].forEach((kind) => {
  document.querySelector(`#${kind}-tab`).addEventListener('click', () => renderHeatmap(kind));
});

['time', 'distance'].forEach((kind) => {
  document.querySelector(`#${kind}-file`).addEventListener('change', (event) => {
    const file = event.target.files[0];
    document.querySelector(`#${kind}-file-name`).textContent = file
      ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB`
      : 'Nenhum arquivo selecionado · .csv';
    document.querySelector('#sample-files').checked = false;
  });
});
document.querySelector('#sample-files').addEventListener('change', (event) => {
  if (event.target.checked) {
    document.querySelector('#time-file').value = '';
    document.querySelector('#distance-file').value = '';
    document.querySelector('#time-file-name').textContent = 'Matriz de tempo · exemplo';
    document.querySelector('#distance-file-name').textContent = 'Matriz de distância · exemplo';
  } else {
    document.querySelector('#time-file-name').textContent = 'Nenhum arquivo selecionado · .csv';
    document.querySelector('#distance-file-name').textContent = 'Nenhum arquivo selecionado · .csv';
  }
});

startButton.addEventListener('click', () => {
  if (runState === 'running') return;
  resultsPanel.hidden = true;
  setRunState('running', 'Execução demonstrativa em andamento. Você pode navegar para outra seção; esta simulação é local e não chama um solver.');
  document.querySelector('#run-time').textContent = 'Executando agora';
  showToast('Otimização demonstrativa iniciada.');
  window.clearTimeout(runTimer);
  runTimer = window.setTimeout(() => {
    setRunState('completed', 'Execução demonstrativa concluída. A análise abaixo contém resultados fictícios.');
    document.querySelector('#run-time').textContent = 'Concluída agora';
    resultsButton.disabled = false;
    document.querySelector('#notification-count').hidden = false;
    document.querySelector('#notifications-button').setAttribute('aria-label', 'Notificações, 1 não lida');
    document.querySelector('#notification-empty').hidden = true;
    document.querySelector('#notification-item').hidden = false;
    document.querySelector('#notification-copy').textContent = `A execução de “${instanceName}” foi concluída.`;
    showToast('Otimização concluída. Há uma nova notificação.');
  }, 5000);
});

cancelButton.addEventListener('click', () => {
  if (runState !== 'running') return;
  window.clearTimeout(runTimer);
  setRunState('canceled', 'A simulação foi cancelada. Nenhum solver real foi iniciado.');
  document.querySelector('#run-time').textContent = 'Cancelada agora';
  showToast('Simulação da otimização cancelada.');
});

resultsButton.addEventListener('click', () => {
  if (runState !== 'completed') return;
  resultsPanel.hidden = false;
  resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

notificationButton.addEventListener('click', () => {
  const opening = notificationPanel.hidden;
  notificationPanel.hidden = !opening;
  notificationButton.setAttribute('aria-expanded', String(opening));
});
document.querySelector('#notification-item').addEventListener('click', () => {
  notificationPanel.hidden = true;
  notificationButton.setAttribute('aria-expanded', 'false');
  document.querySelector('#notification-count').hidden = true;
  document.querySelector('#notifications-button').setAttribute('aria-label', 'Notificações, nenhuma não lida');
  setPage('instances');
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', () => {
  setPage(button.dataset.page);
}));
document.querySelector('#return-to-instance').addEventListener('click', () => setPage('instances'));
document.addEventListener('click', (event) => {
  if (!event.target.closest('.notification-wrap') && !notificationPanel.hidden) {
    notificationPanel.hidden = true;
    notificationButton.setAttribute('aria-expanded', 'false');
  }
});

renderHeatmap(matrixKind);
renderInputGraph();
renderSolutionsTable();
setRunState('ready');
