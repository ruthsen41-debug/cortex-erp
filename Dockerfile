# Dockerfile - Cortex ERP Pro+
FROM python:3.12-slim

# Metadados e variáveis de ambiente
LABEL maintainer="Cortex ERP Solutions <contato@cortex.com.br>"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instala dependências do sistema necessárias para compilação e criptografia
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY backend /app/backend
COPY frontend /app/frontend
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY entrypoint.sh /app/entrypoint.sh
COPY data /app/data

# Cria diretórios e permissões para usuário não-root
RUN mkdir -p /app/data && \
    chmod +x /app/entrypoint.sh && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Entrypoint: valida JWT, aplica migrações Alembic e sobe o servidor
CMD ["/app/entrypoint.sh"]
