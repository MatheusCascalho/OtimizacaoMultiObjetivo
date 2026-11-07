(function emissionHeatmap(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.EmissionHeatmap = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function emissionHeatmapFactory() {
  const INFERNO = [
    [0, 0, 4],
    [12, 8, 38],
    [36, 12, 79],
    [66, 10, 104],
    [93, 18, 110],
    [120, 28, 109],
    [147, 38, 103],
    [174, 48, 92],
    [199, 62, 76],
    [221, 81, 58],
    [237, 105, 37],
    [248, 133, 15],
    [252, 165, 10],
    [250, 198, 45],
    [242, 230, 97],
    [252, 255, 164],
  ];
  let rasterCache = { heatmap: null, canvas: null };

  function infernoColor(intensity) {
    const clamped = Math.min(1, Math.max(0, Number(intensity) || 0));
    const scaled = clamped * (INFERNO.length - 1);
    const index = Math.floor(scaled);
    const next = Math.min(index + 1, INFERNO.length - 1);
    const mix = scaled - index;
    const start = INFERNO[index];
    const end = INFERNO[next];
    return {
      r: Math.round(start[0] + (end[0] - start[0]) * mix),
      g: Math.round(start[1] + (end[1] - start[1]) * mix),
      b: Math.round(start[2] + (end[2] - start[2]) * mix),
    };
  }

  function formatFactor(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return number.toFixed(3);
  }

  function formatCo2(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    return number.toFixed(2);
  }

  function formatDensity(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '--';
    const magnitude = Math.abs(number);
    if (magnitude < 0.001) return '0';
    if (magnitude >= 1000) return number.toExponential(1);
    if (magnitude >= 100) return number.toFixed(0);
    if (magnitude >= 10) return number.toFixed(1);
    return number.toPrecision(3);
  }

  function summaryText(emission) {
    if (!emission || emission.total_speed_emission_factor == null) return '';
    return `Fator de emissão de velocidade: ${formatFactor(emission.total_speed_emission_factor)} · ${formatCo2(emission.co2_kg)} kg CO2`;
  }

  function description(emission) {
    if (!emission || emission.total_speed_emission_factor == null) {
      return 'Densidade de CO2 da rota, em quilogramas, suavizada';
    }
    return `Densidade de CO2 suavizada. Fator de emissão de velocidade ${formatFactor(emission.total_speed_emission_factor)}. Total ${formatCo2(emission.co2_kg)} kg.`;
  }

  function heatmapHint(emission) {
    const base = Number(emission && emission.fe_base_kg_per_km);
    const baseText = Number.isFinite(base) ? base.toFixed(2) : '0.30';
    return `Densidade de CO2 em kg, suavizada. Fator de emissão de velocidade ${formatFactor(emission && emission.total_speed_emission_factor)}. Total ${formatCo2(emission && emission.co2_kg)} kg. Premissa: ${baseText} kg/km na faixa eficiente, ajustado pela velocidade de cada arco.`;
  }

  function indexBySolution(payload) {
    const rows = {};
    const solutions = payload && Array.isArray(payload.solutions) ? payload.solutions : [];
    solutions.forEach((item) => {
      if (item && item.solution_id) rows[item.solution_id] = item;
    });
    return rows;
  }

  function densityRange(grid) {
    let min = Infinity;
    let max = -Infinity;
    grid.forEach((row) => {
      row.forEach((value) => {
        const number = Number(value);
        if (!Number.isFinite(number)) return;
        if (number < min) min = number;
        if (number > max) max = number;
      });
    });
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 0 };
    return { min, max };
  }

  function rasterize(heatmap) {
    if (rasterCache.heatmap === heatmap && rasterCache.canvas) return rasterCache.canvas;
    const grid = heatmap.grid;
    const rows = grid.length;
    const cols = grid[0].length;
    const range = densityRange(grid);
    const span = range.max - range.min;
    const offscreen = document.createElement('canvas');
    offscreen.width = cols;
    offscreen.height = rows;
    const context = offscreen.getContext('2d');
    const image = context.createImageData(cols, rows);
    const data = image.data;
    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < cols; column += 1) {
        const number = Number(grid[row][column]);
        const intensity = span === 0 || !Number.isFinite(number) ? 0 : (number - range.min) / span;
        const color = infernoColor(intensity);
        const offset = (row * cols + column) * 4;
        data[offset] = color.r;
        data[offset + 1] = color.g;
        data[offset + 2] = color.b;
        data[offset + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);
    rasterCache = { heatmap, canvas: offscreen };
    return offscreen;
  }

  function drawColorbar(context, width, height, grid) {
    const range = densityRange(grid);
    const barWidth = 12;
    const x = width - 28;
    const y = 22;
    const barHeight = Math.max(40, height - 52);
    for (let step = 0; step < barHeight; step += 1) {
      const intensity = 1 - (barHeight === 1 ? 0 : step / (barHeight - 1));
      const color = infernoColor(intensity);
      context.fillStyle = `rgb(${color.r} ${color.g} ${color.b})`;
      context.fillRect(x, y + step, barWidth, 1);
    }
    context.fillStyle = '#182b25';
    context.font = '10px "IBM Plex Mono", monospace';
    context.textAlign = 'right';
    context.textBaseline = 'top';
    context.fillText(formatDensity(range.max), x - 6, y);
    context.textBaseline = 'bottom';
    context.fillText(formatDensity(range.min), x - 6, y + barHeight);
    context.textAlign = 'left';
    context.textBaseline = 'alphabetic';
  }

  function draw(canvas, model, view) {
    if (!canvas || typeof canvas.getContext !== 'function') return;
    const context = canvas.getContext('2d');
    const bounds = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(bounds.width, 1);
    const height = Math.max(bounds.height, 1);
    canvas.width = Math.max(1, Math.round(width * ratio));
    canvas.height = Math.max(1, Math.round(height * ratio));
    const zoom = view && view.zoom ? view.zoom : 1;
    const panX = view && view.panX ? view.panX : 0;
    const panY = view && view.panY ? view.panY : 0;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    const heatmap = model && model.heatmap;
    const grid = heatmap && Array.isArray(heatmap.grid) ? heatmap.grid : null;
    if (!grid || !grid.length || !grid[0] || !heatmap.extent) {
      context.fillStyle = '#78817b';
      context.font = '12px "DM Sans", sans-serif';
      context.fillText((model && model.heatmap_message) || 'Densidade de CO2 indisponível', 16, 28);
      return;
    }

    if (zoom !== 1 || panX !== 0 || panY !== 0) {
      context.setTransform(ratio * zoom, 0, 0, ratio * zoom, ratio * panX, ratio * panY);
    }
    const extent = heatmap.extent;
    const inset = 28;
    const rightReserve = 72;
    const plotWidth = Math.max(1, width - inset * 2 - rightReserve);
    const plotHeight = Math.max(1, height - inset * 2);
    const spanX = Math.max(extent.xmax - extent.xmin, 1e-9);
    const spanY = Math.max(extent.ymax - extent.ymin, 1e-9);
    const projectX = (value) => inset + ((value - extent.xmin) / spanX) * plotWidth;
    const projectY = (value) => inset + ((value - extent.ymin) / spanY) * plotHeight;
    context.imageSmoothingEnabled = true;
    context.drawImage(rasterize(heatmap), inset, inset, plotWidth, plotHeight);

    const nodes = new Map((model.nodes || []).map((node) => [node.id, node]));
    const route = Array.isArray(model.route) ? model.route.slice() : [];
    if (route.length > 1 && route[0] !== route[route.length - 1]) route.push(route[0]);
    context.beginPath();
    context.lineWidth = 1.35;
    context.strokeStyle = 'rgba(255, 255, 255, 0.78)';
    route.forEach((cityId, index) => {
      const node = nodes.get(cityId);
      if (!node) return;
      const x = projectX(node.x);
      const y = projectY(node.y);
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();
    (model.nodes || []).forEach((node) => {
      context.beginPath();
      context.arc(projectX(node.x), projectY(node.y), node.id === route[0] ? 4.2 : 2.5, 0, Math.PI * 2);
      context.fillStyle = node.id === route[0] ? '#d96545' : '#fffcf6';
      context.fill();
    });

    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    drawColorbar(context, width, height, grid);
  }

  return {
    infernoColor,
    formatFactor,
    formatCo2,
    summaryText,
    description,
    heatmapHint,
    indexBySolution,
    draw,
  };
});
