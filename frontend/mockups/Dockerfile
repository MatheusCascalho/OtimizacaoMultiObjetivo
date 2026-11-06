FROM nginxinc/nginx-unprivileged:stable-alpine

COPY index.html styles.css app.js frontier_series.js solution_timing.js reference_points.js /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080