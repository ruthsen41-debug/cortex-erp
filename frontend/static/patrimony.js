// ============================================================
// PATRIMÔNIO / ATIVOS FIXOS — Cortex ERP Pro+
// ============================================================

let patTab = 'list';
const patCategories = {
  maquinas_equipamentos: 'Máquinas e Equipamentos',
  moveis_utensilios: 'Móveis e Utensílios',
  veiculos: 'Veículos',
  informatica: 'Informática e Eletrônicos',
  imóveis: 'Imóveis',
  instalacoes: 'Instalações',
  ferramentas: 'Ferramentas',
  outros: 'Outros',
};

const fBRL_p = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fDate_p = s => s ? s.slice(0, 10).split('-').reverse().join('/') : '-';
const fPct_p  = v => `${parseFloat(v || 0).toFixed(1)}%`;

function inputP() {
  return 'w-full text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500';
}
function lblP(t) { return `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${t}</label>`; }
function kpiP(label, value, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
  </div>`;
}

async function renderPatrimony(container) {
  const summary = await apiFetch('/api/patrimony/summary').catch(() => ({}));
  const assets  = await apiFetch('/api/patrimony').catch(() => []);

  container.innerHTML = `
  <div class="space-y-6">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <i data-lucide="building" class="w-5 h-5 text-purple-400"></i> Patrimônio &amp; Ativos Fixos
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">Controle de bens, depreciação e CIAP</p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <button onclick="patRunDepreciation()" class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold transition">
          <i data-lucide="calculator" class="w-4 h-4"></i> Depreciar Mês
        </button>
        <button onclick="patExportCIAP()" class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition">
          <i data-lucide="download" class="w-4 h-4"></i> Exportar CIAP
        </button>
        <button onclick="patOpenModal()" class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold transition">
          <i data-lucide="plus" class="w-4 h-4"></i> Novo Bem
        </button>
      </div>
    </div>

    <!-- KPIs -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      ${kpiP('Total de Bens', summary.total_assets || 0, 'layers', 'text-purple-400')}
      ${kpiP('Valor de Aquisição', fBRL_p(summary.total_acquisition_value), 'dollar-sign', 'text-blue-400')}
      ${kpiP('Depreciação Acumulada', fBRL_p(summary.total_accumulated_depreciation), 'trending-down', 'text-amber-400')}
      ${kpiP('Valor Contábil Líquido', fBRL_p(summary.total_net_value), 'archive', 'text-emerald-400')}
    </div>

    <!-- Tabela de Bens -->
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
      <div class="px-5 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <span class="font-semibold text-slate-700 dark:text-slate-200 text-sm">Bens Patrimoniais</span>
        <div class="flex gap-2">
          <select id="pat-filter-status" onchange="patFilterAssets()" class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-lg px-2 py-1.5">
            <option value="">Todos os Status</option>
            <option value="ativo">Ativo</option>
            <option value="depreciado">Depreciado</option>
            <option value="baixado">Baixado</option>
          </select>
          <select id="pat-filter-cat" onchange="patFilterAssets()" class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-lg px-2 py-1.5">
            <option value="">Todas as Categorias</option>
            ${Object.entries(patCategories).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}
          </select>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm" id="pat-table">
          <thead><tr class="text-xs text-slate-400 border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-3 text-left">Bem</th>
            <th class="px-4 py-3 text-left">Categoria</th>
            <th class="px-4 py-3 text-left">Aquisição</th>
            <th class="px-4 py-3 text-right">Valor Orig.</th>
            <th class="px-4 py-3 text-right">Dep. Acum.</th>
            <th class="px-4 py-3 text-right">Val. Líquido</th>
            <th class="px-4 py-3 text-right">Dep/Mês</th>
            <th class="px-4 py-3 text-left">Status</th>
            <th class="px-4 py-3"></th>
          </tr></thead>
          <tbody id="pat-tbody">
            ${assets.length === 0
              ? `<tr><td colspan="9" class="px-4 py-10 text-center text-slate-400">Nenhum bem cadastrado.</td></tr>`
              : assets.map(a => patRow(a)).join('')}
          </tbody>
        </table>
      </div>
    </div>
  </div>`;
  if (window.lucide) lucide.createIcons();
}

function patRow(a) {
  const depM = a.acquisition_value && a.useful_life_months
    ? (a.acquisition_value - a.residual_value) / a.useful_life_months
    : 0;
  const pct = a.acquisition_value ? (a.accumulated_depreciation / a.acquisition_value * 100) : 0;
  const statusColor = {ativo:'bg-emerald-500/15 text-emerald-400',depreciado:'bg-amber-500/15 text-amber-400',baixado:'bg-slate-500/15 text-slate-400'}[a.status] || '';
  return `<tr class="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30">
    <td class="px-4 py-3">
      <div class="font-medium text-slate-800 dark:text-white text-xs">${a.name}</div>
      ${a.description ? `<div class="text-[10px] text-slate-400">${a.description}</div>` : ''}
      <div class="mt-1 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden w-24">
        <div class="h-full bg-amber-400 rounded-full" style="width:${Math.min(100,pct).toFixed(0)}%"></div>
      </div>
    </td>
    <td class="px-4 py-3 text-xs text-slate-500">${patCategories[a.category] || a.category}</td>
    <td class="px-4 py-3 text-xs text-slate-500">${fDate_p(a.acquisition_date)}</td>
    <td class="px-4 py-3 text-right text-xs font-mono">${fBRL_p(a.acquisition_value)}</td>
    <td class="px-4 py-3 text-right text-xs font-mono text-amber-500">${fBRL_p(a.accumulated_depreciation)}</td>
    <td class="px-4 py-3 text-right text-xs font-mono font-semibold text-emerald-500">${fBRL_p(a.net_value)}</td>
    <td class="px-4 py-3 text-right text-xs font-mono">${fBRL_p(depM)}</td>
    <td class="px-4 py-3"><span class="px-2 py-1 rounded-lg text-[10px] font-semibold ${statusColor}">${a.status}</span></td>
    <td class="px-4 py-3 text-right">
      <div class="flex gap-1 justify-end">
        <button onclick="patOpenModal(${JSON.stringify(a).replace(/"/g,'&quot;')})" class="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-blue-500">
          <i data-lucide="pencil" class="w-3.5 h-3.5"></i>
        </button>
        <button onclick="patDelete(${a.id})" class="p-1.5 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-500/10 text-slate-400 hover:text-rose-500">
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
        </button>
      </div>
    </td>
  </tr>`;
}

function patOpenModal(asset = null) {
  const isEdit = !!asset;
  const catOptions = Object.entries(patCategories).map(([k,v])=>`<option value="${k}" ${asset?.category===k?'selected':''}>${v}</option>`).join('');
  openModal(`
  <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 space-y-4">
    <h3 class="font-bold text-lg text-slate-800 dark:text-white">${isEdit ? 'Editar Bem' : 'Novo Bem Patrimonial'}</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="md:col-span-2">${lblP('Nome / Descrição do Bem')}
        <input id="pat-name" class="${inputP()}" value="${asset?.name||''}" placeholder="Ex: Notebook Dell XPS 15" /></div>
      <div>${lblP('Categoria')}<select id="pat-cat" class="${inputP()}">${catOptions}</select></div>
      <div>${lblP('Data de Aquisição')}<input type="date" id="pat-date" class="${inputP()}" value="${asset?.acquisition_date||new Date().toISOString().slice(0,10)}" /></div>
      <div>${lblP('Valor de Aquisição (R$)')}<input type="number" id="pat-value" class="${inputP()}" value="${asset?.acquisition_value||''}" step="0.01" /></div>
      <div>${lblP('Vida Útil (meses)')}<input type="number" id="pat-life" class="${inputP()}" value="${asset?.useful_life_months||60}" /></div>
      <div>${lblP('Valor Residual (R$)')}<input type="number" id="pat-residual" class="${inputP()}" value="${asset?.residual_value||0}" step="0.01" /></div>
      <div>${lblP('Método de Depreciação')}
        <select id="pat-method" class="${inputP()}">
          <option value="linear" ${asset?.depreciation_method==='linear'?'selected':''}>Linear (Cotas Constantes)</option>
          <option value="acelerado" ${asset?.depreciation_method==='acelerado'?'selected':''}>Acelerado (150%)</option>
        </select></div>
      <div class="md:col-span-2">${lblP('Observações')}
        <input id="pat-notes" class="${inputP()}" value="${asset?.notes||''}" placeholder="Nº série, nota fiscal, etc." /></div>
    </div>
    <div class="flex gap-3 pt-2">
      <button onclick="patSave(${asset?.id||'null'})" class="flex-1 bg-purple-600 hover:bg-purple-700 text-white font-semibold py-2.5 rounded-xl transition">
        ${isEdit ? 'Salvar Alterações' : 'Cadastrar Bem'}
      </button>
      <button onclick="closeModal()" class="px-5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-sm font-semibold hover:bg-slate-50 dark:hover:bg-slate-800 transition">Cancelar</button>
    </div>
  </div>`);
}

async function patSave(id) {
  const body = {
    name: document.getElementById('pat-name')?.value?.trim(),
    category: document.getElementById('pat-cat')?.value,
    acquisition_date: document.getElementById('pat-date')?.value,
    acquisition_value: parseFloat(document.getElementById('pat-value')?.value) || 0,
    useful_life_months: parseInt(document.getElementById('pat-life')?.value) || 60,
    residual_value: parseFloat(document.getElementById('pat-residual')?.value) || 0,
    depreciation_method: document.getElementById('pat-method')?.value,
    notes: document.getElementById('pat-notes')?.value,
  };
  if (!body.name || !body.acquisition_date || !body.acquisition_value) {
    showToast('Preencha nome, data e valor de aquisição.', 'error'); return;
  }
  const url = id ? `/api/patrimony/${id}` : '/api/patrimony';
  const method = id ? 'PUT' : 'POST';
  const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('cortex_token')}` }, body: JSON.stringify(body) });
  if (res.ok) {
    showToast(id ? 'Bem atualizado!' : 'Bem cadastrado!', 'success');
    closeModal();
    switchTab('patrimony');
  } else {
    const e = await res.json();
    showToast(e.detail || 'Erro ao salvar.', 'error');
  }
}

async function patDelete(id) {
  if (!confirm('Excluir este bem patrimonial?')) return;
  const res = await fetch(`/api/patrimony/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('cortex_token')}` } });
  if (res.ok) { showToast('Bem excluído.', 'success'); switchTab('patrimony'); }
}

async function patRunDepreciation() {
  const comp = prompt('Competência (AAAA-MM):', new Date().toISOString().slice(0,7));
  if (!comp) return;
  const res = await apiFetch(`/api/patrimony/run-depreciation?competencia=${comp}`, { method: 'POST' }).catch(e => ({ message: e.message }));
  showToast(res.message || 'Depreciação processada.', 'success');
  switchTab('patrimony');
}

async function patExportCIAP() {
  const year = new Date().getFullYear();
  const data = await apiFetch(`/api/patrimony/ciap?year=${year}`).catch(() => null);
  if (!data) { showToast('Erro ao gerar CIAP.', 'error'); return; }
  let csv = 'Descrição;Data Aquisição;Valor Aquisição;Vida Útil (meses);Dep. Mensal;Dep. Acumulada;Valor Líquido;Status\n';
  data.items.forEach(i => {
    csv += `${i.descricao};${i.data_aquisicao};${i.valor_aquisicao};${i.vida_util_meses};${i.depreciacao_mensal};${i.depreciacao_acumulada};${i.valor_contabil_liquido};${i.status}\n`;
  });
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = `CIAP_${year}.csv`; a.click();
  showToast(`CIAP ${year} exportado — ${data.total_items} itens.`, 'success');
}

async function patFilterAssets() {
  const status = document.getElementById('pat-filter-status')?.value;
  const cat    = document.getElementById('pat-filter-cat')?.value;
  let url = '/api/patrimony?';
  if (status) url += `status=${status}&`;
  if (cat)    url += `category=${cat}&`;
  const assets = await apiFetch(url).catch(() => []);
  const tbody = document.getElementById('pat-tbody');
  if (tbody) tbody.innerHTML = assets.length
    ? assets.map(a => patRow(a)).join('')
    : `<tr><td colspan="9" class="px-4 py-10 text-center text-slate-400">Nenhum bem encontrado.</td></tr>`;
  if (window.lucide) lucide.createIcons();
}
