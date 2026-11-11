// ============================================================
// CONTRATOS RECORRENTES — Cortex ERP Pro+
// Gestão · Faturamento Mensal · Reajuste por Índice
// ============================================================

function authHeaders() { return {}; }

let ctSubTab  = 'contratos';
let ctList    = [];
let ctClients = [];

// ── helpers ──────────────────────────────────────────────────
const fBRL4  = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fDate4 = s => s ? s.slice(0, 10).split('-').reverse().join('/') : '-';
const card4  = html => `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs">${html}</div>`;

const CT_STATUS_CLS = {
  ativo:     'text-emerald-600 bg-emerald-50 dark:bg-emerald-900/30',
  pausado:   'text-amber-500  bg-amber-50  dark:bg-amber-900/20',
  encerrado: 'text-slate-400  bg-slate-100 dark:bg-slate-800',
};

function ctStatusBadge(s) {
  const cls = CT_STATUS_CLS[s] || CT_STATUS_CLS.ativo;
  const label = s === 'ativo' ? 'Ativo' : s === 'pausado' ? 'Pausado' : 'Encerrado';
  return `<span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${cls}">${label}</span>`;
}

function kpiCt(label, value, sub, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-500 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
    ${sub ? `<div class="text-[11px] text-slate-400 mt-1">${sub}</div>` : ''}
  </div>`;
}

function inputCt() {
  return 'w-full text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500';
}
function lblCt(t) {
  return `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${t}</label>`;
}

// ── sub-tabs ─────────────────────────────────────────────────
function ctTabs() {
  const tabs = [
    { id: 'contratos', icon: 'file-check-2', label: 'Contratos' },
    { id: 'reajuste',  icon: 'trending-up',  label: 'Reajuste em Lote' },
  ];
  return `<div class="flex gap-1 overflow-x-auto pb-1 flex-wrap">
    ${tabs.map(t => `
      <button onclick="switchCtTab('${t.id}')" id="ct-tab-${t.id}"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition whitespace-nowrap
          ${ctSubTab === t.id
            ? 'bg-teal-600 text-white'
            : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'}">
        <i data-lucide="${t.icon}" class="w-3.5 h-3.5"></i>${t.label}
      </button>`).join('')}
  </div>`;
}

// ── entry point ───────────────────────────────────────────────
async function renderContracts(container) {
  await Promise.all([
    fetch('/api/contracts', { headers: authHeaders() }).then(r => r.json()).then(d => { ctList = Array.isArray(d) ? d : []; }).catch(() => { ctList = []; }),
    fetch('/api/contacts', { headers: authHeaders() }).then(r => r.json()).then(d => { ctClients = Array.isArray(d) ? d : []; }).catch(() => { ctClients = []; }),
  ]);

  container.innerHTML = `
    <div id="ct-tabs-bar" class="mb-4">${ctTabs()}</div>
    <div id="ct-body"></div>`;

  await switchCtTab(ctSubTab, true);
  if (window.lucide) lucide.createIcons();
}

async function switchCtTab(tab, noRebuild = false) {
  ctSubTab = tab;
  if (!noRebuild) {
    const bar = document.getElementById('ct-tabs-bar');
    if (bar) { bar.innerHTML = ctTabs(); if (window.lucide) lucide.createIcons(); }
  }
  const body = document.getElementById('ct-body');
  if (!body) return;
  body.innerHTML = `<div class="flex items-center justify-center p-10 text-slate-400">
    <div class="animate-spin rounded-full h-7 w-7 border-b-2 border-teal-500 mr-3"></div>Carregando...</div>`;

  if (tab === 'contratos') await renderCtLista(body);
  else if (tab === 'reajuste') renderCtReajuste(body);
  if (window.lucide) lucide.createIcons();
}

// ── 1. LISTA DE CONTRATOS ─────────────────────────────────────
async function renderCtLista(el) {
  try {
    const r = await fetch('/api/contracts', { headers: authHeaders() });
    ctList = await r.json();
  } catch { ctList = []; }

  const thisMonth   = new Date().toISOString().slice(0, 7);
  const ativos      = ctList.filter(c => c.status === 'ativo');
  const naoFaturados = ativos.filter(c => (c.last_billed_month || '') < thisMonth);
  const mrr         = ativos.reduce((s, c) => s + parseFloat(c.monthly_value || 0), 0);

  const rows = ctList.map(c => {
    const jaBilledThisMonth = (c.last_billed_month || '') >= thisMonth;
    const podeAjustar       = c.status === 'ativo';

    return `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
      <td class="px-4 py-3 text-sm font-medium text-slate-800 dark:text-slate-200 max-w-[200px]">
        <div class="truncate">${c.title}</div>
        ${c.inflation_index ? `<div class="text-[10px] text-slate-400 mt-0.5">Índice: ${c.inflation_index} · último reaj: ${c.last_adjusted_at ? fDate4(c.last_adjusted_at) : '—'}</div>` : ''}
      </td>
      <td class="px-4 py-3 text-sm text-slate-600 dark:text-slate-300">${c.contact_name || '-'}</td>
      <td class="px-4 py-3 text-sm font-bold text-teal-600">${fBRL4(c.monthly_value)}</td>
      <td class="px-4 py-3 text-xs text-slate-400">Dia ${c.due_day || 10}</td>
      <td class="px-4 py-3 text-xs text-slate-400">${fDate4(c.start_date)}</td>
      <td class="px-4 py-3">
        ${ctStatusBadge(c.status)}
      </td>
      <td class="px-4 py-3 text-xs">
        ${jaBilledThisMonth
          ? `<span class="text-emerald-500 font-semibold">✓ ${c.last_billed_month}</span>`
          : `<span class="text-amber-500 font-semibold">— não faturado</span>`}
      </td>
      <td class="px-4 py-3 text-right whitespace-nowrap">
        ${c.status === 'ativo' && !jaBilledThisMonth
          ? `<button onclick="billContract(${c.id}, '${c.title.replace(/'/g, "\\'")}')"
               class="text-xs text-teal-600 font-semibold hover:underline mr-2">Faturar Mês</button>`
          : ''}
        ${podeAjustar
          ? `<button onclick="openAjusteModal(${c.id}, '${c.title.replace(/'/g, "\\'")}', ${c.monthly_value})"
               class="text-xs text-indigo-500 hover:underline mr-2">Reajustar</button>`
          : ''}
        ${c.status === 'ativo'
          ? `<button onclick="encerrarContrato(${c.id}, '${c.title.replace(/'/g, "\\'")}')"
               class="text-xs text-rose-500 hover:underline">Encerrar</button>`
          : ''}
      </td>
    </tr>`;
  }).join('');

  el.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      ${kpiCt('Total de Contratos', ctList.length, `${ativos.length} ativos`, 'file-check-2', 'text-teal-600')}
      ${kpiCt('MRR (Receita Mensal)', fBRL4(mrr), 'contratos ativos', 'repeat', 'text-emerald-600')}
      ${kpiCt('MRR Anual Estimado', fBRL4(mrr * 12), 'projeção 12 meses', 'trending-up', 'text-blue-600')}
      ${kpiCt('Não Faturados (Mês)', naoFaturados.length, 'aguardando faturamento', 'alert-circle', naoFaturados.length > 0 ? 'text-amber-500' : 'text-slate-400')}
    </div>

    <div class="flex items-center justify-between mb-4">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Contratos Recorrentes</h2>
      <div class="flex gap-2">
        ${naoFaturados.length > 0
          ? `<button onclick="faturarTodos()"
               class="bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-400 border border-teal-200 dark:border-teal-800 text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2 hover:bg-teal-100 transition">
               <i data-lucide="zap" class="w-3.5 h-3.5"></i> Faturar Todos (${naoFaturados.length})
             </button>`
          : ''}
        <button onclick="openNovoContratoModal()"
          class="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i> Novo Contrato
        </button>
      </div>
    </div>

    ${card4(`
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left font-semibold">Título</th>
            <th class="px-4 py-2 text-left font-semibold">Cliente</th>
            <th class="px-4 py-2 text-left font-semibold">Valor/Mês</th>
            <th class="px-4 py-2 text-left font-semibold">Vencimento</th>
            <th class="px-4 py-2 text-left font-semibold">Início</th>
            <th class="px-4 py-2 text-left font-semibold">Status</th>
            <th class="px-4 py-2 text-left font-semibold">Últ. Fatura</th>
            <th class="px-4 py-2 text-right font-semibold">Ações</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="8" class="px-4 py-8 text-center text-slate-400 text-xs">Nenhum contrato cadastrado.</td></tr>'}</tbody>
        </table>
      </div>`)}`;
}

// ── Faturar um contrato ───────────────────────────────────────
async function billContract(id, title) {
  const thisMonth = new Date().toISOString().slice(0, 7);
  if (!confirm(`Gerar mensalidade de ${thisMonth} para:\n"${title}"\n\nUm lançamento será criado no Contas a Receber.`)) return;
  try {
    const r = await fetch(`/api/contracts/${id}/bill`, { method: 'POST', headers: authHeaders() });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro ao faturar.'); return; }
    const d = await r.json();
    alert(d.message || 'Mensalidade gerada com sucesso!');
    await renderCtLista(document.getElementById('ct-body'));
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

// ── Faturar todos os não faturados deste mês ──────────────────
async function faturarTodos() {
  const thisMonth    = new Date().toISOString().slice(0, 7);
  const naoFaturados = ctList.filter(c => c.status === 'ativo' && (c.last_billed_month || '') < thisMonth);
  if (naoFaturados.length === 0) { alert('Nenhum contrato pendente de faturamento.'); return; }
  if (!confirm(`Faturar ${naoFaturados.length} contrato(s) para ${thisMonth}?\n\nSerão criados ${naoFaturados.length} lançamento(s) no Contas a Receber.`)) return;

  let ok = 0, erros = 0;
  for (const c of naoFaturados) {
    try {
      const r = await fetch(`/api/contracts/${c.id}/bill`, { method: 'POST', headers: authHeaders() });
      if (r.ok) ok++; else erros++;
    } catch { erros++; }
  }
  alert(`Faturamento concluído!\n✓ ${ok} gerado(s) · ✗ ${erros} erro(s)`);
  await renderCtLista(document.getElementById('ct-body'));
  if (window.lucide) lucide.createIcons();
}

// ── Encerrar contrato ─────────────────────────────────────────
async function encerrarContrato(id, title) {
  if (!confirm(`Encerrar contrato "${title}"?\n\nO contrato não poderá ser faturado após encerrado.`)) return;
  try {
    const r = await fetch(`/api/contracts/${id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ status: 'encerrado' }),
    });
    if (r.ok) {
      const idx = ctList.findIndex(c => c.id === id);
      if (idx >= 0) ctList[idx].status = 'encerrado';
      await renderCtLista(document.getElementById('ct-body'));
      if (window.lucide) lucide.createIcons();
    } else {
      alert('Não foi possível encerrar o contrato via API. Verifique se o endpoint PUT /api/contracts/{id} existe no backend.');
    }
  } catch { alert('Erro de conexão.'); }
}

// ── Modal reajuste individual ─────────────────────────────────
function openAjusteModal(id, title, currentValue) {
  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-md w-full">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="trending-up" class="w-5 h-5 text-teal-500"></i> Reajuste de Contrato
      </h3>
      <p class="text-sm text-slate-500 dark:text-slate-400 mb-5">
        <strong class="text-slate-700 dark:text-slate-200">${title}</strong><br>
        Valor atual: <strong class="text-teal-600">${fBRL4(currentValue)}</strong>
      </p>
      <div class="space-y-4">
        <div>
          ${lblCt('Percentual de Reajuste (%)')}
          <input id="ajuste-pct" type="number" step="0.01" min="0" class="${inputCt()}"
            placeholder="ex: 5.5 para 5,5%" oninput="previewAjuste(${currentValue})">
        </div>
        <div>
          ${lblCt('Índice de Referência')}
          <select id="ajuste-idx" class="${inputCt()}">
            <option value="IPCA">IPCA</option>
            <option value="IGP-M">IGP-M</option>
            <option value="INPC">INPC</option>
            <option value="IPCA-E">IPCA-E</option>
            <option value="Fixo">Percentual Fixo</option>
          </select>
        </div>
        <div id="ajuste-preview" class="p-3 bg-teal-50 dark:bg-teal-900/20 rounded-xl text-xs text-slate-600 dark:text-slate-300 hidden">
          Novo valor: <strong id="ajuste-novo-val" class="text-teal-600 text-sm"></strong>
          <span id="ajuste-diff" class="ml-2 text-slate-400"></span>
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="closeModal()" class="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
        <button onclick="confirmarAjuste(${id})"
          class="bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-5 py-2 rounded-xl">
          Aplicar Reajuste
        </button>
      </div>
    </div>`);
  if (window.lucide) lucide.createIcons();
}

function previewAjuste(currentValue) {
  const pct     = parseFloat(document.getElementById('ajuste-pct')?.value || 0);
  const preview = document.getElementById('ajuste-preview');
  const novoVal = document.getElementById('ajuste-novo-val');
  const diff    = document.getElementById('ajuste-diff');
  if (!preview || !novoVal) return;
  if (pct <= 0) { preview.classList.add('hidden'); return; }
  const novo = currentValue * (1 + pct / 100);
  const dif  = novo - currentValue;
  preview.classList.remove('hidden');
  novoVal.textContent = fBRL4(novo);
  diff.textContent    = `(+${fBRL4(dif)})`;
}

async function confirmarAjuste(id) {
  const pct = parseFloat(document.getElementById('ajuste-pct')?.value || 0);
  const idx = document.getElementById('ajuste-idx')?.value || 'IPCA';
  if (pct <= 0) { alert('Informe um percentual maior que zero.'); return; }
  try {
    const r = await fetch(`/api/contracts/${id}/adjust`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ adjustment_percent: pct, inflation_index: idx }),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro.'); return; }
    const d = await r.json();
    alert(`Reajuste aplicado!\n${fBRL4(d.previous_value)} → ${fBRL4(d.new_value)} (+${pct}% ${idx})`);
    closeModal();
    const cr = await fetch('/api/contracts', { headers: authHeaders() });
    ctList = await cr.json();
    await renderCtLista(document.getElementById('ct-body'));
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

// ── Modal novo contrato ───────────────────────────────────────
function openNovoContratoModal() {
  const clientOpts = ctClients.map(c => `<option value="${c.id}">${c.name}${c.document ? ' — ' + c.document : ''}</option>`).join('');
  const today = new Date().toISOString().slice(0, 10);

  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-lg w-full">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="file-plus-2" class="w-5 h-5 text-teal-500"></i> Novo Contrato Recorrente
      </h3>
      <div class="space-y-4">
        <div>
          ${lblCt('Título do Contrato *')}
          <input id="ct-title" class="${inputCt()}" placeholder="ex: Manutenção Mensal — Empresa XYZ">
        </div>
        <div>
          ${lblCt('Cliente *')}
          <select id="ct-contact" class="${inputCt()}">
            <option value="">Selecione o cliente...</option>${clientOpts}
          </select>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            ${lblCt('Valor Mensal (R$) *')}
            <input id="ct-amount" type="number" step="0.01" min="0.01" class="${inputCt()}" placeholder="0,00">
          </div>
          <div>
            ${lblCt('Dia de Vencimento')}
            <input id="ct-dueday" type="number" min="1" max="28" value="10" class="${inputCt()}">
          </div>
        </div>
        <div>
          ${lblCt('Data de Início')}
          <input id="ct-start" type="date" value="${today}" class="${inputCt()}">
        </div>
        <div>
          ${lblCt('Observações')}
          <input id="ct-notes" class="${inputCt()}" placeholder="Descrição do serviço, cláusulas especiais...">
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="closeModal()" class="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
        <button onclick="salvarNovoContrato()"
          class="bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-5 py-2 rounded-xl">
          Criar Contrato
        </button>
      </div>
    </div>`);
  if (window.lucide) lucide.createIcons();
}

async function salvarNovoContrato() {
  const title      = document.getElementById('ct-title')?.value.trim();
  const contact_id = parseInt(document.getElementById('ct-contact')?.value);
  const amount     = parseFloat(document.getElementById('ct-amount')?.value);
  const billing_day = parseInt(document.getElementById('ct-dueday')?.value || 10);
  const start_date = document.getElementById('ct-start')?.value || null;
  const notes      = document.getElementById('ct-notes')?.value.trim() || '';

  if (!title)      { alert('Informe o título do contrato.'); return; }
  if (!contact_id) { alert('Selecione o cliente.'); return; }
  if (!amount || amount <= 0) { alert('Informe o valor mensal.'); return; }

  try {
    const r = await fetch('/api/contracts', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ title, contact_id, amount, billing_day, start_date, notes }),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro ao criar contrato.'); return; }
    closeModal();
    const cr = await fetch('/api/contracts', { headers: authHeaders() });
    ctList = await cr.json();
    await renderCtLista(document.getElementById('ct-body'));
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

// ── 2. REAJUSTE EM LOTE ───────────────────────────────────────
function renderCtReajuste(el) {
  const ativos = ctList.filter(c => c.status === 'ativo');
  const mrr    = ativos.reduce((s, c) => s + parseFloat(c.monthly_value || 0), 0);

  const checkboxes = ativos.map(c => `
    <label class="flex items-center gap-3 p-3 rounded-xl border border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition">
      <input type="checkbox" class="ct-check rounded" value="${c.id}" checked>
      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">${c.title}</div>
        <div class="text-xs text-slate-400">${c.contact_name || '-'}</div>
      </div>
      <div class="text-sm font-bold text-teal-600 whitespace-nowrap">${fBRL4(c.monthly_value)}</div>
      <div id="lote-preview-${c.id}" class="text-xs text-slate-400 whitespace-nowrap w-24 text-right"></div>
    </label>`).join('');

  el.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

      ${card4(`
        <div class="p-5">
          <div class="flex items-center gap-2 mb-4">
            <i data-lucide="settings-2" class="w-5 h-5 text-teal-500"></i>
            <span class="font-bold text-slate-700 dark:text-slate-200">Parâmetros de Reajuste</span>
          </div>
          <div class="space-y-4 mb-5">
            <div>
              ${lblCt('Percentual de Reajuste (%)')}
              <input id="lote-pct" type="number" step="0.01" min="0" class="${inputCt()}"
                placeholder="ex: 5.5 para 5,5%" oninput="previewLote()">
            </div>
            <div>
              ${lblCt('Índice de Referência')}
              <select id="lote-idx" class="${inputCt()}">
                <option value="IPCA">IPCA</option>
                <option value="IGP-M">IGP-M</option>
                <option value="INPC">INPC</option>
                <option value="IPCA-E">IPCA-E</option>
                <option value="Fixo">Percentual Fixo</option>
              </select>
            </div>
          </div>
          <div id="lote-summary" class="p-4 bg-teal-50 dark:bg-teal-900/20 rounded-xl mb-5 hidden">
            <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">Impacto no MRR</div>
            <div class="flex items-center gap-4">
              <div>
                <div class="text-xs text-slate-400">Antes</div>
                <div class="text-base font-bold text-slate-600 dark:text-slate-300" id="lote-mrr-antes">${fBRL4(mrr)}</div>
              </div>
              <i data-lucide="arrow-right" class="w-4 h-4 text-teal-500"></i>
              <div>
                <div class="text-xs text-slate-400">Depois</div>
                <div class="text-base font-bold text-teal-600" id="lote-mrr-depois">—</div>
              </div>
              <div class="ml-auto">
                <div class="text-xs text-slate-400">Acréscimo</div>
                <div class="text-base font-bold text-emerald-600" id="lote-mrr-diff">—</div>
              </div>
            </div>
          </div>
          <button onclick="aplicarLote()"
            class="w-full bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl flex items-center justify-center gap-2">
            <i data-lucide="trending-up" class="w-4 h-4"></i> Aplicar Reajuste nos Selecionados
          </button>
          <div id="lote-result" class="mt-3"></div>
        </div>`)}

      <div>
        <div class="flex items-center justify-between mb-3">
          <span class="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase">
            Contratos Ativos (${ativos.length})
          </span>
          <div class="flex gap-2">
            <button onclick="document.querySelectorAll('.ct-check').forEach(c=>c.checked=true); previewLote()"
              class="text-xs text-teal-500 hover:underline">Todos</button>
            <span class="text-slate-300">|</span>
            <button onclick="document.querySelectorAll('.ct-check').forEach(c=>c.checked=false); previewLote()"
              class="text-xs text-slate-400 hover:underline">Nenhum</button>
          </div>
        </div>
        ${ativos.length > 0
          ? `<div class="space-y-2 max-h-96 overflow-y-auto pr-1">${checkboxes}</div>`
          : '<div class="text-xs text-slate-400 p-4 text-center">Nenhum contrato ativo.</div>'}
      </div>
    </div>`;
}

function previewLote() {
  const pct    = parseFloat(document.getElementById('lote-pct')?.value || 0);
  const checks = document.querySelectorAll('.ct-check:checked');
  const selIds = new Set([...checks].map(c => parseInt(c.value)));
  const sel    = ctList.filter(c => selIds.has(c.id));

  const summary = document.getElementById('lote-summary');
  if (pct <= 0) {
    sel.forEach(c => { const el = document.getElementById(`lote-preview-${c.id}`); if (el) el.textContent = ''; });
    if (summary) summary.classList.add('hidden');
    return;
  }

  let mrrAntes = 0, mrrDepois = 0;
  ctList.filter(c => c.status === 'ativo').forEach(c => {
    const val = parseFloat(c.monthly_value || 0);
    mrrAntes += val;
    const el = document.getElementById(`lote-preview-${c.id}`);
    if (selIds.has(c.id)) {
      const novo = val * (1 + pct / 100);
      mrrDepois += novo;
      if (el) el.innerHTML = `→ <strong class="text-teal-600">${fBRL4(novo)}</strong>`;
    } else {
      mrrDepois += val;
      if (el) el.textContent = '';
    }
  });

  if (summary) {
    summary.classList.remove('hidden');
    document.getElementById('lote-mrr-antes').textContent  = fBRL4(mrrAntes);
    document.getElementById('lote-mrr-depois').textContent = fBRL4(mrrDepois);
    document.getElementById('lote-mrr-diff').textContent   = '+' + fBRL4(mrrDepois - mrrAntes);
  }
  if (window.lucide) lucide.createIcons();
}

async function aplicarLote() {
  const pct    = parseFloat(document.getElementById('lote-pct')?.value || 0);
  const idx    = document.getElementById('lote-idx')?.value || 'IPCA';
  const checks = document.querySelectorAll('.ct-check:checked');
  const ids    = [...checks].map(c => parseInt(c.value));

  if (pct <= 0) { alert('Informe o percentual de reajuste.'); return; }
  if (ids.length === 0) { alert('Selecione ao menos um contrato.'); return; }
  if (!confirm(`Aplicar reajuste de ${pct}% (${idx}) em ${ids.length} contrato(s)?\nEsta ação altera os valores mensais imediatamente.`)) return;

  const res = document.getElementById('lote-result');
  if (res) res.innerHTML = '<p class="text-xs text-slate-400">Aplicando...</p>';

  try {
    const r = await fetch('/api/contracts/batch-adjust', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ adjustment_percent: pct, inflation_index: idx, contract_ids: ids }),
    });
    if (!r.ok) { const e = await r.json(); if (res) res.innerHTML = `<p class="text-xs text-rose-500">${e.detail || 'Erro.'}</p>`; return; }
    const d = await r.json();
    if (res) res.innerHTML = `
      <div class="text-xs text-emerald-600 font-semibold p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
        ✓ ${d.adjusted_count} contrato(s) reajustado(s) em +${pct}% (${idx})
      </div>`;
    const cr = await fetch('/api/contracts', { headers: authHeaders() });
    ctList = await cr.json();
    renderCtReajuste(document.getElementById('ct-body'));
    if (window.lucide) lucide.createIcons();
  } catch { if (res) res.innerHTML = '<p class="text-xs text-rose-500">Erro de conexão.</p>'; }
}
