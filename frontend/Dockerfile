# Choice Jini frontend — chat page + widget.js, served by nginx with /api
# proxied same-origin to the backend service (SSE-safe; see nginx.conf).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# CHO-286: the build stamps this into the bundle — Vite substitutes
# `import.meta.env.VITE_APP_VERSION` statically at build time, and a static
# nginx image has no runtime env, so it CANNOT be set at `docker run` the way
# the backend's BOT_VERSION is. Pass `--build-arg VITE_APP_VERSION=<image tag>`
# (see docs/deployment.md). Unset ⇒ no X-Frontend-Version header, field omitted.
ARG VITE_APP_VERSION
ENV VITE_APP_VERSION=$VITE_APP_VERSION
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
