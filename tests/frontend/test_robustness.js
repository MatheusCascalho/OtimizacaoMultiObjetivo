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
        minmax_regret: 0.071,
        minmax_regret_p95: 0.094,
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
  }, {
    sol_a: { co2_kg: 12.345, total_speed_emission_factor: 1.23456 },
  });

  assert.ok(report);
  assert.equal(report.solutions[0].name, 'SOL-sol_a');
  assert.equal(report.warnings.length, 1);
  assert.deepEqual(robustness.tableRows(report)[0], [
    'SOL-sol_a',
    '4',
    '12,35',
    '1,235',
    '10',
    '10,1',
    '0,08',
    '90%',
    '0,5',
    '1,5',
    '7,1% · 9,4%',
  ]);
  assert.match(robustness.minmaxNote(report), /SOL-sol_a \(7,1%\)/);
  assert.match(robustness.minmaxNote(report), /P95: SOL-sol_a \(9,4%\)/);
  assert.match(robustness.describeReport(report), /5\.000 cenários/);
  assert.match(robustness.describeReport(report), /média igual ao tempo nominal/);
  assert.match(robustness.inversionNote(report), /CV 0,2/);
  assert.equal(robustness.mapReport({ solutions: [] }), null);
});

test('the metrics table filters by the solution name and sorts by a column', () => {
  const report = robustness.mapReport({
    solutions: [
      solution('sol_far', 8, 6, 0.1, 0.2),
      solution('sol_near', 4, 10, 0.071, 0.094),
    ],
    dominance: [[0, 0], [0, 0]],
  }, {
    sol_far: { co2_kg: 25, total_speed_emission_factor: 1.4 },
    sol_near: { co2_kg: 20, total_speed_emission_factor: 1.2 },
  });

  const byDistance = robustness.viewSolutions(report, { sort: { column: 'distance', direction: 'asc' } });
  assert.deepEqual(byDistance.map((item) => item.name), ['SOL-sol_near', 'SOL-sol_far']);
  const byRegret = robustness.tableRows(report, { sort: { column: 'minmax', direction: 'asc' } });
  assert.equal(byRegret[0][0], 'SOL-sol_near');
  assert.equal(byRegret[0][10], '7,1% · 9,4%');
  const byEmissions = robustness.viewSolutions(report, {
    sort: { column: 'co2Kg', direction: 'asc' },
  });
  assert.deepEqual(byEmissions.map((item) => item.name), ['SOL-sol_near', 'SOL-sol_far']);
  const filtered = robustness.tableRows(report, { query: 'sol_far' });
  assert.deepEqual(filtered.map((row) => row[0]), ['SOL-sol_far']);
});

function solution(id, distance, mean, minmax, minmaxP95) {
  return {
    solution_id: id,
    distance,
    nominal_time: mean,
    mean,
    coefficient_of_variation: 0,
    pareto_probability: 1,
    regret_mean: 0,
    hypervolume_contribution: 1,
    minmax_regret: minmax,
    minmax_regret_p95: minmaxP95,
    boxplot: { min: mean, q1: mean, median: mean, q3: mean, max: mean, nominal: mean },
  };
}
