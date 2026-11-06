(function referencePoints(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.ReferencePoints = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function referencePointsFactory() {
  const STORAGE_KEY = 'paretolab.showReferencePoints';
  const EPSILON = 1e-8;

  function estimateFromChartSolutions(solutions) {
    const points = (solutions || [])
      .map((solution) => ({
        cost: Number(solution.cost),
        coverage: Number(solution.coverage),
      }))
      .filter((point) => Number.isFinite(point.cost) && Number.isFinite(point.coverage));
    if (!points.length) return null;

    const bestCost = Math.min(...points.map((point) => point.cost));
    const nadirCoverage = Math.min(
      ...points.filter((point) => point.cost <= bestCost + EPSILON).map((point) => point.coverage),
    );
    const bestCoverage = Math.min(...points.map((point) => point.coverage));
    const nadirCost = Math.min(
      ...points.filter((point) => point.coverage <= bestCoverage + EPSILON).map((point) => point.cost),
    );
    const warnings = [];
    if (nadirCost - bestCost <= EPSILON || nadirCoverage - bestCoverage <= EPSILON) {
      warnings.push({
        code: 'non_conflicting_objectives',
        message: 'Objetivos não conflitantes: a faixa de variação de pelo menos um objetivo é nula.',
      });
    }
    return {
      method: 'approximate_front',
      note: 'Estimativa ilustrativa a partir dos pontos exibidos.',
      distanceLabel: 'Distância euclidiana',
      distanceNote: 'No espaço dos objetivos, sem normalizar',
      utopian: {
        id: 'utopian',
        label: 'Solução utópica',
        cost: bestCost,
        coverage: bestCoverage,
      },
      antiutopian: {
        id: 'antiutopian',
        label: 'Solução antiutópica',
        cost: nadirCost,
        coverage: nadirCoverage,
      },
      warnings,
    };
  }

  function mapApiReferencePoints(payload) {
    const utopianValues = payload && payload.utopian && payload.utopian.objective_values;
    const antiutopianValues = payload && payload.antiutopian && payload.antiutopian.objective_values;
    if (!utopianValues || !antiutopianValues) return null;
    const utopian = {
      id: 'utopian',
      label: payload.utopian.label || 'Solução utópica',
      cost: Number(utopianValues.distance),
      coverage: Number(utopianValues.time),
    };
    const antiutopian = {
      id: 'antiutopian',
      label: payload.antiutopian.label || 'Solução antiutópica',
      cost: Number(antiutopianValues.distance),
      coverage: Number(antiutopianValues.time),
    };
    if (![utopian.cost, utopian.coverage, antiutopian.cost, antiutopian.coverage].every(Number.isFinite)) {
      return null;
    }
    return {
      method: payload.method,
      note: payload.note || '',
      distanceLabel: (payload.distance && payload.distance.label) || 'Distância euclidiana',
      distanceNote: (payload.distance && payload.distance.note) || 'No espaço dos objetivos, sem normalizar',
      utopian,
      antiutopian,
      warnings: payload.warnings || [],
    };
  }

  function euclideanDistance(left, right) {
    return Math.hypot(left.cost - right.cost, left.coverage - right.coverage);
  }

  function formatObjectiveDistance(value) {
    return Number.isFinite(value) ? value.toFixed(2) : '--';
  }

  function measureReferenceDistances(solution, referencePoints) {
    if (!solution || !referencePoints) return { eligible: false };
    if (!solution.frontier) return { eligible: false };
    return {
      eligible: true,
      toUtopian: euclideanDistance(solution, referencePoints.utopian),
      toAntiutopian: euclideanDistance(solution, referencePoints.antiutopian),
    };
  }

  function readShowReferencePoints(storage) {
    try {
      const value = storage.getItem(STORAGE_KEY);
      if (value === '0') return false;
      if (value === '1') return true;
    } catch {
      return true;
    }
    return true;
  }

  function writeShowReferencePoints(storage, visible) {
    storage.setItem(STORAGE_KEY, visible ? '1' : '0');
  }

  return {
    STORAGE_KEY,
    estimateFromChartSolutions,
    mapApiReferencePoints,
    euclideanDistance,
    formatObjectiveDistance,
    measureReferenceDistances,
    readShowReferencePoints,
    writeShowReferencePoints,
  };
});
