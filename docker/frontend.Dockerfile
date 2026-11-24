# Imagen única para los 3 frontends (web-pasajero, web-conductor, web-interno).
# Contexto = raíz del repo: los 3 son workspaces de npm y consumen
# `apps/shared-ui` como fuente TS, así que necesitan el lockfile raíz.
#   docker build -f docker/frontend.Dockerfile --build-arg APP=web-interno .

# ---- Etapa 1: build estático con Vite ----
FROM node:22-alpine AS build
WORKDIR /repo

COPY package.json package-lock.json ./
COPY apps/shared-ui/package.json apps/shared-ui/
COPY apps/web-pasajero/package.json apps/web-pasajero/
COPY apps/web-conductor/package.json apps/web-conductor/
COPY apps/web-interno/package.json apps/web-interno/
# --legacy-peer-deps: mismo criterio que la instalación local del proyecto
# (conflicto de peers de recharts con react-dom, ver CLAUDE.md §7 punto 5.1).
RUN npm ci --legacy-peer-deps --no-audit --no-fund

COPY apps ./apps

ARG APP
# El navegador (no el contenedor) es quien llama a la API, por eso la URL
# pública del backend es la del host, no el hostname interno `backend`.
ARG VITE_API_URL=http://localhost:8000
ARG VITE_GOOGLE_MAPS_API_KEY=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY
RUN npm run build -w @urbanflet/${APP} && cp -r apps/${APP}/dist /out

# ---- Etapa 2: servir con nginx ----
FROM nginx:1.27-alpine
COPY docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /out /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD wget -q --spider http://127.0.0.1/ || exit 1
