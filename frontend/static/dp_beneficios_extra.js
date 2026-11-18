// ============================================================
// DEPARTAMENTO PESSOAL — Benefícios (bloco 4): vale-transporte, plano de saúde e consignado
// Abas dentro de DP › Benefícios. Usa os helpers de dp.js: card2, inputCls, labelCls, _dpEsc,
// fBRL2, fDate2, dpEmployees, openAuthDoc, authHeaders e apiFetch/showToast de app.js.
// ============================================================

const _BFX = '/api/dp/beneficios';
const _bfxMes = () => new Date().toISOString().slice(0, 7);
const _bfxEmpOpts = (sel = '', vazio = 'Selecione…') => `<option value="">${vazio}</option>` +
  (dpEmployees || []).filter(e => e.active !== 0).map(e =>
    `<option value="${e.id}" ${String(sel) === String(e.id) ? 'selected' : ''}>${_dpEsc(e.name)}</option>`).join('');
const _bfxBtn = (txt, on, cor = 'violet', ic = '') =>
  `<button onclick="${on}" class="text-xs px-3 py-1.5 rounded-lg ${cor === 'violet' ? 'bg-violet-600 hover:bg-violet-700 text-white'
    : cor === 'red' ? 'border border-red-200 text-red-600 hover:bg-red-50 dark:hover:bg-red-950'
    : 'border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'} inline-flex items-center gap-1.5">${ic ? `<i data-lucide="${ic}" class="w-3.5 h-3.5"></i>` : ''}${txt}</button>`;
const _bfxTh = cols => `<thead><tr class="text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-200 dark:border-slate-800">${
  cols.map(c => `<th class="text-left py-2 px-2 font-semibold">${c}</th>`).join('')}</tr></thead>`;
const _bfxTd = (v, num) => `<td class="py-2 px-2 ${num ? 'text-right tabular-nums' : ''}">${v}</td>`;
const _bfxVazio = (n, txt) => `<tr><td colspan="${n}" class="py-6 text-center text-xs text-slate-400">${txt}</td></tr>`;

async function _bfxPost(url, body, metodo = 'POST') {
  try { return await apiFetch(url, { method: metodo, body: body ? JSON.stringify(body) : undefined }); }
  catch (e) { showToast(e.message || 'Erro ao salvar.', 'error'); return null; }
}

async function _bfxCsv(url, nome) {
  try {
    const r = await fetch(url, { headers: { ...authHeaders(), Authorization: `Bearer ${localStorage.getItem('cortex_token') || ''}` } });
    if (!r.ok) { const j = await r.json().catch(() => ({})); alert(j.detail || 'Erro ao gerar a planilha.'); return; }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await r.blob()); a.download = nome;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  } catch { alert('Erro de conexão.'); }
}

function _bfxModal(titulo, corpo, onSalvar) {
  document.getElementById('bfx-modal')?.remove();
  const d = document.createElement('div');
  d.id = 'bfx-modal';
  d.className = 'fixed inset-0 z-50 bg-black/40 flex items-start justify-center overflow-y-auto p-4';
  d.innerHTML = `<div class="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-2xl my-8 border border-slate-200 dark:border-slate-800">
    <div class="flex items-center justify-between px-5 py-3 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-slate-800 dark:text-slate-100">${titulo}</h3>
      <button onclick="document.getElementById('bfx-modal').remove()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-4 h-4"></i></button></div>
    <div class="p-5">${corpo}</div>
    <div class="flex justify-end gap-2 px-5 py-3 border-t border-slate-200 dark:border-slate-800">
      ${_bfxBtn('Cancelar', "document.getElementById('bfx-modal').remove()", 'cinza')}
      <button id="bfx-salvar" class="text-xs px-4 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white">Salvar</button></div></div>`;
  document.body.appendChild(d);
  d.querySelector('#bfx-salvar').onclick = async () => { if (await onSalvar()) d.remove(); };
  if (window.lucide) lucide.createIcons();
}

const _bfxV = id => document.getElementById(id)?.value ?? '';
const _bfxC = id => !!document.getElementById(id)?.checked;

// ── VALE-TRANSPORTE ──────────────────────────────────────────────────────────
let _bfxVtComp = _bfxMes();

async function renderBfVT(el) {
  let dados = { linhas: [], previa: [] };
  try { dados = await apiFetch(`${_BFX}/vt/linhas?competencia=${_bfxVtComp}`); } catch (e) { showToast(e.message, 'error'); }
  const prev = Object.fromEntries((dados.previa || []).map(p => [p.employee_id, p]));
  const tot = (dados.previa || []).reduce((s, p) => ({ c: s.c + p.custo, d: s.d + p.desconto, e: s.e + p.empresa }), { c: 0, d: 0, e: 0 });
  const linhas = (dados.linhas || []).map(l => {
    const p = prev[l.employee_id];
    return `<tr class="border-b border-slate-100 dark:border-slate-800 ${l.ativo ? '' : 'opacity-50'}">
      ${_bfxTd(_dpEsc(l.employee_name))}${_bfxTd(_dpEsc(l.descricao))}${_bfxTd(fBRL2(l.tarifa), 1)}
      ${_bfxTd(l.vales_dia, 1)}${_bfxTd(l.dias_mes ? `${l.dias_mes} (fixo)` : (p ? `${p.dias_uso} (auto)` : '—'), 1)}
      ${_bfxTd(fBRL2(l.tarifa * l.vales_dia * (l.dias_mes || (p ? p.dias_uso : 0))), 1)}
      <td class="py-2 px-2 text-right whitespace-nowrap">${_bfxBtn('Editar', `_bfxVtForm(${l.id})`, 'cinza')} ${_bfxBtn('Excluir', `_bfxVtExcluir(${l.id})`, 'red')}</td></tr>`;
  }).join('');
  window._bfxVtLinhas = dados.linhas || [];
  el.innerHTML = `
    <div class="flex flex-wrap items-end justify-between gap-3 mb-4">
      <div><h3 class="font-bold text-slate-800 dark:text-slate-100">Vale-transporte</h3>
        <p class="text-xs text-slate-400 max-w-2xl">Os dias de uso saem do calendário: segunda a sexta, sem feriados, férias, afastamentos e faltas.
        O desconto é de 6% do salário básico, limitado ao custo do vale (Lei 7.418/85), e entra sozinho na folha.</p></div>
      <div class="flex items-end gap-2">
        <div>${labelCls('Competência')}<input id="bfx-vt-comp" type="month" value="${_bfxVtComp}" class="${inputCls()}"
          onchange="_bfxVtComp=this.value; renderBfVT(document.getElementById('bf-content'))"></div>
        ${_bfxBtn('Nova linha', '_bfxVtForm()', 'violet', 'plus')}</div></div>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
      ${kpiDP('Valor a comprar', fBRL2(tot.c), `${(dados.previa || []).length} funcionário(s)`, 'bus', 'text-violet-600')}
      ${kpiDP('Desconto dos funcionários', fBRL2(tot.d), '6% do salário, até o custo', 'percent', 'text-emerald-600')}
      ${kpiDP('Custo da empresa', fBRL2(tot.e), 'valor − desconto', 'building-2', 'text-amber-600')}</div>
    ${card2(`<div class="p-4 overflow-x-auto"><table class="w-full text-sm">
      ${_bfxTh(['Funcionário', 'Linha / trajeto', 'Tarifa', 'Vales/dia', 'Dias', 'Valor no mês', ''])}
      <tbody>${linhas || _bfxVazio(7, 'Nenhuma linha cadastrada. Use “Nova linha” para incluir o trajeto de cada funcionário.')}</tbody></table></div>`)}
    <div class="flex flex-wrap gap-2 mt-4">
      ${_bfxBtn('Pedido de compra', `openAuthDoc('${_BFX}/vt/compra?competencia=${_bfxVtComp}')`, 'violet', 'printer')}
      ${_bfxBtn('Pedido em planilha (CSV)', `_bfxCsv('${_BFX}/vt/compra?competencia=${_bfxVtComp}&formato=csv','compra-vt-${_bfxVtComp}.csv')`, 'cinza', 'sheet')}
      ${_bfxBtn('Recibos de entrega', `openAuthDoc('${_BFX}/vt/recibo?competencia=${_bfxVtComp}')`, 'cinza', 'file-signature')}</div>`;
  if (window.lucide) lucide.createIcons();
}

function _bfxVtForm(id) {
  const l = (window._bfxVtLinhas || []).find(x => x.id === id) || { vales_dia: 2, ativo: 1 };
  _bfxModal(id ? 'Editar linha de VT' : 'Nova linha de VT', `
    <div class="grid grid-cols-2 gap-3">
      <div class="col-span-2">${labelCls('Funcionário')}<select id="bfx-vt-emp" class="${inputCls()}" ${id ? 'disabled' : ''}>${_bfxEmpOpts(l.employee_id)}</select></div>
      <div class="col-span-2">${labelCls('Linha / trajeto')}<input id="bfx-vt-desc" value="${_dpEsc(l.descricao || '')}" placeholder="ex.: Ônibus 101 — Centro/Jardim" class="${inputCls()}"></div>
      <div>${labelCls('Tarifa (R$)')}<input id="bfx-vt-tar" type="number" step="0.01" min="0" value="${l.tarifa ?? ''}" class="${inputCls()}"></div>
      <div>${labelCls('Vales por dia')}<input id="bfx-vt-vd" type="number" min="1" max="10" value="${l.vales_dia ?? 2}" class="${inputCls()}"></div>
      <div>${labelCls('Dias fixos no mês (0 = automático)')}<input id="bfx-vt-dias" type="number" min="0" max="31" value="${l.dias_mes || 0}" class="${inputCls()}"></div>
      <label class="flex items-center gap-2 text-sm mt-6"><input id="bfx-vt-ativo" type="checkbox" ${l.ativo ? 'checked' : ''}> Ativa</label></div>`,
  async () => {
    const body = { employee_id: id ? l.employee_id : _bfxV('bfx-vt-emp'), descricao: _bfxV('bfx-vt-desc'), tarifa: _bfxV('bfx-vt-tar'),
                   vales_dia: _bfxV('bfx-vt-vd'), dias_mes: _bfxV('bfx-vt-dias'), ativo: _bfxC('bfx-vt-ativo') };
    const r = await _bfxPost(id ? `${_BFX}/vt/linhas/${id}` : `${_BFX}/vt/linhas`, body, id ? 'PUT' : 'POST');
    if (r) { showToast('Linha salva.', 'success'); renderBfVT(document.getElementById('bf-content')); }
    return !!r;
  });
}

async function _bfxVtExcluir(id) {
  if (!confirm('Excluir esta linha de vale-transporte?')) return;
  if (await _bfxPost(`${_BFX}/vt/linhas/${id}`, null, 'DELETE')) renderBfVT(document.getElementById('bf-content'));
}

// ── PLANO DE SAÚDE ───────────────────────────────────────────────────────────
let _bfxPlComp = _bfxMes();

async function renderBfPlano(el) {
  let planos = [], adesoes = [], copart = [];
  try {
    [planos, adesoes, copart] = await Promise.all([apiFetch(`${_BFX}/planos`), apiFetch(`${_BFX}/adesoes?competencia=${_bfxPlComp}`),
                                                   apiFetch(`${_BFX}/copart?competencia=${_bfxPlComp}`)]);
  } catch (e) { showToast(e.message, 'error'); }
  window._bfxPlanos = planos;
  const pct = (a, b) => `empresa paga ${a}% do titular e ${b}% dos dependentes`;
  const cards = planos.map(p => card2(`<div class="p-4 ${p.ativo ? '' : 'opacity-60'}">
      <div class="flex items-start justify-between gap-2"><div>
        <div class="font-bold text-sm text-slate-800 dark:text-slate-100">${_dpEsc(p.nome)} <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">${p.tipo === 'odonto' ? 'Odonto' : 'Saúde'}</span></div>
        <div class="text-[11px] text-slate-400">${_dpEsc(p.operadora || 'Operadora não informada')}${p.registro_ans ? ` · ANS ${_dpEsc(p.registro_ans)}` : ''}</div></div>
        <span class="text-xs font-semibold text-violet-600">${p.adesoes} adesão(ões)</span></div>
      <div class="text-xs text-slate-500 mt-2">${p.modalidade_valor === 'faixa' ? `Por faixa etária (${p.faixas.length} faixas)` : `Valor fixo: ${fBRL2(p.valor_fixo_titular)} titular · ${fBRL2(p.valor_fixo_dependente)} dependente`}
        · ${pct(p.pct_empresa_titular, p.pct_empresa_dependente)} · coparticipação ${p.copart_pct_empregado}% no funcionário</div>
      <div class="flex gap-2 mt-3">${_bfxBtn('Editar', `_bfxPlanoForm(${p.id})`, 'cinza')} ${_bfxBtn('Excluir', `_bfxPlanoExcluir(${p.id})`, 'red')}</div></div>`)).join('');
  const optPl = planos.filter(p => p.ativo).map(p => `<option value="${p.id}">${_dpEsc(p.nome)}</option>`).join('');
  const ads = adesoes.map(a => `<tr class="border-b border-slate-100 dark:border-slate-800 align-top ${a.ativo ? '' : 'opacity-50'}">
      ${_bfxTd(_dpEsc(a.employee_name))}${_bfxTd(_dpEsc(a.plano_nome))}${_bfxTd(fDate2(a.data_inicio) + (a.data_fim ? ` a ${fDate2(a.data_fim)}` : ''))}
      <td class="py-2 px-2 text-xs">${(a.vidas || []).map(v => `${_dpEsc(v.beneficiario)}${v.idade != null ? ` (${v.idade} a)` : ''}: ${fBRL2(v.valor)}`).join('<br>')}
        ${(a.avisos || []).map(x => `<div class="text-amber-600">${_dpEsc(x)}</div>`).join('')}</td>
      ${_bfxTd(fBRL2(a.empresa), 1)}${_bfxTd(`<b>${fBRL2(a.empregado)}</b>`, 1)}
      <td class="py-2 px-2 text-right whitespace-nowrap">${_bfxBtn(a.ativo ? 'Encerrar' : 'Reativar', `_bfxAdesaoAtivo(${a.id}, ${a.ativo ? 0 : 1})`, 'cinza')} ${_bfxBtn('Excluir', `_bfxAdesaoExcluir(${a.id})`, 'red')}</td></tr>`).join('');
  const cps = copart.map(c => `<tr class="border-b border-slate-100 dark:border-slate-800">${_bfxTd(_dpEsc(c.employee_name))}${_bfxTd(_dpEsc(c.plano_nome))}
      ${_bfxTd(_dpEsc(c.beneficiario))}${_bfxTd(_dpEsc(c.descricao))}${_bfxTd(fBRL2(c.valor), 1)}
      <td class="py-2 px-2 text-right">${_bfxBtn('Excluir', `_bfxCopartExcluir(${c.id})`, 'red')}</td></tr>`).join('');
  el.innerHTML = `
    <div class="flex flex-wrap items-end justify-between gap-3 mb-4">
      <div><h3 class="font-bold text-slate-800 dark:text-slate-100">Plano de saúde e odontológico</h3>
        <p class="text-xs text-slate-400 max-w-2xl">Mensalidade pela faixa etária da ANS de cada vida (titular e dependentes marcados com “plano de saúde” na ficha).
        A parte do funcionário e a coparticipação são descontadas na folha (natureza eSocial 9219), sem incidir em INSS, FGTS ou IRRF.</p></div>
      <div class="flex items-end gap-2">
        <div>${labelCls('Competência')}<input type="month" value="${_bfxPlComp}" class="${inputCls()}"
          onchange="_bfxPlComp=this.value; renderBfPlano(document.getElementById('bf-content'))"></div>
        ${_bfxBtn('Novo plano', '_bfxPlanoForm()', 'violet', 'plus')}</div></div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-6">${cards || `<p class="text-xs text-slate-400">Nenhum plano cadastrado.</p>`}</div>

    <h4 class="font-bold text-sm text-slate-700 dark:text-slate-200 mb-2">Adesões</h4>
    ${card2(`<div class="p-4"><div class="grid grid-cols-1 sm:grid-cols-5 gap-2 items-end mb-3">
        <div class="sm:col-span-2">${labelCls('Funcionário')}<select id="bfx-ad-emp" class="${inputCls()}">${_bfxEmpOpts()}</select></div>
        <div>${labelCls('Plano')}<select id="bfx-ad-pl" class="${inputCls()}">${optPl || '<option value="">Cadastre um plano</option>'}</select></div>
        <div>${labelCls('Início')}<input id="bfx-ad-ini" type="date" value="${_bfxPlComp}-01" class="${inputCls()}"></div>
        <div class="flex items-center gap-2"><label class="text-xs flex items-center gap-1"><input id="bfx-ad-dep" type="checkbox" checked> Dependentes</label>
          ${_bfxBtn('Incluir', '_bfxAdesaoCriar()', 'violet', 'plus')}</div></div>
      <div class="overflow-x-auto"><table class="w-full text-sm">${_bfxTh(['Funcionário', 'Plano', 'Vigência', `Vidas em ${_bfxPlComp.split('-').reverse().join('/')}`, 'Empresa', 'Funcionário', ''])}
        <tbody>${ads || _bfxVazio(7, 'Nenhuma adesão.')}</tbody></table></div></div>`)}

    <h4 class="font-bold text-sm text-slate-700 dark:text-slate-200 mt-6 mb-2">Coparticipação de ${_bfxPlComp.split('-').reverse().join('/')}</h4>
    ${card2(`<div class="p-4"><div class="grid grid-cols-1 sm:grid-cols-6 gap-2 items-end mb-3">
        <div class="sm:col-span-2">${labelCls('Funcionário')}<select id="bfx-cp-emp" class="${inputCls()}">${_bfxEmpOpts()}</select></div>
        <div>${labelCls('Plano')}<select id="bfx-cp-pl" class="${inputCls()}">${optPl}</select></div>
        <div>${labelCls('Beneficiário')}<input id="bfx-cp-ben" value="Titular" class="${inputCls()}"></div>
        <div>${labelCls('Descrição')}<input id="bfx-cp-desc" placeholder="Consulta, exame…" class="${inputCls()}"></div>
        <div class="flex items-end gap-2"><div>${labelCls('Valor')}<input id="bfx-cp-val" type="number" step="0.01" min="0" class="${inputCls()}"></div>
          ${_bfxBtn('', '_bfxCopartCriar()', 'violet', 'plus')}</div></div>
      <div class="overflow-x-auto"><table class="w-full text-sm">${_bfxTh(['Funcionário', 'Plano', 'Beneficiário', 'Descrição', 'Valor', ''])}
        <tbody>${cps || _bfxVazio(6, 'Sem coparticipação lançada nesta competência.')}</tbody></table></div>
      <div class="flex flex-wrap gap-2 mt-3">
        ${_bfxBtn('Importar extrato da operadora', '_bfxCopartImportar()', 'cinza', 'upload')}
        ${_bfxBtn('Conferência com a fatura', `openAuthDoc('${_BFX}/planos/conferencia?competencia=${_bfxPlComp}')`, 'violet', 'printer')}
        ${_bfxBtn('Conferência (CSV)', `_bfxCsv('${_BFX}/planos/conferencia?competencia=${_bfxPlComp}&formato=csv','conferencia-plano-${_bfxPlComp}.csv')`, 'cinza', 'sheet')}</div></div>`)}`;
  if (window.lucide) lucide.createIcons();
}

async function _bfxPlanoForm(id) {
  let p = (window._bfxPlanos || []).find(x => x.id === id);
  if (!p) {
    let faixas = [];
    try { faixas = await apiFetch(`${_BFX}/faixas-ans`); } catch {}
    p = { tipo: 'saude', modalidade_valor: 'faixa', pct_empresa_titular: 0, pct_empresa_dependente: 0, copart_pct_empregado: 100, ativo: 1, faixas };
  }
  const fx = (p.faixas || []).map((f, i) => `<tr><td class="py-1 pr-2 text-xs text-slate-500">${f.idade_min} a ${f.idade_max >= 120 ? 'mais' : f.idade_max} anos</td>
      <td class="py-1"><input data-fx="${i}" data-min="${f.idade_min}" data-max="${f.idade_max}" type="number" step="0.01" min="0" value="${f.valor}" class="${inputCls()} max-w-[160px]"></td></tr>`).join('');
  _bfxModal(id ? 'Editar plano' : 'Novo plano', `
    <div class="grid grid-cols-2 gap-3">
      <div>${labelCls('Nome do plano')}<input id="bfx-pl-nome" value="${_dpEsc(p.nome || '')}" class="${inputCls()}"></div>
      <div>${labelCls('Tipo')}<select id="bfx-pl-tipo" class="${inputCls()}"><option value="saude" ${p.tipo === 'saude' ? 'selected' : ''}>Saúde</option>
        <option value="odonto" ${p.tipo === 'odonto' ? 'selected' : ''}>Odontológico</option></select></div>
      <div>${labelCls('Operadora')}<input id="bfx-pl-op" value="${_dpEsc(p.operadora || '')}" class="${inputCls()}"></div>
      <div class="grid grid-cols-2 gap-2"><div>${labelCls('CNPJ')}<input id="bfx-pl-cnpj" value="${_dpEsc(p.cnpj_operadora || '')}" class="${inputCls()}"></div>
        <div>${labelCls('Registro ANS')}<input id="bfx-pl-ans" value="${_dpEsc(p.registro_ans || '')}" maxlength="6" class="${inputCls()}"></div></div>
      <div>${labelCls('% pago pela empresa — titular')}<input id="bfx-pl-pt" type="number" min="0" max="100" step="0.01" value="${p.pct_empresa_titular}" class="${inputCls()}"></div>
      <div>${labelCls('% pago pela empresa — dependentes')}<input id="bfx-pl-pd" type="number" min="0" max="100" step="0.01" value="${p.pct_empresa_dependente}" class="${inputCls()}"></div>
      <div>${labelCls('% da coparticipação descontado do funcionário')}<input id="bfx-pl-cp" type="number" min="0" max="100" step="0.01" value="${p.copart_pct_empregado}" class="${inputCls()}"></div>
      <div>${labelCls('Valor da mensalidade')}<select id="bfx-pl-mod" class="${inputCls()}" onchange="document.getElementById('bfx-pl-faixas').classList.toggle('hidden', this.value!=='faixa'); document.getElementById('bfx-pl-fixo').classList.toggle('hidden', this.value!=='fixo')">
        <option value="faixa" ${p.modalidade_valor === 'faixa' ? 'selected' : ''}>Por faixa etária (ANS)</option>
        <option value="fixo" ${p.modalidade_valor === 'fixo' ? 'selected' : ''}>Valor fixo por vida</option></select></div>
      <label class="flex items-center gap-2 text-sm col-span-2"><input id="bfx-pl-ativo" type="checkbox" ${p.ativo ? 'checked' : ''}> Plano ativo</label></div>
    <div id="bfx-pl-faixas" class="${p.modalidade_valor === 'faixa' ? '' : 'hidden'} mt-4">
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600 mb-1">Mensalidade por faixa etária (RN 63/2003)</div>
      <table>${fx}</table></div>
    <div id="bfx-pl-fixo" class="${p.modalidade_valor === 'fixo' ? '' : 'hidden'} grid grid-cols-2 gap-3 mt-4">
      <div>${labelCls('Valor do titular')}<input id="bfx-pl-vt" type="number" step="0.01" min="0" value="${p.valor_fixo_titular || 0}" class="${inputCls()}"></div>
      <div>${labelCls('Valor por dependente')}<input id="bfx-pl-vd" type="number" step="0.01" min="0" value="${p.valor_fixo_dependente || 0}" class="${inputCls()}"></div></div>`,
  async () => {
    const faixas = [...document.querySelectorAll('#bfx-pl-faixas input[data-fx]')].map(i =>
      ({ idade_min: +i.dataset.min, idade_max: +i.dataset.max, valor: i.value || 0 }));
    const body = { nome: _bfxV('bfx-pl-nome'), tipo: _bfxV('bfx-pl-tipo'), operadora: _bfxV('bfx-pl-op'), cnpj_operadora: _bfxV('bfx-pl-cnpj'),
      registro_ans: _bfxV('bfx-pl-ans'), pct_empresa_titular: _bfxV('bfx-pl-pt'), pct_empresa_dependente: _bfxV('bfx-pl-pd'),
      copart_pct_empregado: _bfxV('bfx-pl-cp'), modalidade_valor: _bfxV('bfx-pl-mod'), valor_fixo_titular: _bfxV('bfx-pl-vt'),
      valor_fixo_dependente: _bfxV('bfx-pl-vd'), ativo: _bfxC('bfx-pl-ativo'), faixas };
    const r = await _bfxPost(id ? `${_BFX}/planos/${id}` : `${_BFX}/planos`, body, id ? 'PUT' : 'POST');
    if (r) { showToast('Plano salvo.', 'success'); renderBfPlano(document.getElementById('bf-content')); }
    return !!r;
  });
}

async function _bfxPlanoExcluir(id) {
  if (!confirm('Excluir este plano? A coparticipação lançada nele também será apagada.')) return;
  if (await _bfxPost(`${_BFX}/planos/${id}`, null, 'DELETE')) renderBfPlano(document.getElementById('bf-content'));
}

async function _bfxAdesaoCriar() {
  const r = await _bfxPost(`${_BFX}/adesoes`, { employee_id: _bfxV('bfx-ad-emp'), plano_id: _bfxV('bfx-ad-pl'),
    data_inicio: _bfxV('bfx-ad-ini'), incluir_dependentes: _bfxC('bfx-ad-dep') });
  if (r) { showToast('Adesão incluída.', 'success'); renderBfPlano(document.getElementById('bf-content')); }
}

async function _bfxAdesaoAtivo(id, ativo) {
  const body = ativo ? { ativo: 1, data_fim: '' } : { ativo: 0, data_fim: new Date().toISOString().slice(0, 10) };
  if (await _bfxPost(`${_BFX}/adesoes/${id}`, body, 'PUT')) renderBfPlano(document.getElementById('bf-content'));
}

async function _bfxAdesaoExcluir(id) {
  if (!confirm('Excluir a adesão? Para registrar a saída do plano, prefira “Encerrar”.')) return;
  if (await _bfxPost(`${_BFX}/adesoes/${id}`, null, 'DELETE')) renderBfPlano(document.getElementById('bf-content'));
}

async function _bfxCopartCriar() {
  const r = await _bfxPost(`${_BFX}/copart`, { employee_id: _bfxV('bfx-cp-emp'), plano_id: _bfxV('bfx-cp-pl'), competencia: _bfxPlComp,
    beneficiario: _bfxV('bfx-cp-ben'), descricao: _bfxV('bfx-cp-desc'), valor: _bfxV('bfx-cp-val') });
  if (r) { showToast('Coparticipação lançada.', 'success'); renderBfPlano(document.getElementById('bf-content')); }
}

function _bfxCopartImportar() {
  const optPl = (window._bfxPlanos || []).filter(p => p.ativo).map(p => `<option value="${p.id}">${_dpEsc(p.nome)}</option>`).join('');
  _bfxModal('Importar coparticipação', `
    <p class="text-xs text-slate-500 mb-3">Cole o extrato da operadora (ou de uma planilha), uma utilização por linha:
      <b>CPF do titular; beneficiário; descrição; valor</b>. Separador ponto e vírgula ou tabulação; a linha de cabeçalho é ignorada.</p>
    <div class="grid grid-cols-2 gap-3 mb-3"><div>${labelCls('Plano')}<select id="bfx-imp-pl" class="${inputCls()}">${optPl}</select></div>
      <div>${labelCls('Competência')}<input id="bfx-imp-comp" type="month" value="${_bfxPlComp}" class="${inputCls()}"></div></div>
    <textarea id="bfx-imp-txt" rows="8" class="${inputCls()} font-mono text-xs" placeholder="123.456.789-09;Maria;Consulta;45,00"></textarea>
    <div id="bfx-imp-res" class="text-xs mt-2"></div>`,
  async () => {
    const r = await _bfxPost(`${_BFX}/copart/importar`, { plano_id: _bfxV('bfx-imp-pl'), competencia: _bfxV('bfx-imp-comp'), texto: _bfxV('bfx-imp-txt') });
    if (!r) return false;
    if (r.erros.length) {
      document.getElementById('bfx-imp-res').innerHTML = `<div class="text-emerald-600">${r.importadas} linha(s) importada(s).</div>` +
        r.erros.map(e => `<div class="text-red-600">Linha ${e.linha}: ${_dpEsc(e.erro)}</div>`).join('');
      renderBfPlano(document.getElementById('bf-content'));
      return false;
    }
    showToast(`${r.importadas} linha(s) importada(s).`, 'success');
    renderBfPlano(document.getElementById('bf-content'));
    return true;
  });
}

async function _bfxCopartExcluir(id) {
  if (await _bfxPost(`${_BFX}/copart/${id}`, null, 'DELETE')) renderBfPlano(document.getElementById('bf-content'));
}

// ── CONSIGNADO ───────────────────────────────────────────────────────────────
async function renderBfConsignado(el) {
  const comp = _bfxMes();
  let lista = [];
  try { lista = await apiFetch(`${_BFX}/consignados?competencia=${comp}`); } catch (e) { showToast(e.message, 'error'); }
  window._bfxCons = lista;
  const trs = lista.map(c => `<tr class="border-b border-slate-100 dark:border-slate-800 ${c.ativo ? '' : 'opacity-50'}">
      ${_bfxTd(_dpEsc(c.employee_name))}${_bfxTd(`${_dpEsc(c.instituicao || '—')}<div class="text-[10px] text-slate-400">${_dpEsc(c.origem_nome)}${c.contrato ? ` · ${_dpEsc(c.contrato)}` : ''}</div>`)}
      ${_bfxTd(fBRL2(c.valor_parcela), 1)}${_bfxTd(c.parcela_atual ? `${c.parcela_atual}/${c.parcelas_total}` : `— /${c.parcelas_total}`, 1)}
      ${_bfxTd(c.competencia_inicio.split('-').reverse().join('/'))}${_bfxTd(fBRL2(c.saldo_devedor > 0 ? c.saldo_devedor : c.saldo_estimado), 1)}
      ${_bfxTd(c.desconta_rescisao ? 'Sim' : 'Não')}
      <td class="py-2 px-2 text-right whitespace-nowrap">${_bfxBtn('Margem', `_bfxMargem(${c.employee_id})`, 'cinza')} ${_bfxBtn('Editar', `_bfxConsForm(${c.id})`, 'cinza')} ${_bfxBtn('Excluir', `_bfxConsExcluir(${c.id})`, 'red')}</td></tr>`).join('');
  el.innerHTML = `
    <div class="flex flex-wrap items-end justify-between gap-3 mb-4">
      <div><h3 class="font-bold text-slate-800 dark:text-slate-100">Empréstimo consignado</h3>
        <p class="text-xs text-slate-400 max-w-2xl">A parcela é descontada na folha até a margem consignável (DP › Parâmetros; padrão 35% da remuneração
        disponível, Lei 10.820/2003). Na rescisão, o saldo é descontado das verbas até a mesma margem. Crédito do Trabalhador: as parcelas
        aparecem no FGTS Digital e são pagas na guia; convênio: repasse direto ao banco.</p></div>
      ${_bfxBtn('Novo contrato', '_bfxConsForm()', 'violet', 'plus')}</div>
    ${card2(`<div class="p-4 overflow-x-auto"><table class="w-full text-sm">
      ${_bfxTh(['Funcionário', 'Instituição', 'Parcela', `Parcela em ${comp.split('-').reverse().join('/')}`, '1ª parcela', 'Saldo', 'Na rescisão', ''])}
      <tbody>${trs || _bfxVazio(8, 'Nenhum contrato de consignado.')}</tbody></table></div>`)}
    <div id="bfx-margem" class="mt-4"></div>`;
  if (window.lucide) lucide.createIcons();
}

function _bfxConsForm(id) {
  const c = (window._bfxCons || []).find(x => x.id === id) || { origem: 'credito_trabalhador', competencia_inicio: _bfxMes(), desconta_rescisao: 1, ativo: 1 };
  _bfxModal(id ? 'Editar consignado' : 'Novo contrato de consignado', `
    <div class="grid grid-cols-2 gap-3">
      <div class="col-span-2">${labelCls('Funcionário')}<select id="bfx-cs-emp" class="${inputCls()}" ${id ? 'disabled' : ''}>${_bfxEmpOpts(c.employee_id)}</select></div>
      <div>${labelCls('Origem')}<select id="bfx-cs-orig" class="${inputCls()}">
        <option value="credito_trabalhador" ${c.origem === 'credito_trabalhador' ? 'selected' : ''}>Crédito do Trabalhador (eSocial)</option>
        <option value="convenio" ${c.origem === 'convenio' ? 'selected' : ''}>Convênio com banco</option></select></div>
      <div>${labelCls('Instituição')}<input id="bfx-cs-inst" value="${_dpEsc(c.instituicao || '')}" class="${inputCls()}"></div>
      <div>${labelCls('Nº do contrato')}<input id="bfx-cs-ct" value="${_dpEsc(c.contrato || '')}" class="${inputCls()}"></div>
      <div>${labelCls('Valor da parcela')}<input id="bfx-cs-vp" type="number" step="0.01" min="0" value="${c.valor_parcela ?? ''}" class="${inputCls()}"></div>
      <div>${labelCls('Quantidade de parcelas')}<input id="bfx-cs-np" type="number" min="1" max="200" value="${c.parcelas_total ?? ''}" class="${inputCls()}"></div>
      <div>${labelCls('Competência da 1ª parcela')}<input id="bfx-cs-ini" type="month" value="${c.competencia_inicio}" class="${inputCls()}"></div>
      <div>${labelCls('Saldo devedor informado pelo banco (opcional)')}<input id="bfx-cs-sd" type="number" step="0.01" min="0" value="${c.saldo_devedor || ''}" class="${inputCls()}"></div>
      <div class="flex flex-col gap-1 mt-5"><label class="flex items-center gap-2 text-sm"><input id="bfx-cs-resc" type="checkbox" ${c.desconta_rescisao ? 'checked' : ''}> Descontar o saldo na rescisão</label>
        <label class="flex items-center gap-2 text-sm"><input id="bfx-cs-ativo" type="checkbox" ${c.ativo ? 'checked' : ''}> Contrato ativo</label></div>
      <div class="col-span-2">${labelCls('Observações')}<input id="bfx-cs-obs" value="${_dpEsc(c.observacoes || '')}" class="${inputCls()}"></div></div>`,
  async () => {
    const body = { employee_id: id ? c.employee_id : _bfxV('bfx-cs-emp'), origem: _bfxV('bfx-cs-orig'), instituicao: _bfxV('bfx-cs-inst'),
      contrato: _bfxV('bfx-cs-ct'), valor_parcela: _bfxV('bfx-cs-vp'), parcelas_total: _bfxV('bfx-cs-np'), competencia_inicio: _bfxV('bfx-cs-ini'),
      saldo_devedor: _bfxV('bfx-cs-sd'), desconta_rescisao: _bfxC('bfx-cs-resc'), ativo: _bfxC('bfx-cs-ativo'), observacoes: _bfxV('bfx-cs-obs') };
    const r = await _bfxPost(id ? `${_BFX}/consignados/${id}` : `${_BFX}/consignados`, body, id ? 'PUT' : 'POST');
    if (r) { showToast('Contrato salvo.', 'success'); renderBfConsignado(document.getElementById('bf-content')); }
    return !!r;
  });
}

async function _bfxConsExcluir(id) {
  if (!confirm('Excluir este contrato? Para quitação, prefira editar e desmarcar “Contrato ativo”.')) return;
  if (await _bfxPost(`${_BFX}/consignados/${id}`, null, 'DELETE')) renderBfConsignado(document.getElementById('bf-content'));
}

async function _bfxMargem(empId) {
  const box = document.getElementById('bfx-margem');
  try {
    const m = await apiFetch(`${_BFX}/consignados/margem/${empId}`);
    const lin = (r, v, b) => `<div class="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800 text-sm"><span class="text-slate-500">${r}</span><span class="${b ? 'font-bold' : ''} tabular-nums">${v}</span></div>`;
    box.innerHTML = card2(`<div class="p-4 max-w-md"><div class="font-bold text-sm mb-2">Margem consignável — ${_dpEsc(m.employee_name)}</div>
      <div class="text-[11px] text-slate-400 mb-2">Pela folha de ${m.competencia.split('-').reverse().join('/')}</div>
      ${lin('Remuneração bruta', fBRL2(m.bruto))}${lin('INSS, IRRF e pensão', '− ' + fBRL2(m.descontos_obrigatorios))}
      ${lin('Remuneração disponível', fBRL2(m.remuneracao_disponivel))}${lin(`Margem total (${m.percentual}%)`, fBRL2(m.margem_total))}
      ${lin('Já comprometida', fBRL2(m.margem_utilizada))}${lin('Margem livre', fBRL2(m.margem_disponivel), 1)}</div>`);
  } catch (e) { box.innerHTML = `<p class="text-xs text-amber-600">${_dpEsc(e.message)}</p>`; }
}
