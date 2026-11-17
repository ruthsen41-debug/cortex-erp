// Escrita Fiscal — Acumuladores, Livros, Retenções, Apuração Mensal & Guias
let _fbTab = 'livros';
let _fbComp = new Date().toISOString().slice(0, 7);
let _fbAccs = [];

function _fbBRL(v) {
  return parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function _fbEsc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function renderFiscalBooks(container) {
  const el = container || document.getElementById('main-content');
  _fbAccs = await apiFetch('/api/fiscal-books/accumulators').catch(() => []);

  const tabs = [
    ['livros', 'Livros Fiscais'],
    ['escriturar', 'Escriturar Documento'],
    ['apuracao', 'Apuração & Guias'],
    ['cfop', 'Resumo por CFOP'],
    ['acumuladores', 'Acumuladores'],
  ];

  el.innerHTML = `
    <div class="space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-xl font-bold text-slate-800 dark:text-slate-100">Escrita Fiscal &amp; Apuração</h2>
          <p class="text-xs text-slate-400">Livros de Entradas, Saídas e Serviços, motor de acumuladores, retenções na fonte e guias (DARF / DAE / DAM).</p>
        </div>
        <div class="flex items-center gap-2">
          <input type="month" id="fb-comp" value="${_fbComp}" onchange="_fbComp=this.value;fbLoadTab()"
            class="text-xs border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 rounded-xl px-3 py-2">
          <button onclick="fbSyncErp()" class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-2 rounded-xl">
            Sincronizar ERP
          </button>
        </div>
      </div>

      <div class="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        ${tabs.map(([k, lbl]) => `
          <button onclick="fbSwitchTab('${k}')" id="fb-tab-${k}"
            class="px-3 py-1.5 rounded-xl text-xs font-semibold ${_fbTab === k ? 'bg-violet-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">
            ${lbl}
          </button>`).join('')}
      </div>

      <div id="fb-body"></div>
    </div>`;

  await fbLoadTab();
}

async function fbSwitchTab(tab) {
  _fbTab = tab;
  await renderFiscalBooks(document.getElementById('main-content'));
}

async function fbSyncErp() {
  try {
    const res = await apiFetch(`/api/fiscal-books/sync?competencia=${_fbComp}`, { method: 'POST' });
    showToast(`Sincronizado: ${res.saidas_escrituradas} saída(s) e ${res.entradas_escrituradas} entrada(s).`, 'success');
    await fbLoadTab();
  } catch (e) { showToast('Erro ao sincronizar: ' + e.message, 'error'); }
}

async function fbLoadTab() {
  const body = document.getElementById('fb-body');
  if (!body) return;
  if (_fbTab === 'livros') return fbRenderLivros(body);
  if (_fbTab === 'escriturar') return fbRenderEscriturar(body);
  if (_fbTab === 'apuracao') return fbRenderApuracao(body);
  if (_fbTab === 'cfop') return fbRenderCfop(body);
  if (_fbTab === 'acumuladores') return fbRenderAcumuladores(body);
}

async function fbRenderLivros(body) {
  const data = await apiFetch(`/api/fiscal-books/books?competencia=${_fbComp}`).catch(() => null);
  if (!data) { body.innerHTML = '<div class="text-xs text-rose-500">Erro ao carregar livros.</div>'; return; }

  const sec = (titulo, b, extraRet) => `
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4">
      <div class="flex flex-wrap justify-between items-center mb-3 gap-2">
        <h3 class="font-bold text-sm text-slate-800 dark:text-slate-100">${titulo} (${b.count})</h3>
        <div class="text-xs text-slate-500 flex flex-wrap gap-3">
          <span>Contábil: <strong>${_fbBRL(b.totais.valor_contabil)}</strong></span>
          <span>ICMS: <strong>${_fbBRL(b.totais.valor_icms)}</strong></span>
          <span>PIS/COFINS: <strong>${_fbBRL(b.totais.valor_pis + b.totais.valor_cofins)}</strong></span>
          ${extraRet ? `<span>Retenções (IR/CSRF/INSS/ISS): <strong>${_fbBRL(b.totais.irrf_retido + b.totais.csrf_retido + b.totais.inss_retido + b.totais.iss_retido)}</strong></span>` : ''}
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead><tr class="text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="py-2 text-left">Doc / Série</th><th class="py-2 text-left">Emissão</th>
            <th class="py-2 text-left">Participante</th><th class="py-2 text-left">CFOP / Acum.</th>
            <th class="py-2 text-right">Valor Contábil</th><th class="py-2 text-right">ICMS</th>
            <th class="py-2 text-right">PIS/COF</th><th class="py-2 text-right">ISS / Ret.</th>
            <th class="py-2 text-right">Ação</th>
          </tr></thead>
          <tbody>
            ${b.entries.length ? b.entries.map(r => `
              <tr class="border-b border-slate-100 dark:border-slate-800">
                <td class="py-2 font-mono">${_fbEsc(r.modelo)} #${_fbEsc(r.numero)}/${_fbEsc(r.serie)}</td>
                <td class="py-2">${_fbEsc(r.data_emissao)}</td>
                <td class="py-2">${_fbEsc(r.participante_nome || '-')}</td>
                <td class="py-2 font-mono">${_fbEsc(r.cfop)} ${r.accumulator_code ? `[${_fbEsc(r.accumulator_code)}]` : ''}</td>
                <td class="py-2 text-right font-semibold">${_fbBRL(r.valor_contabil)}</td>
                <td class="py-2 text-right">${_fbBRL(r.valor_icms)}</td>
                <td class="py-2 text-right">${_fbBRL((r.valor_pis || 0) + (r.valor_cofins || 0))}</td>
                <td class="py-2 text-right">${_fbBRL((r.valor_iss || 0) + (r.irrf_retido || 0) + (r.csrf_retido || 0) + (r.inss_retido || 0))}</td>
                <td class="py-2 text-right"><button onclick="fbDeleteEntry(${r.id})" class="text-rose-500 hover:underline">Excluir</button></td>
              </tr>`).join('') : '<tr><td colspan="9" class="py-4 text-center text-slate-400">Sem lançamentos nesta competência.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>`;

  body.innerHTML = `<div class="space-y-4">
    ${sec('Livro Registro de Entradas', data.livro_entradas, false)}
    ${sec('Livro Registro de Saídas', data.livro_saidas, false)}
    ${sec('Livro de Serviços Prestados', data.livro_servicos_prestados, true)}
    ${sec('Livro de Serviços Tomados (com Retenções)', data.livro_servicos_tomados, true)}
  </div>`;
}

async function fbDeleteEntry(id) {
  if (!confirm('Excluir este lançamento fiscal?')) return;
  await apiFetch(`/api/fiscal-books/entries/${id}`, { method: 'DELETE' });
  await fbLoadTab();
}

function fbRenderEscriturar(body) {
  const opts = _fbAccs.map(a => `<option value="${a.id}">${_fbEsc(a.codigo)} — ${_fbEsc(a.descricao)} (${_fbEsc(a.tipo)})</option>`).join('');
  const dtDef = `${_fbComp}-15`;
  body.innerHTML = `
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 max-w-4xl">
      <h3 class="font-bold text-sm mb-4">Escriturar Nota / Serviço via Acumulador Fiscal</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        <div class="md:col-span-2">
          <label class="block text-slate-500 mb-1">Acumulador Fiscal</label>
          <select id="fb-acc" class="w-full border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">${opts}</select>
        </div>
        <div>
          <label class="block text-slate-500 mb-1">Número do Documento</label>
          <input id="fb-num" type="text" placeholder="001234" class="w-full border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">
        </div>
        <div>
          <label class="block text-slate-500 mb-1">Participante (Cliente / Fornecedor)</label>
          <input id="fb-part" type="text" placeholder="Razão Social" class="w-full border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">
        </div>
        <div>
          <label class="block text-slate-500 mb-1">CPF / CNPJ</label>
          <input id="fb-doc" type="text" placeholder="00.000.000/0001-00" class="w-full border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">
        </div>
        <div>
          <label class="block text-slate-500 mb-1">Valor Contábil (R$)</label>
          <input id="fb-val" type="number" step="0.01" placeholder="1000.00" class="w-full border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">
        </div>
        <div>
          <label class="block text-slate-500 mb-1">Data Emissão</label>
          <input id="fb-dt" type="date" value="${dtDef}" class="w-full border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">
        </div>
        <div>
          <label class="block text-slate-500 mb-1">UF Origem / Destino</label>
          <div class="flex gap-2">
            <input id="fb-ufo" type="text" value="MT" maxlength="2" class="w-1/2 border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">
            <input id="fb-ufd" type="text" value="MT" maxlength="2" class="w-1/2 border rounded-xl px-3 py-2 dark:bg-slate-800 dark:border-slate-700">
          </div>
        </div>
        <div class="flex items-end gap-3">
          <label class="flex items-center gap-1.5"><input id="fb-fin" type="checkbox" checked> Gerar Financeiro</label>
          <label class="flex items-center gap-1.5"><input id="fb-con" type="checkbox" checked> Contabilizar</label>
        </div>
      </div>
      <div class="mt-4">
        <button onclick="fbSubmitEntry()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-5 py-2.5 rounded-xl">
          Escriturar Documento
        </button>
      </div>
    </div>`;
}

async function fbSubmitEntry() {
  const payload = {
    accumulator_id: parseInt(document.getElementById('fb-acc').value, 10),
    numero: document.getElementById('fb-num').value.trim(),
    participante_nome: document.getElementById('fb-part').value.trim(),
    participante_doc: document.getElementById('fb-doc').value.trim(),
    valor_contabil: parseFloat(document.getElementById('fb-val').value || '0'),
    data_emissao: document.getElementById('fb-dt').value,
    competencia: _fbComp,
    uf_origem: document.getElementById('fb-ufo').value.toUpperCase(),
    uf_destino: document.getElementById('fb-ufd').value.toUpperCase(),
    gerar_financeiro: document.getElementById('fb-fin').checked,
    gerar_contabil: document.getElementById('fb-con').checked,
  };
  try {
    await apiFetch('/api/fiscal-books/entries', { method: 'POST', body: JSON.stringify(payload) });
    showToast('Documento escriturado com sucesso!', 'success');
    await fbSwitchTab('livros');
  } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function fbRenderApuracao(body) {
  const rows = await apiFetch(`/api/fiscal-books/apurations?competencia=${_fbComp}`).catch(() => []);
  body.innerHTML = `
    <div class="space-y-4">
      <div class="flex justify-between items-center">
        <span class="text-xs text-slate-500">Apuração oficial da competência <strong>${_fbComp}</strong></span>
        <button onclick="fbRunApuracao()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">
          Processar Apuração Mensal
        </button>
      </div>
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-x-auto">
        <table class="w-full text-xs">
          <thead><tr class="text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-4 py-2.5 text-left">Imposto</th><th class="px-4 py-2.5 text-left">Cód. Receita</th>
            <th class="px-4 py-2.5 text-right">Débitos</th><th class="px-4 py-2.5 text-right">Créditos</th>
            <th class="px-4 py-2.5 text-right">Saldo Ant.</th><th class="px-4 py-2.5 text-right">A Recolher</th>
            <th class="px-4 py-2.5 text-right">Transportar</th><th class="px-4 py-2.5 text-left">Vencimento</th>
            <th class="px-4 py-2.5 text-right">Ações</th>
          </tr></thead>
          <tbody>
            ${rows.length ? rows.map(a => `
              <tr class="border-b border-slate-100 dark:border-slate-800">
                <td class="px-4 py-2 font-bold">${_fbEsc(a.imposto)}</td>
                <td class="px-4 py-2 font-mono">${_fbEsc(a.codigo_receita)}</td>
                <td class="px-4 py-2 text-right">${_fbBRL(a.debitos)}</td>
                <td class="px-4 py-2 text-right text-emerald-600">${_fbBRL(a.creditos)}</td>
                <td class="px-4 py-2 text-right">${_fbBRL(a.saldo_credor_anterior)}</td>
                <td class="px-4 py-2 text-right font-bold text-rose-600">${_fbBRL(a.valor_a_recolher)}</td>
                <td class="px-4 py-2 text-right text-blue-600">${_fbBRL(a.saldo_credor_transportar)}</td>
                <td class="px-4 py-2">${_fbEsc(a.vencimento)}</td>
                <td class="px-4 py-2 text-right whitespace-nowrap">
                  <button onclick="fbOpenGuia(${a.id})" class="text-indigo-500 hover:underline mr-2">Guia</button>
                  ${a.valor_a_recolher > 0 ? `<button onclick="fbGerarFin(${a.id})" class="text-emerald-600 hover:underline">Lançar Pagar</button>` : ''}
                </td>
              </tr>`).join('') : '<tr><td colspan="9" class="px-4 py-6 text-center text-slate-400">Clique em "Processar Apuração Mensal" para calcular.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>`;
}

async function fbRunApuracao() {
  await apiFetch(`/api/fiscal-books/apurations/run?competencia=${_fbComp}`, { method: 'POST' });
  showToast('Apuração concluída!', 'success');
  await fbLoadTab();
}

async function fbOpenGuia(id) {
  const r = await fetch(`/api/fiscal-books/apurations/${id}/guia`, { headers: authHeaders() });
  const html = await r.text();
  const w = window.open('', '_blank');
  if (w) { w.document.write(html); w.document.close(); }
}

async function fbGerarFin(id) {
  try {
    await apiFetch(`/api/fiscal-books/apurations/${id}/gerar-financeiro`, { method: 'POST' });
    showToast('Título gerado no Contas a Pagar!', 'success');
    await fbLoadTab();
  } catch (e) { showToast('Erro: ' + e.message, 'error'); }
}

async function fbRenderCfop(body) {
  const data = await apiFetch(`/api/fiscal-books/books?competencia=${_fbComp}`).catch(() => ({ resumo_cfop: [] }));
  const rows = data.resumo_cfop || [];
  body.innerHTML = `
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-x-auto">
      <table class="w-full text-xs">
        <thead><tr class="text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
          <th class="px-4 py-2.5 text-left">CFOP</th><th class="px-4 py-2.5 text-left">Operação</th>
          <th class="px-4 py-2.5 text-right">Docs</th><th class="px-4 py-2.5 text-right">Valor Contábil</th>
          <th class="px-4 py-2.5 text-right">ICMS</th><th class="px-4 py-2.5 text-right">IPI</th>
          <th class="px-4 py-2.5 text-right">PIS</th><th class="px-4 py-2.5 text-right">COFINS</th>
          <th class="px-4 py-2.5 text-right">ISS</th>
        </tr></thead>
        <tbody>
          ${rows.length ? rows.map(r => `
            <tr class="border-b border-slate-100 dark:border-slate-800">
              <td class="px-4 py-2 font-mono font-bold">${_fbEsc(r.cfop)}</td>
              <td class="px-4 py-2">${_fbEsc(r.tipo)}</td>
              <td class="px-4 py-2 text-right">${r.qtd}</td>
              <td class="px-4 py-2 text-right font-semibold">${_fbBRL(r.valor_contabil)}</td>
              <td class="px-4 py-2 text-right">${_fbBRL(r.valor_icms)}</td>
              <td class="px-4 py-2 text-right">${_fbBRL(r.valor_ipi)}</td>
              <td class="px-4 py-2 text-right">${_fbBRL(r.valor_pis)}</td>
              <td class="px-4 py-2 text-right">${_fbBRL(r.valor_cofins)}</td>
              <td class="px-4 py-2 text-right">${_fbBRL(r.valor_iss)}</td>
            </tr>`).join('') : '<tr><td colspan="9" class="px-4 py-6 text-center text-slate-400">Sem movimentação na competência.</td></tr>'}
        </tbody>
      </table>
    </div>`;
}

function fbRenderAcumuladores(body) {
  body.innerHTML = `
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-x-auto">
      <table class="w-full text-xs">
        <thead><tr class="text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
          <th class="px-4 py-2.5 text-left">Código</th><th class="px-4 py-2.5 text-left">Descrição</th>
          <th class="px-4 py-2.5 text-left">Tipo</th><th class="px-4 py-2.5 text-left">CFOP</th>
          <th class="px-4 py-2.5 text-right">ICMS%</th><th class="px-4 py-2.5 text-right">PIS/COF%</th>
          <th class="px-4 py-2.5 text-right">Ret. (IR/CSRF/INSS)</th>
          <th class="px-4 py-2.5 text-left">Contas D / C</th>
        </tr></thead>
        <tbody>
          ${_fbAccs.map(a => `
            <tr class="border-b border-slate-100 dark:border-slate-800">
              <td class="px-4 py-2 font-mono font-bold">${_fbEsc(a.codigo)}</td>
              <td class="px-4 py-2">${_fbEsc(a.descricao)}</td>
              <td class="px-4 py-2">${_fbEsc(a.tipo)}</td>
              <td class="px-4 py-2 font-mono">${_fbEsc(a.cfop_padrao)}</td>
              <td class="px-4 py-2 text-right">${a.aliquota_icms}%${a.gera_credito_icms ? ' (Créd)' : ''}</td>
              <td class="px-4 py-2 text-right">${a.aliquota_pis}% / ${a.aliquota_cofins}%</td>
              <td class="px-4 py-2 text-right">${a.retencao_irrf_pct}% / ${a.retencao_csrf_pct}% / ${a.retencao_inss_pct}%</td>
              <td class="px-4 py-2 font-mono">${_fbEsc(a.conta_contabil_debito)} / ${_fbEsc(a.conta_contabil_credito)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}
