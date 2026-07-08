# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — compila o Vue com Vite
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

# Copia apenas os manifestos de dependência primeiro (maximiza cache de camadas)
COPY package*.json ./
RUN npm ci

# Copia o restante do código e compila
# Variáveis VITE_* podem ser injetadas como --build-arg no CI/CD:
#   docker build --build-arg VITE_API_URL=https://api.exemplo.com.br .
COPY . .
RUN npm run build


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runner — Nginx Alpine ultraleve para servir o SPA
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Remove a config padrão do Nginx e injeta a nossa (Vue Router history mode)
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/

# Copia os arquivos compilados do estágio anterior
COPY --from=builder /app/dist .

# Porta esperada pelo Google Cloud Run
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
