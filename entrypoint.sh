#!/bin/sh
set -e

# Avisa se JWT_SECRET_KEY não está definido no ambiente.
# O config.py gera e persiste uma chave em data/.jwt_secret como fallback,
# mas em ambientes efêmeros (Kubernetes, ECS sem volume) isso faz todos os
# tokens JWT expirarem a cada redeploy. Defina JWT_SECRET_KEY no .env.
if [ -z "$JWT_SECRET_KEY" ] && [ ! -f /app/data/.jwt_secret ]; then
    echo "AVISO: JWT_SECRET_KEY não definido e data/.jwt_secret ausente." >&2
    echo "       Uma chave aleatória será gerada — tokens JWT expirarão a cada restart." >&2
    echo "       Para produção, defina JWT_SECRET_KEY no .env ou monte o volume ./data." >&2
fi

# Aplica migrações pendentes antes de subir o servidor.
# Em banco novo isso cria todas as tabelas; em banco existente é idempotente.
if [ -n "$DATABASE_URL" ]; then
    echo "Aplicando migrações Alembic..."
    alembic upgrade head
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
