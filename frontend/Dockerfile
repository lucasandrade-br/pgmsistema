# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — compila o Vue com Vite
# ─────────────────────────────────────────────────────────────────────────────
# ATUALIZADO: Usando Node 22 para suprir as exigências das bibliotecas
FROM node:22-alpine AS builder
WORKDIR /app

# Copia apenas os manifestos de dependência primeiro (maximiza cache de camadas)
COPY package*.json ./
# ATUALIZADO: Usando npm install para contornar a falta de sincronia do package-lock
RUN npm install

# Copia o restante do código e compila
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
