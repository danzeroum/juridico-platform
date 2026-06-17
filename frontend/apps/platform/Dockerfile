# =============================================================================
# PLATFORM - Next.js 14 (App Router) — pnpm workspace monorepo
# Build context: frontend/ (workspace root)
# =============================================================================

# ── Stage 1: install workspace dependencies ───────────────────────────────────
FROM node:20-alpine AS deps
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate
WORKDIR /app

# Copy workspace manifests for layer caching (source not needed yet)
COPY pnpm-workspace.yaml package.json .npmrc ./
COPY packages/tokens/package.json ./packages/tokens/
COPY packages/ui/package.json     ./packages/ui/
COPY apps/platform/package.json   ./apps/platform/

RUN pnpm install --no-frozen-lockfile

# ── Stage 2: build Next.js standalone bundle ──────────────────────────────────
FROM node:20-alpine AS builder
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate
WORKDIR /app

# Restore node_modules (includes pnpm virtual store + workspace symlinks)
COPY --from=deps /app .

# Copy source on top of the installed workspace
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter @juridico/platform build

# ── Stage 3: minimal production runner ────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

# Standalone bundle (has its own minimal node_modules)
COPY --from=builder /app/apps/platform/.next/standalone ./

# Static & public assets at paths the standalone server.js expects
COPY --from=builder --chown=nextjs:nodejs \
     /app/apps/platform/.next/static   ./apps/platform/.next/static
COPY --from=builder --chown=nextjs:nodejs \
     /app/apps/platform/public         ./apps/platform/public

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME="0.0.0.0"

# server.js is at the standalone root; app code is under apps/platform/
CMD ["node", "apps/platform/server.js"]
