# ---- build ---------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

# Build-time settings (Vite inlines VITE_* variables into the bundle).
ARG VITE_API_BASE_URL=/api
ARG VITE_DEMO_MODE=false
ARG VITE_DEMO_PASSWORD=DemoPass123!
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_DEMO_MODE=$VITE_DEMO_MODE \
    VITE_DEMO_PASSWORD=$VITE_DEMO_PASSWORD

RUN npm run build

# ---- serve ---------------------------------------------------------------
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz || exit 1
