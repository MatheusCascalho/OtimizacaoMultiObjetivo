const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const referenceApi = require(path.join(
  __dirname,
  '../../frontend/mockups/reference_points.js',
));

test('sampled extremes match the utopian and nadir of the numeric example', () => {
  const points = referenceApi.estimateFromChartSolutions([
    { cost: 0, coverage: 4, frontier: true },
    { cost: 4, coverage: 0, frontier: true },
  ]);

  assert.equal(points.utopian.label, 'Solução utópica');
  assert.equal(points.antiutopian.label, 'Solução antiutópica');
  assert.deepEqual(
    { cost: points.utopian.cost, coverage: points.utopian.coverage },
    { cost: 0, coverage: 0 },
  );
  assert.deepEqual(
    { cost: points.antiutopian.cost, coverage: points.antiutopian.coverage },
    { cost: 4, coverage: 4 },
  );
});

test('an alternative optimum does not inflate the antiutopian point', () => {
  const points = referenceApi.estimateFromChartSolutions([
    { cost: 0, coverage: 5, frontier: false },
    { cost: 0, coverage: 1, frontier: true },
    { cost: 3, coverage: 0, frontier: true },
  ]);

  assert.equal(points.antiutopian.cost, 3);
  assert.equal(points.antiutopian.coverage, 1);
  assert.equal(points.utopian.cost, 0);
  assert.equal(points.utopian.coverage, 0);
});

test('non conflicting sample warns and keeps the two points together', () => {
  const points = referenceApi.estimateFromChartSolutions([{ cost: 2, coverage: 3, frontier: true }]);

  assert.equal(points.warnings[0].code, 'non_conflicting_objectives');
  assert.equal(points.utopian.cost, points.antiutopian.cost);
  assert.equal(points.utopian.coverage, points.antiutopian.coverage);
});

test('api payload keeps objective coordinates used by the decision map', () => {
  const points = referenceApi.mapApiReferencePoints({
    method: 'approximate_front',
    note: 'Estimativa a partir das soluções mapeadas.',
    utopian: { label: 'Solução utópica', objective_values: { time: 1.5, distance: 2.5 } },
    antiutopian: { label: 'Solução antiutópica', objective_values: { time: 4, distance: 8 } },
    distance: { label: 'Distância euclidiana', note: 'No espaço dos objetivos, sem normalizar' },
    warnings: [],
  });

  assert.equal(points.utopian.cost, 2.5);
  assert.equal(points.utopian.coverage, 1.5);
  assert.equal(points.antiutopian.cost, 8);
  assert.equal(points.antiutopian.coverage, 4);
  assert.equal(points.distanceLabel, 'Distância euclidiana');
});

test('distance to a frontier solution is euclidean and ignores dominated solutions', () => {
  const points = {
    utopian: { cost: 0, coverage: 0 },
    antiutopian: { cost: 6, coverage: 8 },
  };
  const frontier = referenceApi.measureReferenceDistances({ cost: 3, coverage: 4, frontier: true }, points);
  const dominated = referenceApi.measureReferenceDistances({ cost: 3, coverage: 4, frontier: false }, points);

  assert.equal(frontier.eligible, true);
  assert.equal(frontier.toUtopian, 5);
  assert.equal(referenceApi.formatObjectiveDistance(frontier.toUtopian), '5.00');
  assert.equal(frontier.toAntiutopian, 5);
  assert.equal(dominated.eligible, false);
  assert.equal(referenceApi.measureReferenceDistances(null, points).eligible, false);
});

test('reference point visibility is stored with the other map preferences', () => {
  const saved = new Map();
  const storage = {
    getItem(key) { return saved.has(key) ? saved.get(key) : null; },
    setItem(key, value) { saved.set(key, value); },
  };

  assert.equal(referenceApi.readShowReferencePoints(storage), true);
  referenceApi.writeShowReferencePoints(storage, false);
  assert.equal(saved.get(referenceApi.STORAGE_KEY), '0');
  assert.equal(referenceApi.readShowReferencePoints(storage), false);
  referenceApi.writeShowReferencePoints(storage, true);
  assert.equal(referenceApi.readShowReferencePoints(storage), true);
});
