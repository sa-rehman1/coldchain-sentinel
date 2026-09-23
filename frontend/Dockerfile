FROM node:24.15.0-alpine3.23 AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_CONTROL_TOWER_DATA_SOURCE=api
ENV VITE_CONTROL_TOWER_DATA_SOURCE=${VITE_CONTROL_TOWER_DATA_SOURCE}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29.1-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -q -O - http://127.0.0.1:8080/ >/dev/null || exit 1
