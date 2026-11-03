const API_BASE_URL = window.PARETOLAB_API_BASE_URL || '/api/v1';
const fallbackProblemTypes = [
  { id: 'tsp-time-distance', name: 'TSP biobjetivo: tempo e distância' },
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
  { id: '003', cost: 9.8, coverage: 59.2, items: 6, frontier: true },
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
  { id: '033', cost: 33.2, coverage: 97.4, items: 20, frontier: true },
];

const state = {
  solutions: [...mockSolutions],
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

  select.replaceChildren(...problemTypes.map((problemType) => {
    const option = document.createElement('option');
    option.value = problemType.id;
    option.textContent = problemType.name;
    return option;
  }));
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
        state.solutions = [];
        renderTable();
      }
      return true;
    }
    state.instance = null;
    state.activeRun = null;
    state.selectedInstanceId = null;
    state.resultIsDemo = false;
    state.solutions = [];
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
    state.solutions = [...mockSolutions];
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

async function loadRunResults(runId, offset) {
  const payload = await fetchJson(`/runs/${runId}/results?limit=${state.resultLimit}&offset=${offset}`);
  state.resultOffset = offset;
  state.tableOffset = 0;
  state.resultTotal = payload.total || 0;
  state.resultIsDemo = false;
  state.solutions = (payload.solutions || []).map((solution) => ({
    id: solution.solution_id,
    solutionId: solution.solution_id,
    cost: Number(solution.objective_values.distance),
    coverage: Number(solution.objective_values.time),
    frontier: solution.dominance === 'non_dominated',
    route: solution.route,
  }));
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
  if (state.solutions.length) selectSolution(selectedId);
  else renderTable();
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
          setApiStatus('Execução concluída. Resultados disponíveis.');
        } else {
          state.solutions = [];
          state.resultIsDemo = false;
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
    state.resultIsDemo = false;
    state.resultTotal = 0;
    document.querySelector('#metric-solutions').replaceChildren(document.createTextNode('--'));
    document.querySelector('#metric-frontier').replaceChildren(document.createTextNode('--'));
    renderTable();
    applyInstanceSummary(state.instance);
    setApiStatus('Otimização enfileirada. O progresso será atualizado automaticamente.');
    pollRun(response.run_id);
  } catch (error) {
    button.disabled = false;
    setApiStatus(`Não foi possível iniciar a otimização: ${error.message}`, true);
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
  const timeFile = document.querySelector('#time-file-input').files[0];
  const distanceFile = document.querySelector('#distance-file-input').files[0];
  errorMessage.hidden = true;

  try {
    validateMatrixFile(timeFile, 'de tempo');
    validateMatrixFile(distanceFile, 'de distância');
    if (!name) throw new Error('Informe um nome para a instância.');
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
          algorithm_id: 'random-heuristic',
          preview: ['weighted_graph', 'matrix_heatmap'],
          result_views: ['pareto_frontier', 'solutions_table', 'route_graph', 'route_csv'],
        },
      }),
    });
    state.instance = instance;
    state.selectedInstanceId = instance.instance_id;
    state.instances = [instance, ...state.instances.filter((item) => item.instance_id !== instance.instance_id)];
    populateInstances();
    state.activeRun = null;
    state.solutions = [];
    state.resultIsDemo = false;
    state.resultOffset = 0;
    applyInstanceSummary(instance);
    await loadInputAnalysis('time');
    renderTable();
    dialog.close();
    document.querySelector('#instance-form').reset();
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
  try {
    const graph = await fetchJson(`/runs/${state.activeRun.run_id}/solutions/${solution.solutionId}/graph`);
    drawRouteGraph(graph);
    setApiStatus(`Rota da solução ${solution.id}: ${graph.route.join(' → ')}`);
  } catch (error) {
    setApiStatus(`Não foi possível carregar a rota: ${error.message}`, true);
  }
}

function drawRouteGraph(graph, routeCanvas = document.querySelector('#route-chart')) {
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
  const inset = 18;
  const xValues = nodes.map((node) => node.x);
  const yValues = nodes.map((node) => node.y);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  const pointFor = (nodeId) => {
    const node = nodes.find((item) => item.id === nodeId);
    if (!node) return null;
    return {
      x: inset + ((node.x - minX) / Math.max(1, maxX - minX)) * (bounds.width - inset * 2),
      y: inset + ((node.y - minY) / Math.max(1, maxY - minY)) * (bounds.height - inset * 2),
    };
  };

  (graph.edges || []).forEach((edge) => {
    const source = pointFor(edge.source);
    const target = pointFor(edge.target);
    if (!source || !target) return;
    context.beginPath();
    context.moveTo(source.x, source.y);
    context.lineTo(target.x, target.y);
    context.strokeStyle = '#6d9779';
    context.lineWidth = 1.4;
    context.stroke();
  });
  nodes.forEach((node) => {
    const point = pointFor(node.id);
    if (!point) return;
    context.beginPath();
    context.arc(point.x, point.y, 3.2, 0, Math.PI * 2);
    context.fillStyle = node.id === graph.route?.[0] ? '#d96545' : '#28624d';
    context.fill();
    if (nodes.length <= 40 || node.id === graph.route?.[0] || node.id % 25 === 0) {
      context.fillStyle = '#182b25';
      context.font = '8px "IBM Plex Mono", monospace';
      context.fillText(String(node.id), point.x + 5, point.y - 4);
    }
  });
  routeCanvas.setAttribute('aria-label', graph.route?.length
    ? `Rota pelas cidades ${graph.route.join(', ')}`
    : 'Grafo de entrada da instância com layout persistido');
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

function renderTable() {
  const query = searchInput.value.trim().toLowerCase();
  visibleSolutions = state.solutions.filter((solution) => {
    const matchesSearch = `${solution.id} ${solution.cost} ${solution.coverage}`.toLowerCase().includes(query);
    return matchesSearch && (activeView === 'all' || solution.frontier);
  });

  if (state.tableOffset >= visibleSolutions.length && state.tableOffset > 0) {
    state.tableOffset = Math.max(0, Math.floor((visibleSolutions.length - 1) / state.tablePageSize) * state.tablePageSize);
  }
  const pageSolutions = visibleSolutions.slice(state.tableOffset, state.tableOffset + state.tablePageSize);
  tableBody.innerHTML = pageSolutions.map((solution) => `
    <tr class="${solution.id === selectedId ? 'selected-row' : ''}" data-solution="${solution.id}" tabindex="0" aria-selected="${solution.id === selectedId}">
      <td><span class="table-id">SOL-${solution.id}</span></td>
      <td><span class="table-number">${solution.cost.toFixed(2)} km</span></td>
      <td><span class="table-number">${solution.coverage.toFixed(2)} h</span></td>
      <td><span class="status-pill ${solution.frontier ? 'frontier' : 'dominated'}">${solution.frontier ? 'Não dominada' : 'Dominada'}</span></td>
      <td class="row-arrow" aria-hidden="true">↗</td>
    </tr>`).join('');

  const shown = pageSolutions.length;
  const tableSummary = document.querySelector('#table-summary');
  if (!state.solutions.length) {
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
  document.querySelector('#export-csv').disabled = !state.resultIsDemo && !state.solutions.length;
  drawChart();
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
  const costs = state.solutions.map((solution) => solution.cost);
  const coverages = state.solutions.map((solution) => solution.coverage);
  const minCost = costs.length ? Math.min(...costs) : 0;
  const maxCost = costs.length ? Math.max(...costs) : 1;
  const minCoverage = coverages.length ? Math.min(...coverages) : 0;
  const maxCoverage = coverages.length ? Math.max(...coverages) : 1;
  const costRange = Math.max(maxCost - minCost, 1);
  const coverageRange = Math.max(maxCoverage - minCoverage, 1);
  const costPadding = costRange * 0.1;
  const coveragePadding = coverageRange * 0.1;
  const normalizedX = (cost) => inset.left + ((cost - (minCost - costPadding)) / (costRange + costPadding * 2)) * plotWidth;
  const normalizedY = (coverage) => inset.top + (((maxCoverage + coveragePadding) - coverage) / (coverageRange + coveragePadding * 2)) * plotHeight;

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
    chartContext.fillText(value.toFixed(1), inset.left - 8, position);
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
    chartContext.fillText(value.toFixed(1), position, height - 11);
  }

  const frontier = state.solutions.filter((solution) => solution.frontier).sort((a, b) => a.cost - b.cost);
  chartContext.beginPath();
  frontier.forEach((solution, index) => {
    if (index === 0) chartContext.moveTo(normalizedX(solution.cost), normalizedY(solution.coverage));
    else chartContext.lineTo(normalizedX(solution.cost), normalizedY(solution.coverage));
  });
  chartContext.strokeStyle = '#6d9779';
  chartContext.lineWidth = 1.5;
  chartContext.setLineDash([4, 4]);
  chartContext.stroke();
  chartContext.setLineDash([]);

  plottedPoints = [];
  const pointsToDraw = activeView === 'all' ? state.solutions : frontier;
  pointsToDraw.forEach((solution) => {
    const px = normalizedX(solution.cost);
    const py = normalizedY(solution.coverage);
    const isSelected = solution.id === selectedId;
    const isFrontier = solution.frontier;
    plottedPoints.push({ solution, x: px, y: py });

    chartContext.beginPath();
    chartContext.arc(px, py, isSelected ? 6 : isFrontier ? 4.5 : 3.5, 0, Math.PI * 2);
    chartContext.fillStyle = isSelected ? '#d96545' : isFrontier ? '#28624d' : '#fffefa';
    chartContext.fill();
    chartContext.strokeStyle = isSelected ? '#fffefa' : isFrontier ? '#fffefa' : '#a9b5aa';
    chartContext.lineWidth = isSelected ? 2 : 1.2;
    chartContext.stroke();
    if (isSelected) {
      chartContext.beginPath();
      chartContext.arc(px, py, 10, 0, Math.PI * 2);
      chartContext.strokeStyle = 'rgb(217 101 69 / 27%)';
      chartContext.lineWidth = 4;
      chartContext.stroke();
    }
  });
}

function selectSolution(id) {
  const solution = state.solutions.find((item) => item.id === id);
  if (!solution) return;
  selectedId = id;
  state.selectedSolutionId = id;
  document.querySelector('#selected-title').textContent = `Solução ${solution.id}`;
  document.querySelector('#selected-cost').textContent = `${solution.cost.toFixed(2)} km`;
  document.querySelector('#selected-coverage').textContent = `${solution.coverage.toFixed(2)} h`;
  document.querySelector('#selected-items').textContent = solution.route?.length
    ? `${solution.route.length - 1} arcos`
    : `${solution.items} de 20`;
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
  if (row) selectSolution(row.dataset.solution);
});

tableBody.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const row = event.target.closest('tr[data-solution]');
  if (!row) return;
  event.preventDefault();
  selectSolution(row.dataset.solution);
});

document.querySelectorAll('.segment').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));

chart.addEventListener('pointermove', (event) => {
  const rect = chart.getBoundingClientRect();
  const pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  const nearest = plottedPoints.reduce((best, point) => {
    const distance = Math.hypot(point.x - pointer.x, point.y - pointer.y);
    return distance < best.distance ? { point, distance } : best;
  }, { point: null, distance: 18 });

  if (!nearest.point) {
    tooltip.hidden = true;
    return;
  }

  const { solution } = nearest.point;
  tooltip.innerHTML = `<strong>SOL-${solution.id}</strong><span>Distância: ${solution.cost.toFixed(2)} km</span><span>Tempo: ${solution.coverage.toFixed(2)} h</span>`;
  tooltip.hidden = false;
  tooltip.style.left = `${Math.min(pointer.x + 12, rect.width - 132)}px`;
  tooltip.style.top = `${Math.max(3, pointer.y - 47)}px`;
});

chart.addEventListener('pointerleave', () => { tooltip.hidden = true; });
chart.addEventListener('click', (event) => {
  const rect = chart.getBoundingClientRect();
  const pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  const nearest = plottedPoints.reduce((best, point) => {
    const distance = Math.hypot(point.x - pointer.x, point.y - pointer.y);
    return distance < best.distance ? { point, distance } : best;
  }, { point: null, distance: 18 });
  if (nearest.point) selectSolution(nearest.point.solution.id);
});

document.querySelector('#export-csv').addEventListener('click', () => {
  const header = 'solucao,distancia_km,tempo_h,status';
  const rows = visibleSolutions.map((solution) => `${solution.id},${solution.cost},${solution.coverage},${solution.frontier ? 'nao_dominada' : 'dominada'}`);
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
document.querySelector('#open-modal').addEventListener('click', () => dialog.showModal());
document.querySelector('#open-modal-secondary').addEventListener('click', () => dialog.showModal());
document.querySelector('#instance-form').addEventListener('submit', createInstance);
document.querySelector('#start-run').addEventListener('click', startRun);
document.querySelector('#cancel-run').addEventListener('click', cancelRun);
document.querySelector('#view-route').addEventListener('click', showSelectedRoute);
document.querySelector('#download-route').addEventListener('click', downloadSelectedRoute);
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
  try {
    state.selectedInstanceId = instanceId;
    state.instance = await fetchJson(`/instances/${instanceId}`);
    const runsPayload = await fetchJson(`/instances/${instanceId}/runs?limit=1`);
    state.activeRun = runsPayload.runs?.[0] || null;
    state.resultOffset = 0;
    state.tableOffset = 0;
    applyInstanceSummary(state.instance);
    await loadInputAnalysis('time');
    if (state.activeRun?.status === 'completed') {
      await loadRunResults(state.activeRun.run_id, 0);
    } else {
      state.solutions = [];
      state.resultIsDemo = false;
      renderTable();
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
initializeDashboard();