// ============================================================
// COMPRAS — Cortex ERP Pro+
// Pedidos de Compra · Recebimento · Importar XML NF-e
// ============================================================

function authHeaders() { return {}; }

let purchSubTab   = 'pedidos';
let purchOrders   = [];
let purchSuppliers = [];
let purchProducts  = [];

// ── helpers ──────────────────────────────────────────────────
const fBRL3  = v => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fDate3 = s => s ? s.slice(0, 10).split('-').reverse().join('/') : '-';
const card3  = html => `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs">${html}</div>`;

const STATUS_LABEL = {
  rascunho:  'Rascunho',
  enviado:   'Enviado',
  aprovado:  'Aprovado',
  recebido:  'Recebido',
  cancelado: 'Cancelado',
};
const STATUS_CLS = {
  rascunho:  'text-slate-500 bg-slate-100 dark:bg-slate-800',
  enviado:   'text-blue-600 bg-blue-50 dark:bg-blue-900/30',
  aprovado:  'text-violet-600 bg-violet-50 dark:bg-violet-900/30',
  recebido:  'text-emerald-600 bg-emerald-50 dark:bg-emerald-900/30',
  cancelado: 'text-rose-500 bg-rose-50 dark:bg-rose-900/20',
};

function statusBadge(s) {
  const cls = STATUS_CLS[s] || STATUS_CLS.rascunho;
  return `<span class="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${cls}">${STATUS_LABEL[s] || s}</span>`;
}

function kpiPurch(label, value, sub, icon, color) {
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
    <div class="flex items-center justify-between text-slate-500 text-xs font-semibold mb-2">
      <span>${label}</span><i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
    </div>
    <div class="text-2xl font-extrabold ${color}">${value}</div>
    ${sub ? `<div class="text-[11px] text-slate-400 mt-1">${sub}</div>` : ''}
  </div>`;
}

function inputP() {
  return 'w-full text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-500';
}
function lblP(t) {
  return `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${t}</label>`;
}

// ── sub-tabs ─────────────────────────────────────────────────
function purchTabs() {
  const tabs = [
    { id: 'pedidos',  icon: 'shopping-cart',  label: 'Pedidos de Compra' },
    { id: 'xml',      icon: 'file-code',       label: 'Importar XML NF-e' },
  ];
  return `<div class="flex gap-1 overflow-x-auto pb-1 flex-wrap">
    ${tabs.map(t => `
      <button onclick="switchPurchTab('${t.id}')" id="purch-tab-${t.id}"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition whitespace-nowrap
          ${purchSubTab === t.id
            ? 'bg-orange-500 text-white'
            : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'}">
        <i data-lucide="${t.icon}" class="w-3.5 h-3.5"></i>${t.label}
      </button>`).join('')}
  </div>`;
}

// ── entry point ───────────────────────────────────────────────
async function renderPurchases(container) {
  await Promise.all([
    fetch('/api/purchase-orders', { headers: authHeaders() }).then(r => r.json()).then(d => { purchOrders = Array.isArray(d) ? d : []; }).catch(() => { purchOrders = []; }),
    fetch('/api/contacts?type=fornecedor', { headers: authHeaders() }).then(r => r.json()).then(d => { purchSuppliers = Array.isArray(d) ? d : []; }).catch(() => { purchSuppliers = []; }),
    fetch('/api/products', { headers: authHeaders() }).then(r => r.json()).then(d => { purchProducts = Array.isArray(d?.items || d) ? (d?.items || d) : []; }).catch(() => { purchProducts = []; }),
  ]);

  container.innerHTML = `
    <div id="purch-tabs-bar" class="mb-4">${purchTabs()}</div>
    <div id="purch-body"></div>`;

  await switchPurchTab(purchSubTab, true);
  if (window.lucide) lucide.createIcons();
}

async function switchPurchTab(tab, noRebuild = false) {
  purchSubTab = tab;
  if (!noRebuild) {
    const bar = document.getElementById('purch-tabs-bar');
    if (bar) { bar.innerHTML = purchTabs(); if (window.lucide) lucide.createIcons(); }
  }
  const body = document.getElementById('purch-body');
  if (!body) return;
  body.innerHTML = `<div class="flex items-center justify-center p-10 text-slate-400">
    <div class="animate-spin rounded-full h-7 w-7 border-b-2 border-orange-500 mr-3"></div>Carregando...</div>`;

  if (tab === 'pedidos') await renderPedidos(body);
  else if (tab === 'xml') await renderXmlImport(body);
  if (window.lucide) lucide.createIcons();
}

// ── 1. PEDIDOS DE COMPRA ──────────────────────────────────────
let purchFilter = 'todos';

async function renderPedidos(el, filter) {
  if (filter !== undefined) purchFilter = filter;

  try {
    const qs = purchFilter && purchFilter !== 'todos' ? `?status=${purchFilter}` : '';
    const r = await fetch(`/api/purchase-orders${qs}`, { headers: authHeaders() });
    purchOrders = await r.json();
  } catch { purchOrders = []; }

  const totalVal  = purchOrders.reduce((s, o) => s + parseFloat(o.total_amount || 0), 0);
  const pendentes = purchOrders.filter(o => !['recebido', 'cancelado'].includes(o.status));
  const recebidos = purchOrders.filter(o => o.status === 'recebido');
  const valPend   = pendentes.reduce((s, o) => s + parseFloat(o.total_amount || 0), 0);
  const valReceb  = recebidos.reduce((s, o) => s + parseFloat(o.total_amount || 0), 0);

  const filterBtns = ['todos', 'rascunho', 'enviado', 'aprovado', 'recebido', 'cancelado'].map(s => `
    <button onclick="renderPedidos(document.getElementById('purch-body'), '${s}')"
      class="px-3 py-1.5 rounded-xl text-xs font-semibold transition whitespace-nowrap
        ${purchFilter === s
          ? 'bg-orange-500 text-white'
          : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50'}">
      ${s === 'todos' ? 'Todos' : STATUS_LABEL[s]}
    </button>`).join('');

  const rows = purchOrders.map(o => `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
      <td class="px-4 py-3 text-sm font-mono font-bold text-slate-700 dark:text-slate-200">#${o.order_number}</td>
      <td class="px-4 py-3 text-sm text-slate-700 dark:text-slate-200">${o.supplier_name || '-'}</td>
      <td class="px-4 py-3 text-xs text-slate-400">${fDate3(o.expected_delivery_date)}</td>
      <td class="px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-200">${fBRL3(o.total_amount)}</td>
      <td class="px-4 py-3">${statusBadge(o.status)}</td>
      <td class="px-4 py-3 text-xs text-slate-400">${o.payment_terms || '-'}</td>
      <td class="px-4 py-3 text-right whitespace-nowrap">
        <button onclick="openPurchDetail(${o.id})" class="text-xs text-indigo-500 hover:underline mr-2">Detalhes</button>
        ${o.status === 'rascunho' ? `<button onclick="changePurchStatus(${o.id},'enviado')" class="text-xs text-blue-500 hover:underline mr-2">Enviar</button>` : ''}
        ${o.status === 'enviado'  ? `<button onclick="changePurchStatus(${o.id},'aprovado')" class="text-xs text-violet-500 hover:underline mr-2">Aprovar</button>` : ''}
        ${['aprovado','enviado'].includes(o.status) ? `<button onclick="receivePurchOrder(${o.id}, ${o.order_number})" class="text-xs text-emerald-600 font-semibold hover:underline mr-2">Receber ✓</button>` : ''}
        ${['rascunho','enviado'].includes(o.status) ? `<button onclick="changePurchStatus(${o.id},'cancelado')" class="text-xs text-rose-500 hover:underline">Cancelar</button>` : ''}
      </td>
    </tr>`).join('');

  el.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
      ${kpiPurch('Total de Pedidos', purchOrders.length, `filtro: ${purchFilter}`, 'shopping-cart', 'text-orange-500')}
      ${kpiPurch('Valor Pendente', fBRL3(valPend), `${pendentes.length} pedido(s)`, 'clock', 'text-amber-500')}
      ${kpiPurch('Total Recebido', fBRL3(valReceb), `${recebidos.length} pedido(s)`, 'package-check', 'text-emerald-600')}
    </div>
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div class="flex gap-1 flex-wrap">${filterBtns}</div>
      <button onclick="openNewPurchModal()"
        class="bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2">
        <i data-lucide="plus" class="w-3.5 h-3.5"></i> Novo Pedido
      </button>
    </div>
    ${card3(`
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left font-semibold">Nº</th>
            <th class="px-4 py-2 text-left font-semibold">Fornecedor</th>
            <th class="px-4 py-2 text-left font-semibold">Prev. Entrega</th>
            <th class="px-4 py-2 text-left font-semibold">Total</th>
            <th class="px-4 py-2 text-left font-semibold">Status</th>
            <th class="px-4 py-2 text-left font-semibold">Condições</th>
            <th class="px-4 py-2 text-right font-semibold">Ações</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="7" class="px-4 py-8 text-center text-slate-400 text-xs">Nenhum pedido encontrado.</td></tr>'}</tbody>
        </table>
      </div>`)}
    <div id="purch-detail-area" class="mt-6"></div>`;
}

async function openPurchDetail(id) {
  const area = document.getElementById('purch-detail-area');
  if (!area) return;
  area.innerHTML = '<div class="text-xs text-slate-400 p-4">Carregando...</div>';
  try {
    const r = await fetch(`/api/purchase-orders/${id}`, { headers: authHeaders() });
    const o = await r.json();
    const itemRows = (o.items || []).map(it => `
      <tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200">${it.product_name}</td>
        <td class="px-4 py-2.5 text-xs font-mono text-slate-400">${it.sku || '-'}</td>
        <td class="px-4 py-2.5 text-sm text-right">${parseFloat(it.quantity || 0).toLocaleString('pt-BR')}</td>
        <td class="px-4 py-2.5 text-sm text-right">${fBRL3(it.unit_price)}</td>
        <td class="px-4 py-2.5 text-sm text-right text-rose-400">${it.discount > 0 ? '-' + fBRL3(it.discount) : '-'}</td>
        <td class="px-4 py-2.5 text-sm font-semibold text-right">${fBRL3(it.total_price)}</td>
      </tr>`).join('');

    area.innerHTML = `
      <div class="mb-3 flex items-center justify-between">
        <h3 class="font-bold text-slate-700 dark:text-slate-200">
          Pedido #${o.order_number} — ${o.supplier_name || '-'}
          <span class="ml-2">${statusBadge(o.status)}</span>
        </h3>
        <button onclick="document.getElementById('purch-detail-area').innerHTML=''"
          class="text-xs text-slate-400 hover:text-slate-600">Fechar ✕</button>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-xs text-slate-500">
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">CNPJ Fornecedor</span><br>${o.supplier_cnpj || '-'}</div>
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">Prev. Entrega</span><br>${fDate3(o.expected_delivery_date)}</div>
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">Condições</span><br>${o.payment_terms || '-'}</div>
        <div><span class="font-semibold text-slate-600 dark:text-slate-300">Recebido em</span><br>${o.received_at ? fDate3(o.received_at) : '-'}</div>
      </div>
      ${card3(`
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
              <th class="px-4 py-2 text-left font-semibold">Produto</th>
              <th class="px-4 py-2 text-left font-semibold">SKU</th>
              <th class="px-4 py-2 text-right font-semibold">Qtd</th>
              <th class="px-4 py-2 text-right font-semibold">Preço Unit.</th>
              <th class="px-4 py-2 text-right font-semibold">Desconto</th>
              <th class="px-4 py-2 text-right font-semibold">Total</th>
            </tr></thead>
            <tbody>${itemRows}</tbody>
            <tfoot><tr class="border-t-2 border-slate-200 dark:border-slate-700">
              <td colspan="5" class="px-4 py-3 text-sm font-bold text-slate-700 dark:text-slate-200 text-right">Total do Pedido</td>
              <td class="px-4 py-3 text-lg font-extrabold text-orange-500 text-right">${fBRL3(o.total_amount)}</td>
            </tr></tfoot>
          </table>
        </div>`)}
      ${o.notes ? `<p class="mt-3 text-xs text-slate-400 italic px-1">Obs: ${o.notes}</p>` : ''}`;
    area.scrollIntoView({ behavior: 'smooth' });
    if (window.lucide) lucide.createIcons();
  } catch { area.innerHTML = '<div class="text-xs text-rose-500 p-4">Erro ao carregar detalhes.</div>'; }
}

async function changePurchStatus(id, newStatus) {
  const labels = { enviado: 'enviar', aprovado: 'aprovar', cancelado: 'cancelar' };
  if (!confirm(`Deseja ${labels[newStatus] || newStatus} este pedido?`)) return;
  try {
    const r = await fetch(`/api/purchase-orders/${id}/status`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro.'); return; }
    await renderPedidos(document.getElementById('purch-body'));
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

async function receivePurchOrder(id, orderNum) {
  if (!confirm(`Confirmar recebimento do Pedido #${orderNum}?\n\nIsso irá:\n• Dar entrada dos itens no estoque (custo médio ponderado)\n• Gerar título no Contas a Pagar`)) return;
  try {
    const r = await fetch(`/api/purchase-orders/${id}/receive`, {
      method: 'POST', headers: authHeaders(),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro.'); return; }
    const data = await r.json();
    alert(data.message || 'Recebimento registrado com sucesso!');
    await renderPedidos(document.getElementById('purch-body'));
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

// ── MODAL NOVO PEDIDO ─────────────────────────────────────────
let purchItemCount = 1;

function openNewPurchModal() {
  purchItemCount = 1;
  const suppOpts = purchSuppliers.map(s => `<option value="${s.id}">${s.name}${s.document ? ' — ' + s.document : ''}</option>`).join('');
  const prodOpts = purchProducts.map(p => `<option value="${p.id}" data-price="${p.cost_price || 0}">${p.name}${p.sku ? ' [' + p.sku + ']' : ''}</option>`).join('');

  openModal(`
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-6 max-w-3xl w-full">
      <h3 class="font-bold text-slate-800 dark:text-slate-100 mb-5 text-lg flex items-center gap-2">
        <i data-lucide="shopping-cart" class="w-5 h-5 text-orange-500"></i> Novo Pedido de Compra
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
        <div class="md:col-span-2">
          ${lblP('Fornecedor *')}
          <select id="po-supplier" class="${inputP()}">
            <option value="">Selecione o fornecedor...</option>${suppOpts}
          </select>
        </div>
        <div>
          ${lblP('Prev. de Entrega')}
          <input id="po-delivery" type="date" class="${inputP()}">
        </div>
        <div>
          ${lblP('Condições de Pagamento')}
          <input id="po-terms" class="${inputP()}" value="Boleto 30 dias" placeholder="ex: Boleto 30/60 dias">
        </div>
        <div class="md:col-span-2">
          ${lblP('Observações')}
          <input id="po-notes" class="${inputP()}" placeholder="Referência interna, instruções de entrega...">
        </div>
      </div>

      <div class="mb-3 flex items-center justify-between">
        <span class="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase">Itens do Pedido</span>
        <button onclick="addPurchItem('${prodOpts.replace(/'/g, "\\'")}')"
          class="text-xs text-orange-500 hover:underline flex items-center gap-1">
          <i data-lucide="plus-circle" class="w-3.5 h-3.5"></i> Adicionar item
        </button>
      </div>
      <div id="po-items-container" class="space-y-2 mb-5">
        ${purchItemRow(0, prodOpts)}
      </div>
      <div class="flex justify-between items-center">
        <div class="text-sm font-bold text-slate-700 dark:text-slate-200">
          Total: <span id="po-total" class="text-orange-500">R$ 0,00</span>
        </div>
        <div class="flex gap-3">
          <button onclick="closeModal()" class="px-4 py-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
          <button onclick="savePurchOrder()"
            class="bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold px-5 py-2 rounded-xl">
            Criar Pedido
          </button>
        </div>
      </div>
    </div>`);
  if (window.lucide) lucide.createIcons();
  updatePurchTotal();
}

function purchItemRow(idx, prodOpts) {
  return `
    <div id="po-item-${idx}" class="grid grid-cols-12 gap-2 items-end">
      <div class="col-span-5">
        ${idx === 0 ? lblP('Produto') : ''}
        <select id="po-prod-${idx}" class="${inputP()} text-xs" onchange="onPurchProdChange(${idx})">
          <option value="">Produto...</option>${prodOpts}
        </select>
      </div>
      <div class="col-span-2">
        ${idx === 0 ? lblP('Qtd') : ''}
        <input id="po-qty-${idx}" type="number" min="0.001" step="0.001" value="1"
          class="${inputP()} text-xs" onchange="updatePurchTotal()">
      </div>
      <div class="col-span-2">
        ${idx === 0 ? lblP('Preço Unit.') : ''}
        <input id="po-price-${idx}" type="number" min="0" step="0.01" value="0"
          class="${inputP()} text-xs" onchange="updatePurchTotal()">
      </div>
      <div class="col-span-2">
        ${idx === 0 ? lblP('Desconto') : ''}
        <input id="po-disc-${idx}" type="number" min="0" step="0.01" value="0"
          class="${inputP()} text-xs" onchange="updatePurchTotal()">
      </div>
      <div class="col-span-1 ${idx === 0 ? 'pt-5' : ''}">
        ${idx > 0
          ? `<button onclick="document.getElementById('po-item-${idx}').remove(); updatePurchTotal()"
               class="text-rose-400 hover:text-rose-600 p-2"><i data-lucide="trash-2" class="w-4 h-4"></i></button>`
          : '<div class="h-9"></div>'}
      </div>
    </div>`;
}

function addPurchItem(prodOpts) {
  const container = document.getElementById('po-items-container');
  if (!container) return;
  const div = document.createElement('div');
  div.innerHTML = purchItemRow(purchItemCount, prodOpts);
  container.appendChild(div.firstElementChild);
  purchItemCount++;
  if (window.lucide) lucide.createIcons();
}

function onPurchProdChange(idx) {
  const sel = document.getElementById(`po-prod-${idx}`);
  if (!sel) return;
  const opt = sel.options[sel.selectedIndex];
  const price = opt?.dataset?.price || 0;
  const priceInput = document.getElementById(`po-price-${idx}`);
  if (priceInput && parseFloat(priceInput.value) === 0) priceInput.value = parseFloat(price).toFixed(2);
  updatePurchTotal();
}

function updatePurchTotal() {
  let total = 0;
  for (let i = 0; i <= purchItemCount; i++) {
    const qty   = parseFloat(document.getElementById(`po-qty-${i}`)?.value || 0);
    const price = parseFloat(document.getElementById(`po-price-${i}`)?.value || 0);
    const disc  = parseFloat(document.getElementById(`po-disc-${i}`)?.value || 0);
    if (qty > 0 && price > 0) total += (qty * price) - disc;
  }
  const el = document.getElementById('po-total');
  if (el) el.textContent = fBRL3(total);
}

async function savePurchOrder() {
  const supplier_id = parseInt(document.getElementById('po-supplier')?.value);
  if (!supplier_id) { alert('Selecione o fornecedor.'); return; }

  const items = [];
  for (let i = 0; i <= purchItemCount; i++) {
    const prodEl = document.getElementById(`po-prod-${i}`);
    if (!prodEl) continue;
    const product_id = parseInt(prodEl.value);
    if (!product_id) continue;
    const quantity   = parseFloat(document.getElementById(`po-qty-${i}`)?.value || 1);
    const unit_price = parseFloat(document.getElementById(`po-price-${i}`)?.value || 0);
    const discount   = parseFloat(document.getElementById(`po-disc-${i}`)?.value || 0);
    if (unit_price <= 0) { alert('Informe o preço unitário de todos os itens.'); return; }
    items.push({ product_id, quantity, unit_price, discount });
  }
  if (items.length === 0) { alert('Adicione ao menos um item.'); return; }

  const payload = {
    supplier_id,
    items,
    expected_delivery_date: document.getElementById('po-delivery')?.value || null,
    payment_terms: document.getElementById('po-terms')?.value || 'Boleto 30 dias',
    notes: document.getElementById('po-notes')?.value || '',
  };

  try {
    const r = await fetch('/api/purchase-orders', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Erro ao criar pedido.'); return; }
    closeModal();
    await renderPedidos(document.getElementById('purch-body'));
    if (window.lucide) lucide.createIcons();
  } catch { alert('Erro de conexão.'); }
}

// ── 2. IMPORTAR XML NF-e ──────────────────────────────────────
async function renderXmlImport(el) {
  let xmlList = [];
  try {
    const r = await fetch('/api/xml-purchases', { headers: authHeaders() });
    xmlList = await r.json();
  } catch { xmlList = []; }

  const rows = xmlList.map(x => `
    <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
      <td class="px-4 py-2.5 text-xs font-mono text-slate-500">${x.invoice_number}</td>
      <td class="px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200">${x.supplier_name}</td>
      <td class="px-4 py-2.5 text-xs font-mono text-slate-400">${x.supplier_cnpj || '-'}</td>
      <td class="px-4 py-2.5 text-xs text-slate-400">${fDate3(x.issue_date)}</td>
      <td class="px-4 py-2.5 text-sm font-semibold text-orange-500">${fBRL3(x.total_amount)}</td>
      <td class="px-4 py-2.5 text-xs text-slate-400">${x.items_count} ${x.items_count === 1 ? 'item' : 'itens'}</td>
      <td class="px-4 py-2.5 text-xs text-slate-400">${x.installments_count} dup.</td>
    </tr>`).join('');

  el.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">

      ${card3(`
        <div class="p-5">
          <div class="flex items-center gap-2 mb-4">
            <i data-lucide="upload" class="w-5 h-5 text-orange-500"></i>
            <span class="font-bold text-slate-700 dark:text-slate-200">Upload de Arquivo XML</span>
          </div>
          <p class="text-xs text-slate-400 mb-4">
            Envie a NF-e XML de compra do fornecedor. O sistema importa automaticamente:
            produtos/estoque (custo médio), fornecedor e duplicatas no Contas a Pagar.
          </p>
          <label class="block mb-4">
            <div class="border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-xl p-6 text-center cursor-pointer hover:border-orange-400 transition" id="xml-drop-area">
              <i data-lucide="file-xml" class="w-8 h-8 text-slate-300 mx-auto mb-2"></i>
              <p class="text-xs text-slate-400">Arraste o arquivo .xml aqui ou <span class="text-orange-500 font-semibold">clique para selecionar</span></p>
              <p id="xml-filename" class="text-xs text-orange-500 mt-1 font-semibold"></p>
            </div>
            <input id="xml-file-input" type="file" accept=".xml" class="hidden" onchange="onXmlFileSelect(this)">
          </label>
          <button onclick="importXmlFile()"
            class="w-full bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold px-4 py-2.5 rounded-xl flex items-center justify-center gap-2">
            <i data-lucide="file-down" class="w-4 h-4"></i> Importar XML
          </button>
          <div id="xml-upload-result" class="mt-3"></div>
        </div>`)}

      ${card3(`
        <div class="p-5">
          <div class="flex items-center gap-2 mb-4">
            <i data-lucide="clipboard-paste" class="w-5 h-5 text-orange-500"></i>
            <span class="font-bold text-slate-700 dark:text-slate-200">Colar Conteúdo XML</span>
          </div>
          <p class="text-xs text-slate-400 mb-4">Cole o conteúdo XML da NF-e diretamente no campo abaixo.</p>
          <textarea id="xml-paste-input" rows="6"
            class="w-full text-xs font-mono border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none"
            placeholder='<?xml version="1.0"?><nfeProc>...</nfeProc>'></textarea>
          <button onclick="importXmlText()"
            class="mt-3 w-full bg-orange-500 hover:bg-orange-600 text-white text-sm font-semibold px-4 py-2.5 rounded-xl flex items-center justify-center gap-2">
            <i data-lucide="file-down" class="w-4 h-4"></i> Importar XML
          </button>
          <div id="xml-paste-result" class="mt-3"></div>
        </div>`)}
    </div>

    <div class="flex items-center justify-between mb-3">
      <h3 class="font-bold text-slate-700 dark:text-slate-200">XMLs Importados (${xmlList.length})</h3>
    </div>
    ${card3(`
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="text-xs text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2 text-left font-semibold">NF Nº</th>
            <th class="px-4 py-2 text-left font-semibold">Fornecedor</th>
            <th class="px-4 py-2 text-left font-semibold">CNPJ</th>
            <th class="px-4 py-2 text-left font-semibold">Emissão</th>
            <th class="px-4 py-2 text-left font-semibold">Total</th>
            <th class="px-4 py-2 text-left font-semibold">Itens</th>
            <th class="px-4 py-2 text-left font-semibold">Duplicatas</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="7" class="px-4 py-8 text-center text-slate-400 text-xs">Nenhum XML importado ainda.</td></tr>'}</tbody>
        </table>
      </div>`)}`;

  document.getElementById('xml-drop-area')?.addEventListener('click', () => {
    document.getElementById('xml-file-input')?.click();
  });
}

function onXmlFileSelect(input) {
  const file = input.files?.[0];
  const label = document.getElementById('xml-filename');
  if (label) label.textContent = file ? file.name : '';
}

async function importXmlFile() {
  const input = document.getElementById('xml-file-input');
  const file  = input?.files?.[0];
  const res   = document.getElementById('xml-upload-result');

  if (!file) {
    if (res) res.innerHTML = '<p class="text-xs text-rose-500">Selecione um arquivo XML.</p>';
    return;
  }

  if (res) res.innerHTML = '<p class="text-xs text-slate-400">Importando...</p>';
  const form = new FormData();
  form.append('file', file);

  try {
    const r = await fetch('/api/xml-purchases/import', { method: 'POST', headers: authHeaders(), body: form });
    const d = await r.json();
    if (!r.ok) { res.innerHTML = `<p class="text-xs text-rose-500">${d.detail || 'Erro.'}</p>`; return; }
    res.innerHTML = `<div class="text-xs text-emerald-600 font-semibold p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
      ✓ ${d.message}<br>
      <span class="text-slate-500 font-normal">${d.items_count} produto(s) · ${fBRL3(d.total_amount)}</span>
    </div>`;
    await renderXmlImport(document.getElementById('purch-body'));
    if (window.lucide) lucide.createIcons();
  } catch { res.innerHTML = '<p class="text-xs text-rose-500">Erro de conexão.</p>'; }
}

async function importXmlText() {
  const xml = document.getElementById('xml-paste-input')?.value.trim();
  const res = document.getElementById('xml-paste-result');

  if (!xml) { if (res) res.innerHTML = '<p class="text-xs text-rose-500">Cole o conteúdo XML.</p>'; return; }
  if (res) res.innerHTML = '<p class="text-xs text-slate-400">Importando...</p>';

  try {
    const r = await fetch('/api/xml-purchases/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ xml_content: xml }),
    });
    const d = await r.json();
    if (!r.ok) { res.innerHTML = `<p class="text-xs text-rose-500">${d.detail || 'Erro.'}</p>`; return; }
    res.innerHTML = `<div class="text-xs text-emerald-600 font-semibold p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
      ✓ ${d.message}<br>
      <span class="text-slate-500 font-normal">${d.items_count} produto(s) · ${fBRL3(d.total_amount)}</span>
    </div>`;
    document.getElementById('xml-paste-input').value = '';
    await renderXmlImport(document.getElementById('purch-body'));
    if (window.lucide) lucide.createIcons();
  } catch { res.innerHTML = '<p class="text-xs text-rose-500">Erro de conexão.</p>'; }
}
