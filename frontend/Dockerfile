# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────────
# Frontend Dockerfile — NGINX serving static HTML/CSS/JS
# Uses the unprivileged image so the container can run as a non-root user
# (required by most K8s PodSecurityStandards).
# ─────────────────────────────────────────────────────────────────────────────
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Default backend URL for the local-dev /api proxy.
# Override at runtime: `docker run -e BACKEND_URL=http://backend:8000 ...`
# In K8s, the ALB handles /api routing externally, so this is unused there.
ENV BACKEND_URL=http://localhost:8000

USER root
# Drop the default nginx config and install ours
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf

# Copy static assets
COPY index.html  /usr/share/nginx/html/index.html
COPY style.css   /usr/share/nginx/html/style.css
COPY script.js   /usr/share/nginx/html/script.js

# Switch back to non-root nginx user (UID 101 in the unprivileged image)
USER nginx

EXPOSE 8080

# `envsubst` lets us interpolate $BACKEND_URL into nginx.conf at startup
# (NGINX itself doesn't natively expand env vars in its config).
CMD ["/bin/sh", "-c", \
     "envsubst '${BACKEND_URL}' < /etc/nginx/nginx.conf > /tmp/nginx.conf && \
      exec nginx -c /tmp/nginx.conf -g 'daemon off;'"]
