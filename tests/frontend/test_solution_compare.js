const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const compare = require(path.join(
  __dirname,
  '../../frontend/mockups/solution_compare.js',
));

test('ctrl selection toggles a solution and keeps the earlier order', () => {
  const first = compare.toggleComparedId([], '018');
  const second = compare.toggleComparedId(first, '006');
  const removed = compare.toggleComparedId(second, '018');

  assert.deepEqual(first, ['018']);
  assert.deepEqual(second, ['018', '006']);
  assert.deepEqual(removed, ['006']);
  assert.deepEqual(first, ['018']);
});

test('each compared solution gets its own color and stroke', () => {
  const first = compare.comparisonStyle(0);
  const second = compare.comparisonStyle(1);

  assert.notEqual(first.color, second.color);
  assert.notEqual(first.patternLabel, second.patternLabel);
  assert.deepEqual(first.dash, []);
  assert.ok(second.dash.length > 0);
});

test('coincident edges are shifted perpendicular to the segment', () => {
  const shifted = compare.offsetSegment({ x: 0, y: 0 }, { x: 10, y: 0 }, 4);

  assert.equal(shifted.source.y, 4);
  assert.equal(shifted.target.y, 4);
  assert.equal(shifted.source.x, 0);
  assert.equal(shifted.target.x, 10);
});

test('edge hover hits the nearest segment inside the limit', () => {
  const edges = [
    { id: 'far', source: { x: 0, y: 0 }, target: { x: 10, y: 0 } },
    { id: 'near', source: { x: 0, y: 5 }, target: { x: 10, y: 5 } },
  ];

  const hit = compare.nearestEdge({ x: 4, y: 6 }, edges, 8);
  const miss = compare.nearestEdge({ x: 4, y: 30 }, edges, 8);

  assert.equal(hit.edge.id, 'near');
  assert.equal(miss.edge, null);
});

test('illustrative routes are closed cycles with distinct arcs and totals', () => {
  const first = compare.illustrativeGraph({ id: '018', cost: 18.4, coverage: 82.6 });
  const second = compare.illustrativeGraph({ id: '006', cost: 11.4, coverage: 65.8 });
  const visited = new Set(first.route.slice(0, -1));
  const distance = first.edges.reduce((sum, edge) => sum + edge.distance, 0);
  const time = first.edges.reduce((sum, edge) => sum + edge.time, 0);
  const key = (graph) => graph.edges.map((edge) => `${edge.source}-${edge.target}`).join('|');

  assert.equal(first.illustrative, true);
  assert.equal(first.route[0], first.route[first.route.length - 1]);
  assert.equal(visited.size, first.nodes.length);
  assert.ok(Math.abs(distance - 18.4) < 1e-9);
  assert.ok(Math.abs(time - 82.6) < 1e-9);
  assert.notEqual(key(first), key(second));
  assert.equal(compare.formatObjective(first.edges[0].time, 'h').endsWith(' h'), true);
});

test('matrix lookup reads the arc by city id', () => {
  const payload = { matrix: [[0, 1.25], [4.5, 0]] };

  assert.equal(compare.matrixValue(payload, 1, 2), 1.25);
  assert.equal(compare.matrixValue(payload, 2, 1), 4.5);
  assert.equal(compare.matrixValue(payload, 3, 1), null);
  assert.equal(compare.formatObjective(undefined, 'km'), 'indisponível');
});
