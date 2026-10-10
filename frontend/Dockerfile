# ==========================================
# Multi-stage Dockerfile for React/Vite Frontend
# ==========================================

# Stage 1: Build static assets
FROM node:20-alpine AS builder

WORKDIR /app

# Cache dependencies
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source files
COPY frontend/ ./

# Configurable build-time API base URL
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

# Build production bundle
RUN npm run build

# Stage 2: Production web server
FROM nginx:1.27-alpine AS runner

# Remove default configuration
RUN rm -rf /etc/nginx/conf.d/* /usr/share/nginx/html/*

# Copy built distribution from Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy production Nginx configuration
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# Expose HTTP
EXPOSE 80

# Health check probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
