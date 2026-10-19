# Plano de Evolução — Cortex ERP (meta: paridade com o Conta Azul)

## 1. Estado atual

Backend FastAPI + SQLite (`backend/main.py` ~2.235 linhas, `database.py`, `fiscal_engine.py`). Frontend: `frontend/index.html` com Tailwind via CDN.

| Área | Estado |
|---|---|
| Dashboard e CFO virtual (Gemini, com fallback local) | Existe |
| Contas a pagar/receber: parcelas, baixa parcial, juros/multa, estorno, baixa em lote | Existe |
| Contas bancárias, transferências, plano de contas (DRE), centros de custo | Existe |
| Conciliação OFX | Existe |
| Clientes/fornecedores com busca de CNPJ (BrasilAPI) e CEP (ViaCEP) | Existe |
| Produtos com ficha fiscal, kardex, custo médio | Existe |
| CRM Kanban, orçamentos, vendas, PDV, contratos recorrentes, ordens de serviço | Existe |
| Entrada de compras por XML | Existe |
| NF-e, NFC-e, NFS-e (XML, DANFE, CC-e, cancelamento, ZIP) | Existe, **simulado** |
| DRE e relatórios | DRE existe; fluxo de caixa e curva ABC incompletos |

## 2. Problemas que travam hoje

1. `frontend/static/app.js` não existe: a interface não funciona.
2. `database.py:60`: coluna `certificado_ titular` (espaço no nome) quebra o `CREATE TABLE companies`, e o app não inicia.
3. A emissão fiscal é simulada: protocolo e assinatura fictícios, chave de acesso com número aleatório, nada é enviado à SEFAZ/prefeitura. O XML só cobre ICMSSN102 e não escapa caracteres especiais.
4. Certificado A1: truncado em 2048 caracteres, senha em texto puro, validade inventada (hoje + 365 dias).
5. Sem autenticação, usuários ou permissões; CORS com `*`.
6. Empresa única, com `company_id=1` fixo em vários pontos.
7. Dinheiro em `REAL` (float).
8. Tudo em um `main.py`, sem validação Pydantic, sem testes, sem git, sem `requirements.txt`.
9. `main.py:36` com caminho fixo `C:\Users\USUARIO\cortex_ai\.env`.
10. `category_id` fixos (18, 11, 1) em várias rotas.
11. O fallback do lookup de CNPJ devolve dados falsos quando a API está fora do ar.

## 3. Fases

### Fase 0 — Estabilizar
- [ ] `git init` e `requirements.txt`
- [ ] Corrigir o erro de SQL (`certificado_ titular`)
- [ ] Criar `frontend/static/app.js` ligado às rotas existentes
- [ ] Remover caminho fixo do `.env`, IDs de categoria fixos e fallback com dados falsos
- [ ] Teste de fumaça de cada rota

### Fase 1 — Fundação
- [ ] Separar `main.py` em routers/serviços (financeiro, vendas, estoque, fiscal...) e usar Pydantic
- [ ] Alembic para migrações; valores monetários em centavos (inteiro) ou `Decimal`
- [ ] Multiempresa (`company_id` em todas as tabelas)
- [ ] Autenticação JWT, perfis e permissões; CORS restrito
- [ ] Auditoria de alterações
- [ ] Opcional: PostgreSQL no lugar de SQLite
- [ ] Testes automatizados

### Fase 2 — Financeiro (nível Conta Azul)
- [ ] Boleto, Pix e link de pagamento via gateway (ex.: Asaas), com webhook de baixa automática
- [ ] Régua de cobrança por e-mail e WhatsApp
- [ ] Conciliação com sugestão automática; Open Finance
- [ ] Fluxo de caixa realizado e previsto; DRE por regime de caixa e de competência
- [ ] Orçamento por centro de custo; rateio entre categorias
- [ ] Importação/exportação de planilhas

### Fase 3 — Vendas, compras e estoque
- [ ] Vendas com múltiplos itens, tabelas de preço, comissão de vendedores, devoluções
- [ ] Pedidos de compra, múltiplos depósitos, inventário, lotes e variações
- [ ] Contratos recorrentes com reajuste automático
- [ ] Portal do cliente (orçamento e boleto online)

### Fase 4 — Fiscal real
- [ ] Integrar provedor homologado (Focus NFe, PlugNotas, Nuvem Fiscal) para NF-e, NFC-e e NFS-e (incluindo NFS-e nacional)
- [ ] Eventos fiscais: cancelamento, CC-e, inutilização; manifestação do destinatário
- [ ] Certificado armazenado criptografado (cofre/KMS)
- [ ] Impostos por regime (Simples, Presumido, Real); SPED e pacote do contador; portal do contador

### Fase 5 — Produto
- [ ] Interface em React/Vue, responsiva, PWA
- [ ] API pública e webhooks; integrações com marketplaces e e-commerce
- [ ] Notificações, backup, logs
- [ ] Docker, CI e monitoramento

## 4. Custos estimados (grosseiros)

Claude Code (por token): Fase 0 US$ 1–3 · Fase 1 US$ 10–30 · Fase 2 US$ 15–40 · Fase 3 US$ 15–40 · Fase 4 US$ 15–40 · Fase 5 US$ 30–80. Total aproximado: US$ 90–230.

Fora a IA: provedor fiscal (mensalidade + por nota), certificado A1 (anual), gateway de boleto/Pix (taxa por transação), hospedagem, domínio. Confirmar preços atuais.

Fases 0 a 2 já entregam um financeiro utilizável (US$ 25–75 estimados).

## 5. Decisões pendentes

1. Só corrigir o que existe (Fase 0) ou seguir direto para a refatoração (Fase 1)?
2. Fiscal: provedor de API (mais rápido e seguro) ou SEFAZ direta?
3. Uso próprio ou produto para vários clientes (define prioridade de multiempresa e PostgreSQL)?

## 6. Dicas para gastar menos

- Uma tarefa por vez; `/clear` entre tarefas.
- Leituras pontuais (por função/trecho), não arquivos inteiros.
- Modelo mais barato nas tarefas simples; acompanhar com `/cost`.
