(function referencePoints(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.ReferencePoints = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function referencePointsFactory() {
  const STORAGE_KEY = 'paretolab.showReferencePoints';
  const NORMALIZE_KEY = 'paretolab.normalizeReferenceScale';
  const CONE_KEY = 'paretolab.showDominanceCone';
  const APPROXIMATE_FRONTIER_KEY = 'paretolab.showApproximateFrontier';
  const EPSILON = 1e-8;
  const NORMALIZE_EPSILON = 1e-12;

  function minimizationValue(value, direction) {
    return direction === 'maximize' ? -Number(value) : Number(value);
  }

  function objectiveDirections(reference) {
    const directions = reference && reference.directions;
    return {
      cost: directions && directions.cost === 'maximize' ? 'maximize' : 'minimize',
      coverage: directions && directions.coverage === 'maximize' ? 'maximize' : 'minimize',
    };
  }

  function normalizedRatio(value, utopian, nadir, direction) {
    const best = minimizationValue(utopian, direction);
    const worst = minimizationValue(nadir, direction);
    const observed = minimizationValue(value, direction);
    const span = worst - best;
    if (!(span > NORMALIZE_EPSILON)) return 0;
    return (observed - best) / span;
  }

  function normalizeToPercent(point, reference) {
    const directions = objectiveDirections(reference);
    return {
      cost: normalizedRatio(point.cost, reference.utopian.cost, reference.antiutopian.cost, directions.cost) * 100,
      coverage: normalizedRatio(
        point.coverage,
        reference.utopian.coverage,
        reference.antiutopian.coverage,
        directions.coverage,
      ) * 100,
    };
  }

  function plottedDelta(point, anchor, reference, normalized) {
    if (normalized) {
      const left = normalizeToPercent(point, reference);
      const right = normalizeToPercent(anchor, reference);
      return { cost: left.cost - right.cost, coverage: left.coverage - right.coverage };
    }
    const directions = objectiveDirections(reference);
    return {
      cost: minimizationValue(point.cost, directions.cost) - minimizationValue(anchor.cost, directions.cost),
      coverage: minimizationValue(point.coverage, directions.coverage) - minimizationValue(anchor.coverage, directions.coverage),
    };
  }

  function coneRelation(point, anchor, reference, normalized) {
    if (!point || !anchor) return 'outside';
    const delta = plottedDelta(point, anchor, reference, normalized);
    const worseOrEqualCost = delta.cost >= -EPSILON;
    const worseOrEqualCoverage = delta.coverage >= -EPSILON;
    const strictlyWorseCost = delta.cost > EPSILON;
    const strictlyWorseCoverage = delta.coverage > EPSILON;
    if (strictlyWorseCost && strictlyWorseCoverage) return 'strict-interior';
    if (worseOrEqualCost && worseOrEqualCoverage) return 'boundary';
    return 'outside';
  }

  function visibleUnderCone(solutions, anchor, reference, normalized) {
    return (solutions || []).filter((solution) => {
      if (!anchor || solution.id === anchor.id) return true;
      return coneRelation(solution, anchor, reference, normalized) !== 'strict-interior';
    });
  }

  function dominates(left, right, directions) {
    const specs = objectiveDirections({ directions });
    const costNoWorse = specs.cost === 'maximize'
      ? left.cost >= right.cost - EPSILON
      : left.cost <= right.cost + EPSILON;
    const coverageNoWorse = specs.coverage === 'maximize'
      ? left.coverage >= right.coverage - EPSILON
      : left.coverage <= right.coverage + EPSILON;
    const costBetter = specs.cost === 'maximize'
      ? left.cost > right.cost + EPSILON
      : left.cost < right.cost - EPSILON;
    const coverageBetter = specs.coverage === 'maximize'
      ? left.coverage > right.coverage + EPSILON
      : left.coverage < right.coverage - EPSILON;
    return costNoWorse && coverageNoWorse && (costBetter || coverageBetter);
  }

  function approximateFrontier(solutions, directions) {
    const specs = objectiveDirections({ directions });
    return (solutions || []).filter((candidate, index, all) => !all.some(
      (other, otherIndex) => otherIndex !== index && dominates(other, candidate, specs),
    ));
  }

  function classifyApproximateFrontier(solutions, directions) {
    const frontier = approximateFrontier(solutions, directions);
    const ids = new Set(frontier.map((item) => item.id));
    return {
      frontier,
      dominated: (solutions || []).filter((item) => !ids.has(item.id)),
    };
  }

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
      distanceLabel: 'Distância euclidiana normalizada',
      distanceNote: 'Cada objetivo vai de 0 no utópico a 1 no nadir.',
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
      directions: { cost: 'minimize', coverage: 'minimize' },
    };
  }

  function directionFromObjectives(objectives, id) {
    const found = (objectives || []).find((item) => item && item.id === id);
    return found && found.direction === 'maximize' ? 'maximize' : 'minimize';
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
      distanceLabel: (payload.distance && payload.distance.label) || 'Distância euclidiana normalizada',
      distanceNote: (payload.distance && payload.distance.note) || 'Cada objetivo vai de 0 no utópico a 1 no nadir.',
      utopian,
      antiutopian,
      warnings: payload.warnings || [],
      directions: {
        cost: directionFromObjectives(payload.objectives, 'distance'),
        coverage: directionFromObjectives(payload.objectives, 'time'),
      },
    };
  }

  function euclideanDistance(left, right) {
    return Math.hypot(left.cost - right.cost, left.coverage - right.coverage);
  }

  function formatObjectiveDistance(value) {
    return Number.isFinite(value) ? value.toFixed(2) : '--';
  }

  function normalizedUnitPoint(point, reference) {
    const percent = normalizeToPercent(point, reference);
    return { cost: percent.cost / 100, coverage: percent.coverage / 100 };
  }

  function measureReferenceDistances(solution, referencePoints) {
    if (!solution || !referencePoints) return { eligible: false };
    if (!solution.frontier) return { eligible: false };
    const observed = normalizedUnitPoint(solution, referencePoints);
    return {
      eligible: true,
      toUtopian: euclideanDistance(observed, normalizedUnitPoint(referencePoints.utopian, referencePoints)),
      toAntiutopian: euclideanDistance(observed, normalizedUnitPoint(referencePoints.antiutopian, referencePoints)),
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

  function readPreference(storage, key, defaultValue) {
    try {
      const value = storage.getItem(key);
      if (value === '0') return false;
      if (value === '1') return true;
    } catch {
      return defaultValue;
    }
    return defaultValue;
  }

  function writePreference(storage, key, enabled) {
    storage.setItem(key, enabled ? '1' : '0');
  }

  return {
    STORAGE_KEY,
    NORMALIZE_KEY,
    CONE_KEY,
    APPROXIMATE_FRONTIER_KEY,
    estimateFromChartSolutions,
    mapApiReferencePoints,
    euclideanDistance,
    formatObjectiveDistance,
    measureReferenceDistances,
    readShowReferencePoints,
    writeShowReferencePoints,
    readPreference,
    writePreference,
    normalizeToPercent,
    coneRelation,
    visibleUnderCone,
    approximateFrontier,
    classifyApproximateFrontier,
  };
});
