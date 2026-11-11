// ============================================================
// AUDITORIA — Cortex ERP Pro+
// Rastreabilidade de ações, usuários e alterações
// ============================================================

const fDate_a = s => s ? s.slice(0,16).replace('T',' ') : '-';
const actionColors = {
  INSERT: 'bg-emerald-500/15 text-emerald-400',
  UPDATE: 'bg-blue-500/15 text-blue-400',
  DELETE: 'bg-rose-500/15 text-rose-400',
  LOGIN:  'bg-violet-500/15 text-violet-400',
  LOGOUT: 'bg-slate-500/15 text-slate-400',
  EXPORT: 'bg-amber-500/15 text-amber-400',
};

function kpiA(label, value, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
  </div>`;
}

async function renderAudit(container) {
  const stats = await apiFetch('/api/audit/stats').catch(() => ({}));
  const logs  = stats.recent || [];

  container.innerHTML = `
  <div class="space-y-5">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <i data-lucide="shield-check" class="w-5 h-5 text-cyan-400"></i> Auditoria do Sistema
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">Rastreabilidade de ações, usuários e alterações</p>
      </div>
      <button onclick="auditRefresh()" class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-sm font-semibold hover:bg-slate-50 dark:hover:bg-slate-800 transition">
        <i data-lucide="refresh-cw" class="w-4 h-4"></i> Atualizar
      </button>
    </div>

    <!-- KPIs -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      ${kpiA('Total de Eventos', stats.total_events?.toLocaleString() || 0, 'activity', 'text-cyan-400')}
      ${kpiA('Eventos Hoje', stats.today_events || 0, 'clock', 'text-blue-400')}
      ${kpiA('Usuários Ativos', (stats.by_user || []).length, 'users', 'text-purple-400')}
      ${kpiA('Tabelas Monitoradas', (stats.by_table || []).length, 'database', 'text-emerald-400')}
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- Ações mais frequentes -->
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-3">Ações Mais Frequentes</div>
        ${(stats.by_action || []).slice(0,6).map(a => `
        <div class="flex items-center justify-between py-1.5 border-b border-slate-50 dark:border-slate-800 last:border-0">
          <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${actionColors[a.action] || 'bg-slate-100 text-slate-500'}">${a.action}</span>
          <span class="font-mono text-xs font-bold">${a.cnt}</span>
        </div>`).join('') || '<div class="text-xs text-slate-400 text-center py-4">Sem dados.</div>'}
      </div>

      <!-- Tabelas monitoradas -->
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-3">Tabelas Mais Alteradas</div>
        ${(stats.by_table || []).slice(0,8).map(t => `
        <div class="flex items-center justify-between py-1.5 border-b border-slate-50 dark:border-slate-800 last:border-0">
          <span class="text-xs text-slate-500 font-mono">${t.table_name}</span>
          <span class="font-mono text-xs font-bold text-slate-600 dark:text-slate-300">${t.cnt}</span>
        </div>`).join('') || '<div class="text-xs text-slate-400 text-center py-4">Sem dados.</div>'}
      </div>

      <!-- Top usuários -->
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-3">Usuários Mais Ativos</div>
        ${(stats.by_user || []).slice(0,8).map(u => `
        <div class="flex items-center justify-between py-1.5 border-b border-slate-50 dark:border-slate-800 last:border-0">
          <span class="text-xs font-semibold text-slate-600 dark:text-slate-300">${u.user_name || 'Sistema'}</span>
          <span class="font-mono text-xs font-bold text-slate-500">${u.cnt}</span>
        </div>`).join('') || '<div class="text-xs text-slate-400 text-center py-4">Sem dados.</div>'}
      </div>
    </div>

    <!-- Filtros e log -->
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
      <div class="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3">
        <span class="font-semibold text-slate-700 dark:text-slate-200 text-sm">Log de Auditoria</span>
        <div class="flex gap-2 flex-wrap">
          <input type="date" id="audit-start" class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-lg px-2 py-1.5 w-32" />
          <input type="date" id="audit-end"   class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-lg px-2 py-1.5 w-32" />
          <select id="audit-action" class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-lg px-2 py-1.5">
            <option value="">Todas as Ações</option>
            ${Object.keys(actionColors).map(a=>`<option value="${a}">${a}</option>`).join('')}
          </select>
          <button onclick="auditSearch()" class="bg-cyan-600 text-white text-xs px-3 py-1.5 rounded-lg font-semibold">Filtrar</button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm" id="audit-table">
          <thead><tr class="text-xs text-slate-400 border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-3 text-left">Data/Hora</th>
            <th class="px-4 py-3 text-left">Usuário</th>
            <th class="px-4 py-3 text-left">Ação</th>
            <th class="px-4 py-3 text-left">Tabela</th>
            <th class="px-4 py-3 text-left">Reg. ID</th>
            <th class="px-4 py-3 text-left">IP</th>
          </tr></thead>
          <tbody id="audit-tbody">
            ${auditRows(logs)}
          </tbody>
        </table>
      </div>
    </div>
  </div>`;
  if (window.lucide) lucide.createIcons();
}

function auditRows(logs) {
  if (!logs.length) return `<tr><td colspan="6" class="px-4 py-10 text-center text-slate-400">Nenhum evento registrado.</td></tr>`;
  return logs.map(l => `
  <tr class="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30">
    <td class="px-4 py-2.5 font-mono text-[11px] text-slate-400">${fDate_a(l.created_at)}</td>
    <td class="px-4 py-2.5 text-xs font-semibold text-slate-600 dark:text-slate-300">${l.user_name || 'sistema'}</td>
    <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-semibold ${actionColors[l.action] || 'bg-slate-100 dark:bg-slate-700 text-slate-400'}">${l.action}</span></td>
    <td class="px-4 py-2.5 font-mono text-[11px] text-slate-500">${l.table_name || '-'}</td>
    <td class="px-4 py-2.5 font-mono text-xs text-slate-400">${l.record_id || '-'}</td>
    <td class="px-4 py-2.5 font-mono text-[11px] text-slate-400">${l.ip_address || '-'}</td>
  </tr>`).join('');
}

async function auditSearch() {
  const start  = document.getElementById('audit-start')?.value;
  const end    = document.getElementById('audit-end')?.value;
  const action = document.getElementById('audit-action')?.value;
  let url = '/api/audit/logs?limit=200';
  if (start)  url += `&start_date=${start}`;
  if (end)    url += `&end_date=${end}`;
  if (action) url += `&action=${action}`;
  const rows = await apiFetch(url).catch(() => []);
  const tbody = document.getElementById('audit-tbody');
  if (tbody) tbody.innerHTML = auditRows(rows);
  if (window.lucide) lucide.createIcons();
}

async function auditRefresh() {
  switchTab('audit');
}
