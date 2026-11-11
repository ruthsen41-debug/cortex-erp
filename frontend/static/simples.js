// ============================================================
// SIMPLES NACIONAL — Cortex ERP Pro+
// DAS · PGDAS-D · Histórico · Configuração
// ============================================================

let simplesSubTab = 'pgdas';
const fBRL_s = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fPct_s = v => `${parseFloat(v || 0).toFixed(4)}%`;

function inputS() { return 'w-full text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500'; }
function lblS(t)   { return `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${t}</label>`; }
function kpiS(label, value, sub, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-400 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
    ${sub ? `<div class="text-[11px] text-slate-400 mt-1">${sub}</div>` : ''}
  </div>`;
}

function simplesTab(id, label, active) {
  const cls = active === id
    ? 'border-b-2 border-green-500 text-green-500 font-semibold'
    : 'text-slate-400 hover:text-slate-200';
  return `<button onclick="simplesSubTab='${id}'; renderSimples(document.getElementById('main-content'))" class="px-4 py-2.5 text-sm ${cls} transition whitespace-nowrap">${label}</button>`;
}

async function renderSimples(container) {
  const cfg = await apiFetch('/api/simples/config').catch(() => ({}));
  const pgdas = await apiFetch(`/api/simples/pgdas-preview`).catch(() => null);

  let content = '';
  if (simplesSubTab === 'pgdas') content = await renderPGDAS(pgdas, cfg);
  else if (simplesSubTab === 'das')     content = await renderDASCalc(cfg);
  else if (simplesSubTab === 'historico') content = await renderDASHistory();
  else if (simplesSubTab === 'config')  content = renderSimplesConfig(cfg);

  const regime = cfg.regime || '';
  const isSimples = regime.includes('simples') || regime === 'mei';

  container.innerHTML = `
  <div class="space-y-5">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <i data-lucide="landmark" class="w-5 h-5 text-green-400"></i> Simples Nacional
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">DAS · PGDAS-D · Apuração e Histórico</p>
      </div>
      ${!isSimples ? `<div class="bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs px-4 py-2 rounded-xl">
        Regime atual: <strong>${regime}</strong> — configure o regime em Configurações da Empresa para usar este módulo.
      </div>` : ''}
    </div>

    <div class="flex gap-1 border-b border-slate-200 dark:border-slate-800 overflow-x-auto">
      ${simplesTab('pgdas', 'PGDAS-D Preview', simplesSubTab)}
      ${simplesTab('das', 'Calcular DAS', simplesSubTab)}
      ${simplesTab('historico', 'Histórico', simplesSubTab)}
      ${simplesTab('config', 'Configuração', simplesSubTab)}
    </div>

    ${content}
  </div>`;
  if (window.lucide) lucide.createIcons();
}

async function renderPGDAS(pgdas, cfg) {
  if (!pgdas) return '<div class="p-6 text-slate-400 text-center">Erro ao carregar PGDAS.</div>';
  const breakdown = pgdas.breakdown_estimado || {};
  const breakdownRows = Object.entries(breakdown).map(([k, v]) => `
    <div class="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-800 last:border-0">
      <span class="text-xs font-semibold text-slate-500">${k}</span>
      <span class="text-sm font-mono font-semibold text-slate-700 dark:text-slate-200">${fBRL_s(v)}</span>
    </div>`).join('');
  return `
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
    ${kpiS('Receita Bruta Mês', fBRL_s(pgdas.receita_bruta_mes), pgdas.competencia, 'bar-chart-2', 'text-blue-400')}
    ${kpiS('RBT12', fBRL_s(pgdas.rbt12), 'Faturamento 12 meses', 'trending-up', 'text-indigo-400')}
    ${kpiS('Alíquota Efetiva', fPct_s(pgdas.aliquota_efetiva), `Faixa ${pgdas.faixa} — ${pgdas.anexo ? 'Anexo ' + pgdas.anexo : ''}`, 'percent', 'text-amber-400')}
    ${kpiS('DAS a Recolher', fBRL_s(pgdas.valor_das), `Vence: ${pgdas.vencimento?.split('-').reverse().join('/') || '-'}`, 'receipt', 'text-green-400')}
  </div>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
      <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-4">Distribuição Estimada por Tributo</div>
      ${breakdownRows || '<div class="text-xs text-slate-400 text-center py-4">Sem receita no período.</div>'}
    </div>
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
      <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-4">Dados da Competência</div>
      <div class="space-y-2 text-xs">
        <div class="flex justify-between"><span class="text-slate-400">Empresa</span><span class="font-semibold">${pgdas.razao_social || '-'}</span></div>
        <div class="flex justify-between"><span class="text-slate-400">CNPJ</span><span class="font-mono">${pgdas.cnpj || '-'}</span></div>
        <div class="flex justify-between"><span class="text-slate-400">Competência</span><span class="font-semibold">${pgdas.competencia}</span></div>
        <div class="flex justify-between"><span class="text-slate-400">Alíq. Nominal</span><span>${fPct_s(pgdas.aliquota_nominal)}</span></div>
        <div class="flex justify-between"><span class="text-slate-400">Vencimento DAS</span><span class="font-semibold text-amber-400">${pgdas.vencimento?.split('-').reverse().join('/') || '-'}</span></div>
      </div>
      <div class="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-[11px] text-amber-400">
        Prévia estimada com base nos lançamentos do ERP. Acesse o Portal do Simples Nacional para confirmar.
      </div>
    </div>
  </div>`;
}

async function renderDASCalc(cfg) {
  const today = new Date();
  const comp = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`;
  return `
  <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-lg">
    <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-5">Calcular DAS Manualmente</div>
    <div class="space-y-4">
      <div>${lblS('Competência (AAAA-MM)')}<input type="month" id="das-comp" class="${inputS()}" value="${comp}" /></div>
      <div>${lblS('Receita Bruta do Mês (R$)')}<input type="number" id="das-rb" class="${inputS()}" step="0.01" placeholder="Ex: 15000.00" /></div>
      <div>${lblS('RBT12 — Faturamento 12 meses (R$)')}<input type="number" id="das-rbt12" class="${inputS()}" step="0.01" value="${cfg.faturamento_12m || ''}" placeholder="Deixe vazio para usar o configurado" /></div>
      <button onclick="dasCalculate()" class="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2.5 rounded-xl transition">Calcular DAS</button>
    </div>
    <div id="das-result" class="mt-4"></div>
  </div>`;
}

async function dasCalculate() {
  const comp = document.getElementById('das-comp')?.value;
  const rb = parseFloat(document.getElementById('das-rb')?.value) || 0;
  const rbt12 = parseFloat(document.getElementById('das-rbt12')?.value) || null;
  if (!comp || !rb) { showToast('Preencha a competência e a receita do mês.', 'error'); return; }
  const body = { competencia: comp, receita_bruta_mes: rb };
  if (rbt12) body.rbt12 = rbt12;
  const res = await apiFetch('/api/simples/calculate-das', { method: 'POST', body: JSON.stringify(body) }).catch(e => ({ error: e.message }));
  const el = document.getElementById('das-result');
  if (!el) return;
  if (res.error) { el.innerHTML = `<div class="text-rose-400 text-sm">${res.error}</div>`; return; }
  el.innerHTML = `<div class="bg-green-500/10 border border-green-500/20 rounded-xl p-4 space-y-2 text-sm">
    <div class="font-bold text-green-400 text-base">${fBRL_s(res.valor_das)} a recolher</div>
    <div class="flex justify-between text-xs"><span class="text-slate-400">Alíquota Efetiva</span><span>${fPct_s(res.aliquota_efetiva)}</span></div>
    <div class="flex justify-between text-xs"><span class="text-slate-400">Alíquota Nominal</span><span>${fPct_s(res.aliquota_nominal)}</span></div>
    <div class="flex justify-between text-xs"><span class="text-slate-400">Faixa</span><span>${res.faixa}</span></div>
    <div class="flex justify-between text-xs"><span class="text-slate-400">Anexo</span><span>${res.anexo}</span></div>
    <div class="text-[11px] text-slate-400 pt-1">Calculado e salvo no histórico.</div>
  </div>`;
}

async function renderDASHistory() {
  const rows = await apiFetch('/api/simples/history').catch(() => []);
  if (!rows.length) return '<div class="p-6 text-slate-400 text-center">Nenhum DAS calculado ainda.</div>';
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead><tr class="text-xs text-slate-400 border-b border-slate-100 dark:border-slate-800">
          <th class="px-4 py-3 text-left">Competência</th>
          <th class="px-4 py-3 text-right">Receita Mês</th>
          <th class="px-4 py-3 text-right">RBT12</th>
          <th class="px-4 py-3 text-right">Alíq. Efetiva</th>
          <th class="px-4 py-3 text-right">Valor DAS</th>
          <th class="px-4 py-3 text-left">Anexo</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => `<tr class="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30">
            <td class="px-4 py-3 font-mono font-semibold text-xs">${r.competencia}</td>
            <td class="px-4 py-3 text-right font-mono text-xs">${fBRL_s(r.receita_bruta_mes)}</td>
            <td class="px-4 py-3 text-right font-mono text-xs">${fBRL_s(r.rbt12)}</td>
            <td class="px-4 py-3 text-right font-mono text-xs text-amber-400">${fPct_s(r.aliquota_efetiva)}</td>
            <td class="px-4 py-3 text-right font-mono font-bold text-xs text-green-400">${fBRL_s(r.valor_das)}</td>
            <td class="px-4 py-3 text-xs">${r.anexo}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  </div>`;
}

function renderSimplesConfig(cfg) {
  const anexoOpts = ['I','II','III','IV','V'].map(a =>
    `<option value="${a}" ${cfg.anexo===a?'selected':''}>Anexo ${a}</option>`).join('');
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-lg space-y-4">
    <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm">Configuração do Simples Nacional</div>
    <div class="space-y-2 text-xs text-slate-500 bg-slate-50 dark:bg-slate-800 rounded-xl p-3">
      <div><strong>Anexo I</strong> — Comércio (revenda de mercadorias)</div>
      <div><strong>Anexo II</strong> — Indústria (fabricação de produtos)</div>
      <div><strong>Anexo III</strong> — Serviços com ISS (creche, escritório, etc.)</div>
      <div><strong>Anexo IV</strong> — Serviços sem CPP (construção, vigilância)</div>
      <div><strong>Anexo V</strong> — Serviços de alta tributação (medicina, TI, engenharia)</div>
    </div>
    <div>${lblS('Seu Anexo')}
      <select id="cfg-anexo" class="${inputS()}">${anexoOpts}</select>
    </div>
    <div>${lblS('Faturamento nos Últimos 12 Meses (R$)')}
      <input type="number" id="cfg-rbt12" class="${inputS()}" step="0.01" value="${cfg.faturamento_12m || ''}" placeholder="Ex: 180000.00" />
    </div>
    <button onclick="simplesSaveConfig()" class="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2.5 rounded-xl transition">Salvar Configuração</button>
  </div>`;
}

async function simplesSaveConfig() {
  const body = {
    anexo: document.getElementById('cfg-anexo')?.value,
    faturamento_12m: parseFloat(document.getElementById('cfg-rbt12')?.value) || 0,
  };
  const res = await apiFetch('/api/simples/config', { method: 'PUT', body: JSON.stringify(body) }).catch(e => ({ error: e.message }));
  if (res?.message) { showToast('Configuração salva!', 'success'); switchTab('simples'); }
  else showToast(res?.error || 'Erro ao salvar.', 'error');
}
