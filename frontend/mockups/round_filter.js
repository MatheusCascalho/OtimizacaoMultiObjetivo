(function roundFilter(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.RoundFilter = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function roundFilterFactory() {
  function roundIndex(round) {
    return Number.isInteger(round) && round >= 1 ? round : null;
  }

  function hiddenSet(hiddenRounds) {
    if (hiddenRounds instanceof Set) return hiddenRounds;
    return new Set((hiddenRounds || []).map(roundIndex).filter((round) => round != null));
  }

  function listedRounds(solutions, frontiers) {
    const found = new Set();
    (solutions || []).forEach((solution) => {
      const round = roundIndex(solution && solution.round);
      if (round != null) found.add(round);
    });
    (frontiers || []).forEach((frontier) => {
      const frontierRound = roundIndex(frontier && frontier.round);
      if (frontierRound != null) found.add(frontierRound);
      (frontier && frontier.points || []).forEach((point) => {
        const round = roundIndex(point && point.round);
        if (round != null) found.add(round);
      });
    });
    return [...found].sort((left, right) => left - right);
  }

  function isRoundVisible(round, hiddenRounds) {
    const index = roundIndex(round);
    if (index == null) return true;
    return !hiddenSet(hiddenRounds).has(index);
  }

  function filterSolutions(solutions, hiddenRounds) {
    return (solutions || []).filter((solution) => isRoundVisible(solution && solution.round, hiddenRounds));
  }

  function filterHypervolumeRounds(rounds, hiddenRounds) {
    return (rounds || []).filter((round) => isRoundVisible(round && round.round, hiddenRounds));
  }

  function showAllRounds() {
    return new Set();
  }

  return {
    roundIndex,
    listedRounds,
    isRoundVisible,
    filterSolutions,
    filterHypervolumeRounds,
    showAllRounds,
  };
});
