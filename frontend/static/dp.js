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
    { id: 'tabelas_fiscais',   icon: 'percent',      label: 'Tabelas Fiscais' },
    { id: 'rubricas',          icon: 'list-checks',  label: 'Rubricas' },
    { id: 'esocial_periodico', icon: 'send',         label: 'eSocial Periódico' },
    { id: 'sefip',             icon: 'building-2',   label: 'SEFIP/GFIP' },
    { id: 'efd_reinf',         icon: 'file-code-2',  label: 'EFD-Reinf' },
    { id: 'beneficios',        icon: 'heart',         label: 'Benefícios' },
    { id: 'adiantamentos',     icon: 'banknote',      label: 'Adiantamentos' },
    { id: 'pensao',            icon: 'scale',         label: 'Pensão Alim.' },
    { id: 'autonomos',         icon: 'user-check',    label: 'Autônomos/RPA' },
    { id: 'prolabore',         icon: 'briefcase-business', label: 'Pró-labore' },
    { id: 'aso',               icon: 'stethoscope',   label: 'Exames (ASO)' },
    { id: 'ppp',               icon: 'shield-alert',  label: 'PPP / LTCAT' },
    { id: 'contabil_dp',       icon: 'book-open',     label: 'Integração Contábil' },
    { id: 'estagiarios',       icon: 'graduation-cap',label: 'Estágio & Aprendiz' },
    { id: 'fgts',              icon: 'piggy-bank',    label: 'Extrato FGTS' },
    { id: 'employee_portal',   icon: 'circle-user',   label: 'Portal' },
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
    case 'tabelas_fiscais':    await renderTabelasFiscais(body); break;
    case 'rubricas':           await renderRubricas(body); break;
    case 'esocial_periodico':  await renderEsocialPeriodico(body); break;
    case 'sefip':              await renderSefip(body); break;
    case 'efd_reinf':          await renderEfdReinf(body); break;
    case 'beneficios':         await renderBeneficios(body); break;
    case 'adiantamentos':      await renderAdiantamentos(body); break;
    case 'pensao':             await renderPensao(body); break;
    case 'autonomos':          await renderAutonomos(body); break;
    case 'prolabore':          await renderProlabore(body); break;
    case 'aso':                await renderAso(body); break;
    case 'ppp':                await renderPpp(body); break;
    case 'contabil_dp':        await renderContabilDp(body); break;
    case 'estagiarios':        await renderEstagiarios(body); break;
    case 'fgts':               await renderFgts(body); break;
    case 'employee_portal':    await renderPortalFuncionario(body); break;
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

// ── TABELAS FISCAIS ──────────────────────────────────────────────────────────
async function renderTabelasFiscais(el) {
  const today = new Date();
  const ano = today.getFullYear();
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2 style="font-family:var(--font-display);font-size:1.4rem;font-weight:700;color:var(--text);margin:0">Tabelas Fiscais</h2>
        <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">INSS, IRRF, FGTS e Salário Mínimo vigentes</p>
      </div>
      <div class="d-flex gap-2">
        <input type="number" id="tfAno" class="form-control" style="width:100px" value="${ano}">
        <button class="btn btn-secondary" onclick="window.tfLoadTables()">Buscar</button>
        <button class="btn btn-primary" onclick="window.tfImportDefault()">Importar ${ano}</button>
      </div>
    </div>
    <div id="tfResult"></div>`;

  window.tfLoadTables = async () => {
    const a = document.getElementById('tfAno').value || ano;
    const res = document.getElementById('tfResult');
    try {
      const rows = await apiFetch(`/api/dp/tax-tables?ano=${a}`);
      if (!rows.length) { res.innerHTML = '<p class="text-muted text-center py-6">Nenhuma tabela encontrada. Clique em "Importar" para carregar as tabelas padrão.</p>'; return; }
      const tipoLabel = { INSS:'INSS 2025', IRRF:'IRRF 2025', FGTS:'FGTS', SALARIO_MINIMO:'Salário Mínimo' };
      res.innerHTML = rows.map(t => `
        <div class="card mb-4">
          <div class="card-header d-flex justify-content-between align-items-center">
            <strong>${tipoLabel[t.tipo] || t.tipo} — ${t.ano}</strong>
          </div>
          <div class="table-responsive">
            <table class="table table-sm mb-0">
              <thead><tr>
                ${t.tipo === 'SALARIO_MINIMO' ? '<th>Valor</th>' : '<th>Faixa De</th><th>Faixa Até</th><th>Alíquota (%)</th><th>Dedução (R$)</th>'}
              </tr></thead>
              <tbody>
                ${(t.brackets||[]).map(b => t.tipo === 'SALARIO_MINIMO'
                  ? `<tr><td>R$ ${Number(b.aliquota).toFixed(2)}</td></tr>`
                  : `<tr><td>R$ ${Number(b.faixa_de).toFixed(2)}</td><td>${b.faixa_ate ? 'R$ '+Number(b.faixa_ate).toFixed(2) : 'Acima'}</td><td>${Number(b.aliquota).toFixed(2)}%</td><td>R$ ${Number(b.deducao||0).toFixed(2)}</td></tr>`
                ).join('')}
              </tbody>
            </table>
          </div>
        </div>`).join('');
    } catch(e) { res.innerHTML = `<div class="alert alert-danger">Erro: ${e.message}</div>`; }
  };

  window.tfImportDefault = async () => {
    const a = document.getElementById('tfAno').value || ano;
    try {
      await apiFetch(`/api/dp/tax-tables/seed-default?ano=${parseInt(a)}`, { method:'POST' });
      showToast(`Tabelas ${a} importadas.`, 'success');
      window.tfLoadTables();
    } catch(e) { showToast('Erro: ' + e.message, 'error'); }
  };

  await window.tfLoadTables();
}

// ── RUBRICAS ─────────────────────────────────────────────────────────────────
async function renderRubricas(el) {
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2 style="font-family:var(--font-display);font-size:1.4rem;font-weight:700;color:var(--text);margin:0">Rubricas de Folha</h2>
        <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">Tabela de rubricas S-1010 do eSocial</p>
      </div>
      <div class="d-flex gap-2">
        <button class="btn btn-secondary" onclick="rubricSeedDefault()">Carregar Padrão</button>
        <button class="btn btn-secondary" onclick="rubricDownloadS1010()">Gerar S-1010 XML</button>
        <button class="btn btn-primary" onclick="rubricOpenModal()">+ Nova Rubrica</button>
      </div>
    </div>
    <div id="rubricKpis" class="row g-3 mb-4"></div>
    <div class="table-responsive">
      <table class="table">
        <thead><tr><th>Código</th><th>Nome</th><th>Tipo</th><th>INSS</th><th>IRRF</th><th>FGTS</th><th>Nat.eSocial</th><th>Ativo</th><th>Ações</th></tr></thead>
        <tbody id="rubricTableBody"><tr><td colspan="9" class="text-center text-muted">Carregando...</td></tr></tbody>
      </table>
    </div>
    <div id="rubricModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3 id="rubricModalTitle">Nova Rubrica</h3>
        <input type="hidden" id="rubricEditId">
        <div class="form-row">
          <div class="form-group"><label>Código</label><input type="text" id="rubricCodigo" class="form-control" placeholder="0001"></div>
          <div class="form-group"><label>Nome</label><input type="text" id="rubricNome" class="form-control" placeholder="Salário Base"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Tipo</label>
            <select id="rubricTipo" class="form-control">
              <option value="provento">Provento</option><option value="desconto">Desconto</option><option value="informativo">Informativo</option>
            </select></div>
          <div class="form-group"><label>Nat. eSocial</label><input type="text" id="rubricNat" class="form-control" placeholder="1000"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label><input type="checkbox" id="rubricINSS"> Incide INSS</label></div>
          <div class="form-group"><label><input type="checkbox" id="rubricIRRF"> Incide IRRF</label></div>
          <div class="form-group"><label><input type="checkbox" id="rubricFGTS"> Incide FGTS</label></div>
        </div>
        <div id="rubricModalError" class="alert alert-danger" style="display:none"></div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="document.getElementById('rubricModal').style.display='none'">Cancelar</button>
          <button class="btn btn-primary" onclick="rubricSave()">Salvar</button>
        </div>
      </div>
    </div>`;

  await rubricLoadTable();
}

async function rubricLoadTable() {
  const tbody = document.getElementById('rubricTableBody');
  if (!tbody) return;
  try {
    const rows = await apiFetch('/api/dp/rubrics');
    const kpis = document.getElementById('rubricKpis');
    if (kpis) {
      const prov = rows.filter(r=>r.tipo==='provento').length;
      const desc = rows.filter(r=>r.tipo==='desconto').length;
      const info = rows.filter(r=>r.tipo==='informativo').length;
      kpis.innerHTML = [
        ['Proventos', prov, 'text-success'],['Descontos', desc, 'text-danger'],
        ['Informativos', info, 'text-info'],['Total', rows.length, 'text-primary']
      ].map(([l,v,c])=>`<div class="col-md-3"><div class="card text-center p-3"><div class="fs-4 fw-bold ${c}">${v}</div><div class="text-muted small">${l}</div></div></div>`).join('');
    }
    const badge = {provento:'badge-success', desconto:'badge-danger', informativo:'badge-info'};
    tbody.innerHTML = rows.length ? rows.map(r=>`<tr>
      <td><code>${r.codigo}</code></td><td>${r.nome}</td>
      <td><span class="badge ${badge[r.tipo]||'badge-secondary'}">${r.tipo}</span></td>
      <td>${r.incide_inss?'✓':'—'}</td><td>${r.incide_irrf?'✓':'—'}</td><td>${r.incide_fgts?'✓':'—'}</td>
      <td><code>${r.esocial_nat_rubrica||''}</code></td>
      <td>${r.ativo?'<span class="badge badge-success">Sim</span>':'<span class="badge badge-secondary">Não</span>'}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="rubricEdit(${JSON.stringify(r).replace(/"/g,'&quot;')})">Editar</button>
        <button class="btn btn-sm btn-danger" onclick="rubricDelete(${r.id},'${r.nome.replace(/'/g,"\\'")}')">Excluir</button>
      </td></tr>`).join('')
      : '<tr><td colspan="9" class="text-center text-muted">Nenhuma rubrica. Clique em "Carregar Padrão".</td></tr>';
  } catch(e) { if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="text-danger">${e.message}</td></tr>`; }
}

function rubricOpenModal() {
  document.getElementById('rubricModalTitle').textContent = 'Nova Rubrica';
  document.getElementById('rubricEditId').value = '';
  ['rubricCodigo','rubricNome','rubricNat'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('rubricTipo').value = 'provento';
  ['rubricINSS','rubricIRRF','rubricFGTS'].forEach(id => document.getElementById(id).checked = true);
  document.getElementById('rubricModalError').style.display = 'none';
  document.getElementById('rubricModal').style.display = 'flex';
}

function rubricEdit(r) {
  document.getElementById('rubricModalTitle').textContent = 'Editar Rubrica';
  document.getElementById('rubricEditId').value = r.id;
  document.getElementById('rubricCodigo').value = r.codigo || '';
  document.getElementById('rubricNome').value = r.nome || '';
  document.getElementById('rubricTipo').value = r.tipo || 'provento';
  document.getElementById('rubricNat').value = r.esocial_nat_rubrica || '';
  document.getElementById('rubricINSS').checked = !!r.incide_inss;
  document.getElementById('rubricIRRF').checked = !!r.incide_irrf;
  document.getElementById('rubricFGTS').checked = !!r.incide_fgts;
  document.getElementById('rubricModalError').style.display = 'none';
  document.getElementById('rubricModal').style.display = 'flex';
}

async function rubricSave() {
  const id = document.getElementById('rubricEditId').value;
  const body = {
    codigo: document.getElementById('rubricCodigo').value.trim(),
    nome: document.getElementById('rubricNome').value.trim(),
    tipo: document.getElementById('rubricTipo').value,
    esocial_nat_rubrica: document.getElementById('rubricNat').value.trim(),
    incide_inss: document.getElementById('rubricINSS').checked ? 1 : 0,
    incide_irrf: document.getElementById('rubricIRRF').checked ? 1 : 0,
    incide_fgts: document.getElementById('rubricFGTS').checked ? 1 : 0,
  };
  const errBox = document.getElementById('rubricModalError');
  if (!body.codigo || !body.nome) { errBox.textContent = 'Código e nome são obrigatórios.'; errBox.style.display = ''; return; }
  try {
    if (id) await apiFetch(`/api/dp/rubrics/${id}`, { method:'PUT', body: JSON.stringify(body) });
    else await apiFetch('/api/dp/rubrics', { method:'POST', body: JSON.stringify(body) });
    document.getElementById('rubricModal').style.display = 'none';
    showToast(id ? 'Rubrica atualizada.' : 'Rubrica criada.', 'success');
    await rubricLoadTable();
  } catch(e) { errBox.textContent = 'Erro: ' + e.message; errBox.style.display = ''; }
}

async function rubricDelete(id, nome) {
  if (!confirm(`Excluir rubrica "${nome}"?`)) return;
  try {
    await apiFetch(`/api/dp/rubrics/${id}`, { method:'DELETE' });
    showToast('Rubrica excluída.', 'success');
    await rubricLoadTable();
  } catch(e) { showToast('Erro: ' + e.message, 'error'); }
}

async function rubricSeedDefault() {
  try {
    const r = await apiFetch('/api/dp/rubrics/seed-default', { method:'POST' });
    showToast(r.created ? '20 rubricas padrão carregadas.' : r.message, 'success');
    await rubricLoadTable();
  } catch(e) { showToast('Erro: ' + e.message, 'error'); }
}

function rubricDownloadS1010() {
  const ano = new Date().getFullYear();
  window.open(`/api/dp/esocial/s1010?ano=${ano}`, '_blank');
}

// ── ESOCIAL PERIÓDICO ─────────────────────────────────────────────────────────
async function renderEsocialPeriodico(el) {
  const today = new Date();
  const comp = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`;
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2 style="font-family:var(--font-display);font-size:1.4rem;font-weight:700;color:var(--text);margin:0">eSocial Periódico</h2>
        <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">S-1200 (Remunerações) e S-1299 (Fechamento)</p>
      </div>
      <div class="d-flex gap-2 align-items-center">
        <input type="month" id="espComp" class="form-control" style="width:150px" value="${comp}">
        <button class="btn btn-secondary" onclick="window.espLoad()">Buscar</button>
      </div>
    </div>
    <div id="espKpis" class="row g-3 mb-4"></div>
    <div class="table-responsive mb-4">
      <table class="table">
        <thead><tr><th>Funcionário</th><th>CPF</th><th>Bruto</th><th>INSS</th><th>IRRF</th><th>Líquido</th><th>S-1200</th></tr></thead>
        <tbody id="espTableBody"><tr><td colspan="7" class="text-center text-muted">Selecione uma competência.</td></tr></tbody>
      </table>
    </div>
    <div class="d-flex gap-2 flex-wrap">
      <button class="btn btn-primary" onclick="window.espDownloadAll()">Baixar S-1200 Todos (XML)</button>
      <button class="btn btn-secondary" onclick="window.espDownloadS1299()">Baixar S-1299 Fechamento (XML)</button>
      <button class="btn btn-secondary" onclick="window.espMarkSent()">Marcar como Transmitida</button>
    </div>`;

  window.espLoad = async () => {
    const c = document.getElementById('espComp').value;
    const tbody = document.getElementById('espTableBody');
    const kpis = document.getElementById('espKpis');
    try {
      const items = await apiFetch(`/api/dp/payroll/items?competencia=${c}`);
      const status = await apiFetch(`/api/dp/esocial/periodic/status?competencia=${c}`);
      const sentEvts = new Set(status.map(s=>s.evento));
      if (kpis) {
        const totBruto = items.reduce((s,i)=>s+Number(i.gross_salary||0),0);
        const totLiq = items.reduce((s,i)=>s+Number(i.net_salary||0),0);
        kpis.innerHTML = [
          ['Funcionários', items.length, 'text-primary'],
          ['Total Bruto', 'R$ '+totBruto.toFixed(2), 'text-success'],
          ['Total Líquido', 'R$ '+totLiq.toFixed(2), 'text-info'],
          ['Status S-1200', sentEvts.has('S-1200')?'Transmitido':'Pendente', sentEvts.has('S-1200')?'text-success':'text-warning'],
        ].map(([l,v,c])=>`<div class="col-md-3"><div class="card text-center p-3"><div class="fs-5 fw-bold ${c}">${v}</div><div class="text-muted small">${l}</div></div></div>`).join('');
      }
      tbody.innerHTML = items.length ? items.map(it=>`<tr>
        <td>${it.employee_name||it.name||'—'}</td>
        <td style="font-family:var(--font-mono);font-size:.8rem">${it.cpf||'—'}</td>
        <td>R$ ${Number(it.gross_salary||0).toFixed(2)}</td>
        <td>R$ ${Number(it.inss||0).toFixed(2)}</td>
        <td>R$ ${Number(it.irrf||0).toFixed(2)}</td>
        <td>R$ ${Number(it.net_salary||0).toFixed(2)}</td>
        <td><a href="/api/dp/esocial/s1200/${c}/${it.employee_id}" target="_blank" class="btn btn-sm btn-secondary">XML</a></td>
      </tr>`).join('')
        : '<tr><td colspan="7" class="text-center text-muted">Nenhum item de folha nesta competência.</td></tr>';
    } catch(e) { tbody.innerHTML = `<tr><td colspan="7" class="text-danger">${e.message}</td></tr>`; }
  };

  window.espDownloadAll = () => {
    const c = document.getElementById('espComp').value;
    window.open(`/api/dp/esocial/s1200/${c}/todos`, '_blank');
  };

  window.espDownloadS1299 = () => {
    const c = document.getElementById('espComp').value;
    window.open(`/api/dp/esocial/s1299/${c}`, '_blank');
  };

  window.espMarkSent = async () => {
    const c = document.getElementById('espComp').value;
    try {
      await apiFetch('/api/dp/esocial/periodic/mark-sent', { method:'POST', body: JSON.stringify({ competencia: c, evento:'S-1200' }) });
      showToast('Competência marcada como transmitida.', 'success');
      window.espLoad();
    } catch(e) { showToast('Erro: ' + e.message, 'error'); }
  };
}

// ── SEFIP/GFIP ───────────────────────────────────────────────────────────────
async function renderSefip(el) {
  const today = new Date();
  const comp = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`;
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2 style="font-family:var(--font-display);font-size:1.4rem;font-weight:700;color:var(--text);margin:0">SEFIP / GFIP</h2>
        <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">Geração do arquivo GRF e resumo da GPS</p>
      </div>
      <div class="d-flex gap-2 align-items-center">
        <input type="month" id="sefipComp" class="form-control" style="width:150px" value="${comp}">
        <button class="btn btn-primary" onclick="window.sefipCalc()">Calcular SEFIP</button>
      </div>
    </div>
    <div id="sefipResult"></div>`;

  window.sefipCalc = async () => {
    const c = document.getElementById('sefipComp').value;
    const res = document.getElementById('sefipResult');
    res.innerHTML = '<p class="text-muted text-center py-4">Calculando...</p>';
    try {
      const d = await apiFetch(`/api/dp/sefip/${c}`);
      const rows = [
        ['Total Trabalhadores', d.total_trabalhadores],
        ['Total Remuneração', 'R$ '+Number(d.total_remuneracao).toFixed(2)],
        ['FGTS a Recolher', 'R$ '+Number(d.total_fgts).toFixed(2)],
        ['INSS Empregado', 'R$ '+Number(d.total_inss_emp).toFixed(2)],
        ['INSS Patronal (20%)', 'R$ '+Number(d.total_inss_patronal).toFixed(2)],
        ['RAT (3%)', 'R$ '+Number(d.total_rat).toFixed(2)],
        ['Terceiros (5,8%)', 'R$ '+Number(d.total_terceiros).toFixed(2)],
      ];
      res.innerHTML = `
        <div class="row g-3 mb-4">
          <div class="col-md-5">
            <div class="card p-3">
              <h5 class="mb-3">GPS — Guia da Previdência Social</h5>
              ${rows.map(([l,v])=>`<div class="d-flex justify-content-between border-bottom py-1"><span class="text-muted">${l}</span><strong>${v}</strong></div>`).join('')}
              <div class="d-flex justify-content-between pt-2 mt-1"><strong>Total GPS</strong><strong class="text-primary fs-5">R$ ${Number(d.total_gps).toFixed(2)}</strong></div>
              <div class="text-muted small mt-2">FPAS: ${d.fpas} | Cód. Terceiros: ${d.cod_terceiros}</div>
            </div>
          </div>
          <div class="col-md-7">
            <div class="table-responsive">
              <table class="table table-sm">
                <thead><tr><th>Funcionário</th><th>CPF</th><th>Remuneração</th><th>FGTS</th></tr></thead>
                <tbody>${(d.funcionarios||[]).map(f=>`<tr>
                  <td>${f.name||f.employee_name||'—'}</td>
                  <td style="font-size:.8rem">${f.cpf||'—'}</td>
                  <td>R$ ${Number(f.gross_salary||0).toFixed(2)}</td>
                  <td>R$ ${Number(f.fgts||0).toFixed(2)}</td>
                </tr>`).join('')||'<tr><td colspan="4" class="text-muted text-center">Sem folha nesta competência.</td></tr>'}</tbody>
              </table>
            </div>
          </div>
        </div>
        <button class="btn btn-primary" onclick="window.open('/api/dp/sefip/${c}/arquivo','_blank')">Baixar Arquivo SEFIP (GRF)</button>`;
    } catch(e) { res.innerHTML = `<div class="alert alert-danger">Erro: ${e.message}</div>`; }
  };
}

// ── EFD-REINF ─────────────────────────────────────────────────────────────────
async function renderEfdReinf(el) {
  const today = new Date();
  const comp = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`;
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2 style="font-family:var(--font-display);font-size:1.4rem;font-weight:700;color:var(--text);margin:0">EFD-Reinf</h2>
        <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">Eventos de retenção: R-1000, R-2010, R-4010, R-4020, R-4099</p>
      </div>
      <button class="btn btn-primary" onclick="reinfOpenModal()">+ Tomador</button>
    </div>

    <h5 class="mb-3">Tomadores de Serviço</h5>
    <div class="d-flex gap-2 align-items-center mb-3">
      <input type="month" id="reinfComp" class="form-control" style="width:150px" value="${comp}">
      <button class="btn btn-secondary" onclick="window.reinfLoadTomadores()">Filtrar</button>
    </div>
    <div class="table-responsive mb-4">
      <table class="table">
        <thead><tr><th>Razão Social</th><th>CNPJ/CPF</th><th>Tipo Serviço</th><th>Valor Bruto</th><th>IRRF</th><th>Competência</th><th>Ações</th></tr></thead>
        <tbody id="reinfTableBody"><tr><td colspan="7" class="text-center text-muted">Carregando...</td></tr></tbody>
      </table>
    </div>

    <h5 class="mb-3">Eventos EFD-Reinf</h5>
    <div class="row g-3" id="reinfEventos"></div>

    <div id="reinfModal" class="modal-overlay" style="display:none">
      <div class="modal-box">
        <h3 id="reinfModalTitle">Novo Tomador</h3>
        <input type="hidden" id="reinfEditId">
        <div class="form-row">
          <div class="form-group"><label>Razão Social</label><input type="text" id="reinfRazao" class="form-control"></div>
          <div class="form-group"><label>CNPJ/CPF</label><input type="text" id="reinfNrInsc" class="form-control" placeholder="00.000.000/0000-00"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Tipo Inscrição</label>
            <select id="reinfTipoInsc" class="form-control"><option value="cnpj">CNPJ</option><option value="cpf">CPF</option></select></div>
          <div class="form-group"><label>Tipo Serviço</label><input type="text" id="reinfTipoServ" class="form-control" placeholder="0001" value="0001"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Competência</label><input type="month" id="reinfCompModal" class="form-control" value="${comp}"></div>
          <div class="form-group"><label>Valor Bruto</label><input type="number" id="reinfVlrBruto" class="form-control" step="0.01" placeholder="0.00"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>Base Cálculo Ret.</label><input type="number" id="reinfVlrBc" class="form-control" step="0.01" placeholder="0.00"></div>
          <div class="form-group"><label>IRRF</label><input type="number" id="reinfVlrIrrf" class="form-control" step="0.01" placeholder="0.00"></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label>CSLL</label><input type="number" id="reinfVlrCsll" class="form-control" step="0.01" placeholder="0.00"></div>
          <div class="form-group"><label>PIS</label><input type="number" id="reinfVlrPis" class="form-control" step="0.01" placeholder="0.00"></div>
          <div class="form-group"><label>COFINS</label><input type="number" id="reinfVlrCofins" class="form-control" step="0.01" placeholder="0.00"></div>
        </div>
        <div id="reinfModalError" class="alert alert-danger" style="display:none"></div>
        <div class="d-flex gap-2 justify-content-end mt-3">
          <button class="btn btn-secondary" onclick="document.getElementById('reinfModal').style.display='none'">Cancelar</button>
          <button class="btn btn-primary" onclick="window.reinfSaveTomador()">Salvar</button>
        </div>
      </div>
    </div>`;

  window.reinfLoadTomadores = async () => {
    const c = document.getElementById('reinfComp').value;
    const tbody = document.getElementById('reinfTableBody');
    const eventosEl = document.getElementById('reinfEventos');
    try {
      const rows = await apiFetch(`/api/dp/reinf/tomadores?competencia=${c}`);
      tbody.innerHTML = rows.length ? rows.map(t=>`<tr>
        <td>${t.razao_social}</td>
        <td style="font-family:var(--font-mono);font-size:.8rem">${t.nr_insc}</td>
        <td>${t.tipo_servico}</td>
        <td>R$ ${Number(t.valor_bruto||0).toFixed(2)}</td>
        <td>R$ ${Number(t.valor_irrf||0).toFixed(2)}</td>
        <td>${t.competencia}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="reinfEditTomador(${JSON.stringify(t).replace(/"/g,'&quot;')})">Editar</button>
          <button class="btn btn-sm btn-danger" onclick="window.reinfDeleteTomador(${t.id},'${t.razao_social.replace(/'/g,"\\'")}')">Excluir</button>
        </td></tr>`).join('')
        : '<tr><td colspan="7" class="text-center text-muted">Sem tomadores nesta competência.</td></tr>';
      if (eventosEl) {
        const eventos = [
          { code:'R-1000', label:'Informações do Contribuinte', url:`/api/dp/reinf/r1000`, icon:'building' },
          { code:'R-2010', label:'Serviços Tomados', url:`/api/dp/reinf/r2010/${c}`, icon:'file-input' },
          { code:'R-4010', label:'Pagamentos a PF', url:`/api/dp/reinf/r4010/${c}`, icon:'user' },
          { code:'R-4020', label:'Pagamentos a PJ', url:`/api/dp/reinf/r4020/${c}`, icon:'building-2' },
          { code:'R-4099', label:'Fechamento', url:`/api/dp/reinf/r4099/${c}`, icon:'check-circle' },
        ];
        eventosEl.innerHTML = eventos.map(ev=>`
          <div class="col-md-4">
            <div class="card p-3 d-flex flex-column gap-2">
              <div class="d-flex align-items-center gap-2">
                <i data-lucide="${ev.icon}" class="w-5 h-5 text-violet-400"></i>
                <div>
                  <div class="fw-bold">${ev.code}</div>
                  <div class="text-muted small">${ev.label}</div>
                </div>
              </div>
              <a href="${ev.url}" target="_blank" class="btn btn-sm btn-primary w-100">Baixar XML</a>
            </div>
          </div>`).join('');
        if (window.lucide) lucide.createIcons();
      }
    } catch(e) { tbody.innerHTML = `<tr><td colspan="7" class="text-danger">${e.message}</td></tr>`; }
  };

  function reinfOpenModal(t) {
    document.getElementById('reinfModalTitle').textContent = t ? 'Editar Tomador' : 'Novo Tomador';
    document.getElementById('reinfEditId').value = t ? t.id : '';
    document.getElementById('reinfRazao').value = t ? t.razao_social : '';
    document.getElementById('reinfNrInsc').value = t ? t.nr_insc : '';
    document.getElementById('reinfTipoInsc').value = t ? (t.tipo_insc||'cnpj') : 'cnpj';
    document.getElementById('reinfTipoServ').value = t ? (t.tipo_servico||'0001') : '0001';
    document.getElementById('reinfCompModal').value = t ? t.competencia : document.getElementById('reinfComp').value;
    ['Bruto','Bc','Irrf','Csll','Pis','Cofins'].forEach(f => {
      const el = document.getElementById('reinfVlr'+f);
      if (el) el.value = t ? (Number(t['valor_'+f.toLowerCase()]||0).toFixed(2)) : '';
    });
    document.getElementById('reinfModalError').style.display = 'none';
    document.getElementById('reinfModal').style.display = 'flex';
  }
  window.reinfOpenModal = reinfOpenModal;

  function reinfEditTomador(t) { reinfOpenModal(t); }

  window.reinfSaveTomador = async () => {
    const id = document.getElementById('reinfEditId').value;
    const body = {
      razao_social: document.getElementById('reinfRazao').value.trim(),
      nr_insc: document.getElementById('reinfNrInsc').value.trim(),
      tipo_insc: document.getElementById('reinfTipoInsc').value,
      tipo_servico: document.getElementById('reinfTipoServ').value.trim(),
      competencia: document.getElementById('reinfCompModal').value,
      valor_bruto: parseFloat(document.getElementById('reinfVlrBruto').value||0),
      valor_bc_ret: parseFloat(document.getElementById('reinfVlrBc').value||0),
      valor_irrf: parseFloat(document.getElementById('reinfVlrIrrf').value||0),
      valor_csll: parseFloat(document.getElementById('reinfVlrCsll').value||0),
      valor_pis: parseFloat(document.getElementById('reinfVlrPis').value||0),
      valor_cofins: parseFloat(document.getElementById('reinfVlrCofins').value||0),
    };
    const errBox = document.getElementById('reinfModalError');
    if (!body.razao_social || !body.nr_insc) { errBox.textContent = 'Razão Social e CNPJ/CPF são obrigatórios.'; errBox.style.display = ''; return; }
    try {
      if (id) await apiFetch(`/api/dp/reinf/tomadores/${id}`, { method:'PUT', body: JSON.stringify(body) });
      else await apiFetch('/api/dp/reinf/tomadores', { method:'POST', body: JSON.stringify(body) });
      document.getElementById('reinfModal').style.display = 'none';
      showToast(id ? 'Tomador atualizado.' : 'Tomador criado.', 'success');
      window.reinfLoadTomadores();
    } catch(e) { errBox.textContent = 'Erro: ' + e.message; errBox.style.display = ''; }
  };

  window.reinfDeleteTomador = async (id, nome) => {
    if (!confirm(`Excluir tomador "${nome}"?`)) return;
    try {
      await apiFetch(`/api/dp/reinf/tomadores/${id}`, { method:'DELETE' });
      showToast('Tomador excluído.', 'success');
      window.reinfLoadTomadores();
    } catch(e) { showToast('Erro: ' + e.message, 'error'); }
  };

  await window.reinfLoadTomadores();
}

// ── BENEFÍCIOS ───────────────────────────────────────────────────────────────
async function renderBeneficios(el) {
  let bTypes = [], employees = dpEmployees || [], selEmp = '', innerTab = 'tipos';
  const render = async () => {
    bTypes = await apiFetch('/api/dp/benefit-types');
    el.innerHTML = `
      <div class="flex gap-2 mb-4">
        <button onclick="window._bfTab('tipos')" class="btn btn-sm ${innerTab==='tipos'?'btn-primary':'btn-secondary'}">Tipos de Benefício</button>
        <button onclick="window._bfTab('por_funcionario')" class="btn btn-sm ${innerTab==='por_funcionario'?'btn-primary':'btn-secondary'}">Por Funcionário</button>
      </div>
      <div id="bf-content"></div>`;
    window._bfTab = async (t) => { innerTab = t; await render(); };
    const bc = document.getElementById('bf-content');
    if (innerTab === 'tipos') {
      bc.innerHTML = `
        <div class="flex justify-between items-center mb-3">
          <h3 class="font-bold text-slate-800 dark:text-slate-100">Tipos de Benefício</h3>
          <button onclick="window._bfOpenModal(null)" class="btn btn-primary btn-sm">+ Novo Tipo</button>
        </div>
        <div class="table-responsive">${card2(`
          <table class="table table-sm">
            <thead><tr><th>Nome</th><th>Tipo</th><th>Modalidade</th><th>% Desconto</th><th>Limite %</th><th>Status</th><th>Ações</th></tr></thead>
            <tbody>${bTypes.map(b=>`<tr>
              <td>${b.nome}</td>
              <td><span class="badge badge-info">${b.tipo.replace(/_/g,' ')}</span></td>
              <td>${b.modalidade_desconto}</td>
              <td>${b.percentual_desconto||0}%</td>
              <td>${b.limite_pct_salario>0?b.limite_pct_salario+'%':'—'}</td>
              <td><span class="badge ${b.ativo?'badge-success':'badge-secondary'}">${b.ativo?'Ativo':'Inativo'}</span></td>
              <td>
                <button onclick="window._bfOpenModal(${JSON.stringify(b).replace(/"/g,'&quot;')})" class="btn btn-sm btn-secondary">Editar</button>
                <button onclick="window._bfDelete(${b.id},'${b.nome.replace(/'/g,"\\'")}','tipo')" class="btn btn-sm btn-danger">Excluir</button>
              </td>
            </tr>`).join('')}</tbody>
          </table>`)}
        </div>
        <div id="bf-modal" class="modal-overlay" style="display:none">
          <div class="modal-box">
            <h3 id="bf-modal-title">Tipo de Benefício</h3>
            <input type="hidden" id="bf-id">
            <div class="form-row">
              <div class="form-group"><label>Nome</label><input id="bf-nome" class="form-control" placeholder="Vale Alimentação"></div>
              <div class="form-group"><label>Tipo</label>
                <select id="bf-tipo" class="form-control">
                  <option value="vale_alimentacao">Vale Alimentação</option>
                  <option value="vale_transporte">Vale Transporte</option>
                  <option value="plano_saude">Plano de Saúde</option>
                  <option value="plano_odonto">Plano Odontológico</option>
                  <option value="outros">Outros</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Modalidade de Desconto</label>
                <select id="bf-modalidade" class="form-control">
                  <option value="percentual">Percentual sobre valor</option>
                  <option value="fixo">Valor fixo</option>
                </select>
              </div>
              <div class="form-group"><label>% Desconto</label><input id="bf-pct" type="number" step="0.01" class="form-control" placeholder="20"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Valor Fixo Desconto (R$)</label><input id="bf-fixo" type="number" step="0.01" class="form-control" placeholder="0"></div>
              <div class="form-group"><label>Limite % do Salário</label><input id="bf-limite" type="number" step="0.01" class="form-control" placeholder="6"></div>
            </div>
            <div class="d-flex gap-2 justify-content-end mt-3">
              <button onclick="document.getElementById('bf-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
              <button onclick="window._bfSave()" class="btn btn-primary">Salvar</button>
            </div>
          </div>
        </div>`;
      window._bfOpenModal = (b) => {
        document.getElementById('bf-modal-title').textContent = b ? 'Editar Tipo' : 'Novo Tipo';
        document.getElementById('bf-id').value = b ? b.id : '';
        document.getElementById('bf-nome').value = b ? b.nome : '';
        document.getElementById('bf-tipo').value = b ? b.tipo : 'vale_alimentacao';
        document.getElementById('bf-modalidade').value = b ? b.modalidade_desconto : 'percentual';
        document.getElementById('bf-pct').value = b ? b.percentual_desconto : '';
        document.getElementById('bf-fixo').value = b ? b.valor_fixo_desconto : '';
        document.getElementById('bf-limite').value = b ? b.limite_pct_salario : '';
        document.getElementById('bf-modal').style.display = 'flex';
      };
      window._bfSave = async () => {
        const id = document.getElementById('bf-id').value;
        const body = {
          nome: document.getElementById('bf-nome').value.trim(),
          tipo: document.getElementById('bf-tipo').value,
          modalidade_desconto: document.getElementById('bf-modalidade').value,
          percentual_desconto: parseFloat(document.getElementById('bf-pct').value||0),
          valor_fixo_desconto: parseFloat(document.getElementById('bf-fixo').value||0),
          limite_pct_salario: parseFloat(document.getElementById('bf-limite').value||0),
        };
        try {
          if (id) await apiFetch(`/api/dp/benefit-types/${id}`, {method:'PUT',body:JSON.stringify(body)});
          else await apiFetch('/api/dp/benefit-types', {method:'POST',body:JSON.stringify(body)});
          document.getElementById('bf-modal').style.display = 'none';
          showToast('Salvo!','success'); await render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
    } else {
      // Por funcionário
      const empOpts = employees.map(e=>`<option value="${e.id}" ${selEmp==e.id?'selected':''}>${e.name}</option>`).join('');
      let empBenefits = [];
      if (selEmp) {
        try { empBenefits = await apiFetch(`/api/dp/employees/${selEmp}/benefits`); } catch {}
      }
      const totBruto = empBenefits.reduce((s,b)=>s+parseFloat(b.valor_bruto||0),0);
      const totDesc = empBenefits.reduce((s,b)=>s+parseFloat(b.valor_desconto||0),0);
      bc.innerHTML = `
        <div class="flex gap-3 items-center mb-4">
          <select class="form-control" style="max-width:280px" onchange="selEmp=this.value;window._bfTab('por_funcionario')">
            <option value="">— Selecione o Funcionário —</option>${empOpts}
          </select>
          ${selEmp?`<button onclick="window._bfEmpModal()" class="btn btn-primary btn-sm">+ Conceder Benefício</button>`:''}
        </div>
        ${selEmp?`
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          ${kpiDP('Benefícios',empBenefits.length,'ativos','heart','text-pink-600')}
          ${kpiDP('Total Bruto Empresa',fBRL2(totBruto),'custo empresa','building','text-blue-600')}
          ${kpiDP('Total Desconto',fBRL2(totDesc),'desconto funcionário','minus-circle','text-orange-600')}
          ${kpiDP('Custo Líquido',fBRL2(totBruto-totDesc),'empresa arca','trending-up','text-emerald-600')}
        </div>
        ${card2(`<table class="table table-sm">
          <thead><tr><th>Benefício</th><th>Valor Bruto</th><th>Desconto</th><th>Início</th><th>Fim</th><th>Status</th><th>Ações</th></tr></thead>
          <tbody>${empBenefits.map(b=>`<tr>
            <td>${b.benefit_nome||b.benefit_type_id}</td>
            <td>${fBRL2(b.valor_bruto)}</td>
            <td>${fBRL2(b.valor_desconto)}</td>
            <td>${fDate2(b.data_inicio)}</td>
            <td>${b.data_fim?fDate2(b.data_fim):'—'}</td>
            <td><span class="badge ${b.ativo?'badge-success':'badge-secondary'}">${b.ativo?'Ativo':'Inativo'}</span></td>
            <td><button onclick="window._bfDelete(${b.id},'${(b.benefit_nome||'').replace(/'/g,"\\'")}','emp')" class="btn btn-sm btn-danger">Remover</button></td>
          </tr>`).join('')}</tbody>
        </table>`)}` : '<p class="text-muted">Selecione um funcionário para ver seus benefícios.</p>'}
        <div id="bf-emp-modal" class="modal-overlay" style="display:none">
          <div class="modal-box">
            <h3>Conceder Benefício</h3>
            <div class="form-group"><label>Tipo de Benefício</label>
              <select id="bfe-tipo" class="form-control" onchange="window._bfCalcDesc()">
                ${bTypes.map(b=>`<option value="${b.id}" data-pct="${b.percentual_desconto}" data-fixo="${b.valor_fixo_desconto}" data-mod="${b.modalidade_desconto}" data-lim="${b.limite_pct_salario}">${b.nome}</option>`).join('')}
              </select>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Valor Bruto (R$)</label><input id="bfe-bruto" type="number" step="0.01" class="form-control" oninput="window._bfCalcDesc()" placeholder="500"></div>
              <div class="form-group"><label>Desconto Calculado (R$)</label><input id="bfe-desc" type="number" step="0.01" class="form-control" readonly></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Data Início</label><input id="bfe-inicio" type="date" class="form-control"></div>
              <div class="form-group"><label>Data Fim (opcional)</label><input id="bfe-fim" type="date" class="form-control"></div>
            </div>
            <div class="d-flex gap-2 justify-content-end mt-3">
              <button onclick="document.getElementById('bf-emp-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
              <button onclick="window._bfEmpSave()" class="btn btn-primary">Salvar</button>
            </div>
          </div>
        </div>`;
      window._bfCalcDesc = () => {
        const sel = document.getElementById('bfe-tipo');
        if (!sel) return;
        const opt = sel.options[sel.selectedIndex];
        const bruto = parseFloat(document.getElementById('bfe-bruto')?.value||0);
        const mod = opt.dataset.mod;
        let desc = mod==='fixo' ? parseFloat(opt.dataset.fixo||0) : bruto * parseFloat(opt.dataset.pct||0) / 100;
        const empSalary = (employees.find(e=>e.id==selEmp)||{salary:0}).salary;
        const lim = parseFloat(opt.dataset.lim||0);
        if (lim>0 && empSalary>0) desc = Math.min(desc, empSalary * lim / 100);
        const el2 = document.getElementById('bfe-desc');
        if (el2) el2.value = desc.toFixed(2);
      };
      window._bfEmpModal = () => {
        document.getElementById('bfe-bruto').value = '';
        document.getElementById('bfe-desc').value = '';
        document.getElementById('bfe-inicio').value = new Date().toISOString().slice(0,10);
        document.getElementById('bfe-fim').value = '';
        document.getElementById('bf-emp-modal').style.display = 'flex';
      };
      window._bfEmpSave = async () => {
        const body = {
          benefit_type_id: parseInt(document.getElementById('bfe-tipo').value),
          valor_bruto: parseFloat(document.getElementById('bfe-bruto').value||0),
          data_inicio: document.getElementById('bfe-inicio').value,
          data_fim: document.getElementById('bfe-fim').value||null,
        };
        try {
          await apiFetch(`/api/dp/employees/${selEmp}/benefits`, {method:'POST',body:JSON.stringify(body)});
          document.getElementById('bf-emp-modal').style.display = 'none';
          showToast('Benefício concedido!','success'); await render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
    }
    window._bfDelete = async (id, nome, ctx) => {
      if (!confirm(`Excluir "${nome}"?`)) return;
      try {
        const url = ctx==='tipo' ? `/api/dp/benefit-types/${id}` : `/api/dp/employee-benefits/${id}`;
        await apiFetch(url, {method:'DELETE'});
        showToast('Excluído.','success'); await render();
      } catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    if (window.lucide) lucide.createIcons();
  };
  await render();
}

// ── ADIANTAMENTOS ─────────────────────────────────────────────────────────────
async function renderAdiantamentos(el) {
  const hoje = new Date().toISOString().slice(0,7);
  let comp = hoje;
  const render = async () => {
    const rows = await apiFetch(`/api/dp/advances?competencia=${comp}`);
    const total = rows.reduce((s,r)=>s+parseFloat(r.valor||0),0);
    const emps = [...new Set(rows.map(r=>r.employee_id))].length;
    const max = rows.length ? Math.max(...rows.map(r=>parseFloat(r.valor||0))) : 0;
    const media = rows.length ? total/rows.length : 0;
    el.innerHTML = `
      <div class="flex items-center gap-3 mb-4">
        <label class="text-sm font-semibold text-slate-600 dark:text-slate-300">Competência:</label>
        <input type="month" value="${comp}" class="form-control" style="max-width:160px" onchange="comp=this.value;render()">
        <button onclick="window._advOpenModal()" class="btn btn-primary btn-sm">+ Adiantamento</button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        ${kpiDP('Total Adiantamentos',fBRL2(total),'no mês','banknote','text-blue-600')}
        ${kpiDP('Funcionários',emps,'com adiantamento','users','text-violet-600')}
        ${kpiDP('Maior Adiantamento',fBRL2(max),'no mês','trending-up','text-orange-600')}
        ${kpiDP('Média',fBRL2(media),'por adiantamento','calculator','text-emerald-600')}
      </div>
      ${card2(`<table class="table table-sm">
        <thead><tr><th>Funcionário</th><th>Salário</th><th>Valor</th><th>% Sal.</th><th>Tipo</th><th>Data Pgto</th><th>Ações</th></tr></thead>
        <tbody>${rows.map(r=>`<tr>
          <td>${r.employee_name||''}</td>
          <td>${fBRL2(r.employee_salary)}</td>
          <td>${fBRL2(r.valor)}</td>
          <td>${r.employee_salary>0?(parseFloat(r.valor)/parseFloat(r.employee_salary)*100).toFixed(1)+'%':'—'}</td>
          <td>${r.tipo}</td>
          <td>${r.data_pagamento||'—'}</td>
          <td><button onclick="window._advDelete(${r.id})" class="btn btn-sm btn-danger">Excluir</button></td>
        </tr>`).join('')}</tbody>
      </table>`)}
      <div id="adv-modal" class="modal-overlay" style="display:none">
        <div class="modal-box">
          <h3>Novo Adiantamento</h3>
          <div class="form-row">
            <div class="form-group"><label>Funcionário</label>
              <select id="adv-emp" class="form-control" onchange="window._advCalcPct()">
                <option value="">Selecione</option>
                ${(dpEmployees||[]).filter(e=>e.active).map(e=>`<option value="${e.id}" data-salary="${e.salary}">${e.name}</option>`).join('')}
              </select>
            </div>
            <div class="form-group"><label>Competência</label><input id="adv-comp" type="month" value="${comp}" class="form-control"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Valor (R$)</label><input id="adv-valor" type="number" step="0.01" class="form-control" oninput="window._advCalcPct()" placeholder="500"></div>
            <div class="form-group"><label>% do Salário</label><input id="adv-pct" class="form-control" readonly placeholder="—"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Tipo</label>
              <select id="adv-tipo" class="form-control"><option value="quinzenal">Quinzenal</option><option value="avulso">Avulso</option></select>
            </div>
            <div class="form-group"><label>Data Pagamento</label><input id="adv-data" type="date" class="form-control" value="${new Date().toISOString().slice(0,10)}"></div>
          </div>
          <div id="adv-warn" class="alert alert-warning" style="display:none">⚠️ Valor excede 40% do salário.</div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button onclick="document.getElementById('adv-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
            <button onclick="window._advSave()" class="btn btn-primary">Salvar</button>
          </div>
        </div>
      </div>`;
    window._advCalcPct = () => {
      const sel = document.getElementById('adv-emp');
      if (!sel) return;
      const salary = parseFloat(sel.options[sel.selectedIndex]?.dataset?.salary||0);
      const valor = parseFloat(document.getElementById('adv-valor')?.value||0);
      const pct = salary>0 ? (valor/salary*100).toFixed(1)+'%' : '—';
      const pctEl = document.getElementById('adv-pct');
      if (pctEl) { pctEl.value = pct; pctEl.style.color = (salary>0&&valor>salary*0.4)?'red':''; }
      const warnEl = document.getElementById('adv-warn');
      if (warnEl) warnEl.style.display = (salary>0&&valor>salary*0.4)?'':'none';
    };
    window._advOpenModal = () => {
      document.getElementById('adv-emp').value = '';
      document.getElementById('adv-valor').value = '';
      document.getElementById('adv-pct').value = '';
      document.getElementById('adv-modal').style.display = 'flex';
    };
    window._advSave = async () => {
      const body = {
        employee_id: parseInt(document.getElementById('adv-emp').value),
        competencia: document.getElementById('adv-comp').value,
        valor: parseFloat(document.getElementById('adv-valor').value||0),
        tipo: document.getElementById('adv-tipo').value,
        data_pagamento: document.getElementById('adv-data').value,
      };
      if (!body.employee_id||!body.valor) { showToast('Preencha funcionário e valor.','error'); return; }
      try {
        await apiFetch('/api/dp/advances', {method:'POST',body:JSON.stringify(body)});
        document.getElementById('adv-modal').style.display = 'none';
        showToast('Adiantamento lançado!','success'); await render();
      } catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    window._advDelete = async (id) => {
      if (!confirm('Excluir adiantamento?')) return;
      try { await apiFetch(`/api/dp/advances/${id}`,{method:'DELETE'}); showToast('Excluído.','success'); await render(); }
      catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    if (window.lucide) lucide.createIcons();
  };
  await render();
}

// ── PENSÃO ALIMENTÍCIA ────────────────────────────────────────────────────────
async function renderPensao(el) {
  const render = async () => {
    const rows = await apiFetch('/api/dp/alimony');
    const ativas = rows.filter(r=>r.ativo).length;
    const funcs = [...new Set(rows.filter(r=>r.ativo).map(r=>r.employee_id))].length;
    el.innerHTML = `
      <div class="flex justify-between items-center mb-4">
        <div class="grid grid-cols-3 gap-4">
          ${kpiDP('Ordens Ativas',ativas,'','scale','text-blue-600')}
          ${kpiDP('Funcionários',funcs,'com desconto','users','text-violet-600')}
        </div>
        <button onclick="window._pensaoOpenModal(null)" class="btn btn-primary btn-sm">+ Nova Ordem</button>
      </div>
      ${card2(`<table class="table table-sm">
        <thead><tr><th>Funcionário</th><th>Processo</th><th>Beneficiário</th><th>Modalidade</th><th>Valor/%</th><th>Base</th><th>Conta</th><th>Status</th><th>Ações</th></tr></thead>
        <tbody>${rows.map(r=>`<tr>
          <td>${r.employee_name||''}</td>
          <td style="font-size:.8rem">${r.processo||'—'}</td>
          <td>${r.beneficiario}</td>
          <td>${r.modalidade==='percentual'?'% sobre '+r.base_calculo:'Fixo'}</td>
          <td>${r.modalidade==='percentual'?r.percentual+'%':fBRL2(r.valor_fixo)}</td>
          <td>${r.base_calculo}</td>
          <td style="font-size:.75rem">${r.banco?r.banco+' Ag.'+r.agencia+' C/C '+r.conta:'—'}</td>
          <td><span class="badge ${r.ativo?'badge-success':'badge-secondary'}">${r.ativo?'Ativa':'Encerrada'}</span></td>
          <td>
            <button onclick="window._pensaoOpenModal(${JSON.stringify(r).replace(/"/g,'&quot;')})" class="btn btn-sm btn-secondary">Editar</button>
            <button onclick="window._pensaoDelete(${r.id})" class="btn btn-sm btn-danger">Excluir</button>
          </td>
        </tr>`).join('')}</tbody>
      </table>`)}
      <div id="pensao-modal" class="modal-overlay" style="display:none">
        <div class="modal-box" style="max-width:600px">
          <h3 id="pensao-modal-title">Nova Ordem de Pensão</h3>
          <input type="hidden" id="pensao-id">
          <div class="form-row">
            <div class="form-group"><label>Funcionário</label>
              <select id="pensao-emp" class="form-control">
                ${(dpEmployees||[]).map(e=>`<option value="${e.id}">${e.name}</option>`).join('')}
              </select>
            </div>
            <div class="form-group"><label>Nº Processo</label><input id="pensao-proc" class="form-control" placeholder="0001234-00.2024.8.00.0000"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Nome do Beneficiário</label><input id="pensao-benef" class="form-control" placeholder="Maria Silva"></div>
            <div class="form-group"><label>CPF do Beneficiário</label><input id="pensao-cpf" class="form-control" placeholder="000.000.000-00"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Modalidade</label>
              <select id="pensao-mod" class="form-control">
                <option value="percentual">Percentual</option>
                <option value="fixo">Valor Fixo</option>
              </select>
            </div>
            <div class="form-group"><label>Base de Cálculo</label>
              <select id="pensao-base" class="form-control">
                <option value="liquido">Salário Líquido</option>
                <option value="bruto">Salário Bruto</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Percentual (%)</label><input id="pensao-pct" type="number" step="0.01" class="form-control" placeholder="30"></div>
            <div class="form-group"><label>Valor Fixo (R$)</label><input id="pensao-fixo" type="number" step="0.01" class="form-control" placeholder="0"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Banco</label><input id="pensao-banco" class="form-control" placeholder="001 - Banco do Brasil"></div>
            <div class="form-group"><label>Agência</label><input id="pensao-ag" class="form-control" placeholder="0001"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Conta</label><input id="pensao-conta" class="form-control" placeholder="12345-6"></div>
            <div class="form-group"><label>Data Início</label><input id="pensao-inicio" type="date" class="form-control"></div>
          </div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button onclick="document.getElementById('pensao-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
            <button onclick="window._pensaoSave()" class="btn btn-primary">Salvar</button>
          </div>
        </div>
      </div>`;
    window._pensaoOpenModal = (r) => {
      document.getElementById('pensao-modal-title').textContent = r ? 'Editar Ordem' : 'Nova Ordem de Pensão';
      document.getElementById('pensao-id').value = r ? r.id : '';
      document.getElementById('pensao-emp').value = r ? r.employee_id : '';
      document.getElementById('pensao-proc').value = r ? (r.processo||'') : '';
      document.getElementById('pensao-benef').value = r ? r.beneficiario : '';
      document.getElementById('pensao-cpf').value = r ? (r.cpf_beneficiario||'') : '';
      document.getElementById('pensao-mod').value = r ? r.modalidade : 'percentual';
      document.getElementById('pensao-base').value = r ? r.base_calculo : 'liquido';
      document.getElementById('pensao-pct').value = r ? r.percentual : '';
      document.getElementById('pensao-fixo').value = r ? r.valor_fixo : '';
      document.getElementById('pensao-banco').value = r ? (r.banco||'') : '';
      document.getElementById('pensao-ag').value = r ? (r.agencia||'') : '';
      document.getElementById('pensao-conta').value = r ? (r.conta||'') : '';
      document.getElementById('pensao-inicio').value = r ? (r.data_inicio||'') : new Date().toISOString().slice(0,10);
      document.getElementById('pensao-modal').style.display = 'flex';
    };
    window._pensaoSave = async () => {
      const id = document.getElementById('pensao-id').value;
      const body = {
        employee_id: parseInt(document.getElementById('pensao-emp').value),
        processo: document.getElementById('pensao-proc').value,
        beneficiario: document.getElementById('pensao-benef').value.trim(),
        cpf_beneficiario: document.getElementById('pensao-cpf').value,
        modalidade: document.getElementById('pensao-mod').value,
        base_calculo: document.getElementById('pensao-base').value,
        percentual: parseFloat(document.getElementById('pensao-pct').value||0),
        valor_fixo: parseFloat(document.getElementById('pensao-fixo').value||0),
        banco: document.getElementById('pensao-banco').value,
        agencia: document.getElementById('pensao-ag').value,
        conta: document.getElementById('pensao-conta').value,
        data_inicio: document.getElementById('pensao-inicio').value,
      };
      try {
        if (id) await apiFetch(`/api/dp/alimony/${id}`,{method:'PUT',body:JSON.stringify(body)});
        else await apiFetch('/api/dp/alimony',{method:'POST',body:JSON.stringify(body)});
        document.getElementById('pensao-modal').style.display = 'none';
        showToast('Salvo!','success'); await render();
      } catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    window._pensaoDelete = async (id) => {
      if (!confirm('Excluir ordem de pensão?')) return;
      try { await apiFetch(`/api/dp/alimony/${id}`,{method:'DELETE'}); showToast('Excluída.','success'); await render(); }
      catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    if (window.lucide) lucide.createIcons();
  };
  await render();
}

// ── AUTÔNOMOS / RPA ───────────────────────────────────────────────────────────
async function renderAutonomos(el) {
  let innerTab = 'cadastro';
  const hoje = new Date().toISOString().slice(0,7);
  let comp = hoje;
  const render = async () => {
    el.innerHTML = `
      <div class="flex gap-2 mb-4">
        <button onclick="window._awTab('cadastro')" class="btn btn-sm ${innerTab==='cadastro'?'btn-primary':'btn-secondary'}">Cadastro</button>
        <button onclick="window._awTab('rpa')" class="btn btn-sm ${innerTab==='rpa'?'btn-primary':'btn-secondary'}">Pagamentos RPA</button>
      </div>
      <div id="aw-content"></div>`;
    window._awTab = (t) => { innerTab = t; render(); };
    const bc = document.getElementById('aw-content');
    if (innerTab === 'cadastro') {
      const workers = await apiFetch('/api/dp/autonomous');
      bc.innerHTML = `
        <div class="flex justify-between items-center mb-3">
          <h3 class="font-bold text-slate-800 dark:text-slate-100">Autônomos Cadastrados</h3>
          <button onclick="window._awOpenModal(null)" class="btn btn-primary btn-sm">+ Novo Autônomo</button>
        </div>
        ${card2(`<table class="table table-sm">
          <thead><tr><th>Nome</th><th>CPF</th><th>CBO</th><th>Cidade</th><th>Status</th><th>Ações</th></tr></thead>
          <tbody>${workers.map(w=>`<tr>
            <td>${w.nome}</td>
            <td style="font-family:monospace">${w.cpf}</td>
            <td>${w.cbo||'—'}</td>
            <td>${w.cidade||'—'} ${w.uf||''}</td>
            <td><span class="badge ${w.ativo?'badge-success':'badge-secondary'}">${w.ativo?'Ativo':'Inativo'}</span></td>
            <td>
              <button onclick="window._awOpenModal(${JSON.stringify(w).replace(/"/g,'&quot;')})" class="btn btn-sm btn-secondary">Editar</button>
              <button onclick="openAuthed('/api/dp/esocial/s2300/${w.id}','S-2300-${w.id}.xml')" class="btn btn-sm btn-secondary">S-2300</button>
            </td>
          </tr>`).join('')}</tbody>
        </table>`)}
        <div id="aw-modal" class="modal-overlay" style="display:none">
          <div class="modal-box">
            <h3 id="aw-modal-title">Novo Autônomo</h3>
            <input type="hidden" id="aw-id">
            <div class="form-row">
              <div class="form-group"><label>Nome</label><input id="aw-nome" class="form-control"></div>
              <div class="form-group"><label>CPF</label><input id="aw-cpf" class="form-control" placeholder="000.000.000-00"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>PIS/PASEP</label><input id="aw-pis" class="form-control"></div>
              <div class="form-group"><label>CBO</label><input id="aw-cbo" class="form-control" value="2521-05"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Endereço</label><input id="aw-end" class="form-control"></div>
              <div class="form-group"><label>Cidade</label><input id="aw-cid" class="form-control"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>UF</label><input id="aw-uf" class="form-control" maxlength="2"></div>
              <div class="form-group"><label>Banco / Ag / CC</label><input id="aw-banco" class="form-control" placeholder="001 / 0001 / 12345-6"></div>
            </div>
            <div class="d-flex gap-2 justify-content-end mt-3">
              <button onclick="document.getElementById('aw-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
              <button onclick="window._awSave()" class="btn btn-primary">Salvar</button>
            </div>
          </div>
        </div>`;
      window._awOpenModal = (w) => {
        document.getElementById('aw-modal-title').textContent = w ? 'Editar Autônomo' : 'Novo Autônomo';
        document.getElementById('aw-id').value = w ? w.id : '';
        document.getElementById('aw-nome').value = w ? w.nome : '';
        document.getElementById('aw-cpf').value = w ? w.cpf : '';
        document.getElementById('aw-pis').value = w ? (w.pis_pasep||'') : '';
        document.getElementById('aw-cbo').value = w ? (w.cbo||'2521-05') : '2521-05';
        document.getElementById('aw-end').value = w ? (w.endereco||'') : '';
        document.getElementById('aw-cid').value = w ? (w.cidade||'') : '';
        document.getElementById('aw-uf').value = w ? (w.uf||'') : '';
        const bancoStr = w ? `${w.banco||''} / ${w.agencia||''} / ${w.conta||''}` : '';
        document.getElementById('aw-banco').value = bancoStr.trim() === '/ /' ? '' : bancoStr;
        document.getElementById('aw-modal').style.display = 'flex';
      };
      window._awSave = async () => {
        const id = document.getElementById('aw-id').value;
        const banco_raw = document.getElementById('aw-banco').value.split('/');
        const body = {
          nome: document.getElementById('aw-nome').value.trim(),
          cpf: document.getElementById('aw-cpf').value.trim(),
          pis_pasep: document.getElementById('aw-pis').value.trim(),
          cbo: document.getElementById('aw-cbo').value.trim(),
          endereco: document.getElementById('aw-end').value.trim(),
          cidade: document.getElementById('aw-cid').value.trim(),
          uf: document.getElementById('aw-uf').value.trim(),
          banco: (banco_raw[0]||'').trim(),
          agencia: (banco_raw[1]||'').trim(),
          conta: (banco_raw[2]||'').trim(),
          ativo: 1,
        };
        try {
          if (id) await apiFetch(`/api/dp/autonomous/${id}`,{method:'PUT',body:JSON.stringify(body)});
          else await apiFetch('/api/dp/autonomous',{method:'POST',body:JSON.stringify(body)});
          document.getElementById('aw-modal').style.display = 'none';
          showToast('Salvo!','success'); await render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
    } else {
      // RPA payments
      const workers = await apiFetch('/api/dp/autonomous');
      const payments = await apiFetch(`/api/dp/rpa?competencia=${comp}`);
      const totBruto = payments.reduce((s,p)=>s+parseFloat(p.valor_bruto||0),0);
      const totInss = payments.reduce((s,p)=>s+parseFloat(p.inss_retido||0),0);
      const totIrrf = payments.reduce((s,p)=>s+parseFloat(p.irrf_retido||0),0);
      const totLiq = payments.reduce((s,p)=>s+parseFloat(p.valor_liquido||0),0);
      bc.innerHTML = `
        <div class="flex gap-3 items-center mb-4">
          <input type="month" value="${comp}" class="form-control" style="max-width:160px" onchange="comp=this.value;render()">
          <button onclick="window._rpaOpenModal()" class="btn btn-primary btn-sm">+ Registrar RPA</button>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          ${kpiDP('Pagamentos',payments.length,'no mês','receipt','text-violet-600')}
          ${kpiDP('Total Bruto',fBRL2(totBruto),'','banknote','text-blue-600')}
          ${kpiDP('INSS Retido',fBRL2(totInss),'11%','shield','text-orange-600')}
          ${kpiDP('IRRF Retido',fBRL2(totIrrf),'tabela progressiva','percent','text-red-600')}
          ${kpiDP('Total Líquido',fBRL2(totLiq),'a pagar','trending-down','text-emerald-600')}
        </div>
        ${card2(`<table class="table table-sm">
          <thead><tr><th>Nome</th><th>Descrição</th><th>Bruto</th><th>INSS</th><th>IRRF</th><th>ISS</th><th>Líquido</th><th>Data</th><th>Ações</th></tr></thead>
          <tbody>${payments.map(p=>`<tr>
            <td>${p.nome||''}</td>
            <td style="font-size:.8rem">${p.descricao_servico||''}</td>
            <td>${fBRL2(p.valor_bruto)}</td>
            <td>${fBRL2(p.inss_retido)}</td>
            <td>${fBRL2(p.irrf_retido)}</td>
            <td>${fBRL2(p.iss_retido)}</td>
            <td class="font-semibold text-emerald-600">${fBRL2(p.valor_liquido)}</td>
            <td>${p.data_pagamento||'—'}</td>
            <td>
              <button onclick="openAuthed('/api/dp/rpa/${p.id}/recibo')" class="btn btn-sm btn-secondary">RPA</button>
              <button onclick="openAuthed('/api/dp/esocial/s2300/${p.autonomous_id}','S-2300.xml')" class="btn btn-sm btn-secondary">S-2300</button>
              <button onclick="window._rpaDelete(${p.id})" class="btn btn-sm btn-danger">×</button>
            </td>
          </tr>`).join('')}</tbody>
        </table>`)}
        <div id="rpa-modal" class="modal-overlay" style="display:none">
          <div class="modal-box">
            <h3>Registrar Pagamento RPA</h3>
            <div class="form-row">
              <div class="form-group"><label>Autônomo</label>
                <select id="rpa-aut" class="form-control">
                  ${workers.map(w=>`<option value="${w.id}">${w.nome} — ${w.cpf}</option>`).join('')}
                </select>
              </div>
              <div class="form-group"><label>Competência</label><input id="rpa-comp" type="month" value="${comp}" class="form-control"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Data Pagamento</label><input id="rpa-data" type="date" class="form-control" value="${new Date().toISOString().slice(0,10)}"></div>
              <div class="form-group"><label>ISS Retido (R$)</label><input id="rpa-iss" type="number" step="0.01" value="0" class="form-control"></div>
            </div>
            <div class="form-group"><label>Descrição do Serviço</label><input id="rpa-desc" class="form-control" placeholder="Consultoria em TI — Implantação de sistema"></div>
            <div class="form-row">
              <div class="form-group"><label>Valor Bruto (R$)</label><input id="rpa-bruto" type="number" step="0.01" class="form-control" oninput="window._rpaCalc()" placeholder="1000"></div>
              <div class="form-group"><label>INSS 11% (calculado)</label><input id="rpa-inss-calc" class="form-control" readonly></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>IRRF (calculado)</label><input id="rpa-irrf-calc" class="form-control" readonly></div>
              <div class="form-group"><label>Líquido (calculado)</label><input id="rpa-liq-calc" class="form-control" readonly></div>
            </div>
            <div class="d-flex gap-2 justify-content-end mt-3">
              <button onclick="document.getElementById('rpa-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
              <button onclick="window._rpaSave()" class="btn btn-primary">Salvar</button>
            </div>
          </div>
        </div>`;
      window._rpaCalc = () => {
        const bruto = parseFloat(document.getElementById('rpa-bruto')?.value||0);
        const inss = Math.min(bruto*0.11, 897.32);
        const baseIrrf = bruto - inss;
        let irrf = 0;
        const brackets = [[2824,0,0],[3751.05,7.5,211.80],[4664.68,15,492.78],[5871.22,22.5,843.34],[Infinity,27.5,1137.74]];
        for (const [lim,aliq,ded] of brackets) { if (baseIrrf<=lim){ irrf=Math.max(0,baseIrrf*aliq/100-ded); break; } }
        const iss = parseFloat(document.getElementById('rpa-iss')?.value||0);
        const liq = bruto - inss - irrf - iss;
        const set = (id,v) => { const el=document.getElementById(id); if(el) el.value=v.toFixed(2); };
        set('rpa-inss-calc', inss); set('rpa-irrf-calc', irrf); set('rpa-liq-calc', liq);
      };
      window._rpaOpenModal = () => {
        document.getElementById('rpa-bruto').value = '';
        ['rpa-inss-calc','rpa-irrf-calc','rpa-liq-calc'].forEach(id=>{ const el=document.getElementById(id); if(el) el.value=''; });
        document.getElementById('rpa-modal').style.display = 'flex';
      };
      window._rpaSave = async () => {
        const body = {
          autonomous_id: parseInt(document.getElementById('rpa-aut').value),
          competencia: document.getElementById('rpa-comp').value,
          data_pagamento: document.getElementById('rpa-data').value,
          descricao_servico: document.getElementById('rpa-desc').value.trim(),
          valor_bruto: parseFloat(document.getElementById('rpa-bruto').value||0),
          iss_retido: parseFloat(document.getElementById('rpa-iss').value||0),
        };
        try {
          await apiFetch('/api/dp/rpa',{method:'POST',body:JSON.stringify(body)});
          document.getElementById('rpa-modal').style.display = 'none';
          showToast('RPA registrado!','success'); await render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._rpaDelete = async (id) => {
        if (!confirm('Excluir pagamento RPA?')) return;
        try { await apiFetch(`/api/dp/rpa/${id}`,{method:'DELETE'}); showToast('Excluído.','success'); await render(); }
        catch(e) { showToast('Erro: '+e.message,'error'); }
      };
    }
    if (window.lucide) lucide.createIcons();
  };
  await render();
}

// ── PRÓ-LABORE ────────────────────────────────────────────────────────────────
async function renderProlabore(el) {
  let innerTab = 'socios';
  const hoje = new Date().toISOString().slice(0,7);
  let comp = hoje;
  const render = async () => {
    el.innerHTML = `
      <div class="flex gap-2 mb-4">
        <button onclick="window._plTab('socios')" class="btn btn-sm ${innerTab==='socios'?'btn-primary':'btn-secondary'}">Sócios</button>
        <button onclick="window._plTab('folha')" class="btn btn-sm ${innerTab==='folha'?'btn-primary':'btn-secondary'}">Folha de Pró-labore</button>
      </div>
      <div id="pl-content"></div>`;
    window._plTab = (t) => { innerTab = t; render(); };
    const bc = document.getElementById('pl-content');
    if (innerTab === 'socios') {
      const partners = await apiFetch('/api/dp/partners');
      bc.innerHTML = `
        <div class="flex justify-between items-center mb-3">
          <h3 class="font-bold text-slate-800 dark:text-slate-100">Quadro Societário</h3>
          <button onclick="window._plOpenModal(null)" class="btn btn-primary btn-sm">+ Novo Sócio</button>
        </div>
        ${card2(`<table class="table table-sm">
          <thead><tr><th>Nome</th><th>CPF</th><th>Cargo</th><th>% Sociedade</th><th>Pró-labore</th><th>Status</th><th>Ações</th></tr></thead>
          <tbody>${partners.map(p=>`<tr>
            <td>${p.nome}</td>
            <td style="font-family:monospace">${p.cpf}</td>
            <td>${p.cargo||'—'}</td>
            <td>${p.percentual_sociedade||0}%</td>
            <td class="font-semibold text-emerald-600">${fBRL2(p.salario_prolabore)}</td>
            <td><span class="badge ${p.ativo?'badge-success':'badge-secondary'}">${p.ativo?'Ativo':'Inativo'}</span></td>
            <td>
              <button onclick="window._plOpenModal(${JSON.stringify(p).replace(/"/g,'&quot;')})" class="btn btn-sm btn-secondary">Editar</button>
              <button onclick="window._plDeletePartner(${p.id})" class="btn btn-sm btn-danger">Excluir</button>
            </td>
          </tr>`).join('')}</tbody>
        </table>`)}
        <div id="pl-modal" class="modal-overlay" style="display:none">
          <div class="modal-box">
            <h3 id="pl-modal-title">Novo Sócio</h3>
            <input type="hidden" id="pl-id">
            <div class="form-row">
              <div class="form-group"><label>Nome Completo</label><input id="pl-nome" class="form-control"></div>
              <div class="form-group"><label>CPF</label><input id="pl-cpf" class="form-control" placeholder="000.000.000-00"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Cargo</label><input id="pl-cargo" class="form-control" value="Sócio-Administrador"></div>
              <div class="form-group"><label>% Sociedade</label><input id="pl-pct" type="number" step="0.01" class="form-control" placeholder="50"></div>
            </div>
            <div class="form-row">
              <div class="form-group"><label>Pró-labore (R$)</label><input id="pl-valor" type="number" step="0.01" class="form-control" placeholder="3000"></div>
              <div class="form-group"><label>Banco / Ag / CC</label><input id="pl-banco" class="form-control" placeholder="001 / 0001 / 12345-6"></div>
            </div>
            <div class="d-flex gap-2 justify-content-end mt-3">
              <button onclick="document.getElementById('pl-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
              <button onclick="window._plSavePartner()" class="btn btn-primary">Salvar</button>
            </div>
          </div>
        </div>`;
      window._plOpenModal = (p) => {
        document.getElementById('pl-modal-title').textContent = p ? 'Editar Sócio' : 'Novo Sócio';
        document.getElementById('pl-id').value = p ? p.id : '';
        document.getElementById('pl-nome').value = p ? p.nome : '';
        document.getElementById('pl-cpf').value = p ? p.cpf : '';
        document.getElementById('pl-cargo').value = p ? (p.cargo||'Sócio-Administrador') : 'Sócio-Administrador';
        document.getElementById('pl-pct').value = p ? p.percentual_sociedade : '';
        document.getElementById('pl-valor').value = p ? p.salario_prolabore : '';
        const bancoStr = p ? `${p.banco||''} / ${p.agencia||''} / ${p.conta||''}` : '';
        document.getElementById('pl-banco').value = bancoStr.trim()==='/ /'?'':bancoStr;
        document.getElementById('pl-modal').style.display = 'flex';
      };
      window._plSavePartner = async () => {
        const id = document.getElementById('pl-id').value;
        const banco_raw = document.getElementById('pl-banco').value.split('/');
        const body = {
          nome: document.getElementById('pl-nome').value.trim(),
          cpf: document.getElementById('pl-cpf').value.trim(),
          cargo: document.getElementById('pl-cargo').value.trim(),
          percentual_sociedade: parseFloat(document.getElementById('pl-pct').value||0),
          salario_prolabore: parseFloat(document.getElementById('pl-valor').value||0),
          banco: (banco_raw[0]||'').trim(),
          agencia: (banco_raw[1]||'').trim(),
          conta: (banco_raw[2]||'').trim(),
          ativo: 1,
        };
        try {
          if (id) await apiFetch(`/api/dp/partners/${id}`,{method:'PUT',body:JSON.stringify(body)});
          else await apiFetch('/api/dp/partners',{method:'POST',body:JSON.stringify(body)});
          document.getElementById('pl-modal').style.display = 'none';
          showToast('Salvo!','success'); await render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._plDeletePartner = async (id) => {
        if (!confirm('Excluir sócio?')) return;
        try { await apiFetch(`/api/dp/partners/${id}`,{method:'DELETE'}); showToast('Excluído.','success'); await render(); }
        catch(e) { showToast('Erro: '+e.message,'error'); }
      };
    } else {
      // Folha Pró-labore
      let runs = [];
      try { runs = await apiFetch(`/api/dp/prolabore?competencia=${comp}`); } catch {}
      const totBruto = runs.reduce((s,r)=>s+parseFloat(r.valor_bruto||0),0);
      const totInss = runs.reduce((s,r)=>s+parseFloat(r.inss_retido||0),0);
      const totIrrf = runs.reduce((s,r)=>s+parseFloat(r.irrf_retido||0),0);
      const totLiq = runs.reduce((s,r)=>s+parseFloat(r.valor_liquido||0),0);
      bc.innerHTML = `
        <div class="flex gap-3 items-center mb-4">
          <input type="month" value="${comp}" class="form-control" style="max-width:160px" onchange="comp=this.value;render()">
          <button onclick="window._plCalcular()" class="btn btn-primary btn-sm">Calcular</button>
          ${runs.length?`<button onclick="window._plContabil()" class="btn btn-secondary btn-sm">Partidas Contábeis</button>`:''}
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          ${kpiDP('Total Bruto',fBRL2(totBruto),'','banknote','text-blue-600')}
          ${kpiDP('INSS 11%',fBRL2(totInss),'','shield','text-orange-600')}
          ${kpiDP('IRRF',fBRL2(totIrrf),'','percent','text-red-600')}
          ${kpiDP('Total Líquido',fBRL2(totLiq),'','trending-up','text-emerald-600')}
        </div>
        ${runs.length ? card2(`<table class="table table-sm">
          <thead><tr><th>Sócio</th><th>Cargo</th><th>Bruto</th><th>INSS 11%</th><th>IRRF</th><th>Líquido</th><th>Recibo</th></tr></thead>
          <tbody>${runs.map(r=>`<tr>
            <td>${r.nome||''}</td>
            <td>${r.cargo||''}</td>
            <td>${fBRL2(r.valor_bruto)}</td>
            <td>${fBRL2(r.inss_retido)}</td>
            <td>${fBRL2(r.irrf_retido)}</td>
            <td class="font-semibold text-emerald-600">${fBRL2(r.valor_liquido)}</td>
            <td><button onclick="openAuthed('/api/dp/prolabore/${r.id}/recibo')" class="btn btn-sm btn-secondary">Recibo</button></td>
          </tr>`).join('')}</tbody>
        </table>`) : '<p class="text-muted text-sm">Clique em "Calcular" para gerar a folha de pró-labore.</p>'}
        <div id="pl-contabil-modal" class="modal-overlay" style="display:none">
          <div class="modal-box"><h3>Partidas Contábeis — Pró-labore ${comp}</h3><div id="pl-partidas-content"></div>
            <div class="d-flex justify-content-end mt-3"><button onclick="document.getElementById('pl-contabil-modal').style.display='none'" class="btn btn-secondary">Fechar</button></div>
          </div>
        </div>`;
      window._plCalcular = async () => {
        try {
          await apiFetch(`/api/dp/prolabore/calcular/${comp}`,{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}});
          showToast('Pró-labore calculado!','success'); await render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._plContabil = async () => {
        try {
          const data = await apiFetch(`/api/dp/prolabore/contabil/${comp}`);
          const html = `<table class="table table-sm"><thead><tr><th>Tipo</th><th>Conta</th><th>Descrição</th><th>Valor</th></tr></thead><tbody>
            ${data.partidas.map(p=>`<tr>
              <td><span class="badge ${p.tipo==='debito'?'badge-danger':'badge-success'}">${p.tipo.toUpperCase()}</span></td>
              <td style="font-family:monospace">${p.conta}</td>
              <td>${p.descricao}</td>
              <td>${fBRL2(p.valor)}</td>
            </tr>`).join('')}</tbody></table>`;
          document.getElementById('pl-partidas-content').innerHTML = html;
          document.getElementById('pl-contabil-modal').style.display = 'flex';
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
    }
    if (window.lucide) lucide.createIcons();
  };
  await render();
}

// ── EXAMES MÉDICOS (ASO) ──────────────────────────────────────────────────────
async function renderAso(el) {
  const render = async () => {
    const [exams, vencimentos] = await Promise.all([
      apiFetch('/api/dp/medical-exams').catch(()=>[]),
      apiFetch('/api/dp/medical-exams/vencimentos?dias=30').catch(()=>[]),
    ]);
    const hoje = new Date().toISOString().slice(0,10);
    const vencidos = exams.filter(e=>e.data_vencimento&&e.data_vencimento<hoje).length;
    const aVencer = vencimentos.filter(e=>e.dias_restantes>=0).length;
    const inaptos = exams.filter(e=>e.resultado==='inapto').length;
    const anoAtual = new Date().getFullYear();
    const totalAno = exams.filter(e=>(e.data_exame||'').startsWith(anoAtual)).length;
    el.innerHTML = `
      ${vencidos>0?`<div class="alert alert-danger mb-3">⚠️ ${vencidos} ASO(s) VENCIDO(S) — ação imediata necessária!</div>`:''}
      ${aVencer>0&&vencidos===0?`<div class="alert alert-warning mb-3">⚠️ ${aVencer} ASO(s) vencem nos próximos 30 dias.</div>`:''}
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        ${kpiDP('A Vencer (30d)',aVencer,'próximos 30 dias','clock','text-amber-600')}
        ${kpiDP('Vencidos',vencidos,'requer ação','alert-circle','text-red-600')}
        ${kpiDP('Inaptos',inaptos,'funcionários','x-circle','text-orange-600')}
        ${kpiDP('Total '+anoAtual,totalAno,'exames no ano','stethoscope','text-violet-600')}
      </div>
      <div class="flex justify-between items-center mb-3">
        <h3 class="font-bold text-slate-800 dark:text-slate-100">Exames Médicos (ASO)</h3>
        <button onclick="window._asoOpenModal(null)" class="btn btn-primary btn-sm">+ Novo ASO</button>
      </div>
      ${card2(`<table class="table table-sm">
        <thead><tr><th>Funcionário</th><th>Tipo</th><th>Data Exame</th><th>Vencimento</th><th>Dias</th><th>Resultado</th><th>Médico</th><th>Ações</th></tr></thead>
        <tbody>${exams.map(e=>{
          const dv = e.data_vencimento;
          const dias = dv ? Math.round((new Date(dv)-new Date(hoje))/(86400000)) : null;
          const badgeCls = dias===null?'badge-secondary':dias>30?'badge-success':dias>=0?'badge-warning':'badge-danger';
          const diasStr = dias===null?'—':dias<=0?'VENCIDO':dias+' dias';
          const resCls = e.resultado==='apto'?'badge-success':e.resultado==='inapto'?'badge-danger':'badge-warning';
          return `<tr>
            <td>${e.employee_name||''}</td>
            <td>${e.tipo}</td>
            <td>${fDate2(e.data_exame)}</td>
            <td>${dv?fDate2(dv):'—'}</td>
            <td><span class="badge ${badgeCls}">${diasStr}</span></td>
            <td><span class="badge ${resCls}">${e.resultado}</span></td>
            <td style="font-size:.8rem">${e.medico||'—'} ${e.crm_medico?'CRM '+e.crm_medico:''}</td>
            <td>
              <button onclick="window._asoOpenModal(${JSON.stringify(e).replace(/"/g,'&quot;')})" class="btn btn-sm btn-secondary">Editar</button>
              <button onclick="openAuthed('/api/dp/esocial/s2220/${e.id}','S-2220-${e.id}.xml')" class="btn btn-sm btn-secondary">S-2220</button>
              <button onclick="window._asoDelete(${e.id})" class="btn btn-sm btn-danger">×</button>
            </td>
          </tr>`;
        }).join('')}</tbody>
      </table>`)}
      <div id="aso-modal" class="modal-overlay" style="display:none">
        <div class="modal-box" style="max-width:600px">
          <h3 id="aso-modal-title">Novo ASO</h3>
          <input type="hidden" id="aso-id">
          <div class="form-row">
            <div class="form-group"><label>Funcionário</label>
              <select id="aso-emp" class="form-control">
                ${(dpEmployees||[]).map(e=>`<option value="${e.id}">${e.name}</option>`).join('')}
              </select>
            </div>
            <div class="form-group"><label>Tipo</label>
              <select id="aso-tipo" class="form-control">
                <option value="admissional">Admissional</option>
                <option value="periodico">Periódico</option>
                <option value="retorno_trabalho">Retorno ao Trabalho</option>
                <option value="mudanca_funcao">Mudança de Função</option>
                <option value="demissional">Demissional</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Data do Exame</label><input id="aso-data" type="date" class="form-control" value="${hoje}"></div>
            <div class="form-group"><label>Periodicidade (meses)</label><input id="aso-per" type="number" value="12" class="form-control"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Resultado</label>
              <select id="aso-res" class="form-control">
                <option value="apto">Apto</option>
                <option value="inapto">Inapto</option>
                <option value="apto_restricao">Apto com Restrições</option>
              </select>
            </div>
            <div class="form-group"><label>Restrições</label><input id="aso-rest" class="form-control" placeholder="Sem restrições"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Médico Responsável</label><input id="aso-med" class="form-control"></div>
            <div class="form-group"><label>CRM</label><input id="aso-crm" class="form-control" placeholder="123456"></div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>Clínica</label><input id="aso-clinica" class="form-control"></div>
            <div class="form-group"><label>Observações</label><input id="aso-obs" class="form-control"></div>
          </div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button onclick="document.getElementById('aso-modal').style.display='none'" class="btn btn-secondary">Cancelar</button>
            <button onclick="window._asoSave()" class="btn btn-primary">Salvar</button>
          </div>
        </div>
      </div>`;
    window._asoOpenModal = (e) => {
      document.getElementById('aso-modal-title').textContent = e ? 'Editar ASO' : 'Novo ASO';
      document.getElementById('aso-id').value = e ? e.id : '';
      document.getElementById('aso-emp').value = e ? e.employee_id : '';
      document.getElementById('aso-tipo').value = e ? e.tipo : 'admissional';
      document.getElementById('aso-data').value = e ? (e.data_exame||hoje) : hoje;
      document.getElementById('aso-per').value = e ? (e.periodicidade_meses||12) : 12;
      document.getElementById('aso-res').value = e ? (e.resultado||'apto') : 'apto';
      document.getElementById('aso-rest').value = e ? (e.restricoes||'') : '';
      document.getElementById('aso-med').value = e ? (e.medico||'') : '';
      document.getElementById('aso-crm').value = e ? (e.crm_medico||'') : '';
      document.getElementById('aso-clinica').value = e ? (e.clinica||'') : '';
      document.getElementById('aso-obs').value = e ? (e.observacoes||'') : '';
      document.getElementById('aso-modal').style.display = 'flex';
    };
    window._asoSave = async () => {
      const id = document.getElementById('aso-id').value;
      const body = {
        employee_id: parseInt(document.getElementById('aso-emp').value),
        tipo: document.getElementById('aso-tipo').value,
        data_exame: document.getElementById('aso-data').value,
        periodicidade_meses: parseInt(document.getElementById('aso-per').value||12),
        resultado: document.getElementById('aso-res').value,
        restricoes: document.getElementById('aso-rest').value,
        medico: document.getElementById('aso-med').value,
        crm_medico: document.getElementById('aso-crm').value,
        clinica: document.getElementById('aso-clinica').value,
        observacoes: document.getElementById('aso-obs').value,
      };
      try {
        if (id) await apiFetch(`/api/dp/medical-exams/${id}`,{method:'PUT',body:JSON.stringify(body)});
        else await apiFetch('/api/dp/medical-exams',{method:'POST',body:JSON.stringify(body)});
        document.getElementById('aso-modal').style.display = 'none';
        showToast('ASO salvo!','success'); await render();
      } catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    window._asoDelete = async (id) => {
      if (!confirm('Excluir exame?')) return;
      try { await apiFetch(`/api/dp/medical-exams/${id}`,{method:'DELETE'}); showToast('Excluído.','success'); await render(); }
      catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    if (window.lucide) lucide.createIcons();
  };
  await render();
}


// ── PPP / LTCAT ──────────────────────────────────────────────────
async function renderPpp(el) {
  let envs = [], agents = [], ltcats = [], ppps = [];
  try {
    [envs, agents, ltcats, ppps] = await Promise.all([
      apiFetch('/api/dp/work-environments'),
      apiFetch('/api/dp/risk-agents'),
      apiFetch('/api/dp/ltcat'),
      apiFetch('/api/dp/ppp'),
    ]);
  } catch(e) { el.innerHTML = `<p class="text-red-500">Erro: ${e.message}</p>`; return; }

  let pppTab = 'ambientes';
  const render = () => {
    const tabs2 = [['ambientes','Ambientes'],['agentes','Agentes de Risco'],['ltcat','LTCAT'],['ppps','PPP Funcionários']];
    el.innerHTML = `
      <div class="flex gap-2 mb-4 flex-wrap">
        ${tabs2.map(([id,lbl]) => `<button onclick="window._pppTab('${id}')"
          class="px-3 py-1.5 rounded-xl text-xs font-semibold transition ${pppTab===id ? 'bg-violet-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">${lbl}</button>`).join('')}
      </div>
      <div id="ppp-body"></div>
      <div id="ppp-modal" class="modal-overlay" style="display:none"><div class="modal-box" id="ppp-modal-inner"></div></div>`;

    window._pppTab = (t) => { pppTab = t; render(); };
    const body = document.getElementById('ppp-body');

    if (pppTab === 'ambientes') {
      body.innerHTML = `
        <div class="flex justify-between mb-3"><h3 class="font-bold text-slate-800 dark:text-slate-100">Ambientes de Trabalho</h3>
          <button onclick="window._pppEnvModal()" class="btn btn-primary text-xs">+ Novo Ambiente</button></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Nome</th><th>Local</th><th>Setor</th><th>Atividade</th><th>Ações</th></tr></thead>
        <tbody>${envs.length ? envs.map(e => `<tr><td>${e.nome}</td><td>${e.local_trabalho||'—'}</td><td>${e.setor||'—'}</td><td>${e.atividade_economica||'—'}</td>
          <td><button onclick="window._pppEnvDel(${e.id},'${(e.nome||'').replace(/'/g,"\\'")}')"\n            class="btn btn-sm btn-danger">Excluir</button></td></tr>`).join('') : '<tr><td colspan="5" class="text-center text-muted">Nenhum ambiente cadastrado.</td></tr>'}</tbody></table></div>`;

      window._pppEnvModal = (env={}) => {
        document.getElementById('ppp-modal-inner').innerHTML = `
          <h3 class="${env.id ? 'Editar' : 'Novo'} Ambiente">Ambiente de Trabalho</h3>
          <div class="form-row"><div class="form-group"><label>Nome *</label><input id="penv-nome" class="${inputCls}" value="${env.nome||''}"></div>
          <div class="form-group"><label>Local</label><input id="penv-local" class="${inputCls}" value="${env.local_trabalho||''}"></div></div>
          <div class="form-row"><div class="form-group"><label>Setor</label><input id="penv-setor" class="${inputCls}" value="${env.setor||''}"></div>
          <div class="form-group"><label>Atividade Econômica</label><input id="penv-ativ" class="${inputCls}" value="${env.atividade_economica||''}"></div></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('ppp-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._pppEnvSave(${env.id||0})">Salvar</button></div>`;
        document.getElementById('ppp-modal').style.display = 'flex';
      };
      window._pppEnvSave = async (id) => {
        const b = { nome: document.getElementById('penv-nome').value, local_trabalho: document.getElementById('penv-local').value, setor: document.getElementById('penv-setor').value, atividade_economica: document.getElementById('penv-ativ').value };
        try {
          if (id) await apiFetch(`/api/dp/work-environments/${id}`, {method:'PUT',body:JSON.stringify(b)});
          else { const r = await apiFetch('/api/dp/work-environments', {method:'POST',body:JSON.stringify(b)}); envs.push(r); }
          document.getElementById('ppp-modal').style.display = 'none';
          envs = await apiFetch('/api/dp/work-environments'); showToast('Salvo!','success'); render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._pppEnvDel = async (id, nome) => {
        if (!confirm(`Excluir "${nome}"?`)) return;
        await apiFetch(`/api/dp/work-environments/${id}`, {method:'DELETE'});
        envs = envs.filter(e => e.id !== id); render();
      };

    } else if (pppTab === 'agentes') {
      const tipoColors = {fisico:'badge-warning',quimico:'badge-danger',biologico:'badge-success',ergonomico:'badge-info',mecanico:'badge-secondary'};
      body.innerHTML = `
        <div class="flex justify-between mb-3"><h3 class="font-bold text-slate-800 dark:text-slate-100">Agentes de Risco</h3>
          <button onclick="window._pppAgtModal()" class="btn btn-primary text-xs">+ Novo Agente</button></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Nome</th><th>Tipo</th><th>Ambiente</th><th>NR-15</th><th>Intensidade</th><th>EPI</th><th>Cód. eSocial</th><th>Ações</th></tr></thead>
        <tbody>${agents.length ? agents.map(a => `<tr>
          <td>${a.nome}</td>
          <td><span class="badge ${tipoColors[a.tipo]||'badge-secondary'}">${a.tipo}</span></td>
          <td>${a.ambiente_nome||'—'}</td><td>${a.nr15_codigo||'—'}</td><td>${a.intensidade||'—'}</td><td>${a.epi||'—'}</td><td>${a.esocial_cod_agente||'—'}</td>
          <td><button onclick="window._pppAgtDel(${a.id},'${(a.nome||'').replace(/'/g,"\\'")}')"\n            class="btn btn-sm btn-danger">Excluir</button></td></tr>`).join('') : '<tr><td colspan="8" class="text-center text-muted">Nenhum agente cadastrado.</td></tr>'}</tbody></table></div>`;

      window._pppAgtModal = () => {
        document.getElementById('ppp-modal-inner').innerHTML = `
          <h3>Novo Agente de Risco</h3>
          <div class="form-row">
            <div class="form-group"><label>Ambiente</label><select id="pagt-env" class="${inputCls}"><option value="">— selecione —</option>${envs.map(e => `<option value="${e.id}">${e.nome}</option>`).join('')}</select></div>
            <div class="form-group"><label>Tipo</label><select id="pagt-tipo" class="${inputCls}"><option value="fisico">Físico</option><option value="quimico">Químico</option><option value="biologico">Biológico</option><option value="ergonomico">Ergonômico</option><option value="mecanico">Mecânico</option></select></div>
          </div>
          <div class="form-row"><div class="form-group"><label>Nome *</label><input id="pagt-nome" class="${inputCls}" placeholder="Ex: Ruído acima de 85dB"></div>
          <div class="form-group"><label>Código NR-15</label><input id="pagt-nr15" class="${inputCls}" placeholder="Ex: 15.1.A"></div></div>
          <div class="form-row"><div class="form-group"><label>Intensidade</label><input id="pagt-int" class="${inputCls}" placeholder="Ex: 92 dB(A)"></div>
          <div class="form-group"><label>EPI Utilizado</label><input id="pagt-epi" class="${inputCls}" placeholder="Ex: Protetor auricular CA-123"></div></div>
          <div class="form-row"><div class="form-group"><label>Código eSocial</label><input id="pagt-esoc" class="${inputCls}" placeholder="Ex: 01.01.001"></div>
          <div class="form-group"><label>EPC</label><input id="pagt-epc" class="${inputCls}"></div></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('ppp-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._pppAgtSave()">Salvar</button></div>`;
        document.getElementById('ppp-modal').style.display = 'flex';
      };
      window._pppAgtSave = async () => {
        const b = { work_environment_id: document.getElementById('pagt-env').value||null, tipo: document.getElementById('pagt-tipo').value, nome: document.getElementById('pagt-nome').value, nr15_codigo: document.getElementById('pagt-nr15').value, intensidade: document.getElementById('pagt-int').value, epi: document.getElementById('pagt-epi').value, esocial_cod_agente: document.getElementById('pagt-esoc').value, epc: document.getElementById('pagt-epc').value };
        try { await apiFetch('/api/dp/risk-agents',{method:'POST',body:JSON.stringify(b)}); agents = await apiFetch('/api/dp/risk-agents'); document.getElementById('ppp-modal').style.display='none'; showToast('Salvo!','success'); render(); } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._pppAgtDel = async (id, nome) => {
        if (!confirm(`Excluir "${nome}"?`)) return;
        await apiFetch(`/api/dp/risk-agents/${id}`,{method:'DELETE'}); agents = agents.filter(a=>a.id!==id); render();
      };

    } else if (pppTab === 'ltcat') {
      const concl = {sem_exposicao:'badge-success',com_exposicao:'badge-danger',em_analise:'badge-warning'};
      body.innerHTML = `
        <div class="flex justify-between mb-3"><h3 class="font-bold text-slate-800 dark:text-slate-100">Laudos LTCAT</h3>
          <button onclick="window._ltcatModal()" class="btn btn-primary text-xs">+ Novo LTCAT</button></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Ambiente</th><th>Data Emissão</th><th>Vencimento</th><th>Responsável</th><th>Conselho</th><th>Conclusão</th><th>Ações</th></tr></thead>
        <tbody>${ltcats.length ? ltcats.map(l => {
          const dv = l.dias_vencimento; const badge = dv==null?'':'badge-'+(dv<0?'danger':dv<30?'warning':'success');
          return `<tr>
          <td>${l.ambiente_nome||'—'}</td><td>${l.data_emissao||'—'}</td>
          <td>${l.data_vencimento ? `<span class="badge ${badge}">${l.data_vencimento} (${dv}d)</span>` : '—'}</td>
          <td>${l.responsavel_tecnico}</td><td>${l.conselho_profissional||'—'}</td>
          <td><span class="badge ${concl[l.conclusao]||'badge-secondary'}">${l.conclusao}</span></td>
          <td>
            <button onclick="openAuthed('/api/dp/esocial/s2240/${l.work_environment_id||0}','S-2240-${l.id}.xml')" class="btn btn-sm btn-secondary">S-2240</button>
            <button onclick="window._ltcatDel(${l.id})" class="btn btn-sm btn-danger">Del</button>
          </td></tr>`;}).join('') : '<tr><td colspan="7" class="text-center text-muted">Nenhum LTCAT cadastrado.</td></tr>'}</tbody></table></div>`;

      window._ltcatModal = () => {
        document.getElementById('ppp-modal-inner').innerHTML = `
          <h3>Novo Laudo LTCAT</h3>
          <div class="form-row"><div class="form-group"><label>Ambiente</label><select id="ltc-env" class="${inputCls}"><option value="">— selecione —</option>${envs.map(e=>`<option value="${e.id}">${e.nome}</option>`).join('')}</select></div>
          <div class="form-group"><label>Data Emissão *</label><input type="date" id="ltc-emissao" class="${inputCls}"></div></div>
          <div class="form-row"><div class="form-group"><label>Data Vencimento</label><input type="date" id="ltc-venc" class="${inputCls}"></div>
          <div class="form-group"><label>Responsável Técnico *</label><input id="ltc-resp" class="${inputCls}"></div></div>
          <div class="form-row"><div class="form-group"><label>Conselho Profissional</label><input id="ltc-cons" class="${inputCls}" placeholder="Ex: CREA/SP"></div>
          <div class="form-group"><label>Nº Registro</label><input id="ltc-reg" class="${inputCls}"></div></div>
          <div class="form-group"><label>Conclusão</label><select id="ltc-concl" class="${inputCls}"><option value="sem_exposicao">Sem Exposição</option><option value="com_exposicao">Com Exposição</option><option value="em_analise">Em Análise</option></select></div>
          <div class="form-group"><label>Observações</label><textarea id="ltc-obs" class="${inputCls}" rows="2"></textarea></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('ppp-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._ltcatSave()">Salvar</button></div>`;
        document.getElementById('ppp-modal').style.display = 'flex';
      };
      window._ltcatSave = async () => {
        const b = { work_environment_id: document.getElementById('ltc-env').value||null, data_emissao: document.getElementById('ltc-emissao').value, data_vencimento: document.getElementById('ltc-venc').value||null, responsavel_tecnico: document.getElementById('ltc-resp').value, conselho_profissional: document.getElementById('ltc-cons').value, registro: document.getElementById('ltc-reg').value, conclusao: document.getElementById('ltc-concl').value, observacoes: document.getElementById('ltc-obs').value };
        try { await apiFetch('/api/dp/ltcat',{method:'POST',body:JSON.stringify(b)}); ltcats = await apiFetch('/api/dp/ltcat'); document.getElementById('ppp-modal').style.display='none'; showToast('LTCAT salvo!','success'); render(); } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._ltcatDel = async (id) => {
        if (!confirm('Excluir LTCAT?')) return;
        await apiFetch(`/api/dp/ltcat/${id}`,{method:'DELETE'}); ltcats = ltcats.filter(l=>l.id!==id); render();
      };

    } else if (pppTab === 'ppps') {
      const empOpts = dpEmployees.map(e=>`<option value="${e.id}">${e.name}</option>`).join('');
      body.innerHTML = `
        <div class="flex justify-between mb-3"><h3 class="font-bold text-slate-800 dark:text-slate-100">PPP dos Funcionários</h3>
          <button onclick="window._pppRecModal()" class="btn btn-primary text-xs">+ Vincular Ambiente</button></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Funcionário</th><th>CPF</th><th>Ambiente</th><th>Início Exp.</th><th>Fim Exp.</th><th>Responsável</th><th>Ações</th></tr></thead>
        <tbody>${ppps.length ? ppps.map(p=>`<tr>
          <td>${p.employee_name}</td><td class="font-mono text-xs">${p.cpf||'—'}</td><td>${p.ambiente_nome||'—'}</td>
          <td>${p.data_inicio_exposicao||'—'}</td><td>${p.data_fim_exposicao||'ativo'}</td><td>${p.responsavel_tecnico||'—'}</td>
          <td>
            <button onclick="openAuthed('/api/dp/ppp/${p.id}/documento')" class="btn btn-sm btn-secondary">PPP</button>
            <button onclick="window._pppRecDel(${p.id})" class="btn btn-sm btn-danger">Del</button>
          </td></tr>`).join('') : '<tr><td colspan="7" class="text-center text-muted">Nenhum PPP registrado.</td></tr>'}</tbody></table></div>`;

      window._pppRecModal = () => {
        document.getElementById('ppp-modal-inner').innerHTML = `
          <h3>Vincular Funcionário a Ambiente</h3>
          <div class="form-group"><label>Funcionário *</label><select id="prec-emp" class="${inputCls}"><option value="">— selecione —</option>${empOpts}</select></div>
          <div class="form-group"><label>Ambiente de Trabalho *</label><select id="prec-env" class="${inputCls}"><option value="">— selecione —</option>${envs.map(e=>`<option value="${e.id}">${e.nome}</option>`).join('')}</select></div>
          <div class="form-row"><div class="form-group"><label>Início Exposição</label><input type="date" id="prec-ini" class="${inputCls}"></div>
          <div class="form-group"><label>Fim Exposição</label><input type="date" id="prec-fim" class="${inputCls}"></div></div>
          <div class="form-row"><div class="form-group"><label>Responsável Técnico</label><input id="prec-resp" class="${inputCls}"></div>
          <div class="form-group"><label>Nº Registro</label><input id="prec-reg" class="${inputCls}"></div></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('ppp-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._pppRecSave()">Salvar</button></div>`;
        document.getElementById('ppp-modal').style.display = 'flex';
      };
      window._pppRecSave = async () => {
        const b = { employee_id: +document.getElementById('prec-emp').value, work_environment_id: document.getElementById('prec-env').value||null, data_inicio_exposicao: document.getElementById('prec-ini').value, data_fim_exposicao: document.getElementById('prec-fim').value, responsavel_tecnico: document.getElementById('prec-resp').value, registro_profissional: document.getElementById('prec-reg').value };
        try { await apiFetch('/api/dp/ppp',{method:'POST',body:JSON.stringify(b)}); ppps = await apiFetch('/api/dp/ppp'); document.getElementById('ppp-modal').style.display='none'; showToast('Salvo!','success'); render(); } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._pppRecDel = async (id) => {
        if (!confirm('Excluir registro PPP?')) return;
        await apiFetch(`/api/dp/ppp/${id}`,{method:'DELETE'}); ppps = ppps.filter(p=>p.id!==id); render();
      };
    }
    if (window.lucide) lucide.createIcons();
  };
  render();
}


// ── INTEGRAÇÃO CONTÁBIL ──────────────────────────────────────────
async function renderContabilDp(el) {
  let cfg = {}, entries = [];
  const mes = new Date().toISOString().slice(0,7);
  let selComp = mes;
  try { cfg = await apiFetch('/api/dp/accounting-config'); } catch {}

  let subTab = 'contas';
  const render = async () => {
    el.innerHTML = `
      <div class="flex gap-2 mb-4">
        <button onclick="window._cdpTab('contas')" class="px-3 py-1.5 rounded-xl text-xs font-semibold ${subTab==='contas'?'bg-violet-600 text-white':'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">Plano de Contas</button>
        <button onclick="window._cdpTab('lancamentos')" class="px-3 py-1.5 rounded-xl text-xs font-semibold ${subTab==='lancamentos'?'bg-violet-600 text-white':'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">Lançamentos</button>
      </div>
      <div id="cdp-body"></div>`;
    window._cdpTab = (t) => { subTab = t; render(); };
    const body = document.getElementById('cdp-body');

    if (subTab === 'contas') {
      const flds = [
        ['conta_salarios_bruto','Desp. Salários Brutos (D)'],['conta_salarios_pagar','Salários a Pagar (C)'],
        ['conta_inss_empregado','INSS Empregado a Recolher (C)'],['conta_inss_patronal','INSS Patronal a Recolher (C)'],
        ['conta_fgts_provisao','FGTS a Recolher (C)'],['conta_irrf','IRRF a Recolher (C)'],
        ['conta_ferias_provisao','Provisão Férias (C)'],['conta_decimo_provisao','Provisão 13º Sal (C)'],
        ['conta_prolabore','Pró-labore (D)'],['conta_banco','Caixa/Banco (C)'],
      ];
      body.innerHTML = `
        <div class="card"><div class="card-body">
          <h4 class="font-bold mb-4 text-slate-800 dark:text-slate-100">Configuração das Contas Contábeis</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            ${flds.map(([k,lbl]) => `<div class="form-group"><label>${lbl}</label><input id="cfg-${k}" class="${inputCls}" value="${cfg[k]||''}"></div>`).join('')}
          </div>
          <div class="d-flex justify-content-end mt-4">
            <button onclick="window._cdpSaveCfg()" class="btn btn-primary">Salvar Configuração</button>
          </div>
        </div></div>`;
      window._cdpSaveCfg = async () => {
        const b = {}; flds.forEach(([k]) => { b[k] = document.getElementById('cfg-'+k).value; });
        try { await apiFetch('/api/dp/accounting-config',{method:'PUT',body:JSON.stringify(b)}); cfg = b; showToast('Configuração salva!','success'); } catch(e) { showToast('Erro: '+e.message,'error'); }
      };

    } else {
      entries = await apiFetch(`/api/dp/accounting/entries?competencia=${selComp}`).catch(() => []);
      const totalD = entries.reduce((s,r) => s + (r.debito_valor||0), 0);
      const totalC = entries.reduce((s,r) => s + (r.credito_valor||0), 0);
      body.innerHTML = `
        <div class="flex gap-3 mb-4 flex-wrap items-end">
          <div class="form-group mb-0"><label>Competência</label><input type="month" id="cdp-comp" class="${inputCls}" value="${selComp}"></div>
          <button onclick="window._cdpGerar()" class="btn btn-primary">Gerar Lançamentos</button>
          <button onclick="window._cdpExportar()" class="btn btn-secondary">Exportar CSV</button>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          ${kpiDP('Total Débito', fBRL2(totalD), 'soma lançamentos D', 'arrow-down-left', 'text-rose-500')}
          ${kpiDP('Total Crédito', fBRL2(totalC), 'soma lançamentos C', 'arrow-up-right', 'text-emerald-500')}
          ${kpiDP('Nº Partidas', entries.length, 'lançamentos gerados', 'rows-3', 'text-violet-500')}
          ${kpiDP('Status', entries.filter(e=>e.status==='exportado').length > 0 ? 'Exportado' : entries.length > 0 ? 'Pendente' : '—', '', 'check-circle', 'text-blue-500')}
        </div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Data</th><th>Histórico</th><th>Débito</th><th>Valor D</th><th>Crédito</th><th>Valor C</th><th>Status</th></tr></thead>
        <tbody>${entries.length ? entries.map(e => `<tr>
          <td class="text-xs">${e.data_lancamento}</td><td class="text-xs">${e.historico}</td>
          <td class="font-mono text-xs">${e.debito_conta}</td><td class="text-xs text-rose-500">${fBRL2(e.debito_valor)}</td>
          <td class="font-mono text-xs">${e.credito_conta}</td><td class="text-xs text-emerald-500">${fBRL2(e.credito_valor)}</td>
          <td><span class="badge ${e.status==='exportado'?'badge-success':'badge-secondary'}">${e.status}</span></td>
        </tr>`).join('') : '<tr><td colspan="7" class="text-center text-muted">Nenhum lançamento. Clique em "Gerar Lançamentos".</td></tr>'}</tbody></table></div>`;

      window._cdpGerar = async () => {
        selComp = document.getElementById('cdp-comp').value;
        try { entries = await apiFetch(`/api/dp/accounting/gerar/${selComp}`,{method:'POST'}); showToast(`${entries.length} lançamentos gerados!`,'success'); render(); } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._cdpExportar = async () => {
        selComp = document.getElementById('cdp-comp').value;
        openAuthed(`/api/dp/accounting/exportar/${selComp}`, `contabil-${selComp}.csv`);
      };
    }
    if (window.lucide) lucide.createIcons();
  };
  await render();
}


// ── ESTAGIÁRIOS & APRENDIZES ─────────────────────────────────────
async function renderEstagiarios(el) {
  let interns = [], apprentices = [], cota = {};
  try {
    [interns, apprentices, cota] = await Promise.all([
      apiFetch('/api/dp/interns'),
      apiFetch('/api/dp/apprentices'),
      apiFetch('/api/dp/apprentices/cota'),
    ]);
  } catch(e) {}

  let subTab = 'estagiarios';
  const render = () => {
    const tabs2 = [['estagiarios','Estagiários'],['aprendizes','Aprendizes'],['cota','Controle de Cota']];
    el.innerHTML = `
      <div class="flex gap-2 mb-4 flex-wrap">
        ${tabs2.map(([id,lbl]) => `<button onclick="window._estTab('${id}')" class="px-3 py-1.5 rounded-xl text-xs font-semibold ${subTab===id?'bg-violet-600 text-white':'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">${lbl}</button>`).join('')}
      </div>
      <div id="est-body"></div>
      <div id="est-modal" class="modal-overlay" style="display:none"><div class="modal-box" id="est-modal-inner"></div></div>`;
    window._estTab = (t) => { subTab = t; render(); };
    const body = document.getElementById('est-body');

    if (subTab === 'estagiarios') {
      const ativos = interns.filter(i=>i.status==='ativo').length;
      const enc30 = interns.filter(i=>i.dias_restantes!=null && i.dias_restantes>=0 && i.dias_restantes<=30).length;
      const sup = interns.filter(i=>i.nivel==='superior').length;
      const med = interns.filter(i=>i.nivel!=='superior').length;
      body.innerHTML = `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          ${kpiDP('Ativos', ativos, '', 'users', 'text-emerald-500')}
          ${kpiDP('Encerrando (30d)', enc30, '', 'alert-triangle', 'text-amber-500')}
          ${kpiDP('Nível Superior', sup, '', 'graduation-cap', 'text-violet-500')}
          ${kpiDP('Médio / Técnico', med, '', 'book', 'text-blue-500')}
        </div>
        <div class="flex justify-between mb-3"><h3 class="font-bold text-slate-800 dark:text-slate-100">Estagiários</h3>
          <button onclick="window._internModal()" class="btn btn-primary text-xs">+ Novo Estágio</button></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Nome</th><th>CPF</th><th>Instituição</th><th>Curso</th><th>Período</th><th>Bolsa</th><th>VT</th><th>Status</th><th>Ações</th></tr></thead>
        <tbody>${interns.length ? interns.map(i => {
          const dr = i.dias_restantes; const badge = dr==null?'':dr<0?'badge-secondary':dr<=30?'badge-warning':'badge-success';
          return `<tr>
          <td>${i.nome}</td><td class="font-mono text-xs">${i.cpf||'—'}</td><td>${i.instituicao}</td><td>${i.curso||'—'}</td>
          <td>${i.data_inicio} → ${i.data_fim} ${dr!=null?`<span class="badge ${badge} ml-1">${dr}d</span>`:''}
          </td><td>${fBRL2(i.bolsa_auxilio)}</td><td>${fBRL2(i.vale_transporte)}</td>
          <td><span class="badge ${i.status==='ativo'?'badge-success':'badge-secondary'}">${i.status}</span></td>
          <td>
            <button onclick="openAuthed('/api/dp/interns/termo/${i.id}')" class="btn btn-sm btn-secondary">TCE</button>
            <button onclick="window._internDel(${i.id},'${(i.nome||'').replace(/'/g,"\\'")}')"\n              class="btn btn-sm btn-danger">Del</button>
          </td></tr>`;}).join('') : '<tr><td colspan="9" class="text-center text-muted">Nenhum estagiário.</td></tr>'}</tbody></table></div>`;

      window._internModal = (i={}) => {
        document.getElementById('est-modal-inner').innerHTML = `
          <h3>Cadastro de Estagiário</h3>
          <div class="form-row"><div class="form-group"><label>Nome *</label><input id="int-nome" class="${inputCls}" value="${i.nome||''}"></div>
          <div class="form-group"><label>CPF</label><input id="int-cpf" class="${inputCls}" value="${i.cpf||''}"></div></div>
          <div class="form-row"><div class="form-group"><label>Instituição *</label><input id="int-inst" class="${inputCls}" value="${i.instituicao||''}"></div>
          <div class="form-group"><label>Curso</label><input id="int-curso" class="${inputCls}" value="${i.curso||''}"></div></div>
          <div class="form-row"><div class="form-group"><label>Nível</label><select id="int-nivel" class="${inputCls}"><option value="superior" ${i.nivel==='superior'?'selected':''}>Superior</option><option value="medio" ${i.nivel==='medio'?'selected':''}>Médio/Técnico</option></select></div>
          <div class="form-group"><label>Carga Horária Semanal</label><input type="number" id="int-ch" class="${inputCls}" value="${i.carga_horaria_semanal||20}"></div></div>
          <div class="form-row"><div class="form-group"><label>Início *</label><input type="date" id="int-ini" class="${inputCls}" value="${i.data_inicio||''}"></div>
          <div class="form-group"><label>Fim *</label><input type="date" id="int-fim" class="${inputCls}" value="${i.data_fim||''}"></div></div>
          <div class="form-row"><div class="form-group"><label>Bolsa-Auxílio R$</label><input type="number" id="int-bolsa" class="${inputCls}" value="${i.bolsa_auxilio||0}"></div>
          <div class="form-group"><label>Vale-Transporte R$</label><input type="number" id="int-vt" class="${inputCls}" value="${i.vale_transporte||0}"></div></div>
          <div class="form-row"><div class="form-group"><label>Supervisor</label><input id="int-sup" class="${inputCls}" value="${i.supervisor_nome||''}"></div>
          <div class="form-group"><label>Agente de Integração</label><input id="int-ag" class="${inputCls}" value="${i.agente_integracao||''}"></div></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('est-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._internSave(${i.id||0})">Salvar</button></div>`;
        document.getElementById('est-modal').style.display = 'flex';
      };
      window._internSave = async (id) => {
        const b = { nome: document.getElementById('int-nome').value, cpf: document.getElementById('int-cpf').value, instituicao: document.getElementById('int-inst').value, curso: document.getElementById('int-curso').value, nivel: document.getElementById('int-nivel').value, carga_horaria_semanal: +document.getElementById('int-ch').value, data_inicio: document.getElementById('int-ini').value, data_fim: document.getElementById('int-fim').value, bolsa_auxilio: +document.getElementById('int-bolsa').value, vale_transporte: +document.getElementById('int-vt').value, supervisor_nome: document.getElementById('int-sup').value, agente_integracao: document.getElementById('int-ag').value };
        try {
          if (id) await apiFetch(`/api/dp/interns/${id}`,{method:'PUT',body:JSON.stringify(b)});
          else await apiFetch('/api/dp/interns',{method:'POST',body:JSON.stringify(b)});
          interns = await apiFetch('/api/dp/interns'); document.getElementById('est-modal').style.display='none'; showToast('Salvo!','success'); render();
        } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._internDel = async (id, nome) => {
        if (!confirm(`Excluir "${nome}"?`)) return;
        await apiFetch(`/api/dp/interns/${id}`,{method:'DELETE'}); interns = interns.filter(i=>i.id!==id); render();
      };

    } else if (subTab === 'aprendizes') {
      body.innerHTML = `
        <div class="flex justify-between mb-3"><h3 class="font-bold text-slate-800 dark:text-slate-100">Aprendizes</h3>
          <button onclick="window._appModal()" class="btn btn-primary text-xs">+ Novo Aprendiz</button></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Funcionário</th><th>CPF</th><th>Entidade Qualificadora</th><th>Programa</th><th>Período</th><th>Ações</th></tr></thead>
        <tbody>${apprentices.length ? apprentices.map(a=>`<tr>
          <td>${a.employee_name}</td><td class="font-mono text-xs">${a.cpf||'—'}</td>
          <td>${a.entidade_qualificadora||'—'}</td><td>${a.programa||'—'}</td>
          <td>${a.data_inicio} → ${a.data_fim}</td>
          <td><button onclick="window._appDel(${a.id})" class="btn btn-sm btn-danger">Del</button></td></tr>`).join('') : '<tr><td colspan="6" class="text-center text-muted">Nenhum aprendiz.</td></tr>'}</tbody></table></div>`;

      window._appModal = () => {
        document.getElementById('est-modal-inner').innerHTML = `
          <h3>Novo Aprendiz</h3>
          <div class="form-group"><label>Funcionário *</label><select id="app-emp" class="${inputCls}"><option value="">— selecione —</option>${dpEmployees.map(e=>`<option value="${e.id}">${e.name}</option>`).join('')}</select></div>
          <div class="form-row"><div class="form-group"><label>Início *</label><input type="date" id="app-ini" class="${inputCls}"></div>
          <div class="form-group"><label>Fim *</label><input type="date" id="app-fim" class="${inputCls}"></div></div>
          <div class="form-row"><div class="form-group"><label>Entidade Qualificadora</label><input id="app-ent" class="${inputCls}" placeholder="Ex: SENAI, SENAC"></div>
          <div class="form-group"><label>Programa</label><input id="app-prog" class="${inputCls}"></div></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('est-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._appSave()">Salvar</button></div>`;
        document.getElementById('est-modal').style.display = 'flex';
      };
      window._appSave = async () => {
        const b = { employee_id: +document.getElementById('app-emp').value, data_inicio: document.getElementById('app-ini').value, data_fim: document.getElementById('app-fim').value, entidade_qualificadora: document.getElementById('app-ent').value, programa: document.getElementById('app-prog').value };
        try { await apiFetch('/api/dp/apprentices',{method:'POST',body:JSON.stringify(b)}); apprentices = await apiFetch('/api/dp/apprentices'); document.getElementById('est-modal').style.display='none'; showToast('Aprendiz cadastrado!','success'); render(); } catch(e) { showToast('Erro: '+e.message,'error'); }
      };
      window._appDel = async (id) => {
        if (!confirm('Excluir aprendiz?')) return;
        await apiFetch(`/api/dp/apprentices/${id}`,{method:'DELETE'}); apprentices = apprentices.filter(a=>a.id!==id); render();
      };

    } else {
      const pct = cota.total_empregados > 0 ? Math.round(cota.aprendizes_ativos / cota.total_empregados * 100) : 0;
      const minPct = cota.total_empregados > 0 ? Math.round(cota.cota_minima / cota.total_empregados * 100) : 5;
      const maxPct = cota.total_empregados > 0 ? Math.round(cota.cota_maxima / cota.total_empregados * 100) : 15;
      const color = cota.situacao === 'dentro' ? 'text-emerald-600' : cota.situacao === 'abaixo' ? 'text-red-500' : 'text-amber-500';
      body.innerHTML = `
        <div class="card max-w-lg mx-auto"><div class="card-body">
          <h3 class="font-bold text-center text-slate-800 dark:text-slate-100 mb-4">Controle de Cota de Aprendizes — Lei 10.097/2000</h3>
          <div class="grid grid-cols-2 gap-3 mb-4">
            ${kpiDP('Total Empregados', cota.total_empregados||0, 'com vínculo CLT ativo', 'users', 'text-slate-500')}
            ${kpiDP('Aprendizes Ativos', cota.aprendizes_ativos||0, 'cadastrados', 'graduation-cap', 'text-violet-500')}
            ${kpiDP('Cota Mínima (5%)', cota.cota_minima||0, 'mínimo legal', 'arrow-down', 'text-blue-500')}
            ${kpiDP('Cota Máxima (15%)', cota.cota_maxima||0, 'máximo legal', 'arrow-up', 'text-blue-500')}
          </div>
          <div class="text-center mb-4">
            <span class="text-2xl font-bold ${color}">${cota.situacao === 'dentro' ? '✓ Dentro da cota' : cota.situacao === 'abaixo' ? '⚠ Abaixo da cota mínima' : '⚠ Acima da cota máxima'}</span>
          </div>
          <div class="relative h-6 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden mb-2">
            <div class="h-full bg-violet-500 rounded-full transition-all" style="width:${Math.min(100,pct)}%"></div>
            <div class="absolute top-0 bottom-0 border-l-2 border-blue-400" style="left:${minPct}%" title="Mínimo ${minPct}%"></div>
            <div class="absolute top-0 bottom-0 border-l-2 border-red-400" style="left:${maxPct}%" title="Máximo ${maxPct}%"></div>
          </div>
          <p class="text-xs text-center text-muted">${pct}% do quadro | Faixa permitida: ${minPct}% — ${maxPct}%</p>
          ${cota.situacao === 'abaixo' ? `<div class="alert alert-danger mt-3">Empresa abaixo da cota mínima! Deve contratar mais ${(cota.cota_minima||0) - (cota.aprendizes_ativos||0)} aprendiz(es).</div>` : ''}
        </div></div>`;
    }
    if (window.lucide) lucide.createIcons();
  };
  render();
}


// ── EXTRATO FGTS ──────────────────────────────────────────────────
async function renderFgts(el) {
  let selEmp = dpEmployees[0]?.id || 0;
  let selAno = new Date().getFullYear();
  let extrato = { registros: [], saldo_total: 0, employee_name: '' };
  let resumo = {};

  const load = async () => {
    if (selEmp) extrato = await apiFetch(`/api/dp/fgts/extrato/${selEmp}?ano=${selAno}`).catch(() => ({ registros: [], saldo_total: 0, employee_name: '' }));
    resumo = await apiFetch(`/api/dp/fgts/resumo?competencia=${selAno}-${String(new Date().getMonth()+1).padStart(2,'0')}`).catch(() => ({}));
  };

  await load();

  const render = () => {
    const pendentes = extrato.registros.filter(r => !r.fgts_depositado || r.fgts_depositado == 0).length;
    el.innerHTML = `
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        ${kpiDP('Total Calculado (mês)', fBRL2(resumo.total_calculado||0), 'mês atual', 'calculator', 'text-blue-500')}
        ${kpiDP('Total Depositado', fBRL2(resumo.total_depositado||0), 'confirmados', 'check-circle', 'text-emerald-500')}
        ${kpiDP('Pendente', fBRL2(resumo.total_pendente||0), 'sem confirmação', 'clock', 'text-amber-500')}
        ${kpiDP('Nº Funcionários', resumo.n_funcionarios||0, 'com folha no mês', 'users', 'text-violet-500')}
      </div>
      ${pendentes > 0 ? `<div class="alert alert-warning mb-4">⚠ ${pendentes} competência(s) sem depósito confirmado para ${extrato.employee_name||'este funcionário'}.</div>` : ''}
      <div class="flex gap-3 mb-4 flex-wrap items-end">
        <div class="form-group mb-0"><label>Funcionário</label>
          <select id="fgts-emp" class="${inputCls}" onchange="window._fgtsLoad()"><option value="">— selecione —</option>
            ${dpEmployees.map(e=>`<option value="${e.id}" ${e.id==selEmp?'selected':''}>${e.name}</option>`).join('')}
          </select></div>
        <div class="form-group mb-0"><label>Ano</label>
          <input type="number" id="fgts-ano" class="${inputCls}" value="${selAno}" min="2020" max="2030" onchange="window._fgtsLoad()"></div>
        <button onclick="window._fgtsDepositar()" class="btn btn-primary">Confirmar Depósito</button>
      </div>
      <div class="table-responsive"><table class="table"><thead><tr>
        <th>Competência</th><th>Salário Base</th><th>FGTS 8%</th><th>Depositado</th><th>Data Depósito</th><th>Guia</th><th>Saldo Acumulado</th><th>Status</th>
      </tr></thead>
      <tbody>${extrato.registros.length ? extrato.registros.map(r => `<tr>
        <td>${r.competencia}</td>
        <td>${fBRL2(r.salario_base||0)}</td>
        <td>${fBRL2(r.fgts_calculado||0)}</td>
        <td>${fBRL2(r.fgts_depositado||0)}</td>
        <td>${r.data_deposito||'—'}</td>
        <td class="font-mono text-xs">${r.guia_referencia||'—'}</td>
        <td class="font-semibold text-emerald-600">${fBRL2(r.saldo_acumulado||0)}</td>
        <td>${r.fgts_depositado > 0 ? '<span class="badge badge-success">Depositado</span>' : '<span class="badge badge-danger">Pendente</span>'}</td>
      </tr>`).join('') : '<tr><td colspan="8" class="text-center text-muted">Selecione um funcionário para ver o extrato.</td></tr>'}</tbody></table></div>
      <div id="fgts-dep-modal" class="modal-overlay" style="display:none">
        <div class="modal-box"><h3>Confirmar Depósito FGTS</h3>
          <div class="form-group"><label>Competência</label><input id="fdep-comp" class="${inputCls}" placeholder="YYYY-MM"></div>
          <div class="form-group"><label>Valor Depositado R$</label><input type="number" step="0.01" id="fdep-val" class="${inputCls}"></div>
          <div class="form-row"><div class="form-group"><label>Data Depósito</label><input type="date" id="fdep-data" class="${inputCls}"></div>
          <div class="form-group"><label>Nº Guia</label><input id="fdep-guia" class="${inputCls}"></div></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('fgts-dep-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._fgtsSaveDeposito()">Confirmar</button></div>
        </div></div>`;

    window._fgtsLoad = async () => {
      selEmp = document.getElementById('fgts-emp').value;
      selAno = document.getElementById('fgts-ano').value;
      if (selEmp) { extrato = await apiFetch(`/api/dp/fgts/extrato/${selEmp}?ano=${selAno}`).catch(()=>({registros:[],saldo_total:0,employee_name:''})); }
      render();
    };
    window._fgtsDepositar = () => {
      document.getElementById('fdep-comp').value = `${selAno}-${String(new Date().getMonth()+1).padStart(2,'0')}`;
      document.getElementById('fdep-data').value = new Date().toISOString().slice(0,10);
      document.getElementById('fgts-dep-modal').style.display = 'flex';
    };
    window._fgtsSaveDeposito = async () => {
      if (!selEmp) { showToast('Selecione um funcionário','error'); return; }
      const b = { employee_id: +selEmp, competencia: document.getElementById('fdep-comp').value, fgts_depositado: +document.getElementById('fdep-val').value, data_deposito: document.getElementById('fdep-data').value, guia_referencia: document.getElementById('fdep-guia').value };
      try { await apiFetch('/api/dp/fgts/confirmar-deposito',{method:'POST',body:JSON.stringify(b)}); document.getElementById('fgts-dep-modal').style.display='none'; extrato = await apiFetch(`/api/dp/fgts/extrato/${selEmp}?ano=${selAno}`); showToast('Depósito confirmado!','success'); render(); } catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    if (window.lucide) lucide.createIcons();
  };
  render();
}


// ── PORTAL DO FUNCIONÁRIO ─────────────────────────────────────────
async function renderPortalFuncionario(el) {
  let selEmp = null;
  const isAdmin = currentUserRole === 'admin' || currentUserRole === 'dp';
  const user = (() => { try { return JSON.parse(localStorage.getItem('cortex_user')||'{}'); } catch { return {}; } })();

  if (!isAdmin) {
    try {
      selEmp = await apiFetch(`/api/dp/employees/by-email?email=${encodeURIComponent(user.email||'')}`);
    } catch {}
  }

  const renderPortal = async (emp) => {
    if (!emp) {
      el.innerHTML = `<div class="alert alert-info">Nenhum funcionário vinculado a este usuário. Contate o RH.</div>`; return;
    }
    let holerites = [], ferias = {}, afastamentos = [], fgtsData = {}, asos = [], reqFerias = [];
    try {
      [holerites, afastamentos, asos, reqFerias] = await Promise.all([
        apiFetch(`/api/dp/payroll/${emp.id}/history`).catch(() => []),
        apiFetch(`/api/dp/absences?employee_id=${emp.id}`).catch(() => []),
        apiFetch(`/api/dp/medical-exams?employee_id=${emp.id}`).catch(() => []),
        apiFetch(`/api/dp/vacation-requests?employee_id=${emp.id}`).catch(() => []),
      ]);
      fgtsData = await apiFetch(`/api/dp/fgts/extrato/${emp.id}`).catch(() => ({}));
      ferias = await apiFetch(`/api/dp/vacation/balance/${emp.id}`).catch(() => ({}));
    } catch {}

    const proximo_aso = asos.filter(a=>a.data_vencimento).sort((a,b)=>a.data_vencimento.localeCompare(b.data_vencimento))[0];
    const anoAtual = new Date().getFullYear();

    el.innerHTML = `
      ${isAdmin ? `<div class="flex gap-3 mb-4 items-end">
        <div class="form-group mb-0"><label>Visualizando como:</label>
          <select id="portal-emp-sel" class="${inputCls}" onchange="window._portalSelEmp(this.value)">
            ${dpEmployees.map(e=>`<option value="${e.id}" ${e.id==emp.id?'selected':''}>${e.name}</option>`).join('')}
          </select></div></div>` : ''}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

        <!-- Meus Dados -->
        <div class="card col-span-1"><div class="card-header"><h4 class="font-bold text-slate-800 dark:text-slate-100">Meus Dados</h4></div><div class="card-body">
          <dl class="text-sm space-y-2">
            <div class="flex justify-between"><dt class="text-muted">Nome</dt><dd class="font-semibold">${emp.name}</dd></div>
            <div class="flex justify-between"><dt class="text-muted">Cargo</dt><dd>${emp.role||'—'}</dd></div>
            <div class="flex justify-between"><dt class="text-muted">Departamento</dt><dd>${emp.department||'—'}</dd></div>
            <div class="flex justify-between"><dt class="text-muted">Admissão</dt><dd>${emp.admission_date||'—'}</dd></div>
            <div class="flex justify-between"><dt class="text-muted">CPF</dt><dd class="font-mono">${(emp.cpf||'').replace(/(\d{3})\d{3}(\d{3})(\d{2})/,'$1.***.***-$3')}</dd></div>
            ${isAdmin ? `<div class="flex justify-between"><dt class="text-muted">Salário</dt><dd class="font-semibold text-emerald-600">${fBRL2(emp.salary||0)}</dd></div>` : ''}
          </dl>
        </div></div>

        <!-- Holerites -->
        <div class="card"><div class="card-header"><h4 class="font-bold text-slate-800 dark:text-slate-100">Holerites</h4></div><div class="card-body">
          ${holerites.length ? `<div class="space-y-2 max-h-48 overflow-y-auto">
            ${holerites.map(h=>`<div class="flex justify-between items-center"><span class="text-sm">${h.competencia}</span>
              <button onclick="openAuthed('/api/dp/payslip/${emp.id}/${h.competencia}')" class="btn btn-sm btn-secondary">Baixar</button>
            </div>`).join('')}</div>` : '<p class="text-muted text-sm">Nenhum holerite disponível.</p>'}
        </div></div>

        <!-- Férias -->
        <div class="card"><div class="card-header"><h4 class="font-bold text-slate-800 dark:text-slate-100">Férias</h4></div><div class="card-body">
          <div class="text-center mb-3">
            <span class="text-3xl font-bold text-violet-600">${ferias.dias_disponiveis||0}</span>
            <span class="text-sm text-muted"> dias disponíveis</span>
          </div>
          <button onclick="window._portalSolFer(${emp.id})" class="btn btn-primary w-full text-xs">Solicitar Férias</button>
          ${reqFerias.length ? `<div class="mt-3 space-y-1">${reqFerias.slice(0,3).map(r=>`<div class="text-xs flex justify-between"><span>${r.data_inicio_solicitada} → ${r.data_fim_solicitada}</span><span class="badge ${r.status==='aprovado'?'badge-success':r.status==='recusado'?'badge-danger':'badge-warning'}">${r.status}</span></div>`).join('')}</div>` : ''}
        </div></div>

        <!-- Extrato FGTS -->
        <div class="card"><div class="card-header"><h4 class="font-bold text-slate-800 dark:text-slate-100">Extrato FGTS</h4></div><div class="card-body">
          <div class="text-center mb-3">
            <span class="text-3xl font-bold text-emerald-600">${fBRL2(fgtsData.saldo_total||0)}</span>
            <span class="text-sm text-muted"> saldo estimado</span>
          </div>
          <div class="space-y-1 max-h-32 overflow-y-auto">
            ${(fgtsData.registros||[]).slice(-6).reverse().map(r=>`<div class="text-xs flex justify-between"><span>${r.competencia}</span><span class="text-emerald-600">${fBRL2(r.fgts_calculado||0)}</span></div>`).join('')}
          </div>
        </div></div>

        <!-- Exames ASO -->
        <div class="card"><div class="card-header"><h4 class="font-bold text-slate-800 dark:text-slate-100">Exames Médicos (ASO)</h4></div><div class="card-body">
          ${proximo_aso ? `<div class="mb-3 p-3 rounded-lg ${(()=>{const d=Math.floor((new Date(proximo_aso.data_vencimento)-new Date())/86400000);return d<0?'bg-red-50 dark:bg-red-900/20':d<=30?'bg-amber-50 dark:bg-amber-900/20':'bg-green-50 dark:bg-green-900/20';})()}">
            <p class="text-xs font-semibold">Próximo: ${proximo_aso.tipo}</p>
            <p class="text-xs text-muted">Venc: ${proximo_aso.data_vencimento}</p></div>` : '<p class="text-muted text-sm">Nenhum exame próximo.</p>'}
          <div class="space-y-1 max-h-32 overflow-y-auto">
            ${asos.slice(0,5).map(a=>`<div class="text-xs flex justify-between"><span>${a.tipo}</span><span>${a.data_exame}</span><span class="badge ${a.resultado==='apto'?'badge-success':a.resultado==='inapto'?'badge-danger':'badge-warning'}">${a.resultado}</span></div>`).join('')}
          </div>
        </div></div>

        <!-- Declarações -->
        <div class="card"><div class="card-header"><h4 class="font-bold text-slate-800 dark:text-slate-100">Declarações</h4></div><div class="card-body space-y-2">
          <button onclick="openAuthed('/api/dp/declarations/vinculo/${emp.id}')" class="btn btn-secondary w-full text-xs">Declaração de Vínculo</button>
          <button onclick="openAuthed('/api/dp/declarations/ir/${emp.id}?ano=${anoAtual-1}')" class="btn btn-secondary w-full text-xs">Informe de Rendimentos ${anoAtual-1}</button>
          <button onclick="openAuthed('/api/dp/declarations/ir/${emp.id}?ano=${anoAtual}')" class="btn btn-secondary w-full text-xs">Informe de Rendimentos ${anoAtual}</button>
        </div></div>

      </div>
      <div id="portal-fer-modal" class="modal-overlay" style="display:none">
        <div class="modal-box"><h3>Solicitar Férias</h3>
          <div class="form-row"><div class="form-group"><label>Data Início</label><input type="date" id="pfer-ini" class="${inputCls}"></div>
          <div class="form-group"><label>Data Fim</label><input type="date" id="pfer-fim" class="${inputCls}"></div></div>
          <div class="d-flex gap-2 justify-content-end mt-3">
            <button class="btn btn-secondary" onclick="document.getElementById('portal-fer-modal').style.display='none'">Cancelar</button>
            <button class="btn btn-primary" onclick="window._portalFerSave(${emp.id})">Enviar Solicitação</button></div>
        </div></div>`;

    window._portalSolFer = (eid) => { document.getElementById('portal-fer-modal').style.display = 'flex'; };
    window._portalFerSave = async (eid) => {
      const b = { employee_id: eid, data_inicio_solicitada: document.getElementById('pfer-ini').value, data_fim_solicitada: document.getElementById('pfer-fim').value };
      try { await apiFetch('/api/dp/vacation-requests',{method:'POST',body:JSON.stringify(b)}); document.getElementById('portal-fer-modal').style.display='none'; showToast('Solicitação enviada!','success'); } catch(e) { showToast('Erro: '+e.message,'error'); }
    };
    window._portalSelEmp = async (eid) => {
      const emp2 = dpEmployees.find(e=>e.id==eid); if (emp2) { selEmp = emp2; await renderPortal(emp2); }
    };
    if (window.lucide) lucide.createIcons();
  };

  if (isAdmin) {
    selEmp = dpEmployees[0] || null;
    el.innerHTML = `<div class="flex gap-3 mb-4 items-end">
      <div class="form-group mb-0"><label>Visualizando como:</label>
        <select id="portal-emp-sel" class="${inputCls}" onchange="window._portalSelEmp(this.value)">
          ${dpEmployees.map(e=>`<option value="${e.id}">${e.name}</option>`).join('')}
        </select></div></div><div id="portal-inner"></div>`;
    window._portalSelEmp = async (eid) => {
      const emp2 = dpEmployees.find(e=>e.id==eid);
      if (emp2) { const inner = document.getElementById('portal-inner'); if (inner) await renderPortal(emp2); }
    };
    if (selEmp) {
      const inner = document.createElement('div'); inner.id = 'portal-inner'; el.querySelector('#portal-inner') && (el.querySelector('#portal-inner').outerHTML = '');
      const wrap = el.querySelector('#portal-inner') || el.appendChild(Object.assign(document.createElement('div'),{id:'portal-inner'}));
      await renderPortal(selEmp);
    }
  } else {
    await renderPortal(selEmp);
  }
}

