# ERP Frontend Dockerfile
# Multi-stage build: Build Vue3 app and serve with Nginx

# ===============================
# Stage 1: Build Vue application
# ===============================
FROM node:20-alpine AS builder

ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Use domestic npm mirror to speed up dependency installation
RUN npm config set registry ${NPM_REGISTRY}

# Install dependencies (using npm install for flexibility)
RUN npm install --legacy-peer-deps

# Copy source code
COPY frontend/ ./

# Build for production
ENV VITE_API_BASE_URL=/api
RUN npm run build

# ===============================
# Stage 2: Serve with Nginx
# ===============================
FROM nginx:alpine

# Remove default nginx config
RUN rm -rf /etc/nginx/conf.d/*

# Copy custom nginx config
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf

# Copy built frontend files
COPY --from=builder /app/dist /var/www/erp

# Create necessary directories
RUN mkdir -p /var/cache/nginx /var/log/nginx

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
