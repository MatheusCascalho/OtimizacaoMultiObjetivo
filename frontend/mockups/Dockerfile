FROM nginxinc/nginx-unprivileged:stable-alpine

COPY index.html styles.css app.js frontier_series.js solution_timing.js reference_points.js hypervolume.js quality_evolution.js round_filter.js solution_compare.js robustness.js emission_heatmap.js /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080