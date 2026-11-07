const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const robustness = require(path.join(__dirname, '../../frontend/mockups/robustness.js'));

test('the robustness action waits until the instance has mapped solutions', () => {
  assert.equal(robustness.canAnalyze({
    hasInstance: true,
    resultIsDemo: true,
    mappedCount: 4,
    runStatus: 'completed',
  }), false);
  assert.equal(robustness.canAnalyze({
    hasInstance: true,
    resultIsDemo: false,
    mappedCount: 0,
    runStatus: 'completed',
  }), false);
  assert.equal(robustness.canAnalyze({
    hasInstance: true,
    resultIsDemo: false,
    mappedCount: 3,
    runStatus: 'running',
  }), false);
  assert.equal(robustness.canAnalyze({
    hasInstance: false,
    resultIsDemo: false,
    mappedCount: 3,
    runStatus: 'completed',
  }), false);
  assert.equal(robustness.canAnalyze({
    hasInstance: true,
    resultIsDemo: false,
    mappedCount: 3,
    runStatus: 'completed',
  }), true);
});

test('the summary table and the sensitivity note use the simulated metrics', () => {
  const report = robustness.mapReport({
    parameters: {
      scenarios: 5000,
      seed: 42,
      cv: 0.2,
      rho: 0.3,
      rho0: 0,
      convention: 'mean',
      region_method: 'kmeans_midpoint',
      region_count: 4,
    },
    note: 'As rotas não são reotimizadas.',
    warnings: ['Tempo recalculado diferente.'],
    solutions: [
      {
        solution_id: 'sol_a',
        label: 'S1',
        distance: 4,
        nominal_time: 10,
        mean: 10.1,
        coefficient_of_variation: 0.08,
        p95: 12,
        cvar: 13,
        violation_probability: null,
        win_frequency: 0.4,
        pareto_probability: 0.9,
        regret_mean: 0.5,
        regret_p95: 1.2,
        hypervolume_contribution: 1.5,
        rank_frequencies: [0.4, 0.6],
        boxplot: { min: 8, q1: 9, median: 10, q3: 11, max: 14, nominal: 10 },
        critical_arcs: [{ source: 1, target: 2, nominal_time: 3, variance_share: 0.5, correlation: 0.7 }],
      },
    ],
    dominance: [[0]],
    cloud: { times: [[10.2]] },
    sensitivity: {
      by_cv: [
        { cv: 0.05, rho: 0.3, p95: [10.4], pareto_probability: [1] },
        { cv: 0.2, rho: 0.3, p95: [12], pareto_probability: [0.9] },
      ],
      by_rho: [
        { cv: 0.2, rho: 0, p95: [11], pareto_probability: [1] },
        { cv: 0.2, rho: 0.6, p95: [12.5], pareto_probability: [0.7] },
      ],
      ranking_inversion_cv: 0.2,
      frontier_loss_cv: null,
    },
  });

  assert.ok(report);
  assert.equal(report.solutions[0].label, 'S1');
  assert.equal(report.warnings.length, 1);
  assert.deepEqual(robustness.tableRows(report)[0], [
    'S1',
    '4',
    '10',
    '10,1',
    '0,08',
    '12',
    '13',
    '—',
    '40%',
    '90%',
    '0,5',
    '1,2',
    '1,5',
  ]);
  assert.match(robustness.describeReport(report), /5\.000 cenários/);
  assert.match(robustness.describeReport(report), /média igual ao tempo nominal/);
  assert.match(robustness.inversionNote(report), /CV 0,2/);
  assert.equal(robustness.mapReport({ solutions: [] }), null);
});
