const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const referenceApi = require(path.join(__dirname, '../../frontend/mockups/reference_points.js'));
const hypervolumeApi = require(path.join(
  __dirname,
  '../../frontend/mockups/hypervolume.js',
));

const directions = { cost: 'minimize', coverage: 'minimize' };

test('hypervolume uses the normalized reference at 1.05 and ignores dominated points', () => {
  const summary = hypervolumeApi.summarizeChartSolutions([
    { id: 'a', round: 1, cost: 0, coverage: 4 },
    { id: 'b', round: 1, cost: 4, coverage: 0 },
    { id: 'c', round: 1, cost: 5, coverage: 5 },
    { id: 'd', round: 2, cost: 1, coverage: 3 },
    { id: 'e', round: 2, cost: 3, coverage: 1 },
  ], directions);

  assert.deepEqual(summary.nadir, { cost: 4, coverage: 4 });
  assert.ok(Math.abs(summary.referencePoint.cost - 1.05) < 1e-9);
  assert.ok(Math.abs(summary.referencePoint.coverage - 1.05) < 1e-9);
  assert.equal(summary.rounds[0].candidateCount, 2);
  assert.ok(Math.abs(summary.rounds[0].hypervolume - 0.1025) < 1e-9);
  assert.equal(summary.rounds[1].candidateCount, 2);
  assert.ok(Math.abs(summary.rounds[1].hypervolume - 0.39) < 1e-9);
  assert.ok(Math.abs(summary.meanHypervolume - 0.24625) < 1e-9);
  assert.ok(Math.abs(summary.sampleStdevHypervolume - Math.sqrt((0.1025 - 0.24625) ** 2 * 2)) < 1e-9);
  assert.ok(Math.abs(summary.coefficientOfVariation - (summary.sampleStdevHypervolume / summary.meanHypervolume)) < 1e-9);
  assert.equal(summary.meanCandidateCount, 2);
  assert.ok(Math.abs(summary.rounds[0].distanceToMean - (0.1025 - 0.24625)) < 1e-9);
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
  assert.ok(Math.abs(shifted.rounds[0].hypervolume - 0.1025) < 1e-9);
  assert.ok(Math.abs(shifted.referencePoint.cost - 1.05) < 1e-9);
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
  assert.ok(Math.abs(summary.referencePoint.coverage - 1.05) < 1e-9);
  assert.ok(Math.abs(summary.referencePoint.cost - 1.05) < 1e-9);
  assert.ok(Math.abs(summary.rounds[0].hypervolume - 0.1025) < 1e-9);
});

test('the drawn reference is 105 percent and a null span stays closed', () => {
  const anchors = {
    utopian: { cost: 10, coverage: 100 },
    antiutopian: { cost: 14, coverage: 104 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  };
  const plotted = hypervolumeApi.objectiveReferencePoint(anchors);
  const percent = referenceApi.normalizeToPercent(plotted, anchors);

  assert.ok(Math.abs(plotted.cost - 14.2) < 1e-9);
  assert.ok(Math.abs(plotted.coverage - 104.2) < 1e-9);
  assert.ok(Math.abs(percent.cost - 105) < 1e-6);
  assert.ok(Math.abs(percent.coverage - 105) < 1e-6);

  const flat = hypervolumeApi.objectiveReferencePoint({
    utopian: { cost: 2, coverage: 3 },
    antiutopian: { cost: 2, coverage: 8 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  });
  assert.equal(flat.cost, null);
  assert.ok(Math.abs(flat.coverage - 8.25) < 1e-9);
});

test('the view exposes kpi text, one card per round and the expansion control', () => {
  const summary = hypervolumeApi.summarizeChartSolutions([
    { round: 1, cost: 0, coverage: 4 },
    { round: 1, cost: 4, coverage: 0 },
    { round: 2, cost: 1, coverage: 3 },
    { round: 2, cost: 3, coverage: 1 },
  ], directions);
  const view = hypervolumeApi.hypervolumeView(summary);

  assert.equal(view.mean, '0.25');
  assert.equal(view.cards.length, 2);
  assert.equal(view.cards[0].title, 'Rodada 1');
  assert.equal(view.cards[0].hypervolume, '0.10');
  assert.equal(view.cards[0].candidateCount, '2 soluções na fronteira candidata');
  assert.equal(view.cards[0].distance, '-0.14');
  assert.equal(view.cards[1].distance, '+0.14');
  assert.equal(view.cards[0].hypervolume.includes('km'), false);
  assert.equal(view.meanCount, '2.00');
  assert.equal(view.cv, `${((summary.sampleStdevHypervolume / summary.meanHypervolume) * 100).toFixed(1).replace('.', ',')}%`);
  assert.equal(view.cvUnavailable, false);

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
    reference_shift: 0.05,
    unit: null,
    standard_deviation: 'sample',
    note: 'Área adimensional. Cada objetivo vai de 0 no utópico a 1 no nadir, e a referência é 1,05.',
    nadir: { time: 4, distance: 4 },
    reference_point: { time: 1.05, distance: 1.05 },
    rounds: [
      { round: 1, hypervolume: 1.64, candidate_count: 2, distance_to_mean: -2.3 },
    ],
    mean_hypervolume: 1.64,
    sample_stdev_hypervolume: 0,
    coefficient_of_variation: 0,
    mean_candidate_count: 2,
  });

  assert.equal(mapped.referencePoint.cost, 1.05);
  assert.equal(mapped.referencePoint.coverage, 1.05);
  assert.equal(mapped.unit, null);
  assert.equal(hypervolumeApi.hypervolumeView(mapped).cards[0].hypervolume.includes('km'), false);
  assert.equal(mapped.rounds[0].candidateCount, 2);
  assert.equal(mapped.coefficientOfVariation, 0);
  assert.equal(hypervolumeApi.hypervolumeView(mapped).cv, '0%');
  assert.equal(hypervolumeApi.hypervolumeView(mapped).cards[0].title, 'Rodada 1');

  const unavailable = hypervolumeApi.mapApiHypervolume({
    reference_shift: 0.05,
    nadir: { time: 0, distance: 0 },
    reference_point: { time: 0, distance: 0 },
    rounds: [
      { round: 1, hypervolume: 0, candidate_count: 1, distance_to_mean: 0 },
    ],
    mean_hypervolume: 0,
    sample_stdev_hypervolume: 0,
    coefficient_of_variation: null,
    mean_candidate_count: 1,
  });
  const unavailableView = hypervolumeApi.hypervolumeView(unavailable);
  assert.equal(unavailable.coefficientOfVariation, null);
  assert.equal(unavailableView.cv, 'indisponível');
  assert.equal(unavailableView.cvStatus, 'indisponível');

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
});
