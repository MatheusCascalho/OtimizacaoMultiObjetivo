const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const referenceApi = require(path.join(__dirname, '../../frontend/mockups/reference_points.js'));
const hypervolumeApi = require(path.join(
  __dirname,
  '../../frontend/mockups/hypervolume.js',
));

const directions = { cost: 'minimize', coverage: 'minimize' };

test('hypervolume uses the normalized reference at 1.1 and ignores dominated points', () => {
  const summary = hypervolumeApi.summarizeChartSolutions([
    { id: 'a', round: 1, cost: 0, coverage: 4 },
    { id: 'b', round: 1, cost: 4, coverage: 0 },
    { id: 'c', round: 1, cost: 5, coverage: 5 },
    { id: 'd', round: 2, cost: 1, coverage: 3 },
    { id: 'e', round: 2, cost: 3, coverage: 1 },
  ], directions);

  assert.deepEqual(summary.nadir, { cost: 4, coverage: 4 });
  assert.ok(Math.abs(summary.referencePoint.cost - 1.1) < 1e-9);
  assert.ok(Math.abs(summary.referencePoint.coverage - 1.1) < 1e-9);
  assert.equal(summary.rounds[0].candidateCount, 2);
  assert.ok(Math.abs(summary.rounds[0].hypervolume - 0.21) < 1e-9);
  assert.equal(summary.rounds[1].candidateCount, 2);
  assert.ok(Math.abs(summary.rounds[1].hypervolume - 0.4725) < 1e-9);
  assert.ok(Math.abs(summary.meanHypervolume - 0.34125) < 1e-9);
  assert.ok(Math.abs(summary.sampleStdevHypervolume - Math.sqrt((0.21 - 0.34125) ** 2 * 2)) < 1e-9);
  assert.ok(Math.abs(summary.coefficientOfVariation - (summary.sampleStdevHypervolume / summary.meanHypervolume)) < 1e-9);
  assert.equal(summary.meanCandidateCount, 2);
  assert.ok(Math.abs(summary.rounds[0].distanceToMean - (0.21 - 0.34125)) < 1e-9);
  assert.equal(summary.unit, null);
  assert.equal(summary.standardDeviation, 'sample');
});

test('normalized hypervolume does not inherit absolute objective scales', () => {
  const compact = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 0, coverage: 4 },
    { round: 1, cost: 4, coverage: 0 },
  ], directions);
  const shifted = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 10, coverage: 4000 },
    { round: 1, cost: 14, coverage: 0 },
  ], directions);

  assert.ok(Math.abs(shifted.rounds[0].hypervolume - compact.rounds[0].hypervolume) < 1e-9);
  assert.ok(Math.abs(shifted.rounds[0].hypervolume - 0.21) < 1e-9);
  assert.ok(Math.abs(shifted.referencePoint.cost - 1.1) < 1e-9);
});

test('a single round has sample standard deviation zero', () => {
  const summary = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 0, coverage: 4 },
    { round: 1, cost: 4, coverage: 0 },
  ], directions);

  assert.equal(summary.sampleStdevHypervolume, 0);
  assert.equal(summary.coefficientOfVariation, 0);
  assert.equal(hypervolumeApi.hypervolumeView(summary).cv, '0%');
  assert.equal(summary.rounds[0].distanceToMean, 0);
});

test('a zero mean leaves the coefficient of variation unavailable', () => {
  const summary = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 0, coverage: 0 },
    { round: 2, cost: 0, coverage: 0 },
  ], directions);
  const view = hypervolumeApi.hypervolumeView(summary);

  assert.equal(summary.meanHypervolume, 0);
  assert.equal(summary.coefficientOfVariation, null);
  assert.equal(view.cv, 'indisponível');
  assert.equal(view.cvUnavailable, true);
  assert.equal(view.cvStatus, 'indisponível');
});

test('maximization shifts toward the worse side', () => {
  const summary = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 1, coverage: 5 },
    { round: 1, cost: 0, coverage: 1 },
  ], { cost: 'minimize', coverage: 'maximize' });

  assert.ok(Math.abs(summary.nadir.coverage - 1) < 1e-9);
  assert.ok(Math.abs(summary.nadir.cost - 1) < 1e-9);
  assert.ok(Math.abs(summary.referencePoint.coverage - 1.1) < 1e-9);
  assert.ok(Math.abs(summary.referencePoint.cost - 1.1) < 1e-9);
  assert.ok(Math.abs(summary.rounds[0].hypervolume - 0.21) < 1e-9);
});

test('the drawn reference is 110 percent and a null span stays closed', () => {
  const anchors = {
    utopian: { cost: 10, coverage: 100 },
    antiutopian: { cost: 14, coverage: 104 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  };
  const plotted = hypervolumeApi.objectiveReferencePoint(anchors);
  const percent = referenceApi.normalizeToPercent(plotted, anchors);

  assert.ok(Math.abs(plotted.cost - 14.4) < 1e-9);
  assert.ok(Math.abs(plotted.coverage - 104.4) < 1e-9);
  assert.ok(Math.abs(percent.cost - 110) < 1e-6);
  assert.ok(Math.abs(percent.coverage - 110) < 1e-6);

  const flat = hypervolumeApi.objectiveReferencePoint({
    utopian: { cost: 2, coverage: 3 },
    antiutopian: { cost: 2, coverage: 8 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  });
  assert.equal(flat.cost, null);
  assert.ok(Math.abs(flat.coverage - 8.5) < 1e-9);
});

test('spread delta is zero on a uniform front and larger when points cluster', () => {
  const extremes = { f1: { f1: 0, f2: 1 }, f2: { f1: 1, f2: 0 } };
  const uniform = hypervolumeApi.spreadDelta([
    { f1: 0, f2: 1 },
    { f1: 0.5, f2: 0.5 },
    { f1: 1, f2: 0 },
  ], extremes);
  const concentrated = hypervolumeApi.spreadDelta([
    { f1: 0, f2: 1 },
    { f1: 0.1, f2: 0.9 },
    { f1: 1, f2: 0 },
  ], extremes);

  assert.ok(Math.abs(uniform) < 1e-9);
  assert.ok(Math.abs(concentrated - 0.8) < 1e-9);
  assert.equal(hypervolumeApi.spreadDelta([{ f1: 0, f2: 1 }], extremes), 1);
});

test('normalized spread does not inherit absolute objective scales', () => {
  const compact = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 1, coverage: 0 },
    { round: 1, cost: 0.5, coverage: 0.5 },
    { round: 1, cost: 0, coverage: 1 },
  ], directions);
  const stretched = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 4000, coverage: 10 },
    { round: 1, cost: 2000, coverage: 12 },
    { round: 1, cost: 0, coverage: 14 },
  ], directions);

  assert.ok(Math.abs(compact.rounds[0].spread) < 1e-9);
  assert.ok(Math.abs(stretched.rounds[0].spread - compact.rounds[0].spread) < 1e-9);
});

test('the view exposes kpi text, one table row per round and the expansion control', () => {
  const summary = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 0, coverage: 4 },
    { round: 1, cost: 4, coverage: 0 },
    { round: 2, cost: 1, coverage: 3 },
    { round: 2, cost: 3, coverage: 1 },
  ], directions);
  const view = hypervolumeApi.hypervolumeView(summary);
  const roundFilter = require(path.join(__dirname, '../../frontend/mockups/round_filter.js'));

  assert.equal(view.mean, '0.34');
  assert.deepEqual(view.columns.map((column) => column.label), [
    'Rodada',
    'Hipervolume',
    'Soluções na fronteira candidata',
    'Distância do hipervolume à média',
    'Espalhamento Δ',
  ]);
  assert.equal(view.rows.length, 2);
  assert.equal(view.rows[0].round, 1);
  assert.equal(view.rows[0].hypervolume, '0.21');
  assert.equal(view.rows[0].candidateCount, '2');
  assert.equal(view.rows[0].distance, '-0.13');
  assert.equal(view.rows[0].spread, '0.00');
  assert.equal(view.rows[1].distance, '+0.13');
  assert.equal(view.rows[1].spread, '0.50');
  assert.equal(view.rows[0].hypervolume.includes('km'), false);
  assert.equal(view.meanCount, '2.00');
  assert.equal(view.spreadMean, '0.25');
  assert.equal(view.cv, `${((summary.sampleStdevHypervolume / summary.meanHypervolume) * 100).toFixed(1).replace('.', ',')}%`);
  assert.equal(view.spreadCv, `${((summary.sampleStdevSpread / summary.meanSpread) * 100).toFixed(1).replace('.', ',')}%`);
  assert.equal(view.cvUnavailable, false);
  const visibleRows = view.rows.filter((row) => roundFilter.isRoundVisible(row.round, new Set([2])));
  assert.deepEqual(visibleRows.map((row) => row.round), [1]);
  assert.equal(view.rows.length, 2);
  assert.equal(view.spreadMean, '0.25');

  const collapsed = hypervolumeApi.chartExpansionState(false);
  const expanded = hypervolumeApi.chartExpansionState(true);
  assert.equal(collapsed.label, 'Ampliar mapa');
  assert.equal(collapsed.ariaPressed, 'false');
  assert.equal(expanded.label, 'Recolher mapa');
  assert.equal(expanded.ariaPressed, 'true');
  assert.equal(hypervolumeApi.chartExpansionState(collapsed.expanded).expanded, false);
});

test('api payload and the hypervolume preference use the map contract', () => {
  const mapped = hypervolumeApi.mapApiHypervolume({
    reference_shift: 1.1,
    unit: null,
    standard_deviation: 'sample',
    note: 'Área adimensional. Cada objetivo vai de 0 no utópico a 1 no nadir, e a referência é 1,1 vezes o nadir.',
    nadir: { time: 4, distance: 4 },
    reference_point: { time: 1.1, distance: 1.1 },
    rounds: [
      { round: 1, hypervolume: 1.64, candidate_count: 2, distance_to_mean: -2.3, spread: 0.8 },
    ],
    mean_hypervolume: 1.64,
    sample_stdev_hypervolume: 0,
    coefficient_of_variation: 0,
    mean_candidate_count: 2,
    mean_spread: 0.8,
    sample_stdev_spread: 0,
    spread_coefficient_of_variation: 0,
    spread_note: 'Δ = 0 indica distribuição uniforme.',
  });

  assert.equal(mapped.referencePoint.cost, 1.1);
  assert.equal(mapped.referencePoint.coverage, 1.1);
  assert.equal(mapped.unit, null);
  assert.equal(hypervolumeApi.hypervolumeView(mapped).rows[0].hypervolume.includes('km'), false);
  assert.equal(hypervolumeApi.hypervolumeView(mapped).rows[0].spread, '0.80');
  assert.equal(hypervolumeApi.hypervolumeView(mapped).spreadCv, '0%');
  assert.equal(mapped.rounds[0].candidateCount, 2);
  assert.equal(mapped.coefficientOfVariation, 0);
  assert.equal(hypervolumeApi.hypervolumeView(mapped).cv, '0%');
  assert.equal(hypervolumeApi.hypervolumeView(mapped).rows[0].round, 1);

  const unavailable = hypervolumeApi.mapApiHypervolume({
    reference_shift: 1.1,
    nadir: { time: 0, distance: 0 },
    reference_point: { time: 0, distance: 0 },
    rounds: [
      { round: 1, hypervolume: 0, candidate_count: 1, distance_to_mean: 0, spread: 0 },
      { round: 2, hypervolume: 0, candidate_count: 1, distance_to_mean: 0, spread: 0 },
    ],
    mean_hypervolume: 0,
    sample_stdev_hypervolume: 0,
    coefficient_of_variation: null,
    mean_candidate_count: 1,
    mean_spread: 0,
    sample_stdev_spread: 0,
    spread_coefficient_of_variation: null,
  });
  const unavailableView = hypervolumeApi.hypervolumeView(unavailable);
  assert.equal(unavailable.coefficientOfVariation, null);
  assert.equal(unavailableView.cv, 'indisponível');
  assert.equal(unavailableView.cvStatus, 'indisponível');
  assert.equal(unavailableView.spreadCv, 'indisponível');
  assert.equal(unavailableView.spreadCvUnavailable, true);

  const saved = new Map();
  const storage = {
    getItem(key) { return saved.has(key) ? saved.get(key) : null; },
    setItem(key, value) { saved.set(key, value); },
  };
  assert.equal(hypervolumeApi.readShowHypervolume(storage), false);
  hypervolumeApi.writeShowHypervolume(storage, true);
  assert.equal(saved.get(hypervolumeApi.STORAGE_KEY), '1');
  assert.equal(hypervolumeApi.STORAGE_KEY, 'paretolab.showHypervolume');
  assert.equal(hypervolumeApi.readShowHypervolume(storage), true);
  assert.equal(hypervolumeApi.REFERENCE_STORAGE_KEY, 'paretolab.showHypervolumeReference');
  assert.equal(hypervolumeApi.REFERENCE_LABEL, 'Referência do hipervolume');
  assert.equal(hypervolumeApi.readShowHypervolumeReference(storage), false);
  hypervolumeApi.writeShowHypervolumeReference(storage, true);
  assert.equal(saved.get(hypervolumeApi.REFERENCE_STORAGE_KEY), '1');
  assert.equal(hypervolumeApi.readShowHypervolumeReference(storage), true);
  assert.equal(hypervolumeApi.readShowHypervolume(storage), true);
});
