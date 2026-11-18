// ═══════════════════════════════════════════════════════════════
//  Ficha completa do funcionário (padrão Domínio / leiaute S-2200)
//  Abas: Pessoais · Documentos · Endereço · Contrato · Salário e
//  Jornada · Bancário · Dependentes · Saúde e Outros
// ═══════════════════════════════════════════════════════════════
(function () {
  const UFS = ['', 'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR',
    'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'].map((u) => [u, u || '—']);
  const MESES = [['', '—'], ...['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
    'Setembro', 'Outubro', 'Novembro', 'Dezembro'].map((m, i) => [String(i + 1).padStart(2, '0'), m])];
  const SIM_NAO = [[0, 'Não'], [1, 'Sim']];

  const OPT = {
    sexo: [['M', 'Masculino'], ['F', 'Feminino']],
    estado_civil: [['1', 'Solteiro(a)'], ['2', 'Casado(a)'], ['3', 'Divorciado(a)'], ['4', 'Separado(a)'], ['5', 'Viúvo(a)']],
    raca_cor: [['1', 'Branca'], ['2', 'Preta'], ['3', 'Parda'], ['4', 'Amarela'], ['5', 'Indígena'], ['6', 'Não informado']],
    grau_instrucao: [['01', 'Analfabeto'], ['02', 'Até o 5º ano incompleto'], ['03', '5º ano completo'],
      ['04', '6º ao 9º ano incompleto'], ['05', 'Fundamental completo'], ['06', 'Médio incompleto'],
      ['07', 'Médio completo'], ['08', 'Superior incompleto'], ['09', 'Superior completo'],
      ['10', 'Pós-graduação'], ['11', 'Mestrado'], ['12', 'Doutorado']],
    deficiencia: [['', 'Nenhuma'], ['fisica', 'Física'], ['visual', 'Visual'], ['auditiva', 'Auditiva'],
      ['mental', 'Mental'], ['intelectual', 'Intelectual'], ['reabilitado', 'Reabilitado / readaptado']],
    tipo_sanguineo: [['', '—'], ...['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map((t) => [t, t])],
    esocial_category: [['101', '101 · Empregado geral (CLT)'], ['103', '103 · Aprendiz'], ['104', '104 · Doméstico'],
      ['105', '105 · Prazo determinado (Lei 9.601)'], ['106', '106 · Temporário'], ['111', '111 · Intermitente'],
      ['701', '701 · Contribuinte individual (autônomo)'], ['721', '721 · Diretor não empregado c/ FGTS'],
      ['722', '722 · Diretor não empregado s/ FGTS'], ['901', '901 · Estagiário']],
    tipo_admissao: [['1', '1 · Admissão'], ['2', '2 · Transferência (mesmo grupo)'],
      ['3', '3 · Transferência (fusão/cisão/incorporação)'], ['5', '5 · Mudança de CPF']],
    ind_admissao: [['1', '1 · Normal'], ['2', '2 · Decorrente de ação fiscal'], ['3', '3 · Decisão judicial']],
    regime_previdenciario: [['1', 'RGPS (INSS)'], ['2', 'RPPS (próprio)'], ['3', 'Regime no exterior']],
    tipo_contrato: [['indeterminado', 'Prazo indeterminado'], ['experiencia', 'Experiência'],
      ['determinado', 'Prazo determinado'], ['intermitente', 'Intermitente']],
    experiencia_dias: [[0, '—'], [30, '30 dias'], [45, '45 dias'], [60, '60 dias'], [90, '90 dias']],
    experiencia_prorrogacao: [[0, 'Sem prorrogação'], [30, '+30 dias'], [45, '+45 dias'], [60, '+60 dias']],
    tipo_salario: [['5', 'Mensalista'], ['1', 'Horista'], ['2', 'Diarista'], ['3', 'Semanal'], ['4', 'Quinzenal'],
      ['6', 'Tarefa'], ['7', 'Não aplicável']],
    forma_pagamento: [['deposito', 'Depósito em conta'], ['pix', 'PIX'], ['cheque', 'Cheque'], ['dinheiro', 'Dinheiro']],
    jornada_tipo: [['integral', 'Integral'], ['parcial', 'Tempo parcial']],
    escala: [['', '—'], ['5x2', '5x2 (segunda a sexta)'], ['6x1', '6x1'], ['12x36', '12x36'], ['4x2', '4x2'],
      ['turno', 'Turnos de revezamento'], ['livre', 'Sem controle (art. 62)']],
    insalubridade_grau: [['', 'Não'], ['minimo', 'Mínimo (10%)'], ['medio', 'Médio (20%)'], ['maximo', 'Máximo (40%)']],
    bank_account_type: [['corrente', 'Conta corrente'], ['poupanca', 'Poupança'], ['salario', 'Conta salário']],
    pix_tipo: [['', '—'], ['cpf', 'CPF'], ['email', 'E-mail'], ['telefone', 'Telefone'], ['aleatoria', 'Chave aleatória']],
    aso_resultado: [['', '—'], ['apto', 'Apto'], ['inapto', 'Inapto']],
    parentesco: [['01', 'Cônjuge'], ['02', 'Companheiro(a)'], ['03', 'Filho(a) / enteado(a)'],
      ['04', 'Filho(a)/enteado(a) universitário até 24'], ['06', 'Irmão(ã), neto(a), bisneto(a)'],
      ['09', 'Pais, avós, bisavós'], ['10', 'Menor sob guarda judicial'], ['11', 'Incapaz sob tutela/curatela'],
      ['12', 'Ex-cônjuge com pensão'], ['99', 'Agregado / outros']],
  };

  // [chave, rótulo, tipo, opções/extra, colunas]
  const TABS = [
    { id: 'pessoais', label: 'Pessoais', icon: 'user', fields: [
      ['name', 'Nome completo *', 'text', null, 2], ['nome_social', 'Nome social', 'text', null, 2],
      ['birth_date', 'Nascimento', 'date'], ['sexo', 'Sexo', 'select', OPT.sexo],
      ['estado_civil', 'Estado civil', 'select', OPT.estado_civil], ['raca_cor', 'Raça / cor', 'select', OPT.raca_cor],
      ['grau_instrucao', 'Grau de instrução', 'select', OPT.grau_instrucao, 2],
      ['nacionalidade', 'Nacionalidade', 'text'], ['pais_nascimento', 'País de nascimento (cód.)', 'text'],
      ['naturalidade', 'Naturalidade (cidade)', 'text'], ['uf_nascimento', 'UF nascimento', 'select', UFS],
      ['nome_mae', 'Nome da mãe', 'text', null, 2], ['nome_pai', 'Nome do pai', 'text', null, 2],
      ['deficiencia', 'Pessoa com deficiência', 'select', OPT.deficiencia, 2],
      ['tipo_sanguineo', 'Tipo sanguíneo', 'select', OPT.tipo_sanguineo],
    ]},
    { id: 'documentos', label: 'Documentos', icon: 'id-card', fields: [
      ['cpf', 'CPF *', 'text', '000.000.000-00'], ['pis_pasep', 'PIS / PASEP / NIT', 'text', '000.00000.00-0'],
      ['_h', 'RG'], ['rg', 'Número', 'text'], ['rg_orgao', 'Órgão emissor', 'text', 'SSP'],
      ['rg_uf', 'UF', 'select', UFS], ['rg_emissao', 'Emissão', 'date'],
      ['_h', 'Carteira de Trabalho (CTPS)'], ['ctps', 'Número', 'text'], ['ctps_serie', 'Série', 'text'],
      ['ctps_uf', 'UF', 'select', UFS], ['ctps_emissao', 'Emissão', 'date'],
      ['_h', 'Título de eleitor'], ['titulo_eleitor', 'Número', 'text', null, 2],
      ['titulo_zona', 'Zona', 'text'], ['titulo_secao', 'Seção', 'text'],
      ['_h', 'CNH'], ['cnh', 'Registro', 'text'], ['cnh_categoria', 'Categoria', 'text', 'AB'],
      ['cnh_validade', 'Validade', 'date'], ['cnh_uf', 'UF', 'select', UFS],
      ['_h', 'Outros'], ['reservista', 'Certificado de reservista', 'text', null, 2],
      ['conselho_classe', 'Conselho de classe', 'text', 'CRC, CREA, OAB…'], ['conselho_numero', 'Nº registro', 'text'],
      ['conselho_uf', 'UF conselho', 'select', UFS],
    ]},
    { id: 'endereco', label: 'Endereço', icon: 'map-pin', fields: [
      ['cep', 'CEP', 'cep'], ['logradouro', 'Logradouro', 'text', null, 3],
      ['numero', 'Número', 'text'], ['complemento', 'Complemento', 'text'], ['bairro', 'Bairro', 'text', null, 2],
      ['cidade', 'Cidade', 'text', null, 2], ['uf', 'UF', 'select', UFS], ['cod_municipio', 'Cód. IBGE', 'text'],
      ['_h', 'Contato'], ['email', 'E-mail', 'email', null, 2], ['phone', 'Telefone', 'text'], ['celular', 'Celular', 'text'],
    ]},
    { id: 'contrato', label: 'Contrato', icon: 'file-signature', fields: [
      ['matricula', 'Matrícula', 'text', 'gerada se vazio'], ['admission_date', 'Admissão *', 'date'],
      ['tipo_admissao', 'Tipo de admissão', 'select', OPT.tipo_admissao],
      ['ind_admissao', 'Indicativo de admissão', 'select', OPT.ind_admissao],
      ['esocial_category', 'Categoria eSocial', 'select', OPT.esocial_category, 2],
      ['regime_previdenciario', 'Regime previdenciário', 'select', OPT.regime_previdenciario],
      ['primeiro_emprego', 'Primeiro emprego', 'select', SIM_NAO],
      ['tipo_contrato', 'Tipo de contrato', 'select', OPT.tipo_contrato],
      ['experiencia_dias', 'Experiência', 'select', OPT.experiencia_dias],
      ['experiencia_prorrogacao', 'Prorrogação', 'select', OPT.experiencia_prorrogacao],
      ['data_termino_contrato', 'Término do contrato', 'date'],
      ['_h', 'Lotação e cargo'], ['role', 'Cargo *', 'text'], ['cbo', 'CBO', 'cbo'],
      ['funcao', 'Função', 'text'], ['department', 'Departamento', 'text'],
      ['centro_custo', 'Centro de custo', 'text'], ['local_trabalho', 'Local de trabalho', 'text', null, 3],
      ['_h', 'Sindicato'], ['sindicato_nome', 'Sindicato', 'text', null, 2], ['sindicato_cnpj', 'CNPJ do sindicato', 'text'],
      ['data_base_mes', 'Data-base', 'select', MESES],
      ['contribuicao_sindical', 'Contribuição sindical autorizada', 'select', SIM_NAO, 2],
      ['is_prolabore', 'Pró-labore (sócio)', 'select', SIM_NAO, 2],
    ]},
    { id: 'salario', label: 'Salário e jornada', icon: 'banknote', fields: [
      ['salary', 'Salário base (R$) *', 'number'], ['tipo_salario', 'Tipo de salário', 'select', OPT.tipo_salario],
      ['forma_pagamento', 'Forma de pagamento', 'select', OPT.forma_pagamento],
      ['adiantamento_pct', 'Adiantamento (%)', 'number'],
      ['vt_monthly', 'Vale-transporte mensal (R$)', 'number'],
      ['insalubridade_grau', 'Insalubridade', 'select', OPT.insalubridade_grau],
      ['periculosidade', 'Periculosidade (30%)', 'select', SIM_NAO],
      ['_h', 'Jornada de trabalho'], ['jornada_tipo', 'Jornada', 'select', OPT.jornada_tipo],
      ['horas_semana', 'Horas semanais', 'number'], ['escala', 'Escala', 'select', OPT.escala, 2],
      ['horario_entrada', 'Entrada', 'time'], ['intervalo_inicio', 'Início intervalo', 'time'],
      ['intervalo_fim', 'Fim intervalo', 'time'], ['horario_saida', 'Saída', 'time'],
      ['descricao_jornada', 'Descrição da jornada (eSocial)', 'text', 'gerada a partir dos horários se vazio', 4],
    ]},
    { id: 'bancario', label: 'Bancário', icon: 'landmark', fields: [
      ['bank_code', 'Cód. banco', 'text', '001'], ['bank_name', 'Banco', 'text', null, 3],
      ['bank_agency', 'Agência', 'text'], ['bank_account', 'Conta', 'text'],
      ['bank_account_type', 'Tipo de conta', 'select', OPT.bank_account_type, 2],
      ['_h', 'PIX'], ['pix_tipo', 'Tipo de chave', 'select', OPT.pix_tipo], ['pix_chave', 'Chave PIX', 'text', null, 3],
    ]},
    { id: 'dependentes', label: 'Dependentes', icon: 'baby', fields: [] },
    { id: 'outros', label: 'Saúde e FGTS', icon: 'heart-pulse', fields: [
      ['_h', 'Saúde ocupacional (ASO)'], ['aso_admissional_data', 'Exame admissional', 'date'],
      ['aso_resultado', 'Resultado', 'select', OPT.aso_resultado],
      ['_h', 'FGTS'], ['fgts_opcao_data', 'Data de opção', 'date'],
      ['fgts_aniversario', 'Saque-aniversário', 'select', SIM_NAO],
      ['_h', 'Observações'], ['notes', 'Observações gerais', 'textarea', null, 4],
    ]},
  ];

  const NUMERIC = new Set(['salary', 'vt_monthly', 'adiantamento_pct', 'horas_semana']);
  const INTS = new Set(['primeiro_emprego', 'experiencia_dias', 'experiencia_prorrogacao', 'contribuicao_sindical',
    'periculosidade', 'fgts_aniversario', 'is_prolabore', 'dependents', 'filhos_sal_familia']);
  const DEFAULTS = { sexo: 'M', estado_civil: '1', raca_cor: '6', grau_instrucao: '07', nacionalidade: 'Brasileira',
    pais_nascimento: '105', tipo_admissao: '1', ind_admissao: '1', esocial_category: '101', regime_previdenciario: '1',
    tipo_contrato: 'indeterminado', tipo_salario: '5', forma_pagamento: 'deposito', jornada_tipo: 'integral',
    horas_semana: 44, bank_account_type: 'corrente', vt_monthly: 0, cbo: '' };

  const state = { emp: null, deps: [], tab: 'pessoais' };
  const esc = (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const fid = (k) => `ef-${k}`;
  const optsHtml = (opts, val) => opts.map(([v, l]) =>
    `<option value="${esc(v)}" ${String(val ?? '') === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('');

  function fieldHtml([key, label, type, extra, span]) {
    if (key === '_h') {
      return `<div class="col-span-full mt-2 pt-3 first:mt-0 first:pt-0 border-t first:border-t-0 border-slate-100 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-violet-600">${esc(label)}</div>`;
    }
    const v = state.emp[key] ?? '';
    const cls = inputCls();
    const colspan = span ? `md:col-span-${span}` : '';
    let input;
    if (type === 'select') {
      input = `<select id="${fid(key)}" class="${cls}">${optsHtml(extra, v)}</select>`;
    } else if (type === 'textarea') {
      input = `<textarea id="${fid(key)}" rows="4" class="${cls}">${esc(v)}</textarea>`;
    } else if (type === 'cep') {
      input = `<div class="flex gap-2"><input id="${fid(key)}" class="${cls}" value="${esc(v)}" placeholder="00000-000"
        onblur="efBuscarCep()"><button type="button" onclick="efBuscarCep()" title="Buscar endereço"
        class="px-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-violet-600"><i data-lucide="search" class="w-4 h-4"></i></button></div>`;
    } else if (type === 'cbo') {
      input = `<input id="${fid(key)}" list="ef-cbo-list" class="${cls}" value="${esc(v)}" placeholder="código ou ocupação"
        oninput="efBuscarCbo(this.value)"><datalist id="ef-cbo-list"></datalist>`;
    } else {
      const t = type === 'number' ? 'number" step="0.01' : type;
      input = `<input id="${fid(key)}" type="${t}" class="${cls}" value="${esc(v)}" ${extra ? `placeholder="${esc(extra)}"` : ''}>`;
    }
    return `<div class="${colspan}">${labelCls(esc(label))}${input}</div>`;
  }

  function depsHtml() {
    const parent = Object.fromEntries(OPT.parentesco);
    const rows = state.deps.map((d, i) => `
      <tr class="border-b border-slate-50 dark:border-slate-800">
        <td class="px-3 py-2 font-medium text-slate-700 dark:text-slate-200">${esc(d.nome)}</td>
        <td class="px-3 py-2 text-xs">${esc(parent[d.parentesco] || d.parentesco)}</td>
        <td class="px-3 py-2 text-xs">${d.data_nascimento ? new Date(d.data_nascimento + 'T00:00').toLocaleDateString('pt-BR') : '—'}</td>
        <td class="px-3 py-2 text-xs">${esc(d.cpf || '—')}</td>
        <td class="px-3 py-2 text-center">${d.irrf ? '✔' : ''}</td>
        <td class="px-3 py-2 text-center">${d.salario_familia ? '✔' : ''}</td>
        <td class="px-3 py-2 text-center">${d.plano_saude ? '✔' : ''}</td>
        <td class="px-3 py-2 text-right whitespace-nowrap">
          <button onclick="efDepEditar(${i})" class="text-xs text-indigo-500 hover:underline mr-2">Editar</button>
          <button onclick="efDepRemover(${i})" class="text-xs text-rose-500 hover:underline">Excluir</button>
        </td>
      </tr>`).join('');
    const semLista = !state.deps.length;
    return `
      <div class="col-span-full">
        <div class="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
          <table class="w-full text-sm">
            <thead><tr class="text-[10px] text-slate-400 uppercase bg-slate-50 dark:bg-slate-800/50">
              <th class="px-3 py-2 text-left">Nome</th><th class="px-3 py-2 text-left">Parentesco</th>
              <th class="px-3 py-2 text-left">Nascimento</th><th class="px-3 py-2 text-left">CPF</th>
              <th class="px-3 py-2">IRRF</th><th class="px-3 py-2">Sal. família</th><th class="px-3 py-2">Plano saúde</th><th></th>
            </tr></thead>
            <tbody>${rows || '<tr><td colspan="8" class="px-3 py-6 text-center text-xs text-slate-400">Nenhum dependente cadastrado.</td></tr>'}</tbody>
          </table>
        </div>
        <div id="ef-dep-form" class="mt-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 grid grid-cols-1 md:grid-cols-4 gap-3">
          <input type="hidden" id="ef-dep-idx" value="">
          <div class="md:col-span-2">${labelCls('Nome do dependente')}<input id="ef-dep-nome" class="${inputCls()}"></div>
          <div>${labelCls('Parentesco')}<select id="ef-dep-parentesco" class="${inputCls()}">${optsHtml(OPT.parentesco, '03')}</select></div>
          <div>${labelCls('Nascimento')}<input id="ef-dep-nasc" type="date" class="${inputCls()}"></div>
          <div>${labelCls('CPF')}<input id="ef-dep-cpf" class="${inputCls()}" placeholder="000.000.000-00"></div>
          <div>${labelCls('Sexo')}<select id="ef-dep-sexo" class="${inputCls()}">${optsHtml([['', '—'], ...OPT.sexo], '')}</select></div>
          <div class="md:col-span-2 flex items-end gap-4 text-sm text-slate-600 dark:text-slate-300 pb-2">
            <label class="flex items-center gap-1.5"><input type="checkbox" id="ef-dep-irrf" checked> IRRF</label>
            <label class="flex items-center gap-1.5"><input type="checkbox" id="ef-dep-sf"> Salário-família</label>
            <label class="flex items-center gap-1.5"><input type="checkbox" id="ef-dep-plano"> Plano de saúde</label>
          </div>
          <div class="md:col-span-4 flex justify-end">
            <button onclick="efDepSalvar()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5">
              <i data-lucide="plus" class="w-3.5 h-3.5"></i> <span id="ef-dep-btn">Adicionar dependente</span></button>
          </div>
        </div>
        <div class="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>${labelCls('Dependentes IRRF')}<input id="ef-dependents" type="number" min="0" class="${inputCls()}"
            value="${esc(state.emp.dependents ?? 0)}" ${semLista ? '' : 'disabled'}></div>
          <div>${labelCls('Cotas salário-família')}<input id="ef-filhos_sal_familia" type="number" min="0" class="${inputCls()}"
            value="${esc(state.emp.filhos_sal_familia ?? 0)}" ${semLista ? '' : 'disabled'}></div>
          <p class="col-span-2 self-end text-[11px] text-slate-400 leading-snug pb-1">
            ${semLista ? 'Sem lista de dependentes: informe os totais manualmente.'
              : 'Totais calculados pela lista (salário-família: filhos até 14 anos marcados).'}</p>
        </div>
      </div>`;
  }

  function renderTab() {
    const tab = TABS.find((t) => t.id === state.tab);
    document.querySelectorAll('[data-ef-tab]').forEach((b) => {
      const on = b.dataset.efTab === state.tab;
      b.className = `ef-tab flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg whitespace-nowrap transition ${
        on ? 'bg-violet-600 text-white shadow' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'}`;
    });
    document.querySelectorAll('[data-ef-pane]').forEach((p) => { p.style.display = p.dataset.efPane === state.tab ? '' : 'none'; });
    if (tab.id === 'dependentes') document.getElementById('ef-pane-dependentes').innerHTML = depsHtml();
    if (window.lucide) lucide.createIcons();
  }

  // Grava os valores digitados no estado antes de redesenhar/salvar
  function coletar() {
    TABS.forEach((t) => t.fields.forEach(([key, , type]) => {
      if (key === '_h') return;
      const el = document.getElementById(fid(key));
      if (!el) return;
      let v = el.value;
      if (NUMERIC.has(key)) v = v === '' ? null : parseFloat(v);
      else if (INTS.has(key)) v = v === '' ? 0 : parseInt(v, 10);
      else v = v.trim();
      state.emp[key] = v;
    }));
    ['dependents', 'filhos_sal_familia'].forEach((k) => {
      const el = document.getElementById(fid(k));
      if (el && !el.disabled) state.emp[k] = parseInt(el.value || 0, 10);
    });
  }

  window.efTab = (id) => {
    coletar(); state.tab = id; renderTab();
    const body = document.getElementById('ef-body'); if (body) body.scrollTop = 0;
  };

  async function openEmpForm(id) {
    state.tab = 'pessoais';
    state.deps = [];
    if (id) {
      let emp = (typeof dpEmployees !== 'undefined' ? dpEmployees : []).find((e) => e.id === id);
      try {
        const r = await fetch(`/api/dp/employees/${id}`, { headers: authHeaders() });
        if (r.ok) emp = await r.json();
        const d = await fetch(`/api/dp/employees/${id}/dependents`, { headers: authHeaders() });
        if (d.ok) state.deps = await d.json();
      } catch { /* usa o cache local */ }
      if (!emp) { alert('Erro ao carregar funcionário.'); return; }
      state.emp = { ...emp };
    } else {
      state.emp = { ...DEFAULTS };
      window._newEmpPhotoBase64 = null;
    }
    const e = state.emp;
    const foto = e.photo ? `<img src="${e.photo}" style="width:100%;height:100%;object-fit:cover">`
      : `<div style="text-align:center;color:#9ca3af"><i data-lucide="camera" style="width:24px;height:24px;margin:0 auto 2px;display:block"></i><span style="font-size:9px">Foto 3x4</span></div>`;
    const previewId = id ? 'edit-emp-photo-preview' : 'new-emp-photo-preview';
    const onPhoto = id ? `empPhotoPreview(${id}, this)` : 'newEmpPhotoPreview(this)';

    openModal(`
      <div class="bg-white dark:bg-slate-900 rounded-2xl w-full overflow-hidden flex flex-col max-h-[90vh]">
        <div class="shrink-0 flex items-center gap-4 p-5 [@media(max-height:640px)]:py-3 bg-gradient-to-r from-violet-600 to-indigo-600 text-white">
          <div>
            <div id="${previewId}" onclick="document.getElementById('ef-photo-input').click()" title="Alterar foto"
              style="width:66px;height:88px;border-radius:6px;overflow:hidden;background:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;border:2px solid rgba(255,255,255,.6)">${foto}</div>
            <input type="file" id="ef-photo-input" accept="image/*" style="display:none" onchange="${onPhoto}">
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-[11px] uppercase tracking-wider opacity-80">${id ? 'Ficha do empregado' : 'Admissão de empregado'}</div>
            <div class="text-xl font-bold truncate">${esc(e.name || 'Novo funcionário')}</div>
            <div class="text-xs opacity-90 mt-0.5">${id ? `Matrícula ${esc(e.matricula || '—')} · ${esc(e.role || '')} · ${e.active === 0 ? 'Inativo' : 'Ativo'}` : 'Preencha as abas; campos com * são obrigatórios.'}</div>
          </div>
          <button onclick="closeModal()" class="self-start opacity-80 hover:opacity-100"><i data-lucide="x" class="w-5 h-5"></i></button>
        </div>
        <div class="shrink-0 flex gap-1 px-4 py-2 border-b border-slate-100 dark:border-slate-800 overflow-x-auto custom-scroll">
          ${TABS.map((t) => `<button data-ef-tab="${t.id}" onclick="efTab('${t.id}')"><i data-lucide="${t.icon}" class="w-3.5 h-3.5"></i>${t.label}</button>`).join('')}
        </div>
        <div id="ef-body" class="flex-1 min-h-0 overflow-y-auto custom-scroll p-5 [@media(max-height:640px)]:p-4">
          ${TABS.map((t) => `<div data-ef-pane="${t.id}" id="ef-pane-${t.id}" class="grid grid-cols-1 md:grid-cols-4 gap-4" style="display:none">
            ${t.fields.map(fieldHtml).join('')}</div>`).join('')}
        </div>
        <div class="shrink-0 flex items-center justify-between gap-3 px-5 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30">
          <div class="flex items-center gap-4 text-[11px] text-slate-400">${id ? `
            <button onclick="openAuthDoc('/api/dp/employees/${id}/documento/ficha-registro')"
              class="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-800">
              <i data-lucide="printer" class="w-3.5 h-3.5"></i> Imprimir ficha</button>
            <button onclick="esEnviarCentral('/api/esocial/gerar/admissao/${id}')" class="text-indigo-500 hover:underline" title="Gera o S-2200 na Central do eSocial">Enviar admissão ao eSocial</button>` : ''}</div>
          <div class="flex gap-3">
            <button onclick="closeModal()" class="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
            <button onclick="efSalvar(${id || 0})" class="bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold px-5 py-2 rounded-xl flex items-center gap-2">
              <i data-lucide="save" class="w-4 h-4"></i> ${id ? 'Salvar alterações' : 'Admitir funcionário'}</button>
          </div>
        </div>
      </div>`);
    const box = document.getElementById('modal-box');
    if (box) { box.classList.remove('max-w-3xl', 'p-6', 'overflow-y-auto'); box.classList.add('max-w-5xl', 'p-0', 'rounded-2xl', 'overflow-hidden'); }
    renderTab();
  }

  // ── Validações ────────────────────────────────────────────
  function cpfValido(c) {
    c = String(c || '').replace(/\D/g, '');
    if (c.length !== 11 || /^(\d)\1+$/.test(c)) return false;
    for (let t = 9; t < 11; t++) {
      let s = 0;
      for (let i = 0; i < t; i++) s += +c[i] * (t + 1 - i);
      if (((s * 10) % 11) % 10 !== +c[t]) return false;
    }
    return true;
  }
  function pisValido(p) {
    p = String(p || '').replace(/\D/g, '');
    if (p.length !== 11) return false;
    const pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const r = 11 - (pesos.reduce((s, w, i) => s + w * +p[i], 0) % 11);
    return (r >= 10 ? 0 : r) === +p[10];
  }
  const TAB_DO_CAMPO = {};
  TABS.forEach((t) => t.fields.forEach(([k]) => { TAB_DO_CAMPO[k] = t.id; }));
  function falha(campo, msg) {
    state.tab = TAB_DO_CAMPO[campo] || state.tab;
    renderTab();
    const el = document.getElementById(fid(campo));
    if (el) { el.focus(); el.classList.add('ring-2', 'ring-rose-400'); }
    alert(msg);
    return false;
  }
  function validar(e) {
    if (!e.name) return falha('name', 'Informe o nome completo.');
    if (!e.cpf) return falha('cpf', 'Informe o CPF.');
    if (!cpfValido(e.cpf)) return falha('cpf', 'CPF inválido. Confira os dígitos.');
    if (e.pis_pasep && !pisValido(e.pis_pasep)) return falha('pis_pasep', 'PIS/PASEP inválido. Confira os dígitos.');
    if (!e.admission_date) return falha('admission_date', 'Informe a data de admissão.');
    if (!e.role) return falha('role', 'Informe o cargo.');
    if (!(e.salary > 0)) return falha('salary', 'Informe o salário base.');
    if (e.birth_date && e.admission_date) {
      const idade = (new Date(e.admission_date) - new Date(e.birth_date)) / (365.25 * 864e5);
      if (idade < 14) return falha('birth_date', 'Idade na admissão menor que 14 anos.');
      if (idade < 16 && e.esocial_category !== '103') return falha('esocial_category', 'Menor de 16 anos só pode ser admitido como aprendiz (categoria 103).');
    }
    if (e.tipo_contrato === 'experiencia' && !e.experiencia_dias) return falha('experiencia_dias', 'Informe o prazo da experiência.');
    if ((e.experiencia_dias || 0) + (e.experiencia_prorrogacao || 0) > 90) return falha('experiencia_prorrogacao', 'Experiência com prorrogação não pode passar de 90 dias (CLT art. 445).');
    if (e.tipo_contrato === 'determinado' && !e.data_termino_contrato) return falha('data_termino_contrato', 'Informe o término do contrato por prazo determinado.');
    return true;
  }

  window.efSalvar = async (id) => {
    coletar();
    const e = state.emp;
    if (!validar(e)) return;
    if (e.logradouro) {
      e.address = [`${e.logradouro}, ${e.numero || 'S/N'}`, e.complemento, e.bairro,
        e.cidade && `${e.cidade}${e.uf ? '/' + e.uf : ''}`].filter(Boolean).join(' - ');
    }
    const payload = {};
    TABS.forEach((t) => t.fields.forEach(([k]) => { if (k !== '_h' && k in e) payload[k] = e[k]; }));
    ['address', 'dependents', 'filhos_sal_familia'].forEach((k) => { if (e[k] !== undefined) payload[k] = e[k]; });
    payload.is_prolabore = !!e.is_prolabore;
    if (!payload.cbo) delete payload.cbo;
    if (!payload.matricula) delete payload.matricula;
    if (payload.vt_monthly == null) payload.vt_monthly = 0;

    try {
      const r = await fetch(id ? `/api/dp/employees/${id}` : '/api/dp/employees', {
        method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        const msg = Array.isArray(err.detail) ? err.detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join('\n') : err.detail;
        alert(msg || 'Erro ao salvar.');
        return;
      }
      let emp = await r.json();
      if (!id) {
        // dependentes digitados antes de existir o cadastro
        for (const d of state.deps) {
          await fetch(`/api/dp/employees/${emp.id}/dependents`, {
            method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify(d),
          });
        }
        if (window._newEmpPhotoBase64) {
          await fetch(`/api/dp/employees/${emp.id}/photo`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
            body: JSON.stringify({ photo: window._newEmpPhotoBase64 }),
          });
          window._newEmpPhotoBase64 = null;
        }
        if (state.deps.length) {
          const rr = await fetch(`/api/dp/employees/${emp.id}`, { headers: authHeaders() });
          if (rr.ok) emp = await rr.json();
        }
      }
      if (typeof dpEmployees !== 'undefined') {
        const idx = dpEmployees.findIndex((x) => x.id === emp.id);
        if (idx >= 0) dpEmployees[idx] = emp; else dpEmployees.push(emp);
      }
      closeModal();
      if (window.showToast) showToast(id ? 'Ficha atualizada.' : 'Funcionário admitido.', 'success');
      if (window.switchDpTab) await switchDpTab('funcionarios', true);
      if (window.lucide) lucide.createIcons();
    } catch { alert('Erro de conexão.'); }
  };

  // ── Dependentes ───────────────────────────────────────────
  const depVal = (k) => document.getElementById(`ef-dep-${k}`);
  window.efDepEditar = (i) => {
    const d = state.deps[i];
    depVal('idx').value = i; depVal('nome').value = d.nome || ''; depVal('parentesco').value = d.parentesco || '03';
    depVal('nasc').value = d.data_nascimento || ''; depVal('cpf').value = d.cpf || ''; depVal('sexo').value = d.sexo || '';
    depVal('irrf').checked = !!d.irrf; depVal('sf').checked = !!d.salario_familia; depVal('plano').checked = !!d.plano_saude;
    document.getElementById('ef-dep-btn').textContent = 'Salvar dependente';
    depVal('nome').focus();
  };
  window.efDepSalvar = async () => {
    const d = {
      nome: depVal('nome').value.trim(), parentesco: depVal('parentesco').value, data_nascimento: depVal('nasc').value,
      cpf: depVal('cpf').value.trim(), sexo: depVal('sexo').value, irrf: depVal('irrf').checked ? 1 : 0,
      salario_familia: depVal('sf').checked ? 1 : 0, plano_saude: depVal('plano').checked ? 1 : 0,
    };
    if (d.nome.length < 2) { alert('Informe o nome do dependente.'); return; }
    if (d.cpf && !cpfValido(d.cpf)) { alert('CPF do dependente inválido.'); return; }
    if (d.salario_familia && !['03', '04', '10'].includes(d.parentesco)) {
      alert('Salário-família só vale para filho, enteado ou menor sob guarda.'); return;
    }
    const idx = depVal('idx').value === '' ? -1 : +depVal('idx').value;
    coletar();
    const empId = state.emp.id;
    if (empId) {
      const atual = idx >= 0 ? state.deps[idx] : null;
      const r = await fetch(`/api/dp/employees/${empId}/dependents${atual ? '/' + atual.id : ''}`, {
        method: atual ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify(d),
      });
      if (!r.ok) { const e = await r.json().catch(() => ({})); alert(e.detail || 'Erro ao salvar dependente.'); return; }
      const salvo = await r.json();
      if (idx >= 0) state.deps[idx] = salvo; else state.deps.push(salvo);
      await efAtualizarTotais(empId);
    } else {
      if (idx >= 0) state.deps[idx] = d; else state.deps.push(d);
      efTotaisLocais();
    }
    renderTab();
  };
  window.efDepRemover = async (i) => {
    const d = state.deps[i];
    if (!confirm(`Excluir o dependente "${d.nome}"?`)) return;
    coletar();
    if (state.emp.id && d.id) {
      await fetch(`/api/dp/employees/${state.emp.id}/dependents/${d.id}`, { method: 'DELETE', headers: authHeaders() });
      state.deps.splice(i, 1);
      await efAtualizarTotais(state.emp.id);
    } else {
      state.deps.splice(i, 1);
      efTotaisLocais();
    }
    renderTab();
  };
  async function efAtualizarTotais(empId) {
    try {
      const r = await fetch(`/api/dp/employees/${empId}`, { headers: authHeaders() });
      if (r.ok) {
        const e = await r.json();
        state.emp.dependents = e.dependents;
        state.emp.filhos_sal_familia = e.filhos_sal_familia;
      }
    } catch { /* mantém valores */ }
  }
  function efTotaisLocais() {
    const hoje = new Date();
    const menor14 = (n) => !n || (hoje - new Date(n + 'T00:00')) / (365.25 * 864e5) < 14;
    state.emp.dependents = state.deps.filter((d) => d.irrf).length;
    state.emp.filhos_sal_familia = state.deps.filter((d) => d.salario_familia && menor14(d.data_nascimento)).length;
  }

  // ── CEP (ViaCEP) e CBO ────────────────────────────────────
  window.efBuscarCep = async () => {
    const el = document.getElementById(fid('cep'));
    const cep = (el?.value || '').replace(/\D/g, '');
    if (cep.length !== 8) return;
    try {
      const r = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
      const d = await r.json();
      if (d.erro) return;
      const set = (k, v) => { const f = document.getElementById(fid(k)); if (f && v && !f.value) f.value = v; };
      set('logradouro', d.logradouro); set('bairro', d.bairro); set('cidade', d.localidade);
      set('uf', d.uf); set('cod_municipio', d.ibge);
      el.value = `${cep.slice(0, 5)}-${cep.slice(5)}`;
      document.getElementById(fid('numero'))?.focus();
    } catch { /* sem internet: preenchimento manual */ }
  };
  let cboTimer = null;
  window.efBuscarCbo = (q) => {
    clearTimeout(cboTimer);
    cboTimer = setTimeout(async () => {
      if (!q || q.length < 2) return;
      try {
        const r = await fetch(`/api/dp/cbo?q=${encodeURIComponent(q)}`, { headers: authHeaders() });
        const rows = await r.json();
        const dl = document.getElementById('ef-cbo-list');
        if (dl) dl.innerHTML = rows.map((c) => `<option value="${esc(c.codigo)}">${esc(c.descricao)}</option>`).join('');
      } catch { /* ignora */ }
    }, 250);
  };

  window.openEmpForm = openEmpForm;
  window.openNewEmpModal = () => openEmpForm(null);
  window.openEditEmpModal = (id) => openEmpForm(id);
})();
