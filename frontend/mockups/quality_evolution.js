(function qualityEvolution(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.QualityEvolution = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function qualityEvolutionFactory() {
  const EMPTY_MESSAGE = 'Nenhuma execução não exata concluída para esta instância.';
  const CURVE_STYLES = [
    { color: '#28624d', dash: [], marker: 'circle' },
    { color: '#d96545', dash: [7, 4], marker: 'square' },
    { color: '#4777a8', dash: [2, 3], marker: 'triangle' },
    { color: '#e5b94f', dash: [8, 3, 2, 3], marker: 'diamond' },
    { color: '#6e4b86', dash: [12, 4], marker: 'cross' },
  ];
  const MARKER_LABELS = {
    circle: 'marcador círculo',
    square: 'marcador quadrado',
    triangle: 'marcador triângulo',
    diamond: 'marcador losango',
    cross: 'marcador cruz',
  };

  function mapCurves(curves, axis) {
    const field = axis === 'evaluations' ? 'evaluations' : 'iteration';
    return (curves || []).map((curve) => {
      const points = (curve.points || []).map((point) => ({
        x: Number(point[field]),
        mean: Number(point.mean),
      })).filter((point) => Number.isFinite(point.x) && Number.isFinite(point.mean));
      return {
        algorithmId: curve.algorithm_id,
        label: curve.label,
        points,
      };
    }).filter((curve) => curve.algorithmId && curve.label && curve.points.length);
  }

  function mapApiQualityEvolution(payload) {
    if (!payload || typeof payload !== 'object') return null;
    const hypervolume = payload.hypervolume;
    const spread = payload.spread;
    if (!hypervolume || !spread || !Array.isArray(hypervolume.curves) || !Array.isArray(spread.curves)) {
      return null;
    }
    const axis = payload.axis === 'evaluations' ? 'evaluations' : 'iteration';
    const fallbackLabel = axis === 'evaluations' ? 'Avaliações' : 'Iterações';
    return {
      axis,
      axisLabel: typeof payload.axis_label === 'string' && payload.axis_label
        ? payload.axis_label
        : fallbackLabel,
      hypervolume: mapCurves(hypervolume.curves, axis),
      spread: mapCurves(spread.curves, axis),
    };
  }

  function buildFigure(id, title, xLabel, yLabel, curves, emptyMessage) {
    const styled = (curves || []).map((curve, index) => {
      const style = CURVE_STYLES[index % CURVE_STYLES.length];
      return {
        algorithmId: curve.algorithmId,
        label: curve.label,
        points: curve.points.map((point) => ({ x: point.x, mean: point.mean })),
        color: style.color,
        dash: style.dash.slice(),
        marker: style.marker,
      };
    });
    return {
      id,
      title,
      xLabel,
      yLabel,
      curves: styled,
      empty: styled.length === 0,
      emptyMessage,
    };
  }

  function qualityEvolutionFigures(mapped, options) {
    const emptyMessage = (options && options.emptyMessage) || EMPTY_MESSAGE;
    const axisLabel = mapped && mapped.axisLabel ? mapped.axisLabel : 'Iterações';
    return [
      buildFigure(
        'hypervolume',
        'Evolução do hipervolume',
        axisLabel,
        'Média do hipervolume',
        mapped && mapped.hypervolume,
        emptyMessage,
      ),
      buildFigure(
        'spread',
        'Evolução do espalhamento Δ',
        axisLabel,
        'Média do espalhamento Δ',
        mapped && mapped.spread,
        emptyMessage,
      ),
    ];
  }

  function dashClass(dash) {
    if (!dash || !dash.length) return 'is-solid';
    if (dash.length > 2) return 'is-dashdot';
    if (dash[0] <= 3) return 'is-dotted';
    return 'is-dashed';
  }

  function dashLabel(dash) {
    const kind = dashClass(dash);
    if (kind === 'is-solid') return 'linha contínua';
    if (kind === 'is-dotted') return 'linha pontilhada';
    if (kind === 'is-dashdot') return 'linha traço-ponto';
    return 'linha tracejada';
  }

  function markerLabel(marker) {
    return MARKER_LABELS[marker] || 'marcador';
  }

  function legendEntries(figure) {
    return (figure.curves || []).map((curve) => ({
      label: curve.label,
      color: curve.color,
      dash: curve.dash.slice(),
      marker: curve.marker,
      dashClass: dashClass(curve.dash),
      markerClass: `is-${curve.marker}`,
      dashLabel: dashLabel(curve.dash),
      markerLabel: markerLabel(curve.marker),
    }));
  }

  function figureDescription(figure) {
    if (!figure || figure.empty) {
      return `${figure ? figure.title : 'Evolução'}. ${figure ? figure.emptyMessage : EMPTY_MESSAGE}`;
    }
    const curves = figure.curves
      .map((curve) => `${curve.label}, ${dashLabel(curve.dash)}, ${markerLabel(curve.marker)}`)
      .join('; ');
    return `${figure.title}. ${curves}. Eixo horizontal: ${figure.xLabel}. Eixo vertical: ${figure.yLabel}.`;
  }

  function paddedRange(values) {
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (!(max - min > 1e-9)) {
      const pad = Math.abs(min) > 1e-9 ? Math.abs(min) * 0.15 : 0.5;
      return { min: min - pad, max: max + pad };
    }
    const pad = (max - min) * 0.08;
    return { min: min - pad, max: max + pad };
  }

  function formatTick(value) {
    if (Math.abs(value - Math.round(value)) < 1e-6) return String(Math.round(value));
    const abs = Math.abs(value);
    if (abs >= 100) return value.toFixed(0);
    if (abs >= 10) return value.toFixed(1);
    return value.toFixed(2);
  }

  function drawMarker(context, marker, x, y, color) {
    const size = 3.4;
    context.beginPath();
    context.fillStyle = '#fffefa';
    context.strokeStyle = color;
    context.lineWidth = 1.4;
    context.setLineDash([]);
    if (marker === 'square') {
      context.rect(x - size, y - size, size * 2, size * 2);
    } else if (marker === 'triangle') {
      context.moveTo(x, y - size - 0.6);
      context.lineTo(x + size, y + size);
      context.lineTo(x - size, y + size);
      context.closePath();
    } else if (marker === 'diamond') {
      context.moveTo(x, y - size - 0.8);
      context.lineTo(x + size, y);
      context.lineTo(x, y + size + 0.8);
      context.lineTo(x - size, y);
      context.closePath();
    } else if (marker === 'cross') {
      context.moveTo(x - size, y - size);
      context.lineTo(x + size, y + size);
      context.moveTo(x + size, y - size);
      context.lineTo(x - size, y + size);
      context.stroke();
      return;
    } else {
      context.arc(x, y, size, 0, Math.PI * 2);
    }
    context.fill();
    context.stroke();
  }

  function drawFigure(context, figure, width, height) {
    context.clearRect(0, 0, width, height);
    const curves = (figure && figure.curves) || [];
    if (!curves.length || !(width > 2) || !(height > 2)) return [];
    const inset = { left: 36, right: 12, top: 12, bottom: 22 };
    const xs = curves.flatMap((curve) => curve.points.map((point) => point.x));
    const ys = curves.flatMap((curve) => curve.points.map((point) => point.mean));
    const xRange = paddedRange(xs);
    const yRange = paddedRange(ys);
    const plotWidth = Math.max(width - inset.left - inset.right, 1);
    const plotHeight = Math.max(height - inset.top - inset.bottom, 1);
    const xOf = (value) => inset.left + ((value - xRange.min) / (xRange.max - xRange.min)) * plotWidth;
    const yOf = (value) => inset.top + ((yRange.max - value) / (yRange.max - yRange.min)) * plotHeight;

    context.font = '9px "IBM Plex Mono", monospace';
    context.textBaseline = 'middle';
    context.lineWidth = 1;
    context.setLineDash([]);
    for (let tick = 0; tick <= 4; tick += 1) {
      const value = yRange.max - ((yRange.max - yRange.min) * tick) / 4;
      const position = inset.top + (plotHeight * tick) / 4;
      context.strokeStyle = '#e9ebe3';
      context.beginPath();
      context.moveTo(inset.left, position);
      context.lineTo(width - inset.right, position);
      context.stroke();
      context.fillStyle = '#89928a';
      context.textAlign = 'right';
      context.fillText(formatTick(value), inset.left - 6, position);
    }
    for (let tick = 0; tick <= 4; tick += 1) {
      const value = xRange.min + ((xRange.max - xRange.min) * tick) / 4;
      const position = inset.left + (plotWidth * tick) / 4;
      context.strokeStyle = '#eff0ea';
      context.beginPath();
      context.moveTo(position, inset.top);
      context.lineTo(position, height - inset.bottom);
      context.stroke();
      context.fillStyle = '#89928a';
      context.textAlign = 'center';
      context.fillText(formatTick(value), position, height - 8);
    }

    const painted = [];
    curves.forEach((curve) => {
      context.beginPath();
      curve.points.forEach((point, index) => {
        const x = xOf(point.x);
        const y = yOf(point.mean);
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      });
      context.strokeStyle = curve.color;
      context.lineWidth = 1.75;
      context.setLineDash(curve.dash);
      context.stroke();
      context.setLineDash([]);
      curve.points.forEach((point) => {
        drawMarker(context, curve.marker, xOf(point.x), yOf(point.mean), curve.color);
      });
      painted.push({
        label: curve.label,
        color: curve.color,
        dash: curve.dash.slice(),
        marker: curve.marker,
      });
    });
    context.setLineDash([]);
    return painted;
  }

  return {
    EMPTY_MESSAGE,
    CURVE_STYLES,
    mapApiQualityEvolution,
    qualityEvolutionFigures,
    legendEntries,
    figureDescription,
    drawFigure,
  };
});
