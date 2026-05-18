# Sentinel dashboard — Next.js 14 operator console.
# Used by Railway (service: dashboard).
# NEXT_PUBLIC_SENTINEL_URL is read at BUILD time (Next.js inlines NEXT_PUBLIC_*
# vars into the client bundle), so it must be passed as a build arg.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
ARG NEXT_PUBLIC_SENTINEL_URL=http://127.0.0.1:8088
ENV NEXT_PUBLIC_SENTINEL_URL=${NEXT_PUBLIC_SENTINEL_URL}
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000

# Only ship the runtime artifacts.
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["sh", "-c", "npx next start -p ${PORT:-3000}"]
