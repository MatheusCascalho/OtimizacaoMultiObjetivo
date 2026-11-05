const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const seriesApi = require(path.join(
  __dirname,
  '../../frontend/mockups/frontier_series.js',
));

function point(round, cost, coverage) {
  return {
    id: `sol-${round}-${cost}`,
    cost,
    coverage,
    frontier: true,
    round,
  };
}

test('chart receives five frontier series with distinct colors and labels', () => {
  const solutions = [];
  for (let round = 1; round <= 5; round += 1) {
    solutions.push(point(round, 10 + round, 30 - round));
    solutions.push(point(round, 20 + round, 40 - round));
    solutions.push({ ...point(round, 5, 5), id: `dominated-${round}`, frontier: false });
  }

  const series = seriesApi.frontierSeriesFromSolutions(solutions);

  assert.equal(seriesApi.FRONTIER_REPETITIONS, 5);
  assert.equal(series.length, 5);
  assert.deepEqual(series.map((item) => item.label), [
    'Rodada 1',
    'Rodada 2',
    'Rodada 3',
    'Rodada 4',
    'Rodada 5',
  ]);
  assert.equal(new Set(series.map((item) => item.color)).size, 5);
  series.forEach((item) => {
    assert.equal(item.points.length, 2);
    assert.ok(item.points.every((candidate) => candidate.round === item.round && candidate.frontier));
  });
});

test('chart strokes each frontier with its own color and dash pattern', () => {
  const solutions = [1, 2, 3, 4, 5].map((round) => point(round, round, 10 - round));
  const series = seriesApi.frontierSeriesFromSolutions(solutions);
  const painted = [];
  const context = {
    beginPath() {},
    moveTo() {},
    lineTo() {},
    setLineDash(dash) {
      this.dash = dash.slice();
    },
    stroke() {
      painted.push({ color: this.strokeStyle, dash: this.dash.slice() });
    },
  };

  const result = seriesApi.strokeFrontierSeries(context, series, (candidate) => ({
    x: candidate.cost,
    y: candidate.coverage,
  }));

  assert.equal(result.length, 5);
  assert.deepEqual(painted.map((item) => item.color), series.map((item) => item.color));
  assert.deepEqual(painted.map((item) => item.dash), series.map((item) => item.dash));
  assert.equal(new Set(painted.map((item) => item.color)).size, 5);
  assert.equal(context.dash.length, 0);
});
