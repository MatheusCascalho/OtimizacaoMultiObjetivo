(function solutionCompare(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.SolutionCompare = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function solutionCompareFactory() {
  const STYLES = [
    { color: '#28624d', dash: [], patternLabel: 'linha verde contínua' },
    { color: '#d96545', dash: [8, 4], patternLabel: 'linha coral tracejada' },
    { color: '#4777a8', dash: [2, 3], patternLabel: 'linha azul pontilhada' },
    { color: '#8a6a12', dash: [10, 3, 2, 3], patternLabel: 'linha dourada traço-ponto' },
    { color: '#182b25', dash: [1, 3], patternLabel: 'linha tinta pontilhada' },
  ];
  const CITY_COUNT = 8;

  function toggleComparedId(ids, id) {
    const current = Array.isArray(ids) ? ids.slice() : [];
    const index = current.indexOf(id);
    if (index >= 0) {
      current.splice(index, 1);
      return current;
    }
    current.push(id);
    return current;
  }

  function comparisonStyle(index) {
    const style = STYLES[Math.abs(index) % STYLES.length];
    return { color: style.color, dash: style.dash.slice(), patternLabel: style.patternLabel };
  }

  function offsetSegment(source, target, offset) {
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const length = Math.hypot(dx, dy) || 1;
    const ox = (-dy / length) * offset;
    const oy = (dx / length) * offset;
    return {
      source: { x: source.x + ox, y: source.y + oy },
      target: { x: target.x + ox, y: target.y + oy },
    };
  }

  function distanceToSegment(point, source, target) {
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const lengthSq = dx * dx + dy * dy;
    if (lengthSq === 0) return Math.hypot(point.x - source.x, point.y - source.y);
    const t = Math.max(0, Math.min(1, ((point.x - source.x) * dx + (point.y - source.y) * dy) / lengthSq));
    return Math.hypot(point.x - (source.x + t * dx), point.y - (source.y + t * dy));
  }

  function nearestEdge(pointer, edges, limit) {
    return (edges || []).reduce((best, edge) => {
      const distance = distanceToSegment(pointer, edge.source, edge.target);
      return distance < best.distance ? { edge, distance } : best;
    }, { edge: null, distance: limit });
  }

  function matrixValue(payload, source, target) {
    const matrix = payload && payload.matrix;
    if (!Array.isArray(matrix)) return null;
    const row = matrix[Number(source) - 1];
    if (!Array.isArray(row)) return null;
    const value = Number(row[Number(target) - 1]);
    return Number.isFinite(value) ? value : null;
  }

  function formatObjective(value, unit) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 'indisponível';
    return `${numeric.toFixed(2)} ${unit}`;
  }

  function seedFromId(id) {
    const text = String(id);
    let seed = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      seed ^= text.charCodeAt(index);
      seed = Math.imul(seed, 16777619);
    }
    return seed >>> 0;
  }

  function illustrativeNodes() {
    return Array.from({ length: CITY_COUNT }, (_, index) => {
      const angle = (-Math.PI / 2) + (index / CITY_COUNT) * Math.PI * 2;
      return {
        id: index + 1,
        label: String(index + 1),
        x: Math.cos(angle),
        y: Math.sin(angle),
      };
    });
  }

  function illustrativeRoute(id) {
    const cities = Array.from({ length: CITY_COUNT }, (_, index) => index + 1);
    let state = seedFromId(id) || 1;
    const next = () => {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      return state / 4294967296;
    };
    for (let index = cities.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(next() * (index + 1));
      const city = cities[index];
      cities[index] = cities[swap];
      cities[swap] = city;
    }
    cities.push(cities[0]);
    return cities;
  }

  function distribute(total, lengths) {
    const span = lengths.reduce((sum, length) => sum + length, 0) || 1;
    const values = lengths.map((length) => (Number(total) * length) / span);
    const drift = Number(total) - values.reduce((sum, value) => sum + value, 0);
    if (values.length) values[values.length - 1] += drift;
    return values;
  }

  function illustrativeGraph(solution) {
    const nodes = illustrativeNodes();
    const route = illustrativeRoute(solution && solution.id);
    const lengths = [];
    for (let index = 0; index < route.length - 1; index += 1) {
      const source = nodes[route[index] - 1];
      const target = nodes[route[index + 1] - 1];
      lengths.push(Math.hypot(target.x - source.x, target.y - source.y) || 1);
    }
    const distances = distribute(solution ? solution.cost : 0, lengths);
    const times = distribute(solution ? solution.coverage : 0, lengths);
    const edges = lengths.map((_, index) => ({
      source: route[index],
      target: route[index + 1],
      distance: distances[index],
      time: times[index],
    }));
    return { illustrative: true, nodes, route, edges };
  }

  return {
    toggleComparedId,
    comparisonStyle,
    offsetSegment,
    nearestEdge,
    matrixValue,
    formatObjective,
    illustrativeGraph,
  };
});
