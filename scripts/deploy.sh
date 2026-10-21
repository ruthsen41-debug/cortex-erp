#!/usr/bin/env bash
# =============================================================================
# Cortex ERP – Script de Deploy para Produção
# =============================================================================
# Uso:
#   bash scripts/deploy.sh              # deploy completo (SQLite)
#   bash scripts/deploy.sh --postgres   # ativa perfil PostgreSQL
#   bash scripts/deploy.sh --proxy      # ativa Caddy (HTTPS automático)
#   bash scripts/deploy.sh --full       # PostgreSQL + Caddy
#
# Pré-requisitos: docker, docker compose v2, curl
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
APP_URL="http://localhost:8000/api/health"
BACKUP_SCRIPT="$SCRIPT_DIR/backup.py"

PROFILES=()
USE_POSTGRES=false
USE_PROXY=false

# ── Parsing de argumentos ────────────────────────────────────────────────────
for arg in "$@"; do
  case $arg in
    --postgres) USE_POSTGRES=true; PROFILES+=(postgres) ;;
    --proxy)    USE_PROXY=true;    PROFILES+=(proxy) ;;
    --full)     USE_POSTGRES=true; USE_PROXY=true; PROFILES+=(postgres proxy) ;;
    *) echo "Argumento desconhecido: $arg"; exit 1 ;;
  esac
done

# ── Funções auxiliares ───────────────────────────────────────────────────────
log()  { echo -e "\033[1;34m[DEPLOY]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
warn() { echo -e "\033[1;33m[ WARN ]\033[0m $*"; }
fail() { echo -e "\033[1;31m[ FAIL ]\033[0m $*"; exit 1; }

# ── Checklist de pré-deploy ──────────────────────────────────────────────────
log "=== CHECKLIST DE PRÉ-DEPLOY ==="

# 1. Arquivo .env presente
if [[ ! -f "$ENV_FILE" ]]; then
  fail ".env não encontrado. Copie .env.example para .env e preencha as variáveis."
fi
ok ".env encontrado"

# 2. JWT_SECRET_KEY definido
JWT_SECRET=$(grep -E '^JWT_SECRET_KEY=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
if [[ -z "$JWT_SECRET" ]]; then
  warn "JWT_SECRET_KEY vazio. Gerando chave aleatória..."
  GENERATED=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))" 2>/dev/null || openssl rand -base64 48)
  sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$GENERATED|" "$ENV_FILE"
  ok "JWT_SECRET_KEY gerada e salva no .env"
fi
ok "JWT_SECRET_KEY configurada"

# 3. Docker disponível
if ! command -v docker &>/dev/null; then
  fail "Docker não encontrado. Instale em https://docs.docker.com/get-docker/"
fi
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"

# 4. Docker Compose v2
if ! docker compose version &>/dev/null; then
  fail "Docker Compose v2 não encontrado. Atualize o Docker Desktop ou instale o plugin."
fi
ok "Docker Compose $(docker compose version --short)"

# 5. Porta 8000 livre (ou proxy assumirá)
if $USE_PROXY; then
  ok "Porta 8000 será acessada internamente pelo Caddy"
else
  if ss -tlnp 2>/dev/null | grep -q ':8000 ' || netstat -tlnp 2>/dev/null | grep -q ':8000 '; then
    warn "Porta 8000 já em uso. Verifique se outro processo está rodando."
  else
    ok "Porta 8000 livre"
  fi
fi

# ── Backup antes de atualizar ────────────────────────────────────────────────
log "=== PRÉ-DEPLOY: BACKUP ==="
if [[ -f "$BACKUP_SCRIPT" ]]; then
  log "Executando backup preventivo antes do deploy..."
  python3 "$BACKUP_SCRIPT" --keep 14 && ok "Backup concluído" || warn "Backup falhou (continuando deploy)"
else
  warn "Script de backup não encontrado em $BACKUP_SCRIPT"
fi

# ── Build e Deploy ───────────────────────────────────────────────────────────
log "=== BUILD ==="
cd "$PROJECT_DIR"

PROFILE_ARGS=()
for p in "${PROFILES[@]}"; do
  PROFILE_ARGS+=(--profile "$p")
done

docker compose "${PROFILE_ARGS[@]}" build --no-cache
ok "Imagem construída"

log "=== DEPLOY ==="
docker compose "${PROFILE_ARGS[@]}" up -d --remove-orphans
ok "Containers iniciados"

# ── Health Check ─────────────────────────────────────────────────────────────
log "=== HEALTH CHECK ==="
MAX_RETRIES=15
RETRY=0
until curl -sf "$APP_URL" >/dev/null 2>&1; do
  RETRY=$((RETRY + 1))
  if [[ $RETRY -ge $MAX_RETRIES ]]; then
    fail "Health check falhou após ${MAX_RETRIES}s. Verifique: docker compose logs cortex_erp_app"
  fi
  log "Aguardando aplicação iniciar... ($RETRY/$MAX_RETRIES)"
  sleep 2
done
ok "Aplicação respondendo em $APP_URL"

# ── Relatório final ──────────────────────────────────────────────────────────
log "=== DEPLOY CONCLUÍDO ==="
echo ""
echo "  Aplicação:   http://localhost:8000"
$USE_PROXY && echo "  HTTPS:       https://$(grep -E '^DOMAIN=' "$ENV_FILE" | cut -d= -f2 | tr -d '"' | tr -d "'" || echo 'seu-dominio.com')"
echo ""
echo "  Logs:        docker compose logs -f cortex_erp_app"
echo "  Status:      docker compose ps"
echo "  Parar:       docker compose down"
echo "  Backup:      python3 scripts/backup.py"
echo ""

# Agenda backup diário no cron se disponível
if command -v crontab &>/dev/null; then
  CRON_LINE="0 2 * * * python3 $BACKUP_SCRIPT --keep 14 >> $PROJECT_DIR/data/backup.log 2>&1"
  if ! crontab -l 2>/dev/null | grep -qF "$BACKUP_SCRIPT"; then
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    ok "Backup diário agendado no cron (02:00)"
  else
    ok "Cron de backup já configurado"
  fi
fi
