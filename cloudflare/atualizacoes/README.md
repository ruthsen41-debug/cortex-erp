# Servidor de atualizações e licenças (Cloudflare)

Modelo híbrido: o **porteiro** (Worker) confere a chave de licença do escritório e
entrega um link de download assinado; o **depósito** (R2, privado) guarda os
instaladores; as **licenças** ficam num banco D1. Tudo no plano grátis da Cloudflare.

```
Servidor do escritório --POST /v1/verificar {chave}--> Worker --confere--> D1 (licenças)
                       <--manifesto + link (30 min)---
                       --GET /v1/baixar/4.6.0?...----> Worker --lê-----> R2 (instaladores)
```

## Implantação (uma vez só)

Na pasta `cloudflare/atualizacoes`:

```powershell
npx wrangler@3 login                         # abre o navegador para autorizar a conta
npx wrangler@3 r2 bucket create cortex-atualizacoes
npx wrangler@3 d1 create cortex-licencas     # copie o database_id para o wrangler.toml
npx wrangler@3 d1 execute cortex-licencas --remote --file schema.sql
npx wrangler@3 secret put ADMIN_TOKEN        # cole um token longo e aleatório (guarde-o)
npx wrangler@3 secret put LINK_SECRET        # outro valor aleatório (não precisa guardar)
npx wrangler@3 deploy                        # mostra o endereço https://cortex-atualizacoes.<conta>.workers.dev
```

Para gerar um valor aleatório no PowerShell:
`-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | % {[char]$_})`

## Depois de implantar

1. **Endereço no código:** troque `SERVIDOR_PADRAO` em `backend/routers/atualizacao.py`
   pelo endereço do Worker (assim toda instalação nova já sai apontando para ele).
2. **Script de lançamento:** crie `%USERPROFILE%\.cortex\atualizacoes.json`:
   ```json
   { "url": "https://cortex-atualizacoes.<conta>.workers.dev", "token": "<ADMIN_TOKEN>" }
   ```
3. **Painel do Sistema › Licenças:** no Render (e no seu .env local), defina
   `CORTEX_ATUALIZACOES_URL` e `CORTEX_ATUALIZACOES_ADMIN_TOKEN`.

## No dia a dia

- **Vender:** Painel do Sistema › Licenças › Nova licença → envie a chave `CTX-XXXX-XXXX-XXXX`
  ao escritório; o admin dele digita em Administração › Atualizações.
- **Lançar versão:** `scripts\lancar_versao.ps1 -Versao 4.6.0 -Notas "..."` envia o instalador
  ao R2 (o R2 confere o SHA-256) e publica a versão.
- **Cliente parou de pagar:** Suspender. O sistema dele continua funcionando, só não recebe versões novas.

## Rotas

| Rota | Quem usa |
|---|---|
| `POST /v1/verificar` | servidor do escritório (chave de licença) |
| `GET /v1/baixar/:versao?k&exp&sig` | servidor do escritório (link assinado, vale 30 min) |
| `GET/POST /v1/admin/licencas`, `PATCH /v1/admin/licencas/:chave` | Painel do Sistema |
| `GET /v1/admin/versoes`, `PUT /v1/admin/versoes/:v/arquivo`, `PUT /v1/admin/versoes/:v/publicar` | lancar_versao.ps1 |

As rotas `/v1/admin/*` exigem `Authorization: Bearer <ADMIN_TOKEN>`.
