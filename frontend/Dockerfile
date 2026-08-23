# Local dev target (default) — Vite dev server with hot reload, matching
# ARCHITECTURE.md §5's "web: Node (React build/dev server), hot-reloaded".
FROM node:20-slim AS dev
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Production build target — static assets only. Not used by
# docker-compose; see ARCHITECTURE.md §6 (S3 + CloudFront, or a
# Deployment behind ingress if SSR is later needed).
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
