# CinePilot AI frontend — static build served by nginx, for Cloud Run.
#
# Build-time API URL: pass the deployed backend's URL as a build arg, e.g.
#   docker build --build-arg VITE_API_BASE_URL=https://cinepilot-api-xxxx.a.run.app -t cinepilot-frontend .
# because Vite inlines VITE_* env vars at build time, not at container start.

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Cloud Run injects PORT; nginx's docker-entrypoint envsubst's templates/*
# into conf.d/ using PORT (and other env vars) at container start.
ENV PORT=8080
EXPOSE 8080
