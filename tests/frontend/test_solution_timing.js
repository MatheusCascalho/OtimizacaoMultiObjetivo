const assert = require('node:assert/strict');
const fs = require('node:fs');
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

test('creating an instance does not read solutionTimingView when the module is missing', () => {
  assert.equal(timingApi.solutionTimingViewOrEmpty(undefined, null), null);
  assert.equal(timingApi.solutionTimingViewOrEmpty(null, null), null);
  assert.equal(timingApi.solutionTimingViewOrEmpty({}, null), null);
  assert.equal(timingApi.solutionTimingViewOrEmpty(timingApi, null), null);

  const appSource = fs.readFileSync(path.join(
    __dirname,
    '../../frontend/mockups/app.js',
  ), 'utf8');
  assert.doesNotMatch(appSource, /window\.SolutionTiming\.solutionTimingView/);
});

test('frontend image ships every local script the page loads', () => {
  const root = path.join(__dirname, '../../frontend/mockups');
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const dockerfile = fs.readFileSync(path.join(root, 'Dockerfile'), 'utf8');
  const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(scripts, ['frontier_series.js', 'solution_timing.js', 'reference_points.js', 'app.js']);
  scripts.forEach((script) => {
    assert.match(dockerfile, new RegExp(script.replace('.', '\\.')));
  });
});
