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
2. ✅ (2026-11-18) **Folha Complementar e Dissídio Coletivo Retroativo:** cálculo automático das diferenças salariais retroativas à data-base do sindicato (geração de folha complementar de dissídio e parcelamento).
3. **Importação de arquivo AFD / Portaria 671 (Relógio de Ponto Eletrônico):** leitura de marcações brutas do REP e apuração automática de horas extras (50%/100%), intrajornada, interjornada, DSR e adicional noturno.
4. **Arquivo bancário CNAB 240 de pagamento de folha:** geração de remessa bancária para crédito de salários em lote (Itaú, Bradesco, Banco do Brasil, Santander, Caixa).
5. ✅ (2026-11-18) **Troca de escala / horários complexos (12x36, turnos ininterruptos):** calendário de escalas cíclicas integrado ao controle de ponto.

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
  - [x] Folha Complementar (`POST /api/dp/payroll/complementar`, recalcula o mês e paga só a diferença) e Dissídio/Acordo/Convenção retroativo (`POST /api/dp/payroll/dissidio`: INSS por mês de referência, IRRF no mês do pagamento ou RRA, FGTS, reajuste do cadastro) com S-1200 `infoPerAnt`/`ideADC` validado no XSD (`backend/services/payroll_complementar.py`) — 2026-11-18
  - [x] Escalas cíclicas 12x36, 24x48, 24x72, 5x1, 6x1 e personalizadas com turmas, hora noturna reduzida e prorrogação (Súmula 60), integradas ao ponto, à importação AFD (plantão que vira a meia-noite) e ao adicional noturno da folha (`backend/services/escalas.py`, aba DP › Escalas & Horários) — 2026-11-18
  - [ ] Transmissão eSocial direta (mTLS): implementada na Central do eSocial; falta testar no ambiente do governo com um certificado A1 real

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

---

## Mapa do módulo Folha da Domínio × Cortex (levantamento de 2026-11-18)

**Fonte:** títulos e caminhos de menu dos artigos públicos da Central de Soluções da Domínio, módulo Folha. Foram lidos 1.312 artigos de três tópicos: Cálculos e Lançamentos, Configurações e Cadastros, e Relatórios e Guias. O levantamento serve só para identificar *quais funções existem*. Regras de cálculo e leiautes seguem a CLT e a documentação oficial do gov.br. Nenhum texto da Domínio foi copiado.

Legenda: ✅ existe no Cortex · ⚠️ parcial · ❌ falta. O número entre parênteses é a quantidade de artigos da Domínio sobre o menu, um indicativo de uso.

### Arquivo (cadastros)
| Menu Domínio | Cortex |
|---|---|
| Empregados (139) | ✅ Ficha completa de 8 abas, S-2200, histórico salarial. ⚠️ Faltam: nome social, campos livres, copiar cadastro, alteração em grupo |
| Rubricas (160) e Bases de Cálculo (16) | ✅ Rubricas com incidências e fórmulas, rubricas fixas por funcionário. ⚠️ Faltam: base de cálculo nomeada e reutilizável; rubricas-padrão de mercado como anuênio, triênio, quinquênio, quebra de caixa, sobreaviso, gratificação e dupla função |
| Sindicatos (106) | ✅ CCT, contribuição assistencial e oposição, repasse, piso. ✅ (2026-11-18) **Regras da CCT aplicadas na folha**: HE em dia útil e domingo/feriado e adicional noturno (nunca abaixo da lei), adicional por tempo de serviço (anuênio/biênio/triênio/quinquênio, base salário/piso/mínimo, teto de períodos), meses para médias de férias/13º/rescisão e indenização da data-base (Lei 7.238/84 art. 9º; Súmulas 182 e 314); convenção escolhida no cadastro ou a única vigente. ⚠️ Faltam: dias para pagamento da rescisão e estabilidades da convenção |
| Contribuintes, Estagiários (76) | ✅ Autônomos/RPA (S-2300), estágio, pró-labore. ⚠️ Faltam: MEI prestador, cooperado, dirigente sindical |
| Serviços (51) | ⚠️ S-1005 e S-1020 existem. Faltam: tomador de serviço, empreitada, obra própria (CNO), alocação de empregado por serviço, trabalho temporário |
| Tabelas (14) | ✅ Tabelas fiscais por ano editáveis (INSS, IRRF, salário mínimo, salário-família). ⚠️ Faltam: IRRF exclusivo de PLR, salário mínimo estadual |
| Jornadas e Horários (25) | ✅ Escalas fixas e cíclicas (12x36 e outras) |
| Plano de Saúde, VT, VA (11) | ✅ (2026-11-18) **VT** com cadastro de linhas por funcionário, dias de uso automáticos (sem feriados, férias, afastamentos e faltas), desconto de 6% do salário básico limitado ao custo, pedido de compra (HTML/CSV) e recibo de entrega. **Plano de saúde/odonto** por faixa etária da ANS (RN 63/2003) ou valor fixo, titular e dependentes, rateio empresa × empregado, coparticipação (lançamento e importação do extrato da operadora) e conferência com a fatura. Rubricas 0111/0112 (natureza 9219). ⚠️ Falta: informações de plano de saúde por beneficiário no S-1210 |
| Cargos, Funções, Departamentos, Centros de Custo | ✅ |

### Processos
| Menu Domínio | Cortex |
|---|---|
| Cálculo (39): mensal, adiantamento, complementar | ✅ Mensal, adiantamento, complementar, dissídio. ❌ Faltam: folha de PLR, semanalista, mais de um adiantamento no mês |
| Lançamentos (102) | ✅ Comissões com DSR e garantia mínima (mínimo ou piso). ✅ Lançamento por rubrica, por funcionário e em lote, horas do ponto. ⚠️ Faltam: lançamento fixo com data-fim, faltas parciais em horas com DSR na semana |
| Férias (54) | ✅ Individual com períodos, abono, dobro, médias, 13º nas férias e perda por afastamento ou faltas. ❌ Faltam: **programação de férias**, **férias em grupo e coletivas calculadas**, fracionamento em até 3 períodos (art. 134 §1º), antecipação da Lei 14.457 |
| Rescisões (69) | ✅ Individual com TRCT, aviso, multa FGTS e 13º/férias. ✅ (2026-11-18) **Rescisão complementar** (dissídio/CCT com recálculo por diferença, multa do art. 477, indenização da data-base, verbas avulsas), **rescisão em grupo** e **aviso prévio como processo** (registrar, carta, cancelar por reconsideração, redução 2h/7 dias, proporcional indenizado). ❌ Faltam: transferência entre empresas e filiais, morte, força maior |
| Afastamentos (46) | ✅ Afastamentos com S-2230, atestados, CAT. ⚠️ Faltam: prorrogação de licença-maternidade, limbo previdenciário, declaração de último dia trabalhado |
| Alteração Salarial (14) | ⚠️ Histórico salarial e dissídio existem. ✅ (2026-11-18) Categorias no cadastro: mensalista, horista, diarista, semanal, quinzenal, tarefa, só comissões e professor (hora-aula × aulas × 4,5 + DSR 1/6). Faltam: alteração em grupo |
| Rotinas Automáticas (25) | ❌ Agendar cálculo da folha, recibos, guias e envios ao eSocial |
| RPA (8), Pró-labore | ✅ |
| Intermitente: convocações (3) | ❌ |
| Empréstimo consignado (2) | ✅ (2026-11-18) Contratos do Crédito do Trabalhador (natureza 9253) e de convênio (9254), parcela por competência, margem consignável configurável (padrão 35% da remuneração disponível), consulta de margem e desconto do saldo na rescisão até a margem. ⚠️ Falta: importar as parcelas do FGTS Digital |
| Aposentadoria, Advertência e Suspensão, Estabilidades | ✅ Advertência, suspensão e estabilidades. ⚠️ Aposentadoria só como motivo de desligamento |
| Pagamentos (4): baixa da folha e dos encargos | ❌ |
| Informações: desoneração e multivínculo | ✅ Multivínculo. ⚠️ Desoneração / INSS sobre receita bruta |

### Relatórios
| Menu Domínio | Cortex |
|---|---|
| Recibos (20) | ✅ Holerite em 2 vias, TRCT, recibo de férias, mensagem no recibo. ✅ (2026-11-18) **Holerite por e-mail** (SMTP próprio da empresa com senha cifrada, texto com campos, teste, registro e reenvio das falhas). ❌ Faltam: termos de quitação e homologação, carta de preposto |
| Folha (14) | ✅ Folha analítica com resumo, CNAB. ✅ (2026-11-18) Relação de líquidos, ficha financeira anual (folha por empregado), lançamentos por rubrica, resumo de férias e relação de rescisões, em HTML para imprimir ou CSV. ❌ Faltam: extrato mensal consolidado |
| Encargos e Guias (24) | ✅ GPS, DARF, DCTFWeb, FGTS Digital, SEFIP. ⚠️ Faltam: relatório de IRRF, analítico de GPS, encargos da empresa consolidado |
| eSocial (57) | ✅ Central do eSocial e totalizadores. ✅ (2026-11-18) **Conferência folha × eSocial** (aba na Central do eSocial): por trabalhador, bases e INSS do S-5001, IRRF do S-5002 (mês do pagamento) e base/depósito do S-5003 contra a folha, com motivo provável de cada diferença, totais, CSV e aviso de quando dá para fechar. ⚠️ PIS sobre folha (entidades imunes) não conferido |
| Cadastrais e Gerenciador (72) | ✅ Ficha de registro, contrato, advertência e quitação. ✅ (2026-11-18) **Pacote de 17 modelos** em DP › Documentos: contratos de experiência, determinado e intermitente, prorrogação e término da experiência, acordos de compensação e de prorrogação de horas, termo de salário-família, dependentes para IR, opção/renúncia de VT, autorização de desconto, termo LGPD, carta de recomendação e convocação por abandono. Textos editáveis por empresa (variáveis do cadastro, prévia, voltar ao padrão) e modelos próprios — o equivalente ao Gerenciador |
| Aviso Prévio (12) | ✅ Carta de aviso do empregador (trabalhado/indenizado, acordo) e pedido de demissão. ✅ (2026-11-18) Aviso de férias (usa a programação), requerimento de abono pecuniário e pedido da 1ª parcela do 13º nas férias |
| Outros (29) | ✅ Vencimento de experiência e de férias. ❌ Faltam: faltas, histórico do empregado, alterações salariais, quantidade de colaboradores, quadro de horário, cálculo de médias |
| Informativos | ❌ Relatório de Transparência Salarial (Lei 14.611/2023) |
| Programação de Férias | ❌ |

### Utilitários e Controle
| Menu Domínio | Cortex |
|---|---|
| Simuladores (férias e rescisão) | ✅ Simular nas telas. ❌ Falta relatório de simulações |
| Excluir cálculos em grupo (férias, rescisões, RPA) | ✅ DP › Utilitários (férias, 13º, rescisões e RPA; bloqueia competência fechada e S-2299 aceito) |
| Alterar cadastros em grupo | ✅ DP › Utilitários (salário com histórico e piso, cargo, CBO, departamento, centro de custo, escala, CCT, horas) |
| Acerto de data de pagamento | ✅ DP › Utilitários (folhas, recibos e RPA; avisa S-1210 já aceito e mudança do mês do IRRF) |
| Rotinas automáticas e baixa de pagamentos | ✅ DP › Utilitários: folha e guias no contas a pagar (5º dia útil e dia 20), baixa em lote, rotinas agendadas (calcular folha, enviar holerites, lançar no financeiro) |
| Controle > Parâmetros (224): sempre 30 dias × dias do mês, divisor de férias, arredondamento, % do adiantamento | ⚠️ Fixo no código. Falta tela de parâmetros da folha por empresa |
| Avisos de vencimento: certificado, experiência, férias, ASO | ⚠️ Há alertas espalhados. Falta painel único |

### Prioridade sugerida para as lacunas
1. **Uso diário:** parâmetros da folha por empresa · programação de férias, férias em grupo e coletivas · rescisão complementar e em grupo, aviso prévio como processo · holerite por e-mail · relação de líquidos e relatórios de folha.
2. ✅ **Documentos (concluído em 2026-11-18):** pacote de modelos (contratos, aviso e abono de férias, salário-família, VT, termos), personalizável por empresa.
3. ✅ **Regras de CCT e categorias (concluído em 2026-11-18):** adicional por tempo de serviço, médias por CCT, indenização da data-base, comissionados com garantia mínima, horista e professor. Também: médias de HE e adicional noturno pela quantidade de horas × salário-hora atual (Súmula 347) e HE do comissionista só com o adicional sobre as comissões (Súmula 340 e OJ 397).
4. ✅ **Benefícios (concluído em 2026-11-18):** VT automático e compra, plano de saúde por faixa etária e coparticipação, consignado.
5. ✅ **Automação e utilitários (concluído em 2026-11-18):** rotinas automáticas, alterações e exclusões em grupo, acerto de data de pagamento, baixa de pagamentos.
6. **Menor uso:** ✅ demonstrativos folha × eSocial (2026-11-18) · PLR, intermitente, trabalho temporário e tomador, transparência salarial.
