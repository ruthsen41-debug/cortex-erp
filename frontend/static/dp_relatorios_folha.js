// ============================================================
// DEPARTAMENTO PESSOAL — Relatórios da folha (imprimir em HTML ou baixar CSV)
// Usa os helpers de dp.js: authHeaders, card2, inputCls, labelCls, _dpEsc, dpEmployees, openAuthDoc.
// ============================================================

async function renderRelatoriosFolha(el) {
  let runs = [];
  try { runs = await fetch('/api/dp/payroll', { headers: authHeaders() }).then(r => r.json()); } catch { runs = []; }
  const optRuns = (Array.isArray(runs) ? runs : []).map(r =>
    `<option value="${r.id}">${_dpEsc(r.competence)} · ${_dpEsc(r.tipo || 'mensal')} (${r.employee_count || 0} func.)</option>`).join('')
    || '<option value="">Nenhuma folha processada</option>';
  const optEmps = dpEmployees.map(e => `<option value="${e.id}">${_dpEsc(e.name)}${e.active ? '' : ' (desligado)'}</option>`).join('');
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = hoje.toISOString().slice(0, 7);
  const botoes = nome => `<div class="flex gap-2 mt-3">
      <button onclick="_dprfAbrir('${nome}', 'html')" class="text-xs px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white flex items-center gap-1.5">
        <i data-lucide="printer" class="w-3.5 h-3.5"></i> Imprimir</button>
      <button onclick="_dprfAbrir('${nome}', 'csv')" class="text-xs px-3 py-1.5 rounded-lg border border-emerald-200 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 flex items-center gap-1.5">
        <i data-lucide="sheet" class="w-3.5 h-3.5"></i> Planilha (CSV)</button></div>`;
  const cartao = (icone, titulo, desc, campos, nome) => card2(`<div class="p-5">
      <div class="flex items-center gap-2 mb-1"><i data-lucide="${icone}" class="w-4 h-4 text-violet-600"></i>
        <h3 class="font-bold text-sm text-slate-800 dark:text-slate-100">${titulo}</h3></div>
      <p class="text-[11px] text-slate-400 mb-3">${desc}</p>${campos}${botoes(nome)}</div>`);
  el.innerHTML = `
    <div class="mb-6"><h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">Relatórios da folha</h2>
      <p class="text-xs text-slate-400">Para imprimir ou salvar em PDF, ou baixar em planilha (abre no Excel).</p></div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      ${cartao('banknote', 'Relação de líquidos', 'Valor líquido de cada funcionário com banco, agência e conta, para conferir o pagamento.',
        `${labelCls('Folha')}<select id="rf-liq-run" class="${inputCls()}">${optRuns}</select>`, 'liquidos')}
      ${cartao('file-spreadsheet', 'Ficha financeira anual', 'Todas as rubricas do funcionário mês a mês: folhas, férias, 13º e rescisão.',
        `<div class="grid grid-cols-3 gap-3"><div class="col-span-2">${labelCls('Funcionário')}<select id="rf-ff-emp" class="${inputCls()}">${optEmps}</select></div>
         <div>${labelCls('Ano')}<input id="rf-ff-ano" type="number" value="${ano}" class="${inputCls()}"></div></div>`, 'ficha-financeira')}
      ${cartao('list-ordered', 'Lançamentos por rubrica', 'Quem recebeu ou teve desconto em cada rubrica na competência, com subtotais.',
        `<div class="grid grid-cols-2 gap-3"><div>${labelCls('Competência')}<input id="rf-lc-comp" type="month" value="${mes}" class="${inputCls()}"></div>
         <div>${labelCls('Rubrica (opcional)')}<input id="rf-lc-cod" placeholder="ex.: 0002" class="${inputCls()}"></div></div>`, 'lancamentos')}
      ${cartao('umbrella', 'Resumo de férias', 'Recibos de férias com início do gozo no período: dias, abono, valores e encargos.',
        `<div class="grid grid-cols-2 gap-3"><div>${labelCls('De')}<input id="rf-fe-ini" type="date" value="${ano}-01-01" class="${inputCls()}"></div>
         <div>${labelCls('Até')}<input id="rf-fe-fim" type="date" value="${ano}-12-31" class="${inputCls()}"></div></div>`, 'ferias')}
      ${cartao('user-x', 'Relação de rescisões', 'Desligamentos do período com verbas, FGTS e multa, incluindo as complementares.',
        `<div class="grid grid-cols-2 gap-3"><div>${labelCls('De')}<input id="rf-re-ini" type="date" value="${ano}-01-01" class="${inputCls()}"></div>
         <div>${labelCls('Até')}<input id="rf-re-fim" type="date" value="${ano}-12-31" class="${inputCls()}"></div></div>`, 'rescisoes')}
    </div>`;
  if (window.lucide) lucide.createIcons();
}

function _dprfQuery(nome) {
  const v = id => encodeURIComponent(document.getElementById(id)?.value || '');
  switch (nome) {
    case 'liquidos': return document.getElementById('rf-liq-run').value ? `run_id=${v('rf-liq-run')}` : null;
    case 'ficha-financeira': return document.getElementById('rf-ff-emp').value ? `employee_id=${v('rf-ff-emp')}&ano=${v('rf-ff-ano')}` : null;
    case 'lancamentos': return `competencia=${v('rf-lc-comp')}&codigo=${v('rf-lc-cod')}`;
    case 'ferias': return `inicio=${v('rf-fe-ini')}&fim=${v('rf-fe-fim')}`;
    case 'rescisoes': return `inicio=${v('rf-re-ini')}&fim=${v('rf-re-fim')}`;
  }
  return null;
}

async function _dprfAbrir(nome, formato) {
  const q = _dprfQuery(nome);
  if (!q) { alert('Preencha os filtros do relatório.'); return; }
  const url = `/api/dp/relatorios-folha/${nome}?${q}&formato=${formato}`;
  if (formato === 'html') { openAuthDoc(url); return; }
  try {
    const r = await fetch(url, { headers: authHeaders() });
    if (!r.ok) { const j = await r.json().catch(() => ({})); alert(j.detail || 'Erro ao gerar a planilha.'); return; }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await r.blob());
    a.download = `${nome}.csv`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  } catch { alert('Erro de conexão.'); }
}
