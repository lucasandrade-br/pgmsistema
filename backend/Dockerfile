# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — compila wheels do Python (inclui mysqlclient)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências de compilação (necessárias só para gerar as wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runner — imagem final enxuta, sem ferramentas de compilação
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Apenas o runtime do MySQL (libmysqlclient.so) — sem gcc/build-essential
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Instala as wheels compiladas no Stage 1
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir /wheels/*

# Copia o código da aplicação
COPY . .

# collectstatic com DEBUG=True para STATIC_ROOT ficar disponível sem banco de dados
# (STATIC_ROOT é definido incondicionalmente no settings.py)
RUN DATABASE_URL=sqlite:///dummy.db \
    SECRET_KEY=dummy_key_build \
    DEBUG=True \
    python manage.py collectstatic --noinput

# Remove o sqlite de build — não deve existir na imagem final
RUN rm -f dummy.db

# Permissões e troca de usuário
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Gunicorn: 2 workers + 4 threads por worker = boa concorrência em Cloud Run
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "90", \
     "--graceful-timeout", "30", \
     "core_api.wsgi:application"]
