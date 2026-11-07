const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

const emission = require(path.join(
  __dirname,
  '../../frontend/mockups/emission_heatmap.js',
));

test('inferno keeps low density dark and high density bright', () => {
  const low = emission.infernoColor(0);
  const high = emission.infernoColor(1);
  const lowSum = low.r + low.g + low.b;
  const highSum = high.r + high.g + high.b;

  assert.ok(lowSum < highSum);
  assert.ok(low.b >= low.r);
  assert.ok(high.r > high.b);
});

test('the solution index keeps the total speed factor', () => {
  const indexed = emission.indexBySolution({
    solutions: [
      { solution_id: 'sol_a', total_speed_emission_factor: 1.233333, co2_kg: 11.1 },
      { solution_id: 'sol_b', total_speed_emission_factor: 1.283333, co2_kg: 11.55 },
    ],
  });

  assert.equal(indexed.sol_a.total_speed_emission_factor, 1.233333);
  assert.equal(emission.formatFactor(indexed.sol_b.total_speed_emission_factor), '1.283');
  assert.equal(
    emission.summaryText(indexed.sol_a),
    'Fator de emissão de velocidade: 1.233 · 11.10 kg CO2',
  );
  assert.equal(emission.summaryText({ total_speed_emission_factor: null }), '');
  assert.match(emission.description(indexed.sol_a), /1\.233/);
  assert.match(emission.heatmapHint(indexed.sol_a), /suavizada/);
});
