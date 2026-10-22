// Cortex ERP Pro+ Frontend SPA Application
let currentTab = 'dashboard';
let chartInstance = null;
let currentProducts = [];
let currentBankAccounts = [];
let currentCategories = [];
let currentContacts = [];

// Formatters
const formatCurrency = (val) => {
  const num = parseFloat(val) || 0.0;
  return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const d = dateStr.slice(0, 10).split('-');
  if (d.length === 3) return `${d[2]}/${d[1]}/${d[0]}`;
  return dateStr;
};

// UI Feedback
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const colors = {
    success: 'bg-emerald-600 text-white',
    error: 'bg-rose-600 text-white',
    info: 'bg-blue-600 text-white',
    warning: 'bg-amber-600 text-white',
  };
  const toast = document.createElement('div');
  toast.className = `px-4 py-3 rounded-xl shadow-lg text-xs font-semibold flex items-center gap-2 transition-all transform duration-300 ${colors[type] || colors.info}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-x-4');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Modal Management
function openModal(htmlContent) {
  const backdrop = document.getElementById('modal-backdrop');
  const box = document.getElementById('modal-box');
  if (!backdrop || !box) return;
  box.innerHTML = htmlContent;
  backdrop.classList.remove('hidden');
  backdrop.classList.add('flex');
  if (window.lucide) lucide.createIcons();
}

function closeModal() {
  const backdrop = document.getElementById('modal-backdrop');
  const box = document.getElementById('modal-box');
  if (!backdrop || !box) return;
  backdrop.classList.add('hidden');
  backdrop.classList.remove('flex');
  box.innerHTML = '';
}

// Dark Mode Toggle
function toggleDarkMode() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('cortex_theme', isDark ? 'dark' : 'light');
}

// AI Quick Launch in Header
async function executeAiLaunch() {
  const input = document.getElementById('ai-quick-input');
  if (!input || !input.value.trim()) return;
  const text = input.value.trim();
  input.value = '';
  showToast('Processando comando mágico com IA...', 'info');

  try {
    const res = await fetch('/api/financial/ai-launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`Lançamento realizado: ${data.description || text} (${formatCurrency(data.amount)})`, 'success');
      if (['dashboard', 'receivables', 'payables'].includes(currentTab)) {
        switchTab(currentTab);
      }
    } else {
      showToast(`Erro ao lançar: ${data.detail || 'Falha no processamento'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação com o servidor.', 'error');
  }
}

// Cache global lookups
async function preloadLookups() {
  try {
    const [pRes, bRes, cRes, ctRes] = await Promise.all([
      fetch('/api/products').then(r => r.json()),
      fetch('/api/bank-accounts').then(r => r.json()),
      fetch('/api/categories').then(r => r.json()),
      fetch('/api/contacts').then(r => r.json()),
    ]);
    currentProducts = Array.isArray(pRes) ? pRes : [];
    currentBankAccounts = Array.isArray(bRes) ? bRes : [];
    currentCategories = Array.isArray(cRes) ? cRes : [];
    currentContacts = Array.isArray(ctRes) ? ctRes : [];
  } catch (e) {
    console.warn('Erro ao carregar dados auxiliares:', e);
  }
}

// Navigation & Tab Switching
async function switchTab(tab) {
  currentTab = tab;
  if (typeof closeSidebar === 'function') closeSidebar();
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const activeNav = document.getElementById(`nav-${tab}`);
  if (activeNav) activeNav.classList.add('active');

  const main = document.getElementById('main-content');
  main.innerHTML = '<div class="flex items-center justify-center p-12 text-slate-400"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>Carregando módulo...</div>';

  await preloadLookups();

  switch (tab) {
    case 'dashboard':
      await renderDashboard(main);
      break;
    case 'receivables':
      await renderFinancial(main, 'receita');
      break;
    case 'payables':
      await renderFinancial(main, 'despesa');
      break;
    case 'ofx':
      await renderOfx(main);
      break;
    case 'crm':
      await renderCrm(main);
      break;
    case 'sales':
      await renderSales(main);
      break;
    case 'pdv':
      await renderPdv(main);
      break;
    case 'os':
      await renderServiceOrders(main);
      break;
    case 'inventory':
      await renderInventory(main);
      break;
    case 'quotes':
      await renderQuotes(main);
      break;
    case 'invoices':
      await renderInvoices(main);
      break;
    case 'reports':
      await renderReports(main);
      break;
    case 'settings':
      await renderSettings(main);
      break;
    default:
      main.innerHTML = `<div class="p-6">Módulo "${tab}" em desenvolvimento.</div>`;
  }
  if (window.lucide) lucide.createIcons();
}

// ==============================================================================
// 1. DASHBOARD & CFO IA
// ==============================================================================
async function renderDashboard(container) {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();

    const kpis = data.kpis || {};
    const flow = data.monthly_cash_flow || [];
    const accounts = data.bank_accounts || [];
    const pendingPay = data.upcoming_payables || [];
    const pendingRec = data.upcoming_receivables || [];

    let accountsHtml = accounts.map(a => `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs flex justify-between items-center">
        <div>
          <div class="text-xs text-slate-500 font-medium">${a.bank_name || 'Banco'} (${a.agency || '0001'})</div>
          <div class="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5">${a.name}</div>
        </div>
        <div class="text-right">
          <div class="text-xs text-slate-400">Saldo Atual</div>
          <div class="font-extrabold text-sm ${a.current_balance >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600'}">
            ${formatCurrency(a.current_balance)}
          </div>
        </div>
      </div>
    `).join('');

    container.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>Saldo Bancário Total</span>
            <i data-lucide="wallet" class="w-4 h-4 text-blue-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 text-slate-900 dark:text-slate-50">${formatCurrency(kpis.total_balance)}</div>
          <div class="text-[11px] text-slate-400 mt-1">Soma de todas as contas ativas</div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>A Receber (Mês)</span>
            <i data-lucide="arrow-up-right" class="w-4 h-4 text-emerald-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 text-emerald-600">${formatCurrency(kpis.month_receivables)}</div>
          <div class="text-[11px] text-rose-500 mt-1">Vencidos: ${formatCurrency(kpis.overdue_receivables)}</div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>A Pagar (Mês)</span>
            <i data-lucide="arrow-down-left" class="w-4 h-4 text-rose-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 text-rose-600">${formatCurrency(kpis.month_payables)}</div>
          <div class="text-[11px] text-rose-500 mt-1">Vencidos: ${formatCurrency(kpis.overdue_payables)}</div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between text-slate-500 text-xs font-semibold">
            <span>Lucro Líquido Previsto</span>
            <i data-lucide="trending-up" class="w-4 h-4 text-indigo-500"></i>
          </div>
          <div class="text-2xl font-extrabold mt-2 ${kpis.net_income >= 0 ? 'text-indigo-600' : 'text-rose-600'}">
            ${formatCurrency(kpis.net_income)}
          </div>
          <div class="text-[11px] text-slate-400 mt-1">Faturamento: ${formatCurrency(kpis.month_revenue)}</div>
        </div>
      </div>

      <!-- CFO VIRTUAL IA -->
      <div class="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-2xl p-6 text-white shadow-lg">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-10 h-10 rounded-xl bg-blue-500/30 flex items-center justify-center border border-blue-400/30">
            <i data-lucide="bot" class="w-5 h-5 text-blue-300"></i>
          </div>
          <div>
            <h3 class="font-bold text-base">CFO Virtual com IA (Gemini)</h3>
            <p class="text-xs text-blue-200">Análise financeira executiva, riscos e recomendações estratégicas</p>
          </div>
        </div>
        <div id="cfo-reply" class="bg-black/30 backdrop-blur-xs rounded-xl p-4 text-xs md:text-sm leading-relaxed border border-white/10 text-blue-50 max-h-48 overflow-y-auto">
          Clique no botão abaixo ou pergunte algo ao CFO Virtual sobre o fluxo de caixa, inadimplência ou redução de custos.
        </div>
        <div class="mt-4 flex gap-2">
          <input id="cfo-question" type="text" placeholder="Ex: 'Faça um diagnóstico do meu fluxo de caixa deste mês e aponte os 3 maiores riscos.'" class="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-2 text-xs md:text-sm text-white placeholder-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-400">
          <button onclick="askCfo()" class="bg-white text-blue-900 hover:bg-blue-50 font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 transition">
            <i data-lucide="send" class="w-3.5 h-3.5"></i> Perguntar
          </button>
        </div>
      </div>

      <!-- FLUXO DE CAIXA GRÁFICO & CONTAS -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <i data-lucide="bar-chart-3" class="w-4 h-4 text-blue-600"></i> Fluxo de Caixa Mensal
            </h3>
            <span class="text-xs text-slate-400">Últimos meses</span>
          </div>
          <div class="h-64">
            <canvas id="cashFlowChart"></canvas>
          </div>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-col">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <i data-lucide="landmark" class="w-4 h-4 text-blue-600"></i> Contas Bancárias
            </h3>
            <button onclick="openTransferModal()" class="text-xs bg-blue-50 text-blue-700 hover:bg-blue-100 font-semibold px-2 py-1 rounded-lg">
              Transferir
            </button>
          </div>
          <div class="space-y-3 flex-1 overflow-y-auto">
            ${accountsHtml || '<div class="text-xs text-slate-400">Nenhuma conta bancária cadastrada.</div>'}
          </div>
        </div>
      </div>
    `;

    // Render chart
    const ctx = document.getElementById('cashFlowChart');
    if (ctx && window.Chart) {
      if (chartInstance) chartInstance.destroy();
      const labels = flow.map(f => f.month);
      const recData = flow.map(f => f.receitas);
      const despData = flow.map(f => f.despesas);
      chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            { label: 'Receitas', data: recData, backgroundColor: '#34d399', hoverBackgroundColor: '#6ee7b7', borderRadius: 8, borderSkipped: false, maxBarThickness: 28 },
            { label: 'Despesas', data: despData, backgroundColor: '#fb7185', hoverBackgroundColor: '#fda4af', borderRadius: 8, borderSkipped: false, maxBarThickness: 28 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { grid: { color: 'rgba(129,140,248,0.10)' }, border: { display: false } },
            x: { grid: { display: false }, border: { display: false } },
          },
        },
      });
    }
  } catch (err) {
    container.innerHTML = `<div class="p-6 text-rose-500 font-semibold">Erro ao carregar Dashboard: ${err.message}</div>`;
  }
}

async function askCfo() {
  const qInput = document.getElementById('cfo-question');
  const rDiv = document.getElementById('cfo-reply');
  if (!qInput || !rDiv) return;
  const question = qInput.value.trim() || 'Faça um diagnóstico do meu fluxo de caixa deste mês e aponte os 3 maiores riscos.';
  rDiv.innerHTML = '<span class="animate-pulse">Consultando CFO Virtual IA... aguarde.</span>';
  try {
    const res = await fetch('/api/cfo/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: question }),
    });
    const d = await res.json();
    rDiv.innerHTML = `<div class="font-bold mb-1 text-blue-200">Parecer do CFO:</div><div>${(d.reply || 'Sem resposta.').replace(/\n/g, '<br>')}</div>`;
  } catch (e) {
    rDiv.innerHTML = 'Falha ao consultar CFO IA.';
  }
}

// ==============================================================================
// 2. FINANCEIRO (CONTAS A RECEBER E A PAGAR)
// ==============================================================================
async function renderFinancial(container, type) {
  const isRec = type === 'receita';
  const title = isRec ? 'Contas a Receber' : 'Contas a Pagar';
  const badgeColor = isRec ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700';

  try {
    const res = await fetch(`/api/financial?type=${type}`);
    const entries = await res.json();

    let rowsHtml = entries.map(e => `
      <tr class="border-b border-slate-100 dark:border-slate-800/80 hover:bg-slate-50/60 dark:hover:bg-slate-800/40 text-xs">
        <td class="py-3 px-4">
          <div class="font-bold text-slate-800 dark:text-slate-100">${e.description}</div>
          <div class="text-[11px] text-slate-400">${e.contact_name || 'Sem contato'} · ${e.category_name || 'Geral'}</div>
        </td>
        <td class="py-3 px-4 font-medium">${formatDate(e.due_date)}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(e.amount)}</td>
        <td class="py-3 px-4 font-semibold text-emerald-600">${formatCurrency(e.paid_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            e.status === 'pago' ? 'bg-emerald-500/20 text-emerald-600' :
            e.status === 'parcial' ? 'bg-amber-500/20 text-amber-600' :
            'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
          }">
            ${e.status.toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          ${isRec && e.status !== 'pago' ? `
            <button onclick="openChargeModal(${e.id})" class="bg-indigo-600 hover:bg-indigo-700 text-white px-2 py-1 rounded-lg font-semibold text-[11px] transition" title="Gerar Cobrança Pix / Boleto Asaas">
              Pix/Boleto
            </button>
            <button onclick="sendWhatsAppCollection(${e.id})" class="bg-emerald-600 hover:bg-emerald-700 text-white px-2 py-1 rounded-lg font-semibold text-[11px] transition" title="Cobrar cliente no WhatsApp">
              WhatsApp
            </button>
          ` : ''}
          ${e.status !== 'pago' ? `
            <button onclick="openPayModal(${e.id}, '${e.type}', ${e.amount - e.paid_amount})" class="bg-emerald-600 hover:bg-emerald-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
              ${isRec ? 'Receber' : 'Pagar'}
            </button>
          ` : `
            <button onclick="reverseEntry(${e.id})" class="bg-amber-600 hover:bg-amber-700 text-white px-2 py-1 rounded-lg font-semibold text-[11px] transition" title="Estornar baixa">
              Estorno
            </button>
          `}
          <button onclick="deleteEntry(${e.id})" class="text-rose-500 hover:text-rose-700 p-1" title="Excluir">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            ${isRec ? '<i data-lucide="arrow-up-right" class="w-5 h-5 text-emerald-500"></i>' : '<i data-lucide="arrow-down-left" class="w-5 h-5 text-rose-500"></i>'}
            ${title}
          </h2>
          <p class="text-xs text-slate-400">Gerenciamento completo de lançamentos, parcelamentos e baixas</p>
        </div>
        <div class="flex gap-2">
          <a href="/api/financial/export-excel?type=${type}" download class="bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition">
            <i data-lucide="file-spreadsheet" class="w-4 h-4"></i> Excel
          </a>
          <a href="/api/financial/export-csv?type=${type}" download class="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition">
            <i data-lucide="download" class="w-4 h-4"></i> CSV
          </a>
          <button onclick="openFinancialModal('${type}')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="plus-circle" class="w-4 h-4"></i> ${isRec ? 'Nova Receita' : 'Nova Despesa'}
          </button>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <th class="py-3 px-4">Descrição / Categoria</th>
                <th class="py-3 px-4">Vencimento</th>
                <th class="py-3 px-4">Valor Total</th>
                <th class="py-3 px-4">Valor Pago</th>
                <th class="py-3 px-4">Status</th>
                <th class="py-3 px-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhum lançamento de ${type} encontrado.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro ao carregar lista de ${type}: ${err.message}</div>`;
  }
}

// Modal Nova Receita / Despesa
function openFinancialModal(type = 'despesa') {
  const isRec = type === 'receita';
  const catOptions = currentCategories
    .filter(c => c.type === type)
    .map(c => `<option value="${c.id}">${c.code} - ${c.name}</option>`)
    .join('');

  const accOptions = currentBankAccounts
    .map(a => `<option value="${a.id}">${a.name} (${formatCurrency(a.current_balance)})</option>`)
    .join('');

  const contactOptions = currentContacts
    .map(ct => `<option value="${ct.id}">${ct.name} (${ct.document || ct.type})</option>`)
    .join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
        ${isRec ? '<i data-lucide="plus-circle" class="w-5 h-5 text-emerald-500"></i> Nova Receita' : '<i data-lucide="minus-circle" class="w-5 h-5 text-rose-500"></i> Nova Despesa'}
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitFinancial(event, '${type}')" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Descrição *</label>
        <input required name="description" placeholder="Ex: Prestação de serviços ou Fatura de Energia" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Valor Total (R$) *</label>
          <input required type="number" step="0.01" name="amount" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Vencimento *</label>
          <input required type="date" name="due_date" value="${new Date().toISOString().slice(0, 10)}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Categoria DRE</label>
          <select name="category_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${catOptions}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Conta Bancária</label>
          <select name="bank_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${accOptions}
          </select>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Cliente / Fornecedor</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Nenhum</option>
            ${contactOptions}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Parcelas</label>
          <input type="number" min="1" max="120" name="installments" value="1" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Método de Pagamento</label>
          <select name="payment_method" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="Pix">Pix</option>
            <option value="Boleto">Boleto</option>
            <option value="Cartão de Crédito">Cartão de Crédito</option>
            <option value="Transferência/TED">Transferência/TED</option>
            <option value="Dinheiro">Dinheiro</option>
          </select>
        </div>
      </div>

      <div class="flex items-center gap-2 pt-2">
        <input type="checkbox" id="already_paid" name="already_paid" class="rounded">
        <label for="already_paid" class="font-semibold text-slate-700 dark:text-slate-300">Já está pago / baixado hoje na conta selecionada</label>
      </div>

      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Salvar Lançamento</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitFinancial(e, type) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    type,
    description: form.description.value,
    amount: parseFloat(form.amount.value),
    due_date: form.due_date.value,
    category_id: form.category_id.value ? parseInt(form.category_id.value) : null,
    bank_account_id: form.bank_account_id.value ? parseInt(form.bank_account_id.value) : null,
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    installments: parseInt(form.installments.value) || 1,
    payment_method: form.payment_method.value,
    already_paid: form.already_paid.checked,
  };

  try {
    const res = await fetch('/api/financial', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Lançamento salvo com sucesso!', 'success');
      closeModal();
      switchTab(currentTab);
    } else {
      const err = await res.json();
      showToast(`Erro ao salvar: ${err.detail || 'Falha'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação com o backend.', 'error');
  }
}

// Gateway de Cobrança (Pix / Boleto / Asaas)
async function openChargeModal(entryId) {
  showToast('Consultando/Gerando cobrança no gateway...', 'info');
  try {
    const res = await fetch(`/api/payments/charge/${entryId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ billing_type: 'PIX' }),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(`Erro na cobrança: ${data.detail || 'Falha'}`, 'error');
      return;
    }
    const ch = data.charge;
    const qrImg = ch.pix_qr_code_b64 ? `<img src="data:image/png;base64,${ch.pix_qr_code_b64}" class="w-48 h-48 mx-auto my-3 border p-2 rounded-xl bg-white shadow-sm" />` : '';

    const html = `
      <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
        <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <i data-lucide="qr-code" class="w-5 h-5 text-indigo-500"></i> Cobrança Digital (Gateway Asaas / Pix)
        </h3>
        <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
      </div>

      <div class="mt-4 text-center space-y-3">
        <div class="text-xs text-slate-400">ID da Cobrança: <span class="font-mono font-bold">${ch.gateway_id}</span></div>
        <div class="text-2xl font-extrabold text-emerald-600">${formatCurrency(ch.value)}</div>
        <div class="text-xs font-semibold">Vencimento: ${formatDate(ch.due_date)}</div>

        ${qrImg}

        <div class="bg-slate-100 dark:bg-slate-800 p-2.5 rounded-xl font-mono text-[10px] break-all border border-slate-200 dark:border-slate-700 select-all" id="pixCopyStr">
          ${ch.pix_copy_paste || 'Código Pix Indisponível'}
        </div>

        <div class="flex justify-center gap-2 pt-2">
          <button onclick="navigator.clipboard.writeText(document.getElementById('pixCopyStr').innerText);showToast('Chave Pix Copia e Cola copiada!', 'success')" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs px-3 py-2 rounded-xl flex items-center gap-1.5 transition">
            <i data-lucide="copy" class="w-4 h-4"></i> Copiar Pix
          </button>
          <a href="${ch.bank_slip_url || '#'}" target="_blank" class="bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs px-3 py-2 rounded-xl flex items-center gap-1.5 transition">
            <i data-lucide="file-text" class="w-4 h-4"></i> Imprimir Boleto
          </a>
          <a href="${ch.invoice_url || '#'}" target="_blank" class="bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-bold text-xs px-3 py-2 rounded-xl flex items-center gap-1.5 transition">
            <i data-lucide="external-link" class="w-4 h-4"></i> Fatura Online
          </a>
        </div>
      </div>
    `;
    openModal(html);
  } catch (e) {
    showToast('Falha na comunicação com gateway.', 'error');
  }
}

// Régua de Cobrança WhatsApp
async function sendWhatsAppCollection(entryId) {
  showToast('Gerando mensagem de cobrança...', 'info');
  try {
    const res = await fetch(`/api/collection/send/${entryId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel: 'whatsapp' }),
    });
    const data = await res.json();
    if (res.ok && data.whatsapp_url) {
      window.open(data.whatsapp_url, '_blank');
      showToast('Janela do WhatsApp aberta com a mensagem formatada!', 'success');
    } else {
      showToast(`Erro ao gerar cobrança: ${data.detail || 'Falha'}`, 'error');
    }
  } catch (e) {
    showToast('Falha ao acionar régua de cobrança.', 'error');
  }
}

// Modal Baixa / Pagamento
function openPayModal(entryId, type, remainingAmount) {
  const isRec = type === 'receita';
  const accOptions = currentBankAccounts
    .map(a => `<option value="${a.id}">${a.name}</option>`)
    .join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">
        ${isRec ? 'Confirmar Recebimento' : 'Confirmar Pagamento'} (ID #${entryId})
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitPay(event, ${entryId})" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Valor a Baixar (R$) *</label>
        <input required type="number" step="0.01" name="amount" value="${remainingAmount.toFixed(2)}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div>
        <label class="block font-semibold mb-1">Conta Bancária de Liquidação</label>
        <select name="bank_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
          ${accOptions}
        </select>
      </div>
      <div>
        <label class="block font-semibold mb-1">Data do Pagamento</label>
        <input type="date" name="payment_date" value="${new Date().toISOString().slice(0, 10)}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold">Confirmar Baixa</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitPay(e, entryId) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    amount: parseFloat(form.amount.value),
    bank_account_id: parseInt(form.bank_account_id.value),
    payment_date: form.payment_date.value,
  };
  try {
    const res = await fetch(`/api/financial/${entryId}/pay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Baixa realizada com sucesso!', 'success');
      closeModal();
      switchTab(currentTab);
    } else {
      const err = await res.json();
      showToast(`Erro na baixa: ${err.detail || 'Falha'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na comunicação.', 'error');
  }
}

async function reverseEntry(entryId) {
  if (!confirm('Deseja estornar as baixas realizadas para este lançamento?')) return;
  try {
    const res = await fetch(`/api/financial/${entryId}/reverse`, { method: 'POST' });
    if (res.ok) {
      showToast('Estorno realizado!', 'success');
      switchTab(currentTab);
    } else {
      showToast('Erro ao estornar.', 'error');
    }
  } catch (e) {
    showToast('Erro de comunicação.', 'error');
  }
}

async function deleteEntry(entryId) {
  if (!confirm('Deseja realmente excluir este lançamento?')) return;
  try {
    const res = await fetch(`/api/financial/${entryId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Lançamento excluído!', 'success');
      switchTab(currentTab);
    } else {
      showToast('Erro ao excluir.', 'error');
    }
  } catch (e) {
    showToast('Erro de conexão.', 'error');
  }
}

// Transfer Modal
function openTransferModal() {
  const accOptions = currentBankAccounts
    .map(a => `<option value="${a.id}">${a.name} (${formatCurrency(a.current_balance)})</option>`)
    .join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
        <i data-lucide="arrow-left-right" class="w-5 h-5 text-blue-500"></i> Transferência entre Contas
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitTransfer(event)" class="mt-4 space-y-4 text-xs">
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Conta de Origem (Saída)</label>
          <select name="from_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${accOptions}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Conta de Destino (Entrada)</label>
          <select name="to_account_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${accOptions}
          </select>
        </div>
      </div>
      <div>
        <label class="block font-semibold mb-1">Valor da Transferência (R$)</label>
        <input required type="number" step="0.01" name="amount" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div>
        <label class="block font-semibold mb-1">Descrição</label>
        <input name="description" value="Transferência entre contas" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Transferir Agora</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitTransfer(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    from_account_id: parseInt(form.from_account_id.value),
    to_account_id: parseInt(form.to_account_id.value),
    amount: parseFloat(form.amount.value),
    description: form.description.value,
  };
  try {
    const res = await fetch('/api/bank-accounts/transfer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Transferência efetuada com sucesso!', 'success');
      closeModal();
      switchTab(currentTab);
    } else {
      const err = await res.json();
      showToast(`Erro na transferência: ${err.detail || 'Falha'}`, 'error');
    }
  } catch (err) {
    showToast('Falha de conexão.', 'error');
  }
}

// ==============================================================================
// 3. CONCILIAÇÃO BANCÁRIA OFX + OPEN FINANCE
// ==============================================================================

let _ofxCurrentFilter = 'pendente';

async function renderOfx(container) {
  try {
    const [listRes, summaryRes, ofRes] = await Promise.all([
      fetch('/api/ofx'),
      fetch('/api/ofx/reconciliation-summary'),
      fetch('/api/open-finance/status'),
    ]);
    const items = await listRes.json();
    const summary = summaryRes.ok ? await summaryRes.json() : { accounts: [], integrations: [] };
    const ofStatus = ofRes.ok ? await ofRes.json() : { configured: false, integrations: [] };

    const pending    = items.filter(i => i.status === 'pendente');
    const reconciled = items.filter(i => i.status === 'conciliado');
    const ignored    = items.filter(i => i.status === 'ignorado');

    const countBadge = document.getElementById('badge-ofx');
    if (countBadge) countBadge.innerText = pending.length;

    const totalBalance    = (summary.accounts || []).reduce((s, a) => s + (a.current_balance || 0), 0);
    const totalPendingAmt = (summary.accounts || []).reduce((s, a) => s + (a.pending_amount || 0), 0);
    const lastImport      = (summary.accounts || []).reduce((best, a) => (!best || a.last_import > best) ? a.last_import : best, null);

    const filtered = _ofxCurrentFilter === 'pendente' ? pending :
                     _ofxCurrentFilter === 'conciliado' ? reconciled : ignored;
    const rowsHtml = filtered.map(_buildOfxRow).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="landmark" class="w-5 h-5 text-amber-500"></i> Conciliação Bancária
          </h2>
          <p class="text-xs text-slate-400">Reconcilie extratos OFX e conecte seus bancos via Open Finance (Pluggy)</p>
        </div>
        <div class="flex gap-2 flex-wrap">
          <input type="file" id="ofx-file-input" accept=".ofx,.txt" class="hidden" onchange="uploadOfxFile(event)">
          <button onclick="document.getElementById('ofx-file-input').click()" class="bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 transition">
            <i data-lucide="upload" class="w-4 h-4"></i> Importar OFX
          </button>
          <button onclick="autoReconcileAll()" class="bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 transition">
            <i data-lucide="zap" class="w-4 h-4"></i> Auto-Conciliar
          </button>
        </div>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div class="cx-card p-4 rounded-2xl">
          <div class="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Saldo Contábil Total</div>
          <div class="text-xl font-bold font-mono ${totalBalance >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${formatCurrency(totalBalance)}</div>
          <div class="text-[10px] text-slate-500 mt-1">${(summary.accounts || []).length} conta(s) ativa(s)</div>
        </div>
        <div class="cx-card p-4 rounded-2xl">
          <div class="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Pendente Conciliação</div>
          <div class="text-xl font-bold font-mono text-amber-400">${formatCurrency(totalPendingAmt)}</div>
          <div class="text-[10px] text-slate-500 mt-1">${pending.length} transação(ões)</div>
        </div>
        <div class="cx-card p-4 rounded-2xl">
          <div class="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Conciliadas</div>
          <div class="text-xl font-bold font-mono text-emerald-400">${reconciled.length}</div>
          <div class="text-[10px] text-slate-500 mt-1">de ${items.length} importadas</div>
        </div>
        <div class="cx-card p-4 rounded-2xl">
          <div class="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Última Importação</div>
          <div class="text-sm font-bold text-slate-200">${lastImport ? formatDate(lastImport) : '—'}</div>
          <div class="text-[10px] text-slate-500 mt-1">extrato mais recente</div>
        </div>
      </div>

      ${_buildOpenFinanceSection(ofStatus)}

      <div class="cx-card rounded-2xl overflow-hidden">
        <div class="flex items-center gap-1 p-3 border-b border-white/5">
          <button onclick="setOfxFilter('pendente')" class="px-3 py-1.5 rounded-lg text-xs font-semibold transition ${_ofxCurrentFilter === 'pendente' ? 'bg-amber-500/20 text-amber-300' : 'text-slate-400 hover:text-slate-200'}">
            Pendentes <span class="font-mono">(${pending.length})</span>
          </button>
          <button onclick="setOfxFilter('conciliado')" class="px-3 py-1.5 rounded-lg text-xs font-semibold transition ${_ofxCurrentFilter === 'conciliado' ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-400 hover:text-slate-200'}">
            Conciliadas <span class="font-mono">(${reconciled.length})</span>
          </button>
          <button onclick="setOfxFilter('ignorado')" class="px-3 py-1.5 rounded-lg text-xs font-semibold transition ${_ofxCurrentFilter === 'ignorado' ? 'bg-slate-500/20 text-slate-300' : 'text-slate-400 hover:text-slate-200'}">
            Ignoradas <span class="font-mono">(${ignored.length})</span>
          </button>
        </div>
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-800/60 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Data</th>
              <th class="py-3 px-4">Histórico</th>
              <th class="py-3 px-4">Conta</th>
              <th class="py-3 px-4">Valor</th>
              <th class="py-3 px-4">Sugestão</th>
              <th class="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="6" class="py-8 text-center text-slate-500 text-xs">Nenhuma transação ${_ofxCurrentFilter === 'pendente' ? 'pendente' : _ofxCurrentFilter === 'conciliado' ? 'conciliada' : 'ignorada'}.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
    lucide.createIcons();
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro ao carregar conciliação: ${e.message}</div>`;
  }
}

function _buildOfxRow(it) {
  const isCredit = it.amount >= 0;
  let actionsHtml = '';
  if (it.status === 'pendente') {
    actionsHtml = `
      <div class="flex items-center justify-end gap-1">
        <button onclick="openReconcileModal(${it.id})" class="bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 rounded-lg text-[11px] font-semibold transition">Conciliar</button>
        <button onclick="quickReconcileOfx(${it.id})" title="Criar lançamento automaticamente" class="bg-slate-600 hover:bg-slate-500 text-white px-2 py-1 rounded-lg text-[11px] transition"><i data-lucide="plus" class="w-3 h-3"></i></button>
        <button onclick="ignoreOfxTx(${it.id})" title="Ignorar" class="bg-slate-700 hover:bg-slate-600 text-slate-300 px-2 py-1 rounded-lg text-[11px] transition"><i data-lucide="eye-off" class="w-3 h-3"></i></button>
      </div>`;
  } else if (it.status === 'conciliado') {
    actionsHtml = `<span class="text-emerald-400 text-[11px] flex items-center justify-end gap-1"><i data-lucide="check-circle" class="w-3 h-3"></i> Conciliado</span>`;
  } else {
    actionsHtml = `<span class="text-slate-500 text-[11px] flex items-center justify-end gap-1"><i data-lucide="eye-off" class="w-3 h-3"></i> Ignorado</span>`;
  }
  const suggestionHtml = it.matched_entry_description
    ? `<span class="text-xs text-blue-400 truncate max-w-[150px] block" title="${it.matched_entry_description}">${it.matched_entry_description}</span>`
    : it.suggested_category_name
    ? `<span class="text-xs text-slate-500">${it.suggested_category_name}</span>`
    : '<span class="text-xs text-slate-600">—</span>';
  return `
    <tr class="border-b border-white/5 hover:bg-white/5 text-xs transition">
      <td class="py-3 px-4 font-mono text-slate-400">${formatDate(it.date)}</td>
      <td class="py-3 px-4 font-medium text-slate-100"><div class="truncate max-w-[200px]" title="${it.memo || ''}">${it.memo || 'Lançamento OFX'}</div></td>
      <td class="py-3 px-4 text-slate-400">${it.bank_name || '—'}</td>
      <td class="py-3 px-4 font-bold font-mono ${isCredit ? 'text-emerald-400' : 'text-rose-400'}">${formatCurrency(it.amount)}</td>
      <td class="py-3 px-4">${suggestionHtml}</td>
      <td class="py-3 px-4">${actionsHtml}</td>
    </tr>`;
}

function _buildOpenFinanceSection(ofStatus) {
  const integrations = ofStatus.integrations || [];
  const intHtml = integrations.map(i => `
    <div class="flex items-center gap-2 bg-slate-800/50 border border-white/10 rounded-xl px-3 py-2">
      <div class="w-2 h-2 rounded-full flex-shrink-0 ${i.status === 'synced' ? 'bg-emerald-400' : 'bg-amber-400'}"></div>
      <div class="flex-1 min-w-0">
        <div class="text-xs font-semibold text-slate-200">${i.connector_name}</div>
        <div class="text-[10px] text-slate-500">${i.last_sync ? 'Sync: ' + formatDate(i.last_sync) : 'Nunca sincronizado'}</div>
      </div>
      <button onclick="syncOpenFinance('${i.item_id}')" title="Sincronizar" class="bg-blue-600/80 hover:bg-blue-600 text-white p-1.5 rounded-lg transition"><i data-lucide="refresh-cw" class="w-3 h-3"></i></button>
      <button onclick="disconnectOpenFinance('${i.item_id}')" title="Remover" class="bg-rose-600/80 hover:bg-rose-600 text-white p-1.5 rounded-lg transition"><i data-lucide="unlink" class="w-3 h-3"></i></button>
    </div>`).join('');

  const connectBtn = ofStatus.configured
    ? `<button onclick="connectOpenFinance()" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded-xl flex items-center gap-1.5 transition"><i data-lucide="plug" class="w-3.5 h-3.5"></i> Conectar Banco</button>`
    : `<span class="text-[11px] text-amber-400 flex items-center gap-1"><i data-lucide="alert-triangle" class="w-3.5 h-3.5"></i> Configure PLUGGY_CLIENT_ID nas variáveis de ambiente</span>`;

  return `
    <div class="cx-card rounded-2xl p-4 mb-4">
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <i data-lucide="wifi" class="w-4 h-4 text-blue-400"></i>
          <span class="font-semibold text-sm text-slate-100">Open Finance</span>
          <span class="text-[10px] font-mono bg-blue-500/15 text-blue-300 border border-blue-400/30 px-1.5 py-0.5 rounded-md">via Pluggy</span>
          ${ofStatus.configured ? '<span class="text-[10px] text-emerald-400">● Ativo</span>' : '<span class="text-[10px] text-amber-400">● Não configurado</span>'}
        </div>
        ${connectBtn}
      </div>
      ${intHtml
        ? `<div class="flex flex-wrap gap-2">${intHtml}</div>`
        : `<p class="text-xs text-slate-500">Conecte seus bancos para sincronizar extratos automaticamente — sem precisar baixar arquivos OFX.</p>`}
    </div>`;
}

function setOfxFilter(filter) {
  _ofxCurrentFilter = filter;
  renderOfx(document.getElementById('main-content'));
}

async function uploadOfxFile(e) {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  showToast('Enviando extrato OFX...', 'info');
  try {
    const res = await fetch('/api/ofx/import', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Extrato OFX importado!', 'success');
      renderOfx(document.getElementById('main-content'));
    } else {
      showToast(data.detail || 'Erro ao importar.', 'error');
    }
  } catch (err) {
    showToast('Falha no upload.', 'error');
  }
}

async function reconcileOfx(ofxId) {
  try {
    const res = await fetch(`/api/ofx/${ofxId}/reconcile`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}' });
    const data = await res.json();
    if (res.ok) { showToast(data.message || 'Conciliado!', 'success'); renderOfx(document.getElementById('main-content')); }
    else showToast(data.detail || 'Erro.', 'error');
  } catch (e) { showToast('Falha na requisição.', 'error'); }
}

async function quickReconcileOfx(ofxId) {
  try {
    const res = await fetch(`/api/ofx/${ofxId}/reconcile`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}' });
    const data = await res.json();
    if (res.ok) { showToast(data.message || 'Lançamento criado e conciliado!', 'success'); renderOfx(document.getElementById('main-content')); }
    else showToast(data.detail || 'Erro.', 'error');
  } catch (e) { showToast('Erro.', 'error'); }
}

async function autoReconcileAll() {
  showToast('Conciliando automaticamente...', 'info');
  try {
    const res = await fetch('/api/ofx/auto-reconcile-all', { method: 'POST' });
    const data = await res.json();
    if (res.ok) { showToast(data.message || `${data.reconciled} conciliadas!`, 'success'); renderOfx(document.getElementById('main-content')); }
    else showToast(data.detail || 'Erro.', 'error');
  } catch (e) { showToast('Erro.', 'error'); }
}

async function ignoreOfxTx(ofxId) {
  try {
    const res = await fetch(`/api/ofx/${ofxId}/ignore`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) { showToast('Transação ignorada.', 'info'); renderOfx(document.getElementById('main-content')); }
    else showToast(data.detail || 'Erro.', 'error');
  } catch (e) { showToast('Erro.', 'error'); }
}

async function openReconcileModal(ofxId) {
  try {
    const res = await fetch(`/api/ofx/match-suggestions/${ofxId}`);
    const { ofx, suggestions } = await res.json();
    const isCredit = ofx.amount >= 0;

    const sugRows = suggestions.map(s => `
      <tr class="border-b border-white/5 hover:bg-white/5 cursor-pointer text-xs" onclick="confirmReconcile(${ofxId}, ${s.id})">
        <td class="py-2 px-3 font-mono text-slate-400">${formatDate(s.due_date)}</td>
        <td class="py-2 px-3 font-medium text-slate-100 max-w-[180px]"><div class="truncate">${s.description}</div></td>
        <td class="py-2 px-3 font-bold font-mono ${s.type === 'receita' ? 'text-emerald-400' : 'text-rose-400'}">${formatCurrency(s.amount)}</td>
        <td class="py-2 px-3 text-slate-400">${s.category_name || '—'}</td>
        <td class="py-2 px-3">
          <div class="flex items-center gap-1">
            <div class="h-1.5 rounded-full bg-slate-700 w-14 overflow-hidden">
              <div class="h-full rounded-full ${s.score >= 0.75 ? 'bg-emerald-500' : s.score >= 0.5 ? 'bg-amber-500' : 'bg-rose-500'}" style="width:${Math.round(s.score*100)}%"></div>
            </div>
            <span class="text-[10px] font-mono text-slate-400">${Math.round(s.score*100)}%</span>
          </div>
        </td>
        <td class="py-2 px-3 text-right"><button class="bg-blue-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-lg">Usar</button></td>
      </tr>`).join('');

    openModal(`
      <div class="space-y-4">
        <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">
          <i data-lucide="git-merge" class="w-4 h-4 text-amber-400"></i> Conciliar Transação
        </h3>
        <div class="bg-slate-800/60 rounded-xl p-4 border border-white/10 flex items-center justify-between gap-4">
          <div>
            <div class="font-semibold text-slate-100">${ofx.memo || 'Lançamento OFX'}</div>
            <div class="text-xs text-slate-400">${formatDate(ofx.posted_date)} · ${ofx.bank_name || 'Banco'}</div>
          </div>
          <div class="text-xl font-bold font-mono flex-shrink-0 ${isCredit ? 'text-emerald-400' : 'text-rose-400'}">${formatCurrency(ofx.amount)}</div>
        </div>
        <div>
          <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Lançamentos Sugeridos</div>
          ${suggestions.length > 0 ? `
          <div class="bg-slate-900 rounded-xl overflow-hidden border border-white/10">
            <table class="w-full">
              <thead><tr class="text-[10px] font-bold uppercase text-slate-500 border-b border-white/10">
                <th class="py-2 px-3">Vencimento</th><th class="py-2 px-3">Descrição</th><th class="py-2 px-3">Valor</th>
                <th class="py-2 px-3">Categoria</th><th class="py-2 px-3">Match</th><th class="py-2 px-3"></th>
              </tr></thead>
              <tbody>${sugRows}</tbody>
            </table>
          </div>` : `<p class="text-xs text-slate-500 text-center py-4 border border-white/10 rounded-xl">Nenhum lançamento pendente com valor compatível encontrado.</p>`}
        </div>
        <div class="flex items-center justify-between pt-2 border-t border-white/10">
          <span class="text-xs text-slate-500">Sem correspondência? Crie um lançamento automaticamente:</span>
          <button onclick="quickReconcileOfx(${ofxId}); closeModal();" class="bg-slate-600 hover:bg-slate-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition">
            Criar Lançamento
          </button>
        </div>
      </div>`);
    lucide.createIcons();
  } catch (e) { showToast('Erro ao carregar sugestões.', 'error'); }
}

async function confirmReconcile(ofxId, entryId) {
  closeModal();
  try {
    const res = await fetch(`/api/ofx/${ofxId}/reconcile`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ matched_entry_id: entryId })
    });
    const data = await res.json();
    if (res.ok) { showToast(data.message || 'Conciliado!', 'success'); renderOfx(document.getElementById('main-content')); }
    else showToast(data.detail || 'Erro.', 'error');
  } catch (e) { showToast('Erro.', 'error'); }
}

async function connectOpenFinance() {
  try {
    const res = await fetch('/api/open-finance/connect-token', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) { showToast(data.detail || 'Erro ao iniciar conexão.', 'error'); return; }
    if (!window.PluggyConnect) {
      await new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://cdn.pluggy.ai/pluggy-connect/v2/pluggy-connect.js';
        s.onload = resolve; s.onerror = reject;
        document.head.appendChild(s);
      });
    }
    const widget = new window.PluggyConnect({
      connectToken: data.connect_token,
      onSuccess: async ({ item }) => {
        const r = await fetch('/api/open-finance/connect', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ itemId: item.id }) });
        const d = await r.json();
        if (r.ok) { showToast(d.message || 'Banco conectado!', 'success'); renderOfx(document.getElementById('main-content')); }
      },
      onError: (err) => showToast('Erro ao conectar: ' + (err.message || err), 'error'),
    });
    widget.open();
  } catch (e) { showToast('Falha ao iniciar Open Finance.', 'error'); }
}

async function syncOpenFinance(itemId) {
  showToast('Sincronizando...', 'info');
  try {
    const res = await fetch(`/api/open-finance/sync/${itemId}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) { showToast(data.message || 'Sincronizado!', 'success'); renderOfx(document.getElementById('main-content')); }
    else showToast(data.detail || 'Erro na sincronização.', 'error');
  } catch (e) { showToast('Erro.', 'error'); }
}

async function disconnectOpenFinance(itemId) {
  if (!confirm('Remover conexão com este banco?')) return;
  try {
    const res = await fetch(`/api/open-finance/disconnect/${itemId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) { showToast(data.message || 'Conexão removida.', 'info'); renderOfx(document.getElementById('main-content')); }
  } catch (e) { showToast('Erro.', 'error'); }
}

// ==============================================================================
// 4. CRM FUNIL KANBAN
// ==============================================================================
async function renderCrm(container) {
  try {
    const res = await fetch('/api/crm');
    const deals = await res.json();

    const stages = [
      { id: 'prospeccao', name: 'Prospecção' },
      { id: 'qualificacao', name: 'Qualificação' },
      { id: 'proposta', name: 'Proposta Enviada' },
      { id: 'negociacao', name: 'Negociação' },
      { id: 'ganho', name: 'Fechado Ganho' },
      { id: 'perdido', name: 'Perdido' },
    ];

    let columnsHtml = stages.map(s => {
      const stageDeals = deals.filter(d => d.stage === s.id);
      const totalStage = stageDeals.reduce((sum, d) => sum + (parseFloat(d.value) || 0), 0);

      const cardsHtml = stageDeals.map(d => `
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-xs space-y-2">
          <div class="flex justify-between items-start">
            <h4 class="font-bold text-slate-800 dark:text-slate-100 text-xs">${d.title}</h4>
            <span class="text-[10px] font-bold text-blue-600">${formatCurrency(d.value)}</span>
          </div>
          <div class="text-[11px] text-slate-400">${d.contact_name || 'Sem contato'}</div>
          <div class="flex justify-between items-center pt-2 border-t border-slate-100 dark:border-slate-800">
            <select onchange="updateDealStage(${d.id}, this.value)" class="text-[10px] bg-slate-100 dark:bg-slate-800 rounded p-1">
              ${stages.map(st => `<option value="${st.id}" ${st.id === d.stage ? 'selected' : ''}>${st.name}</option>`).join('')}
            </select>
            ${s.id === 'ganho' && !d.converted_to_sale_id ? `
              <button onclick="convertDealToSale(${d.id})" class="text-[10px] bg-emerald-600 text-white px-2 py-0.5 rounded font-semibold">
                Gerar Venda
              </button>
            ` : ''}
          </div>
        </div>
      `).join('');

      return `
        <div class="bg-slate-100 dark:bg-slate-900/50 rounded-2xl p-3 flex flex-col shrink-0 w-[280px]">
          <div class="flex justify-between items-center mb-2 px-1">
            <span class="font-bold text-xs text-slate-700 dark:text-slate-300">${s.name} (${stageDeals.length})</span>
            <span class="text-[10px] text-slate-400 font-semibold">${formatCurrency(totalStage)}</span>
          </div>
          <div class="space-y-2 flex-1 overflow-y-auto max-h-[65vh]">
            ${cardsHtml || '<div class="text-[11px] text-slate-400 text-center py-6">Vazio</div>'}
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="kanban" class="w-5 h-5 text-purple-500"></i> CRM & Funil Comercial
          </h2>
          <p class="text-xs text-slate-400">Pipeline de oportunidades, negociações e conversão em vendas</p>
        </div>
        <button onclick="openDealModal()" class="bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
          <i data-lucide="plus-circle" class="w-4 h-4"></i> Nova Oportunidade
        </button>
      </div>

      <div class="flex gap-4 overflow-x-auto pb-4 items-start">
        ${columnsHtml}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro no CRM: ${e.message}</div>`;
  }
}

function openDealModal() {
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Nova Oportunidade (CRM)</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitDeal(event)" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Título da Negociação *</label>
        <input required name="title" placeholder="Ex: Projeto Implantação ERP - Empresa X" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Valor Estimado (R$) *</label>
          <input required type="number" step="0.01" name="value" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Cliente / Prospect</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Nenhum</option>
            ${contactOpts}
          </select>
        </div>
      </div>
      <div>
        <label class="block font-semibold mb-1">Estágio Inicial</label>
        <select name="stage" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
          <option value="prospeccao">Prospecção</option>
          <option value="qualificacao">Qualificação</option>
          <option value="proposta">Proposta Enviada</option>
          <option value="negociacao">Negociação</option>
        </select>
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold">Criar Oportunidade</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitDeal(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    title: form.title.value,
    value: parseFloat(form.value.value),
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    stage: form.stage.value,
  };
  try {
    const res = await fetch('/api/crm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Oportunidade cadastrada no funil!', 'success');
      closeModal();
      renderCrm(document.getElementById('main-content'));
    } else {
      showToast('Erro ao cadastrar deal.', 'error');
    }
  } catch (err) {
    showToast('Falha na requisição.', 'error');
  }
}

async function updateDealStage(dealId, newStage) {
  try {
    const res = await fetch(`/api/crm/${dealId}/stage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage: newStage }),
    });
    if (res.ok) {
      showToast('Estágio atualizado!', 'success');
      renderCrm(document.getElementById('main-content'));
    }
  } catch (e) {
    showToast('Falha ao atualizar estágio.', 'error');
  }
}

async function convertDealToSale(dealId) {
  try {
    const res = await fetch(`/api/crm/${dealId}/convert`, { method: 'POST' });
    if (res.ok) {
      showToast('Oportunidade convertida em Venda com sucesso!', 'success');
      switchTab('sales');
    } else {
      showToast('Erro ao converter em venda.', 'error');
    }
  } catch (e) {
    showToast('Erro na requisição.', 'error');
  }
}

// ==============================================================================
// 5. VENDAS & ORÇAMENTOS
// ==============================================================================
async function renderSales(container) {
  try {
    const res = await fetch('/api/sales');
    const sales = await res.json();

    let rowsHtml = sales.map(s => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">#${s.id}</td>
        <td class="py-3 px-4 font-medium">${formatDate(s.created_at)}</td>
        <td class="py-3 px-4">${s.client_name || 'Consumidor Final'}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(s.total_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            s.status === 'aprovado' ? 'bg-emerald-500/20 text-emerald-600' :
            s.status === 'faturado' ? 'bg-blue-500/20 text-blue-600' :
            'bg-amber-500/20 text-amber-600'
          }">
            ${s.status.toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          ${s.token_access ? `
            <button onclick="copyPortalLink('${s.token_access}')" class="bg-indigo-600 hover:bg-indigo-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition" title="Copiar link do portal do cliente">
              Link Portal
            </button>
          ` : ''}
          ${s.status === 'orcamento' ? `
            <button onclick="approveSale(${s.id})" class="bg-emerald-600 hover:bg-emerald-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
              Aprovar Venda
            </button>
          ` : ''}
          <a href="#" onclick="openAuthed('/api/sales/${s.id}/print'); return false;" class="inline-block bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
            Imprimir
          </a>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="shopping-bag" class="w-5 h-5 text-blue-500"></i> Vendas & Orçamentos
          </h2>
          <p class="text-xs text-slate-400">Controle comercial, propostas comerciais, pedidos e faturamento</p>
        </div>
        <button onclick="openSaleModal('venda')" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
          <i data-lucide="plus-circle" class="w-4 h-4"></i> Nova Venda / Orçamento
        </button>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Pedido #</th>
              <th class="py-3 px-4">Data</th>
              <th class="py-3 px-4">Cliente</th>
              <th class="py-3 px-4">Valor Total</th>
              <th class="py-3 px-4">Status</th>
              <th class="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhuma venda encontrada.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro ao carregar vendas: ${e.message}</div>`;
  }
}

function openSaleModal(defaultType = 'venda') {
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const productOpts = currentProducts.map(p => `<option value="${p.id}" data-price="${p.sale_price}">${p.name} - ${formatCurrency(p.sale_price)}</option>`).join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Nova Venda ou Orçamento</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form onsubmit="submitSale(event)" class="mt-4 space-y-4 text-xs">
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Tipo de Registro</label>
          <select name="type" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="venda" ${defaultType === 'venda' ? 'selected' : ''}>Pedido de Venda (Direto)</option>
            <option value="orcamento" ${defaultType === 'orcamento' ? 'selected' : ''}>Orçamento / Proposta Comercial</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Cliente</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Consumidor Final</option>
            ${contactOpts}
          </select>
        </div>
      </div>

      <div class="border border-slate-200 dark:border-slate-700 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/30">
        <label class="block font-bold mb-2">Item Inicial</label>
        <div class="grid grid-cols-3 gap-3">
          <div class="col-span-2">
            <select id="sale-product-select" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
              ${productOpts}
            </select>
          </div>
          <div>
            <input id="sale-product-qty" type="number" min="1" value="1" placeholder="Qtd" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Condição de Pagamento</label>
          <select name="payment_method" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="Pix">Pix à Vista</option>
            <option value="Cartão de Crédito">Cartão de Crédito</option>
            <option value="Boleto">Boleto Bancário</option>
            <option value="Dinheiro">Dinheiro</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Observações</label>
          <input name="notes" placeholder="Detalhes do pedido ou frete" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Criar Registro</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitSale(e) {
  e.preventDefault();
  const form = e.target;
  const prodSelect = document.getElementById('sale-product-select');
  const qtyInput = document.getElementById('sale-product-qty');
  const prodId = prodSelect ? parseInt(prodSelect.value) : null;
  const qty = qtyInput ? parseFloat(qtyInput.value) || 1 : 1;
  const prod = currentProducts.find(p => p.id === prodId);
  const unitPrice = prod ? prod.sale_price : 100.0;

  const payload = {
    type: form.type.value,
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    payment_method: form.payment_method.value,
    notes: form.notes.value,
    items: prodId ? [{ product_id: prodId, quantity: qty, unit_price: unitPrice }] : [],
    total_amount: prodId ? (unitPrice * qty) : 0.0,
  };

  try {
    const res = await fetch('/api/sales', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Venda/Orçamento criado com sucesso!', 'success');
      closeModal();
      switchTab('sales');
    } else {
      showToast('Erro ao criar venda.', 'error');
    }
  } catch (err) {
    showToast('Falha na conexão.', 'error');
  }
}

async function approveSale(saleId) {
  try {
    const res = await fetch(`/api/sales/${saleId}/approve`, { method: 'POST' });
    if (res.ok) {
      showToast('Orçamento aprovado e faturado!', 'success');
      renderSales(document.getElementById('main-content'));
    } else {
      showToast('Erro ao aprovar orçamento.', 'error');
    }
  } catch (e) {
    showToast('Erro na requisição.', 'error');
  }
}

function copyPortalLink(token) {
  const url = `${window.location.origin}/api/portal/quote/${token}`;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => {
      showToast('Link do Portal do Cliente copiado com sucesso!', 'success');
    }).catch(() => {
      prompt('Copie o link do portal abaixo:', url);
    });
  } else {
    prompt('Copie o link do portal abaixo:', url);
  }
}

// ==============================================================================
// 6. PDV FRENTE DE CAIXA RÁPIDO
// ==============================================================================
let pdvCart = [];

async function renderPdv(container) {
  pdvCart = [];
  container.innerHTML = `
    <div class="h-full flex flex-col md:flex-row gap-6">
      <!-- LADO ESQUERDO: CATÁLOGO DE PRODUTOS -->
      <div class="flex-1 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="monitor-smartphone" class="w-5 h-5 text-cyan-500"></i> PDV Frente de Caixa
          </h2>
          <input
            id="pdv-search"
            type="text"
            placeholder="Buscar produto por nome, SKU ou leitor de código de barras..."
            oninput="filterPdvProducts(this.value)"
            class="bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs w-72 focus:outline-none"
          />
        </div>
        <div id="pdv-products-grid" class="grid grid-cols-2 lg:grid-cols-3 gap-3 flex-1 overflow-y-auto max-h-[60vh] p-1">
          ${renderPdvCards(currentProducts)}
        </div>
      </div>

      <!-- LADO DIREITO: CUPOM & CARRINHO -->
      <div class="w-full md:w-96 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
        <div class="font-bold text-sm text-slate-800 dark:text-slate-100 pb-3 border-b border-slate-100 dark:border-slate-800 flex justify-between">
          <span>Cupom de Venda</span>
          <button onclick="clearPdvCart()" class="text-xs text-rose-500 hover:underline">Limpar</button>
        </div>

        <div id="pdv-cart-items" class="flex-1 overflow-y-auto space-y-2 py-3 min-h-[200px]">
          <div class="text-xs text-slate-400 text-center py-12">Nenhum item adicionado</div>
        </div>

        <div class="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
          <div class="flex justify-between items-center text-sm font-extrabold">
            <span>Total a Pagar:</span>
            <span id="pdv-cart-total" class="text-xl text-blue-600">R$ 0,00</span>
          </div>
          <div>
            <label class="block text-[11px] font-semibold text-slate-500 mb-1">Forma de Pagamento:</label>
            <select id="pdv-payment-method" class="w-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs font-semibold">
              <option value="Pix">Pix Instantâneo</option>
              <option value="Cartão de Débito">Cartão de Débito</option>
              <option value="Cartão de Crédito">Cartão de Crédito</option>
              <option value="Dinheiro">Dinheiro</option>
            </select>
          </div>
          <button onclick="finalizePdvSale()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-xl shadow-lg transition text-sm flex items-center justify-center gap-2">
            <i data-lucide="check-circle" class="w-4 h-4"></i> Finalizar Venda & Emitir NFC-e
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderPdvCards(products) {
  if (!products.length) return '<div class="col-span-3 text-center text-slate-400 text-xs py-8">Nenhum produto cadastrado.</div>';
  return products.map(p => `
    <div onclick="addPdvItem(${p.id})" class="cursor-pointer border border-slate-200 dark:border-slate-800 hover:border-blue-500 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/40 hover:bg-blue-50/20 transition flex flex-col justify-between">
      <div>
        <div class="font-bold text-xs text-slate-800 dark:text-slate-100 line-clamp-1">${p.name}</div>
        <div class="text-[10px] text-slate-400">SKU: ${p.sku || '-'} · Est: ${p.stock_current}</div>
      </div>
      <div class="mt-2 flex justify-between items-center">
        <span class="font-extrabold text-blue-600 dark:text-blue-400 text-xs">${formatCurrency(p.sale_price)}</span>
        <span class="text-[10px] bg-blue-100 text-blue-700 font-bold px-1.5 py-0.5 rounded">+</span>
      </div>
    </div>
  `).join('');
}

function filterPdvProducts(term) {
  const filtered = currentProducts.filter(p =>
    p.name.toLowerCase().includes(term.toLowerCase()) ||
    (p.sku && p.sku.toLowerCase().includes(term.toLowerCase()))
  );
  const grid = document.getElementById('pdv-products-grid');
  if (grid) grid.innerHTML = renderPdvCards(filtered);
}

function addPdvItem(prodId) {
  const prod = currentProducts.find(p => p.id === prodId);
  if (!prod) return;
  const existing = pdvCart.find(i => i.product_id === prodId);
  if (existing) {
    existing.quantity += 1;
  } else {
    pdvCart.push({
      product_id: prod.id,
      name: prod.name,
      unit_price: prod.sale_price,
      quantity: 1,
    });
  }
  updatePdvCartUi();
}

function removePdvItem(prodId) {
  pdvCart = pdvCart.filter(i => i.product_id !== prodId);
  updatePdvCartUi();
}

function clearPdvCart() {
  pdvCart = [];
  updatePdvCartUi();
}

function updatePdvCartUi() {
  const container = document.getElementById('pdv-cart-items');
  const totalEl = document.getElementById('pdv-cart-total');
  if (!container || !totalEl) return;

  if (pdvCart.length === 0) {
    container.innerHTML = '<div class="text-xs text-slate-400 text-center py-12">Nenhum item adicionado</div>';
    totalEl.innerText = formatCurrency(0);
    return;
  }

  let total = 0;
  container.innerHTML = pdvCart.map(item => {
    const sub = item.unit_price * item.quantity;
    total += sub;
    return `
      <div class="flex justify-between items-center text-xs p-2 rounded-lg bg-slate-50 dark:bg-slate-800">
        <div class="truncate pr-2">
          <div class="font-bold truncate text-slate-800 dark:text-slate-100">${item.name}</div>
          <div class="text-[10px] text-slate-400">${item.quantity}x ${formatCurrency(item.unit_price)}</div>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-slate-900 dark:text-slate-100">${formatCurrency(sub)}</span>
          <button onclick="removePdvItem(${item.product_id})" class="text-rose-500 hover:text-rose-700"><i data-lucide="x" class="w-3.5 h-3.5"></i></button>
        </div>
      </div>
    `;
  }).join('');
  totalEl.innerText = formatCurrency(total);
  if (window.lucide) lucide.createIcons();
}

async function finalizePdvSale() {
  if (pdvCart.length === 0) {
    showToast('Adicione produtos ao cupom antes de finalizar.', 'warning');
    return;
  }
  const payMethod = document.getElementById('pdv-payment-method').value;
  const total = pdvCart.reduce((sum, i) => sum + (i.unit_price * i.quantity), 0);

  const payload = {
    type: 'pdv',
    payment_method: payMethod,
    items: pdvCart,
    total_amount: total,
    notes: 'Venda rápida balcão PDV',
  };

  try {
    const res = await fetch('/api/sales', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = await res.json();
      showToast(`Venda PDV #${data.id} realizada com sucesso!`, 'success');
      clearPdvCart();
    } else {
      showToast('Erro ao concluir venda no PDV.', 'error');
    }
  } catch (e) {
    showToast('Falha ao comunicar com PDV.', 'error');
  }
}

// ==============================================================================
// 7. ORDENS DE SERVIÇO & CONTRATOS RECORRENTES
// ==============================================================================
async function renderServiceOrders(container) {
  try {
    const [osRes, contRes] = await Promise.all([
      fetch('/api/service-orders').then(r => r.json()),
      fetch('/api/contracts').then(r => r.json()),
    ]);

    const osList = Array.isArray(osRes) ? osRes : [];
    const contracts = Array.isArray(contRes) ? contRes : [];

    let osRows = osList.map(os => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold">#${os.id}</td>
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">${os.title}</td>
        <td class="py-3 px-4">${os.client_name || 'Sem cliente'}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(os.total_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            os.status === 'concluido' ? 'bg-emerald-500/20 text-emerald-600' :
            os.status === 'faturado' ? 'bg-blue-500/20 text-blue-600' :
            'bg-amber-500/20 text-amber-600'
          }">
            ${os.status.toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          ${os.status !== 'faturado' ? `
            <button onclick="billServiceOrder(${os.id})" class="bg-blue-600 hover:bg-blue-700 text-white px-2.5 py-1 rounded-lg font-semibold text-[11px] transition">
              Faturar OS
            </button>
          ` : ''}
          <a href="#" onclick="openAuthed('/api/service-orders/${os.id}/print'); return false;" class="inline-block bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2.5 py-1 rounded-lg font-semibold text-[11px]">
            Imprimir
          </a>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="wrench" class="w-5 h-5 text-orange-500"></i> Ordens de Serviço & Contratos Recorrentes
          </h2>
          <p class="text-xs text-slate-400">Prestação de serviços técnicos, faturamento recorrente e emissão de NFS-e</p>
        </div>
        <button onclick="openOsModal()" class="bg-orange-600 hover:bg-orange-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
          <i data-lucide="plus-circle" class="w-4 h-4"></i> Nova Ordem de Serviço
        </button>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">OS #</th>
              <th class="py-3 px-4">Serviço / Título</th>
              <th class="py-3 px-4">Cliente</th>
              <th class="py-3 px-4">Valor Total</th>
              <th class="py-3 px-4">Status</th>
              <th class="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            ${osRows || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhuma Ordem de Serviço registrada.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro em OS: ${e.message}</div>`;
  }
}

function openOsModal() {
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Nova Ordem de Serviço</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitOs(event)" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Título / Equipamento / Escopo do Serviço *</label>
        <input required name="title" placeholder="Ex: Manutenção Servidor Dell ou Instalação Cabeamento" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Cliente</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${contactOpts}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Valor do Serviço (R$) *</label>
          <input required type="number" step="0.01" name="total_amount" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>
      <div>
        <label class="block font-semibold mb-1">Laudo / Descrição dos Trabalhos</label>
        <textarea name="description" rows="3" placeholder="Diagnóstico do problema e serviços executados" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5"></textarea>
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-700 text-white font-bold">Salvar OS</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitOs(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    title: form.title.value,
    contact_id: form.contact_id.value ? parseInt(form.contact_id.value) : null,
    total_amount: parseFloat(form.total_amount.value),
    description: form.description.value,
  };
  try {
    const res = await fetch('/api/service-orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Ordem de Serviço criada com sucesso!', 'success');
      closeModal();
      renderServiceOrders(document.getElementById('main-content'));
    } else {
      showToast('Erro ao criar OS.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

async function billServiceOrder(osId) {
  try {
    const res = await fetch(`/api/service-orders/${osId}/bill`, { method: 'POST' });
    if (res.ok) {
      showToast('OS faturada e enviada para o Contas a Receber!', 'success');
      renderServiceOrders(document.getElementById('main-content'));
    } else {
      showToast('Erro ao faturar OS.', 'error');
    }
  } catch (e) {
    showToast('Falha na conexão.', 'error');
  }
}

// ==============================================================================
// 8. ESTOQUE, PRODUTOS & CLIENTES / FORNECEDORES
// ==============================================================================
async function renderInventory(container) {
  try {
    const products = currentProducts;

    let prodRows = products.map(p => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">${p.name}</td>
        <td class="py-3 px-4 text-slate-400 font-mono">${p.sku || '-'}</td>
        <td class="py-3 px-4">${p.ncm || '-'}</td>
        <td class="py-3 px-4 font-bold ${p.stock_current <= p.stock_min ? 'text-rose-600' : 'text-slate-800 dark:text-slate-100'}">
          ${p.stock_current} ${p.unit || 'UN'}
        </td>
        <td class="py-3 px-4 text-slate-500">${formatCurrency(p.cost_price)}</td>
        <td class="py-3 px-4 font-extrabold text-blue-600 dark:text-blue-400">${formatCurrency(p.sale_price)}</td>
        <td class="py-3 px-4 text-right">
          <button onclick="openStockAdjustModal(${p.id}, '${p.name}', ${p.stock_current})" class="bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 px-2 py-1 rounded-lg font-semibold text-[11px] transition">
            Ajustar Estoque
          </button>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="package-search" class="w-5 h-5 text-indigo-500"></i> Catálogo de Produtos, Estoque & XML
          </h2>
          <p class="text-xs text-slate-400">Controle de inventário, kardex, ficha fiscal e importação de XML de compras</p>
        </div>
        <div class="flex gap-2">
          <input type="file" id="xml-purchase-input" accept=".xml" class="hidden" onchange="uploadPurchaseXml(event)">
          <button onclick="document.getElementById('xml-purchase-input').click()" class="bg-indigo-50 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 font-semibold px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 transition">
            <i data-lucide="file-code" class="w-4 h-4"></i> Importar XML Compra
          </button>
          <button onclick="openProductModal()" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="plus-circle" class="w-4 h-4"></i> Novo Produto
          </button>
          <button onclick="openContactModal()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="user-plus" class="w-4 h-4"></i> Novo Cliente/Fornecedor
          </button>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Produto</th>
              <th class="py-3 px-4">SKU / Código</th>
              <th class="py-3 px-4">NCM</th>
              <th class="py-3 px-4">Estoque Atual</th>
              <th class="py-3 px-4">Custo Médio</th>
              <th class="py-3 px-4">Preço Venda</th>
              <th class="py-3 px-4 text-right">Ação</th>
            </tr>
          </thead>
          <tbody>
            ${prodRows || `<tr><td colspan="7" class="py-8 text-center text-slate-400 text-xs">Nenhum produto em estoque.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro em Produtos: ${e.message}</div>`;
  }
}

function openProductModal() {
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Novo Produto / Serviço</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitProduct(event)" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Nome do Produto *</label>
        <input required name="name" placeholder="Ex: Teclado Mecânico RGB ou Licença Software" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="block font-semibold mb-1">SKU / Código Interno</label>
          <input name="sku" placeholder="PRD-001" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">NCM Fiscal</label>
          <input name="ncm" placeholder="8471.60.52" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">CFOP Padrão</label>
          <input name="cfop" value="5102" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>
      <div class="grid grid-cols-3 gap-4">
        <div>
          <label class="block font-semibold mb-1">Preço de Custo (R$)</label>
          <input type="number" step="0.01" name="cost_price" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Preço de Venda (R$) *</label>
          <input required type="number" step="0.01" name="sale_price" placeholder="0.00" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Estoque Inicial</label>
          <input type="number" name="stock_current" value="0" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Cadastrar Produto</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitProduct(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    name: form.name.value,
    sku: form.sku.value,
    ncm: form.ncm.value,
    cfop: form.cfop.value,
    cost_price: parseFloat(form.cost_price.value) || 0.0,
    sale_price: parseFloat(form.sale_price.value) || 0.0,
    stock_current: parseFloat(form.stock_current.value) || 0.0,
  };
  try {
    const res = await fetch('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Produto cadastrado!', 'success');
      closeModal();
      switchTab('inventory');
    } else {
      showToast('Erro ao cadastrar produto.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

function openStockAdjustModal(prodId, prodName, currentStock) {
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Ajustar Estoque: ${prodName}</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitStockAdjust(event, ${prodId})" class="mt-4 space-y-4 text-xs">
      <div>
        <label class="block font-semibold mb-1">Novo Saldo de Estoque Real</label>
        <input required type="number" step="1" name="new_stock" value="${currentStock}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div>
        <label class="block font-semibold mb-1">Motivo do Ajuste</label>
        <input name="reason" placeholder="Ex: Inventário Físico ou Avaria" value="Inventário de rotina" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
      </div>
      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">Salvar Ajuste</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function submitStockAdjust(e, prodId) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    new_stock: parseFloat(form.new_stock.value),
    reason: form.reason.value,
  };
  try {
    const res = await fetch(`/api/products/${prodId}/stock-adjust`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Estoque ajustado com sucesso!', 'success');
      closeModal();
      switchTab('inventory');
    } else {
      showToast('Erro ao ajustar estoque.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

async function uploadPurchaseXml(e) {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  showToast('Processando XML de Compra (NF-e)...', 'info');
  try {
    const res = await fetch('/api/xml-purchases/import', { method: 'POST', body: formData });
    if (res.ok) {
      showToast('Nota de compra importada, produtos atualizados e contas geradas!', 'success');
      switchTab('inventory');
    } else {
      showToast('Erro ao importar XML de compra.', 'error');
    }
  } catch (err) {
    showToast('Falha no upload do XML.', 'error');
  }
}

// Modal Cadastro de Contatos com Busca CNPJ e CEP
function openContactModal() {
  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100">Novo Cliente / Fornecedor</h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>
    <form onsubmit="submitContact(event)" class="mt-4 space-y-4 text-xs">
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">Tipo de Cadastro</label>
          <select name="type" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="cliente">Cliente</option>
            <option value="fornecedor">Fornecedor</option>
            <option value="ambos">Cliente & Fornecedor</option>
          </select>
        </div>
        <div class="col-span-2">
          <label class="block font-semibold mb-1">CNPJ / CPF</label>
          <div class="flex gap-2">
            <input id="contact-doc" name="document" placeholder="00.000.000/0000-00" class="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <button type="button" onclick="lookupCnpj()" class="bg-blue-600 text-white font-semibold px-3 py-2 rounded-xl text-xs flex items-center gap-1">
              <i data-lucide="search" class="w-3.5 h-3.5"></i> Consultar
            </button>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block font-semibold mb-1">Razão Social / Nome Completo *</label>
          <input required id="contact-name" name="name" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Nome Fantasia</label>
          <input id="contact-trade-name" name="trade_name" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">CEP</label>
          <div class="flex gap-2">
            <input id="contact-cep" name="cep" placeholder="00000-000" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <button type="button" onclick="lookupCep()" class="bg-slate-200 dark:bg-slate-700 px-2.5 rounded-xl font-bold">CEP</button>
          </div>
        </div>
        <div class="col-span-2">
          <label class="block font-semibold mb-1">Logradouro / Rua</label>
          <input id="contact-street" name="street" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">Número</label>
          <input id="contact-number" name="number" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Bairro</label>
          <input id="contact-neighborhood" name="neighborhood" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Cidade / UF</label>
          <div class="flex gap-1">
            <input id="contact-city" name="city" placeholder="Cidade" class="flex-1 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <input id="contact-state" name="state" placeholder="UF" maxlength="2" class="w-12 text-center bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-4 border-t border-slate-200 dark:border-slate-800">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold">Salvar Contato</button>
      </div>
    </form>
  `;
  openModal(html);
}

async function lookupCnpj() {
  const docInput = document.getElementById('contact-doc');
  if (!docInput || !docInput.value) return;
  const raw = docInput.value.replace(/\D/g, '');
  if (raw.length !== 14) {
    showToast('CNPJ deve ter 14 dígitos.', 'warning');
    return;
  }
  showToast('Consultando Receita Federal via BrasilAPI...', 'info');
  try {
    const res = await fetch(`/api/lookup/cnpj/${raw}`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('contact-name').value = data.name || '';
      document.getElementById('contact-trade-name').value = data.trade_name || '';
      document.getElementById('contact-cep').value = data.cep || '';
      document.getElementById('contact-street').value = data.street || '';
      document.getElementById('contact-number').value = data.number || '';
      document.getElementById('contact-neighborhood').value = data.neighborhood || '';
      document.getElementById('contact-city').value = data.city || '';
      document.getElementById('contact-state').value = data.state || '';
      showToast('Dados do CNPJ preenchidos automaticamente!', 'success');
    } else {
      showToast('CNPJ não encontrado ou serviço indisponível.', 'error');
    }
  } catch (e) {
    showToast('Falha na consulta do CNPJ.', 'error');
  }
}

async function lookupCep() {
  const cepInput = document.getElementById('contact-cep');
  if (!cepInput || !cepInput.value) return;
  const raw = cepInput.value.replace(/\D/g, '');
  if (raw.length !== 8) {
    showToast('CEP deve ter 8 dígitos.', 'warning');
    return;
  }
  try {
    const res = await fetch(`/api/lookup/cep/${raw}`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById('contact-street').value = data.street || '';
      document.getElementById('contact-neighborhood').value = data.neighborhood || '';
      document.getElementById('contact-city').value = data.city || '';
      document.getElementById('contact-state').value = data.state || '';
      showToast('Endereço preenchido!', 'success');
    } else {
      showToast('CEP não encontrado.', 'error');
    }
  } catch (e) {
    showToast('Falha ao buscar CEP.', 'error');
  }
}

async function submitContact(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    type: form.type.value,
    document: form.document.value,
    name: form.name.value,
    trade_name: form.trade_name.value,
    cep: form.cep.value,
    street: form.street.value,
    number: form.number.value,
    neighborhood: form.neighborhood.value,
    city: form.city.value,
    state: form.state.value,
  };
  try {
    const res = await fetch('/api/contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Contato cadastrado com sucesso!', 'success');
      closeModal();
      await preloadLookups();
      switchTab('inventory');
    } else {
      showToast('Erro ao cadastrar contato.', 'error');
    }
  } catch (e) {
    showToast('Falha na comunicação.', 'error');
  }
}

// ==============================================================================
// 9. EMISSOR FISCAL (NF-e, NFC-e, NFS-e)
// ==============================================================================
async function renderInvoices(container) {
  try {
    const res = await fetch('/api/invoices');
    const invoices = await res.json();

    let rowsHtml = invoices.map(inv => `
      <tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
        <td class="py-3 px-4 font-bold text-slate-800 dark:text-slate-100">
          ${inv.model ? inv.model.toUpperCase() : 'NF-E'} #${inv.number || inv.id}
        </td>
        <td class="py-3 px-4 font-medium">${formatDate(inv.issue_date || inv.created_at)}</td>
        <td class="py-3 px-4">${inv.recipient_name || 'Consumidor'}</td>
        <td class="py-3 px-4 font-bold text-slate-900 dark:text-slate-100">${formatCurrency(inv.total_amount)}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
            inv.status === 'autorizada' ? 'bg-emerald-500/20 text-emerald-600' :
            inv.status === 'cancelada' ? 'bg-rose-500/20 text-rose-600' :
            'bg-amber-500/20 text-amber-600'
          }">
            ${(inv.status || 'AUTORIZADA').toUpperCase()}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-1">
          <a href="#" onclick="openAuthed('/api/invoices/${inv.id}/danfe'); return false;" class="inline-block bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 px-2 py-1 rounded-lg font-semibold text-[11px] transition">
            DANFE
          </a>
          <a href="#" onclick="openAuthed('/api/invoices/${inv.id}/xml'); return false;" class="inline-block bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-1 rounded-lg font-semibold text-[11px]">
            XML
          </a>
          ${inv.status === 'autorizada' ? `
            <button onclick="cancelInvoicePrompt(${inv.id})" class="text-rose-600 hover:text-rose-800 px-2 py-1 text-[11px] font-semibold">
              Cancelar
            </button>
          ` : ''}
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <i data-lucide="receipt" class="w-5 h-5 text-emerald-500"></i> Emissor Fiscal Inteligente (NF-e, NFC-e, NFS-e)
          </h2>
          <p class="text-xs text-slate-400">Emissão de notas fiscais com assinatura digital, DANFE em PDF e arquivo XML</p>
        </div>
        <div class="flex gap-2">
          <a href="#" onclick="openAuthed('/api/invoices/export-zip', 'XMLs_Contabilidade_CortexERP.zip'); return false;" class="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold px-3 py-2 rounded-xl flex items-center gap-1.5 transition">
            <i data-lucide="archive" class="w-4 h-4"></i> Exportar ZIP Contabilidade
          </a>
          <button onclick="openEmitInvoiceModal()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-sm transition">
            <i data-lucide="file-check" class="w-4 h-4"></i> Emitir Nova Nota Fiscal
          </button>
        </div>
      </div>

      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="py-3 px-4">Nota / Modelo</th>
              <th class="py-3 px-4">Data Emissão</th>
              <th class="py-3 px-4">Destinatário</th>
              <th class="py-3 px-4">Valor Total</th>
              <th class="py-3 px-4">Status SEFAZ</th>
              <th class="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || `<tr><td colspan="6" class="py-8 text-center text-slate-400 text-xs">Nenhuma nota fiscal emitida ainda.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro no Emissor Fiscal: ${e.message}</div>`;
  }
}

// Estado global dos itens do formulário de emissão fiscal
let invoiceItems = [];
let invItemCounter = 0;

function openEmitInvoiceModal() {
  invoiceItems = [];
  invItemCounter = 0;
  const contactOpts = currentContacts.map(c => `<option value="${c.id}">${c.name} (${c.document || 'Sem doc'})</option>`).join('');

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
        <i data-lucide="file-check" class="w-5 h-5 text-emerald-500"></i> Emissão de Documento Fiscal
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form id="emit-invoice-form" onsubmit="submitEmitInvoice(event)" class="mt-4 space-y-4 text-xs">

      <!-- 1. IDENTIFICAÇÃO -->
      <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        <div class="bg-slate-100 dark:bg-slate-800 px-4 py-2 font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
          1. Identificação do Documento
        </div>
        <div class="p-4 space-y-3">
          <div class="grid grid-cols-3 gap-3">
            <div>
              <label class="block font-semibold mb-1">Modelo *</label>
              <select name="model" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                <option value="55">NF-e (Mod. 55 — Mercadorias)</option>
                <option value="65">NFC-e (Mod. 65 — Consumidor)</option>
                <option value="nfse">NFS-e (Serviços Municipal)</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold mb-1">Finalidade *</label>
              <select name="finalidade" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                <option value="1">1 — NF-e Normal</option>
                <option value="2">2 — NF-e Complementar</option>
                <option value="3">3 — NF-e de Ajuste</option>
                <option value="4">4 — Devolução / Retorno</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold mb-1">Tipo de Operação *</label>
              <select name="tipo_operacao" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                <option value="1">1 — Saída</option>
                <option value="0">0 — Entrada</option>
              </select>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block font-semibold mb-1">Destino da Operação *</label>
              <select name="destino_operacao" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                <option value="1">1 — Operação Interna</option>
                <option value="2">2 — Operação Interestadual</option>
                <option value="3">3 — Operação com Exterior</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold mb-1">Presença do Comprador *</label>
              <select name="ind_presenca" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                <option value="1">1 — Presencial</option>
                <option value="2">2 — Operação pela Internet</option>
                <option value="3">3 — Teleatendimento</option>
                <option value="4">4 — Entrega em Domicílio (NFC-e)</option>
                <option value="9">9 — Outros</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block font-semibold mb-1">Natureza da Operação *</label>
            <input name="natureza_operacao" value="VENDA DE MERCADORIA DENTRO DO ESTADO"
              class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
          </div>
        </div>
      </div>

      <!-- 2. DESTINATÁRIO -->
      <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        <div class="bg-slate-100 dark:bg-slate-800 px-4 py-2 font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
          2. Destinatário
        </div>
        <div class="p-4 grid grid-cols-2 gap-3">
          <div>
            <label class="block font-semibold mb-1">Destinatário *</label>
            <select name="recipient_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
              <option value="">Consumidor Final Não Identificado</option>
              ${contactOpts}
            </select>
          </div>
          <div>
            <label class="block font-semibold mb-1">Indicador IE do Destinatário</label>
            <select name="ind_ie_dest" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
              <option value="9">9 — Não Contribuinte / SUFRAMA</option>
              <option value="1">1 — Contribuinte do ICMS</option>
              <option value="2">2 — Contribuinte Isento de IE</option>
            </select>
          </div>
        </div>
      </div>

      <!-- 3. ITENS -->
      <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        <div class="bg-slate-100 dark:bg-slate-800 px-4 py-2 font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center justify-between">
          <span>3. Itens / Produtos</span>
          <button type="button" onclick="addInvoiceItem()"
            class="bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1 rounded-lg font-semibold text-[11px]">
            + Adicionar Item
          </button>
        </div>
        <div class="p-4">
          <div id="invoice-items-list" class="space-y-3"></div>
          <p id="invoice-items-empty" class="text-center text-slate-400 py-3 italic">
            Clique em "+ Adicionar Item" para incluir produtos na nota.
          </p>
        </div>
      </div>

      <!-- 4. FRETE & PAGAMENTO -->
      <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        <div class="bg-slate-100 dark:bg-slate-800 px-4 py-2 font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
          4. Frete, Totais & Pagamento
        </div>
        <div class="p-4 space-y-3">
          <div class="grid grid-cols-3 gap-3">
            <div>
              <label class="block font-semibold mb-1">Modalidade do Frete</label>
              <select name="modalidade_frete" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                <option value="9">9 — Sem Frete</option>
                <option value="0">0 — Por conta do Emitente (CIF)</option>
                <option value="1">1 — Por conta do Destinatário (FOB)</option>
                <option value="2">2 — Por conta de Terceiros</option>
                <option value="3">3 — Próprio / Emitente</option>
                <option value="4">4 — Próprio / Destinatário</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold mb-1">Valor do Frete (R$)</label>
              <input name="shipping_amount" type="number" step="0.01" min="0" value="0"
                class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
            <div>
              <label class="block font-semibold mb-1">Desconto Geral (R$)</label>
              <input name="discount_amount" type="number" step="0.01" min="0" value="0"
                class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block font-semibold mb-1">Forma de Pagamento *</label>
              <select name="forma_pagamento" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                <option value="01">01 — Dinheiro</option>
                <option value="15">15 — PIX</option>
                <option value="03">03 — Cartão de Crédito</option>
                <option value="04">04 — Cartão de Débito</option>
                <option value="02">02 — Cheque</option>
                <option value="14">14 — Duplicata Mercantil</option>
                <option value="10">10 — Vale Alimentação</option>
                <option value="11">11 — Vale Refeição</option>
                <option value="05">05 — Crédito em Loja</option>
                <option value="99">99 — Outros</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold mb-1">Outras Despesas Acessórias (R$)</label>
              <input name="outras_despesas" type="number" step="0.01" min="0" value="0"
                class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
          </div>
        </div>
      </div>

      <!-- 5. INFORMAÇÕES ADICIONAIS -->
      <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        <div class="bg-slate-100 dark:bg-slate-800 px-4 py-2 font-bold text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
          5. Informações Adicionais
        </div>
        <div class="p-4 space-y-3">
          <div>
            <label class="block font-semibold mb-1">Informações Complementares (para o consumidor)</label>
            <textarea name="informacoes_adicionais" rows="2"
              placeholder="Ex: Pedido nº 123 | Validade 12 meses | Garantia de fábrica..."
              class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 resize-none"></textarea>
          </div>
          <div>
            <label class="block font-semibold mb-1">Informações de Interesse do Fisco</label>
            <textarea name="informe_fisco" rows="2"
              placeholder="Ex: NF referenciada: chave com 44 dígitos..."
              class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 resize-none"></textarea>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
        <button type="submit" class="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold flex items-center gap-2">
          <i data-lucide="send" class="w-4 h-4"></i> Transmitir para SEFAZ
        </button>
      </div>
    </form>
  `;
  openModal(html);
  addInvoiceItem();
}

function _invItemRowHtml(idx) {
  const prodOpts = currentProducts.map(p =>
    `<option value="${p.id}" data-price="${p.sale_price||0}" data-ncm="${p.ncm||''}" data-cfop="${p.cfop_internal||'5102'}" data-csosn="${p.csosn_cst||'102'}">${p.name}</option>`
  ).join('');
  return `
    <div id="inv-item-${idx}" class="border border-slate-200 dark:border-slate-700 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/30 space-y-2">
      <div class="flex items-center justify-between">
        <span class="font-bold text-slate-600 dark:text-slate-300">Item ${idx + 1}</span>
        <button type="button" onclick="removeInvoiceItem(${idx})" class="text-rose-500 hover:text-rose-700 text-[11px] font-semibold">Remover</button>
      </div>
      <div class="grid grid-cols-4 gap-2">
        <div class="col-span-2">
          <label class="block font-semibold mb-1">Produto / Serviço *</label>
          <select id="inv-item-prod-${idx}" onchange="invItemFillFromProduct(${idx})"
            class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            ${prodOpts}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Quantidade *</label>
          <input id="inv-item-qty-${idx}" type="number" step="0.001" min="0.001" value="1"
            class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
        </div>
        <div>
          <label class="block font-semibold mb-1">Unidade</label>
          <select id="inv-item-unit-${idx}" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            <option value="UN">UN</option><option value="CX">CX</option><option value="KG">KG</option>
            <option value="L">L</option><option value="M">M</option><option value="M2">M²</option>
            <option value="M3">M³</option><option value="PC">PC</option><option value="PAR">PAR</option>
            <option value="HR">HR</option><option value="SC">SC</option><option value="FD">FD</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-4 gap-2">
        <div>
          <label class="block font-semibold mb-1">Valor Unit. (R$) *</label>
          <input id="inv-item-price-${idx}" type="number" step="0.01" min="0" value="0"
            class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
        </div>
        <div>
          <label class="block font-semibold mb-1">Desconto Unit. (R$)</label>
          <input id="inv-item-disc-${idx}" type="number" step="0.01" min="0" value="0"
            class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
        </div>
        <div>
          <label class="block font-semibold mb-1">NCM *</label>
          <input id="inv-item-ncm-${idx}" type="text" maxlength="8" placeholder="00000000"
            class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
        </div>
        <div>
          <label class="block font-semibold mb-1">CFOP *</label>
          <input id="inv-item-cfop-${idx}" type="text" maxlength="4" placeholder="5102" value="5102"
            class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
        </div>
      </div>
      <div class="grid grid-cols-3 gap-2">
        <div>
          <label class="block font-semibold mb-1">CSOSN / CST</label>
          <select id="inv-item-csosn-${idx}" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            <option value="102">102 — Trib. s/ permissão de crédito (SN)</option>
            <option value="103">103 — Isenção do ICMS / receita bruta (SN)</option>
            <option value="300">300 — Imune (SN)</option>
            <option value="400">400 — Não tributada pelo Simples Nacional</option>
            <option value="500">500 — ICMS cobrado anteriormente por ST</option>
            <option value="900">900 — Outros (SN)</option>
            <option value="00">00 — Tributada integralmente (Regime Normal)</option>
            <option value="20">20 — Com redução de BC</option>
            <option value="40">40 — Isenta</option>
            <option value="41">41 — Não tributada</option>
            <option value="50">50 — Suspensão</option>
            <option value="51">51 — Diferimento</option>
            <option value="60">60 — ICMS cobrado anteriormente por ST</option>
            <option value="70">70 — Red. BC + cobrança do ICMS-ST</option>
            <option value="90">90 — Outras</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Origem do Produto</label>
          <select id="inv-item-origin-${idx}" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            <option value="0">0 — Nacional</option>
            <option value="1">1 — Estrangeira (importação direta)</option>
            <option value="2">2 — Estrangeira (mercado interno)</option>
            <option value="3">3 — Nacional c/ +40% conteúdo estrangeiro</option>
            <option value="4">4 — Nacional / processo produtivo básico</option>
            <option value="5">5 — Nacional c/ até 40% conteúdo estrangeiro</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">GTIN / EAN (opcional)</label>
          <input id="inv-item-ean-${idx}" type="text" placeholder="SEM GTIN"
            class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
        </div>
      </div>
    </div>
  `;
}

function addInvoiceItem() {
  const list = document.getElementById('invoice-items-list');
  const empty = document.getElementById('invoice-items-empty');
  if (!list) return;
  const idx = invItemCounter++;
  invoiceItems.push(idx);
  list.insertAdjacentHTML('beforeend', _invItemRowHtml(idx));
  if (empty) empty.style.display = 'none';
  if (window.lucide) lucide.createIcons();
  invItemFillFromProduct(idx);
}

function removeInvoiceItem(idx) {
  const el = document.getElementById(`inv-item-${idx}`);
  if (el) el.remove();
  invoiceItems = invoiceItems.filter(i => i !== idx);
  const list = document.getElementById('invoice-items-list');
  const empty = document.getElementById('invoice-items-empty');
  if (empty && list && list.children.length === 0) empty.style.display = '';
}

function invItemFillFromProduct(idx) {
  const sel = document.getElementById(`inv-item-prod-${idx}`);
  if (!sel) return;
  const prodId = parseInt(sel.value);
  const prod = currentProducts.find(p => p.id === prodId);
  if (!prod) return;
  const priceEl = document.getElementById(`inv-item-price-${idx}`);
  const ncmEl   = document.getElementById(`inv-item-ncm-${idx}`);
  const cfopEl  = document.getElementById(`inv-item-cfop-${idx}`);
  const csosnEl = document.getElementById(`inv-item-csosn-${idx}`);
  if (priceEl) priceEl.value = prod.sale_price || 0;
  if (ncmEl)   ncmEl.value   = prod.ncm || '';
  if (cfopEl)  cfopEl.value  = prod.cfop_internal || '5102';
  if (csosnEl && prod.csosn_cst) {
    for (const o of csosnEl.options) { if (o.value === String(prod.csosn_cst)) { o.selected = true; break; } }
  }
}

async function submitEmitInvoice(e) {
  e.preventDefault();
  const form = e.target;

  const items = invoiceItems.map(idx => {
    const prodSel = document.getElementById(`inv-item-prod-${idx}`);
    const prodId  = prodSel ? parseInt(prodSel.value) : null;
    const prod    = prodId  ? currentProducts.find(p => p.id === prodId) : null;
    return {
      product_id:      prodId,
      name:            prod?.name || 'Item',
      quantity:        parseFloat(document.getElementById(`inv-item-qty-${idx}`)?.value   || 1),
      unit_price:      parseFloat(document.getElementById(`inv-item-price-${idx}`)?.value || 0),
      discount_amount: parseFloat(document.getElementById(`inv-item-disc-${idx}`)?.value  || 0),
      ncm:             document.getElementById(`inv-item-ncm-${idx}`)?.value   || (prod?.ncm || '84716052'),
      cfop:            document.getElementById(`inv-item-cfop-${idx}`)?.value  || '5102',
      csosn_cst:       document.getElementById(`inv-item-csosn-${idx}`)?.value || '102',
      origin:          document.getElementById(`inv-item-origin-${idx}`)?.value || '0',
      unit:            document.getElementById(`inv-item-unit-${idx}`)?.value  || 'UN',
      ean:             document.getElementById(`inv-item-ean-${idx}`)?.value   || 'SEM GTIN',
      sku:             prod?.sku || null,
    };
  }).filter(it => it.quantity > 0 && it.unit_price >= 0);

  if (items.length === 0) {
    showToast('Adicione pelo menos 1 item à nota fiscal.', 'warning');
    return;
  }

  const payload = {
    model:                 form.model.value,
    recipient_id:          form.recipient_id.value ? parseInt(form.recipient_id.value) : null,
    natureza_operacao:     form.natureza_operacao.value,
    finalidade:            form.finalidade.value,
    tipo_operacao:         form.tipo_operacao.value,
    destino_operacao:      form.destino_operacao.value,
    ind_presenca:          form.ind_presenca.value,
    ind_ie_dest:           form.ind_ie_dest.value,
    modalidade_frete:      form.modalidade_frete.value,
    shipping_amount:       parseFloat(form.shipping_amount.value   || 0),
    discount_amount:       parseFloat(form.discount_amount.value   || 0),
    outras_despesas:       parseFloat(form.outras_despesas.value   || 0),
    forma_pagamento:       form.forma_pagamento.value,
    informacoes_adicionais: form.informacoes_adicionais.value || '',
    informe_fisco:         form.informe_fisco.value           || '',
    items,
  };

  showToast('Transmitindo XML e obtendo protocolo SEFAZ...', 'info');
  try {
    const res = await fetch('/api/invoices/emit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = await res.json();
      showToast(`Nota Fiscal emitida e autorizada! Protocolo: ${data.protocol || data.id}`, 'success');
      closeModal();
      switchTab('invoices');
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(`Erro: ${err.detail || 'Falha na autorização da nota fiscal.'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na transmissão.', 'error');
  }
}

async function cancelInvoicePrompt(invId) {
  const reason = prompt('Informe a justificativa do cancelamento (mínimo 15 caracteres):');
  if (!reason || reason.length < 15) {
    showToast('A justificativa deve conter no mínimo 15 caracteres.', 'warning');
    return;
  }
  try {
    const res = await fetch(`/api/invoices/${invId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    if (res.ok) {
      showToast('Nota fiscal cancelada na SEFAZ com sucesso!', 'success');
      renderInvoices(document.getElementById('main-content'));
    } else {
      showToast('Erro ao cancelar nota.', 'error');
    }
  } catch (e) {
    showToast('Falha na requisição.', 'error');
  }
}

// ==============================================================================
// 10. RELATÓRIOS (DRE) & CERTIFICADO A1
// ==============================================================================
async function renderReports(container) {
  try {
    const [dreRes, compRes] = await Promise.all([
      fetch('/api/reports/dre?regime=competencia').then(r => r.json()),
      fetch('/api/company').then(r => r.json()),
    ]);

    const lines = dreRes.lines || [];
    const comp = compRes || {};

    let dreTableRows = lines.map(l => `
      <tr class="border-b border-slate-100 dark:border-slate-800 ${l.bold ? 'font-bold bg-slate-50/60 dark:bg-slate-800/40 text-slate-900 dark:text-slate-100' : 'text-slate-700 dark:text-slate-300'} text-xs">
        <td class="py-2.5 px-4">${l.label}</td>
        <td class="py-2.5 px-4 text-right ${l.color}">${formatCurrency(l.value)}</td>
        <td class="py-2.5 px-4 text-right text-slate-400">${l.av_percent !== undefined ? `${l.av_percent}%` : '-'}</td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- DRE DEMONSTRATIVO DE RESULTADO -->
        <div class="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <i data-lucide="bar-chart-4" class="w-5 h-5 text-pink-500"></i> DRE Gerencial (Regime de Competência)
              </h2>
              <p class="text-xs text-slate-400">Demonstrativo de Resultado do Exercício com Análise Vertical</p>
            </div>
            <div class="flex gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl text-xs font-semibold">
              <button onclick="toggleDreRegime('competencia')" class="px-2.5 py-1 rounded-lg bg-white dark:bg-slate-700 shadow-xs text-slate-800 dark:text-slate-100">Competência</button>
              <button onclick="toggleDreRegime('caixa')" class="px-2.5 py-1 rounded-lg text-slate-500 hover:text-slate-800">Caixa</button>
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th class="py-2.5 px-4">Estrutura DRE</th>
                  <th class="py-2.5 px-4 text-right">Valor Líquido</th>
                  <th class="py-2.5 px-4 text-right">Análise Vertical (%)</th>
                </tr>
              </thead>
              <tbody id="dre-table-body">
                ${dreTableRows}
              </tbody>
            </table>
          </div>
        </div>

        <!-- CONFIGURAÇÃO DA EMPRESA & CERTIFICADO A1 -->
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
          <h3 class="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <i data-lucide="shield-check" class="w-5 h-5 text-blue-500"></i> Certificado A1 & Empresa
          </h3>

          <form onsubmit="submitCompanyInfo(event)" class="space-y-3 text-xs">
            <div>
              <label class="block font-semibold mb-1">Razão Social</label>
              <input name="razao_social" value="${comp.razao_social || ''}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
            <div>
              <label class="block font-semibold mb-1">CNPJ da Empresa</label>
              <input name="cnpj" value="${comp.cnpj || ''}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
            <div>
              <label class="block font-semibold mb-1">Inscrição Estadual (IE)</label>
              <input name="ie" value="${comp.ie || ''}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2">
            </div>
            <div class="flex justify-end">
              <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-3 py-1.5 rounded-lg">Atualizar Empresa</button>
            </div>
          </form>

          <div class="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
            <div class="font-bold text-xs text-slate-800 dark:text-slate-100">Upload Certificado Digital (.PFX ou .P12)</div>
            <input type="file" id="cert-file" accept=".pfx,.p12" class="text-xs w-full">
            <input type="password" id="cert-pass" placeholder="Senha do Certificado A1" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
            <button onclick="uploadCertificate()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded-xl text-xs transition">
              Salvar Certificado Digital
            </button>
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro em Relatórios: ${e.message}</div>`;
  }
}

async function toggleDreRegime(regime) {
  try {
    const res = await fetch(`/api/reports/dre?regime=${regime}`);
    const data = await res.json();
    const tbody = document.getElementById('dre-table-body');
    if (!tbody) return;
    tbody.innerHTML = (data.lines || []).map(l => `
      <tr class="border-b border-slate-100 dark:border-slate-800 ${l.bold ? 'font-bold bg-slate-50/60 dark:bg-slate-800/40 text-slate-900 dark:text-slate-100' : 'text-slate-700 dark:text-slate-300'} text-xs">
        <td class="py-2.5 px-4">${l.label}</td>
        <td class="py-2.5 px-4 text-right ${l.color}">${formatCurrency(l.value)}</td>
        <td class="py-2.5 px-4 text-right text-slate-400">${l.av_percent !== undefined ? `${l.av_percent}%` : '-'}</td>
      </tr>
    `).join('');
  } catch (e) {
    showToast('Erro ao alternar regime DRE.', 'error');
  }
}

async function submitCompanyInfo(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    razao_social: form.razao_social.value,
    cnpj: form.cnpj.value,
    ie: form.ie.value,
  };
  try {
    const res = await fetch('/api/company', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('Dados da empresa atualizados!', 'success');
    } else {
      showToast('Erro ao atualizar dados.', 'error');
    }
  } catch (e) {
    showToast('Falha na requisição.', 'error');
  }
}

async function uploadCertificate() {
  const fileInput = document.getElementById('cert-file');
  const passInput = document.getElementById('cert-pass');
  if (!fileInput.files[0] || !passInput.value) {
    showToast('Selecione o arquivo do certificado e digite a senha.', 'warning');
    return;
  }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('password', passInput.value);

  showToast('Enviando e validando certificado A1...', 'info');
  try {
    const res = await fetch('/api/company/certificate', { method: 'POST', body: formData });
    if (res.ok) {
      showToast('Certificado A1 configurado com sucesso!', 'success');
      passInput.value = '';
    } else {
      showToast('Falha ao configurar certificado.', 'error');
    }
  } catch (e) {
    showToast('Erro no envio do certificado.', 'error');
  }
}

// Central de Notificações
async function refreshNotificationBadge() {
  try {
    const res = await fetch('/api/notifications?unread_only=true');
    if (res.ok) {
      const data = await res.json();
      const badge = document.getElementById('notif-badge');
      if (badge) {
        badge.innerText = data.unread_count || 0;
        badge.style.display = data.unread_count > 0 ? 'flex' : 'none';
      }
    }
  } catch (e) {}
}

async function openNotificationsModal() {
  try {
    const res = await fetch('/api/notifications');
    const data = await res.json();
    const list = data.notifications || [];

    const itemsHtml = list.length ? list.map(n => `
      <div class="p-3 rounded-xl border border-slate-200 dark:border-slate-800 ${n.is_read ? 'bg-slate-50/50 dark:bg-slate-800/30' : 'bg-blue-50/50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'} flex items-start justify-between gap-3">
        <div>
          <div class="font-bold text-xs ${n.is_read ? 'text-slate-700 dark:text-slate-300' : 'text-blue-600 dark:text-blue-400'}">${n.title}</div>
          <div class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">${n.message}</div>
          <div class="text-[9px] text-slate-400 mt-1">${formatDate(n.created_at)}</div>
        </div>
        ${!n.is_read ? `<button onclick="markNotificationRead(${n.id})" class="text-[10px] text-blue-600 hover:underline shrink-0">Marcar lida</button>` : ''}
      </div>
    `).join('') : '<div class="py-8 text-center text-slate-400 text-xs">Nenhuma notificação encontrada.</div>';

    openModal(`
      <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
        <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <i data-lucide="bell" class="w-5 h-5 text-blue-500"></i> Central de Notificações
        </h3>
        <div class="flex items-center gap-2">
          <button onclick="markAllNotificationsRead()" class="text-xs text-blue-600 hover:underline font-semibold">Marcar todas como lidas</button>
          <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
        </div>
      </div>
      <div class="mt-4 space-y-2 max-h-[60vh] overflow-y-auto">
        ${itemsHtml}
      </div>
    `);
  } catch (e) {
    showToast('Erro ao carregar notificações.', 'error');
  }
}

async function markNotificationRead(id) {
  await fetch(`/api/notifications/${id}/read`, { method: 'POST' });
  refreshNotificationBadge();
  openNotificationsModal();
}

async function markAllNotificationsRead() {
  await fetch('/api/notifications/mark-all-read', { method: 'POST' });
  refreshNotificationBadge();
  openNotificationsModal();
}

// ==============================================================================
// PEDIDOS & ORÇAMENTOS
// ==============================================================================
let quoteItems = [];
let quoteItemCounter = 0;

const QUOTE_STATUS_STYLES = {
  rascunho:  'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300',
  enviado:   'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
  aprovado:  'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300',
  rejeitado: 'bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300',
  faturado:  'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300',
  cancelado: 'bg-slate-200 dark:bg-slate-800 text-slate-400',
};

async function renderQuotes(container) {
  try {
    const [quotes, stats] = await Promise.all([
      fetch('/api/quotes').then(r => r.json()),
      fetch('/api/quotes/stats').then(r => r.json()),
    ]);

    const totalOrc = quotes.filter(q => q.type === 'orcamento').length;
    const totalPed = quotes.filter(q => q.type === 'pedido').length;
    const totalAprov = quotes.filter(q => q.status === 'aprovado').length;
    const totalValor = quotes.reduce((s, q) => s + (q.total_amount || 0), 0);

    const kpis = [
      { label: 'Orçamentos',   value: totalOrc,  icon: 'file-text',   color: 'text-yellow-500' },
      { label: 'Pedidos',      value: totalPed,  icon: 'shopping-bag', color: 'text-blue-500' },
      { label: 'Aprovados',    value: totalAprov, icon: 'check-circle', color: 'text-emerald-500' },
      { label: 'Valor Total',  value: formatCurrency(totalValor), icon: 'dollar-sign', color: 'text-purple-500' },
    ];

    const kpiHtml = kpis.map(k => `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 flex items-center gap-3 shadow-xs">
        <div class="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center shrink-0">
          <i data-lucide="${k.icon}" class="w-5 h-5 ${k.color}"></i>
        </div>
        <div>
          <div class="text-lg font-bold text-slate-900 dark:text-slate-100">${k.value}</div>
          <div class="text-xs text-slate-500">${k.label}</div>
        </div>
      </div>`).join('');

    const rows = quotes.map(q => {
      const style = QUOTE_STATUS_STYLES[q.status] || '';
      const isExpired = q.valid_until && new Date(q.valid_until) < new Date() && !['faturado','cancelado'].includes(q.status);
      return `
        <tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition text-xs">
          <td class="py-2.5 px-4 font-bold text-slate-700 dark:text-slate-200">
            <span class="text-${q.type === 'orcamento' ? 'yellow' : 'blue'}-600">${q.type === 'orcamento' ? 'ORC' : 'PED'}-${String(q.quote_number).padStart(4,'0')}</span>
          </td>
          <td class="py-2.5 px-4">${q.contact_name || '<span class="text-slate-400 italic">Sem cliente</span>'}</td>
          <td class="py-2.5 px-4">${q.created_at ? q.created_at.substring(0,10) : ''}</td>
          <td class="py-2.5 px-4 ${isExpired ? 'text-rose-500 font-semibold' : ''}">${q.valid_until || '—'} ${isExpired ? '⚠️' : ''}</td>
          <td class="py-2.5 px-4 font-semibold text-slate-800 dark:text-slate-100">${formatCurrency(q.total_amount)}</td>
          <td class="py-2.5 px-4">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${style}">${q.status_label}</span>
          </td>
          <td class="py-2.5 px-4">
            <div class="flex gap-1 flex-wrap">
              <button onclick="openQuoteModal(${q.id})" class="text-blue-600 hover:underline font-semibold px-2 py-1 rounded-lg bg-blue-50 dark:bg-blue-900/20">Editar</button>
              ${q.status === 'rascunho' ? `<button onclick="quoteAction(${q.id},'send')" class="text-slate-600 hover:underline font-semibold px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800">Enviar</button>` : ''}
              ${['rascunho','enviado'].includes(q.status) ? `<button onclick="quoteAction(${q.id},'approve')" class="text-emerald-600 hover:underline font-semibold px-2 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-900/20">Aprovar</button>` : ''}
              ${q.status === 'aprovado' ? `<button onclick="quoteAction(${q.id},'convert')" class="text-purple-600 hover:underline font-semibold px-2 py-1 rounded-lg bg-purple-50 dark:bg-purple-900/20">→ Venda</button>` : ''}
              <button onclick="openAuthed('/api/quotes/${q.id}/print'); return false;" class="text-slate-500 hover:underline font-semibold px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-800">Imprimir</button>
              ${!['faturado','cancelado'].includes(q.status) ? `<button onclick="quoteAction(${q.id},'cancel')" class="text-rose-500 hover:underline font-semibold px-2 py-1 rounded-lg bg-rose-50 dark:bg-rose-900/20">Cancelar</button>` : ''}
            </div>
          </td>
        </tr>`;
    }).join('') || '<tr><td colspan="7" class="py-8 text-center text-slate-400 italic">Nenhum orçamento/pedido encontrado.</td></tr>';

    container.innerHTML = `
      <div class="space-y-5">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <i data-lucide="file-text" class="w-5 h-5 text-yellow-500"></i> Pedidos &amp; Orçamentos
            </h2>
            <p class="text-xs text-slate-400 mt-0.5">Crie orçamentos, envie para clientes e converta em vendas</p>
          </div>
          <button onclick="openQuoteModal(null)"
            class="bg-yellow-500 hover:bg-yellow-600 text-white font-bold text-xs px-4 py-2.5 rounded-xl flex items-center gap-2 shadow-sm transition">
            <i data-lucide="plus" class="w-4 h-4"></i> Novo Orçamento / Pedido
          </button>
        </div>

        <div class="grid grid-cols-4 gap-4">${kpiHtml}</div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50 dark:bg-slate-800/50">
                  <th class="py-3 px-4">Nº</th>
                  <th class="py-3 px-4">Cliente</th>
                  <th class="py-3 px-4">Data</th>
                  <th class="py-3 px-4">Validade</th>
                  <th class="py-3 px-4">Total</th>
                  <th class="py-3 px-4">Status</th>
                  <th class="py-3 px-4">Ações</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </div>
      </div>`;
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro: ${e.message}</div>`;
  }
}

async function openQuoteModal(quoteId) {
  quoteItems = [];
  quoteItemCounter = 0;

  let q = null;
  if (quoteId) {
    try { q = await fetch(`/api/quotes/${quoteId}`).then(r => r.json()); } catch {}
  }

  const contactOpts = currentContacts.map(c =>
    `<option value="${c.id}" ${q && q.contact_id === c.id ? 'selected' : ''}>${c.name} (${c.document || '—'})</option>`
  ).join('');

  const today = new Date();
  const defaultValidity = new Date(today.setDate(today.getDate() + 30)).toISOString().split('T')[0];

  const html = `
    <div class="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
      <h3 class="font-bold text-base text-slate-900 dark:text-slate-100 flex items-center gap-2">
        <i data-lucide="file-text" class="w-5 h-5 text-yellow-500"></i>
        ${quoteId ? 'Editar' : 'Novo'} Orçamento / Pedido
      </h3>
      <button onclick="closeModal()" class="text-slate-400 hover:text-slate-600"><i data-lucide="x" class="w-5 h-5"></i></button>
    </div>

    <form id="quote-form" onsubmit="submitQuote(event, ${quoteId || 'null'})" class="mt-4 space-y-4 text-xs">

      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">Tipo *</label>
          <select name="type" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="orcamento" ${!q || q.type === 'orcamento' ? 'selected' : ''}>📋 Orçamento</option>
            <option value="pedido" ${q && q.type === 'pedido' ? 'selected' : ''}>🛒 Pedido de Venda</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Cliente</label>
          <select name="contact_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Selecionar cliente...</option>
            ${contactOpts}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Válido até *</label>
          <input name="valid_until" type="date" value="${q ? q.valid_until : defaultValidity}"
            class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block font-semibold mb-1">Condição de Pagamento</label>
          <select name="payment_terms" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            ${['À Vista','30 dias','60 dias','30/60 dias','30/60/90 dias','Boleto 30 dias','Cartão de Crédito','Cartão de Débito','PIX','Cheque'].map(t =>
              `<option ${q && q.payment_terms === t ? 'selected' : ''}>${t}</option>`
            ).join('')}
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">Vendedor</label>
          <select name="seller_id" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
            <option value="">Nenhum</option>
            ${(window.currentSellers || []).map(s =>
              `<option value="${s.id}" ${q && q.seller_id === s.id ? 'selected' : ''}>${s.name}</option>`
            ).join('')}
          </select>
        </div>
      </div>

      <!-- ITENS -->
      <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        <div class="bg-slate-100 dark:bg-slate-800 px-4 py-2 font-bold text-[11px] uppercase tracking-wider text-slate-500 flex items-center justify-between">
          <span>Itens</span>
          <button type="button" onclick="addQuoteItem()"
            class="bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-1 rounded-lg font-semibold text-[11px]">
            + Adicionar Item
          </button>
        </div>
        <div class="p-4">
          <div id="quote-items-list" class="space-y-2"></div>
          <p id="quote-items-empty" class="text-center text-slate-400 py-3 italic">Clique em "+ Adicionar Item".</p>
        </div>
      </div>

      <!-- TOTAIS -->
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="block font-semibold mb-1">Desconto Geral (R$)</label>
          <input name="discount_amount" type="number" step="0.01" min="0" value="${q ? q.discount_amount : 0}"
            oninput="updateQuoteTotals()"
            class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div>
          <label class="block font-semibold mb-1">Frete (R$)</label>
          <input name="shipping_amount" type="number" step="0.01" min="0" value="${q ? q.shipping_amount : 0}"
            oninput="updateQuoteTotals()"
            class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
        </div>
        <div class="flex flex-col justify-end">
          <div class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl p-3 text-right">
            <div class="text-xs text-slate-500">Total do Documento</div>
            <div id="quote-total-display" class="text-xl font-bold text-yellow-700 dark:text-yellow-400">R$ 0,00</div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block font-semibold mb-1">Observações (visível ao cliente)</label>
          <textarea name="notes" rows="2" placeholder="Condições de garantia, prazo de entrega, validade da proposta..."
            class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5 resize-none">${q ? q.notes : ''}</textarea>
        </div>
        <div>
          <label class="block font-semibold mb-1">Notas Internas (não aparece na impressão)</label>
          <textarea name="internal_notes" rows="2" placeholder="Margem negociável, contato preferencial..."
            class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5 resize-none">${q ? q.internal_notes : ''}</textarea>
        </div>
      </div>

      <div class="flex justify-between items-center gap-2 pt-2">
        <div>
          ${quoteId ? `<button type="button" onclick="openAuthed('/api/quotes/${quoteId}/print')" class="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 font-semibold flex items-center gap-2 text-slate-600 dark:text-slate-300 transition">
            <i data-lucide="printer" class="w-4 h-4"></i> Imprimir
          </button>` : ''}
        </div>
        <div class="flex gap-2">
          <button type="button" onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 font-semibold">Cancelar</button>
          <button type="submit" class="px-5 py-2 rounded-xl bg-yellow-500 hover:bg-yellow-600 text-white font-bold flex items-center gap-2">
            <i data-lucide="save" class="w-4 h-4"></i> Salvar
          </button>
        </div>
      </div>
    </form>`;

  openModal(html);

  // Pré-carrega itens existentes
  if (q && q.items && q.items.length > 0) {
    for (const it of q.items) addQuoteItem(it);
  } else {
    addQuoteItem();
  }
  updateQuoteTotals();
}

function _quoteItemRowHtml(idx, it) {
  const prodOpts = currentProducts.map(p =>
    `<option value="${p.id}" data-price="${p.sale_price||0}" ${it && it.product_id === p.id ? 'selected' : ''}>${p.name}</option>`
  ).join('');
  return `
    <div id="qit-${idx}" class="grid grid-cols-12 gap-2 items-end border border-slate-200 dark:border-slate-700 rounded-xl p-3 bg-slate-50/50 dark:bg-slate-800/30">
      <div class="col-span-4">
        <label class="block font-semibold mb-1 text-[10px] text-slate-500">Produto / Serviço *</label>
        <select id="qit-prod-${idx}" onchange="quoteItemFillFromProduct(${idx})"
          class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
          <option value="">Descrição livre...</option>
          ${prodOpts}
        </select>
      </div>
      <div class="col-span-3">
        <label class="block font-semibold mb-1 text-[10px] text-slate-500">Descrição (se livre)</label>
        <input id="qit-name-${idx}" type="text" value="${it ? (it.product_name || '') : ''}" placeholder="Nome do item"
          class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
      </div>
      <div class="col-span-1">
        <label class="block font-semibold mb-1 text-[10px] text-slate-500">Qtd *</label>
        <input id="qit-qty-${idx}" type="number" step="0.01" min="0.01" value="${it ? it.quantity : 1}"
          oninput="updateQuoteTotals()"
          class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
      </div>
      <div class="col-span-1">
        <label class="block font-semibold mb-1 text-[10px] text-slate-500">Un</label>
        <select id="qit-unit-${idx}" class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
          ${['UN','CX','KG','L','M','M2','PC','HR','SC'].map(u =>
            `<option ${it && it.unit === u ? 'selected' : ''}>${u}</option>`).join('')}
        </select>
      </div>
      <div class="col-span-1">
        <label class="block font-semibold mb-1 text-[10px] text-slate-500">V. Unit (R$) *</label>
        <input id="qit-price-${idx}" type="number" step="0.01" min="0" value="${it ? it.unit_price : 0}"
          oninput="updateQuoteTotals()"
          class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
      </div>
      <div class="col-span-1">
        <label class="block font-semibold mb-1 text-[10px] text-slate-500">Desc (R$)</label>
        <input id="qit-disc-${idx}" type="number" step="0.01" min="0" value="${it ? it.discount : 0}"
          oninput="updateQuoteTotals()"
          class="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2 text-xs">
      </div>
      <div class="col-span-1 flex items-center justify-end pb-0.5">
        <button type="button" onclick="removeQuoteItem(${idx})"
          class="text-rose-500 hover:text-rose-700 text-xs font-bold px-2 py-2 rounded-lg bg-rose-50 dark:bg-rose-900/20">✕</button>
      </div>
    </div>`;
}

function addQuoteItem(it) {
  const list  = document.getElementById('quote-items-list');
  const empty = document.getElementById('quote-items-empty');
  if (!list) return;
  const idx = quoteItemCounter++;
  quoteItems.push(idx);
  list.insertAdjacentHTML('beforeend', _quoteItemRowHtml(idx, it || null));
  if (empty) empty.style.display = 'none';
  if (it && it.product_id) {
    const sel = document.getElementById(`qit-prod-${idx}`);
    if (sel) sel.value = it.product_id;
  }
  updateQuoteTotals();
}

function removeQuoteItem(idx) {
  const el = document.getElementById(`qit-${idx}`);
  if (el) el.remove();
  quoteItems = quoteItems.filter(i => i !== idx);
  const list  = document.getElementById('quote-items-list');
  const empty = document.getElementById('quote-items-empty');
  if (empty && list && list.children.length === 0) empty.style.display = '';
  updateQuoteTotals();
}

function quoteItemFillFromProduct(idx) {
  const sel   = document.getElementById(`qit-prod-${idx}`);
  if (!sel || !sel.value) return;
  const prod  = currentProducts.find(p => p.id === parseInt(sel.value));
  if (!prod) return;
  const nameEl  = document.getElementById(`qit-name-${idx}`);
  const priceEl = document.getElementById(`qit-price-${idx}`);
  if (nameEl)  nameEl.value  = prod.name;
  if (priceEl) priceEl.value = prod.sale_price || 0;
  updateQuoteTotals();
}

function updateQuoteTotals() {
  let sub = 0;
  for (const idx of quoteItems) {
    const qty   = parseFloat(document.getElementById(`qit-qty-${idx}`)?.value   || 0);
    const price = parseFloat(document.getElementById(`qit-price-${idx}`)?.value || 0);
    const disc  = parseFloat(document.getElementById(`qit-disc-${idx}`)?.value  || 0);
    sub += Math.max(0, (qty * price) - disc);
  }
  const form     = document.getElementById('quote-form');
  const discGl   = parseFloat(form?.querySelector('[name=discount_amount]')?.value || 0);
  const shipping = parseFloat(form?.querySelector('[name=shipping_amount]')?.value || 0);
  const total    = Math.max(0, sub - discGl + shipping);
  const el = document.getElementById('quote-total-display');
  if (el) el.textContent = formatCurrency(total);
}

async function submitQuote(e, quoteId) {
  e.preventDefault();
  const form = document.getElementById('quote-form');

  let sub = 0;
  const items = quoteItems.map(idx => {
    const prodSel = document.getElementById(`qit-prod-${idx}`);
    const prodId  = prodSel?.value ? parseInt(prodSel.value) : null;
    const prod    = prodId ? currentProducts.find(p => p.id === prodId) : null;
    const nameEl  = document.getElementById(`qit-name-${idx}`);
    const qty   = parseFloat(document.getElementById(`qit-qty-${idx}`)?.value   || 1);
    const price = parseFloat(document.getElementById(`qit-price-${idx}`)?.value || 0);
    const disc  = parseFloat(document.getElementById(`qit-disc-${idx}`)?.value  || 0);
    const total = Math.max(0, (qty * price) - disc);
    sub += total;
    return {
      product_id:   prodId,
      product_name: nameEl?.value || prod?.name || 'Item',
      sku:          prod?.sku || '',
      quantity:     qty,
      unit:         document.getElementById(`qit-unit-${idx}`)?.value || 'UN',
      unit_price:   price,
      discount:     disc,
      total_price:  total,
    };
  });

  if (items.length === 0) { showToast('Adicione pelo menos 1 item.', 'warning'); return; }

  const fd = new FormData(form);
  const discGl   = parseFloat(fd.get('discount_amount') || 0);
  const shipping = parseFloat(fd.get('shipping_amount') || 0);

  const payload = {
    type:            fd.get('type'),
    contact_id:      fd.get('contact_id') ? parseInt(fd.get('contact_id')) : null,
    seller_id:       fd.get('seller_id')  ? parseInt(fd.get('seller_id'))  : null,
    valid_until:     fd.get('valid_until'),
    payment_terms:   fd.get('payment_terms'),
    subtotal:        sub,
    discount_amount: discGl,
    shipping_amount: shipping,
    total_amount:    Math.max(0, sub - discGl + shipping),
    notes:           fd.get('notes') || '',
    internal_notes:  fd.get('internal_notes') || '',
    items,
  };

  try {
    const url    = quoteId ? `/api/quotes/${quoteId}` : '/api/quotes';
    const method = quoteId ? 'PUT' : 'POST';
    const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (res.ok) {
      const d = await res.json();
      showToast(d.message || 'Salvo com sucesso!', 'success');
      closeModal();
      switchTab('quotes');
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(`Erro: ${err.detail || 'Falha ao salvar.'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na requisição.', 'error');
  }
}

async function quoteAction(quoteId, action) {
  const labels = { send: 'Enviar', approve: 'Aprovar', reject: 'Rejeitar', convert: 'Converter em Venda', cancel: 'Cancelar' };
  const confirm_actions = ['cancel', 'reject', 'convert'];
  if (confirm_actions.includes(action)) {
    if (!confirm(`Confirma: ${labels[action]} este orçamento?`)) return;
  }
  try {
    const res = await fetch(`/api/quotes/${quoteId}/${action}`, { method: 'POST' });
    const d   = await res.json();
    if (res.ok) {
      showToast(d.message || 'Operação realizada!', 'success');
      switchTab('quotes');
    } else {
      showToast(`Erro: ${d.detail || 'Falha.'}`, 'error');
    }
  } catch {
    showToast('Falha na requisição.', 'error');
  }
}

// ==============================================================================
// CONFIGURAÇÕES DA EMPRESA (EMITENTE FISCAL)
// ==============================================================================
async function renderSettings(container) {
  try {
    const comp = await fetch('/api/company').then(r => r.json());
    const cert = await fetch('/api/company/certificate/status').then(r => r.json());

    const field = (name, label, value, type = 'text', placeholder = '') => `
      <div>
        <label class="block font-semibold mb-1 text-slate-600 dark:text-slate-400">${label}</label>
        <input name="${name}" type="${type}" value="${value ?? ''}" placeholder="${placeholder}"
          class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none">
      </div>`;

    const select = (name, label, options, selected) => `
      <div>
        <label class="block font-semibold mb-1 text-slate-600 dark:text-slate-400">${label}</label>
        <select name="${name}" class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5 text-xs focus:ring-2 focus:ring-blue-500 outline-none">
          ${options.map(([v, l]) => `<option value="${v}" ${String(selected) === String(v) ? 'selected' : ''}>${l}</option>`).join('')}
        </select>
      </div>`;

    const section = (title, icon, color, content) => `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xs">
        <div class="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-slate-800">
          <i data-lucide="${icon}" class="w-4 h-4 ${color}"></i>
          <h3 class="font-bold text-sm text-slate-800 dark:text-slate-100">${title}</h3>
        </div>
        <div class="p-5">${content}</div>
      </div>`;

    const certBadge = cert.installed
      ? `<div class="flex items-center gap-2 text-xs ${cert.is_expired ? 'text-rose-600' : 'text-emerald-600'} font-semibold">
           <i data-lucide="${cert.is_expired ? 'shield-x' : 'shield-check'}" class="w-4 h-4"></i>
           ${cert.titular} — válido até ${cert.valid_until ? cert.valid_until.substring(0,10) : '?'}
           ${cert.days_remaining !== null ? `(${cert.days_remaining} dias)` : ''}
         </div>`
      : `<div class="flex items-center gap-2 text-xs text-amber-600 font-semibold">
           <i data-lucide="shield-alert" class="w-4 h-4"></i> Nenhum certificado A1 instalado
         </div>`;

    container.innerHTML = `
      <div class="space-y-5 max-w-4xl">

        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <i data-lucide="building-2" class="w-5 h-5 text-orange-500"></i> Configurações da Empresa
            </h2>
            <p class="text-xs text-slate-400 mt-0.5">Dados do emitente utilizados nas Notas Fiscais (NF-e, NFC-e, NFS-e)</p>
          </div>
          <button onclick="submitCompanySettings(event)"
            class="bg-orange-500 hover:bg-orange-600 text-white font-bold text-xs px-5 py-2.5 rounded-xl flex items-center gap-2 shadow-sm transition">
            <i data-lucide="save" class="w-4 h-4"></i> Salvar Todas as Configurações
          </button>
        </div>

        <form id="company-settings-form" onsubmit="submitCompanySettings(event)" class="space-y-5">

          ${section('Identificação da Empresa', 'building-2', 'text-orange-500', `
            <div class="grid grid-cols-2 gap-4">
              ${field('razao_social', 'Razão Social *', comp.razao_social, 'text', 'Ex: Empresa LTDA')}
              ${field('nome_fantasia', 'Nome Fantasia *', comp.nome_fantasia, 'text', 'Ex: Empresa')}
            </div>
            <div class="grid grid-cols-3 gap-4 mt-3">
              ${field('cnpj', 'CNPJ *', comp.cnpj, 'text', '00.000.000/0000-00')}
              ${field('inscricao_estadual', 'Inscrição Estadual (IE)', comp.inscricao_estadual, 'text', 'ISENTO ou número')}
              ${field('inscricao_municipal', 'Inscrição Municipal (IM)', comp.inscricao_municipal, 'text', 'Para NFS-e')}
            </div>
            <div class="grid grid-cols-2 gap-4 mt-3">
              ${field('cnae_principal', 'CNAE Principal', comp.cnae_principal, 'text', '6201-5/01')}
              ${select('regime_tributario', 'Regime Tributário *', [
                ['simples_nacional', 'Simples Nacional'],
                ['mei', 'MEI — Microempreendedor Individual'],
                ['lucro_presumido', 'Lucro Presumido'],
                ['lucro_real', 'Lucro Real'],
              ], comp.regime_tributario)}
            </div>
            <div class="grid grid-cols-1 gap-4 mt-3">
              ${field('aliquota_simples', 'Alíquota Simples Nacional (%)', comp.aliquota_simples, 'number', '6.0')}
            </div>
          `)}

          ${section('Endereço do Emitente', 'map-pin', 'text-blue-500', `
            <div class="grid grid-cols-4 gap-4">
              ${field('cep', 'CEP *', comp.cep, 'text', '00000-000')}
              ${field('logradouro', 'Logradouro (Rua / Av.) *', comp.logradouro, 'text', 'Av. Principal')}
              ${field('numero', 'Número *', comp.numero, 'text', 'S/N')}
              ${field('complemento', 'Complemento', comp.complemento, 'text', 'Sala 01')}
            </div>
            <div class="grid grid-cols-4 gap-4 mt-3">
              ${field('bairro', 'Bairro *', comp.bairro, 'text', 'Centro')}
              ${field('cidade', 'Município *', comp.cidade, 'text', 'Cáceres')}
              ${select('uf', 'UF *', [
                ['AC','AC'],['AL','AL'],['AP','AP'],['AM','AM'],['BA','BA'],['CE','CE'],
                ['DF','DF'],['ES','ES'],['GO','GO'],['MA','MA'],['MT','MT'],['MS','MS'],
                ['MG','MG'],['PA','PA'],['PB','PB'],['PR','PR'],['PE','PE'],['PI','PI'],
                ['RJ','RJ'],['RN','RN'],['RS','RS'],['RO','RO'],['RR','RR'],['SC','SC'],
                ['SP','SP'],['SE','SE'],['TO','TO'],
              ], comp.uf)}
              ${field('codigo_ibge_municipio', 'Código IBGE Município *', comp.codigo_ibge_municipio, 'text', '5102504')}
            </div>
          `)}

          ${section('Contato', 'phone', 'text-green-500', `
            <div class="grid grid-cols-3 gap-4">
              ${field('telefone', 'Telefone / WhatsApp', comp.telefone, 'text', '(65) 99999-0000')}
              ${field('email', 'E-mail da Empresa', comp.email, 'email', 'contato@empresa.com.br')}
              ${field('chave_pix', 'Chave PIX', comp.chave_pix, 'text', 'CNPJ, CPF, e-mail ou telefone')}
            </div>
          `)}

          ${section('Configurações Fiscais SEFAZ', 'server', 'text-purple-500', `
            <div class="grid grid-cols-3 gap-4">
              ${select('ambiente_fiscal', 'Ambiente SEFAZ *', [
                ['homologacao', '🧪 Homologação (Testes)'],
                ['producao', '🟢 Produção (Notas Reais)'],
              ], comp.ambiente_fiscal)}
              ${select('motor_fiscal', 'Motor / Provedor Fiscal', [
                ['sefaz_direto', 'SEFAZ Direto (A1 Local)'],
                ['nuvem_fiscal', 'Nuvem Fiscal'],
                ['focus_nfe', 'Focus NFe'],
                ['plug_notas', 'PlugNotas'],
              ], comp.motor_fiscal)}
              ${field('api_fiscal_token', 'Token da API Fiscal', comp.api_fiscal_token, 'text', 'Token do provedor (se aplicável)')}
            </div>
            <div class="grid grid-cols-2 gap-4 mt-3">
              ${field('codigo_ibge_uf', 'Código IBGE da UF', comp.codigo_ibge_uf, 'text', '51')}
              <div>
                <label class="block font-semibold mb-1 text-slate-600 dark:text-slate-400">Ambiente atual</label>
                <div class="flex items-center gap-2 h-9 px-3 rounded-xl border ${comp.ambiente_fiscal === 'producao' ? 'border-emerald-300 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400' : 'border-amber-300 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400'} text-xs font-bold">
                  <span class="w-2 h-2 rounded-full ${comp.ambiente_fiscal === 'producao' ? 'bg-emerald-500' : 'bg-amber-500'}"></span>
                  ${comp.ambiente_fiscal === 'producao' ? 'PRODUÇÃO — Notas com validade jurídica' : 'HOMOLOGAÇÃO — Apenas para testes'}
                </div>
              </div>
            </div>
          `)}

          ${section('Séries e Numeração Fiscal', 'hash', 'text-indigo-500', `
            <div class="grid grid-cols-3 gap-4">
              <div class="border border-slate-200 dark:border-slate-700 rounded-xl p-3 space-y-2">
                <div class="text-[11px] font-bold uppercase text-slate-500 tracking-wider">NF-e (Mod. 55)</div>
                ${field('serie_nfe', 'Série', comp.serie_nfe, 'number', '1')}
                ${field('proximo_numero_nfe', 'Próximo Número', comp.proximo_numero_nfe, 'number', '101')}
              </div>
              <div class="border border-slate-200 dark:border-slate-700 rounded-xl p-3 space-y-2">
                <div class="text-[11px] font-bold uppercase text-slate-500 tracking-wider">NFC-e (Mod. 65)</div>
                ${field('serie_nfce', 'Série', comp.serie_nfce, 'number', '1')}
                ${field('proximo_numero_nfce', 'Próximo Número', comp.proximo_numero_nfce, 'number', '501')}
              </div>
              <div class="border border-slate-200 dark:border-slate-700 rounded-xl p-3 space-y-2">
                <div class="text-[11px] font-bold uppercase text-slate-500 tracking-wider">NFS-e (Serviços)</div>
                ${field('serie_nfse', 'Série', comp.serie_nfse, 'number', '1')}
                ${field('proximo_numero_nfse', 'Próximo Número', comp.proximo_numero_nfse, 'number', '201')}
              </div>
            </div>
          `)}

          ${section('NFC-e — CSC (Código de Segurança do Contribuinte)', 'key-round', 'text-rose-500', `
            <p class="text-xs text-slate-500 mb-3">Necessário para emissão de NFC-e (Modelo 65). Obtido no portal SEFAZ do seu estado.</p>
            <div class="grid grid-cols-2 gap-4">
              ${field('csc_id', 'CSC ID (Identificador)', comp.csc_id, 'text', '000001')}
              ${field('csc_token', 'CSC Token', comp.csc_token, 'text', 'Token gerado pelo SEFAZ')}
            </div>
          `)}

        </form>

        ${section('Certificado Digital A1 (.PFX / .P12)', 'shield-check', 'text-blue-500', `
          <div class="space-y-4">
            <div>${certBadge}</div>
            <form onsubmit="submitCertificate(event)" class="space-y-3" enctype="multipart/form-data">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block font-semibold mb-1 text-slate-600 dark:text-slate-400 text-xs">Arquivo .PFX ou .P12</label>
                  <input type="file" name="file" accept=".pfx,.p12"
                    class="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5 file:mr-2 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white file:px-3 file:py-1 file:text-xs cursor-pointer">
                </div>
                <div>
                  <label class="block font-semibold mb-1 text-slate-600 dark:text-slate-400 text-xs">Senha do Certificado</label>
                  <input type="password" name="password" placeholder="Senha do arquivo .PFX"
                    class="w-full text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-2.5">
                </div>
              </div>
              <button type="submit"
                class="bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs px-5 py-2.5 rounded-xl flex items-center gap-2 transition">
                <i data-lucide="upload" class="w-4 h-4"></i> Instalar Certificado no Cofre Seguro
              </button>
            </form>
          </div>
        `)}

      </div>
    `;
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    container.innerHTML = `<div class="p-6 text-rose-500">Erro ao carregar configurações: ${e.message}</div>`;
  }
}

async function submitCompanySettings(e) {
  e.preventDefault();
  const form = document.getElementById('company-settings-form');
  if (!form) return;
  const fd = new FormData(form);
  const data = {};
  for (const [k, v] of fd.entries()) {
    if (['serie_nfe','proximo_numero_nfe','serie_nfce','proximo_numero_nfce','serie_nfse','proximo_numero_nfse'].includes(k)) {
      data[k] = parseInt(v) || 0;
    } else if (k === 'aliquota_simples') {
      data[k] = parseFloat(v) || 0;
    } else {
      data[k] = v;
    }
  }
  try {
    const res = await fetch('/api/company', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      showToast('Configurações da empresa salvas com sucesso!', 'success');
      const sidebarName = document.getElementById('sidebar-company-name');
      if (sidebarName && data.razao_social) sidebarName.textContent = data.nome_fantasia || data.razao_social;
      switchTab('settings');
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(`Erro: ${err.detail || 'Falha ao salvar.'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na requisição.', 'error');
  }
}

async function submitCertificate(e) {
  e.preventDefault();
  const form = e.target;
  const fd = new FormData(form);
  showToast('Instalando certificado no cofre seguro...', 'info');
  try {
    const res = await fetch('/api/company/certificate', { method: 'POST', body: fd });
    if (res.ok) {
      const d = await res.json();
      showToast(`Certificado instalado! Titular: ${d.titular} | Validade: ${d.validade}`, 'success');
      switchTab('settings');
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(`Erro: ${err.detail || 'Falha ao instalar certificado.'}`, 'error');
    }
  } catch (err) {
    showToast('Falha na requisição.', 'error');
  }
}

// Initial Boot
document.addEventListener('DOMContentLoaded', () => {
  const theme = localStorage.getItem('cortex_theme');
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  }
  switchTab('dashboard');
  refreshNotificationBadge();
  setInterval(refreshNotificationBadge, 30000);
});
