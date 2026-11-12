// ============================================================
// DEPARTAMENTO PESSOAL — Cortex ERP Pro+
// Funcionários · Holerite · Folha · 13º · Férias · Rescisão · eSocial
// ============================================================

function authHeaders() { return {}; }

let dpSubTab = 'funcionarios';
let dpEmployees = [];

// ── helpers ──────────────────────────────────────────────────
const fBRL2  = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fDate2 = s => s ? s.slice(0, 10).split('-').reverse().join('/') : '-';
const card2  = html => `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs">${html}</div>`;

function kpiDP(label, value, sub, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-500 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
    ${sub ? `<div class="text-[11px] text-slate-400 mt-1">${sub}</div>` : ''}
  </div>`;
}

function inputCls() {
  return 'w-full text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500';
}

function labelCls(text) {
  return `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${text}</label>`;
}

// ── sub-tabs bar ─────────────────────────────────────────────
function dpTabs() {
  const tabs = [
    { id: 'funcionarios', icon: 'users',         label: 'Funcionários' },
    { id: 'holerite',     icon: 'receipt',        label: 'Holerite' },
    { id: 'folha',        icon: 'file-spreadsheet',label: 'Folha Mensal' },
    { id: 'decimo',       icon: 'gift',           label: '13º Salário' },
    { id: 'ferias',       icon: 'umbrella',       label: 'Férias' },
    { id: 'rescisao',     icon: 'user-x',         label: 'Rescisão' },
    { id: 'esocial',      icon: 'file-code',      label: 'eSocial' },
    { id: 'afastamentos', icon: 'calendar-x',     label: 'Afastamentos' },
    { id: 'atestados',    icon: 'file-heart',      label: 'Atestados' },
    { id: 'cat',          icon: 'triangle-alert',  label: 'CAT' },
    { id: 'ponto',        icon: 'clock',           label: 'Ponto' },
    { id: 'banco_horas',  icon: 'timer',           label: 'Banco de Horas' },
    { id: 'cargos',       icon: 'briefcase',       label: 'Cargos & Depts' },
    { id: 'historico',    icon: 'trending-up',     label: 'Histórico Salarial' },
    { id: 'obrigacoes',   icon: 'file-check',      label: 'Obrigações' },
  ];
  return `<div class="flex gap-1 overflow-x-auto pb-1 flex-wrap">
    ${tabs.map(t => `
      <button onclick="switchDpTab('${t.id}')" id="dp-tab-${t.id}"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition whitespace-nowrap
          ${dpSubTab === t.id
            ? 'bg-violet-600 text-white'
            : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'}">
        <i data-lucide="${t.icon}" class="w-3.5 h-3.5"></i>${t.label}
      </button>`).join('')}
  </div>`;
}

// ── entry point ──────────────────────────────────────────────
async function renderDp(container) {
  try {
    const r = await fetch('/api/dp/employees?active_only=false', { headers: authHeaders() });
    dpEmployees = await r.json();
  } catch { dpEmployees = []; }

  container.innerHTML = `
    <div id="dp-tabs-bar" class="mb-4">${dpTabs()}</div>
    <div id="dp-body"></div>`;

  await switchDpTab(dpSubTab, true);
  if (window.lucide) lucide.createIcons();
}

async function switchDpTab(tab, noRebuildTabs = false) {
  dpSubTab = tab;
  if (!noRebuildTabs) {
    const bar = document.getElementById('dp-tabs-bar');
    if (bar) { bar.innerHTML = dpTabs(); if (window.lucide) lucide.createIcons(); }
  }
  const body = document.getElementById('dp-body');
  if (!body) return;
  body.innerHTML = `<div class="flex items-center justify-center p-10 text-slate-400">
    <div class="animate-spin rounded-full h-7 w-7 border-b-2 border-violet-500 mr-3"></div>Carregando...</div>`;

  switch (tab) {
    case 'funcionarios': await renderFuncionarios(body); break;
    case 'holerite':     await renderHolerite(body); break;
    case 'folha':        await renderFolha(body); break;
    case 'decimo':       await renderDecimo(body); break;
    case 'ferias':       await renderFerias(body); break;
    case 'rescisao':     renderRescisao(body); break;
    case 'esocial':      renderEsocial(body); break;
    case 'afastamentos': await renderAfastamentos(body); break;
    case 'atestados':    await renderAtestados(body); break;
    case 'cat':          await renderCat(body); break;
    case 'ponto':        await renderPonto(body); break;
    case 'banco_horas':  await renderBancoHoras(body); break;
    case 'cargos':       await renderCargos(body); break;
    case 'historico':    await renderHistoricoSalarial(body); break;
    case 'obrigacoes':   renderObrigacoes(body); break;
  }
  if (window.lucide) lucide.createIcons();
}

// ── 1. FUNCIONÁRIOS ──────────────────────────────────────────
async function renderFuncionarios(el) {
  const ativos   = dpEmployees.filter(e => e.active);
  const inativos = dpEmployees.filter(e => !e.active);

  const rows = dpEmployees.map(emp => `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
      <td class="px-4 py-3 text-sm font-medium text-slate-800 dark:text-slate-200">
        ${emp.name}
        ${emp.is_prolabore ? '<span class="ml-2 text-[10px] font-bold text-purple-500 bg-purple-50 dark:bg-purple-900/30 px-1.5 py-0.5 rounded-full">PRÓ-LABORE</span>' : ''}
      </td>
      <td class="px-4 py-3 text-xs font-mono text-slate-500">${emp.cpf || '-'}</td>
      <td class="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">${emp.role || '-'}</td>
      <td class="px-4 py-3 text-xs text-slate-500">${emp.department || '-'}</td>
      <td class="px-4 py-3 text-sm font-semibold text-emerald-600">${fBRL2(emp.salary)}</td>
      <td class="px-4 py-3 text-xs text-slate-400">${fDate2(emp.admission_date)}</td>
      <td class="px-4 py-3">
        ${emp.active
          ? '<span class="text-[10px] font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">ATIVO</span>'
          : '<span class="text-[10px] font-bold text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">INATIVO</span>'}
      </td>
      <td class="px-4 py-3 text-right whitespace-nowrap">
        <button onclick="openEditEmpModal(${emp.id})" class="text-xs text-indigo-500 hover:underline mr-3">Editar</button>
        ${emp.active
          ? `<button onclick="deactivateEmp(${emp.id},'${emp.name.replace(/'/g,"\\'")}')"\n            class="text-xs text-rose-500 hover:underline">Desligar</button>`
          : ''}
      </td>
    </tr>`).join('');

  el.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
      ${kpiDP('Total de Funcionários', dpEmployees.length, 'ativos + inativos', 'users', 'text-violet-600')}
      ${kpiDP('Ativos', ativos.length, `${inativos.length} inativos`, 'user-check', 'text-emerald-600')}
      ${kpiDP('Folha Bruta Estimada', fBRL2(ativos.reduce((s, e) => s + parseFloat(e.salary || 0), 0)), 'soma dos salários ativos', 'banknote', 'text-blue-600')}
    </div>
    <div class="flex items-center justify-between mb-4">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Funcionários</h2>
      <button onclick="openNewEmpModal()"
        class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="user-plus" class="w-3.5 h-3.5"></i> Novo Funcionário
      </button>
    </div>
    ${card2(`
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left font-semibold">Nome</th>
            <th class="px-4 py-2 text-left font-semibold">CPF</th>
            <th class="px-4 py-2 text-left font-semibold">Cargo</th>
            <th class="px-4 py-2 text-left font-semibold">Departamento</th>
            <th class="px-4 py-2 text-left font-semibold">Salário</th>
            <th class="px-4 py-2 text-left font-semibold">Admissão</th>
            <th class="px-4 py-2 text-left font-semibold">Status</th>
            <th class="px-4 py-2 text-right font-semibold">Ações</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="8" class="px-4 py-8 text-center text-slate-400 text-xs">Nenhum funcionário cadastrado.</td></tr>'}</tbody>
        </table>
      </div>`)}`;
}

function openNewEmpModal() {
  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-2xl w-full">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="user-plus" class="w-5 h-5 text-violet-500"></i> Novo Funcionário
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2">
          ${labelCls('Nome completo *')}
          <input id="emp-name" class="${inputCls()}" placeholder="Nome do funcionário">
        </div>
        <div>
          ${labelCls('CPF *')}
          <input id="emp-cpf" class="${inputCls()}" placeholder="000.000.000-00">
        </div>
        <div>
          ${labelCls('PIS/PASEP')}
          <input id="emp-pis" class="${inputCls()}" placeholder="000.00000.00-0">
        </div>
        <div>
          ${labelCls('Cargo *')}
          <input id="emp-role" class="${inputCls()}" placeholder="ex: Analista">
        </div>
        <div>
          ${labelCls('Departamento')}
          <input id="emp-dept" class="${inputCls()}" placeholder="ex: TI">
        </div>
        <div>
          ${labelCls('Salário Bruto (R$) *')}
          <input id="emp-salary" type="number" step="0.01" class="${inputCls()}" placeholder="0.00">
        </div>
        <div>
          ${labelCls('Data de Admissão *')}
          <input id="emp-admission" type="date" class="${inputCls()}">
        </div>
        <div>
          ${labelCls('Dependentes (IRRF)')}
          <input id="emp-deps" type="number" min="0" value="0" class="${inputCls()}">
        </div>
        <div>
          ${labelCls('Vale-Transporte Mensal (R$)')}
          <input id="emp-vt" type="number" step="0.01" value="0" class="${inputCls()}">
        </div>
        <div>
          ${labelCls('E-mail')}
          <input id="emp-email" type="email" class="${inputCls()}" placeholder="email@empresa.com">
        </div>
        <div>
          ${labelCls('Telefone')}
          <input id="emp-phone" class="${inputCls()}" placeholder="(11) 99999-9999">
        </div>
        <div class="md:col-span-2 flex items-center gap-3">
          <input id="emp-prolabore" type="checkbox" class="rounded">
          <label for="emp-prolabore" class="text-sm text-slate-700 dark:text-slate-300">
            Pró-labore (sócio/administrador) — INSS flat 11%, sem FGTS
          </label>
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="closeModal()" class="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
        <button onclick="saveNewEmp()"
          class="bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold px-5 py-2 rounded-xl">
          Salvar Funcionário
        </button>
      </div>
    </div>`);
  if (window.lucide) lucide.createIcons();
}

async function saveNewEmp() {
  const name       = document.getElementById('emp-name')?.value.trim();
  const cpf        = document.getElementById('emp-cpf')?.value.trim();
  const role       = document.getElementById('emp-role')?.value.trim();
  const salary     = document.getElementById('emp-salary')?.value;
  const admission  = document.getElementById('emp-admission')?.value;

  if (!name || !cpf || !role || !salary || !admission) {
    alert('Preencha os campos obrigatórios: Nome, CPF, Cargo, Salário e Admissão.');
    return;
  }

  const payload = {
    name, cpf, role, salary: parseFloat(salary), admission_date: admission,
    pis_pasep:   document.getElementById('emp-pis')?.value.trim() || null,
    department:  document.getElementById('emp-dept')?.value.trim() || null,
    dependents:  parseInt(document.getElementById('emp-deps')?.value || 0),
    vt_monthly:  parseFloat(document.getElementById('emp-vt')?.value || 0),
    email:       document.getElementById('emp-email')?.value.trim() || null,
    phone:       document.getElementById('emp-phone')?.value.trim() || null,
    is_prolabore: document.getElementById('emp-prolabore')?.checked || false,
  };

  try {
    const r = await fetch('/api/dp/employees', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const err = await r.json();
      alert(err.detail || 'Erro ao salvar.');
      return;
    }
    const emp = await r.json();
    dpEmployees.push(emp);
    closeModal();
    await switchDpTab('funcionarios', true);
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

async function openEditEmpModal(id) {
  let emp = dpEmployees.find(e => e.id === id);
  if (!emp) {
    try {
      const r = await fetch(`/api/dp/employees/${id}`, { headers: authHeaders() });
      emp = await r.json();
    } catch { alert('Erro ao carregar funcionário.'); return; }
  }

  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-2xl w-full">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="user-cog" class="w-5 h-5 text-violet-500"></i> Editar Funcionário
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2">
          ${labelCls('Nome completo *')}
          <input id="edit-emp-name" class="${inputCls()}" value="${emp.name || ''}">
        </div>
        <div>
          ${labelCls('Cargo *')}
          <input id="edit-emp-role" class="${inputCls()}" value="${emp.role || ''}">
        </div>
        <div>
          ${labelCls('Departamento')}
          <input id="edit-emp-dept" class="${inputCls()}" value="${emp.department || ''}">
        </div>
        <div>
          ${labelCls('Salário Bruto (R$) *')}
          <input id="edit-emp-salary" type="number" step="0.01" class="${inputCls()}" value="${emp.salary || ''}">
        </div>
        <div>
          ${labelCls('Dependentes (IRRF)')}
          <input id="edit-emp-deps" type="number" min="0" class="${inputCls()}" value="${emp.dependents || 0}">
        </div>
        <div>
          ${labelCls('Vale-Transporte Mensal (R$)')}
          <input id="edit-emp-vt" type="number" step="0.01" class="${inputCls()}" value="${emp.vt_monthly || 0}">
        </div>
        <div>
          ${labelCls('E-mail')}
          <input id="edit-emp-email" type="email" class="${inputCls()}" value="${emp.email || ''}">
        </div>
        <div>
          ${labelCls('Telefone')}
          <input id="edit-emp-phone" class="${inputCls()}" value="${emp.phone || ''}">
        </div>
        <div class="md:col-span-2 flex items-center gap-3">
          <input id="edit-emp-prolabore" type="checkbox" class="rounded" ${emp.is_prolabore ? 'checked' : ''}>
          <label for="edit-emp-prolabore" class="text-sm text-slate-700 dark:text-slate-300">
            Pró-labore (sócio/administrador)
          </label>
        </div>
      </div>
      <div class="flex justify-end gap-3 mt-6">
        <button onclick="closeModal()" class="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
        <button onclick="saveEditEmp(${id})"
          class="bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold px-5 py-2 rounded-xl">
          Salvar Alterações
        </button>
      </div>
    </div>`);
  if (window.lucide) lucide.createIcons();
}

async function saveEditEmp(id) {
  const payload = {
    name:        document.getElementById('edit-emp-name')?.value.trim() || undefined,
    role:        document.getElementById('edit-emp-role')?.value.trim() || undefined,
    department:  document.getElementById('edit-emp-dept')?.value.trim() || undefined,
    salary:      parseFloat(document.getElementById('edit-emp-salary')?.value) || undefined,
    dependents:  parseInt(document.getElementById('edit-emp-deps')?.value || 0),
    vt_monthly:  parseFloat(document.getElementById('edit-emp-vt')?.value || 0),
    email:       document.getElementById('edit-emp-email')?.value.trim() || undefined,
    phone:       document.getElementById('edit-emp-phone')?.value.trim() || undefined,
    is_prolabore: document.getElementById('edit-emp-prolabore')?.checked,
  };

  try {
    const r = await fetch(`/api/dp/employees/${id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro.'); return; }
    const updated = await r.json();
    const idx = dpEmployees.findIndex(e => e.id === id);
    if (idx >= 0) dpEmployees[idx] = updated;
    closeModal();
    await switchDpTab('funcionarios', true);
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

async function deactivateEmp(id, name) {
  if (!confirm(`Desligar funcionário "${name}"? Ele ficará inativo no sistema.`)) return;
  try {
    const r = await fetch(`/api/dp/employees/${id}`, { method: 'DELETE', headers: authHeaders() });
    if (!r.ok) { alert('Erro ao desligar funcionário.'); return; }
    const idx = dpEmployees.findIndex(e => e.id === id);
    if (idx >= 0) dpEmployees[idx].active = false;
    await switchDpTab('funcionarios', true);
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

// ── 2. HOLERITE ──────────────────────────────────────────────
async function renderHolerite(el) {
  const ativos = dpEmployees.filter(e => e.active);

  const opts = ativos.map(e => `<option value="${e.id}">${e.name} — ${fBRL2(e.salary)}</option>`).join('');

  el.innerHTML = `
    <div class="mb-6">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">Simulação de Holerite</h2>
      <p class="text-xs text-slate-400">Calcula INSS, IRRF e líquido com base no salário cadastrado.</p>
    </div>
    ${card2(`
      <div class="p-5">
        <div class="flex flex-wrap gap-4 items-end mb-6">
          <div>
            ${labelCls('Funcionário')}
            <select id="hol-emp" class="${inputCls()} min-w-[220px]">
              <option value="">Selecione...</option>${opts}
            </select>
          </div>
          <button onclick="calcHolerite()"
            class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-5 py-2 rounded-xl flex items-center gap-2">
            <i data-lucide="calculator" class="w-3.5 h-3.5"></i> Calcular
          </button>
        </div>
        <div id="hol-result"></div>
      </div>`)}`;
}

async function calcHolerite() {
  const empId = document.getElementById('hol-emp')?.value;
  if (!empId) { alert('Selecione um funcionário.'); return; }
  const res = document.getElementById('hol-result');
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    const r = await fetch(`/api/dp/employees/${empId}/holerite-preview`, { headers: authHeaders() });
    if (!r.ok) { res.innerHTML = '<div class="text-xs text-rose-500">Erro ao calcular.</div>'; return; }
    const { employee: emp, holerite: h } = await r.json();

    const linhas = [
      ['Salário Bruto', h.gross_salary, 'text-slate-700 dark:text-slate-200'],
      ['INSS', -h.inss, 'text-rose-500'],
      ['IRRF', -h.irrf, 'text-rose-500'],
      ['VT Desconto', -(h.vt_discount || 0), 'text-orange-500'],
      ['Outros Descontos', -(h.other_discounts || 0), 'text-orange-500'],
    ];
    const rows = linhas.filter(([, v]) => v !== 0).map(([label, val, cls]) => `
      <tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-4 py-2.5 text-sm text-slate-600 dark:text-slate-300">${label}</td>
        <td class="px-4 py-2.5 text-sm font-semibold text-right ${cls}">${val < 0 ? '-' : ''}${fBRL2(Math.abs(val))}</td>
      </tr>`).join('');

    res.innerHTML = `
      <div class="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
        ${emp.name} — ${emp.role || ''}
        ${emp.is_prolabore ? '<span class="ml-2 text-[10px] font-bold text-purple-500 bg-purple-50 dark:bg-purple-900/30 px-1.5 py-0.5 rounded-full">PRÓ-LABORE</span>' : ''}
      </div>
      <table class="w-full max-w-sm mb-4">
        <tbody>${rows}</tbody>
        <tfoot><tr class="border-t-2 border-slate-300 dark:border-slate-600">
          <td class="px-4 py-3 text-sm font-bold text-slate-800 dark:text-slate-100">Salário Líquido</td>
          <td class="px-4 py-3 text-lg font-extrabold text-emerald-600 text-right">${fBRL2(h.net_salary)}</td>
        </tr></tfoot>
      </table>
      <div class="flex gap-4 text-xs text-slate-500">
        <span>FGTS (encargo empresa): <strong class="text-blue-600">${fBRL2(h.fgts)}</strong></span>
        <span>${emp.dependents || 0} dependente(s)</span>
        <span>VT nominal: ${fBRL2(emp.vt_monthly)}</span>
      </div>`;
    if (window.lucide) lucide.createIcons();
  } catch { res.innerHTML = '<div class="text-xs text-rose-500">Erro de conexão.</div>'; }
}

// ── 3. FOLHA MENSAL ──────────────────────────────────────────
async function renderFolha(el) {
  let runs = [];
  try {
    const r = await fetch('/api/dp/payroll', { headers: authHeaders() });
    runs = await r.json();
  } catch { runs = []; }

  const today = new Date();
  const defComp = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;

  const runsRows = runs.map(run => `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition cursor-pointer"
        onclick="openFolhaDetail(${run.id})">
      <td class="px-4 py-3 text-sm font-mono font-semibold text-slate-700 dark:text-slate-200">${run.competence}</td>
      <td class="px-4 py-3 text-xs text-slate-500">${run.employee_count} funcionário(s)</td>
      <td class="px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-200">${fBRL2(run.total_gross)}</td>
      <td class="px-4 py-3 text-sm text-rose-500">-${fBRL2(run.total_discounts)}</td>
      <td class="px-4 py-3 text-sm font-bold text-emerald-600">${fBRL2(run.total_net)}</td>
      <td class="px-4 py-3 text-xs text-blue-500">${fBRL2(run.total_fgts)}</td>
      <td class="px-4 py-3">
        <span class="text-[10px] font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full uppercase">${run.status}</span>
      </td>
      <td class="px-4 py-3 text-right text-xs text-indigo-500 hover:underline">Ver →</td>
    </tr>`).join('');

  el.innerHTML = `
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg">Folha de Pagamento</h2>
        <p class="text-xs text-slate-400 mt-0.5">${runs.length} folha(s) processada(s)</p>
      </div>
      <div class="flex items-center gap-3">
        <input id="folha-comp" type="month" value="${defComp}"
          class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500">
        <button onclick="processFolha()"
          class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
          <i data-lucide="play" class="w-3.5 h-3.5"></i> Processar Folha
        </button>
      </div>
    </div>
    ${card2(`
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left font-semibold">Competência</th>
            <th class="px-4 py-2 text-left font-semibold">Funcionários</th>
            <th class="px-4 py-2 text-left font-semibold">Bruto</th>
            <th class="px-4 py-2 text-left font-semibold">Descontos</th>
            <th class="px-4 py-2 text-left font-semibold">Líquido</th>
            <th class="px-4 py-2 text-left font-semibold">FGTS</th>
            <th class="px-4 py-2 text-left font-semibold">Status</th>
            <th class="px-4 py-2 text-right font-semibold">Detalhe</th>
          </tr></thead>
          <tbody>${runsRows || '<tr><td colspan="8" class="px-4 py-8 text-center text-slate-400 text-xs">Nenhuma folha processada.</td></tr>'}</tbody>
        </table>
      </div>`)}
    <div id="folha-detail-area" class="mt-6"></div>`;
}

async function processFolha() {
  const comp = document.getElementById('folha-comp')?.value;
  if (!comp) { alert('Informe a competência.'); return; }
  if (!confirm(`Processar folha da competência ${comp}?`)) return;
  try {
    const r = await fetch('/api/dp/payroll/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ competence: comp }),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro.'); return; }
    await renderFolha(document.getElementById('dp-body'));
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

async function openFolhaDetail(runId) {
  const area = document.getElementById('folha-detail-area');
  if (!area) return;
  area.innerHTML = '<div class="text-xs text-slate-400 p-4">Carregando...</div>';
  try {
    const r = await fetch(`/api/dp/payroll/${runId}`, { headers: authHeaders() });
    const { run, items } = await r.json();
    const rows = items.map(item => `
      <tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200">${item.employee_name}</td>
        <td class="px-4 py-2.5 text-xs text-slate-500">${item.role || '-'}</td>
        <td class="px-4 py-2.5 text-xs font-mono text-slate-400">${item.matricula || '-'}</td>
        <td class="px-4 py-2.5 text-sm text-slate-600 dark:text-slate-300">${fBRL2(item.gross_salary)}</td>
        <td class="px-4 py-2.5 text-sm text-rose-500">-${fBRL2(item.inss)}</td>
        <td class="px-4 py-2.5 text-sm text-orange-500">-${fBRL2(item.irrf)}</td>
        <td class="px-4 py-2.5 text-sm font-bold text-emerald-600">${fBRL2(item.net_salary)}</td>
        <td class="px-4 py-2.5 text-xs text-blue-500">${fBRL2(item.fgts)}</td>
        <td class="px-4 py-2.5 text-right">
          <button onclick="downloadS1200(${runId},${item.employee_id})"
            class="text-xs text-indigo-500 hover:underline">S-1200</button>
        </td>
      </tr>`).join('');

    area.innerHTML = `
      <h3 class="font-bold text-slate-700 dark:text-slate-200 mb-3">
        Folha ${run.competence} — ${items.length} funcionário(s)
      </h3>
      ${card2(`
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
              <th class="px-4 py-2 text-left font-semibold">Funcionário</th>
              <th class="px-4 py-2 text-left font-semibold">Cargo</th>
              <th class="px-4 py-2 text-left font-semibold">Matrícula</th>
              <th class="px-4 py-2 text-left font-semibold">Bruto</th>
              <th class="px-4 py-2 text-left font-semibold">INSS</th>
              <th class="px-4 py-2 text-left font-semibold">IRRF</th>
              <th class="px-4 py-2 text-left font-semibold">Líquido</th>
              <th class="px-4 py-2 text-left font-semibold">FGTS</th>
              <th class="px-4 py-2 text-right font-semibold">eSocial</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`)}`;
    area.scrollIntoView({ behavior: 'smooth' });
    if (window.lucide) lucide.createIcons();
  } catch { area.innerHTML = '<div class="text-xs text-rose-500 p-4">Erro ao carregar detalhe.</div>'; }
}

// ── 4. 13º SALÁRIO ───────────────────────────────────────────
async function renderDecimo(el) {
  const opts = dpEmployees.filter(e => e.active)
    .map(e => `<option value="${e.id}">${e.name} — ${fBRL2(e.salary)}</option>`).join('');

  el.innerHTML = `
    <div class="mb-6">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">Cálculo de 13º Salário</h2>
      <p class="text-xs text-slate-400">Proporcional pelo número de meses trabalhados no ano.</p>
    </div>
    ${card2(`
      <div class="p-5">
        <div class="flex flex-wrap gap-4 items-end mb-6">
          <div>
            ${labelCls('Funcionário')}
            <select id="dec-emp" class="${inputCls()} min-w-[220px]">
              <option value="">Selecione...</option>${opts}
            </select>
          </div>
          <div>
            ${labelCls('Meses trabalhados')}
            <input id="dec-meses" type="number" min="1" max="12" value="12" class="${inputCls()} w-28">
          </div>
          <button onclick="calcDecimo()"
            class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-5 py-2 rounded-xl flex items-center gap-2">
            <i data-lucide="calculator" class="w-3.5 h-3.5"></i> Calcular
          </button>
        </div>
        <div id="dec-result"></div>
      </div>`)}`;
}

async function calcDecimo() {
  const empId = document.getElementById('dec-emp')?.value;
  const meses = document.getElementById('dec-meses')?.value || 12;
  if (!empId) { alert('Selecione um funcionário.'); return; }
  const res = document.getElementById('dec-result');
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    const r = await fetch(`/api/dp/employees/${empId}/thirteenth?months_worked=${meses}`, { headers: authHeaders() });
    if (!r.ok) { res.innerHTML = '<div class="text-xs text-rose-500">Erro.</div>'; return; }
    const d = await r.json();
    res.innerHTML = `
      <div class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">${d.employee_name}</div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        ${kpiDP('Salário Base', fBRL2(d.salary), `${meses}/12 meses`, 'banknote', 'text-slate-600')}
        ${kpiDP('Bruto 13º', fBRL2(d.gross_thirteenth), 'proporcional', 'gift', 'text-violet-600')}
        ${kpiDP('INSS', fBRL2(d.inss), 'desconto', 'minus-circle', 'text-rose-500')}
        ${kpiDP('Líquido 13º', fBRL2(d.net_thirteenth), '1ª + 2ª parcela', 'check-circle', 'text-emerald-600')}
      </div>
      <div class="mt-4 flex gap-6 text-xs text-slate-500">
        <span>1ª Parcela (nov): <strong>${fBRL2(d.first_installment)}</strong></span>
        <span>2ª Parcela (dez): <strong>${fBRL2(d.second_installment)}</strong></span>
        <span>FGTS: <strong class="text-blue-600">${fBRL2(d.fgts)}</strong></span>
      </div>`;
    if (window.lucide) lucide.createIcons();
  } catch { res.innerHTML = '<div class="text-xs text-rose-500">Erro de conexão.</div>'; }
}

// ── 5. FÉRIAS ─────────────────────────────────────────────────
async function renderFerias(el) {
  const opts = dpEmployees.filter(e => e.active)
    .map(e => `<option value="${e.id}">${e.name} — ${fBRL2(e.salary)}</option>`).join('');

  el.innerHTML = `
    <div class="mb-6">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">Cálculo de Férias</h2>
      <p class="text-xs text-slate-400">Inclui 1/3 constitucional e desconto de INSS/IRRF.</p>
    </div>
    ${card2(`
      <div class="p-5">
        <div class="flex flex-wrap gap-4 items-end mb-6">
          <div>
            ${labelCls('Funcionário')}
            <select id="fer-emp" class="${inputCls()} min-w-[220px]">
              <option value="">Selecione...</option>${opts}
            </select>
          </div>
          <div>
            ${labelCls('Dias de férias')}
            <input id="fer-dias" type="number" min="1" max="30" value="30" class="${inputCls()} w-24">
          </div>
          <button onclick="calcFerias()"
            class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-5 py-2 rounded-xl flex items-center gap-2">
            <i data-lucide="calculator" class="w-3.5 h-3.5"></i> Calcular
          </button>
        </div>
        <div id="fer-result"></div>
      </div>`)}`;
}

async function calcFerias() {
  const empId = document.getElementById('fer-emp')?.value;
  const dias  = document.getElementById('fer-dias')?.value || 30;
  if (!empId) { alert('Selecione um funcionário.'); return; }
  const res = document.getElementById('fer-result');
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    const r = await fetch(`/api/dp/employees/${empId}/vacation?days=${dias}`, { headers: authHeaders() });
    if (!r.ok) { res.innerHTML = '<div class="text-xs text-rose-500">Erro.</div>'; return; }
    const d = await r.json();
    res.innerHTML = `
      <div class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">${d.employee_name} — ${dias} dias</div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        ${kpiDP('Salário Proporcional', fBRL2(d.vacation_salary), `${dias} dias`, 'umbrella', 'text-blue-600')}
        ${kpiDP('1/3 Constitucional', fBRL2(d.one_third), 'adicional', 'plus-circle', 'text-violet-600')}
        ${kpiDP('Bruto Férias', fBRL2(d.gross_vacation), 'antes dos descontos', 'banknote', 'text-slate-600')}
        ${kpiDP('Líquido Férias', fBRL2(d.net_vacation), 'a receber', 'check-circle', 'text-emerald-600')}
      </div>
      <div class="mt-4 flex gap-6 text-xs text-slate-500">
        <span>INSS: <strong class="text-rose-500">-${fBRL2(d.inss)}</strong></span>
        <span>IRRF: <strong class="text-orange-500">-${fBRL2(d.irrf)}</strong></span>
      </div>`;
    if (window.lucide) lucide.createIcons();
  } catch { res.innerHTML = '<div class="text-xs text-rose-500">Erro de conexão.</div>'; }
}

// ── 6. RESCISÃO ───────────────────────────────────────────────
function renderRescisao(el) {
  const opts = dpEmployees.filter(e => e.active)
    .map(e => `<option value="${e.id}">${e.name} — ${fBRL2(e.salary)}</option>`).join('');

  const today = new Date().toISOString().slice(0, 10);

  el.innerHTML = `
    <div class="mb-6">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">Cálculo de Rescisão</h2>
      <p class="text-xs text-slate-400">Saldo de salário, 13º proporcional, férias, aviso prévio e multa FGTS.</p>
    </div>
    ${card2(`
      <div class="p-5">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div>
            ${labelCls('Funcionário')}
            <select id="res-emp" class="${inputCls()}">
              <option value="">Selecione...</option>${opts}
            </select>
          </div>
          <div>
            ${labelCls('Data de Desligamento')}
            <input id="res-date" type="date" value="${today}" class="${inputCls()}">
          </div>
          <div>
            ${labelCls('Tipo de Rescisão')}
            <select id="res-tipo" class="${inputCls()}">
              <option value="sem_justa_causa">Sem Justa Causa (empresa)</option>
              <option value="justa_causa">Justa Causa</option>
              <option value="pedido_demissao">Pedido de Demissão</option>
              <option value="acordo_mutuo">Acordo Mútuo</option>
            </select>
          </div>
          <div class="flex items-end">
            <button onclick="calcRescisao()"
              class="w-full bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-5 py-2 rounded-xl flex items-center justify-center gap-2">
              <i data-lucide="calculator" class="w-3.5 h-3.5"></i> Calcular
            </button>
          </div>
        </div>
        <div id="res-result"></div>
      </div>`)}`;
}

async function calcRescisao() {
  const empId = document.getElementById('res-emp')?.value;
  const date  = document.getElementById('res-date')?.value;
  const tipo  = document.getElementById('res-tipo')?.value;
  if (!empId || !date) { alert('Selecione o funcionário e a data.'); return; }
  const res = document.getElementById('res-result');
  res.innerHTML = '<div class="text-xs text-slate-400">Calculando...</div>';
  try {
    const r = await fetch(`/api/dp/employees/${empId}/termination`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ termination_date: date, termination_type: tipo }),
    });
    if (!r.ok) { const e = await r.json(); res.innerHTML = `<div class="text-xs text-rose-500">${e.detail || 'Erro.'}</div>`; return; }
    const d = await r.json();
    const emp = dpEmployees.find(e => e.id === parseInt(empId));

    const linhas = [
      ['Saldo de Salário', d.salary_balance],
      ['13º Proporcional', d.thirteenth_proportional],
      ['Férias Proporcionais', d.vacation_proportional],
      ['1/3 de Férias', d.vacation_one_third],
      ['Aviso Prévio', d.notice_period],
      ['Multa FGTS (40%)', d.fgts_fine],
    ].filter(([, v]) => v && parseFloat(v) > 0);

    const rows = linhas.map(([label, val]) => `
      <tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-4 py-2.5 text-sm text-slate-600 dark:text-slate-300">${label}</td>
        <td class="px-4 py-2.5 text-sm font-semibold text-slate-800 dark:text-slate-200 text-right">${fBRL2(val)}</td>
      </tr>`).join('');

    res.innerHTML = `
      <div class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">
        ${d.employee_name} — ${tipo.replace(/_/g, ' ')} — ${fDate2(date)}
      </div>
      <table class="w-full max-w-sm mb-4">
        <tbody>${rows}</tbody>
        <tfoot><tr class="border-t-2 border-slate-300 dark:border-slate-600">
          <td class="px-4 py-3 text-sm font-bold text-slate-800 dark:text-slate-100">Total Líquido Rescisão</td>
          <td class="px-4 py-3 text-lg font-extrabold text-emerald-600 text-right">${fBRL2(d.total_net)}</td>
        </tr></tfoot>
      </table>
      <p class="text-xs text-slate-400">
        Meses trabalhados: ${d.months_worked || '-'} &nbsp;·&nbsp;
        INSS: -${fBRL2(d.inss)} &nbsp;·&nbsp;
        IRRF: -${fBRL2(d.irrf)}
      </p>
      ${emp ? `<div class="mt-4">
        <button onclick="downloadS2299(${empId}, document.getElementById('res-date').value, document.getElementById('res-tipo').value)"
          class="text-xs text-indigo-500 hover:underline flex items-center gap-1">
          <i data-lucide="file-down" class="w-3.5 h-3.5"></i> Baixar S-2299 (eSocial Desligamento)
        </button>
      </div>` : ''}`;
    if (window.lucide) lucide.createIcons();
  } catch { res.innerHTML = '<div class="text-xs text-rose-500">Erro de conexão.</div>'; }
}

// ── 7. eSocial ────────────────────────────────────────────────
function renderEsocial(el) {
  const opts = dpEmployees.map(e => `<option value="${e.id}">${e.name}</option>`).join('');

  el.innerHTML = `
    <div class="mb-6">
      <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">eSocial — Geração de Eventos XML</h2>
      <p class="text-xs text-slate-400">Gera os XMLs S-2200 (Admissão), S-1200 (Folha) e S-2299 (Desligamento).</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">

      ${card2(`
        <div class="p-5">
          <div class="flex items-center gap-2 mb-4">
            <i data-lucide="user-check" class="w-5 h-5 text-emerald-500"></i>
            <span class="font-bold text-slate-700 dark:text-slate-200">S-2200 — Admissão</span>
          </div>
          <p class="text-xs text-slate-400 mb-4">Evento de cadastramento inicial do vínculo empregatício.</p>
          <div class="mb-3">
            ${labelCls('Funcionário')}
            <select id="s2200-emp" class="${inputCls()}">${opts}</select>
          </div>
          <button onclick="downloadS2200()"
            class="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center justify-center gap-2">
            <i data-lucide="download" class="w-3.5 h-3.5"></i> Baixar S-2200 XML
          </button>
        </div>`)}

      ${card2(`
        <div class="p-5">
          <div class="flex items-center gap-2 mb-4">
            <i data-lucide="file-text" class="w-5 h-5 text-blue-500"></i>
            <span class="font-bold text-slate-700 dark:text-slate-200">S-1200 — Remuneração</span>
          </div>
          <p class="text-xs text-slate-400 mb-4">Remuneração mensal do trabalhador vinculada a uma folha processada.</p>
          <div class="mb-3">
            ${labelCls('Funcionário')}
            <select id="s1200-emp" class="${inputCls()}">${opts}</select>
          </div>
          <div class="mb-3">
            ${labelCls('Competência (AAAA-MM)')}
            <input id="s1200-comp" type="month" value="${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2,'0')}" class="${inputCls()}">
          </div>
          <button onclick="downloadS1200FromEsocial()"
            class="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center justify-center gap-2">
            <i data-lucide="download" class="w-3.5 h-3.5"></i> Baixar S-1200 XML
          </button>
        </div>`)}

      ${card2(`
        <div class="p-5">
          <div class="flex items-center gap-2 mb-4">
            <i data-lucide="user-x" class="w-5 h-5 text-rose-500"></i>
            <span class="font-bold text-slate-700 dark:text-slate-200">S-2299 — Desligamento</span>
          </div>
          <p class="text-xs text-slate-400 mb-4">Comunicação de rescisão do contrato de trabalho.</p>
          <div class="mb-3">
            ${labelCls('Funcionário')}
            <select id="s2299-emp" class="${inputCls()}">${opts}</select>
          </div>
          <div class="mb-3">
            ${labelCls('Data de Desligamento')}
            <input id="s2299-date" type="date" value="${new Date().toISOString().slice(0,10)}" class="${inputCls()}">
          </div>
          <div class="mb-4">
            ${labelCls('Motivo (eSocial)')}
            <select id="s2299-motivo" class="${inputCls()}">
              <option value="01">01 — Rescisão sem justa causa</option>
              <option value="02">02 — Rescisão por justa causa</option>
              <option value="03">03 — Pedido de demissão</option>
              <option value="10">10 — Acordo mútuo (§ 484-A CLT)</option>
              <option value="11">11 — Término de contrato</option>
            </select>
          </div>
          <button onclick="downloadS2299FromEsocial()"
            class="w-full bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center justify-center gap-2">
            <i data-lucide="download" class="w-3.5 h-3.5"></i> Baixar S-2299 XML
          </button>
        </div>`)}
    </div>`;
}

async function downloadS2200() {
  const empId = document.getElementById('s2200-emp')?.value;
  if (!empId) { alert('Selecione um funcionário.'); return; }
  triggerDownload(`/api/dp/employees/${empId}/esocial/s2200`);
}

async function downloadS1200FromEsocial() {
  const empId = document.getElementById('s1200-emp')?.value;
  const comp  = document.getElementById('s1200-comp')?.value;
  if (!empId || !comp) { alert('Selecione o funcionário e a competência.'); return; }
  try {
    const r = await fetch('/api/dp/payroll', { headers: authHeaders() });
    const runs = await r.json();
    const run = runs.find(r => r.competence === comp);
    if (!run) { alert(`Folha da competência ${comp} não encontrada. Processe-a primeiro na aba Folha Mensal.`); return; }
    triggerDownload(`/api/dp/payroll/${run.id}/employee/${empId}/esocial/s1200`);
  } catch { alert('Erro de conexão.'); }
}

async function downloadS1200(runId, empId) {
  triggerDownload(`/api/dp/payroll/${runId}/employee/${empId}/esocial/s1200`);
}

async function downloadS2299(empId, termDate, terminationType) {
  const motivo = terminationType === 'justa_causa' ? '02'
    : terminationType === 'pedido_demissao' ? '03'
    : terminationType === 'acordo_mutuo' ? '10'
    : '01';
  const r = await fetch(`/api/dp/employees/${empId}/esocial/s2299`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ termination_date: termDate, termination_type: terminationType, motivo_esocial: motivo }),
  });
  if (!r.ok) { alert('Erro ao gerar S-2299.'); return; }
  const blob = await r.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `S2299_${empId}_${termDate.replace(/-/g,'')}.xml`; a.click();
  URL.revokeObjectURL(url);
}

async function downloadS2299FromEsocial() {
  const empId  = document.getElementById('s2299-emp')?.value;
  const date   = document.getElementById('s2299-date')?.value;
  const motivo = document.getElementById('s2299-motivo')?.value;
  if (!empId || !date) { alert('Selecione o funcionário e a data.'); return; }
  const r = await fetch(`/api/dp/employees/${empId}/esocial/s2299`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ termination_date: date, termination_type: 'sem_justa_causa', motivo_esocial: motivo }),
  });
  if (!r.ok) { alert('Erro ao gerar S-2299.'); return; }
  const blob = await r.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `S2299_${empId}_${date.replace(/-/g,'')}.xml`; a.click();
  URL.revokeObjectURL(url);
}

function triggerDownload(url) {
  const a = document.createElement('a');
  a.href = url; a.target = '_blank'; a.click();
}

// ── 8. AFASTAMENTOS ──────────────────────────────────────────
const TIPO_AFASTAMENTO = {
  auxilio_doenca_b31: 'Aux. Doença B31', auxilio_doenca_b91: 'Aux. Doença B91',
  acidente_trabalho: 'Acidente Trabalho', maternidade: 'Maternidade (120d)',
  maternidade_180: 'Maternidade (180d)', paternidade: 'Paternidade (5d)',
  paternidade_20: 'Paternidade (20d)', luto: 'Luto', casamento: 'Casamento',
  doacao_sangue: 'Doação de Sangue', militar: 'Serviço Militar',
  suspensao: 'Suspensão', outros: 'Outros',
};

async function renderAfastamentos(el) {
  let rows = [];
  try { rows = await apiFetch('/api/dp/afastamentos'); } catch { rows = []; }

  const ativos = rows.filter(r => !r.retorno_efetivo);
  const auxDoenca = rows.filter(r => r.tipo?.startsWith('auxilio_doenca') && !r.retorno_efetivo);
  const maternidade = rows.filter(r => r.tipo?.startsWith('maternidade') && !r.retorno_efetivo);
  const totalAno = rows.filter(r => r.data_inicio?.startsWith(new Date().getFullYear().toString())).length;

  const empOpts = dpEmployees.map(e => `<option value="${e.id}">${e.name}</option>`).join('');
  const tipoOpts = Object.entries(TIPO_AFASTAMENTO).map(([v,l]) => `<option value="${v}">${l}</option>`).join('');

  el.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      ${kpiDP('Afastados Ativos', ativos.length, 'sem retorno registrado', 'calendar-x', 'text-rose-600')}
      ${kpiDP('Auxílio Doença', auxDoenca.length, 'B31 + B91 ativos', 'stethoscope', 'text-amber-600')}
      ${kpiDP('Maternidade', maternidade.length, 'ativos', 'baby', 'text-pink-500')}
      ${kpiDP('Total no Ano', totalAno, 'todos os tipos', 'calendar', 'text-violet-600')}
    </div>

    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-bold text-slate-700 dark:text-slate-200">Afastamentos</h3>
        <button onclick="afastOpenModal()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition">+ Registrar</button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="border-b border-slate-100 dark:border-slate-800 text-xs text-slate-500 uppercase">
            <th class="text-left px-3 py-2">Funcionário</th>
            <th class="text-left px-3 py-2">Tipo</th>
            <th class="text-left px-3 py-2">CID</th>
            <th class="text-left px-3 py-2">Início</th>
            <th class="text-left px-3 py-2">Retorno Prev.</th>
            <th class="text-center px-3 py-2">Dias Emp.</th>
            <th class="text-center px-3 py-2">Dias INSS</th>
            <th class="text-left px-3 py-2">Status</th>
            <th class="text-right px-3 py-2">Ações</th>
          </tr></thead>
          <tbody>
            ${rows.length === 0 ? '<tr><td colspan="9" class="text-center py-8 text-slate-400">Nenhum afastamento registrado.</td></tr>' :
              rows.map(r => `
                <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40">
                  <td class="px-3 py-2 font-medium">${r.employee_name || '-'}</td>
                  <td class="px-3 py-2 text-xs">${TIPO_AFASTAMENTO[r.tipo] || r.tipo}</td>
                  <td class="px-3 py-2 font-mono text-xs text-slate-500">${r.cid || '-'}</td>
                  <td class="px-3 py-2 text-xs">${fDate2(r.data_inicio)}</td>
                  <td class="px-3 py-2 text-xs">${r.data_fim ? fDate2(r.data_fim) : '-'}</td>
                  <td class="px-3 py-2 text-center text-xs">${r.dias_empresa || 0}</td>
                  <td class="px-3 py-2 text-center text-xs">${r.dias_inss || 0}</td>
                  <td class="px-3 py-2">
                    ${r.retorno_efetivo
                      ? `<span class="text-[10px] font-bold bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">Retornou ${fDate2(r.retorno_efetivo)}</span>`
                      : '<span class="text-[10px] font-bold bg-rose-50 text-rose-600 dark:bg-rose-900/20 px-2 py-0.5 rounded-full">Afastado</span>'}
                  </td>
                  <td class="px-3 py-2 text-right whitespace-nowrap">
                    ${!r.retorno_efetivo ? `<button onclick="afastRetorno(${r.id})" class="text-xs text-emerald-500 hover:underline mr-2">Retorno</button>` : ''}
                    <button onclick="openAuthed('/api/dp/afastamentos/${r.id}/esocial/s2230','S2230_${r.id}.xml')" class="text-xs text-blue-500 hover:underline mr-2">S-2230</button>
                    <button onclick="afastDelete(${r.id})" class="text-xs text-rose-500 hover:underline">Excluir</button>
                  </td>
                </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <div id="afastModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-lg mx-4">
        <h3 class="font-bold text-lg mb-4 text-slate-800 dark:text-slate-100">Registrar Afastamento</h3>
        <div class="grid grid-cols-2 gap-3">
          <div class="col-span-2">
            ${labelCls('Funcionário')}
            <select id="afastEmp" class="${inputCls()}"><option value="">Selecione...</option>${empOpts}</select>
          </div>
          <div>
            ${labelCls('Tipo de Afastamento')}
            <select id="afastTipo" class="${inputCls()}" onchange="afastCalcDias()">${tipoOpts}</select>
          </div>
          <div>
            ${labelCls('CID (opcional)')}
            <input type="text" id="afastCid" class="${inputCls()}" placeholder="Ex: J11.0">
          </div>
          <div>
            ${labelCls('Data de Início')}
            <input type="date" id="afastInicio" class="${inputCls()}" onchange="afastCalcDias()">
          </div>
          <div>
            ${labelCls('Data Prevista de Retorno')}
            <input type="date" id="afastFim" class="${inputCls()}" onchange="afastCalcDias()">
          </div>
          <div>
            ${labelCls('Dias Empresa (calculado)')}
            <input type="number" id="afastDiasEmp" class="${inputCls()}" value="0" min="0">
          </div>
          <div>
            ${labelCls('Dias INSS (calculado)')}
            <input type="number" id="afastDiasInss" class="${inputCls()}" value="0" min="0">
          </div>
          <div class="col-span-2">
            ${labelCls('Observações')}
            <textarea id="afastObs" class="${inputCls()}" rows="2" placeholder="Observações..."></textarea>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-5">
          <button onclick="afastCloseModal()" class="text-sm px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition">Cancelar</button>
          <button onclick="afastSave()" class="bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold px-5 py-2 rounded-xl transition">Salvar</button>
        </div>
      </div>
    </div>`;

  if (window.lucide) lucide.createIcons();
}

function afastOpenModal() {
  const m = document.getElementById('afastModal');
  if (m) m.style.cssText = 'display:flex!important';
}
function afastCloseModal() {
  const m = document.getElementById('afastModal');
  if (m) m.style.cssText = 'display:none!important';
}
function afastCalcDias() {
  const tipo = document.getElementById('afastTipo')?.value;
  const ini = document.getElementById('afastInicio')?.value;
  const fim = document.getElementById('afastFim')?.value;
  if (!ini || !fim) return;
  const total = Math.max(0, Math.round((new Date(fim) - new Date(ini)) / 86400000) + 1);
  if (['auxilio_doenca_b31','auxilio_doenca_b91','acidente_trabalho'].includes(tipo)) {
    document.getElementById('afastDiasEmp').value = Math.min(total, 15);
    document.getElementById('afastDiasInss').value = Math.max(0, total - 15);
  } else {
    document.getElementById('afastDiasEmp').value = total;
    document.getElementById('afastDiasInss').value = 0;
  }
}
async function afastSave() {
  const empId = document.getElementById('afastEmp')?.value;
  const ini = document.getElementById('afastInicio')?.value;
  if (!empId || !ini) { alert('Funcionário e data de início são obrigatórios.'); return; }
  try {
    await apiFetch('/api/dp/afastamentos', { method: 'POST', body: JSON.stringify({
      employee_id: parseInt(empId),
      tipo: document.getElementById('afastTipo').value,
      cid: document.getElementById('afastCid').value,
      data_inicio: ini,
      data_fim: document.getElementById('afastFim').value,
      dias_empresa: parseInt(document.getElementById('afastDiasEmp').value) || 0,
      dias_inss: parseInt(document.getElementById('afastDiasInss').value) || 0,
      observacoes: document.getElementById('afastObs').value,
    })});
    afastCloseModal();
    switchDpTab('afastamentos');
    if (typeof showToast === 'function') showToast('Afastamento registrado.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}
async function afastRetorno(id) {
  const data = prompt('Data de retorno efetivo (AAAA-MM-DD):');
  if (!data) return;
  try {
    await apiFetch(`/api/dp/afastamentos/${id}/retorno`, { method: 'POST', body: JSON.stringify({ retorno_efetivo: data }) });
    switchDpTab('afastamentos');
    if (typeof showToast === 'function') showToast('Retorno registrado.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}
async function afastDelete(id) {
  if (!confirm('Excluir este afastamento?')) return;
  try {
    await apiFetch(`/api/dp/afastamentos/${id}`, { method: 'DELETE' });
    switchDpTab('afastamentos');
    if (typeof showToast === 'function') showToast('Afastamento excluído.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}

// ── 9. ATESTADOS ──────────────────────────────────────────────
async function renderAtestados(el) {
  let rows = [];
  try { rows = await apiFetch('/api/dp/atestados'); } catch { rows = []; }

  const mesAtual = new Date().toISOString().slice(0, 7);
  const empOpts = dpEmployees.map(e => `<option value="${e.id}">${e.name}</option>`).join('');

  el.innerHTML = `
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-bold text-slate-700 dark:text-slate-200">Atestados Médicos</h3>
        <div class="flex gap-3 items-center">
          <input type="month" id="atestMesFiltro" value="${mesAtual}" class="${inputCls()} w-40" onchange="atestFiltrar()">
          <button onclick="atestOpenModal()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition">+ Registrar</button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="border-b border-slate-100 dark:border-slate-800 text-xs text-slate-500 uppercase">
            <th class="text-left px-3 py-2">Funcionário</th>
            <th class="text-left px-3 py-2">Emissão</th>
            <th class="text-left px-3 py-2">Apresentação</th>
            <th class="text-center px-3 py-2">Dias Afas.</th>
            <th class="text-left px-3 py-2">CID</th>
            <th class="text-left px-3 py-2">Médico</th>
            <th class="text-center px-3 py-2">Justifica Falta</th>
            <th class="text-right px-3 py-2">Ações</th>
          </tr></thead>
          <tbody id="atestTbody">
            ${renderAtestRows(rows, mesAtual)}
          </tbody>
        </table>
      </div>
    </div>

    <div id="atestModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-lg mx-4">
        <h3 class="font-bold text-lg mb-4 text-slate-800 dark:text-slate-100">Registrar Atestado</h3>
        <div class="grid grid-cols-2 gap-3">
          <div class="col-span-2">
            ${labelCls('Funcionário')}
            <select id="atestEmp" class="${inputCls()}"><option value="">Selecione...</option>${empOpts}</select>
          </div>
          <div>
            ${labelCls('Data de Emissão')}
            <input type="date" id="atestEmissao" class="${inputCls()}">
          </div>
          <div>
            ${labelCls('Data de Apresentação')}
            <input type="date" id="atestApres" class="${inputCls()}">
          </div>
          <div>
            ${labelCls('Dias de Afastamento')}
            <input type="number" id="atestDias" class="${inputCls()}" value="1" min="0">
          </div>
          <div>
            ${labelCls('Horas de Afastamento')}
            <input type="number" id="atestHoras" class="${inputCls()}" value="0" min="0" step="0.5">
          </div>
          <div>
            ${labelCls('CID')}
            <input type="text" id="atestCid" class="${inputCls()}" placeholder="Ex: J11.0">
          </div>
          <div>
            ${labelCls('CRM do Médico')}
            <input type="text" id="atestCrm" class="${inputCls()}" placeholder="Ex: 12345/SP">
          </div>
          <div>
            ${labelCls('Nome do Médico')}
            <input type="text" id="atestMedico" class="${inputCls()}" placeholder="Dr. Nome">
          </div>
          <div>
            ${labelCls('Hipótese Diagnóstica')}
            <input type="text" id="atestHipotese" class="${inputCls()}" placeholder="Descrição...">
          </div>
          <div class="col-span-2 flex items-center gap-2">
            <input type="checkbox" id="atestJustifica" checked class="w-4 h-4">
            <label for="atestJustifica" class="text-sm text-slate-600 dark:text-slate-300">Justifica a falta</label>
          </div>
          <div class="col-span-2" id="atestAlertaDias" style="display:none">
            <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl px-4 py-2 text-sm text-amber-700 dark:text-amber-400">
              Atestado ≥ 15 dias — considere vincular a um Afastamento pelo INSS (aba Afastamentos).
            </div>
          </div>
          <div class="col-span-2">
            ${labelCls('Observações')}
            <textarea id="atestObs" class="${inputCls()}" rows="2"></textarea>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-5">
          <button onclick="atestCloseModal()" class="text-sm px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition">Cancelar</button>
          <button onclick="atestSave()" class="bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold px-5 py-2 rounded-xl transition">Salvar</button>
        </div>
      </div>
    </div>`;

  document.getElementById('atestDias')?.addEventListener('input', function() {
    const alert = document.getElementById('atestAlertaDias');
    if (alert) alert.style.display = parseInt(this.value) >= 15 ? '' : 'none';
  });

  if (window.lucide) lucide.createIcons();
}

function renderAtestRows(rows, mes) {
  const filtered = mes ? rows.filter(r => (r.data_apresentacao || r.data_emissao || '').startsWith(mes)) : rows;
  if (!filtered.length) return '<tr><td colspan="8" class="text-center py-8 text-slate-400">Nenhum atestado no período.</td></tr>';
  return filtered.map(r => `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40">
      <td class="px-3 py-2 font-medium">${r.employee_name || '-'}</td>
      <td class="px-3 py-2 text-xs">${fDate2(r.data_emissao)}</td>
      <td class="px-3 py-2 text-xs">${r.data_apresentacao ? fDate2(r.data_apresentacao) : '-'}</td>
      <td class="px-3 py-2 text-center text-xs ${r.dias_afastamento >= 15 ? 'text-amber-600 font-bold' : ''}">${r.dias_afastamento || 0}d</td>
      <td class="px-3 py-2 font-mono text-xs text-slate-500">${r.cid || '-'}</td>
      <td class="px-3 py-2 text-xs">${r.nome_medico || '-'}</td>
      <td class="px-3 py-2 text-center">
        ${r.justifica_falta ? '<span class="text-[10px] font-bold bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">Sim</span>'
                            : '<span class="text-[10px] font-bold bg-slate-100 text-slate-500 dark:bg-slate-800 px-2 py-0.5 rounded-full">Não</span>'}
      </td>
      <td class="px-3 py-2 text-right">
        <button onclick="atestDelete(${r.id})" class="text-xs text-rose-500 hover:underline">Excluir</button>
      </td>
    </tr>`).join('');
}

function atestFiltrar() {
  const mes = document.getElementById('atestMesFiltro')?.value;
  apiFetch('/api/dp/atestados').then(rows => {
    const tbody = document.getElementById('atestTbody');
    if (tbody) tbody.innerHTML = renderAtestRows(rows, mes);
  }).catch(() => {});
}
function atestOpenModal() {
  const m = document.getElementById('atestModal');
  if (m) m.style.cssText = 'display:flex!important';
}
function atestCloseModal() {
  const m = document.getElementById('atestModal');
  if (m) m.style.cssText = 'display:none!important';
}
async function atestSave() {
  const empId = document.getElementById('atestEmp')?.value;
  const emissao = document.getElementById('atestEmissao')?.value;
  if (!empId || !emissao) { alert('Funcionário e data de emissão são obrigatórios.'); return; }
  try {
    await apiFetch('/api/dp/atestados', { method: 'POST', body: JSON.stringify({
      employee_id: parseInt(empId),
      data_emissao: emissao,
      data_apresentacao: document.getElementById('atestApres').value,
      dias_afastamento: parseInt(document.getElementById('atestDias').value) || 0,
      horas_afastamento: parseFloat(document.getElementById('atestHoras').value) || 0,
      cid: document.getElementById('atestCid').value,
      crm_medico: document.getElementById('atestCrm').value,
      nome_medico: document.getElementById('atestMedico').value,
      hipotese_diagnostica: document.getElementById('atestHipotese').value,
      justifica_falta: document.getElementById('atestJustifica').checked,
      observacoes: document.getElementById('atestObs').value,
    })});
    atestCloseModal();
    switchDpTab('atestados');
    if (typeof showToast === 'function') showToast('Atestado registrado.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}
async function atestDelete(id) {
  if (!confirm('Excluir este atestado?')) return;
  try {
    await apiFetch(`/api/dp/atestados/${id}`, { method: 'DELETE' });
    switchDpTab('atestados');
    if (typeof showToast === 'function') showToast('Atestado excluído.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}

// ── 10. CAT ───────────────────────────────────────────────────
async function renderCat(el) {
  let rows = [];
  try { rows = await apiFetch('/api/dp/cat'); } catch { rows = []; }

  const empOpts = dpEmployees.map(e => `<option value="${e.id}">${e.name}</option>`).join('');

  el.innerHTML = `
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="font-bold text-slate-700 dark:text-slate-200">CAT — Comunicação de Acidente de Trabalho</h3>
          <p class="text-xs text-slate-400 mt-0.5">Registre e gere o XML eSocial S-2210</p>
        </div>
        <button onclick="catOpenModal()" class="bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition">+ Registrar CAT</button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="border-b border-slate-100 dark:border-slate-800 text-xs text-slate-500 uppercase">
            <th class="text-left px-3 py-2">Funcionário</th>
            <th class="text-left px-3 py-2">Data Acidente</th>
            <th class="text-left px-3 py-2">Hora</th>
            <th class="text-left px-3 py-2">Tipo</th>
            <th class="text-left px-3 py-2">Local</th>
            <th class="text-center px-3 py-2">Afastamento</th>
            <th class="text-center px-3 py-2">Óbito</th>
            <th class="text-left px-3 py-2">Nº CAT</th>
            <th class="text-right px-3 py-2">Ações</th>
          </tr></thead>
          <tbody>
            ${rows.length === 0 ? '<tr><td colspan="9" class="text-center py-8 text-slate-400">Nenhuma CAT registrada.</td></tr>' :
              rows.map(r => `
                <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40">
                  <td class="px-3 py-2 font-medium">${r.employee_name || '-'}</td>
                  <td class="px-3 py-2 text-xs">${fDate2(r.data_acidente)}</td>
                  <td class="px-3 py-2 text-xs font-mono">${r.hora_acidente || '-'}</td>
                  <td class="px-3 py-2 text-xs capitalize">${r.tipo_acidente || 'típico'}</td>
                  <td class="px-3 py-2 text-xs">${r.local_acidente || '-'}</td>
                  <td class="px-3 py-2 text-center">
                    ${r.houve_afastamento ? '<span class="text-[10px] font-bold bg-amber-50 text-amber-600 dark:bg-amber-900/20 px-2 py-0.5 rounded-full">Sim</span>' : '<span class="text-[10px] font-bold bg-slate-100 text-slate-400 dark:bg-slate-800 px-2 py-0.5 rounded-full">Não</span>'}
                  </td>
                  <td class="px-3 py-2 text-center">
                    ${r.houve_obito ? '<span class="text-[10px] font-bold bg-rose-100 text-rose-700 dark:bg-rose-900/20 px-2 py-0.5 rounded-full">Sim</span>' : '<span class="text-[10px] font-bold bg-slate-100 text-slate-400 dark:bg-slate-800 px-2 py-0.5 rounded-full">Não</span>'}
                  </td>
                  <td class="px-3 py-2 text-xs font-mono">${r.cat_numero || '-'}</td>
                  <td class="px-3 py-2 text-right whitespace-nowrap">
                    <button onclick="openAuthed('/api/dp/cat/${r.id}/esocial/s2210','S2210_${r.id}.xml')" class="text-xs text-blue-500 hover:underline mr-2">S-2210</button>
                    <button onclick="catDelete(${r.id})" class="text-xs text-rose-500 hover:underline">Excluir</button>
                  </td>
                </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <div id="catModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-xl mx-4 max-h-[90vh] overflow-y-auto">
        <h3 class="font-bold text-lg mb-4 text-slate-800 dark:text-slate-100">Registrar CAT</h3>
        <div class="grid grid-cols-2 gap-3">
          <div class="col-span-2">
            ${labelCls('Funcionário')}
            <select id="catEmp" class="${inputCls()}"><option value="">Selecione...</option>${empOpts}</select>
          </div>
          <div>
            ${labelCls('Data do Acidente')}
            <input type="date" id="catData" class="${inputCls()}">
          </div>
          <div>
            ${labelCls('Hora do Acidente')}
            <input type="time" id="catHora" class="${inputCls()}">
          </div>
          <div>
            ${labelCls('Tipo do Acidente')}
            <select id="catTipo" class="${inputCls()}">
              <option value="tipico">Típico</option>
              <option value="trajeto">De Trajeto</option>
              <option value="doenca_trabalho">Doença do Trabalho</option>
            </select>
          </div>
          <div>
            ${labelCls('Local do Acidente')}
            <input type="text" id="catLocal" class="${inputCls()}" placeholder="Ex: Setor de produção">
          </div>
          <div>
            ${labelCls('Parte do Corpo Atingida')}
            <input type="text" id="catParte" class="${inputCls()}" placeholder="Ex: Mão direita">
          </div>
          <div>
            ${labelCls('Agente Causador')}
            <input type="text" id="catAgente" class="${inputCls()}" placeholder="Ex: Máquina cortadora">
          </div>
          <div class="col-span-2">
            ${labelCls('Descrição do Acidente')}
            <textarea id="catDesc" class="${inputCls()}" rows="2" placeholder="Descreva como ocorreu..."></textarea>
          </div>
          <div class="flex items-center gap-2">
            <input type="checkbox" id="catAfastamento" class="w-4 h-4">
            <label for="catAfastamento" class="text-sm text-slate-600 dark:text-slate-300">Houve afastamento</label>
          </div>
          <div>
            ${labelCls('Dias de Afastamento')}
            <input type="number" id="catDiasAfas" class="${inputCls()}" value="0" min="0">
          </div>
          <div class="flex items-center gap-2">
            <input type="checkbox" id="catObito" class="w-4 h-4">
            <label for="catObito" class="text-sm text-rose-600">Houve óbito</label>
          </div>
          <div>
            ${labelCls('Nº da CAT (se já emitida)')}
            <input type="text" id="catNumero" class="${inputCls()}" placeholder="Número oficial">
          </div>
          <div class="col-span-2">
            ${labelCls('Observações')}
            <textarea id="catObs" class="${inputCls()}" rows="2"></textarea>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-5">
          <button onclick="catCloseModal()" class="text-sm px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition">Cancelar</button>
          <button onclick="catSave()" class="bg-rose-600 hover:bg-rose-700 text-white text-sm font-semibold px-5 py-2 rounded-xl transition">Salvar</button>
        </div>
      </div>
    </div>`;

  if (window.lucide) lucide.createIcons();
}

function catOpenModal() {
  const m = document.getElementById('catModal');
  if (m) m.style.cssText = 'display:flex!important';
}
function catCloseModal() {
  const m = document.getElementById('catModal');
  if (m) m.style.cssText = 'display:none!important';
}
async function catSave() {
  const empId = document.getElementById('catEmp')?.value;
  const data = document.getElementById('catData')?.value;
  if (!empId || !data) { alert('Funcionário e data do acidente são obrigatórios.'); return; }
  try {
    await apiFetch('/api/dp/cat', { method: 'POST', body: JSON.stringify({
      employee_id: parseInt(empId),
      data_acidente: data,
      hora_acidente: document.getElementById('catHora').value,
      local_acidente: document.getElementById('catLocal').value,
      tipo_acidente: document.getElementById('catTipo').value,
      parte_corpo: document.getElementById('catParte').value,
      agente_causador: document.getElementById('catAgente').value,
      descricao: document.getElementById('catDesc').value,
      houve_afastamento: document.getElementById('catAfastamento').checked,
      dias_afastamento: parseInt(document.getElementById('catDiasAfas').value) || 0,
      houve_obito: document.getElementById('catObito').checked,
      cat_numero: document.getElementById('catNumero').value,
      observacoes: document.getElementById('catObs').value,
    })});
    catCloseModal();
    switchDpTab('cat');
    if (typeof showToast === 'function') showToast('CAT registrada.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}
async function catDelete(id) {
  if (!confirm('Excluir esta CAT?')) return;
  try {
    await apiFetch(`/api/dp/cat/${id}`, { method: 'DELETE' });
    switchDpTab('cat');
    if (typeof showToast === 'function') showToast('CAT excluída.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}

// ── PONTO ELETRÔNICO ─────────────────────────────────────────────────────────

let pontoEmpId = null;
let pontoMes = new Date().toISOString().slice(0, 7);

async function renderPonto(el) {
  const empOpts = dpEmployees.filter(e => e.active).map(e =>
    `<option value="${e.id}">${e.name}</option>`).join('');
  el.innerHTML = `
    <div class="flex flex-wrap gap-3 mb-5 items-end">
      <div>
        ${labelCls('Funcionário')}
        <select id="ponto-emp" class="${inputCls()}" onchange="pontoLoad()" style="min-width:200px">
          <option value="">Selecione...</option>${empOpts}
        </select>
      </div>
      <div>
        ${labelCls('Mês')}
        <input type="month" id="ponto-mes" value="${pontoMes}" class="${inputCls()}" onchange="pontoLoad()">
      </div>
      <button onclick="pontoOpenModal()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i> Lançar
      </button>
      <button onclick="pontoEspelho()" class="bg-slate-600 hover:bg-slate-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="printer" class="w-3.5 h-3.5"></i> Espelho
      </button>
    </div>
    <div id="ponto-kpis" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5"></div>
    <div id="ponto-table"></div>
    <div id="ponto-modal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-lg">
        <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-4">Lançar Ponto</h3>
        <input type="hidden" id="ponto-rec-id">
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div>${labelCls('Data')}<input type="date" id="ponto-data" class="${inputCls()}"></div>
          <div>${labelCls('Ocorrência')}
            <select id="ponto-ocorrencia" class="${inputCls()}">
              <option value="normal">Normal</option>
              <option value="falta_justificada">Falta Justificada</option>
              <option value="falta_injustificada">Falta Injustificada</option>
              <option value="feriado">Feriado</option>
              <option value="folga">Folga</option>
              <option value="afastamento">Afastamento</option>
              <option value="meio_periodo">Meio Período</option>
            </select>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div>${labelCls('Entrada')}<input type="time" id="ponto-entrada" class="${inputCls()}"></div>
          <div>${labelCls('Saída Almoço')}<input type="time" id="ponto-saida-alm" class="${inputCls()}"></div>
          <div>${labelCls('Retorno Almoço')}<input type="time" id="ponto-ret-alm" class="${inputCls()}"></div>
          <div>${labelCls('Saída')}<input type="time" id="ponto-saida" class="${inputCls()}"></div>
        </div>
        <div class="mb-3">${labelCls('Justificativa')}<input type="text" id="ponto-justif" class="${inputCls()}" placeholder="Opcional"></div>
        <div class="flex justify-end gap-2">
          <button onclick="pontoCloseModal()" class="text-xs px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300">Cancelar</button>
          <button onclick="pontoSave()" class="bg-violet-600 text-white text-xs font-semibold px-4 py-2 rounded-xl">Salvar</button>
        </div>
      </div>
    </div>`;
  if (window.lucide) lucide.createIcons();
  if (pontoEmpId) {
    document.getElementById('ponto-emp').value = pontoEmpId;
    await pontoLoad();
  }
}

async function pontoLoad() {
  const empSel = document.getElementById('ponto-emp');
  const mesSel = document.getElementById('ponto-mes');
  if (!empSel || !mesSel) return;
  pontoEmpId = empSel.value ? parseInt(empSel.value) : null;
  pontoMes = mesSel.value;
  if (!pontoEmpId) return;
  try {
    const rows = await apiFetch(`/api/dp/ponto?employee_id=${pontoEmpId}&mes=${pontoMes}`);
    const kpiEl = document.getElementById('ponto-kpis');
    const tblEl = document.getElementById('ponto-table');
    if (!kpiEl || !tblEl) return;
    const totalDias = rows.filter(r => r.tipo_ocorrencia === 'normal' || r.tipo_ocorrencia === 'meio_periodo').length;
    const totalExtra = rows.reduce((s, r) => s + (r.horas_extras || 0), 0);
    const totalFalt = rows.filter(r => r.tipo_ocorrencia === 'falta_justificada' || r.tipo_ocorrencia === 'falta_injustificada').length;
    kpiEl.innerHTML = [
      kpiDP('Dias Trabalhados', totalDias, pontoMes, 'calendar-check', 'text-emerald-600'),
      kpiDP('Horas Extras', totalExtra.toFixed(2) + 'h', 'no mês', 'clock', 'text-blue-600'),
      kpiDP('Faltas', totalFalt, 'no mês', 'calendar-x', 'text-rose-500'),
    ].join('');
    const ocorClass = {
      normal: 'text-emerald-600', falta_justificada: 'text-amber-500', falta_injustificada: 'text-rose-500',
      feriado: 'text-blue-500', folga: 'text-purple-500', afastamento: 'text-orange-500', meio_periodo: 'text-teal-500',
    };
    const trs = rows.map(r => `
      <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40">
        <td class="px-3 py-2 text-xs">${fDate2(r.data)}</td>
        <td class="px-3 py-2 text-xs font-mono">${r.entrada || '-'}</td>
        <td class="px-3 py-2 text-xs font-mono">${r.saida_almoco || '-'}</td>
        <td class="px-3 py-2 text-xs font-mono">${r.retorno_almoco || '-'}</td>
        <td class="px-3 py-2 text-xs font-mono">${r.saida || '-'}</td>
        <td class="px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200">${(r.horas_trabalhadas || 0).toFixed(2)}h</td>
        <td class="px-3 py-2 text-xs text-blue-600 font-semibold">${(r.horas_extras || 0) > 0 ? '+' + r.horas_extras.toFixed(2) + 'h' : '-'}</td>
        <td class="px-3 py-2 text-xs text-rose-500">${(r.horas_faltantes || 0) > 0 ? '-' + r.horas_faltantes.toFixed(2) + 'h' : '-'}</td>
        <td class="px-3 py-2 text-xs font-semibold ${ocorClass[r.tipo_ocorrencia] || ''}">${r.tipo_ocorrencia}</td>
        <td class="px-3 py-2 text-xs">${r.aprovado ? '✓' : ''}</td>
        <td class="px-3 py-2 text-xs whitespace-nowrap">
          <button onclick="pontoEdit(${JSON.stringify(r).replace(/"/g,'&quot;')})" class="text-indigo-500 hover:underline mr-2">Editar</button>
          <button onclick="pontoDelete(${r.id})" class="text-rose-500 hover:underline">Excluir</button>
        </td>
      </tr>`).join('');
    tblEl.innerHTML = `${card2(`<div class="overflow-x-auto"><table class="w-full text-sm">
      <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
        <th class="px-3 py-2 text-left">Data</th><th class="px-3 py-2">Entrada</th><th class="px-3 py-2">S.Almoço</th>
        <th class="px-3 py-2">R.Almoço</th><th class="px-3 py-2">Saída</th><th class="px-3 py-2">H.Trab</th>
        <th class="px-3 py-2">H.Extra</th><th class="px-3 py-2">H.Falt</th><th class="px-3 py-2">Ocorrência</th>
        <th class="px-3 py-2">Aprov</th><th class="px-3 py-2">Ações</th>
      </tr></thead>
      <tbody>${trs || '<tr><td colspan="11" class="px-3 py-6 text-center text-slate-400 text-xs">Nenhum registro.</td></tr>'}</tbody>
    </table></div>`)}`;
    if (window.lucide) lucide.createIcons();
  } catch (e) { console.error(e); }
}

function pontoOpenModal() {
  document.getElementById('ponto-rec-id').value = '';
  document.getElementById('ponto-data').value = new Date().toISOString().slice(0,10);
  ['ponto-entrada','ponto-saida-alm','ponto-ret-alm','ponto-saida'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('ponto-ocorrencia').value = 'normal';
  document.getElementById('ponto-justif').value = '';
  document.getElementById('ponto-modal').style.display = 'flex';
}

function pontoEdit(r) {
  document.getElementById('ponto-rec-id').value = r.id;
  document.getElementById('ponto-data').value = r.data || '';
  document.getElementById('ponto-entrada').value = r.entrada || '';
  document.getElementById('ponto-saida-alm').value = r.saida_almoco || '';
  document.getElementById('ponto-ret-alm').value = r.retorno_almoco || '';
  document.getElementById('ponto-saida').value = r.saida || '';
  document.getElementById('ponto-ocorrencia').value = r.tipo_ocorrencia || 'normal';
  document.getElementById('ponto-justif').value = r.justificativa || '';
  document.getElementById('ponto-modal').style.display = 'flex';
}

function pontoCloseModal() {
  document.getElementById('ponto-modal').style.display = 'none';
}

async function pontoSave() {
  if (!pontoEmpId) { alert('Selecione um funcionário primeiro.'); return; }
  const body = {
    employee_id: pontoEmpId,
    data: document.getElementById('ponto-data').value,
    entrada: document.getElementById('ponto-entrada').value,
    saida_almoco: document.getElementById('ponto-saida-alm').value,
    retorno_almoco: document.getElementById('ponto-ret-alm').value,
    saida: document.getElementById('ponto-saida').value,
    tipo_ocorrencia: document.getElementById('ponto-ocorrencia').value,
    justificativa: document.getElementById('ponto-justif').value,
  };
  try {
    await apiFetch('/api/dp/ponto', { method: 'POST', body: JSON.stringify(body) });
    pontoCloseModal();
    pontoLoad();
    if (typeof showToast === 'function') showToast('Ponto salvo.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}

async function pontoDelete(id) {
  if (!confirm('Excluir este registro?')) return;
  try {
    await apiFetch(`/api/dp/ponto/${id}`, { method: 'DELETE' });
    pontoLoad();
    if (typeof showToast === 'function') showToast('Excluído.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}

async function pontoEspelho() {
  if (!pontoEmpId) { alert('Selecione um funcionário.'); return; }
  try {
    const d = await apiFetch(`/api/dp/ponto/espelho/${pontoEmpId}/${pontoMes}`);
    const trs = (d.registros || []).map(r => `
      <tr><td>${fDate2(r.data)}</td><td>${r.entrada||'-'}</td><td>${r.saida_almoco||'-'}</td>
      <td>${r.retorno_almoco||'-'}</td><td>${r.saida||'-'}</td>
      <td>${(r.horas_trabalhadas||0).toFixed(2)}h</td><td>${r.tipo_ocorrencia}</td></tr>`).join('');
    const w = window.open('', '_blank');
    w.document.write(`<html><head><title>Espelho de Ponto</title>
      <style>body{font-family:sans-serif;padding:20px}table{width:100%;border-collapse:collapse}
      th,td{border:1px solid #ccc;padding:6px 10px;text-align:left}th{background:#f5f5f5}</style></head>
      <body><h2>Espelho de Ponto — ${d.employee_name} — ${pontoMes}</h2>
      <p>Total trabalhado: <b>${d.total_horas_trabalhadas}h</b> | Extras: <b>${d.total_horas_extras}h</b> | Faltas: <b>${d.total_faltas}</b> | Banco: <b>${d.saldo_banco}h</b></p>
      <table><thead><tr><th>Data</th><th>Entrada</th><th>S.Almoço</th><th>R.Almoço</th><th>Saída</th><th>H.Trab</th><th>Ocorrência</th></tr></thead>
      <tbody>${trs}</tbody></table></body></html>`);
    w.document.close();
  } catch (e) { alert('Erro: ' + e.message); }
}

// ── BANCO DE HORAS ───────────────────────────────────────────────────────────

let bhEmpId = null;

async function renderBancoHoras(el) {
  const empOpts = dpEmployees.filter(e => e.active).map(e =>
    `<option value="${e.id}">${e.name}</option>`).join('');
  el.innerHTML = `
    <div class="flex gap-3 items-end mb-5">
      <div>
        ${labelCls('Funcionário')}
        <select id="bh-emp" class="${inputCls()}" onchange="bhLoad()" style="min-width:220px">
          <option value="">Selecione...</option>${empOpts}
        </select>
      </div>
    </div>
    <div id="bh-saldo"></div>
    <div id="bh-hist"></div>
    <div id="bh-modal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-sm">
        <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-4">Compensar Horas</h3>
        <div class="mb-3">${labelCls('Data')}<input type="date" id="bh-data" class="${inputCls()}" value="${new Date().toISOString().slice(0,10)}"></div>
        <div class="mb-3">${labelCls('Horas a compensar')}<input type="number" id="bh-horas" class="${inputCls()}" placeholder="ex: 2.5" step="0.5" min="0.5"></div>
        <div class="mb-4">${labelCls('Observação')}<input type="text" id="bh-obs" class="${inputCls()}"></div>
        <div class="flex justify-end gap-2">
          <button onclick="bhCloseModal()" class="text-xs px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700">Cancelar</button>
          <button onclick="bhSave()" class="bg-violet-600 text-white text-xs font-semibold px-4 py-2 rounded-xl">Compensar</button>
        </div>
      </div>
    </div>`;
  if (bhEmpId) {
    document.getElementById('bh-emp').value = bhEmpId;
    await bhLoad();
  }
}

async function bhLoad() {
  const sel = document.getElementById('bh-emp');
  if (!sel) return;
  bhEmpId = sel.value ? parseInt(sel.value) : null;
  if (!bhEmpId) return;
  try {
    const d = await apiFetch(`/api/dp/banco-horas?employee_id=${bhEmpId}`);
    const saldoEl = document.getElementById('bh-saldo');
    const histEl = document.getElementById('bh-hist');
    const saldo = d.saldo || 0;
    const cor = saldo >= 0 ? 'text-emerald-600' : 'text-rose-500';
    const bg = saldo >= 0 ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200' : 'bg-rose-50 dark:bg-rose-900/20 border-rose-200';
    saldoEl.innerHTML = `
      <div class="rounded-2xl border p-5 mb-4 ${bg} flex items-center justify-between">
        <div>
          <div class="text-xs font-semibold text-slate-500 mb-1">Saldo Atual</div>
          <div class="text-3xl font-extrabold ${cor}">${saldo >= 0 ? '+' : ''}${saldo.toFixed(2)}h</div>
          <div class="text-xs text-slate-400 mt-1">${Math.floor(Math.abs(saldo))}h ${Math.round((Math.abs(saldo) % 1) * 60)}min</div>
        </div>
        <button onclick="bhOpenModal()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">
          Compensar Horas
        </button>
      </div>`;
    const rows = (d.historico || []).map(r => {
      const tipoColor = r.tipo === 'credito' ? 'text-emerald-600' : r.tipo === 'compensacao' ? 'text-amber-500' : 'text-rose-500';
      return `<tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-3 py-2 text-xs">${fDate2(r.data)}</td>
        <td class="px-3 py-2 text-xs font-semibold ${tipoColor}">${r.tipo}</td>
        <td class="px-3 py-2 text-xs font-semibold ${r.horas >= 0 ? 'text-emerald-600' : 'text-rose-500'}">${r.horas >= 0 ? '+' : ''}${(r.horas || 0).toFixed(2)}h</td>
        <td class="px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200">${(r.saldo_acumulado || 0).toFixed(2)}h</td>
        <td class="px-3 py-2 text-xs text-slate-500">${r.observacao || '-'}</td>
      </tr>`;
    }).join('');
    histEl.innerHTML = `${card2(`<div class="overflow-x-auto"><table class="w-full text-sm">
      <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
        <th class="px-3 py-2 text-left">Data</th><th class="px-3 py-2">Tipo</th>
        <th class="px-3 py-2">Horas</th><th class="px-3 py-2">Saldo</th><th class="px-3 py-2">Observação</th>
      </tr></thead>
      <tbody>${rows || '<tr><td colspan="5" class="px-3 py-6 text-center text-slate-400 text-xs">Nenhum lançamento.</td></tr>'}</tbody>
    </table></div>`)}`;
    if (window.lucide) lucide.createIcons();
  } catch (e) { console.error(e); }
}

function bhOpenModal() { document.getElementById('bh-modal').style.display = 'flex'; }
function bhCloseModal() { document.getElementById('bh-modal').style.display = 'none'; }

async function bhSave() {
  if (!bhEmpId) return;
  const body = {
    employee_id: bhEmpId,
    data: document.getElementById('bh-data').value,
    horas: parseFloat(document.getElementById('bh-horas').value || 0),
    observacao: document.getElementById('bh-obs').value,
  };
  try {
    await apiFetch('/api/dp/banco-horas/compensar', { method: 'POST', body: JSON.stringify(body) });
    bhCloseModal();
    bhLoad();
    if (typeof showToast === 'function') showToast('Compensação registrada.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}

// ── CARGOS & DEPARTAMENTOS ───────────────────────────────────────────────────

let cargosSubTab = 'cargos';

async function renderCargos(el) {
  el.innerHTML = `
    <div class="flex gap-2 mb-5">
      <button onclick="cargosTab('cargos')" id="ct-cargos"
        class="px-4 py-2 rounded-xl text-xs font-semibold bg-violet-600 text-white">Cargos</button>
      <button onclick="cargosTab('depts')" id="ct-depts"
        class="px-4 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">Departamentos</button>
    </div>
    <div id="cargos-body"></div>
    <div id="cargo-modal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-md">
        <h3 id="cargo-modal-title" class="font-bold text-slate-800 dark:text-slate-100 mb-4">Novo Cargo</h3>
        <input type="hidden" id="cargo-id">
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div class="col-span-2">${labelCls('Nome do Cargo')}<input type="text" id="cargo-nome" class="${inputCls()}"></div>
          <div>${labelCls('CBO')}<input type="text" id="cargo-cbo" class="${inputCls()}" placeholder="ex: 2124-20"></div>
          <div>${labelCls('Nível')}<input type="text" id="cargo-nivel" class="${inputCls()}" placeholder="ex: Júnior"></div>
          <div>${labelCls('Salário Base (R$)')}<input type="number" id="cargo-sal-base" class="${inputCls()}" step="0.01"></div>
          <div>${labelCls('Salário Máx (R$)')}<input type="number" id="cargo-sal-max" class="${inputCls()}" step="0.01"></div>
        </div>
        <div class="mb-4">${labelCls('Descrição')}<input type="text" id="cargo-desc" class="${inputCls()}"></div>
        <div class="flex justify-end gap-2">
          <button onclick="cargoCloseModal()" class="text-xs px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700">Cancelar</button>
          <button onclick="cargoSave()" class="bg-violet-600 text-white text-xs font-semibold px-4 py-2 rounded-xl">Salvar</button>
        </div>
      </div>
    </div>
    <div id="dept-modal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-sm">
        <h3 id="dept-modal-title" class="font-bold text-slate-800 dark:text-slate-100 mb-4">Novo Departamento</h3>
        <input type="hidden" id="dept-id">
        <div class="mb-3">${labelCls('Nome')}<input type="text" id="dept-nome" class="${inputCls()}"></div>
        <div class="mb-3">${labelCls('Código')}<input type="text" id="dept-codigo" class="${inputCls()}"></div>
        <div class="mb-4">${labelCls('Responsável')}
          <select id="dept-resp" class="${inputCls()}">
            <option value="">Nenhum</option>
            ${dpEmployees.filter(e => e.active).map(e => `<option value="${e.id}">${e.name}</option>`).join('')}
          </select>
        </div>
        <div class="flex justify-end gap-2">
          <button onclick="deptCloseModal()" class="text-xs px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700">Cancelar</button>
          <button onclick="deptSave()" class="bg-violet-600 text-white text-xs font-semibold px-4 py-2 rounded-xl">Salvar</button>
        </div>
      </div>
    </div>`;
  cargosSubTab = 'cargos';
  await cargosLoadBody();
}

async function cargosTab(t) {
  cargosSubTab = t;
  ['cargos','depts'].forEach(id => {
    const btn = document.getElementById(`ct-${id}`);
    if (btn) {
      btn.className = id === t
        ? 'px-4 py-2 rounded-xl text-xs font-semibold bg-violet-600 text-white'
        : 'px-4 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800';
    }
  });
  await cargosLoadBody();
}

async function cargosLoadBody() {
  const body = document.getElementById('cargos-body');
  if (!body) return;
  if (cargosSubTab === 'cargos') {
    const rows = await apiFetch('/api/dp/job-positions');
    const trs = rows.map(r => `
      <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40">
        <td class="px-3 py-2 text-sm font-medium text-slate-800 dark:text-slate-200">${r.nome}</td>
        <td class="px-3 py-2 text-xs font-mono">${r.cbo || '-'}</td>
        <td class="px-3 py-2 text-xs">${r.nivel || '-'}</td>
        <td class="px-3 py-2 text-xs text-emerald-600 font-semibold">${fBRL2(r.salario_base)}</td>
        <td class="px-3 py-2 text-xs text-blue-600 font-semibold">${fBRL2(r.salario_maximo)}</td>
        <td class="px-3 py-2"><span class="text-[10px] font-bold ${r.ativo ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20' : 'text-slate-400 bg-slate-100 dark:bg-slate-800'} px-2 py-0.5 rounded-full">${r.ativo ? 'ATIVO' : 'INATIVO'}</span></td>
        <td class="px-3 py-2 whitespace-nowrap">
          <button onclick="cargoEdit(${JSON.stringify(r).replace(/"/g,'&quot;')})" class="text-indigo-500 hover:underline text-xs mr-2">Editar</button>
          <button onclick="cargoDelete(${r.id})" class="text-rose-500 hover:underline text-xs">Excluir</button>
        </td>
      </tr>`).join('');
    body.innerHTML = `
      <div class="flex justify-end mb-3">
        <button onclick="cargoOpenModal()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i> Novo Cargo
        </button>
      </div>
      ${card2(`<div class="overflow-x-auto"><table class="w-full text-sm">
        <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
          <th class="px-3 py-2 text-left">Cargo</th><th class="px-3 py-2">CBO</th><th class="px-3 py-2">Nível</th>
          <th class="px-3 py-2">Sal. Base</th><th class="px-3 py-2">Sal. Máx</th><th class="px-3 py-2">Status</th><th class="px-3 py-2">Ações</th>
        </tr></thead>
        <tbody>${trs || '<tr><td colspan="7" class="px-3 py-6 text-center text-slate-400 text-xs">Nenhum cargo cadastrado.</td></tr>'}</tbody>
      </table></div>`)}`;
  } else {
    const rows = await apiFetch('/api/dp/departments');
    const trs = rows.map(r => `
      <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40">
        <td class="px-3 py-2 text-sm font-medium text-slate-800 dark:text-slate-200">${r.nome}</td>
        <td class="px-3 py-2 text-xs font-mono">${r.codigo || '-'}</td>
        <td class="px-3 py-2 text-xs">${r.responsavel_nome || '-'}</td>
        <td class="px-3 py-2 whitespace-nowrap">
          <button onclick="deptEdit(${JSON.stringify(r).replace(/"/g,'&quot;')})" class="text-indigo-500 hover:underline text-xs mr-2">Editar</button>
          <button onclick="deptDelete(${r.id})" class="text-rose-500 hover:underline text-xs">Excluir</button>
        </td>
      </tr>`).join('');
    body.innerHTML = `
      <div class="flex justify-end mb-3">
        <button onclick="deptOpenModal()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i> Novo Departamento
        </button>
      </div>
      ${card2(`<div class="overflow-x-auto"><table class="w-full text-sm">
        <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
          <th class="px-3 py-2 text-left">Departamento</th><th class="px-3 py-2">Código</th>
          <th class="px-3 py-2">Responsável</th><th class="px-3 py-2">Ações</th>
        </tr></thead>
        <tbody>${trs || '<tr><td colspan="4" class="px-3 py-6 text-center text-slate-400 text-xs">Nenhum departamento.</td></tr>'}</tbody>
      </table></div>`)}`;
  }
  if (window.lucide) lucide.createIcons();
}

function cargoOpenModal() {
  document.getElementById('cargo-modal-title').textContent = 'Novo Cargo';
  ['cargo-id','cargo-nome','cargo-cbo','cargo-nivel','cargo-desc'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('cargo-sal-base').value = 0;
  document.getElementById('cargo-sal-max').value = 0;
  document.getElementById('cargo-modal').style.display = 'flex';
}
function cargoEdit(r) {
  document.getElementById('cargo-modal-title').textContent = 'Editar Cargo';
  document.getElementById('cargo-id').value = r.id;
  document.getElementById('cargo-nome').value = r.nome || '';
  document.getElementById('cargo-cbo').value = r.cbo || '';
  document.getElementById('cargo-nivel').value = r.nivel || '';
  document.getElementById('cargo-sal-base').value = r.salario_base || 0;
  document.getElementById('cargo-sal-max').value = r.salario_maximo || 0;
  document.getElementById('cargo-desc').value = r.descricao || '';
  document.getElementById('cargo-modal').style.display = 'flex';
}
function cargoCloseModal() { document.getElementById('cargo-modal').style.display = 'none'; }
async function cargoSave() {
  const id = document.getElementById('cargo-id').value;
  const body = {
    nome: document.getElementById('cargo-nome').value,
    cbo: document.getElementById('cargo-cbo').value,
    nivel: document.getElementById('cargo-nivel').value,
    salario_base: parseFloat(document.getElementById('cargo-sal-base').value || 0),
    salario_maximo: parseFloat(document.getElementById('cargo-sal-max').value || 0),
    descricao: document.getElementById('cargo-desc').value,
  };
  try {
    if (id) await apiFetch(`/api/dp/job-positions/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    else await apiFetch('/api/dp/job-positions', { method: 'POST', body: JSON.stringify(body) });
    cargoCloseModal();
    cargosLoadBody();
    if (typeof showToast === 'function') showToast('Cargo salvo.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}
async function cargoDelete(id) {
  if (!confirm('Excluir este cargo?')) return;
  await apiFetch(`/api/dp/job-positions/${id}`, { method: 'DELETE' });
  cargosLoadBody();
}

function deptOpenModal() {
  document.getElementById('dept-modal-title').textContent = 'Novo Departamento';
  ['dept-id','dept-nome','dept-codigo'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('dept-resp').value = '';
  document.getElementById('dept-modal').style.display = 'flex';
}
function deptEdit(r) {
  document.getElementById('dept-modal-title').textContent = 'Editar Departamento';
  document.getElementById('dept-id').value = r.id;
  document.getElementById('dept-nome').value = r.nome || '';
  document.getElementById('dept-codigo').value = r.codigo || '';
  document.getElementById('dept-resp').value = r.responsavel_id || '';
  document.getElementById('dept-modal').style.display = 'flex';
}
function deptCloseModal() { document.getElementById('dept-modal').style.display = 'none'; }
async function deptSave() {
  const id = document.getElementById('dept-id').value;
  const body = {
    nome: document.getElementById('dept-nome').value,
    codigo: document.getElementById('dept-codigo').value,
    responsavel_id: document.getElementById('dept-resp').value || null,
  };
  try {
    if (id) await apiFetch(`/api/dp/departments/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    else await apiFetch('/api/dp/departments', { method: 'POST', body: JSON.stringify(body) });
    deptCloseModal();
    cargosLoadBody();
    if (typeof showToast === 'function') showToast('Departamento salvo.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}
async function deptDelete(id) {
  if (!confirm('Excluir este departamento?')) return;
  await apiFetch(`/api/dp/departments/${id}`, { method: 'DELETE' });
  cargosLoadBody();
}

// ── HISTÓRICO SALARIAL ───────────────────────────────────────────────────────

let histEmpId = null;

async function renderHistoricoSalarial(el) {
  const empOpts = dpEmployees.map(e =>
    `<option value="${e.id}">${e.name}</option>`).join('');
  el.innerHTML = `
    <div class="flex gap-3 items-end mb-5">
      <div>
        ${labelCls('Funcionário')}
        <select id="hist-emp" class="${inputCls()}" onchange="histLoad()" style="min-width:220px">
          <option value="">Selecione...</option>${empOpts}
        </select>
      </div>
      <button onclick="histOpenModal()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i> Reajuste / Promoção
      </button>
    </div>
    <div id="hist-timeline"></div>
    <div id="hist-modal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" style="display:none!important">
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 w-full max-w-md">
        <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-4">Registrar Alteração Salarial</h3>
        <div class="mb-3">
          ${labelCls('Funcionário')}
          <select id="hist-modal-emp" class="${inputCls()}">
            <option value="">Selecione...</option>
            ${dpEmployees.filter(e => e.active).map(e => `<option value="${e.id}">${e.name}</option>`).join('')}
          </select>
        </div>
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div>${labelCls('Data de Vigência')}<input type="date" id="hist-data" class="${inputCls()}"></div>
          <div>${labelCls('Tipo')}
            <select id="hist-tipo" class="${inputCls()}">
              <option value="admissao">Admissão</option>
              <option value="reajuste" selected>Reajuste</option>
              <option value="promocao">Promoção</option>
              <option value="transferencia">Transferência</option>
              <option value="correcao">Correção</option>
            </select>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div>${labelCls('Novo Salário (R$)')}<input type="number" id="hist-sal-novo" class="${inputCls()}" step="0.01" oninput="histCalcPct()"></div>
          <div>${labelCls('Variação (%)')} <div id="hist-pct" class="mt-1 text-sm font-semibold text-slate-600 dark:text-slate-300">-</div></div>
        </div>
        <div class="mb-3">${labelCls('Novo Cargo (opcional)')}<input type="text" id="hist-cargo-novo" class="${inputCls()}"></div>
        <div class="mb-4">${labelCls('Motivo')}<input type="text" id="hist-motivo" class="${inputCls()}"></div>
        <div class="flex justify-end gap-2">
          <button onclick="histCloseModal()" class="text-xs px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700">Cancelar</button>
          <button onclick="histSave()" class="bg-violet-600 text-white text-xs font-semibold px-4 py-2 rounded-xl">Salvar</button>
        </div>
      </div>
    </div>`;
  if (histEmpId) {
    document.getElementById('hist-emp').value = histEmpId;
    await histLoad();
  }
}

async function histLoad() {
  const sel = document.getElementById('hist-emp');
  if (!sel) return;
  histEmpId = sel.value ? parseInt(sel.value) : null;
  if (!histEmpId) return;
  const timeline = document.getElementById('hist-timeline');
  try {
    const rows = await apiFetch(`/api/dp/employees/${histEmpId}/salary-history`);
    const tipoStyle = {
      admissao: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700',
      reajuste: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700',
      promocao: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700',
      transferencia: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700',
      correcao: 'bg-slate-100 dark:bg-slate-800 text-slate-600',
    };
    const cards = rows.map(r => {
      const pct = r.percentual || 0;
      const pctStr = pct > 0 ? `+${pct.toFixed(2)}%` : pct < 0 ? `${pct.toFixed(2)}%` : '0%';
      return `
        <div class="relative pl-8 pb-4">
          <div class="absolute left-2 top-2 w-3 h-3 rounded-full ${r.tipo === 'admissao' ? 'bg-emerald-500' : r.tipo === 'promocao' ? 'bg-purple-500' : 'bg-blue-500'}"></div>
          <div class="absolute left-2.5 top-5 bottom-0 w-0.5 bg-slate-200 dark:bg-slate-700"></div>
          <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs font-semibold text-slate-500">${fDate2(r.data_vigencia)}</span>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${tipoStyle[r.tipo] || tipoStyle.correcao}">${r.tipo}</span>
              <span class="ml-auto text-xs font-bold ${pct >= 0 ? 'text-emerald-600' : 'text-rose-500'}">${pctStr}</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-sm text-slate-400 line-through">${fBRL2(r.salario_anterior)}</span>
              <span class="text-slate-400">→</span>
              <span class="text-sm font-extrabold text-slate-800 dark:text-slate-100">${fBRL2(r.salario_novo)}</span>
            </div>
            ${r.motivo ? `<div class="text-xs text-slate-500 mt-1">${r.motivo}</div>` : ''}
            ${r.cargo_novo ? `<div class="text-xs text-purple-500 mt-1">Cargo: ${r.cargo_novo}</div>` : ''}
          </div>
        </div>`;
    }).join('');
    timeline.innerHTML = cards || '<div class="text-center text-slate-400 text-xs py-8">Nenhum histórico registrado.</div>';
  } catch (e) { console.error(e); }
}

function histOpenModal() {
  document.getElementById('hist-data').value = new Date().toISOString().slice(0,10);
  document.getElementById('hist-sal-novo').value = '';
  document.getElementById('hist-tipo').value = 'reajuste';
  document.getElementById('hist-cargo-novo').value = '';
  document.getElementById('hist-motivo').value = '';
  document.getElementById('hist-pct').textContent = '-';
  if (histEmpId) document.getElementById('hist-modal-emp').value = histEmpId;
  document.getElementById('hist-modal').style.display = 'flex';
}

function histCloseModal() { document.getElementById('hist-modal').style.display = 'none'; }

function histCalcPct() {
  const empId = parseInt(document.getElementById('hist-modal-emp').value);
  const emp = dpEmployees.find(e => e.id === empId);
  if (!emp) return;
  const novo = parseFloat(document.getElementById('hist-sal-novo').value || 0);
  const ant = parseFloat(emp.salary || 0);
  const pct = ant > 0 ? ((novo - ant) / ant * 100).toFixed(2) : 0;
  const el = document.getElementById('hist-pct');
  el.textContent = `${pct >= 0 ? '+' : ''}${pct}%`;
  el.className = `mt-1 text-sm font-semibold ${pct >= 0 ? 'text-emerald-600' : 'text-rose-500'}`;
}

async function histSave() {
  const empId = document.getElementById('hist-modal-emp').value;
  if (!empId) { alert('Selecione o funcionário.'); return; }
  const body = {
    data_vigencia: document.getElementById('hist-data').value,
    salario_novo: parseFloat(document.getElementById('hist-sal-novo').value),
    tipo: document.getElementById('hist-tipo').value,
    cargo_novo: document.getElementById('hist-cargo-novo').value,
    motivo: document.getElementById('hist-motivo').value,
  };
  try {
    await apiFetch(`/api/dp/employees/${empId}/salary-history`, { method: 'POST', body: JSON.stringify(body) });
    histCloseModal();
    histEmpId = parseInt(empId);
    document.getElementById('hist-emp').value = histEmpId;
    histLoad();
    const idx = dpEmployees.findIndex(e => e.id === histEmpId);
    if (idx >= 0) dpEmployees[idx].salary = body.salario_novo;
    if (typeof showToast === 'function') showToast('Histórico registrado.', 'success');
  } catch (e) { alert('Erro: ' + e.message); }
}

// ── OBRIGAÇÕES ACESSÓRIAS ────────────────────────────────────────────────────

function renderObrigacoes(el) {
  const anoAtual = new Date().getFullYear();
  const mesAtual = new Date().toISOString().slice(0, 7);
  el.innerHTML = `
    <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-5">Obrigações Acessórias</h2>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
      ${obrigCard('RAIS', 'Relação Anual de Informações Sociais', 'number', anoAtual, 'Gerar RAIS', 'obrigExec("rais", document.getElementById("v-rais").value)', 'v-rais', 'emerald')}
      ${obrigCard('CAGED', 'Cadastro Geral de Empregados e Desempregados', 'month', mesAtual, 'Gerar CAGED', 'obrigExec("caged", document.getElementById("v-caged").value)', 'v-caged', 'blue')}
      ${obrigCard('DIRF', 'Declaração do Imposto de Renda Retido na Fonte', 'number', anoAtual, 'Gerar DIRF', 'obrigExec("dirf", document.getElementById("v-dirf").value)', 'v-dirf', 'purple')}
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      ${obrigCard('GPS/INSS', 'Guia da Previdência Social', 'month', mesAtual, 'Calcular GPS', 'obrigExec("gps", document.getElementById("v-gps").value)', 'v-gps', 'amber')}
      ${obrigCard('DARF/IRRF', 'Documento de Arrecadação de Receitas Federais', 'month', mesAtual, 'Calcular DARF', 'obrigExec("darf", document.getElementById("v-darf").value)', 'v-darf', 'rose')}
    </div>
    <div id="obrig-result"></div>`;
}

function obrigCard(title, subtitle, inputType, defaultVal, btnLabel, onClick, inputId, color) {
  const colorMap = {
    emerald: 'border-emerald-200 dark:border-emerald-800',
    blue: 'border-blue-200 dark:border-blue-800',
    purple: 'border-purple-200 dark:border-purple-800',
    amber: 'border-amber-200 dark:border-amber-800',
    rose: 'border-rose-200 dark:border-rose-800',
  };
  const btnColor = {
    emerald: 'bg-emerald-600 hover:bg-emerald-700',
    blue: 'bg-blue-600 hover:bg-blue-700',
    purple: 'bg-purple-600 hover:bg-purple-700',
    amber: 'bg-amber-600 hover:bg-amber-700',
    rose: 'bg-rose-600 hover:bg-rose-700',
  };
  return `
    <div class="bg-white dark:bg-slate-900 border ${colorMap[color] || ''} rounded-2xl p-4 shadow-xs">
      <div class="font-bold text-slate-800 dark:text-slate-100 mb-0.5">${title}</div>
      <div class="text-xs text-slate-500 mb-3">${subtitle}</div>
      <div class="flex gap-2">
        <input type="${inputType}" id="${inputId}" value="${defaultVal}" class="${inputCls()} flex-1" ${inputType === 'number' ? 'min="2000" max="2099" step="1"' : ''}>
        <button onclick="${onClick}" class="${btnColor[color] || 'bg-violet-600 hover:bg-violet-700'} text-white text-xs font-semibold px-3 py-2 rounded-xl whitespace-nowrap">${btnLabel}</button>
      </div>
    </div>`;
}

async function obrigExec(tipo, valor) {
  const res = document.getElementById('obrig-result');
  if (!res) return;
  res.innerHTML = '<div class="text-xs text-slate-400 py-4 text-center">Carregando...</div>';
  try {
    const url = tipo === 'rais' ? `/api/dp/rais/${valor}`
      : tipo === 'caged' ? `/api/dp/caged/${valor}`
      : tipo === 'dirf' ? `/api/dp/dirf/${valor}`
      : tipo === 'gps' ? `/api/dp/gps/${valor}`
      : `/api/dp/darf/${valor}`;
    const d = await apiFetch(url);
    let html = '';
    if (tipo === 'rais') {
      const trs = (d.trabalhadores || []).map(t => `
        <tr class="border-b border-slate-100 dark:border-slate-800">
          <td class="px-3 py-2 text-xs">${t.nome}</td>
          <td class="px-3 py-2 text-xs font-mono">${t.cpf}</td>
          <td class="px-3 py-2 text-xs">${fDate2(t.data_admissao)}</td>
          <td class="px-3 py-2 text-xs">${t.cargo}</td>
          <td class="px-3 py-2 text-xs font-semibold text-emerald-600">${fBRL2(t.total_remuneracao_ano)}</td>
          <td class="px-3 py-2 text-xs">${t.meses_trabalhados}</td>
        </tr>`).join('');
      html = `<h3 class="font-bold mb-3">RAIS ${d.ano} — ${d.totais?.total_trabalhadores} trabalhadores | Total: ${fBRL2(d.totais?.total_remuneracao)}</h3>
        ${card2(`<div class="overflow-x-auto"><table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-3 py-2 text-left">Nome</th><th class="px-3 py-2">CPF</th><th class="px-3 py-2">Admissão</th>
            <th class="px-3 py-2">Cargo</th><th class="px-3 py-2">Total Rem.</th><th class="px-3 py-2">Meses</th>
          </tr></thead><tbody>${trs}</tbody></table></div>`)}`;
    } else if (tipo === 'caged') {
      const trAdm = (d.admissoes || []).map(t => `<tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-3 py-2 text-xs">${t.nome}</td><td class="px-3 py-2 text-xs font-mono">${t.cpf}</td>
        <td class="px-3 py-2 text-xs">${fDate2(t.data_admissao)}</td><td class="px-3 py-2 text-xs">${t.cargo}</td>
        <td class="px-3 py-2 text-xs font-semibold text-emerald-600">${fBRL2(t.salario)}</td></tr>`).join('');
      const trDem = (d.demissoes || []).map(t => `<tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-3 py-2 text-xs">${t.nome}</td><td class="px-3 py-2 text-xs font-mono">${t.cpf}</td>
        <td class="px-3 py-2 text-xs">${fDate2(t.data_demissao)}</td><td class="px-3 py-2 text-xs">${t.cargo}</td>
        <td class="px-3 py-2 text-xs font-semibold text-rose-500">${fBRL2(t.salario)}</td></tr>`).join('');
      html = `<h3 class="font-bold mb-3">CAGED ${d.competencia} — Saldo: ${d.saldo >= 0 ? '+' : ''}${d.saldo}</h3>
        <div class="mb-4"><div class="font-semibold text-sm text-emerald-600 mb-2">Admissões (${(d.admissoes||[]).length})</div>
        ${card2(`<table class="w-full text-sm"><thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800"><th class="px-3 py-2 text-left">Nome</th><th>CPF</th><th>Data</th><th>Cargo</th><th>Salário</th></tr></thead><tbody>${trAdm || '<tr><td colspan="5" class="px-3 py-4 text-center text-slate-400 text-xs">Nenhuma admissão.</td></tr>'}</tbody></table>`)}</div>
        <div><div class="font-semibold text-sm text-rose-500 mb-2">Demissões (${(d.demissoes||[]).length})</div>
        ${card2(`<table class="w-full text-sm"><thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800"><th class="px-3 py-2 text-left">Nome</th><th>CPF</th><th>Data</th><th>Cargo</th><th>Salário</th></tr></thead><tbody>${trDem || '<tr><td colspan="5" class="px-3 py-4 text-center text-slate-400 text-xs">Nenhuma demissão.</td></tr>'}</tbody></table>`)}</div>`;
    } else if (tipo === 'dirf') {
      const trs = (d.beneficiarios || []).map(b => `<tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-3 py-2 text-xs">${b.nome}</td><td class="px-3 py-2 text-xs font-mono">${b.cpf}</td>
        <td class="px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200">${fBRL2(b.rendimentos_tributaveis)}</td>
        <td class="px-3 py-2 text-xs text-rose-500">${fBRL2(b.irrf_retido)}</td>
        <td class="px-3 py-2 text-xs text-amber-500">${fBRL2(b.deducoes_inss)}</td>
        <td class="px-3 py-2 text-xs">${b.dependentes}</td></tr>`).join('');
      html = `<h3 class="font-bold mb-3">DIRF ${d.ano}</h3>
        ${card2(`<div class="overflow-x-auto"><table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-3 py-2 text-left">Nome</th><th>CPF</th><th>Rendimentos</th><th>IRRF</th><th>INSS</th><th>Dep.</th>
          </tr></thead><tbody>${trs || '<tr><td colspan="6" class="px-3 py-4 text-center text-slate-400 text-xs">Sem dados.</td></tr>'}</tbody></table></div>`)}`;
    } else if (tipo === 'gps') {
      html = `<div class="bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-800 rounded-2xl p-6 max-w-md">
        <div class="font-bold text-lg mb-4">GPS/INSS — ${d.competencia}</div>
        ${[
          ['Total da Folha', fBRL2(d.total_folha), 'text-slate-700 dark:text-slate-200'],
          ['INSS Funcionários', fBRL2(d.inss_funcionarios), 'text-amber-600'],
          ['INSS Patronal (20%)', fBRL2(d.inss_patronal_20pct), 'text-amber-600'],
          ['RAT Ajustado (3%)', fBRL2(d.rat_ajustado), 'text-amber-600'],
          ['Terceiros (5,8%)', fBRL2(d.terceiros), 'text-amber-600'],
        ].map(([l, v, c]) => `<div class="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-800">
          <span class="text-sm text-slate-600 dark:text-slate-400">${l}</span>
          <span class="text-sm font-semibold ${c}">${v}</span></div>`).join('')}
        <div class="flex justify-between items-center mt-3">
          <span class="font-bold text-slate-800 dark:text-slate-100">TOTAL GPS</span>
          <span class="text-xl font-extrabold text-emerald-600">${fBRL2(d.total_gps)}</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Código: ${d.codigo_pagamento} | Vencimento: ${fDate2(d.vencimento)}</div>
      </div>`;
    } else {
      html = `<div class="bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-800 rounded-2xl p-6 max-w-md">
        <div class="font-bold text-lg mb-4">DARF/IRRF — ${d.competencia}</div>
        <div class="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-800">
          <span class="text-sm text-slate-600 dark:text-slate-400">Total IRRF Retido</span>
          <span class="text-sm font-semibold text-rose-500">${fBRL2(d.total_irrf)}</span>
        </div>
        <div class="flex justify-between items-center mt-3">
          <span class="font-bold text-slate-800 dark:text-slate-100">TOTAL DARF</span>
          <span class="text-xl font-extrabold text-emerald-600">${fBRL2(d.total_irrf)}</span>
        </div>
        <div class="text-xs text-slate-500 mt-2">Código: ${d.codigo_receita} | Período: ${d.periodo_apuracao} | Vencimento: ${fDate2(d.vencimento)}</div>
      </div>`;
    }
    res.innerHTML = `
      <div class="mb-3 flex justify-end">
        <button onclick="obrigExportJSON()" class="text-xs px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">
          Exportar JSON
        </button>
      </div>
      ${html}`;
    window._lastObrigData = d;
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    res.innerHTML = `<div class="text-rose-500 text-sm py-4">${e.message}</div>`;
  }
}

function obrigExportJSON() {
  if (!window._lastObrigData) return;
  const blob = new Blob([JSON.stringify(window._lastObrigData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'cortex_obrigacao.json';
  a.click();
  URL.revokeObjectURL(url);
}
