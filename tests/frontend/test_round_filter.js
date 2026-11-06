const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const roundFilter = require(path.join(__dirname, '../../frontend/mockups/round_filter.js'));
const referenceApi = require(path.join(__dirname, '../../frontend/mockups/reference_points.js'));

const solutions = [
  { id: 'a', round: 1, cost: 1, coverage: 4, frontier: true },
  { id: 'b', round: 1, cost: 4, coverage: 5, frontier: false },
  { id: 'c', round: 2, cost: 0, coverage: 0, frontier: true },
  { id: 'd', round: 2, cost: 3, coverage: 1, frontier: true },
];

test('hiding a round removes its points from the chart and table source', () => {
  const hidden = new Set([2]);
  const visible = roundFilter.filterSolutions(solutions, hidden);

  assert.deepEqual(visible.map((item) => item.id), ['a', 'b']);
  assert.equal(visible.some((item) => item.round === 2), false);
});

test('showing all rounds restores every point', () => {
  const hidden = new Set([1, 2]);
  const restored = roundFilter.filterSolutions(solutions, roundFilter.showAllRounds());
  const afterClear = roundFilter.filterSolutions(solutions, hidden);

  hidden.clear();
  assert.deepEqual(restored.map((item) => item.id), ['a', 'b', 'c', 'd']);
  assert.deepEqual(roundFilter.filterSolutions(solutions, hidden).map((item) => item.id), ['a', 'b', 'c', 'd']);
  assert.deepEqual(afterClear.map((item) => item.id), []);
});

test('a hidden round is omitted from the hypervolume areas and cards', () => {
  const rounds = [
    { round: 1, hypervolume: 1.64, points: [{ id: 'a', cost: 1, coverage: 4 }] },
    { round: 2, hypervolume: 6.24, points: [{ id: 'c', cost: 0, coverage: 0 }] },
  ];
  const visible = roundFilter.filterHypervolumeRounds(rounds, new Set([2]));

  assert.deepEqual(visible.map((item) => item.round), [1]);
  assert.equal(visible.some((item) => item.points.some((point) => point.id === 'c')), false);
  assert.equal(rounds[1].hypervolume, 6.24);
});

test('approximate frontier ignores points from hidden rounds', () => {
  const visibleUnion = roundFilter.filterSolutions(solutions, new Set([2]));
  const front = referenceApi.classifyApproximateFrontier(visibleUnion, {
    cost: 'minimize',
    coverage: 'minimize',
  });

  assert.deepEqual(visibleUnion.map((item) => item.id), ['a', 'b']);
  assert.equal(visibleUnion.some((item) => item.id === 'c'), false);
  assert.deepEqual(front.frontier.map((item) => item.id), ['a']);
  assert.deepEqual(
    referenceApi.classifyApproximateFrontier(solutions, { cost: 'minimize', coverage: 'minimize' }).frontier.map((item) => item.id),
    ['c'],
  );
});
