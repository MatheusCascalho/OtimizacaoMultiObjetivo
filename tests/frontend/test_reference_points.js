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
    distance: {
      label: 'Distância euclidiana normalizada',
      note: 'Cada objetivo vai de 0 no utópico a 1 no nadir.',
    },
    warnings: [],
  });

  assert.equal(points.utopian.cost, 2.5);
  assert.equal(points.utopian.coverage, 1.5);
  assert.equal(points.antiutopian.cost, 8);
  assert.equal(points.antiutopian.coverage, 4);
  assert.equal(points.distanceLabel, 'Distância euclidiana normalizada');
  assert.equal(points.distanceNote, 'Cada objetivo vai de 0 no utópico a 1 no nadir.');
});

test('distance to a frontier solution is normalized euclidean and ignores dominated solutions', () => {
  const points = {
    utopian: { cost: 0, coverage: 0 },
    antiutopian: { cost: 6, coverage: 8 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  };
  const frontier = referenceApi.measureReferenceDistances({ cost: 3, coverage: 4, frontier: true }, points);
  const dominated = referenceApi.measureReferenceDistances({ cost: 3, coverage: 4, frontier: false }, points);
  const expected = Math.hypot(0.5, 0.5);

  assert.equal(frontier.eligible, true);
  assert.ok(Math.abs(frontier.toUtopian - expected) < 1e-12);
  assert.equal(referenceApi.formatObjectiveDistance(frontier.toUtopian), expected.toFixed(2));
  assert.ok(Math.abs(frontier.toAntiutopian - expected) < 1e-12);
  assert.notEqual(frontier.toUtopian, 5);
  assert.equal(dominated.eligible, false);
  assert.equal(referenceApi.measureReferenceDistances(null, points).eligible, false);

  const flat = {
    utopian: { cost: 2, coverage: 3 },
    antiutopian: { cost: 2, coverage: 3 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  };
  assert.equal(
    referenceApi.measureReferenceDistances({ cost: 9, coverage: 9, frontier: true }, flat).toUtopian,
    0,
  );

  const maximized = {
    utopian: { cost: 10, coverage: 0 },
    antiutopian: { cost: 4, coverage: 4 },
    directions: { cost: 'maximize', coverage: 'minimize' },
  };
  assert.ok(Math.abs(
    referenceApi.measureReferenceDistances({ cost: 7, coverage: 2, frontier: true }, maximized).toUtopian - expected,
  ) < 1e-12);
});

test('normalization places the utopian point at 0% and the nadir at 100%', () => {
  const reference = {
    utopian: { cost: 0, coverage: 0 },
    antiutopian: { cost: 4, coverage: 4 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  };

  assert.deepEqual(referenceApi.normalizeToPercent(reference.utopian, reference), { cost: 0, coverage: 0 });
  assert.deepEqual(referenceApi.normalizeToPercent(reference.antiutopian, reference), { cost: 100, coverage: 100 });
  assert.deepEqual(referenceApi.normalizeToPercent({ cost: 1, coverage: 1 }, reference), { cost: 25, coverage: 25 });
});

test('a null objective range normalizes to 0 and maximization keeps 0 at the best value', () => {
  const flat = {
    utopian: { cost: 2, coverage: 3 },
    antiutopian: { cost: 2, coverage: 8 },
    directions: { cost: 'minimize', coverage: 'minimize' },
  };
  assert.equal(referenceApi.normalizeToPercent({ cost: 9, coverage: 3 }, flat).cost, 0);
  assert.equal(referenceApi.normalizeToPercent({ cost: 2, coverage: 3 }, flat).coverage, 0);
  assert.equal(referenceApi.normalizeToPercent({ cost: 2, coverage: 8 }, flat).coverage, 100);

  const maximized = {
    utopian: { cost: 10, coverage: 0 },
    antiutopian: { cost: 4, coverage: 4 },
    directions: { cost: 'maximize', coverage: 'minimize' },
  };
  assert.deepEqual(referenceApi.normalizeToPercent(maximized.utopian, maximized), { cost: 0, coverage: 0 });
  assert.deepEqual(referenceApi.normalizeToPercent(maximized.antiutopian, maximized), { cost: 100, coverage: 100 });
  assert.equal(referenceApi.normalizeToPercent({ cost: 7, coverage: 2 }, maximized).cost, 50);
});

test('the dominance cone hides only solutions strictly inside it', () => {
  const anchor = { id: 'anchor', cost: 2, coverage: 2 };
  const reference = { directions: { cost: 'minimize', coverage: 'minimize' } };
  const solutions = [
    anchor,
    { id: 'interior', cost: 3, coverage: 4 },
    { id: 'boundary', cost: 2, coverage: 5 },
    { id: 'outside', cost: 1, coverage: 9 },
  ];

  assert.equal(referenceApi.coneRelation(solutions[1], anchor, reference, false), 'strict-interior');
  assert.equal(referenceApi.coneRelation(solutions[2], anchor, reference, false), 'boundary');
  assert.equal(referenceApi.coneRelation(anchor, anchor, reference, false), 'boundary');
  assert.equal(referenceApi.coneRelation(solutions[3], anchor, reference, false), 'outside');
  assert.deepEqual(
    referenceApi.visibleUnderCone(solutions, null, reference, false).map((item) => item.id),
    ['anchor', 'interior', 'boundary', 'outside'],
  );
  assert.deepEqual(
    referenceApi.visibleUnderCone(solutions, anchor, reference, false).map((item) => item.id),
    ['anchor', 'boundary', 'outside'],
  );

  const maximized = { directions: { cost: 'maximize', coverage: 'minimize' } };
  const qualityAnchor = { id: 'quality', cost: 5, coverage: 2 };
  assert.equal(
    referenceApi.coneRelation({ cost: 3, coverage: 4 }, qualityAnchor, maximized, false),
    'strict-interior',
  );
  assert.equal(
    referenceApi.coneRelation({ cost: 5, coverage: 4 }, qualityAnchor, maximized, false),
    'boundary',
  );
});

test('approximate frontier keeps the non-dominated union of every round', () => {
  const solutions = [
    { id: 'a', cost: 1, coverage: 4, round: 1, frontier: true },
    { id: 'b', cost: 3, coverage: 1, round: 1, frontier: true },
    { id: 'c', cost: 4, coverage: 5, round: 1, frontier: false },
    { id: 'd', cost: 2, coverage: 2, round: 2, frontier: true },
    { id: 'e', cost: 2.5, coverage: 3, round: 2, frontier: true },
  ];

  const classified = referenceApi.classifyApproximateFrontier(solutions, { cost: 'minimize', coverage: 'minimize' });

  assert.deepEqual(classified.frontier.map((item) => item.id), ['a', 'b', 'd']);
  assert.deepEqual(classified.dominated.map((item) => item.id), ['c', 'e']);
  assert.equal(classified.frontier.length + classified.dominated.length, solutions.length);
});

test('normalization, cone and approximate frontier combine', () => {
  const directions = { cost: 'minimize', coverage: 'minimize' };
  const reference = {
    utopian: { cost: 0, coverage: 0 },
    antiutopian: { cost: 4, coverage: 5 },
    directions,
  };
  const solutions = [
    { id: 'a', cost: 1, coverage: 4, round: 1, frontier: true },
    { id: 'b', cost: 3, coverage: 1, round: 1, frontier: true },
    { id: 'c', cost: 4, coverage: 5, round: 1, frontier: false },
    { id: 'd', cost: 2, coverage: 2, round: 2, frontier: true },
    { id: 'e', cost: 2.5, coverage: 3, round: 2, frontier: true },
  ];
  const front = referenceApi.approximateFrontier(solutions, directions);
  const anchor = front.find((item) => item.id === 'b');

  assert.deepEqual(referenceApi.normalizeToPercent(reference.utopian, reference), { cost: 0, coverage: 0 });
  assert.deepEqual(referenceApi.normalizeToPercent(reference.antiutopian, reference), { cost: 100, coverage: 100 });
  assert.deepEqual(
    referenceApi.visibleUnderCone(solutions, anchor, reference, true).map((item) => item.id),
    ['a', 'b', 'd', 'e'],
  );
  assert.deepEqual(
    referenceApi.visibleUnderCone(front, anchor, reference, true).map((item) => item.id),
    ['a', 'b', 'd'],
  );
  assert.ok(front.every((item) => {
    const percent = referenceApi.normalizeToPercent(item, reference);
    return percent.cost >= 0 && percent.cost <= 100 && percent.coverage >= 0 && percent.coverage <= 100;
  }));
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
  assert.equal(referenceApi.readPreference(storage, referenceApi.NORMALIZE_KEY, false), false);
  referenceApi.writePreference(storage, referenceApi.NORMALIZE_KEY, true);
  referenceApi.writePreference(storage, referenceApi.CONE_KEY, true);
  referenceApi.writePreference(storage, referenceApi.APPROXIMATE_FRONTIER_KEY, false);
  assert.equal(referenceApi.readPreference(storage, referenceApi.NORMALIZE_KEY, false), true);
  assert.equal(referenceApi.readPreference(storage, referenceApi.CONE_KEY, false), true);
  assert.equal(referenceApi.readPreference(storage, referenceApi.APPROXIMATE_FRONTIER_KEY, true), false);
});
