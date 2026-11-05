(function paretoFrontierSeries(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.ParetoFrontierSeries = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function frontierSeriesFactory() {
  const FRONTIER_REPETITIONS = 5;
  const FRONTIER_ROUND_STYLES = [
    { round: 1, label: 'Rodada 1', color: '#28624d', dash: [] },
    { round: 2, label: 'Rodada 2', color: '#d96545', dash: [7, 4] },
    { round: 3, label: 'Rodada 3', color: '#4777a8', dash: [2, 3] },
    { round: 4, label: 'Rodada 4', color: '#e5b94f', dash: [8, 3, 2, 3] },
    { round: 5, label: 'Rodada 5', color: '#6e4b86', dash: [12, 4] },
  ];

  function comparePoints(left, right) {
    return left.cost - right.cost || left.coverage - right.coverage;
  }

  function styleForRound(round) {
    return FRONTIER_ROUND_STYLES.find((style) => style.round === round)
      || FRONTIER_ROUND_STYLES[(round - 1) % FRONTIER_ROUND_STYLES.length];
  }

  function frontierSeriesFromSolutions(solutions) {
    const frontier = solutions.filter((solution) => solution.frontier);
    const rounds = [...new Set(
      frontier
        .map((solution) => solution.round)
        .filter((round) => Number.isInteger(round) && round >= 1),
    )].sort((left, right) => left - right);

    if (!rounds.length) {
      return [{
        round: null,
        label: 'Não dominadas',
        color: '#6d9779',
        dash: [4, 4],
        points: frontier.slice().sort(comparePoints),
      }];
    }

    return rounds.map((round) => {
      const style = styleForRound(round);
      return {
        round,
        label: style.label,
        color: style.color,
        dash: style.dash.slice(),
        points: frontier.filter((solution) => solution.round === round).sort(comparePoints),
      };
    });
  }

  function strokeFrontierSeries(context, seriesList, toPoint) {
    const painted = [];
    seriesList.forEach((series) => {
      if (!series.points.length) return;
      context.beginPath();
      series.points.forEach((point, index) => {
        const position = toPoint(point);
        if (index === 0) context.moveTo(position.x, position.y);
        else context.lineTo(position.x, position.y);
      });
      context.strokeStyle = series.color;
      context.lineWidth = 1.5;
      context.setLineDash(series.dash);
      context.stroke();
      painted.push({
        round: series.round,
        label: series.label,
        color: series.color,
        dash: series.dash.slice(),
      });
    });
    context.setLineDash([]);
    return painted;
  }

  return {
    FRONTIER_REPETITIONS,
    FRONTIER_ROUND_STYLES,
    frontierSeriesFromSolutions,
    strokeFrontierSeries,
  };
});
