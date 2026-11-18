// ============================================================
// DEPARTAMENTO PESSOAL — Utilitários e rotinas automáticas (bloco 5 da paridade)
// Pagamentos (folha no contas a pagar), alteração e exclusão em grupo, acerto da data de pagamento
// e rotinas agendadas. Usa os helpers de dp.js (card2, inputCls, labelCls, _dpEsc, fBRL2, fDate2,
// dpEmployees, authHeaders) e de app.js (apiFetch, showToast).
// ============================================================

const _DU = '/api/dp/utilitarios';
let _duAba = 'pagamentos';
const _duV = id => document.getElementById(id)?.value ?? '';
const _duC = id => !!document.getElementById(id)?.checked;
const _duBtn = (txt, on, cor = 'violet', ic = '') =>
  `<button onclick="${on}" class="text-xs px-3 py-1.5 rounded-lg ${cor === 'violet' ? 'bg-violet-600 hover:bg-violet-700 text-white'
    : cor === 'red' ? 'border border-red-200 text-red-600 hover:bg-red-50 dark:hover:bg-red-950'
    : 'border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'} inline-flex items-center gap-1.5">${ic ? `<i data-lucide="${ic}" class="w-3.5 h-3.5"></i>` : ''}${txt}</button>`;
const _duTh = cols => `<thead><tr class="text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-200 dark:border-slate-800">${
  cols.map(c => `<th class="text-left py-2 px-2 font-semibold">${c}</th>`).join('')}</tr></thead>`;
const _duTd = (v, num) => `<td class="py-2 px-2 ${num ? 'text-right tabular-nums' : ''}">${v}</td>`;
const _duVazio = (n, txt) => `<tr><td colspan="${n}" class="py-6 text-center text-xs text-slate-400">${txt}</td></tr>`;
const _duMes = () => new Date().toISOString().slice(0, 7);
const _duStatus = s => {
  const m = { pago: ['Pago', 'emerald'], pendente: ['Pendente', 'amber'], nao_lancado: ['Não lançado', 'slate'],
              ok: ['OK', 'emerald'], ignorada: ['Ignorada', 'slate'], erro: ['Erro', 'red'] }[s] || [s || '-', 'slate'];
  return `<span class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-${m[1]}-100 text-${m[1]}-700 dark:bg-${m[1]}-950 dark:text-${m[1]}-300">${m[0]}</span>`;
};

async function _duApi(url, body, metodo = 'POST') {
  try { return await apiFetch(url, { method: metodo, body: body ? JSON.stringify(body) : undefined }); }
  catch (e) { showToast(e.message || 'Erro.', 'error'); return null; }
}

async function renderDpUtilitarios(el) {
  const abas = [['pagamentos', 'banknote', 'Pagamentos'], ['alteracao', 'users-round', 'Alteração em grupo'],
                ['exclusao', 'trash-2', 'Exclusão em grupo'], ['data_pg', 'calendar-clock', 'Data de pagamento'],
                ['rotinas', 'timer', 'Rotinas automáticas']];
  if (!el.id) el.id = 'du-host';
  el.innerHTML = `
    <div class="mb-4"><h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">Utilitários</h2>
      <p class="text-xs text-slate-400">Rotinas em lote da folha e tarefas que o sistema faz sozinho nos dias marcados.</p></div>
    <div class="flex gap-1 flex-wrap mb-4">${abas.map(([id, ic, t]) => `
      <button onclick="_duAba='${id}';renderDpUtilitarios(document.getElementById('${el.id}'))"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold ${_duAba === id
          ? 'bg-violet-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200'}">
        <i data-lucide="${ic}" class="w-3.5 h-3.5"></i>${t}</button>`).join('')}</div>
    <div id="du-corpo"></div>`;
  const corpo = document.getElementById('du-corpo');
  corpo.innerHTML = '<p class="text-xs text-slate-400">Carregando…</p>';
  ({ pagamentos: _duPagamentos, alteracao: _duAlteracao, exclusao: _duExclusao,
     data_pg: _duDataPg, rotinas: _duRotinas })[_duAba](corpo);
  if (window.lucide) lucide.createIcons();
}

// ── 1. PAGAMENTOS ────────────────────────────────────────────────────────────
let _duRun = '';
async function _duPagamentos(el) {
  let runs = [], contas = [];
  try {
    [runs, contas] = await Promise.all([
      fetch('/api/dp/payroll', { headers: authHeaders() }).then(r => r.json()),
      fetch('/api/bank-accounts', { headers: authHeaders() }).then(r => r.json()).catch(() => [])]);
  } catch { runs = []; }
  runs = (Array.isArray(runs) ? runs : []).filter(r => r.status !== 'cancelado');
  if (!_duRun && runs.length) _duRun = String(runs[0].id);
  const opt = runs.map(r => `<option value="${r.id}" ${String(r.id) === _duRun ? 'selected' : ''}>${_dpEsc(r.competence)} · ${_dpEsc(r.tipo || 'mensal')} (${r.employee_count || 0} func.)</option>`).join('')
    || '<option value="">Nenhuma folha processada</option>';
  const optContas = (Array.isArray(contas) ? contas : []).filter(c => c.active !== 0)
    .map(c => `<option value="${c.id}">${_dpEsc(c.name)}</option>`).join('');
  let tit = [];
  if (_duRun) {
    const d = await fetch(`${_DU}/financeiro/${_duRun}`, { headers: authHeaders() }).then(r => r.ok ? r.json() : null).catch(() => null);
    tit = d?.titulos || [];
  }
  const total = tit.reduce((s, t) => s + Number(t.valor || 0), 0);
  el.innerHTML = card2(`<div class="p-5">
    <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">Lança os líquidos, pensões, FGTS, INSS, IRRF e consignado da folha no
      contas a pagar, com os vencimentos legais: salário até o <b>5º dia útil</b> (sábado conta) e guias no <b>dia 20</b>
      (antecipado se não for dia útil). Lançar de novo não duplica.</p>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-end mb-4">
      <div class="md:col-span-2">${labelCls('Folha')}<select id="du-run" class="${inputCls()}"
        onchange="_duRun=this.value;_duPagamentos(document.getElementById('du-corpo'))">${opt}</select></div>
      <label class="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 pb-2">
        <input id="du-porfunc" type="checkbox"> Um título por funcionário</label>
    </div>
    <div class="overflow-x-auto"><table class="w-full text-xs">${_duTh(['Título', 'Vencimento', 'Valor', 'Situação'])}<tbody>
      ${tit.length ? tit.map(t => `<tr class="border-b border-slate-100 dark:border-slate-800">${_duTd(_dpEsc(t.descricao))}${_duTd(fDate2(t.vencimento))}${
        _duTd(fBRL2(t.valor), 1)}${_duTd(_duStatus(t.status))}</tr>`).join('')
        + `<tr class="font-semibold">${_duTd('Total')}${_duTd('')}${_duTd(fBRL2(total), 1)}${_duTd('')}</tr>`
        : _duVazio(4, 'Escolha uma folha processada.')}</tbody></table></div>
    <div class="flex flex-wrap gap-2 items-end mt-4">
      ${_duBtn('Lançar no contas a pagar', '_duGerar()', 'violet', 'file-plus-2')}
      <span class="flex-1"></span>
      <div>${labelCls('Conta do pagamento')}<select id="du-conta" class="${inputCls()}">${optContas || '<option value="">Cadastre uma conta</option>'}</select></div>
      <div>${labelCls('Data')}<input id="du-dtpg" type="date" value="${new Date().toISOString().slice(0, 10)}" class="${inputCls()}"></div>
      ${_duBtn('Dar baixa em todos', '_duBaixar()', 'cinza', 'check-check')}
    </div></div>`);
  if (window.lucide) lucide.createIcons();
}

async function _duGerar() {
  if (!_duRun) return;
  const r = await _duApi(`${_DU}/financeiro/${_duRun}/gerar`, { por_funcionario: _duC('du-porfunc') });
  if (r) { showToast(`${r.criados.length} título(s) lançado(s)${r.ja_existiam ? `, ${r.ja_existiam} já existiam` : ''}.`, 'success');
           _duPagamentos(document.getElementById('du-corpo')); }
}

async function _duBaixar() {
  if (!_duRun || !_duV('du-conta')) { showToast('Escolha a folha e a conta bancária.', 'error'); return; }
  if (!confirm('Dar baixa (pago) em todos os títulos pendentes desta folha?')) return;
  const r = await _duApi(`${_DU}/financeiro/${_duRun}/baixar`, { bank_account_id: Number(_duV('du-conta')), payment_date: _duV('du-dtpg') });
  if (r) { showToast('Baixa registrada.', 'success'); _duPagamentos(document.getElementById('du-corpo')); }
}

// ── 2. ALTERAÇÃO EM GRUPO ────────────────────────────────────────────────────
async function _duAlteracao(el) {
  const [escalas, ccts] = await Promise.all([
    fetch('/api/dp/work-schedules', { headers: authHeaders() }).then(r => r.json()).catch(() => []),
    fetch('/api/conventions/list', { headers: authHeaders() }).then(r => r.json()).catch(() => [])]);
  window._duListas = { escalas: Array.isArray(escalas) ? escalas : [], ccts: Array.isArray(ccts) ? ccts : (ccts.items || []) };
  const deps = [...new Set((dpEmployees || []).map(e => e.department).filter(Boolean))].sort();
  el.innerHTML = card2(`<div class="p-5">
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div>
        <div class="flex items-center justify-between mb-2">${labelCls('Funcionários')}
          <div class="flex gap-2 text-[11px]">
            <select id="du-dep" class="text-[11px] rounded border border-slate-200 dark:border-slate-700 bg-transparent px-1" onchange="_duMarcar(this.value)">
              <option value="">Marcar por departamento…</option>${deps.map(d => `<option>${_dpEsc(d)}</option>`).join('')}</select>
            <button class="text-violet-600" onclick="_duMarcar('*')">todos</button>
            <button class="text-slate-500" onclick="_duMarcar('')">nenhum</button></div></div>
        <div class="max-h-72 overflow-y-auto border border-slate-200 dark:border-slate-800 rounded-lg p-2 space-y-1">
          ${(dpEmployees || []).filter(e => e.active !== 0).map(e => `<label class="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200">
            <input type="checkbox" class="du-emp" value="${e.id}" data-dep="${_dpEsc(e.department || '')}">
            <span class="flex-1">${_dpEsc(e.name)}</span><span class="text-slate-400">${_dpEsc(e.department || '')}</span></label>`).join('')
            || '<p class="text-xs text-slate-400">Nenhum funcionário ativo.</p>'}</div>
      </div>
      <div class="space-y-3">
        <div>${labelCls('O que alterar')}<select id="du-campo" class="${inputCls()}" onchange="_duCampo()">
          <option value="salario">Salário</option><option value="role">Cargo</option><option value="cbo">CBO</option>
          <option value="department">Departamento</option><option value="centro_custo">Centro de custo</option>
          <option value="work_schedule_id">Escala / horário</option><option value="cct_id">Convenção coletiva</option>
          <option value="horas_semana">Horas semanais</option></select></div>
        <div id="du-campo-valor"></div>
        <div class="flex gap-2">${_duBtn('Prévia', '_duGrupo(false)', 'cinza', 'eye')}${_duBtn('Aplicar', '_duGrupo(true)', 'violet', 'check')}</div>
      </div>
    </div>
    <div id="du-previa" class="mt-5"></div></div>`);
  _duCampo();
}

function _duMarcar(dep) {
  document.querySelectorAll('.du-emp').forEach(c => { c.checked = dep === '*' ? true : dep ? (c.checked || c.dataset.dep === dep) : false; });
}

function _duCampo() {
  const c = _duV('du-campo'), L = window._duListas || { escalas: [], ccts: [] };
  const box = document.getElementById('du-campo-valor');
  if (c === 'salario') {
    box.innerHTML = `<div class="grid grid-cols-2 gap-3">
      <div>${labelCls('Forma')}<select id="du-modo" class="${inputCls()}"><option value="percentual">Reajuste em %</option>
        <option value="acrescimo">Acréscimo em R$</option><option value="novo">Novo salário (piso)</option></select></div>
      <div>${labelCls('Valor')}<input id="du-valor" type="number" step="0.01" class="${inputCls()}"></div>
      <div>${labelCls('Vigência')}<input id="du-vig" type="date" value="${new Date().toISOString().slice(0, 10)}" class="${inputCls()}"></div>
      <div>${labelCls('Motivo')}<select id="du-tipo" class="${inputCls()}"><option value="reajuste">Reajuste / dissídio</option>
        <option value="promocao">Promoção</option><option value="merito">Mérito</option><option value="enquadramento">Enquadramento</option></select></div>
      <label class="col-span-2 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
        <input id="du-abaixo" type="checkbox"> Só para quem ganha menos que o novo valor (piso)</label></div>`;
  } else if (c === 'work_schedule_id' || c === 'cct_id') {
    const lista = c === 'work_schedule_id' ? L.escalas.map(x => [x.id, x.nome]) : L.ccts.map(x => [x.id, `${x.categoria} — ${x.sindicato_empregados || ''}`]);
    box.innerHTML = `${labelCls(c === 'cct_id' ? 'Convenção' : 'Escala')}<select id="du-valor" class="${inputCls()}">
      <option value="">(nenhuma)</option>${lista.map(([id, n]) => `<option value="${id}">${_dpEsc(n)}</option>`).join('')}</select>`;
  } else {
    box.innerHTML = `${labelCls('Novo valor')}<input id="du-valor" ${c === 'horas_semana' ? 'type="number" step="0.5" min="1" max="44"' : ''} class="${inputCls()}">`;
  }
}

async function _duGrupo(aplicar) {
  const ids = [...document.querySelectorAll('.du-emp:checked')].map(c => Number(c.value));
  if (!ids.length) { showToast('Marque ao menos um funcionário.', 'error'); return; }
  const campo = _duV('du-campo');
  const body = { campo, valor: _duV('du-valor'), employee_ids: ids };
  if (campo === 'salario') Object.assign(body, { modo: _duV('du-modo'), somente_abaixo: _duC('du-abaixo'),
    data_vigencia: _duV('du-vig'), tipo: _duV('du-tipo'), motivo: 'Alteração em grupo' });
  if (aplicar && !confirm(`Aplicar a alteração em ${ids.length} funcionário(s)?`)) return;
  const r = await _duApi(`${_DU}/alteracao-grupo/${aplicar ? 'aplicar' : 'previa'}`, body);
  if (!r) return;
  const fmt = v => campo === 'salario' ? fBRL2(v) : _dpEsc(v ?? '—');
  document.getElementById('du-previa').innerHTML = `
    <h4 class="text-xs font-bold text-slate-700 dark:text-slate-200 mb-2">${aplicar ? 'Alteração aplicada' : 'Prévia'} — ${_dpEsc(r.rotulo)}: ${r.alterados} mudança(s)</h4>
    ${(r.avisos || []).map(a => `<p class="text-[11px] text-amber-600 mb-1">⚠ ${_dpEsc(a)}</p>`).join('')}
    <table class="w-full text-xs">${_duTh(['Funcionário', 'Antes', 'Depois', ''])}<tbody>${r.linhas.map(l => `
      <tr class="border-b border-slate-100 dark:border-slate-800 ${l.muda ? '' : 'opacity-50'}">${_duTd(_dpEsc(l.nome))}${_duTd(fmt(l.antes))}${
        _duTd(fmt(l.depois))}${_duTd(l.muda ? '' : 'sem mudança')}</tr>`).join('')}</tbody></table>`;
  if (aplicar) { showToast('Alteração aplicada.', 'success'); fetch('/api/dp/employees?active_only=false', { headers: authHeaders() }).then(r => r.json()).then(l => { if (Array.isArray(l)) dpEmployees = l; }).catch(() => {}); }
}

// ── 3. EXCLUSÃO EM GRUPO ─────────────────────────────────────────────────────
async function _duExclusao(el) {
  const ano = new Date().getFullYear();
  el.innerHTML = card2(`<div class="p-5">
    <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">Exclui vários cálculos de uma vez pela mesma rotina da exclusão individual
      (a rescisão excluída reativa o funcionário). Não exclui de competência fechada nem rescisão com S-2299 aceito.</p>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
      <div>${labelCls('Tipo')}<select id="du-ex-tipo" class="${inputCls()}"><option value="ferias">Férias</option>
        <option value="decimo_1">13º — 1ª parcela</option><option value="decimo_2">13º — 2ª parcela</option>
        <option value="rescisao">Rescisões</option><option value="rpa">RPA (autônomos)</option></select></div>
      <div>${labelCls('De')}<input id="du-ex-ini" type="date" value="${ano}-01-01" class="${inputCls()}"></div>
      <div>${labelCls('Até')}<input id="du-ex-fim" type="date" value="${ano}-12-31" class="${inputCls()}"></div>
      <div>${_duBtn('Buscar', '_duExBuscar()', 'cinza', 'search')}</div>
    </div><div id="du-ex-lista" class="mt-4"></div></div>`);
  if (window.lucide) lucide.createIcons();
}

async function _duExBuscar() {
  const q = `tipo=${_duV('du-ex-tipo')}&inicio=${_duV('du-ex-ini')}&fim=${_duV('du-ex-fim')}`;
  const lista = await _duApi(`${_DU}/exclusao-grupo?${q}`, null, 'GET');
  if (!lista) return;
  document.getElementById('du-ex-lista').innerHTML = `<table class="w-full text-xs">${_duTh([
      `<input type="checkbox" onchange="document.querySelectorAll('.du-ex').forEach(c=>c.checked=this.checked)">`, 'Nome', 'Competência', 'Data', 'Líquido'])}<tbody>
    ${lista.length ? lista.map(x => `<tr class="border-b border-slate-100 dark:border-slate-800" id="du-ex-${x.id}">
      ${_duTd(`<input type="checkbox" class="du-ex" value="${x.id}">`)}${_duTd(_dpEsc(x.nome))}${_duTd(_dpEsc(x.competencia || ''))}${
      _duTd(fDate2(x.data))}${_duTd(fBRL2(x.liquido), 1)}</tr>`).join('') : _duVazio(5, 'Nada encontrado no período.')}</tbody></table>
    ${lista.length ? `<div class="mt-3">${_duBtn('Excluir selecionados', '_duExExcluir()', 'red', 'trash-2')}</div>` : ''}`;
  if (window.lucide) lucide.createIcons();
}

async function _duExExcluir() {
  const ids = [...document.querySelectorAll('.du-ex:checked')].map(c => Number(c.value));
  if (!ids.length) { showToast('Marque o que excluir.', 'error'); return; }
  if (!confirm(`Excluir ${ids.length} cálculo(s)? Esta ação não pode ser desfeita.`)) return;
  const r = await _duApi(`${_DU}/exclusao-grupo`, { tipo: _duV('du-ex-tipo'), ids });
  if (!r) return;
  const falhas = r.resultado.filter(x => !x.ok);
  showToast(`${r.excluidos} excluído(s)${falhas.length ? `, ${falhas.length} não` : ''}.`, falhas.length ? 'warning' : 'success');
  if (falhas.length) alert(falhas.map(f => `#${f.id}: ${f.erro}`).join('\n'));
  _duExBuscar();
}

// ── 4. DATA DE PAGAMENTO ─────────────────────────────────────────────────────
let _duPgComp = _duMes();
async function _duDataPg(el) {
  const lista = await fetch(`${_DU}/data-pagamento?competencia=${_duPgComp}`, { headers: authHeaders() })
    .then(r => r.ok ? r.json() : []).catch(() => []);
  const rot = { folha: 'Folha', especial: 'Recibo', rpa: 'RPA' };
  el.innerHTML = card2(`<div class="p-5">
    <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">Corrige a data em que a folha, os recibos ou os RPA foram pagos. Essa data
      define o mês do IRRF (regime de caixa) e do S-1210; os títulos pendentes de líquido e pensão no contas a pagar acompanham.</p>
    <div class="flex flex-wrap gap-3 items-end mb-4">
      <div>${labelCls('Competência')}<input type="month" value="${_duPgComp}" class="${inputCls()}"
        onchange="_duPgComp=this.value;_duDataPg(document.getElementById('du-corpo'))"></div></div>
    <table class="w-full text-xs">${_duTh([`<input type="checkbox" onchange="document.querySelectorAll('.du-pg').forEach(c=>c.checked=this.checked)">`,
      'Tipo', 'Descrição', 'Pessoas', 'Pago em'])}<tbody>
      ${lista.length ? lista.map(x => `<tr class="border-b border-slate-100 dark:border-slate-800">
        ${_duTd(`<input type="checkbox" class="du-pg" data-tipo="${x.tipo}" value="${x.id}">`)}${_duTd(rot[x.tipo] || x.tipo)}${
        _duTd(_dpEsc(x.descricao))}${_duTd(x.qtd, 1)}${_duTd(fDate2(x.data_pagamento))}</tr>`).join('') : _duVazio(5, 'Nada calculado nesta competência.')}
    </tbody></table>
    <div class="flex flex-wrap gap-2 items-end mt-4">
      <div>${labelCls('Nova data de pagamento')}<input id="du-pg-nova" type="date" class="${inputCls()}"></div>
      ${_duBtn('Alterar data', '_duPgAplicar(false)', 'violet', 'calendar-check')}</div></div>`);
  if (window.lucide) lucide.createIcons();
}

async function _duPgAplicar(confirmar) {
  const itens = [...document.querySelectorAll('.du-pg:checked')].map(c => ({ tipo: c.dataset.tipo, id: Number(c.value) }));
  if (!itens.length || !_duV('du-pg-nova')) { showToast('Marque os itens e informe a nova data.', 'error'); return; }
  const r = await fetch(`${_DU}/data-pagamento`, { method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ nova_data: _duV('du-pg-nova'), itens, confirmar }) });
  const j = await r.json().catch(() => ({}));
  if (r.status === 409 && j.detail?.avisos) {
    if (confirm(`${j.detail.mensagem}\n\n${j.detail.avisos.join('\n')}\n\nAlterar mesmo assim?`)) _duPgAplicar(true);
    return;
  }
  if (!r.ok) { showToast(typeof j.detail === 'string' ? j.detail : 'Erro ao alterar.', 'error'); return; }
  showToast(`${j.alterados} item(ns) com a nova data.`, 'success');
  if (j.avisos?.length) alert(j.avisos.join('\n'));
  _duDataPg(document.getElementById('du-corpo'));
}

// ── 5. ROTINAS AUTOMÁTICAS ───────────────────────────────────────────────────
async function _duRotinas(el) {
  const d = await fetch(`${_DU}/rotinas`, { headers: authHeaders() }).then(r => r.json()).catch(() => null);
  if (!d) { el.innerHTML = '<p class="text-xs text-red-500">Não foi possível carregar as rotinas.</p>'; return; }
  window._duRot = d;
  const quando = s => s ? `${fDate2(s)} ${s.slice(11, 16)}` : '—';
  el.innerHTML = `<div class="space-y-4">${card2(`<div class="p-5">
    <div class="flex items-center justify-between mb-3"><h3 class="font-bold text-sm text-slate-800 dark:text-slate-100">Rotinas agendadas</h3>
      ${_duBtn('Nova rotina', '_duRotForm()', 'violet', 'plus')}</div>
    <p class="text-[11px] text-slate-400 mb-3">O servidor confere a cada 5 minutos se há rotina vencida. No plano gratuito do Render o
      servidor dorme sem uso; nesse caso use um agendador externo chamando <code>/api/dp/utilitarios/rotinas/executar-pendentes</code>
      com o cabeçalho <code>X-Cron-Token</code>.</p>
    <table class="w-full text-xs">${_duTh(['Rotina', 'Quando', 'Competência', 'Próxima', 'Última', ''])}<tbody>
      ${d.rotinas.length ? d.rotinas.map(r => `<tr class="border-b border-slate-100 dark:border-slate-800 ${r.ativo ? '' : 'opacity-50'}">
        ${_duTd(_dpEsc(r.tipo_nome))}${_duTd(`dia ${r.dia} às ${_dpEsc(r.hora)}`)}${_duTd(_dpEsc(d.competencias[r.competencia] || r.competencia))}${
        _duTd(r.ativo ? quando(r.proxima_execucao) : 'desativada')}${_duTd(r.ultima_execucao ? `${_duStatus(r.ultimo_status)} <span class="text-slate-400">${quando(r.ultima_execucao)}</span>` : '—')}
        <td class="py-2 px-2 text-right whitespace-nowrap">${_duBtn('Executar agora', `_duRotExec(${r.id})`, 'cinza', 'play')}
          ${_duBtn('', `_duRotForm(${r.id})`, 'cinza', 'pencil')} ${_duBtn('', `_duRotExcluir(${r.id})`, 'red', 'trash-2')}</td></tr>`).join('')
        : _duVazio(6, 'Nenhuma rotina. Ex.: calcular a folha no dia 25, enviar holerites e lançar no financeiro no dia 1.')}
    </tbody></table></div>`)}
    ${card2(`<div class="p-5"><h3 class="font-bold text-sm text-slate-800 dark:text-slate-100 mb-3">Últimas execuções</h3>
      <table class="w-full text-xs">${_duTh(['Quando', 'Rotina', 'Competência', 'Situação', 'Resultado', 'Origem'])}<tbody>
      ${d.execucoes.length ? d.execucoes.map(x => `<tr class="border-b border-slate-100 dark:border-slate-800">${_duTd(quando(x.inicio))}${
        _duTd(_dpEsc(d.tipos[x.tipo] || x.tipo))}${_duTd(_dpEsc(x.competencia))}${_duTd(_duStatus(x.status))}${_duTd(_dpEsc(x.mensagem))}${
        _duTd(`<span class="text-slate-400">${_dpEsc(x.origem)}</span>`)}</tr>`).join('') : _duVazio(6, 'Nenhuma execução ainda.')}
      </tbody></table></div>`)}</div>`;
  if (window.lucide) lucide.createIcons();
}

function _duRotForm(id) {
  const d = window._duRot, r = id ? d.rotinas.find(x => x.id === id) : { tipo: 'calcular_folha', dia: 25, hora: '08:00', competencia: 'atual', ativo: 1 };
  document.getElementById('du-modal')?.remove();
  const m = document.createElement('div');
  m.id = 'du-modal';
  m.className = 'fixed inset-0 z-50 bg-black/40 flex items-start justify-center overflow-y-auto p-4';
  m.innerHTML = `<div class="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md my-16 border border-slate-200 dark:border-slate-800">
    <div class="px-5 py-3 border-b border-slate-200 dark:border-slate-800 font-bold text-slate-800 dark:text-slate-100">${id ? 'Editar' : 'Nova'} rotina</div>
    <div class="p-5 grid grid-cols-2 gap-3">
      <div class="col-span-2">${labelCls('Rotina')}<select id="du-r-tipo" class="${inputCls()}">${Object.entries(d.tipos).map(([k, v]) =>
        `<option value="${k}" ${k === r.tipo ? 'selected' : ''}>${_dpEsc(v)}</option>`).join('')}</select></div>
      <div>${labelCls('Dia do mês')}<input id="du-r-dia" type="number" min="1" max="31" value="${r.dia}" class="${inputCls()}"></div>
      <div>${labelCls('Hora')}<input id="du-r-hora" type="time" value="${r.hora}" class="${inputCls()}"></div>
      <div class="col-span-2">${labelCls('Competência')}<select id="du-r-comp" class="${inputCls()}">${Object.entries(d.competencias).map(([k, v]) =>
        `<option value="${k}" ${k === r.competencia ? 'selected' : ''}>${_dpEsc(v)}</option>`).join('')}</select>
        <p class="text-[10px] text-slate-400 mt-1">Para o dia 1 a 5 do mês, use "mês anterior" (folha do mês que acabou).</p></div>
      <label class="col-span-2 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
        <input id="du-r-ativo" type="checkbox" ${r.ativo ? 'checked' : ''}> Ativa</label></div>
    <div class="flex justify-end gap-2 px-5 py-3 border-t border-slate-200 dark:border-slate-800">
      ${_duBtn('Cancelar', "document.getElementById('du-modal').remove()", 'cinza')}${_duBtn('Salvar', `_duRotSalvar(${id || 0})`)}</div></div>`;
  document.body.appendChild(m);
}

async function _duRotSalvar(id) {
  const body = { tipo: _duV('du-r-tipo'), dia: Number(_duV('du-r-dia')), hora: _duV('du-r-hora'),
                 competencia: _duV('du-r-comp'), ativo: _duC('du-r-ativo') };
  const r = await _duApi(id ? `${_DU}/rotinas/${id}` : `${_DU}/rotinas`, body, id ? 'PUT' : 'POST');
  if (r) { document.getElementById('du-modal')?.remove(); showToast('Rotina salva.', 'success'); _duRotinas(document.getElementById('du-corpo')); }
}

async function _duRotExec(id) {
  if (!confirm('Executar esta rotina agora?')) return;
  const r = await _duApi(`${_DU}/rotinas/${id}/executar`, {});
  if (r) { showToast(r.mensagem || r.status, r.status === 'erro' ? 'error' : 'success'); _duRotinas(document.getElementById('du-corpo')); }
}

async function _duRotExcluir(id) {
  if (!confirm('Excluir esta rotina?')) return;
  if (await _duApi(`${_DU}/rotinas/${id}`, null, 'DELETE')) _duRotinas(document.getElementById('du-corpo'));
}
