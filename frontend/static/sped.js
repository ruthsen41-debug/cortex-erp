// ============================================================
// SPED FISCAL — Cortex ERP Pro+
// EFD ICMS/IPI · Pacote do Contador · Portal Contábil
// ============================================================

let spedSubTab = 'efd';
let spedPreview = null;

// ── helpers ──────────────────────────────────────────────────
const fBRL5  = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fDate5 = s => s ? s.slice(0, 10).split('-').reverse().join('/') : '-';

function kpiSped(label, value, sub, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-500 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
    ${sub ? `<div class="text-[11px] text-slate-400 mt-1">${sub}</div>` : ''}
  </div>`;
}

function inputSped() {
  return 'w-full text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-500';
}
function lblSped(t) {
  return `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${t}</label>`;
}
function btnAmber(onclick, icon, text, extra = '') {
  return `<button onclick="${onclick}" class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold transition ${extra}">
    <i data-lucide="${icon}" class="w-4 h-4"></i>${text}
  </button>`;
}

// ── tabs ─────────────────────────────────────────────────────
function spedTabs() {
  const tabs = [
    { id: 'efd',         icon: 'file-code-2',    label: 'EFD ICMS/IPI' },
    { id: 'efd_contrib', icon: 'file-text',       label: 'EFD Contribuições' },
    { id: 'reinf',       icon: 'file-code',       label: 'EFD-Reinf' },
    { id: 'dctfweb',     icon: 'file-check',      label: 'DCTFWeb' },
    { id: 'ecf',         icon: 'calculator',      label: 'ECF' },
    { id: 'pacote',      icon: 'archive',         label: 'Pacote do Contador' },
    { id: 'portal',      icon: 'link-2',          label: 'Portal Contábil' },
  ];
  return `<div class="flex gap-1 overflow-x-auto pb-1 flex-wrap">
    ${tabs.map(t => `
      <button onclick="switchSpedTab('${t.id}')" id="sped-tab-${t.id}"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition whitespace-nowrap
          ${spedSubTab === t.id
            ? 'bg-amber-500 text-white'
            : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'}">
        <i data-lucide="${t.icon}" class="w-3.5 h-3.5"></i>${t.label}
      </button>`).join('')}
  </div>`;
}

function switchSpedTab(id) {
  spedSubTab = id;
  const el = document.getElementById('sped-subtab-content');
  if (!el) return;
  if (id === 'efd')          renderSpedEfd(el);
  else if (id === 'efd_contrib') renderSpedEfdContrib(el);
  else if (id === 'reinf')   renderSpedReinf(el);
  else if (id === 'dctfweb') renderSpedDctfweb(el);
  else if (id === 'ecf')     renderSpedEcf(el);
  else if (id === 'pacote')  renderSpedPacote(el);
  else if (id === 'portal')  renderSpedPortal(el);
  if (window.lucide) lucide.createIcons();
  ['efd','efd_contrib','reinf','dctfweb','ecf','pacote', 'portal'].forEach(t => {
    const btn = document.getElementById(`sped-tab-${t}`);
    if (!btn) return;
    if (t === id) btn.className = btn.className.replace(/bg-white[^\s]*/g, 'bg-amber-500 text-white').replace('dark:bg-slate-900', '').replace('border border-slate-200 dark:border-slate-800', '').replace('text-slate-600 dark:text-slate-300', '').replace('hover:bg-slate-50 dark:hover:bg-slate-800', '');
    else { btn.className = btn.className.replace('bg-amber-500 text-white', 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'); }
  });
}

// ── EFD ICMS/IPI ─────────────────────────────────────────────
function renderSpedEfd(el) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm   = String(today.getMonth() + 1).padStart(2, '0');
  const firstDay = `${yyyy}-${mm}-01`;
  const lastDay  = `${yyyy}-${mm}-${new Date(yyyy, today.getMonth() + 1, 0).getDate()}`;

  el.innerHTML = `
    <div class="space-y-6">
      <!-- Período -->
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
        <h3 class="text-sm font-bold text-slate-700 dark:text-slate-200 mb-4 flex items-center gap-2">
          <i data-lucide="calendar-range" class="w-4 h-4 text-amber-400"></i>
          Período de Apuração
        </h3>
        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            ${lblSped('Data Inicial')}
            <input type="date" id="sped-start" value="${firstDay}" class="${inputSped()}" />
          </div>
          <div>
            ${lblSped('Data Final')}
            <input type="date" id="sped-end" value="${lastDay}" class="${inputSped()}" />
          </div>
        </div>
        <button onclick="loadSpedPreview()" class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-amber-50 dark:hover:bg-amber-900/20 text-slate-700 dark:text-slate-200 text-sm font-semibold transition border border-slate-200 dark:border-slate-700 hover:border-amber-400">
          <i data-lucide="eye" class="w-4 h-4 text-amber-400"></i>
          Pré-visualizar Período
        </button>
      </div>

      <!-- Preview KPIs -->
      <div id="sped-preview-kpis" class="hidden">
        <div id="sped-kpi-grid" class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4"></div>
        <div class="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/40 rounded-xl p-4 flex items-start gap-3 mb-4">
          <i data-lucide="info" class="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0"></i>
          <div class="text-xs text-amber-700 dark:text-amber-300">
            O arquivo EFD segue o layout <strong>EFD ICMS/IPI (versão 018)</strong> conforme Guia Prático da RFB.
            Inclui blocos 0 (Abertura), C (Documentos Fiscais NF-e), E (Apuração ICMS) e 9 (Encerramento).
          </div>
        </div>
        ${btnAmber('downloadSpedEfd()', 'download', 'Gerar e Baixar EFD ICMS/IPI (.txt)')}
      </div>

      <!-- Empty state -->
      <div id="sped-empty-hint" class="bg-white dark:bg-slate-900 border border-dashed border-slate-300 dark:border-slate-700 rounded-2xl p-10 text-center">
        <i data-lucide="file-code-2" class="w-10 h-10 text-amber-300 mx-auto mb-3"></i>
        <div class="text-sm text-slate-500">Clique em <strong>Pré-visualizar Período</strong> para ver as notas e gerar o SPED Fiscal.</div>
      </div>
    </div>`;
  if (window.lucide) lucide.createIcons();
}

async function loadSpedPreview() {
  const start = document.getElementById('sped-start')?.value;
  const end   = document.getElementById('sped-end')?.value;
  if (!start || !end) return showToast('Informe o período.', 'warning');
  if (start > end)    return showToast('Data inicial maior que final.', 'warning');

  try {
    const res = await fetch(`/api/reports/sped-preview?start_date=${start}&end_date=${end}`);
    if (!res.ok) throw new Error(await res.text());
    spedPreview = await res.json();

    document.getElementById('sped-empty-hint')?.classList.add('hidden');
    const kpiEl = document.getElementById('sped-kpi-grid');
    const pvEl  = document.getElementById('sped-preview-kpis');
    if (!kpiEl || !pvEl) return;

    const p = spedPreview;
    kpiEl.innerHTML = [
      kpiSped('Notas Fiscais (NF-e)', p.count_nfe, `${p.start_date} → ${p.end_date}`, 'receipt', 'text-amber-500'),
      kpiSped('Faturamento Bruto', fBRL5(p.total_faturamento), p.company?.razao_social || '', 'trending-up', 'text-emerald-500'),
      kpiSped('ICMS Apurado', fBRL5(p.total_icms), 'Operações próprias', 'landmark', 'text-blue-500'),
      kpiSped('PIS Apurado', fBRL5(p.total_pis), 'Conf. regime tributário', 'percent', 'text-indigo-500'),
      kpiSped('COFINS Apurado', fBRL5(p.total_cofins), 'Conf. regime tributário', 'percent', 'text-purple-500'),
      kpiSped('Total de Impostos', fBRL5(p.total_impostos), 'ICMS + PIS + COFINS', 'calculator', 'text-rose-500'),
    ].join('');
    pvEl.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    showToast('Erro ao carregar preview: ' + e.message, 'error');
  }
}

async function downloadSpedEfd() {
  const start = document.getElementById('sped-start')?.value;
  const end   = document.getElementById('sped-end')?.value;
  if (!start || !end) return showToast('Informe o período.', 'warning');
  showToast('Gerando arquivo EFD ICMS/IPI...', 'info');
  window.location.href = `/api/reports/sped-fiscal?start_date=${start}&end_date=${end}`;
}

// ── Pacote do Contador ────────────────────────────────────────
function renderSpedPacote(el) {
  const today = new Date();
  const thisMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;

  el.innerHTML = `
    <div class="space-y-6">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
        <h3 class="text-sm font-bold text-slate-700 dark:text-slate-200 mb-1 flex items-center gap-2">
          <i data-lucide="archive" class="w-4 h-4 text-amber-400"></i>
          Pacote Mensal do Contador
        </h3>
        <p class="text-xs text-slate-500 mb-5">
          Exporta em um único arquivo <strong>.zip</strong>: todos os XMLs de NF-e/NFC-e/NFS-e do mês,
          o arquivo SPED Fiscal (EFD ICMS/IPI) e o resumo de apuração de impostos em JSON.
        </p>
        <div class="max-w-xs mb-5">
          ${lblSped('Competência (mês/ano)')}
          <input type="month" id="pacote-month" value="${thisMonth}" class="${inputSped()}" />
        </div>

        <div class="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 mb-5 text-xs text-slate-500 space-y-1.5">
          <div class="flex items-center gap-2"><i data-lucide="file-xml" class="w-3.5 h-3.5 text-blue-400"></i> <span>XMLs de todas as NF-e/NFC-e/NFS-e autorizadas no mês</span></div>
          <div class="flex items-center gap-2"><i data-lucide="file-code-2" class="w-3.5 h-3.5 text-amber-400"></i> <span>SPED Fiscal — EFD ICMS/IPI (layout 018)</span></div>
          <div class="flex items-center gap-2"><i data-lucide="file-json-2" class="w-3.5 h-3.5 text-emerald-400"></i> <span>Resumo de apuração: faturamento, ICMS, PIS, COFINS, ISS</span></div>
        </div>

        ${btnAmber('downloadPacoteContador()', 'archive', 'Baixar Pacote do Contador (.zip)')}
      </div>

      <div class="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/40 rounded-2xl p-5">
        <div class="flex items-start gap-3">
          <i data-lucide="shield-check" class="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0"></i>
          <div>
            <div class="text-sm font-bold text-amber-700 dark:text-amber-300 mb-1">Dica para o Escritório Contábil</div>
            <div class="text-xs text-amber-600 dark:text-amber-400">
              Envie este pacote mensalmente ao seu contador. Ele contém todos os dados necessários para
              a apuração do ICMS, PIS, COFINS e para a escrituração no SPED Fiscal.
              Para acesso direto sem login, use o <strong>Portal Contábil</strong> na aba ao lado.
            </div>
          </div>
        </div>
      </div>
    </div>`;
  if (window.lucide) lucide.createIcons();
}

async function downloadPacoteContador() {
  const month = document.getElementById('pacote-month')?.value;
  if (!month) return showToast('Selecione a competência.', 'warning');
  showToast('Gerando pacote do contador...', 'info');
  window.location.href = `/api/reports/fiscal-package?month=${month}`;
}

// ── Portal Contábil ───────────────────────────────────────────
function renderSpedPortal(el) {
  el.innerHTML = `
    <div class="space-y-6">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
        <h3 class="text-sm font-bold text-slate-700 dark:text-slate-200 mb-1 flex items-center gap-2">
          <i data-lucide="link-2" class="w-4 h-4 text-amber-400"></i>
          Portal do Contador (Acesso Externo)
        </h3>
        <p class="text-xs text-slate-500 mb-5">
          Gere um link exclusivo para o seu escritório contábil. Com ele, o contador acessa o resumo fiscal
          e faz download do pacote sem precisar de login no sistema.
        </p>
        <button onclick="loadPortalLink()" class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-amber-50 dark:hover:bg-amber-900/20 text-slate-700 dark:text-slate-200 text-sm font-semibold transition border border-slate-200 dark:border-slate-700 hover:border-amber-400">
          <i data-lucide="key-round" class="w-4 h-4 text-amber-400"></i>
          Carregar Link do Portal
        </button>
      </div>

      <div id="portal-link-area" class="hidden bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
        <div class="text-xs font-semibold text-slate-500 mb-2">Link de acesso do contador:</div>
        <div class="flex gap-2 items-center">
          <input id="portal-link-input" readonly class="${inputSped()} font-mono text-xs text-amber-600 dark:text-amber-400" />
          <button onclick="copyPortalLink()" class="flex-shrink-0 p-2.5 rounded-xl bg-amber-100 dark:bg-amber-900/30 hover:bg-amber-200 dark:hover:bg-amber-800/40 text-amber-600 dark:text-amber-300 transition">
            <i data-lucide="copy" class="w-4 h-4"></i>
          </button>
        </div>
        <div class="mt-3 text-[11px] text-slate-400 flex items-center gap-1.5">
          <i data-lucide="shield-alert" class="w-3 h-3 text-amber-400"></i>
          Compartilhe apenas com seu escritório contábil. O token dá acesso a dados fiscais da empresa.
        </div>
      </div>

      <div id="portal-data" class="hidden"></div>
    </div>`;
  if (window.lucide) lucide.createIcons();
}

async function loadPortalLink() {
  try {
    const res = await fetch('/api/me');
    const user = await res.json();
    const companyId = user?.company_id || 1;
    const link = `${window.location.origin}/api/portal/accountant/${companyId}`;
    document.getElementById('portal-link-input').value = link;
    document.getElementById('portal-link-area')?.classList.remove('hidden');

    // Carregar dados do portal
    const pRes = await fetch(`/api/portal/accountant/${companyId}`);
    if (!pRes.ok) return;
    const pData = await pRes.json();
    const pEl = document.getElementById('portal-data');
    if (!pEl) return;

    pEl.innerHTML = `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
        <div class="text-sm font-bold text-slate-700 dark:text-slate-200 mb-4 flex items-center gap-2">
          <i data-lucide="building-2" class="w-4 h-4 text-amber-400"></i>
          Prévia do Portal (mês atual)
        </div>
        <div class="grid grid-cols-2 gap-4">
          ${kpiSped('NF-e no Mês', pData.invoices_count, pData.period, 'receipt', 'text-amber-500')}
          ${kpiSped('Faturado no Mês', fBRL5(pData.total_billed), pData.company?.razao_social || '', 'trending-up', 'text-emerald-500')}
        </div>
      </div>`;
    pEl.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    showToast('Erro ao carregar portal: ' + e.message, 'error');
  }
}

function copyPortalLink() {
  const inp = document.getElementById('portal-link-input');
  if (!inp) return;
  navigator.clipboard.writeText(inp.value).then(() => showToast('Link copiado!', 'success'));
}

// ── Entry point ───────────────────────────────────────────────
async function renderSped(container) {
  spedSubTab = 'efd';
  spedPreview = null;
  container.innerHTML = `
    <div class="p-6 space-y-6">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 class="text-xl font-extrabold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="file-code-2" class="w-5 h-5 text-amber-400"></i>
            SPED Fiscal
          </h2>
          <p class="text-xs text-slate-500 mt-0.5">EFD ICMS/IPI · EFD Contribuições · EFD-Reinf · DCTFWeb · ECF</p>
        </div>
      </div>
      ${spedTabs()}
      <div id="sped-subtab-content"></div>
    </div>`;
  if (window.lucide) lucide.createIcons();
  renderSpedEfd(document.getElementById('sped-subtab-content'));
}

// ── EFD Contribuições (PIS/COFINS) ───────────────────────────
async function renderSpedEfdContrib(el) {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  el.innerHTML = `<div class="space-y-5">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-4">EFD Contribuições — PIS/COFINS</div>
        ${lblSped('Data Início')}<input type="date" id="efdcont-start" class="${inputSped()} mb-3" value="${yyyy}-${mm}-01" />
        ${lblSped('Data Fim')}<input type="date" id="efdcont-end" class="${inputSped()} mb-4" value="${yyyy}-${mm}-${new Date(yyyy,today.getMonth()+1,0).getDate()}" />
        <div class="flex gap-2 flex-wrap">
          ${btnAmber('spedContribPreview()', 'bar-chart-2', 'Pré-visualizar')}
          ${btnAmber('spedContribDownload()', 'download', 'Download .txt')}
        </div>
      </div>
      <div id="efdcont-result" class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="text-xs text-slate-400 text-center py-8">Clique em Pré-visualizar para ver os KPIs do período.</div>
      </div>
    </div>
  </div>`;
  if (window.lucide) lucide.createIcons();
}

async function spedContribPreview() {
  const s = document.getElementById('efdcont-start')?.value;
  const e = document.getElementById('efdcont-end')?.value;
  const data = await apiFetch(`/api/reports/efd-contribuicoes-preview?start_date=${s}&end_date=${e}`).catch(() => null);
  const el = document.getElementById('efdcont-result');
  if (!el) return;
  if (!data) { el.innerHTML = '<div class="text-rose-400 text-xs text-center py-8">Erro ao carregar.</div>'; return; }
  el.innerHTML = `<div class="space-y-3">
    <div class="font-semibold text-sm text-slate-700 dark:text-slate-200">EFD Contribuições — Período ${s} a ${e}</div>
    ${[
      ['Receita Bruta', fBRL5(data.total_receita), 'text-blue-400'],
      ['PIS Saída', fBRL5(data.pis_saida), 'text-rose-400'],
      ['COFINS Saída', fBRL5(data.cofins_saida), 'text-rose-400'],
      ['Total Compras', fBRL5(data.total_compras), 'text-slate-400'],
      ['PIS Crédito Est.', fBRL5(data.pis_credito_estimado), 'text-emerald-400'],
      ['COFINS Crédito Est.', fBRL5(data.cofins_credito_estimado), 'text-emerald-400'],
      ['PIS a Recolher', fBRL5(data.pis_a_recolher), 'text-amber-400'],
      ['COFINS a Recolher', fBRL5(data.cofins_a_recolher), 'text-amber-400'],
    ].map(([l,v,c])=>`<div class="flex justify-between border-b border-slate-100 dark:border-slate-800 py-1.5 last:border-0"><span class="text-xs text-slate-400">${l}</span><span class="font-mono font-semibold text-xs ${c}">${v}</span></div>`).join('')}
    <div class="text-[10px] text-slate-400 pt-1">Apuração: <strong>${data.tipo_apuracao}</strong> · ${data.count_nfe} NF-e</div>
  </div>`;
}

async function spedContribDownload() {
  const s = document.getElementById('efdcont-start')?.value;
  const e = document.getElementById('efdcont-end')?.value;
  const url = `/api/reports/efd-contribuicoes?start_date=${s}&end_date=${e}`;
  const a = document.createElement('a'); a.href = url; a.click();
}

// ── EFD-Reinf ─────────────────────────────────────────────────
async function renderSpedReinf(el) {
  const today = new Date();
  const comp = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`;
  el.innerHTML = `<div class="space-y-5">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-4">EFD-Reinf — Retenções na Fonte</div>
        ${lblSped('Competência (AAAA-MM)')}
        <input type="month" id="reinf-comp" class="${inputSped()} mb-4" value="${comp}" />
        ${btnAmber('reinfPreview()', 'bar-chart-2', 'Pré-visualizar')}
      </div>
      <div id="reinf-result" class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="text-xs text-slate-400 text-center py-8">Selecione a competência e clique em Pré-visualizar.</div>
      </div>
    </div>
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
      <div class="font-semibold text-sm text-slate-700 dark:text-slate-200 mb-3">Eventos EFD-Reinf</div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        ${[
          ['R-1000','Informações do Contribuinte','Obrigatório no início'],
          ['R-2010','Serviços Tomados (INSS)','Retenções de PJ'],
          ['R-4010','Pagamentos PF (IRRF)','Rendimentos à PF'],
          ['R-4020','Pagamentos PJ','Retenções CSLL/PIS/COFINS'],
          ['R-9000','Fechamento','Encerra os periódicos'],
          ['R-1070','Proc. Judicial/Admin.','Suspensão do crédito'],
        ].map(([ev,name,desc])=>`
          <div class="border border-slate-100 dark:border-slate-800 rounded-xl p-3">
            <div class="font-mono font-bold text-xs text-indigo-400">${ev}</div>
            <div class="font-semibold text-xs text-slate-700 dark:text-slate-200 mt-1">${name}</div>
            <div class="text-[10px] text-slate-400">${desc}</div>
          </div>`).join('')}
      </div>
    </div>
  </div>`;
  if (window.lucide) lucide.createIcons();
}

async function reinfPreview() {
  const comp = document.getElementById('reinf-comp')?.value;
  const data = await apiFetch(`/api/reports/efd-reinf-preview?competencia=${comp}`).catch(() => null);
  const el = document.getElementById('reinf-result');
  if (!el) return;
  if (!data) { el.innerHTML = '<div class="text-rose-400 text-xs text-center py-8">Erro ao carregar.</div>'; return; }
  const eventos = Object.entries(data.eventos || {});
  el.innerHTML = `<div class="space-y-2">
    <div class="font-semibold text-sm text-slate-700 dark:text-slate-200">EFD-Reinf — ${comp}</div>
    <div class="text-xs text-slate-400">${data.razao_social} · ${data.cnpj}</div>
    ${eventos.map(([k,v])=>`<div class="flex items-start gap-2 border-b border-slate-100 dark:border-slate-800 py-2 last:border-0">
      <span class="font-mono text-[10px] font-bold text-indigo-400 w-14 shrink-0">${k}</span>
      <div class="flex-1 text-xs"><div class="text-slate-600 dark:text-slate-300">${v.descricao}</div>
        ${v.valor !== undefined ? `<div class="text-slate-400">R$ ${parseFloat(v.valor||0).toLocaleString('pt-BR')}</div>` : ''}
        ${v.ir_retido !== undefined ? `<div class="text-slate-400">IR: R$ ${parseFloat(v.ir_retido||0).toLocaleString('pt-BR')}</div>` : ''}
        ${v.status ? `<div class="text-amber-400">${v.status}</div>` : ''}
      </div>
    </div>`).join('')}
    <div class="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-3 text-xs text-indigo-400">
      Total retenções estimadas: <strong>${fBRL5(data.total_retencoes_estimadas)}</strong> · Vence: ${data.vencimento?.split('-').reverse().join('/')||'-'}
    </div>
  </div>`;
}

// ── DCTFWeb ───────────────────────────────────────────────────
async function renderSpedDctfweb(el) {
  const today = new Date();
  const comp = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`;
  el.innerHTML = `<div class="space-y-5">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-4">DCTFWeb — Declaração de Débitos</div>
        ${lblSped('Competência (AAAA-MM)')}<input type="month" id="dctf-comp" class="${inputSped()} mb-4" value="${comp}" />
        ${btnAmber('dctfPreview()', 'bar-chart-2', 'Pré-visualizar')}
      </div>
      <div id="dctf-result" class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="text-xs text-slate-400 text-center py-8">Selecione a competência e clique em Pré-visualizar.</div>
      </div>
    </div>
  </div>`;
  if (window.lucide) lucide.createIcons();
}

async function dctfPreview() {
  const comp = document.getElementById('dctf-comp')?.value;
  const data = await apiFetch(`/api/reports/dctfweb-preview?competencia=${comp}`).catch(() => null);
  const el = document.getElementById('dctf-result');
  if (!el) return;
  if (!data) { el.innerHTML = '<div class="text-rose-400 text-xs text-center py-8">Erro ao carregar.</div>'; return; }
  const debitos = Object.entries(data.debitos || {});
  el.innerHTML = `<div class="space-y-2">
    <div class="font-semibold text-sm text-slate-700 dark:text-slate-200">DCTFWeb — ${comp}</div>
    <div class="text-xs text-slate-400">${data.razao_social} · ${data.cnpj}</div>
    <div class="font-semibold text-xs text-slate-500 mt-3 mb-1">Débitos</div>
    ${debitos.map(([k,v])=>`<div class="flex justify-between border-b border-slate-100 dark:border-slate-800 py-1.5 last:border-0">
      <span class="text-xs text-slate-400">${k.replace(/_/g,' ')}</span>
      <span class="font-mono text-xs font-bold text-rose-400">${fBRL5(v)}</span>
    </div>`).join('')}
    <div class="flex justify-between py-2 border-t border-slate-200 dark:border-slate-700">
      <span class="text-sm font-bold text-slate-600 dark:text-slate-200">Total Débitos</span>
      <span class="font-mono font-bold text-rose-400">${fBRL5(data.total_debitos)}</span>
    </div>
    <div class="flex justify-between py-1"><span class="text-xs text-slate-400">FGTS (separado)</span><span class="font-mono text-xs">${fBRL5(data.total_fgts)}</span></div>
    <div class="bg-blue-500/10 border border-blue-500/20 rounded-xl p-3 text-xs space-y-1 mt-2">
      <div class="text-blue-400">Venc. DARF: <strong>${data.vencimento_darf?.split('-').reverse().join('/')||'-'}</strong></div>
      <div class="text-slate-400">Venc. FGTS: ${data.vencimento_fgts?.split('-').reverse().join('/')||'-'}</div>
      <div class="text-slate-400 text-[10px]">${data.observacao}</div>
    </div>
  </div>`;
}

// ── ECF ───────────────────────────────────────────────────────
async function renderSpedEcf(el) {
  const year = new Date().getFullYear();
  el.innerHTML = `<div class="space-y-5">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="font-semibold text-slate-700 dark:text-slate-200 text-sm mb-4">ECF — Escrituração Contábil Fiscal (IRPJ/CSLL)</div>
        ${lblSped('Ano-Calendário')}<input type="number" id="ecf-year" class="${inputSped()} mb-4" value="${year - 1}" min="2020" max="${year}" />
        ${btnAmber('ecfPreview()', 'bar-chart-2', 'Pré-visualizar')}
      </div>
      <div id="ecf-result" class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="text-xs text-slate-400 text-center py-8">Selecione o ano e clique em Pré-visualizar.</div>
      </div>
    </div>
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
      <div class="font-semibold text-sm text-slate-700 dark:text-slate-200 mb-3">Blocos ECF (Layout RFB)</div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        ${[['0','Abertura','Identificação da empresa'],['C','Lucro Contábil','Resultado antes ajustes'],
          ['E','LALUR','Adições / Exclusões'],['J','IRPJ / CSLL','Cálculo final'],
          ['K','Mapeamento','Plano Referencial'],['L','Lucro Real','Base definitiva'],
          ['M','CSLL','Apuração separada'],['P','Lucro Presumido','Para LP/SN'],
        ].map(([b,n,d])=>`<div class="border border-slate-100 dark:border-slate-800 rounded-xl p-3">
          <div class="font-mono font-bold text-fuchsia-400 text-sm">Bloco ${b}</div>
          <div class="font-semibold text-slate-700 dark:text-slate-200 mt-1">${n}</div>
          <div class="text-slate-400 text-[10px]">${d}</div>
        </div>`).join('')}
      </div>
    </div>
  </div>`;
  if (window.lucide) lucide.createIcons();
}

async function ecfPreview() {
  const year = parseInt(document.getElementById('ecf-year')?.value) || new Date().getFullYear() - 1;
  const data = await apiFetch(`/api/reports/ecf-preview?year=${year}`).catch(() => null);
  const el = document.getElementById('ecf-result');
  if (!el) return;
  if (!data) { el.innerHTML = '<div class="text-rose-400 text-xs text-center py-8">Erro ao carregar.</div>'; return; }
  el.innerHTML = `<div class="space-y-2">
    <div class="font-semibold text-sm text-slate-700 dark:text-slate-200">ECF ${year}</div>
    <div class="text-xs text-slate-400">${data.razao_social} · ${data.cnpj}</div>
    <div class="text-xs font-semibold text-fuchsia-400">Regime: ${data.regime}</div>
    ${[
      ['Receita Bruta', fBRL5(data.receita_bruta_total), 'text-blue-400'],
      ['Despesas Totais', fBRL5(data.total_despesas), 'text-rose-400'],
      ['Lucro Bruto Contábil', fBRL5(data.lucro_bruto_contabil), 'text-emerald-400'],
      ['Base IRPJ', fBRL5(data.base_calculo_irpj), 'text-slate-400'],
      ['IRPJ 15%', fBRL5(data.irpj_normal_15pct), 'text-fuchsia-400'],
      ['IRPJ Adicional 10%', fBRL5(data.irpj_adicional_10pct), 'text-fuchsia-400'],
      ['CSLL 9%', fBRL5(data.csll_total), 'text-fuchsia-400'],
    ].map(([l,v,c])=>`<div class="flex justify-between border-b border-slate-100 dark:border-slate-800 py-1.5 last:border-0">
      <span class="text-xs text-slate-400">${l}</span><span class="font-mono text-xs font-bold ${c}">${v}</span>
    </div>`).join('')}
    <div class="flex justify-between py-2 border-t border-slate-200 dark:border-slate-700">
      <span class="text-sm font-bold text-slate-600 dark:text-slate-200">Total IRPJ + CSLL</span>
      <span class="font-mono font-bold text-fuchsia-400">${fBRL5(data.total_impostos_federais)}</span>
    </div>
    <div class="bg-fuchsia-500/10 border border-fuchsia-500/20 rounded-xl p-3 text-xs text-fuchsia-400">
      Prazo entrega: <strong>${data.prazo_entrega?.split('-').reverse().join('/')||'-'}</strong>
      <div class="text-slate-400 text-[10px] mt-1">${data.observacao}</div>
    </div>
  </div>`;
}
