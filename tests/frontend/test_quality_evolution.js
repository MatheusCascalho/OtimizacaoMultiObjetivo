const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const path = require('node:path');

const evolutionApi = require(path.join(
  __dirname,
  '../../frontend/mockups/quality_evolution.js',
));

function payload() {
  return {
    instance_id: 'inst_1',
    axis: 'iteration',
    axis_label: 'Iterações',
    hypervolume: {
      curves: [
        {
          algorithm_id: 'random-heuristic',
          label: 'RandomHeuristic',
          points: [
            { iteration: 1, mean: 0.2 },
            { iteration: 2, mean: 0.4 },
          ],
        },
        {
          algorithm_id: 'weighted-sum',
          label: 'Soma ponderada',
          points: [
            { iteration: 1, mean: 0.5 },
            { iteration: 2, mean: 0.7 },
          ],
        },
      ],
    },
    spread: {
      curves: [
        {
          algorithm_id: 'random-heuristic',
          label: 'RandomHeuristic',
          points: [
            { iteration: 1, mean: 0.1 },
            { iteration: 2, mean: 0.2 },
          ],
        },
        {
          algorithm_id: 'weighted-sum',
          label: 'Soma ponderada',
          points: [
            { iteration: 1, mean: 0.3 },
            { iteration: 2, mean: 0.4 },
          ],
        },
      ],
    },
  };
}

function mockContext() {
  const dashes = [];
  const context = {
    dash: [],
    setLineDash(dash) {
      this.dash = dash.slice();
      dashes.push(dash.slice());
    },
    beginPath() {},
    moveTo() {},
    lineTo() {},
    closePath() {},
    arc() {},
    rect() {},
    stroke() {},
    fill() {},
    clearRect() {},
    fillText() {},
    save() {},
    restore() {},
  };
  context.dashes = dashes;
  return context;
}

test('frontend builds two figures with two overlaid curves', () => {
  const figures = evolutionApi.qualityEvolutionFigures(
    evolutionApi.mapApiQualityEvolution(payload()),
  );

  assert.equal(figures.length, 2);
  assert.equal(figures[0].title, 'Evolução do hipervolume');
  assert.equal(figures[1].title, 'Evolução do espalhamento Δ');
  assert.equal(figures[0].xLabel, 'Iterações');
  assert.equal(figures[0].yLabel, 'Média do hipervolume');
  assert.equal(figures[1].yLabel, 'Média do espalhamento Δ');
  assert.equal(figures[0].empty, false);
  assert.equal(figures[0].curves.length, 2);
  assert.equal(figures[1].curves.length, 2);
  assert.deepEqual(figures[0].curves.map((curve) => curve.label), [
    'RandomHeuristic',
    'Soma ponderada',
  ]);
  assert.notDeepEqual(figures[0].curves[0].dash, figures[0].curves[1].dash);
  assert.notEqual(figures[0].curves[0].marker, figures[0].curves[1].marker);
  assert.notEqual(figures[0].curves[0].color, figures[0].curves[1].color);

  const legend = evolutionApi.legendEntries(figures[0]);
  assert.equal(legend.length, 2);
  assert.notEqual(legend[0].dashLabel, legend[1].dashLabel);
  assert.notEqual(legend[0].markerLabel, legend[1].markerLabel);
  assert.match(evolutionApi.figureDescription(figures[0]), /linha contínua/);
  assert.match(evolutionApi.figureDescription(figures[0]), /linha tracejada/);

  const context = mockContext();
  const painted = evolutionApi.drawFigure(context, figures[0], 320, 180);
  assert.equal(painted.length, 2);
  assert.deepEqual(painted.map((item) => item.dash), figures[0].curves.map((curve) => curve.dash));
  assert.deepEqual(painted.map((item) => item.marker), figures[0].curves.map((curve) => curve.marker));
  assert.ok(context.dashes.some((dash) => dash.length === 0));
  assert.ok(context.dashes.some((dash) => dash.length > 0));
});

test('a single algorithm still produces both figures', () => {
  const source = payload();
  source.hypervolume.curves = source.hypervolume.curves.slice(0, 1);
  source.spread.curves = source.spread.curves.slice(0, 1);
  const figures = evolutionApi.qualityEvolutionFigures(
    evolutionApi.mapApiQualityEvolution(source),
  );

  assert.equal(figures[0].curves.length, 1);
  assert.equal(figures[1].curves.length, 1);
  assert.equal(figures[0].curves[0].label, 'RandomHeuristic');
  assert.equal(figures[0].curves[0].marker, 'circle');
});

test('empty evolution explains that no non-exact execution is available', () => {
  const figures = evolutionApi.qualityEvolutionFigures(evolutionApi.mapApiQualityEvolution({
    axis: 'iteration',
    axis_label: 'Iterações',
    hypervolume: { curves: [] },
    spread: { curves: [] },
  }));

  assert.equal(figures[0].empty, true);
  assert.equal(figures[1].empty, true);
  assert.match(figures[0].emptyMessage, /não exata/);
  assert.match(figures[1].title, /espalhamento Δ/);
  assert.equal(evolutionApi.drawFigure(mockContext(), figures[0], 320, 180).length, 0);
});

test('evaluations become the horizontal axis when the payload says so', () => {
  const mapped = evolutionApi.mapApiQualityEvolution({
    axis: 'evaluations',
    axis_label: 'Avaliações',
    hypervolume: {
      curves: [
        { algorithm_id: 'a', label: 'Heurística A', points: [{ evaluations: 30, mean: 0.2 }] },
      ],
    },
    spread: {
      curves: [
        { algorithm_id: 'a', label: 'Heurística A', points: [{ evaluations: 30, mean: 0.4 }] },
      ],
    },
  });
  const figures = evolutionApi.qualityEvolutionFigures(mapped);

  assert.equal(figures[0].xLabel, 'Avaliações');
  assert.equal(figures[0].curves[0].points[0].x, 30);
  assert.equal(figures[1].curves[0].points[0].mean, 0.4);
});

test('the served dashboard includes the evolution script', () => {
  const root = path.join(__dirname, '../..');
  const html = fs.readFileSync(path.join(root, 'frontend/mockups/index.html'), 'utf8');
  const dockerfile = fs.readFileSync(path.join(root, 'frontend/mockups/Dockerfile'), 'utf8');
  const devCompose = fs.readFileSync(path.join(root, 'compose-dev.yaml'), 'utf8');

  assert.match(html, /<script src="quality_evolution\.js"/);
  assert.match(dockerfile, /quality_evolution\.js/);
  assert.match(devCompose, /quality_evolution\.js:\/usr\/share\/nginx\/html\/quality_evolution\.js/);

  const figures = evolutionApi.qualityEvolutionFigures(evolutionApi.mapApiQualityEvolution(payload()));
  assert.equal(figures.length, 2);
  assert.ok(figures.every((figure) => figure.curves.some((curve) => curve.points.length >= 2)));
  assert.equal(figures[0].empty, false);
  assert.equal(figures[1].empty, false);
});
