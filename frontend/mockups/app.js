const solutions = [
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

const chart = document.querySelector('#pareto-chart');
const chartContext = chart.getContext('2d');
const tableBody = document.querySelector('#solutions-body');
const tooltip = document.querySelector('#chart-tooltip');
const searchInput = document.querySelector('#solution-search');
let selectedId = '018';
let activeView = 'frontier';
let visibleSolutions = [];
let plottedPoints = [];

const currency = (value) => `R$ ${value.toFixed(2).replace('.', ',')}`;
const percent = (value) => `${value.toFixed(1).replace('.', ',')}%`;

function renderTable() {
  const query = searchInput.value.trim().toLowerCase();
  visibleSolutions = solutions.filter((solution) => {
    const matchesSearch = `${solution.id} ${currency(solution.cost)} ${percent(solution.coverage)}`.toLowerCase().includes(query);
    return matchesSearch && (activeView === 'all' || solution.frontier);
  });

  const pageSolutions = visibleSolutions.slice(0, 6);
  tableBody.innerHTML = pageSolutions.map((solution) => `
    <tr class="${solution.id === selectedId ? 'selected-row' : ''}" data-solution="${solution.id}" tabindex="0" aria-selected="${solution.id === selectedId}">
      <td><span class="table-id">SOL-${solution.id}</span></td>
      <td><span class="table-number">${currency(solution.cost)}</span></td>
      <td><span class="table-number">${percent(solution.coverage)}</span></td>
      <td><span class="status-pill ${solution.frontier ? 'frontier' : 'dominated'}">${solution.frontier ? 'Não dominada' : 'Dominada'}</span></td>
      <td class="row-arrow" aria-hidden="true">↗</td>
    </tr>`).join('');

  const shown = pageSolutions.length;
  document.querySelector('#table-summary').textContent = query
    ? `Encontradas ${visibleSolutions.length} soluções`
    : `Mostrando ${shown} de ${activeView === 'all' ? solutions.length : solutions.filter((solution) => solution.frontier).length} soluções`;
  document.querySelector('.table-count').textContent = visibleSolutions.length;
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
  const minCost = 8;
  const maxCost = 35;
  const minCoverage = 55;
  const maxCoverage = 100;
  const x = (cost) => inset.left + ((cost - minCost) / (maxCost - minCost)) * plotWidth;
  const y = (coverage) => inset.top + ((maxCoverage - coverage) / (maxCoverage - minCoverage)) * plotHeight;

  chartContext.clearRect(0, 0, width, height);
  chartContext.font = '9px "IBM Plex Mono", monospace';
  chartContext.textBaseline = 'middle';
  chartContext.lineWidth = 1;

  [60, 70, 80, 90, 100].forEach((tick) => {
    const position = y(tick);
    chartContext.strokeStyle = '#e9ebe3';
    chartContext.beginPath();
    chartContext.moveTo(inset.left, position);
    chartContext.lineTo(width - inset.right, position);
    chartContext.stroke();
    chartContext.fillStyle = '#89928a';
    chartContext.textAlign = 'right';
    chartContext.fillText(String(tick), inset.left - 8, position);
  });

  [10, 15, 20, 25, 30, 35].forEach((tick) => {
    const position = x(tick);
    chartContext.strokeStyle = '#eff0ea';
    chartContext.beginPath();
    chartContext.moveTo(position, inset.top);
    chartContext.lineTo(position, height - inset.bottom);
    chartContext.stroke();
    chartContext.fillStyle = '#89928a';
    chartContext.textAlign = 'center';
    chartContext.fillText(String(tick), position, height - 11);
  });

  const frontier = solutions.filter((solution) => solution.frontier).sort((a, b) => a.cost - b.cost);
  chartContext.beginPath();
  frontier.forEach((solution, index) => {
    if (index === 0) chartContext.moveTo(x(solution.cost), y(solution.coverage));
    else chartContext.lineTo(x(solution.cost), y(solution.coverage));
  });
  chartContext.strokeStyle = '#6d9779';
  chartContext.lineWidth = 1.5;
  chartContext.setLineDash([4, 4]);
  chartContext.stroke();
  chartContext.setLineDash([]);

  plottedPoints = [];
  const pointsToDraw = activeView === 'all' ? solutions : frontier;
  pointsToDraw.forEach((solution) => {
    const px = x(solution.cost);
    const py = y(solution.coverage);
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
  const solution = solutions.find((item) => item.id === id);
  if (!solution) return;
  selectedId = id;
  document.querySelector('#selected-title').textContent = `Solução ${solution.id}`;
  document.querySelector('#selected-cost').textContent = currency(solution.cost);
  document.querySelector('#selected-coverage').textContent = percent(solution.coverage);
  document.querySelector('#selected-items').textContent = `${solution.items} de 20`;
  renderTable();
}

function setView(view) {
  activeView = view;
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

searchInput.addEventListener('input', renderTable);
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
  tooltip.innerHTML = `<strong>SOL-${solution.id}</strong><span>Custo: ${currency(solution.cost)}</span><span>Cobertura: ${percent(solution.coverage)}</span>`;
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

document.querySelector('#compare-button').addEventListener('click', () => {
  const feedback = document.querySelector('#compare-feedback');
  feedback.textContent = `Solução ${selectedId} adicionada à comparação.`;
  window.setTimeout(() => { feedback.textContent = ''; }, 2600);
});

document.querySelector('#export-csv').addEventListener('click', () => {
  const header = 'solucao,custo,cobertura,status';
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
document.querySelector('#open-modal').addEventListener('click', () => dialog.showModal());

function showFileName(input, target, fallback) {
  const file = input.files[0];
  target.textContent = file ? `${file.name} · ${(file.size / (1024 * 1024)).toFixed(1)} MB` : fallback;
}

const fileInput = document.querySelector('#file-input');
fileInput.addEventListener('change', () => showFileName(fileInput, document.querySelector('#file-feedback'), 'Os dados ficam neste protótipo, não são enviados.'));
const dropZone = document.querySelector('.drop-zone');
['dragenter', 'dragover'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.add('dragover');
}));
['dragleave', 'drop'].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.remove('dragover');
}));
dropZone.addEventListener('drop', (event) => {
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  showFileName(fileInput, document.querySelector('#file-feedback'), 'Os dados ficam neste protótipo, não são enviados.');
});

const dialogFileInput = document.querySelector('#dialog-file-input');
dialogFileInput.addEventListener('change', () => showFileName(dialogFileInput, document.querySelector('#dialog-file-name'), 'Nenhum arquivo selecionado'));
document.querySelector('#instance-form').addEventListener('submit', (event) => {
  if (event.submitter?.id !== 'create-instance') return;
  event.preventDefault();
  const name = document.querySelector('#instance-title').value.trim();
  if (!name) return;
  const instanceName = document.querySelector('#instance-name');
  instanceName.innerHTML = `${name} <span class="instance-id">/ nova instância</span>`;
  document.querySelector('.micro-label').textContent = `${document.querySelector('#problem-type').value.toUpperCase()} · RASCUNHO`;
  document.querySelector('.run-badge').innerHTML = '<span class="status-dot"></span>Não executada';
  document.querySelector('.toolbar-date').textContent = 'Agora';
  dialog.close();
  document.querySelector('#instance-title').value = '';
});

const resizeObserver = new ResizeObserver(drawChart);
resizeObserver.observe(chart);
renderTable();