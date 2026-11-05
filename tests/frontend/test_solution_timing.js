const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const timingApi = require(path.join(
  __dirname,
  '../../frontend/mockups/solution_timing.js',
));

test('formats search durations and identifies the extreme attempts', () => {
  const view = timingApi.solutionTimingView({
    unit: 'ms',
    count: 3,
    mean_ms: 20,
    sample_stdev_ms: 10,
    slowest: { round: 2, attempt: 1, duration_ms: 1250 },
    fastest: { round: 1, attempt: 4, duration_ms: 8.5 },
  });

  assert.equal(view.mean, '20.0 ms');
  assert.equal(view.stdev, '10.0 ms');
  assert.equal(view.slowest, '1.25 s');
  assert.equal(view.slowestDetail, 'Rodada 2 · tentativa 1');
  assert.equal(view.fastest, '8.50 ms');
  assert.equal(view.fastestDetail, 'Rodada 1 · tentativa 4');
});

test('missing timing stays empty', () => {
  assert.equal(timingApi.solutionTimingView(null), null);
  assert.equal(timingApi.formatSolutionDuration(0), '0.00 ms');
});
