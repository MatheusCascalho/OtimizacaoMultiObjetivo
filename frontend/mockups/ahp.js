(function ahp(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.AHP = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function ahpFactory() {
  const CRITERIA = [
    { id: 'distance', label: 'Distância' },
    { id: 'nominalTime', label: 'Tempo' },
    { id: 'co2Kg', label: 'Emissão de CO2' },
    { id: 'minmax', label: 'Min-Max Regret' },
  ];
  const SCALE = [
    { value: 1 / 9, label: '1/9 · extrema (direita)' },
    { value: 1 / 8, label: '1/8 · intermediária' },
    { value: 1 / 7, label: '1/7 · muito forte (direita)' },
    { value: 1 / 6, label: '1/6 · intermediária' },
    { value: 1 / 5, label: '1/5 · forte (direita)' },
    { value: 1 / 4, label: '1/4 · intermediária' },
    { value: 1 / 3, label: '1/3 · moderada (direita)' },
    { value: 1 / 2, label: '1/2 · intermediária' },
    { value: 1, label: '1 · igual importância' },
    { value: 2, label: '2 · intermediária' },
    { value: 3, label: '3 · moderada (esquerda)' },
    { value: 4, label: '4 · intermediária' },
    { value: 5, label: '5 · forte (esquerda)' },
    { value: 6, label: '6 · intermediária' },
    { value: 7, label: '7 · muito forte (esquerda)' },
    { value: 8, label: '8 · intermediária' },
    { value: 9, label: '9 · extrema (esquerda)' },
  ];
  const MATRIX_PAGE_SIZE = 12;

  let container = null;
  let submitJudgments = null;
  let fetchMatrix = null;
  let solutions = [];
  let comparisons = {};
  let result = null;
  let matrixCriterion = CRITERIA[0].id;
  let matrixRowStart = 0;
  let matrixColumnStart = 0;

  function mount(node, calculate, loadMatrix) {
    container = node;
    if (!container) return;
    submitJudgments = calculate;
    fetchMatrix = loadMatrix;
    renderComparisons();
    container.querySelector('#ahp-calculate').addEventListener('click', runCalculation);
    container.querySelector('#ahp-reset').addEventListener('click', resetComparisons);
    container.querySelector('#ahp-matrix-criterion').addEventListener('change', (event) => {
      matrixCriterion = event.target.value;
      renderAlternativeMatrix();
    });
    container.querySelector('#ahp-matrix-row-prev').addEventListener('click', () => moveMatrixPage('row', -MATRIX_PAGE_SIZE));
    container.querySelector('#ahp-matrix-row-next').addEventListener('click', () => moveMatrixPage('row', MATRIX_PAGE_SIZE));
    container.querySelector('#ahp-matrix-column-prev').addEventListener('click', () => moveMatrixPage('column', -MATRIX_PAGE_SIZE));
    container.querySelector('#ahp-matrix-column-next').addEventListener('click', () => moveMatrixPage('column', MATRIX_PAGE_SIZE));
    container.querySelector('#ahp-matrices').addEventListener('toggle', (event) => {
      if (event.target.open && result) renderMatrices();
    });
    container.querySelector('#ahp-comparisons').addEventListener('change', (event) => {
      if (event.target.matches('select[data-pair]')) {
        comparisons[event.target.dataset.pair] = Number(event.target.value);
        result = null;
        container.querySelector('#ahp-results').hidden = true;
        container.querySelector('#ahp-matrices').hidden = true;
        setStatus('Julgamentos atualizados. Recalcule o ranking para aplicar os novos pesos.');
      }
    });
    setSolutions(null);
  }

  function renderComparisons() {
    const target = container.querySelector('#ahp-comparisons');
    const fragment = document.createDocumentFragment();
    for (let left = 0; left < CRITERIA.length; left += 1) {
      for (let right = left + 1; right < CRITERIA.length; right += 1) {
        const first = CRITERIA[left];
        const second = CRITERIA[right];
        const key = pairKey(first.id, second.id);
        const label = document.createElement('label');
        label.className = 'ahp-comparison';
        const prompt = document.createElement('span');
        prompt.append(
          document.createTextNode('Importância de '),
          Object.assign(document.createElement('strong'), { textContent: first.label }),
          document.createTextNode(' em relação a '),
          Object.assign(document.createElement('strong'), { textContent: second.label }),
        );
        const select = document.createElement('select');
        select.dataset.pair = key;
        select.setAttribute('aria-label', `Importância de ${first.label} em relação a ${second.label}`);
        SCALE.forEach((option) => {
          const element = document.createElement('option');
          element.value = String(option.value);
          element.textContent = option.label;
          if (isClose(option.value, Number(comparisons[key] ?? 1))) element.selected = true;
          select.append(element);
        });
        label.append(prompt, select);
        fragment.append(label);
      }
    }
    target.replaceChildren(fragment);
  }

  function setSolutions(items) {
    solutions = Array.isArray(items) ? items : [];
    result = null;
    if (!container) return;
    container.querySelector('#ahp-results').hidden = true;
    container.querySelector('#ahp-matrices').hidden = true;
    const calculateButton = container.querySelector('#ahp-calculate');
    const incomplete = solutions.find((item) => CRITERIA.some((criterion) => !hasCriterionValue(item, criterion)));
    calculateButton.disabled = !solutions.length || Boolean(incomplete);
    if (!solutions.length) {
      setStatus('Execute uma otimização e a análise de robustez para carregar as rotas e calcular emissão e Min-Max Regret.');
      return;
    }
    if (incomplete) {
      const missing = CRITERIA
        .filter((criterion) => !hasCriterionValue(incomplete, criterion))
        .map((criterion) => criterion.label)
        .join(', ');
      setStatus(`Ranking indisponível: ${incomplete.name || incomplete.id || 'uma solução'} não tem dados válidos para ${missing}. Verifique a análise de robustez e as emissões.`);
      return;
    }
    setStatus(`${solutions.length} ${solutions.length === 1 ? 'solução disponível' : 'soluções disponíveis'} para comparação. Dados da execução selecionada.`);
  }

  function hasCriterionValue(solution, criterion) {
    const value = solution?.[criterion.id];
    return typeof value === 'number' && Number.isFinite(value);
  }

  async function runCalculation() {
    const calculateButton = container.querySelector('#ahp-calculate');
    if (!submitJudgments) {
      setStatus('O serviço de decisão AHP não está disponível.', true);
      return;
    }
    if (!solutions.length) {
      setStatus('Não há soluções disponíveis para o ranking.', true);
      return;
    }
    calculateButton.disabled = true;
    calculateButton.textContent = 'Calculando ranking...';
    try {
      result = await submitJudgments(comparisons);
      if (!result
        || !Array.isArray(result.criteria_matrix)
        || !result.consistency
        || !Array.isArray(result.ranking)
        || !result.criteria_weights) {
        throw new Error('A resposta do serviço AHP está incompleta.');
      }
      matrixRowStart = 0;
      matrixColumnStart = 0;
      renderResults();
      container.querySelector('#ahp-matrices').hidden = false;
      const ratio = result.consistency.ratio;
      setStatus(ratio <= 0.1
        ? `Ranking calculado. Razão de consistência (RC): ${formatNumber(ratio * 100, 2)}% — julgamentos aceitáveis.`
        : `Ranking calculado, mas a RC é ${formatNumber(ratio * 100, 2)}% (acima de 10%). Revise as comparações; o ranking atual é provisório.`);
    } catch (error) {
      result = null;
      container.querySelector('#ahp-results').hidden = true;
      container.querySelector('#ahp-matrices').hidden = true;
      setStatus(`Não foi possível calcular o ranking AHP: ${error.message}`, true);
    } finally {
      calculateButton.textContent = 'Calcular ranking';
      calculateButton.disabled = !solutions.length;
    }
  }

  function resetComparisons() {
    comparisons = {};
    renderComparisons();
    result = null;
    container.querySelector('#ahp-results').hidden = true;
    container.querySelector('#ahp-matrices').hidden = true;
    setStatus('Todas as comparações foram redefinidas para igual importância (1).');
  }

  function renderResults() {
    const weightsBody = container.querySelector('#ahp-weights tbody');
    weightsBody.replaceChildren(...CRITERIA.map((criterion) => {
      const row = document.createElement('tr');
      appendCell(row, criterion.label, 'th', { scope: 'row' });
      appendCell(row, formatPercent(result.criteria_weights[criterion.id]));
      return row;
    }));
    container.querySelector('#ahp-consistency').textContent =
      `λmax ${formatNumber(result.consistency.lambda_max, 4)} · IC ${formatNumber(result.consistency.consistency_index, 4)} · RC ${formatPercent(result.consistency.ratio)}`;

    const rankingBody = container.querySelector('#ahp-ranking tbody');
    rankingBody.replaceChildren(...result.ranking.map((solution, index) => {
      const row = document.createElement('tr');
      if (index === 0) row.className = 'ahp-best';
      appendCell(row, String(index + 1), 'th', { scope: 'row' });
      appendCell(row, solution.name || solution.label || solution.solution_id || `Solução ${index + 1}`, 'th', {
        scope: 'row',
        title: solution.solution_id ? String(solution.solution_id) : '',
      });
      CRITERIA.forEach((criterion) => appendCell(row, formatPercent(solution.local?.[criterion.id])));
      appendCell(row, formatNumber(solution.score, 5), 'td', { className: 'ahp-score' });
      rankingBody.append(row);
    }));
    container.querySelector('#ahp-results').hidden = false;
    if (container.querySelector('#ahp-matrices').open) renderMatrices();
  }

  function renderMatrices() {
    if (!result) return;
    renderCriteriaMatrix();
    renderAlternativeMatrix();
  }

  function renderCriteriaMatrix() {
    const table = container.querySelector('#ahp-criteria-matrix');
    const header = document.createElement('thead');
    const heading = document.createElement('tr');
    appendCell(heading, 'Critério', 'th', { scope: 'col' });
    CRITERIA.forEach((criterion) => appendCell(heading, criterion.label, 'th', { scope: 'col' }));
    header.append(heading);
    const body = document.createElement('tbody');
    CRITERIA.forEach((criterion, rowIndex) => {
      const row = document.createElement('tr');
      appendCell(row, criterion.label, 'th', { scope: 'row' });
      result.criteria_matrix[rowIndex].forEach((value) => appendCell(row, formatMatrixValue(value)));
      body.append(row);
    });
    table.replaceChildren(header, body);
  }

  async function renderAlternativeMatrix() {
    if (!container || !result) return;
    const criterion = CRITERIA.find((item) => item.id === matrixCriterion) || CRITERIA[0];
    const items = solutions;
    matrixRowStart = clampStart(matrixRowStart, items.length);
    matrixColumnStart = clampStart(matrixColumnStart, items.length);
    const rowEnd = Math.min(matrixRowStart + MATRIX_PAGE_SIZE, items.length);
    const columnEnd = Math.min(matrixColumnStart + MATRIX_PAGE_SIZE, items.length);
    if (!fetchMatrix) {
      setStatus('O serviço de matrizes AHP não está disponível.', true);
      return;
    }
    const request = {
      criterion: criterion.id,
      rowOffset: matrixRowStart,
      columnOffset: matrixColumnStart,
    };
    try {
      const response = await fetchMatrix(request);
      if (request.criterion !== matrixCriterion
        || request.rowOffset !== matrixRowStart
        || request.columnOffset !== matrixColumnStart) return;
      if (response?.criterion !== criterion.id
        || response.row_offset !== matrixRowStart
        || response.column_offset !== matrixColumnStart
        || !Array.isArray(response.matrix)
        || response.matrix.length !== rowEnd - matrixRowStart
        || response.matrix.some((row) => !Array.isArray(row) || row.length !== columnEnd - matrixColumnStart)) {
        throw new Error('A resposta do serviço AHP não contém o bloco da matriz solicitado.');
      }
      renderAlternativeMatrixTable(criterion, items, response.matrix, rowEnd, columnEnd);
    } catch (error) {
      setStatus(`Não foi possível carregar a matriz de alternativas: ${error.message}`, true);
    }
  }

  function renderAlternativeMatrixTable(criterion, items, matrix, rowEnd, columnEnd) {
    const table = container.querySelector('#ahp-alternatives-matrix');
    const header = document.createElement('thead');
    const heading = document.createElement('tr');
    appendCell(heading, 'Solução', 'th', { scope: 'col' });
    items.slice(matrixColumnStart, columnEnd).forEach((item, index) => {
      appendCell(heading, item.label || `S${matrixColumnStart + index + 1}`, 'th', {
        scope: 'col',
        title: item.name || item.id || '',
      });
    });
    header.append(heading);
    const body = document.createElement('tbody');
    items.slice(matrixRowStart, rowEnd).forEach((item, localIndex) => {
      const rowIndex = matrixRowStart + localIndex;
      const row = document.createElement('tr');
      appendCell(row, item.label || `S${rowIndex + 1}`, 'th', {
        scope: 'row',
        title: item.name || item.id || '',
      });
      items.slice(matrixColumnStart, columnEnd).forEach((_, localColumnIndex) => {
        appendCell(row, formatMatrixValue(matrix[localIndex]?.[localColumnIndex]));
      });
      body.append(row);
    });
    table.replaceChildren(header, body);
    const rowLabel = container.querySelector('#ahp-matrix-row-range');
    const columnLabel = container.querySelector('#ahp-matrix-column-range');
    rowLabel.textContent = `Linhas ${matrixRowStart + 1}–${rowEnd} de ${items.length}`;
    columnLabel.textContent = `Colunas ${matrixColumnStart + 1}–${columnEnd} de ${items.length}`;
    container.querySelector('#ahp-matrix-row-prev').disabled = matrixRowStart === 0;
    container.querySelector('#ahp-matrix-column-prev').disabled = matrixColumnStart === 0;
    container.querySelector('#ahp-matrix-row-next').disabled = rowEnd >= items.length;
    container.querySelector('#ahp-matrix-column-next').disabled = columnEnd >= items.length;
  }

  function moveMatrixPage(axis, amount) {
    if (axis === 'row') matrixRowStart = clampStart(matrixRowStart + amount, solutions.length);
    else matrixColumnStart = clampStart(matrixColumnStart + amount, solutions.length);
    renderAlternativeMatrix();
  }

  function clampStart(start, length) {
    if (!length) return 0;
    return Math.max(0, Math.min(start, Math.floor((length - 1) / MATRIX_PAGE_SIZE) * MATRIX_PAGE_SIZE));
  }

  function appendCell(row, text, tagName = 'td', attributes = {}) {
    const cell = document.createElement(tagName);
    cell.textContent = text == null ? '—' : String(text);
    Object.entries(attributes).forEach(([name, value]) => {
      if (name === 'className') cell.className = value;
      else if (value !== '') cell.setAttribute(name, String(value));
    });
    row.append(cell);
    return cell;
  }

  function setStatus(message, isError = false) {
    const status = container?.querySelector('#ahp-status');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('error', isError);
  }

  function formatNumber(value, digits = 3) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    return Number(value).toLocaleString('pt-BR', { maximumFractionDigits: digits });
  }

  function formatPercent(value) {
    if (value == null || !Number.isFinite(Number(value))) return '—';
    return `${(Number(value) * 100).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`;
  }

  function formatMatrixValue(value) {
    if (!Number.isFinite(Number(value))) return '—';
    value = Number(value);
    if (Math.abs(value - 1) < 1e-10) return '1';
    if (value < 1) return `1/${formatNumber(1 / value, 2)}`;
    return formatNumber(value, 3);
  }

  function isClose(left, right) {
    return Math.abs(left - right) <= Math.max(1, Math.abs(left), Math.abs(right)) * 1e-10;
  }

  function pairKey(first, second) {
    return `${first}:${second}`;
  }

  return {
    CRITERIA,
    SCALE,
    mount,
    setSolutions,
    clear: () => setSolutions(null),
  };
});
