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
