# Diagnóstico de Paridade — Cortex ERP vs. Domínio Sistemas (Thomson Reuters)

Documento gerado em `2026-11-16` com o mapeamento módulo a módulo do que **já existe** no Cortex ERP e do que **falta implementar** para atingir paridade funcional completa com a suíte Domínio Sistemas (Folha, Escrita Fiscal, Contábil, LALUR/ECF, Patrimônio, Honorários, Processos e Auditoria).

---

## 1. Domínio Folha (Departamento Pessoal) — ~85–90% pronto

### Já implementado
- Arquivos principais: `backend/routers/dp.py`, `backend/services/payroll_engine.py`, `backend/services/payroll_special.py`, `backend/services/payroll_tables.py`, `backend/services/formula_engine.py`, `backend/services/esocial_generator.py`, `backend/routers/conventions.py`, `backend/routers/employee_portal.py`.
- Funcionalidades:
  - Motor de folha por rubricas e fórmulas (`formula_engine.py`, `payroll_engine.py`).
  - Cálculos especiais: 13º salário (1ª e 2ª parcelas com médias), Férias (períodos aquisitivos, abono pecuniário, férias em dobro), Rescisão / TRCT (projeção de aviso prévio proporcional e multa do FGTS).
  - SST: ASO, EPI, CIPA, CAT e PPP/LTCAT.
  - eSocial (geração de XMLs S-2200, S-1200, S-2298, S-2299 e tabelas).
  - FGTS Digital / SEFIP, EFD-Reinf e DCTFWeb.
  - Múltiplos vínculos, reintegração, rateio por centro de custo/rubrica, sindicatos/CCT, autônomos/RPA, pró-labore, estagiários e portal do empregado.

### O que falta para igualar o Domínio Folha
1. **Transmissão direta ao WebService do eSocial (mTLS A1) e retorno de recibos:** enviar lotes SOAP/REST diretamente ao governo usando o certificado A1 e importar eventos totalizadores de retorno (`S-5001` INSS, `S-5002` IRRF, `S-5003` FGTS, `S-5011`).
2. **Folha Complementar e Dissídio Coletivo Retroativo:** cálculo automático das diferenças salariais retroativas à data-base do sindicato (geração de folha complementar de dissídio e parcelamento).
3. **Importação de arquivo AFD / Portaria 671 (Relógio de Ponto Eletrônico):** leitura de marcações brutas do REP e apuração automática de horas extras (50%/100%), intrajornada, interjornada, DSR e adicional noturno.
4. **Arquivo bancário CNAB 240 de pagamento de folha:** geração de remessa bancária para crédito de salários em lote (Itaú, Bradesco, Banco do Brasil, Santander, Caixa).
5. **Troca de escala / horários complexos (12x36, turnos ininterruptos):** calendário de escalas cíclicas integrado ao controle de ponto.

---

## 2. Domínio Escrita Fiscal — ~65% pronto

### Já implementado
- Arquivos principais: `backend/routers/invoices.py`, `backend/routers/nfe_manifest.py`, `backend/routers/accountant.py`, `backend/routers/simples.py`, `backend/routers/dirbi.py`, `backend/services/fiscal_provider.py`, `backend/services/sefaz_direct_real.py`, `backend/services/sped_generator.py`, `backend/services/tax_calculator.py`.
- Funcionalidades:
  - Emissão e gestão de NF-e, NFC-e e NFS-e.
  - Manifestação do Destinatário (`nfe_manifest.py`).
  - SPED Fiscal (ICMS/IPI) e EFD-Contribuições (PIS/COFINS).
  - Simples Nacional / PGDAS-D (Anexos I a V + Fator R).
  - DIRBI, EFD-Reinf e DCTFWeb (previews/geração).

### O que falta para igualar o Domínio Escrita Fiscal
1. **Motor de "Acumuladores":** cada lançamento fiscal passa por um acumulador vinculado a CFOP/NCM que dispara automaticamente as regras de ICMS próprio, ICMS-ST, DIFAL, FCP, IPI, PIS/COFINS e retenções na fonte (`IRRF`, `CSRF 4,65%` — PIS/COFINS/CSLL, `INSS 11%` / Reinf R-2010/R-2020), gerando automaticamente a integração contábil e financeira.
2. **Busca automática de DF-e (CT-e, NF-e de entrada e NFS-e tomadas):** sincronização contínua por NSU na SEFAZ e prefeituras com escrituração automática por regras de NCM/fornecedor.
3. **Obrigações Estaduais e Municipais (GIA, DAPI, DIME, SEDIF/DeSTDA, DES):** geração de arquivos estaduais por UF e emissão de guias estaduais/federais (DARF com código de barras/QR Code Pix, GNRE, DAE).
4. **Reforma Tributária (IBS, CBS e Imposto Seletivo — EC 132 / LC 214):** campos de destaque nos documentos e apuração de teste de CBS/IBS a partir de 2026.

---

## 3. Domínio Contábil — ~75% pronto

### Já implementado
- Arquivos principais: `backend/routers/accounting.py`, `backend/services/accounting_autopost.py`, `backend/services/ecd_generator.py`.
- Funcionalidades:
  - Plano de Contas, lançamentos por partidas dobradas e integração contábil automática (Financeiro e DP).
  - Livro Diário, Razão, Balancete, DRE, Balanço Patrimonial e SPED ECD.

### O que falta para igualar o Domínio Contábil
1. **Zeramento / Encerramento formal de Exercício (ARE):** rotina automática trimestral/anual de transferência das contas de resultado para Apuração do Resultado do Exercício e Lucros/Prejuízos Acumulados, com **bloqueio de períodos fechados** por senha/data.
2. **Demonstrações Contábeis completas (padrão CPC / NBC TG):**
   - **DFC** (Demonstração dos Fluxos de Caixa — método direto e indireto);
   - **DMPL** (Demonstração das Mutações do Patrimônio Líquido) e **DLPA**;
   - **Notas Explicativas** parametrizáveis e **Carta de Responsabilidade da Administração**.
3. **Plano de Contas Referencial da RFB / BACEN:** mapeamento (De-Para) das contas analíticas para o Plano Referencial da Receita Federal (registros `I051` na ECD e blocos `L`/`M` na ECF).
4. **Lançamentos por Histórico Padrão e Rateio Contábil entre filiais e centros de custo.**

---

## 4. Domínio LALUR (Lucro Real) e SPED ECF — ~70% pronto

### Já implementado
- Arquivos principais: `backend/routers/lalur.py`, `backend/routers/accountant.py`.
- Funcionalidades:
  - Parte A (Adições e Exclusões), Parte B (controle de saldo de Prejuízo Fiscal e Base Negativa de CSLL com trava de 30%), apuração de IRPJ/CSLL (15% + adicional de 10% + 9%) e preview da ECF.

### O que falta para igualar o Domínio LALUR / ECF
1. **Lucro Real Anual com Balancetes de Suspensão/Redução mensais:** apuração mês a mês comparando estimativa por receita bruta contra balancete acumulado de suspensão/redução.
2. **Exportação completa do arquivo `.txt` da SPED ECF (leiaute oficial RFB):** geração integral dos blocos `0`, `C`, `E`, `J`, `K`, `L`, `M` (e-LALUR/e-LACS vinculados à Parte B), `N`, `P` e `Y` pronto para validação no PVA.

---

## 5. Domínio Patrimônio — ~70% pronto

### Já implementado
- Arquivos principais: `backend/routers/patrimony.py`.
- Funcionalidades:
  - Cadastro de imobilizado, cálculo de depreciação linear mensal e controle de créditos de ICMS no **CIAP** (1/48 avos).

### O que falta para igualar o Domínio Patrimônio
1. **Baixa total ou parcial de bens com apuração de Ganho/Perda de Capital** (com lançamento contábil automático da baixa do custo e da depreciação acumulada).
2. **Depreciação Fiscal vs. Societária (CPC 27 / Lei 12.973):** controle paralelo de taxas (vida útil econômica societária vs. taxas fiscais da IN RFB 1.700), gerando ajuste automático no LALUR.
3. **Crédito de PIS/COFINS sobre o Ativo Imobilizado** (apropriação em 1/48 ou sobre encargos de depreciação para o Bloco F da EFD-Contribuições) e geração do **Bloco G** dentro do arquivo SPED Fiscal.

---

## 6. Gestão do Escritório Contábil (Honorários, Processos, Protocolo e Auditoria) — ~50% pronto

### Já implementado
- Arquivos principais: `backend/routers/honorarios.py`, `backend/routers/portal.py`, `backend/routers/accountant.py`, `backend/routers/audit.py`.
- Funcionalidades:
  - Contratos de honorários, geração de faturas mensais, portal do cliente/contador e log de auditoria de ações.

### O que falta para igualar a suíte Domínio + Onvio
1. **Domínio Processos (Gestão de Tarefas e Obrigações Acessórias por Cliente):** geração automática da agenda mensal de obrigações por empresa conforme regime tributário (Simples, Presumido, Real), atribuição de responsável, SLA, checklist de entrega e confirmação de leitura pelo cliente (**Protocolo Digital**).
2. **Monitoramento automático de CNDs e Caixa Postal Fiscal (e-CAC / DET / DTE):** painel/rotina de acompanhamento de validade de Certidões Negativas (Federal, FGTS, Estadual, Municipal, Trabalhista) e alertas de intimações.
3. **Domínio Auditoria Fiscal Cruzada:** validador interno que cruza automaticamente **SPED Fiscal × EFD-Contribuições × DCTFWeb × ECD × Folha** antes da transmissão para apontar divergências.
4. **Reajuste anual automático de contratos de honorários** por índice (IGP-M, IPCA, Salário Mínimo) e faturamento de serviços extras por evento (ex.: valor por holerite processado, rescisão, alteração contratual).

---

## Roteiro de Priorização Recomendado — Progresso (atualizado 2026-11-17)

- [x] **Etapa 1 — Fechamento do Motor de Folha por Rubricas (DP)**
  - [x] Soma progressiva de INSS de férias na folha mensal e consolidação de multi-vínculo (`backend/services/payroll_engine.py`)
  - [x] Eventos eSocial `S-1200` e `S-2299` detalhados por rubrica (`backend/services/esocial_generator.py`, `backend/routers/dp.py`)
  - [x] TRCT oficial, Recibo de Férias e Recibo de 13º imprimíveis em HTML (`GET /api/dp/especiais/{id}/documento`, `frontend/static/dp.js`)
  - [x] Importação de arquivo AFD Portaria 671 / 1.510 (`POST /api/dp/ponto/importar-afd`) e Remessa Bancária CNAB 240 (`GET /api/dp/payroll/{run_id}/cnab240`)
  - [ ] Folha Complementar / Dissídio retroativo no novo motor, escalas cíclicas 12x36 e transmissão eSocial direta (mTLS)

- [x] **Etapa 2 — Escrita Fiscal Completa (Acumuladores, Livros e Apuração)**
  - [x] Tabelas `fiscal_accumulators`, `fiscal_entries`, `fiscal_apurations` e seed dos acumuladores `101`–`401` (`backend/database.py`)
  - [x] Alíquotas ICMS internas das 27 UFs e regra interestadual (`backend/services/tax_calculator.py`)
  - [x] Motor fiscal por acumulador (`backend/services/fiscal_book_engine.py`): ICMS, ICMS-ST, DIFAL/FCP, IPI, PIS/COFINS cumulativo e não-cumulativo, ISS, retenções (`IRRF`, `CSRF 4,65%`, `INSS 11%`), Reforma Tributária (`IBS/CBS` teste), contabilização automática, transporte de saldo credor e guias DARF/DAE/DAM HTML
  - [x] API e Frontend (`backend/routers/fiscal_books.py`, `frontend/static/fiscal_books.js`, `tests/test_fiscal_books.py`)

- [x] **Etapa 3 — Geradores SPED Válidos no PVA + Contábil Completo**
  - [x] SPED Fiscal EFD ICMS/IPI (`backend/services/sped_generator.py`): `0100` dinâmico, `0150`, `C100`/`C190` reais, `E110`/`E116` apurados e **Bloco G (CIAP)**
  - [x] SPED Contábil ECD (`backend/services/ecd_generator.py`): registros oficiais `I010`, `I030`, `I050`, `I051`, `I150`/`I155`, `I200`/`I250`, `I350`/`I355`, `J100`, `J150`, `J210`, `J900`, `J930` (substituindo `L020`/`L022`)
  - [x] EFD-Contribuições (Blocos `A`, `C`, `F` [`F120`/`F600`] e `M`) e **SPED ECF** oficial `.txt` (`backend/services/ecf_generator.py`, `GET /api/reports/ecf`, `frontend/static/sped.js`)
  - [x] Balancetes Mensais de Suspensão/Redução no LALUR (`GET /api/lalur/balancetes-suspensao`)
  - [x] **Etapa 3.2:** Encerramento de Exercício Contábil (`ARE`) + Bloqueio de Período, DFC (Direto/Indireto), DMPL/DLPA, Notas Explicativas + Caderno Contábil HTML, Mapeamento Plano Referencial RFB (`I051`) e Históricos Padrão (`backend/routers/accounting.py`, `backend/schemas/accounting.py`, `frontend/static/accounting.js`, `tests/test_sped_and_accounting.py`)

- [x] **Etapa 4 — Escritório Contábil Multiempresa, Processos, Auditoria Cruzada, Patrimônio e Honorários**
  - [x] Multiempresa de Escritório Contábil (`user_companies`, `/api/company/list|create|switch` sem relogar + seletor modal na sidebar em `frontend/index.html` e `frontend/static/app.js`)
  - [x] Domínio Processos (agenda automática de obrigações por regime, SLA e Protocolo Digital) + Monitoramento de CNDs (`office_processes`, `company_cnds`, `backend/routers/accountant.py`, `frontend/static/obligations.js`)
  - [x] Domínio Auditoria Fiscal Cruzada (`GET /api/audit/cruzamento-fiscal`: NF-e × Escrita Fiscal × Contábil × Folha × Diário)
  - [x] Patrimônio Avançado (`POST /api/patrimony/{id}/baixa` com ganho/perda de capital e `GET /api/patrimony/depreciacao-paralela` CPC 27 vs. fiscal IN 1.700 integrada ao LALUR) e Honorários (`POST /api/honorarios/reajustar-anual` e cobrança por eventos em `POST /api/honorarios/faturar-mes`, `tests/test_office_and_parity.py`)
