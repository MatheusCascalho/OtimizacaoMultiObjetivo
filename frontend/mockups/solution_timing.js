(function solutionTiming(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.SolutionTiming = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function solutionTimingFactory() {
  function formatSolutionDuration(durationMs) {
    if (!Number.isFinite(durationMs) || durationMs < 0) return '--';
    if (durationMs >= 1000) {
      const seconds = durationMs / 1000;
      return `${seconds.toFixed(seconds >= 10 ? 1 : 2)} s`;
    }
    if (durationMs >= 100) return `${durationMs.toFixed(0)} ms`;
    if (durationMs >= 10) return `${durationMs.toFixed(1)} ms`;
    return `${durationMs.toFixed(2)} ms`;
  }

  function formatAttemptIdentity(sample) {
    if (!sample || !Number.isInteger(sample.round) || !Number.isInteger(sample.attempt)) return '';
    return `Rodada ${sample.round} · tentativa ${sample.attempt}`;
  }

  function solutionTimingView(timing) {
    if (!timing || !Number.isFinite(timing.mean_ms) || !Number.isFinite(timing.sample_stdev_ms)) return null;
    return {
      mean: formatSolutionDuration(timing.mean_ms),
      stdev: formatSolutionDuration(timing.sample_stdev_ms),
      slowest: formatSolutionDuration(timing.slowest && timing.slowest.duration_ms),
      slowestDetail: formatAttemptIdentity(timing.slowest),
      fastest: formatSolutionDuration(timing.fastest && timing.fastest.duration_ms),
      fastestDetail: formatAttemptIdentity(timing.fastest),
    };
  }

  return { formatSolutionDuration, formatAttemptIdentity, solutionTimingView };
});
