FROM node:22-bookworm-slim@sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9 AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

FROM base AS dependencies
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci

FROM dependencies AS build
COPY apps/web ./apps/web
RUN npm run build

FROM base AS runtime
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
RUN groupadd --gid 10001 forge && useradd --uid 10001 --gid forge --no-create-home forge
COPY --from=build --chown=forge:forge /app/apps/web/.next/standalone ./
COPY --from=build --chown=forge:forge /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=forge:forge /app/apps/web/public ./apps/web/public
USER forge
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
