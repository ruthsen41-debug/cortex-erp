// ============================================================
// MÓDULO CONTÁBIL — Cortex ERP Pro+
// Plano de Contas · Lançamentos · Razão · Balancete · DRE
// Balanço Patrimonial · Livro Diário · ECD
// ============================================================

// auth.js já injeta Bearer em window.fetch para /api/; retorna {} sem fazer nada.
function authHeaders() { return {}; }

let acctSubTab = 'plano';
let acctAccounts = [];
let acctPeriod = (() => {
  const y = new Date().getFullYear();
  const m = String(new Date().getMonth() + 1).padStart(2, '0');
  const d = String(new Date().getDate()).padStart(2, '0');
  return { start: `${y}-01-01`, end: `${y}-${m}-${d}` };
})();

const ACCT_TYPE_LABEL = {
  ativo: 'Ativo', passivo: 'Passivo', patrimonio_liquido: 'Pat. Líquido',
  receita: 'Receita', custo: 'Custo', despesa: 'Despesa',
};
const ACCT_TYPE_COLOR = {
  ativo: 'text-blue-500', passivo: 'text-orange-500',
  patrimonio_liquido: 'text-purple-500', receita: 'text-emerald-500',
  custo: 'text-amber-500', despesa: 'text-rose-500',
};

// ── helpers ──────────────────────────────────────────────────
const fBRL = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fDate = s => s ? s.slice(0, 10).split('-').reverse().join('/') : '-';
const cls = (...a) => a.filter(Boolean).join(' ');
const card = html => `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs">${html}</div>`;
const badge = (t, color) => `<span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${color} bg-current/10">${t}</span>`;
function kpiCard(label, value, sub, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-500 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
    ${sub ? `<div class="text-[11px] text-slate-400 mt-1">${sub}</div>` : ''}
  </div>`;
}

// ── sub-tabs bar ─────────────────────────────────────────────
function acctTabs() {
  const tabs = [
    { id: 'plano',     icon: 'list-tree',       label: 'Plano de Contas' },
    { id: 'lanctos',   icon: 'book-open',        label: 'Lançamentos' },
    { id: 'razao',     icon: 'book-marked',      label: 'Razão' },
    { id: 'balancete', icon: 'table-2',          label: 'Balancete' },
    { id: 'dre',       icon: 'trending-up',      label: 'DRE' },
    { id: 'balanco',   icon: 'scale',            label: 'Balanço' },
    { id: 'diario',    icon: 'scroll-text',      label: 'Livro Diário' },
    { id: 'ecd',       icon: 'file-down',        label: 'SPED ECD' },
  ];
  return `<div class="flex gap-1 overflow-x-auto pb-1 flex-wrap">
    ${tabs.map(t => `
      <button onclick="switchAcctTab('${t.id}')" id="acct-tab-${t.id}"
        class="acct-tab flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition whitespace-nowrap
          ${acctSubTab === t.id
            ? 'bg-indigo-600 text-white'
            : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'}">
        <i data-lucide="${t.icon}" class="w-3.5 h-3.5"></i>${t.label}
      </button>`).join('')}
  </div>`;
}

function periodBar(extraHtml = '') {
  return `<div class="flex flex-wrap items-center gap-3">
    <label class="text-xs text-slate-500 font-semibold">Período:</label>
    <input type="date" id="acct-start" value="${acctPeriod.start}"
      class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      onchange="acctPeriod.start=this.value">
    <span class="text-slate-400 text-xs">até</span>
    <input type="date" id="acct-end" value="${acctPeriod.end}"
      class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      onchange="acctPeriod.end=this.value">
    ${extraHtml}
  </div>`;
}

// ── entry point ──────────────────────────────────────────────
async function renderAccounting(container) {
  // pre-load accounts for all sub-tabs
  try {
    const r = await fetch('/api/accounting/accounts?active_only=false', { headers: authHeaders() });
    acctAccounts = await r.json();
  } catch { acctAccounts = []; }

  container.innerHTML = `
    <div id="acct-tabs-bar" class="mb-4">${acctTabs()}</div>
    <div id="acct-body"></div>`;

  await switchAcctTab(acctSubTab, true);
  if (window.lucide) lucide.createIcons();
}

async function switchAcctTab(tab, noRebuildTabs = false) {
  acctSubTab = tab;
  if (!noRebuildTabs) {
    const bar = document.getElementById('acct-tabs-bar');
    if (bar) { bar.innerHTML = acctTabs(); if (window.lucide) lucide.createIcons(); }
  }
  const body = document.getElementById('acct-body');
  if (!body) return;
  body.innerHTML = `<div class="flex items-center justify-center p-10 text-slate-400">
    <div class="animate-spin rounded-full h-7 w-7 border-b-2 border-indigo-500 mr-3"></div>Carregando...</div>`;

  switch (tab) {
    case 'plano':     await renderPlanoConta(body); break;
    case 'lanctos':   await renderLancamentos(body); break;
    case 'razao':     await renderRazao(body); break;
    case 'balancete': await renderBalancete(body); break;
    case 'dre':       await renderDre(body); break;
    case 'balanco':   await renderBalanco(body); break;
    case 'diario':    await renderLivroDiario(body); break;
    case 'ecd':       renderEcd(body); break;
  }
  if (window.lucide) lucide.createIcons();
}

// ── 1. PLANO DE CONTAS ───────────────────────────────────────
async function renderPlanoConta(el) {
  const groups = {};
  acctAccounts.forEach(a => {
    const g = a.account_type;
    if (!groups[g]) groups[g] = [];
    groups[g].push(a);
  });

  const groupHtml = Object.entries(groups).map(([type, accs]) => {
    const rows = accs.map(a => `
      <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
        <td class="px-4 py-2.5 font-mono text-xs text-slate-400">${a.code}</td>
        <td class="px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 pl-${(a.code.split('.').length - 1) * 4}">${a.name}</td>
        <td class="px-4 py-2.5">
          ${a.accepts_entries
            ? '<span class="text-[10px] font-bold text-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 px-2 py-0.5 rounded-full">ANALÍTICA</span>'
            : '<span class="text-[10px] font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">SINTÉTICA</span>'}
        </td>
        <td class="px-4 py-2.5 text-xs font-semibold ${a.nature === 'devedora' ? 'text-blue-500' : 'text-emerald-500'}">
          ${a.nature === 'devedora' ? 'D — Devedora' : 'C — Credora'}
        </td>
        <td class="px-4 py-2.5">
          ${a.active
            ? '<span class="text-[10px] font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">ATIVA</span>'
            : '<span class="text-[10px] font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">INATIVA</span>'}
        </td>
        <td class="px-4 py-2.5 text-right">
          <button onclick="openEditAccountModal(${a.id})" class="text-xs text-indigo-500 hover:underline mr-3">Editar</button>
          <button onclick="deleteAccount(${a.id},'${a.name.replace(/'/g,"\\'")}',${!!a.accepts_entries})"
            class="text-xs text-rose-500 hover:underline">Excluir</button>
        </td>
      </tr>`).join('');

    return `
      <div class="mb-4">${card(`
        <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center gap-2">
          <span class="font-bold text-sm ${ACCT_TYPE_COLOR[type] || 'text-slate-600'}">${ACCT_TYPE_LABEL[type] || type}</span>
          <span class="text-xs text-slate-400">(${accs.length} contas)</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
              <th class="px-4 py-2 text-left font-semibold">Código</th>
              <th class="px-4 py-2 text-left font-semibold">Nome</th>
              <th class="px-4 py-2 text-left font-semibold">Tipo</th>
              <th class="px-4 py-2 text-left font-semibold">Natureza</th>
              <th class="px-4 py-2 text-left font-semibold">Status</th>
              <th class="px-4 py-2 text-right font-semibold">Ações</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`)}</div>`;
  }).join('');

  el.innerHTML = `
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Plano de Contas</h2>
        <p class="text-xs text-slate-400 mt-0.5">${acctAccounts.length} contas cadastradas · Padrão NBC/CFC</p>
      </div>
      <button onclick="openNewAccountModal()"
        class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i> Nova Conta
      </button>
    </div>
    ${groupHtml}`;
}

function openNewAccountModal() {
  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="plus-circle" class="w-5 h-5 text-indigo-500"></i> Nova Conta Contábil
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div><label class="label">Código *</label>
          <input id="na-code" class="input w-full" placeholder="Ex: 1.1.10"/></div>
        <div><label class="label">Nome *</label>
          <input id="na-name" class="input w-full" placeholder="Ex: Outros Ativos Circulantes"/></div>
        <div><label class="label">Tipo *</label>
          <select id="na-type" class="input w-full">
            ${Object.entries(ACCT_TYPE_LABEL).map(([v,l]) => `<option value="${v}">${l}</option>`).join('')}
          </select></div>
        <div><label class="label">Natureza *</label>
          <select id="na-nature" class="input w-full">
            <option value="devedora">Devedora (Saldo Normal Débito)</option>
            <option value="credora">Credora (Saldo Normal Crédito)</option>
          </select></div>
        <div><label class="label">Conta Pai (Código)</label>
          <input id="na-parent" class="input w-full" placeholder="Ex: 1.1"/></div>
        <div class="flex items-center gap-3 pt-5">
          <input type="checkbox" id="na-accepts" checked class="w-4 h-4 rounded accent-indigo-600"/>
          <label for="na-accepts" class="text-sm text-slate-700 dark:text-slate-300">Aceita lançamentos (analítica)</label>
        </div>
      </div>
      <div class="flex gap-3 mt-6 justify-end">
        <button onclick="closeModal()" class="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">Cancelar</button>
        <button onclick="saveNewAccount()"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-5 py-2 rounded-xl">Criar Conta</button>
      </div>
    </div>`);
}

async function saveNewAccount() {
  const body = {
    code: document.getElementById('na-code').value.trim(),
    name: document.getElementById('na-name').value.trim(),
    account_type: document.getElementById('na-type').value,
    nature: document.getElementById('na-nature').value,
    parent_code: document.getElementById('na-parent').value.trim() || null,
    accepts_entries: document.getElementById('na-accepts').checked,
  };
  if (!body.code || !body.name) { showToast('Código e Nome são obrigatórios.', 'error'); return; }
  const r = await fetch('/api/accounting/accounts', {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) { showToast(data.detail || 'Erro ao criar conta.', 'error'); return; }
  showToast('Conta criada com sucesso!', 'success');
  closeModal();
  const r2 = await fetch('/api/accounting/accounts?active_only=false', { headers: authHeaders() });
  acctAccounts = await r2.json();
  await switchAcctTab('plano');
}

async function openEditAccountModal(id) {
  const acc = acctAccounts.find(a => a.id === id);
  if (!acc) return;
  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg">Editar Conta — ${acc.code}</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div><label class="label">Nome</label>
          <input id="ea-name" class="input w-full" value="${acc.name}"/></div>
        <div><label class="label">Descrição</label>
          <input id="ea-desc" class="input w-full" value="${acc.description || ''}"/></div>
        <div class="flex items-center gap-3 pt-5">
          <input type="checkbox" id="ea-accepts" ${acc.accepts_entries ? 'checked' : ''} class="w-4 h-4 rounded accent-indigo-600"/>
          <label for="ea-accepts" class="text-sm text-slate-700 dark:text-slate-300">Aceita lançamentos (analítica)</label>
        </div>
        <div class="flex items-center gap-3 pt-5">
          <input type="checkbox" id="ea-active" ${acc.active ? 'checked' : ''} class="w-4 h-4 rounded accent-indigo-600"/>
          <label for="ea-active" class="text-sm text-slate-700 dark:text-slate-300">Conta ativa</label>
        </div>
      </div>
      <div class="flex gap-3 mt-6 justify-end">
        <button onclick="closeModal()" class="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-300">Cancelar</button>
        <button onclick="saveEditAccount(${id})"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-5 py-2 rounded-xl">Salvar</button>
      </div>
    </div>`);
}

async function saveEditAccount(id) {
  const body = {
    name: document.getElementById('ea-name').value.trim(),
    description: document.getElementById('ea-desc').value.trim(),
    accepts_entries: document.getElementById('ea-accepts').checked,
    active: document.getElementById('ea-active').checked,
  };
  const r = await fetch(`/api/accounting/accounts/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!r.ok) { const d = await r.json(); showToast(d.detail || 'Erro ao salvar.', 'error'); return; }
  showToast('Conta atualizada!', 'success');
  closeModal();
  const r2 = await fetch('/api/accounting/accounts?active_only=false', { headers: authHeaders() });
  acctAccounts = await r2.json();
  await switchAcctTab('plano');
}

async function deleteAccount(id, name) {
  if (!confirm(`Excluir a conta "${name}"? Esta ação é irreversível.`)) return;
  const r = await fetch(`/api/accounting/accounts/${id}`, { method: 'DELETE', headers: authHeaders() });
  const d = await r.json();
  if (!r.ok) { showToast(d.detail || 'Não foi possível excluir.', 'error'); return; }
  showToast('Conta removida.', 'success');
  const r2 = await fetch('/api/accounting/accounts?active_only=false', { headers: authHeaders() });
  acctAccounts = await r2.json();
  await switchAcctTab('plano');
}

// ── 2. LANÇAMENTOS CONTÁBEIS ─────────────────────────────────
async function renderLancamentos(el) {
  const url = `/api/accounting/entries?start_date=${acctPeriod.start}&end_date=${acctPeriod.end}`;
  let entries = [];
  try { entries = await fetch(url, { headers: authHeaders() }).then(r => r.json()); } catch {}

  const rows = entries.map(e => {
    const linesHtml = (e.lines || []).map(ln => `
      <tr class="text-xs border-b border-slate-100 dark:border-slate-800">
        <td class="px-4 py-1.5 font-mono text-slate-400">${ln.account_code || ''}</td>
        <td class="px-4 py-1.5 text-slate-600 dark:text-slate-300">${ln.account_name || ''}</td>
        <td class="px-4 py-1.5 text-right font-mono font-semibold text-blue-500">${ln.debit > 0 ? fBRL(ln.debit) : ''}</td>
        <td class="px-4 py-1.5 text-right font-mono font-semibold text-emerald-500">${ln.credit > 0 ? fBRL(ln.credit) : ''}</td>
        <td class="px-4 py-1.5 text-slate-400">${ln.description || ''}</td>
      </tr>`).join('');

    return `
      <div class="mb-3">${card(`
        <div class="px-4 py-3 flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 dark:border-slate-800 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
          onclick="this.nextElementSibling.classList.toggle('hidden')">
          <div>
            <div class="text-xs font-mono text-slate-400">${fDate(e.entry_date)} · #${e.id}</div>
            <div class="font-semibold text-slate-800 dark:text-slate-200 text-sm mt-0.5">${e.description}</div>
            ${e.document_number ? `<div class="text-xs text-slate-400">Doc: ${e.document_number}</div>` : ''}
          </div>
          <div class="flex items-center gap-4">
            <div class="text-right">
              <div class="text-xs text-slate-400">Débitos / Créditos</div>
              <div class="text-sm font-bold">
                <span class="text-blue-500">${fBRL(e.total_debit)}</span>
                <span class="text-slate-300 mx-1">/</span>
                <span class="text-emerald-500">${fBRL(e.total_credit)}</span>
              </div>
            </div>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${e.entry_type === 'automatico' ? 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-600' : 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600'}">
              ${e.entry_type === 'automatico' ? 'AUTO' : 'MANUAL'}
            </span>
            ${e.entry_type !== 'automatico' ? `<button onclick="event.stopPropagation();deleteEntry(${e.id})"
              class="text-rose-500 hover:text-rose-700 p-1 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-900/20">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>` : ''}
          </div>
        </div>
        <div class="hidden overflow-x-auto">
          <table class="w-full text-sm">
            <thead><tr class="text-[10px] text-slate-400 uppercase bg-slate-50 dark:bg-slate-800/50">
              <th class="px-4 py-2 text-left">Código</th><th class="px-4 py-2 text-left">Conta</th>
              <th class="px-4 py-2 text-right">Débito</th><th class="px-4 py-2 text-right">Crédito</th>
              <th class="px-4 py-2 text-left">Histórico</th>
            </tr></thead>
            <tbody>${linesHtml}</tbody>
          </table>
        </div>`)}</div>`;
  }).join('') || '<div class="text-center text-slate-400 py-12">Nenhum lançamento no período.</div>';

  el.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Lançamentos Contábeis</h2>
        <p class="text-xs text-slate-400 mt-0.5">${entries.length} lançamentos · Clique para expandir as partidas</p>
      </div>
      <div class="flex items-center gap-3 flex-wrap">
        ${periodBar()}
        <button onclick="switchAcctTab('lanctos')"
          class="text-xs font-semibold text-indigo-500 border border-indigo-300 dark:border-indigo-700 px-3 py-1.5 rounded-xl hover:bg-indigo-50 dark:hover:bg-indigo-900/20">
          <i data-lucide="refresh-cw" class="w-3 h-3 inline mr-1"></i>Atualizar
        </button>
        <button onclick="openNewEntryModal()"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i>Novo Lançamento
        </button>
      </div>
    </div>
    ${rows}`;
}

let entryLines = [];

function openNewEntryModal() {
  entryLines = [
    { id: 1, account_id: '', dc: 'D', amount: '', desc: '' },
    { id: 2, account_id: '', dc: 'C', amount: '', desc: '' },
  ];

  const analyticAccounts = acctAccounts.filter(a => a.accepts_entries && a.active);
  const opts = analyticAccounts.map(a =>
    `<option value="${a.id}">[${a.code}] ${a.name}</option>`).join('');

  function renderLines() {
    return entryLines.map((ln, idx) => `
      <tr>
        <td class="py-1.5 pr-2">
          <select id="el-acc-${ln.id}" class="input w-full text-xs" onchange="entryLines[${idx}].account_id=this.value;updateEntryBalance()">
            <option value="">— Conta —</option>${opts}
          </select>
        </td>
        <td class="py-1.5 pr-2 w-24">
          <select id="el-dc-${ln.id}" class="input w-full text-xs font-bold"
            onchange="entryLines[${idx}].dc=this.value;updateEntryBalance()">
            <option value="D" ${ln.dc==='D'?'selected':''} class="text-blue-600">D — Débito</option>
            <option value="C" ${ln.dc==='C'?'selected':''} class="text-emerald-600">C — Crédito</option>
          </select>
        </td>
        <td class="py-1.5 pr-2 w-36">
          <input id="el-amt-${ln.id}" type="number" step="0.01" min="0" value="${ln.amount}"
            class="input w-full text-xs text-right font-mono"
            placeholder="0,00"
            oninput="entryLines[${idx}].amount=parseFloat(this.value)||0;updateEntryBalance()"/>
        </td>
        <td class="py-1.5 pr-2">
          <input id="el-desc-${ln.id}" class="input w-full text-xs" placeholder="Histórico da partida"
            oninput="entryLines[${idx}].desc=this.value"/>
        </td>
        <td class="py-1.5 w-8">
          ${entryLines.length > 2 ? `<button onclick="removeEntryLine(${idx})"
            class="text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20 p-1 rounded">
            <i data-lucide="x" class="w-3.5 h-3.5"></i></button>` : ''}
        </td>
      </tr>`).join('');
  }

  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="book-open" class="w-5 h-5 text-indigo-500"></i> Novo Lançamento Contábil
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        <div><label class="label">Data *</label>
          <input id="ne-date" type="date" class="input w-full" value="${acctPeriod.end}"/></div>
        <div><label class="label">Descrição *</label>
          <input id="ne-desc" class="input w-full" placeholder="Histórico do lançamento"/></div>
        <div><label class="label">Nº Documento</label>
          <input id="ne-doc" class="input w-full" placeholder="NF-100 / REC-01..."/></div>
      </div>

      <div class="mb-2 flex items-center justify-between">
        <span class="text-sm font-semibold text-slate-700 dark:text-slate-300">Partidas Dobradas</span>
        <div id="entry-balance-badge" class="text-xs font-mono font-bold px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500">
          Débitos: R$ 0,00 · Créditos: R$ 0,00
        </div>
      </div>

      <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 mb-3">
        <table class="w-full text-sm">
          <thead><tr class="text-[10px] text-slate-400 uppercase bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
            <th class="px-3 py-2 text-left">Conta</th>
            <th class="px-3 py-2 text-left w-24">D/C</th>
            <th class="px-3 py-2 text-right w-36">Valor</th>
            <th class="px-3 py-2 text-left">Histórico</th>
            <th class="px-3 py-2 w-8"></th>
          </tr></thead>
          <tbody id="entry-lines-body" class="divide-y divide-slate-100 dark:divide-slate-800">
            ${renderLines()}
          </tbody>
        </table>
      </div>
      <button onclick="addEntryLine()"
        class="text-xs font-semibold text-indigo-500 border border-indigo-200 dark:border-indigo-800 px-3 py-1.5 rounded-xl hover:bg-indigo-50 dark:hover:bg-indigo-900/20 flex items-center gap-1.5 mb-5">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i> Adicionar Partida
      </button>

      <div class="flex gap-3 justify-end">
        <button onclick="closeModal()" class="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-300">Cancelar</button>
        <button onclick="saveNewEntry()"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-5 py-2 rounded-xl">Lançar</button>
      </div>
    </div>`);
  if (window.lucide) lucide.createIcons();
}

function addEntryLine() {
  const newId = Date.now();
  entryLines.push({ id: newId, account_id: '', dc: 'C', amount: 0, desc: '' });
  const analyticAccounts = acctAccounts.filter(a => a.accepts_entries && a.active);
  const opts = analyticAccounts.map(a => `<option value="${a.id}">[${a.code}] ${a.name}</option>`).join('');
  const idx = entryLines.length - 1;
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="py-1.5 pr-2">
      <select id="el-acc-${newId}" class="input w-full text-xs" onchange="entryLines[${idx}].account_id=this.value;updateEntryBalance()">
        <option value="">— Conta —</option>${opts}
      </select>
    </td>
    <td class="py-1.5 pr-2 w-24">
      <select id="el-dc-${newId}" class="input w-full text-xs font-bold" onchange="entryLines[${idx}].dc=this.value;updateEntryBalance()">
        <option value="D">D — Débito</option><option value="C" selected>C — Crédito</option>
      </select>
    </td>
    <td class="py-1.5 pr-2 w-36">
      <input id="el-amt-${newId}" type="number" step="0.01" min="0" value="" class="input w-full text-xs text-right font-mono" placeholder="0,00"
        oninput="entryLines[${idx}].amount=parseFloat(this.value)||0;updateEntryBalance()"/>
    </td>
    <td class="py-1.5 pr-2">
      <input id="el-desc-${newId}" class="input w-full text-xs" placeholder="Histórico" oninput="entryLines[${idx}].desc=this.value"/>
    </td>
    <td class="py-1.5 w-8">
      <button onclick="removeEntryLine(${idx})" class="text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20 p-1 rounded">
        <i data-lucide="x" class="w-3.5 h-3.5"></i></button>
    </td>`;
  document.getElementById('entry-lines-body').appendChild(tr);
  if (window.lucide) lucide.createIcons();
}

function removeEntryLine(idx) {
  entryLines.splice(idx, 1);
  openNewEntryModal(); // re-render modal
}

function updateEntryBalance() {
  const totalD = entryLines.reduce((s, l) => s + (l.dc === 'D' ? (parseFloat(l.amount) || 0) : 0), 0);
  const totalC = entryLines.reduce((s, l) => s + (l.dc === 'C' ? (parseFloat(l.amount) || 0) : 0), 0);
  const balanced = Math.abs(totalD - totalC) < 0.02;
  const badge = document.getElementById('entry-balance-badge');
  if (badge) {
    badge.textContent = `D: ${fBRL(totalD)} · C: ${fBRL(totalC)}`;
    badge.className = `text-xs font-mono font-bold px-3 py-1 rounded-full ${balanced
      ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600'
      : 'bg-rose-100 dark:bg-rose-900/30 text-rose-600'}`;
  }
}

async function saveNewEntry() {
  const lines = entryLines.map(ln => ({
    account_id: parseInt(ln.account_id),
    debit: ln.dc === 'D' ? (parseFloat(ln.amount) || 0) : 0,
    credit: ln.dc === 'C' ? (parseFloat(ln.amount) || 0) : 0,
    description: document.getElementById(`el-desc-${ln.id}`)?.value || ln.desc || '',
  })).filter(l => l.account_id && (l.debit > 0 || l.credit > 0));

  const body = {
    entry_date: document.getElementById('ne-date').value,
    description: document.getElementById('ne-desc').value.trim(),
    document_number: document.getElementById('ne-doc').value.trim(),
    lines,
  };

  if (!body.description || !body.entry_date) { showToast('Preencha data e descrição.', 'error'); return; }
  if (lines.length < 2) { showToast('Mínimo 2 partidas.', 'error'); return; }

  const r = await fetch('/api/accounting/entries', {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) { showToast(data.detail || 'Erro ao lançar.', 'error'); return; }
  showToast('Lançamento registrado!', 'success');
  closeModal();
  await switchAcctTab('lanctos');
}

async function deleteEntry(id) {
  if (!confirm(`Excluir o lançamento #${id}?`)) return;
  const r = await fetch(`/api/accounting/entries/${id}`, { method: 'DELETE', headers: authHeaders() });
  const d = await r.json();
  if (!r.ok) { showToast(d.detail || 'Erro ao excluir.', 'error'); return; }
  showToast('Lançamento excluído.', 'success');
  await switchAcctTab('lanctos');
}

// ── 3. RAZÃO CONTÁBIL ────────────────────────────────────────
async function renderRazao(el) {
  const analyticAccounts = acctAccounts.filter(a => a.accepts_entries);
  const opts = analyticAccounts.map(a =>
    `<option value="${a.id}">[${a.code}] ${a.name}</option>`).join('');

  el.innerHTML = `
    <div class="mb-5">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-3">Razão Contábil</h2>
      <div class="flex flex-wrap items-center gap-3">
        ${periodBar()}
        <label class="text-xs text-slate-500 font-semibold">Conta:</label>
        <select id="razao-account" class="input text-xs min-w-[260px]">
          <option value="">— Selecione —</option>${opts}
        </select>
        <button onclick="loadRazao()"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">
          <i data-lucide="search" class="w-3.5 h-3.5 inline mr-1"></i>Consultar
        </button>
      </div>
    </div>
    <div id="razao-result"></div>`;
}

async function loadRazao() {
  const accId = document.getElementById('razao-account').value;
  if (!accId) { showToast('Selecione uma conta.', 'error'); return; }
  const start = document.getElementById('acct-start').value;
  const end = document.getElementById('acct-end').value;
  acctPeriod = { start, end };

  const el = document.getElementById('razao-result');
  el.innerHTML = '<div class="text-slate-400 text-sm text-center py-6">Carregando...</div>';
  const r = await fetch(`/api/accounting/razao?account_id=${accId}&start_date=${start}&end_date=${end}`, { headers: authHeaders() });
  const data = await r.json();
  if (!r.ok) { el.innerHTML = `<div class="text-rose-500 text-sm">${data.detail}</div>`; return; }

  const acc = data.account;
  const rows = data.movements.map(m => `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/30 text-sm">
      <td class="px-4 py-2.5 font-mono text-xs text-slate-400">${fDate(m.entry_date)}</td>
      <td class="px-4 py-2.5 text-slate-700 dark:text-slate-300">${m.entry_desc || ''}</td>
      <td class="px-4 py-2.5 text-xs text-slate-400">${m.line_desc || ''}</td>
      <td class="px-4 py-2.5 text-right font-mono font-semibold text-blue-500">${parseFloat(m.debit||0)>0 ? fBRL(m.debit) : ''}</td>
      <td class="px-4 py-2.5 text-right font-mono font-semibold text-emerald-500">${parseFloat(m.credit||0)>0 ? fBRL(m.credit) : ''}</td>
      <td class="px-4 py-2.5 text-right font-mono font-bold ${m.saldo_acumulado>=0?'text-slate-800 dark:text-slate-200':'text-rose-500'}">${fBRL(m.saldo_acumulado)}</td>
    </tr>`).join('') || '<tr><td colspan="6" class="text-center text-slate-400 py-6 text-sm">Sem movimentos.</td></tr>';

  el.innerHTML = `
    <div class="mb-3 flex flex-wrap gap-4">
      ${kpiCard('Total Débitos', fBRL(data.total_debit), '', 'arrow-up', 'text-blue-500')}
      ${kpiCard('Total Créditos', fBRL(data.total_credit), '', 'arrow-down', 'text-emerald-500')}
      ${kpiCard('Saldo Final', fBRL(data.saldo_final), `${acc.nature === 'devedora' ? 'Devedora' : 'Credora'}`, 'scale', data.saldo_final >= 0 ? 'text-indigo-500' : 'text-rose-500')}
    </div>
    ${card(`
      <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
        <div class="font-bold text-slate-800 dark:text-slate-100">${acc.code} · ${acc.name}</div>
        <div class="text-xs text-slate-400 mt-0.5">Período: ${fDate(data.period.start)} a ${fDate(data.period.end)}</div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left">Data</th>
            <th class="px-4 py-2 text-left">Descrição</th>
            <th class="px-4 py-2 text-left">Histórico</th>
            <th class="px-4 py-2 text-right">Débito</th>
            <th class="px-4 py-2 text-right">Crédito</th>
            <th class="px-4 py-2 text-right">Saldo</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`)}`;
}

// ── 4. BALANCETE ─────────────────────────────────────────────
async function renderBalancete(el) {
  const start = acctPeriod.start, end = acctPeriod.end;
  let data;
  try {
    data = await fetch(`/api/accounting/balancete?start_date=${start}&end_date=${end}`, { headers: authHeaders() }).then(r => r.json());
  } catch { el.innerHTML = '<div class="text-rose-500 p-4">Erro ao carregar balancete.</div>'; return; }

  const groups = {};
  (data.accounts || []).forEach(a => {
    if (!groups[a.account_type]) groups[a.account_type] = [];
    groups[a.account_type].push(a);
  });

  const groupHtml = Object.entries(groups).map(([type, accs]) => {
    const rows = accs.map(a => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-sm hover:bg-slate-50 dark:hover:bg-slate-800/30">
        <td class="px-4 py-2 font-mono text-xs text-slate-400">${a.code}</td>
        <td class="px-4 py-2 text-slate-700 dark:text-slate-300">${a.name}</td>
        <td class="px-4 py-2 text-right font-mono text-blue-500">${a.total_debit > 0 ? fBRL(a.total_debit) : '-'}</td>
        <td class="px-4 py-2 text-right font-mono text-emerald-500">${a.total_credit > 0 ? fBRL(a.total_credit) : '-'}</td>
        <td class="px-4 py-2 text-right font-mono font-bold ${a.saldo >= 0 ? 'text-slate-800 dark:text-slate-200' : 'text-rose-500'}">${fBRL(a.saldo)}</td>
      </tr>`).join('');

    return `<div class="mb-4">${card(`
      <div class="px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 font-bold text-sm ${ACCT_TYPE_COLOR[type] || ''}">${ACCT_TYPE_LABEL[type] || type}</div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-[10px] text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left">Código</th><th class="px-4 py-2 text-left">Conta</th>
            <th class="px-4 py-2 text-right">Débitos</th><th class="px-4 py-2 text-right">Créditos</th>
            <th class="px-4 py-2 text-right">Saldo</th>
          </tr></thead>
          <tbody>${rows}</tbody>
          <tfoot><tr class="bg-slate-50 dark:bg-slate-800/50 font-bold text-sm border-t border-slate-200 dark:border-slate-700">
            <td colspan="2" class="px-4 py-2 text-slate-500 uppercase text-xs">Subtotal</td>
            <td class="px-4 py-2 text-right font-mono text-blue-500">${fBRL(accs.reduce((s,a)=>s+a.total_debit,0))}</td>
            <td class="px-4 py-2 text-right font-mono text-emerald-500">${fBRL(accs.reduce((s,a)=>s+a.total_credit,0))}</td>
            <td class="px-4 py-2 text-right font-mono">${fBRL(accs.reduce((s,a)=>s+a.saldo,0))}</td>
          </tr></tfoot>
        </table>
      </div>`)}</div>`;
  }).join('');

  el.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Balancete de Verificação</h2>
        <p class="text-xs text-slate-400 mt-0.5">Período: ${fDate(start)} a ${fDate(end)}</p>
      </div>
      <div class="flex items-center gap-3">
        ${periodBar()}
        <button onclick="switchAcctTab('balancete')"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">Atualizar</button>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-4 mb-4">
      ${kpiCard('Total Débitos', fBRL(data.totals?.total_debit), '', 'arrow-up', 'text-blue-500')}
      ${kpiCard('Total Créditos', fBRL(data.totals?.total_credit), '', 'arrow-down', 'text-emerald-500')}
    </div>
    ${groupHtml}`;
}

// ── 5. DRE ───────────────────────────────────────────────────
async function renderDre(el) {
  const start = acctPeriod.start, end = acctPeriod.end;
  let d;
  try {
    d = await fetch(`/api/accounting/dre?start_date=${start}&end_date=${end}`, { headers: authHeaders() }).then(r => r.json());
  } catch { el.innerHTML = '<div class="text-rose-500 p-4">Erro ao carregar DRE.</div>'; return; }

  function dreRow(label, value, indent = 0, bold = false, separator = false) {
    const neg = value < 0;
    const prefix = indent > 0 ? `<span class="text-slate-300 dark:text-slate-600 mr-1">${'─'.repeat(indent)}</span>` : '';
    const sep = separator ? 'border-t-2 border-slate-300 dark:border-slate-600 mt-1 pt-1' : '';
    return `<div class="flex justify-between items-center py-1.5 ${sep} ${bold ? 'font-bold' : ''}">
      <span class="text-slate-700 dark:text-slate-300 text-sm">${prefix}${label}</span>
      <span class="font-mono text-sm ${neg ? 'text-rose-500' : bold ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-700 dark:text-slate-300'}">${fBRL(value)}</span>
    </div>`;
  }

  el.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">DRE — Demonstrativo de Resultado</h2>
        <p class="text-xs text-slate-400 mt-0.5">Período: ${fDate(start)} a ${fDate(end)}</p>
      </div>
      <div class="flex items-center gap-3">${periodBar()}
        <button onclick="switchAcctTab('dre')" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">Atualizar</button>
      </div>
    </div>
    <div class="max-w-2xl mx-auto">${card(`
      <div class="p-6">
        <div class="text-center mb-6">
          <div class="font-bold text-lg text-slate-800 dark:text-slate-100">Demonstrativo de Resultado do Exercício</div>
          <div class="text-xs text-slate-400 mt-1">${fDate(start)} a ${fDate(end)}</div>
        </div>
        ${dreRow('(+) Receita Bruta', d.receita_bruta, 0, false)}
        ${dreRow('(−) Deduções da Receita', -d.deducoes_receita, 1)}
        ${dreRow('= Receita Líquida', d.receita_liquida, 0, true, true)}
        ${dreRow('(−) Custo das Mercad./Serviços (CMV/CSP)', -d.custo_mercadorias_servicos, 1)}
        ${dreRow('= Lucro Bruto', d.lucro_bruto, 0, true, true)}
        ${dreRow('(−) Despesas Operacionais', -d.despesas_operacionais, 1)}
        ${dreRow('= Lucro Operacional', d.lucro_operacional, 0, true, true)}
        ${dreRow('(+/−) Resultado Financeiro', d.resultado_financeiro, 1)}
        ${dreRow('= Lucro Líquido do Período', d.lucro_liquido, 0, true, true)}
      </div>`)}</div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto mt-4">
      ${kpiCard('Receita Bruta', fBRL(d.receita_bruta), '', 'trending-up', 'text-emerald-500')}
      ${kpiCard('Despesas Totais', fBRL(d.despesas_operacionais + d.custo_mercadorias_servicos), '', 'trending-down', 'text-rose-500')}
      ${kpiCard('Lucro Líquido', fBRL(d.lucro_liquido), d.lucro_liquido >= 0 ? 'Positivo' : 'Prejuízo', 'circle-dollar-sign', d.lucro_liquido >= 0 ? 'text-indigo-600' : 'text-rose-600')}
    </div>`;
}

// ── 6. BALANÇO PATRIMONIAL ───────────────────────────────────
async function renderBalanco(el) {
  const refDate = acctPeriod.end;
  let d;
  try {
    d = await fetch(`/api/accounting/balanco?ref_date=${refDate}`, { headers: authHeaders() }).then(r => r.json());
  } catch { el.innerHTML = '<div class="text-rose-500 p-4">Erro ao carregar Balanço.</div>'; return; }

  function groupHtml(group, colorClass) {
    const items = (group.items || []).map(it => `
      <div class="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800 last:border-0 text-sm">
        <span class="text-slate-700 dark:text-slate-300 truncate pr-2">${it.name}</span>
        <span class="font-mono font-semibold whitespace-nowrap ${colorClass}">${fBRL(it.saldo)}</span>
      </div>`).join('') || '<div class="text-xs text-slate-400 py-2">Sem movimentos.</div>';
    return `${items}
      <div class="flex justify-between py-2 font-bold text-sm border-t-2 border-slate-300 dark:border-slate-600 mt-1">
        <span>Total</span>
        <span class="font-mono ${colorClass}">${fBRL(group.total)}</span>
      </div>`;
  }

  el.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Balanço Patrimonial</h2>
        <p class="text-xs ${d.balanceado ? 'text-emerald-500' : 'text-rose-500'} mt-0.5 font-semibold">
          <i data-lucide="${d.balanceado ? 'check-circle-2' : 'alert-triangle'}" class="w-3 h-3 inline mr-1"></i>
          ${d.balanceado ? 'Balanço equilibrado' : 'Atenção: balanço desiquilibrado'} · Data: ${fDate(refDate)}
        </p>
      </div>
      <div class="flex items-center gap-3">
        <input type="date" id="balanco-date" value="${refDate}"
          class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-lg px-2 py-1.5 focus:outline-none"/>
        <button onclick="acctPeriod.end=document.getElementById('balanco-date').value;switchAcctTab('balanco')"
          class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">Atualizar</button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div>${card(`
        <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 font-bold text-blue-500 flex items-center gap-2">
          <i data-lucide="landmark" class="w-4 h-4"></i> ATIVO
          <span class="ml-auto font-mono text-sm">${fBRL(d.ativo?.total)}</span>
        </div>
        <div class="p-4">${groupHtml(d.ativo, 'text-blue-600 dark:text-blue-400')}</div>`)}</div>

      <div class="space-y-4">
        ${card(`
          <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 font-bold text-orange-500 flex items-center gap-2">
            <i data-lucide="credit-card" class="w-4 h-4"></i> PASSIVO
            <span class="ml-auto font-mono text-sm">${fBRL(d.passivo?.total)}</span>
          </div>
          <div class="p-4">${groupHtml(d.passivo, 'text-orange-600 dark:text-orange-400')}</div>`)}
        ${card(`
          <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 font-bold text-purple-500 flex items-center gap-2">
            <i data-lucide="shield-check" class="w-4 h-4"></i> PATRIMÔNIO LÍQUIDO
            <span class="ml-auto font-mono text-sm">${fBRL(d.patrimonio_liquido?.total)}</span>
          </div>
          <div class="p-4">${groupHtml(d.patrimonio_liquido, 'text-purple-600 dark:text-purple-400')}</div>`)}
      </div>
    </div>`;
}

// ── 7. LIVRO DIÁRIO ──────────────────────────────────────────
async function renderLivroDiario(el) {
  const start = acctPeriod.start, end = acctPeriod.end;
  let data;
  try {
    data = await fetch(`/api/accounting/livro-diario?start_date=${start}&end_date=${end}`, { headers: authHeaders() }).then(r => r.json());
  } catch { el.innerHTML = '<div class="text-rose-500 p-4">Erro ao carregar Livro Diário.</div>'; return; }

  const rows = (data.entries || []).map((e, i) => {
    const linesHtml = (e.lines || []).map(ln => `
      <tr class="text-xs border-b border-slate-100 dark:border-slate-800">
        <td class="px-4 py-1.5 font-mono text-slate-400">${ln.account_code}</td>
        <td class="px-4 py-1.5 text-slate-600 dark:text-slate-300">${ln.account_name}</td>
        <td class="px-4 py-1.5 text-right font-mono text-blue-500">${ln.debit > 0 ? fBRL(ln.debit) : ''}</td>
        <td class="px-4 py-1.5 text-right font-mono text-emerald-500">${ln.credit > 0 ? fBRL(ln.credit) : ''}</td>
      </tr>`).join('');

    return `<div class="mb-2">${card(`
      <div class="px-4 py-2.5 flex items-start justify-between gap-2 border-b border-slate-100 dark:border-slate-800">
        <div>
          <span class="font-mono text-xs text-slate-400">${String(i+1).padStart(3,'0')} · ${fDate(e.entry_date)}</span>
          <div class="font-semibold text-sm text-slate-800 dark:text-slate-200 mt-0.5">${e.description}</div>
          ${e.document_number ? `<div class="text-xs text-slate-400">Doc: ${e.document_number}</div>` : ''}
        </div>
        <span class="font-mono text-xs text-slate-400 whitespace-nowrap">D/C: ${fBRL(e.total_debit)}</span>
      </div>
      <table class="w-full text-sm"><tbody>${linesHtml}</tbody></table>`)}</div>`;
  }).join('') || '<div class="text-center text-slate-400 py-12">Nenhum lançamento no período.</div>';

  el.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Livro Diário</h2>
        <p class="text-xs text-slate-400 mt-0.5">${data.total_entries || 0} lançamentos · ${fDate(start)} a ${fDate(end)}</p>
      </div>
      <div class="flex items-center gap-3">${periodBar()}
        <button onclick="switchAcctTab('diario')" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">Atualizar</button>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-4 mb-4">
      ${kpiCard('Total Débitos', fBRL(data.total_debit), '', 'arrow-up', 'text-blue-500')}
      ${kpiCard('Total Créditos', fBRL(data.total_credit), '', 'arrow-down', 'text-emerald-500')}
    </div>
    ${rows}`;
}

// ── 8. DOWNLOAD ECD ──────────────────────────────────────────
function renderEcd(el) {
  const year = new Date().getFullYear();
  el.innerHTML = `
    <div class="max-w-lg mx-auto mt-8">
      ${card(`
        <div class="p-6 text-center">
          <div class="w-16 h-16 rounded-2xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center mx-auto mb-4">
            <i data-lucide="file-down" class="w-8 h-8 text-indigo-500"></i>
          </div>
          <h3 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">SPED Contábil (ECD)</h3>
          <p class="text-sm text-slate-400 mb-6">Escrituração Contábil Digital · Guia Prático RFB v9.1<br>Blocos: 0 (Identificação) · I (Plano de Contas) · J (Balanços) · L (Diário) · 9 (Encerramento)</p>

          <div class="flex items-center justify-center gap-4 mb-6">
            <div>
              <label class="label">Ano de Referência</label>
              <select id="ecd-year" class="input text-sm">
                ${[year, year-1, year-2].map(y => `<option value="${y}" ${y===year?'selected':''}>${y}</option>`).join('')}
              </select>
            </div>
            <div>
              <label class="label">Data Início</label>
              <input type="date" id="ecd-start" class="input text-sm" value="${year}-01-01"/>
            </div>
            <div>
              <label class="label">Data Fim</label>
              <input type="date" id="ecd-end" class="input text-sm" value="${year}-12-31"/>
            </div>
          </div>

          <button onclick="downloadEcd()"
            class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-6 py-3 rounded-xl flex items-center gap-2 mx-auto">
            <i data-lucide="download" class="w-4 h-4"></i> Gerar e Baixar ECD (.txt)
          </button>

          <p class="text-xs text-slate-400 mt-4">
            O arquivo gerado segue o formato SPED Contábil para importação no<br>
            <strong>Validador SPED</strong> da Receita Federal do Brasil.
          </p>
        </div>`)}
    </div>`;
}

function downloadEcd() {
  const year = document.getElementById('ecd-year').value;
  const start = document.getElementById('ecd-start').value;
  const end = document.getElementById('ecd-end').value;
  const token = localStorage.getItem('cortex_token') || '';
  const url = `/api/accounting/ecd?year=${year}&start_date=${start}&end_date=${end}`;
  const a = document.createElement('a');
  a.href = url;
  a.setAttribute('download', '');
  // Adicionar header via fetch para download autenticado
  fetch(url, { headers: authHeaders() }).then(r => {
    if (!r.ok) { showToast('Erro ao gerar ECD.', 'error'); return; }
    return r.blob();
  }).then(blob => {
    if (!blob) return;
    const url2 = URL.createObjectURL(blob);
    const a2 = document.createElement('a');
    a2.href = url2;
    a2.download = `ECD_SPED_${year}.txt`;
    a2.click();
    URL.revokeObjectURL(url2);
    showToast('ECD gerado com sucesso!', 'success');
  });
}
