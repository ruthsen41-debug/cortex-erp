# Cortex ERP Pro+

Sistema de gestão empresarial, financeira e emissor fiscal com IA. Construído com FastAPI, SQLite/PostgreSQL, Docker e Tailwind CSS.

## Funcionalidades

- **Financeiro** — contas a pagar/receber, parcelas, baixa parcial, juros/multa, estorno, DRE, centros de custo, orçamento por CC
- **Boleto e Pix** — integração Asaas com webhook de baixa automática; régua de cobrança por e-mail e WhatsApp
- **Conciliação bancária** — importação OFX com sugestão automática; Open Finance
- **CRM** — Kanban, orçamentos, PDV, contratos recorrentes com reajuste automático, ordens de serviço, portal do cliente
- **Estoque** — kardex, custo médio, variações, lotes, múltiplos depósitos; pedidos de compra com entrada por XML
- **Emissor fiscal** — NF-e (55), NFC-e (65) e NFS-e via Nuvem Fiscal ou Focus NFe; cancelamento, CC-e, inutilização, manifestação do destinatário
- **Certificado A1** — upload, validação e armazenamento criptografado (Fernet)
- **SPED e Contador** — pacote do contador e portal de acesso por token
- **IA** — CFO virtual via Gemini (com fallback local); lançamento por linguagem natural
- **API pública** — webhooks, integrações com marketplaces e e-commerce
- **PWA** — interface responsiva com tema claro/escuro, offline-ready

---

## Pré-requisitos

| Software | Versão mínima |
|---|---|
| Docker Desktop | 24 + |
| Docker Compose | v2 (incluído no Docker Desktop) |

Ou, sem Docker: Python 3.12+.

---

## Instalação rápida (Docker)

```bash
# 1. Clone o repositório
git clone https://github.com/sua-org/cortex_erp.git
cd cortex_erp

# 2. Configure o ambiente (OBRIGATÓRIO)
cp .env.example .env
```

Abra `.env` e **preencha no mínimo**:

```env
JWT_SECRET_KEY=<gere com: python -c "import secrets; print(secrets.token_urlsafe(64))">
ENVIRONMENT=production
APP_BASE_URL=https://erp.suaempresa.com.br
```

```bash
# 3. Suba o sistema
docker compose up -d

# 4. Verifique se está saudável
docker compose ps
curl http://localhost:8000/api/health
```

Acesse **http://localhost:8000** no navegador.

---

## Primeiro acesso

| Campo | Valor padrão |
|---|---|
| E-mail | `admin@cortex.com.br` |
| Senha | `admin123` |

> **Troque a senha imediatamente** após o primeiro login em Configurações → Usuários.

---

## Configuração do HTTPS (produção)

Use o perfil `proxy` para habilitar o Caddy com Let's Encrypt automático:

```bash
# No .env, configure:
DOMAIN=erp.suaempresa.com.br
ACME_EMAIL=ti@suaempresa.com.br

# Suba com HTTPS
docker compose --profile proxy up -d
```

O Caddy obtém e renova o certificado TLS automaticamente.

---

## Banco de dados PostgreSQL (opcional)

SQLite é o padrão e funciona bem para empresas de pequeno e médio porte. Para alta disponibilidade ou múltiplos workers, use PostgreSQL:

```bash
# No .env:
POSTGRES_PASSWORD=senha_segura
DATABASE_URL=postgresql://cortex:senha_segura@db:5432/cortex

# Suba com PostgreSQL
docker compose --profile postgres up -d
```

As migrações Alembic são aplicadas automaticamente pelo `entrypoint.sh` na inicialização.

---

## Módulo Fiscal — configuração obrigatória para emissão real

Por padrão, o sistema inicia em **ambiente de homologação** e com **geração de XML local** (`sefaz_direto`). As notas emitidas neste modo **não têm validade legal**.

Para emissão real:

### Opção A — Motor direto SEFAZ (gratuito, sem limite)

Comunica-se diretamente com os webservices da SEFAZ sem nenhum intermediário.

Em **Empresa → Fiscal**:

| Campo | Valor |
|---|---|
| Motor Fiscal | `sefaz_real` |
| Token do Provedor | (deixar em branco) |
| Ambiente Fiscal | `producao` |
| Certificado A1 | Faça upload do arquivo `.pfx` com a senha |

> Requer apenas o certificado A1 válido. Zero custo de emissão, sem limite de notas.

### Opção B — Provedor intermediário (Nuvem Fiscal / Focus NFe)

| Provedor | Plano gratuito | Link |
|---|---|---|
| **Nuvem Fiscal** | Sim (até 50 NF/mês) | https://nuvemfiscal.com.br |
| **Focus NFe** | Não (trial disponível) | https://focusnfe.com.br |

Em **Empresa → Fiscal**:

| Campo | Valor |
|---|---|
| Motor Fiscal | `nuvem_fiscal` ou `focus_nfe` |
| Token do Provedor | Credenciais obtidas no painel do provedor |
| Ambiente Fiscal | `producao` |
| Certificado A1 | Faça upload do arquivo `.pfx` com a senha |

> O certificado A1 é armazenado criptografado com Fernet (chave derivada do `JWT_SECRET_KEY`). Mantenha este segredo seguro e com backup.

### 3. Teste em homologação primeiro

Antes de apontar para produção, emita uma nota de teste com `Ambiente Fiscal = homologacao` e verifique a resposta do provedor.

---

## E-mail (recuperação de senha)

Sem configuração, o link de reset é retornado na resposta da API (seguro apenas para desenvolvimento).

Para produção, preencha no `.env`:

```env
SMTP_HOST=smtp.seuservidor.com.br
SMTP_PORT=587
SMTP_USER=noreply@suaempresa.com.br
SMTP_PASSWORD=senha_smtp
SMTP_FROM=noreply@suaempresa.com.br
```

Serviços transacionais recomendados: **Resend**, **SendGrid**, **Amazon SES**.

---

## Gateway de Cobranças (Boleto e Pix)

Integração com **Asaas**. Configure no `.env`:

```env
ASAAS_ENVIRONMENT=production   # sandbox para testes
ASAAS_API_KEY=sua_chave_asaas
PAYMENT_WEBHOOK_TOKEN=token_secreto_webhook
```

No painel do Asaas, cadastre o webhook apontando para:
`https://erp.suaempresa.com.br/api/payments/webhook`

---

## IA — CFO Virtual (Gemini)

```env
GEMINI_API_KEY=sua_chave_gemini
```

Sem a chave, o sistema usa análise financeira local como fallback.

---

## Atualizações

```bash
git pull
docker compose build --no-cache
docker compose up -d
```

As migrações de banco são aplicadas automaticamente na inicialização.

Para usuários da imagem publicada no GHCR:

```bash
docker pull ghcr.io/sua-org/cortex_erp:latest
docker compose up -d
```

---

## Desenvolvimento local (sem Docker)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-cov ruff httpx

cp .env.example .env               # edite conforme necessário

python -m backend.main             # ou: uvicorn backend.main:app --reload
```

Testes:

```bash
pytest tests -v --cov=backend
ruff check backend tests alembic
```

---

## Variáveis de ambiente — referência rápida

| Variável | Obrigatória | Descrição |
|---|---|---|
| `JWT_SECRET_KEY` | **Sim** | Segredo para assinatura dos tokens JWT |
| `ENVIRONMENT` | **Sim** (prod) | `production` habilita modo seguro |
| `APP_BASE_URL` | Recomendado | URL pública, usada no link de reset de senha |
| `DATABASE_URL` | Não | Vazio = SQLite. PostgreSQL: `postgresql://...` |
| `ASAAS_API_KEY` | Cobrança | Chave de API do Asaas |
| `NUVEM_FISCAL_CLIENT_ID` | Fiscal (opt.) | Credenciais da Nuvem Fiscal (alternativa ao motor direto) |
| `NUVEM_FISCAL_CLIENT_SECRET` | Fiscal (opt.) | Credenciais da Nuvem Fiscal |
| `FOCUSNFE_TOKEN` | Fiscal (opt.) | Token da Focus NFe |
| `GEMINI_API_KEY` | IA | Chave Google Gemini para o CFO virtual |
| `SMTP_HOST` | E-mail | Servidor SMTP para recuperação de senha |
| `DOMAIN` | HTTPS | Domínio para o Caddy (perfil `proxy`) |

Consulte `.env.example` para a lista completa.

---

## Licença

MIT — consulte [LICENSE](LICENSE).
