# Build stage — full toolchain
FROM node:22-alpine AS build
WORKDIR /app
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable && corepack prepare pnpm@12.4.1 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm run build

# Runtime stage — vite preview serves dist/ and proxies /api to the backend.
# pnpm's node_modules is self-contained (virtual store lives inside it),
# so copying it keeps the runtime image install-free.
FROM node:22-alpine
WORKDIR /app
ENV CREO_API_PROXY_TARGET=http://backend:8000
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/vite.config.ts ./
EXPOSE 4173
CMD ["node_modules/.bin/vite", "preview", "--host", "0.0.0.0", "--port", "4173"]
