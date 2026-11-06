(function hypervolume(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.Hypervolume = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function hypervolumeFactory() {
  const STORAGE_KEY = 'paretolab.showHypervolume';
  const REFERENCE_SHIFT = 0.05;
  const EPSILON = 1e-8;
  const NORMALIZE_EPSILON = 1e-12;

  function readShowHypervolume(storage) {
    try {
      return storage.getItem(STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  }

  function writeShowHypervolume(storage, enabled) {
    storage.setItem(STORAGE_KEY, enabled ? '1' : '0');
  }

  function directionOf(directions, key) {
    return directions && directions[key] === 'maximize' ? 'maximize' : 'minimize';
  }

  function minimizationValue(value, direction) {
    return direction === 'maximize' ? -Number(value) : Number(value);
  }

  function normalizedComponent(value, utopian, nadir, direction) {
    const best = minimizationValue(utopian, direction);
    const worst = minimizationValue(nadir, direction);
    const observed = minimizationValue(value, direction);
    const span = worst - best;
    if (!(span > NORMALIZE_EPSILON)) return 0;
    return (observed - best) / span;
  }

  function shiftNormalized(value) {
    const numeric = Number(value);
    return numeric + REFERENCE_SHIFT * Math.abs(numeric);
  }

  function objectiveReferencePoint(anchors) {
    if (!anchors || !anchors.utopian || !anchors.antiutopian) return null;
    const directions = anchors.directions || {};
    const invert = (utopian, nadir, direction) => {
      const span = minimizationValue(nadir, direction) - minimizationValue(utopian, direction);
      if (!(span > NORMALIZE_EPSILON)) return null;
      const minimized = minimizationValue(utopian, direction) + (1 + REFERENCE_SHIFT) * span;
      return direction === 'maximize' ? -minimized : minimized;
    };
    return {
      cost: invert(anchors.utopian.cost, anchors.antiutopian.cost, directionOf(directions, 'cost')),
      coverage: invert(anchors.utopian.coverage, anchors.antiutopian.coverage, directionOf(directions, 'coverage')),
    };
  }

  function dominates(left, right, directions) {
    const costDirection = directionOf(directions, 'cost');
    const coverageDirection = directionOf(directions, 'coverage');
    const costNoWorse = costDirection === 'maximize'
      ? left.cost >= right.cost - EPSILON
      : left.cost <= right.cost + EPSILON;
    const coverageNoWorse = coverageDirection === 'maximize'
      ? left.coverage >= right.coverage - EPSILON
      : left.coverage <= right.coverage + EPSILON;
    const costBetter = costDirection === 'maximize'
      ? left.cost > right.cost + EPSILON
      : left.cost < right.cost - EPSILON;
    const coverageBetter = coverageDirection === 'maximize'
      ? left.coverage > right.coverage + EPSILON
      : left.coverage < right.coverage - EPSILON;
    return costNoWorse && coverageNoWorse && (costBetter || coverageBetter);
  }

  function nonDominated(points, directions) {
    return points.filter((candidate, index, all) => !all.some(
      (other, otherIndex) => otherIndex !== index && dominates(other, candidate, directions),
    ));
  }

  function spreadDelta(points, extremes) {
    const ordered = points.slice().sort((left, right) => left.f1 - right.f1 || left.f2 - right.f2);
    if (ordered.length < 2) return 1;
    const distances = [];
    for (let index = 0; index < ordered.length - 1; index += 1) {
      distances.push(Math.hypot(
        ordered[index + 1].f1 - ordered[index].f1,
        ordered[index + 1].f2 - ordered[index].f2,
      ));
    }
    const meanDistance = distances.reduce((sum, value) => sum + value, 0) / distances.length;
    const deviation = distances.reduce((sum, value) => sum + Math.abs(value - meanDistance), 0);
    const extremeDistance = Math.hypot(ordered[0].f1 - extremes.f1.f1, ordered[0].f2 - extremes.f1.f2)
      + Math.hypot(ordered[ordered.length - 1].f1 - extremes.f2.f1, ordered[ordered.length - 1].f2 - extremes.f2.f2);
    const denominator = extremeDistance + distances.length * meanDistance;
    if (!(denominator > NORMALIZE_EPSILON)) return 0;
    return (extremeDistance + deviation) / denominator;
  }

  function referenceExtremes(points) {
    return {
      f1: points.reduce((best, point) => (
        point.f1 < best.f1 || (point.f1 === best.f1 && point.f2 < best.f2) ? point : best
      )),
      f2: points.reduce((best, point) => (
        point.f2 < best.f2 || (point.f2 === best.f2 && point.f1 < best.f1) ? point : best
      )),
    };
  }

  function hypervolume2d(points, reference) {
    const valid = points.filter((point) => point.cost <= reference.cost && point.coverage <= reference.coverage);
    if (!valid.length) return 0;
    const ordered = valid.slice().sort((left, right) => left.cost - right.cost || right.coverage - left.coverage);
    let total = 0;
    ordered.forEach((point, index) => {
      const nextCost = index === ordered.length - 1 ? reference.cost : ordered[index + 1].cost;
      const width = nextCost - point.cost;
      const height = reference.coverage - point.coverage;
      if (width > 0 && height > 0) total += width * height;
    });
    return total;
  }

  function sampleStdev(values) {
    if (values.length <= 1) return 0;
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
    const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (values.length - 1);
    return Math.sqrt(variance);
  }

  function coefficientOfVariation(mean, sampleStdevValue) {
    if (!Number.isFinite(mean) || mean === 0 || !Number.isFinite(sampleStdevValue)) return null;
    return sampleStdevValue / mean;
  }

  function readCoefficientOfVariation(payload, mean, sampleStdevValue) {
    if (payload && Object.prototype.hasOwnProperty.call(payload, 'coefficient_of_variation')) {
      if (payload.coefficient_of_variation == null) return null;
      const value = Number(payload.coefficient_of_variation);
      return Number.isFinite(value) ? value : null;
    }
    return coefficientOfVariation(mean, sampleStdevValue);
  }

  function formatCoefficientOfVariation(value) {
    if (!Number.isFinite(value)) {
      return { text: 'indisponível', unavailable: true, status: 'indisponível' };
    }
    if (value === 0) return { text: '0%', unavailable: false, status: '' };
    const percent = (value * 100).toFixed(1).replace('.', ',');
    return { text: `${percent}%`, unavailable: false, status: '' };
  }

  function summarizeChartSolutions(solutions, directions) {
    const specs = {
      cost: directionOf(directions, 'cost'),
      coverage: directionOf(directions, 'coverage'),
    };
    const points = (solutions || [])
      .map((solution) => ({
        id: solution.id,
        round: Number.isInteger(solution.round) && solution.round >= 1 ? solution.round : 1,
        cost: Number(solution.cost),
        coverage: Number(solution.coverage),
      }))
      .filter((point) => Number.isFinite(point.cost) && Number.isFinite(point.coverage));
    const referenceApi = globalThis.ReferencePoints;
    if (!points.length || !referenceApi) return null;
    const referencePoints = referenceApi.estimateFromChartSolutions(points.map((point) => ({
      cost: minimizationValue(point.cost, specs.cost),
      coverage: minimizationValue(point.coverage, specs.coverage),
    })));
    if (!referencePoints) return null;
    const restore = (value, direction) => (direction === 'maximize' ? -value : value);
    const utopian = {
      cost: restore(referencePoints.utopian.cost, specs.cost),
      coverage: restore(referencePoints.utopian.coverage, specs.coverage),
    };
    const nadir = {
      cost: restore(referencePoints.antiutopian.cost, specs.cost),
      coverage: restore(referencePoints.antiutopian.coverage, specs.coverage),
    };
    const reference = {
      cost: shiftNormalized(normalizedComponent(nadir.cost, utopian.cost, nadir.cost, specs.cost)),
      coverage: shiftNormalized(normalizedComponent(nadir.coverage, utopian.coverage, nadir.coverage, specs.coverage)),
    };
    const normalizedPoint = (point) => ({
      f1: normalizedComponent(point.coverage, utopian.coverage, nadir.coverage, specs.coverage),
      f2: normalizedComponent(point.cost, utopian.cost, nadir.cost, specs.cost),
      cost: normalizedComponent(point.cost, utopian.cost, nadir.cost, specs.cost),
      coverage: normalizedComponent(point.coverage, utopian.coverage, nadir.coverage, specs.coverage),
    });
    const normalized = points.map(normalizedPoint);
    const extremes = referenceExtremes(normalized);
    const rounds = [...new Set(points.map((point) => point.round))].sort((left, right) => left - right);
    const measured = rounds.map((round) => {
      const group = points.filter((point) => point.round === round);
      const front = nonDominated(group, specs);
      const normalizedFront = front.map(normalizedPoint);
      const area = hypervolume2d(normalizedFront, reference);
      return {
        round,
        hypervolume: area,
        candidateCount: front.length,
        points: front,
        spread: spreadDelta(normalizedFront, extremes),
      };
    });
    const hypervolumes = measured.map((item) => item.hypervolume);
    const spreads = measured.map((item) => item.spread);
    const meanHypervolume = hypervolumes.reduce((sum, value) => sum + value, 0) / hypervolumes.length;
    const sampleStdevHypervolume = sampleStdev(hypervolumes);
    const meanSpread = spreads.reduce((sum, value) => sum + value, 0) / spreads.length;
    const sampleStdevSpread = sampleStdev(spreads);
    return {
      nadir,
      referencePoint: reference,
      referenceShift: REFERENCE_SHIFT,
      unit: null,
      note: 'Área adimensional. Cada objetivo vai de 0 no utópico a 1 no nadir, e a referência é 1,05.',
      spreadNote: 'O espalhamento Δ usa o mesmo espaço. Δ = 0 indica distâncias consecutivas iguais e cobertura dos extremos.',
      standardDeviation: 'sample',
      rounds: measured.map((item) => ({
        ...item,
        distanceToMean: item.hypervolume - meanHypervolume,
      })),
      meanHypervolume,
      sampleStdevHypervolume,
      coefficientOfVariation: coefficientOfVariation(meanHypervolume, sampleStdevHypervolume),
      meanCandidateCount: measured.reduce((sum, item) => sum + item.candidateCount, 0) / measured.length,
      meanSpread,
      sampleStdevSpread,
      spreadCoefficientOfVariation: coefficientOfVariation(meanSpread, sampleStdevSpread),
    };
  }

  function mapApiHypervolume(payload) {
    if (!payload || !Array.isArray(payload.rounds) || !payload.reference_point || !payload.nadir) return null;
    const referencePoint = {
      cost: Number(payload.reference_point.distance),
      coverage: Number(payload.reference_point.time),
    };
    const nadir = {
      cost: Number(payload.nadir.distance),
      coverage: Number(payload.nadir.time),
    };
    if (![referencePoint.cost, referencePoint.coverage, nadir.cost, nadir.coverage].every(Number.isFinite)) return null;
    const rounds = payload.rounds.map((round) => ({
      round: round.round,
      hypervolume: Number(round.hypervolume),
      candidateCount: round.candidate_count,
      distanceToMean: Number(round.distance_to_mean),
      spread: Number(round.spread),
    }));
    if (rounds.some((round) => !Number.isFinite(round.hypervolume) || !Number.isFinite(round.distanceToMean) || !Number.isFinite(round.spread))) return null;
    const meanHypervolume = Number(payload.mean_hypervolume);
    const sampleStdevHypervolume = Number(payload.sample_stdev_hypervolume);
    const meanSpread = Number(payload.mean_spread);
    const sampleStdevSpread = Number(payload.sample_stdev_spread);
    return {
      nadir,
      referencePoint,
      referenceShift: payload.reference_shift,
      unit: null,
      note: payload.note || '',
      spreadNote: payload.spread_note || '',
      standardDeviation: payload.standard_deviation || 'sample',
      rounds,
      meanHypervolume,
      sampleStdevHypervolume,
      coefficientOfVariation: readCoefficientOfVariation(payload, meanHypervolume, sampleStdevHypervolume),
      meanCandidateCount: Number(payload.mean_candidate_count),
      meanSpread,
      sampleStdevSpread,
      spreadCoefficientOfVariation: readNamedCoefficient(
        payload,
        'spread_coefficient_of_variation',
        meanSpread,
        sampleStdevSpread,
      ),
    };
  }

  function readNamedCoefficient(payload, key, mean, sampleStdevValue) {
    if (payload && Object.prototype.hasOwnProperty.call(payload, key)) {
      if (payload[key] == null) return null;
      const value = Number(payload[key]);
      return Number.isFinite(value) ? value : null;
    }
    return coefficientOfVariation(mean, sampleStdevValue);
  }

  function formatHypervolume(value) {
    return Number.isFinite(value) ? value.toFixed(2) : '--';
  }

  function formatSignedDistance(value) {
    if (!Number.isFinite(value)) return '--';
    const formatted = value.toFixed(2);
    return value > 0 ? `+${formatted}` : formatted;
  }

  const QUALITY_COLUMNS = [
    { id: 'round', label: 'Rodada' },
    { id: 'hypervolume', label: 'Hipervolume' },
    { id: 'candidateCount', label: 'Soluções na fronteira candidata' },
    { id: 'distance', label: 'Distância do hipervolume à média' },
    { id: 'spread', label: 'Espalhamento Δ' },
  ];

  function hypervolumeView(summary) {
    if (!summary || !Array.isArray(summary.rounds)) return null;
    const coefficient = formatCoefficientOfVariation(summary.coefficientOfVariation);
    const spreadCoefficient = formatCoefficientOfVariation(summary.spreadCoefficientOfVariation);
    const notes = [summary.note, summary.spreadNote].filter(Boolean);
    return {
      mean: formatHypervolume(summary.meanHypervolume),
      stdev: formatHypervolume(summary.sampleStdevHypervolume),
      cv: coefficient.text,
      cvUnavailable: coefficient.unavailable,
      cvStatus: coefficient.status,
      meanCount: Number.isFinite(summary.meanCandidateCount) ? summary.meanCandidateCount.toFixed(2) : '--',
      spreadMean: formatHypervolume(summary.meanSpread),
      spreadStdev: formatHypervolume(summary.sampleStdevSpread),
      spreadCv: spreadCoefficient.text,
      spreadCvUnavailable: spreadCoefficient.unavailable,
      spreadCvStatus: spreadCoefficient.status,
      note: notes.join(' '),
      columns: QUALITY_COLUMNS,
      rows: summary.rounds.map((round) => ({
        round: round.round,
        hypervolume: formatHypervolume(round.hypervolume),
        candidateCount: String(round.candidateCount),
        distance: formatSignedDistance(round.distanceToMean),
        spread: formatHypervolume(round.spread),
      })),
    };
  }

  function chartExpansionState(expanded) {
    const isExpanded = Boolean(expanded);
    return {
      expanded: isExpanded,
      label: isExpanded ? 'Recolher mapa' : 'Ampliar mapa',
      ariaPressed: isExpanded ? 'true' : 'false',
    };
  }

  return {
    STORAGE_KEY,
    REFERENCE_SHIFT,
    readShowHypervolume,
    writeShowHypervolume,
    shiftNormalized,
    objectiveReferencePoint,
    hypervolume2d,
    spreadDelta,
    summarizeChartSolutions,
    mapApiHypervolume,
    formatHypervolume,
    formatSignedDistance,
    QUALITY_COLUMNS,
    hypervolumeView,
    chartExpansionState,
  };
});
