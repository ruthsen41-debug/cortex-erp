// ═══════════════════════════════════════════════════════════════
//  Central do eSocial (leiaute S-1.3)
//  Painel de eventos · Gerar eventos · Lotes · Totalizadores · Configuração
//  + conferência do FGTS Digital (usada na aba FGTS Digital)
// ═══════════════════════════════════════════════════════════════
(function () {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const brl = (v) => parseFloat(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const hojeData = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const hojeComp = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; };
  const inp = 'w-full border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100';
  const lbl = (t) => `<label class="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">${t}</label>`;
  const btn = (cor) => ({
    primario: 'bg-violet-600 hover:bg-violet-700 text-white',
    secundario: 'border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800',
    verde: 'bg-emerald-600 hover:bg-emerald-700 text-white',
  }[cor] + ' inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl transition disabled:opacity-50');

  const COR_STATUS = {
    pendente: 'bg-sky-50 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300',
    erro_validacao: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    enviado: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300',
    aceito: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    rejeitado: 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
    erro_envio: 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300',
    excluido: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
    substituido: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
  };
  const NOME_STATUS = {
    pendente: 'Pronto para enviar', erro_validacao: 'Com erro', enviado: 'Enviado', aceito: 'Aceito',
    rejeitado: 'Rejeitado', erro_envio: 'Erro no envio', excluido: 'Excluído', substituido: 'Retificado',
  };

  const st = { aba: 'painel', filtros: { status: '', tipo: '', per_apur: '' }, cfg: null, aberto: {} };
  let raiz = null;

  function toast(msg, tipo) { if (window.showToast) showToast(msg, tipo || 'info'); else alert(msg); }

  async function chamar(url, opts) {
    try { return await apiFetch(url, opts); } catch (e) { toast(e.message, 'error'); throw e; }
  }

  // ── estrutura ───────────────────────────────────────────────
  async function renderCentralEsocial(el) {
    raiz = el;
    try { st.cfg = await apiFetch('/api/esocial/config'); } catch (e) { st.cfg = null; }
    const abas = [['painel', 'layout-list', 'Painel de eventos'], ['gerar', 'wand-sparkles', 'Gerar eventos'],
      ['lotes', 'package', 'Lotes enviados'], ['totalizadores', 'sigma', 'Totalizadores'], ['config', 'settings', 'Configuração']];
    const cert = st.cfg?.certificado || {};
    const amb = st.cfg?.config?.ambiente || 2;
    el.innerHTML = `
      <div class="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg flex items-center gap-2"><i data-lucide="send" class="w-5 h-5 text-violet-500"></i>Central do eSocial</h2>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Leiaute S-1.3 · eventos validados pelos esquemas oficiais antes do envio</p>
        </div>
        <div class="flex flex-wrap gap-2 text-xs">
          <span class="px-3 py-1.5 rounded-full font-semibold ${amb === 1 ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'}">
            ${amb === 1 ? 'Ambiente: PRODUÇÃO' : 'Ambiente: produção restrita (testes)'}</span>
          <span class="px-3 py-1.5 rounded-full font-semibold ${cert.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}"
            title="${esc(cert.mensagem || '')}"><i data-lucide="${cert.ok ? 'shield-check' : 'shield-alert'}" class="w-3.5 h-3.5 inline -mt-0.5"></i>
            ${cert.ok ? 'Certificado A1 ok' : 'Sem certificado A1'}</span>
        </div>
      </div>
      ${!cert.ok ? `<div class="mb-4 text-xs rounded-xl px-4 py-3 bg-amber-50 text-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
        <strong>Sem certificado digital A1:</strong> você já pode gerar e validar todos os eventos (eles são conferidos com os esquemas oficiais do governo).
        Para <strong>transmitir</strong>, cadastre o certificado A1 da empresa em Empresa → Fiscal → Certificado A1. ${esc(cert.mensagem || '')}</div>` : ''}
      <div class="flex gap-1 mb-4 overflow-x-auto custom-scroll border-b border-slate-100 dark:border-slate-800 pb-2">
        ${abas.map(([id, ic, nome]) => `<button data-es-aba="${id}" onclick="esAba('${id}')"
          class="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg whitespace-nowrap ${st.aba === id ? 'bg-violet-600 text-white' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'}">
          <i data-lucide="${ic}" class="w-3.5 h-3.5"></i>${nome}</button>`).join('')}
      </div>
      <div id="es-corpo"></div>`;
    if (window.lucide) lucide.createIcons();
    await abrir(st.aba);
  }

  window.esAba = async (id) => { st.aba = id; await renderCentralEsocial(raiz); };

  async function abrir(id) {
    const c = document.getElementById('es-corpo');
    c.innerHTML = '<div class="p-8 text-center text-sm text-slate-400">Carregando…</div>';
    if (id === 'painel') await painel(c);
    else if (id === 'gerar') await gerar(c);
    else if (id === 'lotes') await lotes(c);
    else if (id === 'totalizadores') await totalizadores(c);
    else await config(c);
    if (window.lucide) lucide.createIcons();
  }

  // ── painel ──────────────────────────────────────────────────
  async function painel(c) {
    const f = st.filtros;
    const q = new URLSearchParams(f).toString();
    const d = await chamar(`/api/esocial/painel?${q}`);
    const n = d.contagem || {};
    const kpi = (k, rot, cor) => `<button onclick="esFiltro('status','${k}')" class="text-left rounded-2xl border p-3 ${f.status === k ? 'border-violet-400 ring-2 ring-violet-200' : 'border-slate-200 dark:border-slate-800'} bg-white dark:bg-slate-900">
      <div class="text-[11px] text-slate-500">${rot}</div><div class="text-xl font-bold ${cor}">${n[k] || 0}</div></button>`;
    const tipos = Object.keys(st.cfg?.eventos || {}).filter((t) => !t.startsWith('S-5'));
    const linhas = (d.eventos || []).map((e) => {
      const probl = [...(e.erros || []), ...(e.ocorrencias || []).map((o) => `${o.codigo}: ${o.descricao}${o.localizacao ? ` (${o.localizacao})` : ''}`)];
      const aberto = st.aberto[e.id];
      return `<tr class="border-b border-slate-100 dark:border-slate-800 text-sm">
        <td class="px-3 py-2"><input type="checkbox" class="es-sel" value="${e.id}" ${['pendente', 'erro_envio'].includes(e.status) ? '' : 'disabled'}></td>
        <td class="px-3 py-2 font-mono text-xs text-violet-600 whitespace-nowrap">${esc(e.tipo)}${e.ind_retif === 2 ? ' <span title="Retificação" class="text-amber-600">R</span>' : ''}</td>
        <td class="px-3 py-2 text-slate-700 dark:text-slate-200">${esc(e.descricao)}</td>
        <td class="px-3 py-2 text-xs text-slate-500 whitespace-nowrap">${esc(e.per_apur || '')}</td>
        <td class="px-3 py-2"><span class="text-[11px] font-semibold px-2 py-1 rounded-full ${COR_STATUS[e.status] || ''}">${NOME_STATUS[e.status] || esc(e.status)}</span>
          ${probl.length ? `<button onclick="esToggle(${e.id})" class="ml-1 text-[11px] text-amber-700 underline">${probl.length} aviso(s)</button>` : ''}</td>
        <td class="px-3 py-2 font-mono text-[11px] text-slate-400 whitespace-nowrap">${esc(e.nr_recibo || '')}</td>
        <td class="px-3 py-2 text-right whitespace-nowrap">${acoes(e)}</td>
      </tr>${aberto && probl.length ? `<tr class="bg-amber-50/60 dark:bg-amber-900/10"><td></td><td colspan="6" class="px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
        ${probl.map((p) => `<div>• ${esc(p)}</div>`).join('')}</td></tr>` : ''}`;
    }).join('');
    c.innerHTML = `
      <div class="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4">
        ${kpi('pendente', 'Prontos para enviar', 'text-sky-600')}${kpi('erro_validacao', 'Com erro', 'text-amber-600')}
        ${kpi('enviado', 'Aguardando retorno', 'text-indigo-600')}${kpi('aceito', 'Aceitos', 'text-emerald-600')}
        ${kpi('rejeitado', 'Rejeitados', 'text-rose-600')}${kpi('erro_envio', 'Erro no envio', 'text-rose-600')}
      </div>
      <div class="flex flex-wrap items-end gap-2 mb-3">
        <div>${lbl('Evento')}<select class="${inp}" onchange="esFiltro('tipo', this.value)"><option value="">Todos</option>
          ${tipos.map((t) => `<option value="${t}" ${f.tipo === t ? 'selected' : ''}>${t} — ${esc(st.cfg.eventos[t])}</option>`).join('')}</select></div>
        <div>${lbl('Competência')}<input type="month" class="${inp}" value="${esc(f.per_apur)}" onchange="esFiltro('per_apur', this.value)"></div>
        ${f.status || f.tipo || f.per_apur ? `<button class="${btn('secundario')}" onclick="esLimpar()">Limpar filtros</button>` : ''}
        <div class="ml-auto flex flex-wrap gap-2">
          <button class="${btn('secundario')}" onclick="esConsultar()"><i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>Consultar retornos</button>
          <button class="${btn('primario')}" onclick="esTransmitir(true)"><i data-lucide="send" class="w-3.5 h-3.5"></i>Enviar selecionados</button>
          <button class="${btn('verde')}" onclick="esTransmitir(false)"><i data-lucide="send-horizontal" class="w-3.5 h-3.5"></i>Enviar todos os prontos</button>
        </div>
      </div>
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-x-auto">
        <table class="w-full">
          <thead><tr class="text-[11px] text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
            <th class="px-3 py-2 w-8"><input type="checkbox" onchange="document.querySelectorAll('.es-sel:not(:disabled)').forEach(x=>x.checked=this.checked)"></th>
            <th class="px-3 py-2 text-left">Evento</th><th class="px-3 py-2 text-left">Descrição</th><th class="px-3 py-2 text-left">Período</th>
            <th class="px-3 py-2 text-left">Situação</th><th class="px-3 py-2 text-left">Recibo</th><th class="px-3 py-2"></th></tr></thead>
          <tbody>${linhas || '<tr><td colspan="7" class="px-3 py-10 text-center text-sm text-slate-400">Nenhum evento. Use a aba "Gerar eventos" para começar.</td></tr>'}</tbody>
        </table>
      </div>`;
  }

  function acoes(e) {
    const a = [];
    const lk = (fn, txt, cor) => `<button onclick="${fn}" class="text-xs ${cor || 'text-indigo-600'} hover:underline ml-2">${txt}</button>`;
    if (e.tem_xml) a.push(lk(`triggerDownload('/api/esocial/eventos/${e.id}/xml')`, 'XML'));
    if (['pendente', 'erro_validacao', 'erro_envio'].includes(e.status)) {
      a.push(lk(`esAcao(${e.id},'validar')`, 'Validar'));
      a.push(lk(`esDescartar(${e.id})`, 'Descartar', 'text-rose-600'));
    }
    if (e.status === 'aceito') {
      if (['S-2200', 'S-2230', 'S-2299', 'S-1200', 'S-1210', 'S-2210', 'S-2220', 'S-2240', 'S-2298', 'S-2300', 'S-2399'].includes(e.tipo)) a.push(lk(`esAcao(${e.id},'retificar')`, 'Retificar', 'text-amber-600'));
      if (!['S-1000', 'S-1005', 'S-1010', 'S-1020', 'S-1298', 'S-1299', 'S-3000'].includes(e.tipo)) a.push(lk(`esExcluir(${e.id})`, 'Excluir (S-3000)', 'text-rose-600'));
    }
    if (['aceito', 'rejeitado'].includes(e.status)) a.push(lk(`openAuthDoc('/api/esocial/eventos/${e.id}/retorno')`, 'Retorno', 'text-slate-500'));
    return a.join('');
  }

  window.esFiltro = async (k, v) => { st.filtros[k] = st.filtros[k] === v && k === 'status' ? '' : v; await abrir('painel'); };
  window.esLimpar = async () => { st.filtros = { status: '', tipo: '', per_apur: '' }; await abrir('painel'); };
  window.esToggle = async (id) => { st.aberto[id] = !st.aberto[id]; await abrir('painel'); };

  window.esAcao = async (id, acao) => {
    const r = await chamar(`/api/esocial/eventos/${id}/${acao}`, { method: 'POST' });
    const ev = (r.eventos || [r])[0] || {};
    toast(ev.status === 'erro_validacao' ? 'O evento ainda tem erros — veja os avisos.' : (acao === 'retificar' ? 'Retificação gerada. Envie para o eSocial.' : 'Evento validado.'),
      ev.status === 'erro_validacao' ? 'warning' : 'success');
    await abrir('painel');
  };
  window.esDescartar = async (id) => {
    if (!confirm('Descartar este evento da fila? (ele ainda não foi enviado)')) return;
    await chamar(`/api/esocial/eventos/${id}`, { method: 'DELETE' });
    await abrir('painel');
  };
  window.esExcluir = async (id) => {
    if (!confirm('Gerar o S-3000 para EXCLUIR este evento no eSocial? Depois é preciso enviar o S-3000.')) return;
    await chamar(`/api/esocial/eventos/${id}/excluir`, { method: 'POST' });
    toast('S-3000 gerado e pronto para enviar.', 'success');
    await abrir('painel');
  };
  window.esTransmitir = async (soSel) => {
    const ids = soSel ? [...document.querySelectorAll('.es-sel:checked')].map((x) => +x.value) : [];
    if (soSel && !ids.length) { toast('Selecione os eventos prontos para enviar.', 'warning'); return; }
    if ((st.cfg?.config?.ambiente || 2) === 1 && !confirm('Enviar para o ambiente de PRODUÇÃO do eSocial? Isso tem valor legal.')) return;
    const r = await chamar('/api/esocial/transmitir', { method: 'POST', body: JSON.stringify({ ids }) });
    const ok = (r.lotes || []).filter((l) => l.ok).length;
    const falhas = (r.lotes || []).filter((l) => !l.ok);
    if (!(r.lotes || []).length) toast('Nenhum evento pronto para enviar.', 'warning');
    else toast(`${r.enviados} evento(s) enviados em ${ok} lote(s).${falhas.length ? ' Falha: ' + falhas[0].mensagem : ''} Consulte os retornos em instantes.`, falhas.length ? 'warning' : 'success');
    await abrir('painel');
  };
  window.esConsultar = async () => {
    const r = await chamar('/api/esocial/consultar', { method: 'POST', body: '{}' });
    const l = r.lotes || [];
    if (!l.length) toast('Nenhum lote aguardando retorno.', 'info');
    else toast(l.map((x) => x.status === 'processado' ? `Lote ${x.lote_id}: ${x.aceitos} aceito(s), ${x.rejeitados} rejeitado(s)` : `Lote ${x.lote_id}: ${x.mensagem}`).join(' · '), 'success');
    await abrir('painel');
  };

  // ── gerar eventos ───────────────────────────────────────────
  async function gerar(c) {
    const o = await chamar('/api/esocial/origens');
    const opt = (lista, fmt) => lista.map((x) => `<option value="${x.id}">${esc(fmt(x))}</option>`).join('');
    const card = (ic, tit, desc, corpo) => `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 flex flex-col gap-3">
        <div class="flex items-center gap-2"><i data-lucide="${ic}" class="w-4 h-4 text-violet-500"></i><span class="font-bold text-sm text-slate-800 dark:text-slate-100">${tit}</span></div>
        <p class="text-xs text-slate-500 dark:text-slate-400 -mt-1">${desc}</p>${corpo}</div>`;
    const ativos = o.funcionarios.filter((f) => f.active !== 0);
    c.innerHTML = `
      <p class="text-xs text-slate-500 dark:text-slate-400 mb-3">Os eventos gerados vão para o painel já conferidos com os esquemas oficiais. Se faltar algum dado do cadastro, o painel mostra exatamente o quê.
        Ordem recomendada no início: <strong>tabelas → admissões → folha → fechamento</strong>.</p>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        ${card('building-2', 'Tabelas do empregador', 'S-1000 (empregador), S-1005 (estabelecimento), S-1020 (lotação) e S-1010 (rubricas). Primeiro envio da empresa ou após mudanças.',
          `<button class="${btn('primario')} justify-center" onclick="esGerar('/api/esocial/gerar/tabelas')"><i data-lucide="wand-sparkles" class="w-3.5 h-3.5"></i>Gerar tabelas</button>`)}
        ${card('user-plus', 'Admissão (S-2200)', 'Cadastro do vínculo. Gere para um funcionário ou para todos os ativos que ainda não têm admissão aceita.',
          `<select id="es-adm" class="${inp}">${opt(ativos, (f) => `${f.name} — ${f.status_s2200}`)}</select>
           <div class="flex gap-2"><button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/admissao/'+document.getElementById('es-adm').value)">Gerar para o selecionado</button>
           <button class="${btn('secundario')}" onclick="esGerar('/api/esocial/gerar/admissoes')">Todos pendentes</button></div>`)}
        ${card('user-cog', 'Alterações (S-2205 / S-2206)', 'Dados cadastrais (endereço, estado civil, dependentes…) ou contratuais (salário, cargo, jornada). Ajuste a ficha do funcionário antes.',
          `<select id="es-alt-emp" class="${inp}">${opt(ativos, (f) => f.name)}</select>
           <div class="grid grid-cols-2 gap-2"><select id="es-alt-tipo" class="${inp}"><option value="cadastral">Cadastral (S-2205)</option><option value="contratual">Contratual (S-2206)</option></select>
           <input id="es-alt-data" type="date" class="${inp}" value="${hojeData()}"></div>
           <button class="${btn('primario')}" onclick="esGerarAlteracao()">Gerar alteração</button>`)}
        ${card('calendar-x', 'Afastamento (S-2230)', 'Acidente/doença (acima de 15 dias quando não for do trabalho), licença-maternidade, serviço militar, suspensão…',
          o.afastamentos.length ? `<select id="es-afast" class="${inp}">${opt(o.afastamentos, (a) => `${a.name} — ${a.tipo} desde ${a.data_inicio}${a.codigo_esocial ? '' : ' (não vai ao eSocial)'}`)}</select>
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/afastamento/'+document.getElementById('es-afast').value)">Gerar afastamento</button>`
            : '<p class="text-xs text-slate-400">Nenhum afastamento lançado (DP → Afastamentos).</p>')}
        ${card('user-x', 'Desligamento (S-2299)', 'Rescisão com as verbas rescisórias por rubrica. Prazo: até 10 dias após o desligamento.',
          o.rescisoes.length ? `<select id="es-resc" class="${inp}">${opt(o.rescisoes, (r) => `${r.name} — ${r.referencia} em ${r.data_inicio}`)}</select>
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/desligamento/'+document.getElementById('es-resc').value)">Gerar desligamento</button>`
            : '<p class="text-xs text-slate-400">Nenhuma rescisão calculada (DP → Rescisão).</p>')}
        ${card('file-spreadsheet', 'Folha da competência (S-1200)', 'Um S-1200 por trabalhador com todos os valores do período: folha, férias, adiantamento do 13º, bolsa de estágio e RPA de autônomos. Para o 13º anual, informe só o ano.',
          `<div class="grid grid-cols-2 gap-2"><input id="es-rem-comp" type="month" class="${inp}" value="${hojeComp()}">
           <label class="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300"><input id="es-rem-13" type="checkbox"> 13º salário (anual)</label></div>
           <button class="${btn('primario')}" onclick="esGerarRemuneracoes()">Gerar remunerações</button>
           ${o.folhas.length ? `<details class="text-xs text-slate-500"><summary class="cursor-pointer">Gerar a partir de uma folha e informar a data de pagamento</summary>
             <div class="mt-2 flex flex-col gap-2"><select id="es-folha" class="${inp}">${opt(o.folhas, (f) => `${f.competence} — ${f.employee_count} func. (${f.status})`)}</select>
             <input id="es-folha-pg" type="date" class="${inp}"><button class="${btn('secundario')}" onclick="esGerarFolha()">Gerar S-1200 + S-1210 da folha</button></div></details>` : ''}`)}
        ${card('banknote', 'Pagamentos do mês (S-1210)', 'Um S-1210 por trabalhador com o que foi pago no mês: salários, férias, 13º, rescisões e RPA. Usa as datas de pagamento lançadas.',
          `<input id="es-pg-comp" type="month" class="${inp}" value="${hojeComp()}">
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/pagamentos',{per_apur:document.getElementById('es-pg-comp').value})">Gerar pagamentos</button>`)}
        ${card('triangle-alert', 'Acidente de trabalho — CAT (S-2210)', 'Prazo: 1º dia útil seguinte ao acidente (imediato em caso de óbito). Complete os códigos do eSocial antes de gerar.',
          o.cats.length ? `<select id="es-cat" class="${inp}">${opt(o.cats, (c) => `${c.name} — ${c.data_acidente}`)}</select>
           <div class="flex gap-2"><button class="${btn('secundario')}" onclick="esComplementar('cat', document.getElementById('es-cat').value)">Completar dados</button>
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/cat/'+document.getElementById('es-cat').value)">Gerar CAT</button></div>`
            : '<p class="text-xs text-slate-400">Nenhuma CAT lançada (DP → CAT).</p>')}
        ${card('stethoscope', 'Exame ocupacional — ASO (S-2220)', 'Admissional, periódico, retorno, mudança de risco e demissional. Prazo: dia 15 do mês seguinte ao exame.',
          o.asos.length ? `<select id="es-aso" class="${inp}">${opt(o.asos, (a) => `${a.name} — ${a.tipo} em ${a.data_exame}`)}</select>
           <div class="flex flex-wrap gap-2"><button class="${btn('secundario')}" onclick="esComplementar('aso', document.getElementById('es-aso').value)">Exames realizados</button>
           ${o.pcmso.length ? `<button class="${btn('secundario')}" onclick="esComplementar('pcmso', ${o.pcmso[0].id})">Médico do PCMSO</button>` : ''}
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/aso/'+document.getElementById('es-aso').value)">Gerar ASO</button></div>`
            : '<p class="text-xs text-slate-400">Nenhum exame lançado (DP → Exames/ASO).</p>')}
        ${card('hard-hat', 'Condições ambientais (S-2240)', 'Agentes nocivos a que o funcionário está exposto (ou ausência deles). Enviar na admissão e quando a condição mudar.',
          `${o.exposicoes.length ? `<select id="es-expo" class="${inp}">${opt(o.exposicoes, (x) => `${x.name} — ${x.dsc_setor || 'sem setor'} desde ${x.dt_inicio}`)}</select>
           <div class="flex gap-2"><button class="${btn('secundario')}" onclick="esComplementar('exposicao', document.getElementById('es-expo').value)">Editar</button>
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/exposicao/'+document.getElementById('es-expo').value)">Gerar S-2240</button></div>` : ''}
           <div class="flex gap-2"><select id="es-expo-emp" class="${inp}">${opt(ativos, (f) => f.name)}</select>
           <button class="${btn('secundario')} whitespace-nowrap" onclick="esNovaExposicao()">+ Nova</button></div>`)}
        ${card('user-check', 'Reintegração (S-2298)', 'Retorno do empregado desligado, por decisão judicial ou anistia.',
          o.reintegracoes.length ? `<select id="es-reint" class="${inp}">${opt(o.reintegracoes, (r) => `${r.name} — retorno em ${r.data_reintegracao}`)}</select>
           <div class="flex gap-2"><button class="${btn('secundario')}" onclick="esComplementar('reintegracao', document.getElementById('es-reint').value)">Completar dados</button>
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/reintegracao/'+document.getElementById('es-reint').value)">Gerar S-2298</button></div>`
            : '<p class="text-xs text-slate-400">Nenhuma reintegração lançada (DP → Reintegrações).</p>')}
        ${card('graduation-cap', 'Estagiário (S-2300 / S-2399)', 'Início e término do estágio. A bolsa mensal entra automaticamente no S-1200 da competência.',
          o.estagiarios.length ? `<select id="es-estag" class="${inp}">${opt(o.estagiarios, (e) => `${e.nome} — ${e.data_inicio} a ${e.data_fim || '?'}`)}</select>
           <div class="flex flex-wrap gap-2"><button class="${btn('secundario')}" onclick="esComplementar('estagiario', document.getElementById('es-estag').value)">Completar dados</button>
           <button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/estagio-inicio/'+document.getElementById('es-estag').value)">Início (S-2300)</button>
           <button class="${btn('secundario')}" onclick="esGerar('/api/esocial/gerar/estagio-termino/'+document.getElementById('es-estag').value)">Término (S-2399)</button></div>`
            : '<p class="text-xs text-slate-400">Nenhum estagiário cadastrado (DP → Estágio & Aprendiz).</p>')}
        ${card('user-round', 'Autônomos (RPA)', 'Os pagamentos de RPA entram no S-1200 da competência (categoria 701). O eSocial exige a data de nascimento e o CBO do autônomo.',
          o.autonomos.length ? `<select id="es-auto" class="${inp}">${opt(o.autonomos, (a) => a.nome)}</select>
           <button class="${btn('secundario')}" onclick="esComplementar('autonomo', document.getElementById('es-auto').value)">Completar dados</button>`
            : '<p class="text-xs text-slate-400">Nenhum autônomo cadastrado (DP → Autônomos/RPA).</p>')}
        ${card('lock', 'Fechamento / reabertura (S-1299 / S-1298)', 'Fecha a competência no eSocial (envia os débitos à DCTFWeb) ou reabre para corrigir eventos periódicos.',
          `<input id="es-fech-comp" type="month" class="${inp}" value="${hojeComp()}">
           <div class="flex gap-2"><button class="${btn('primario')}" onclick="esGerar('/api/esocial/gerar/fechamento',{per_apur:document.getElementById('es-fech-comp').value})">Gerar fechamento</button>
           <button class="${btn('secundario')}" onclick="esGerar('/api/esocial/gerar/reabertura',{per_apur:document.getElementById('es-fech-comp').value})">Reabertura</button></div>`)}
      </div>`;
  }

  window.esGerar = async (url, corpo) => {
    const r = await chamar(url, { method: 'POST', body: JSON.stringify(corpo || {}) });
    const evs = r.eventos || [];
    const erros = evs.filter((e) => e.status === 'erro_validacao');
    if (!evs.length) toast('Nada para gerar.', 'info');
    else if (erros.length) toast(`${evs.length} evento(s) gerado(s); ${erros.length} com dados faltando — veja no painel.`, 'warning');
    else toast(`${evs.length} evento(s) gerado(s) e validado(s). Pronto(s) para enviar.`, 'success');
    st.filtros = { status: erros.length ? 'erro_validacao' : '', tipo: '', per_apur: '' };
    await window.esAba('painel');
  };
  window.esGerarAlteracao = () => {
    const id = document.getElementById('es-alt-emp').value;
    const tipo = document.getElementById('es-alt-tipo').value;
    return window.esGerar(`/api/esocial/gerar/alteracao-${tipo}/${id}`, { data: document.getElementById('es-alt-data').value });
  };
  window.esGerarRemuneracoes = () => {
    const comp = document.getElementById('es-rem-comp').value;
    const anual = document.getElementById('es-rem-13').checked;
    return window.esGerar('/api/esocial/gerar/remuneracoes', { per_apur: anual ? comp.slice(0, 4) : comp });
  };
  window.esNovaExposicao = async () => {
    const emp = document.getElementById('es-expo-emp').value;
    const r = await chamar('/api/esocial/exposicoes', { method: 'POST', body: JSON.stringify({ employee_id: +emp }) });
    await window.esComplementar('exposicao', r.id, true);
  };

  // ── complementos do eSocial (janela) ────────────────────────
  const cpx = { tipo: '', id: 0, dados: null, recarregar: false };

  window.esComplementar = async (tipo, id, recarregar) => {
    if (!id) return;
    const d = await chamar(`/api/esocial/complementos/${tipo}/${id}`);
    Object.assign(cpx, { tipo, id, dados: d, recarregar: !!recarregar });
    const campo = (c) => {
      const v = d.valores[c.k] ?? '';
      const largo = c.largo ? 'md:col-span-2' : '';
      const dica = c.dica ? `<p class="text-[11px] text-slate-400 mt-1">${esc(c.dica)}</p>` : '';
      if (c.tipo === 'select') {
        return `<div class="${largo}">${lbl(c.rot)}<select data-cpx="${c.k}" class="${inp}">${c.opcoes.map(([k, t]) => `<option value="${esc(k)}" ${String(v) === String(k) ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select>${dica}</div>`;
      }
      if (c.tipo === 'textarea') return `<div class="${largo}">${lbl(c.rot)}<textarea data-cpx="${c.k}" rows="2" class="${inp}">${esc(v)}</textarea>${dica}</div>`;
      if (c.tipo === 'tabela') {
        return `<div class="${largo}">${lbl(c.rot)}<div class="flex gap-2"><input data-cpx="${c.k}" class="${inp} font-mono" style="max-width:130px" value="${esc(v)}" placeholder="código">
          <input class="${inp}" placeholder="buscar na tabela ${esc(c.tabela)}…" oninput="esBuscaTab(this,'${c.tabela}','${c.k}')"></div>
          <div id="cpx-res-${c.k}" class="mt-1 max-h-36 overflow-y-auto text-xs"></div>${dica}</div>`;
      }
      if (c.tipo === 'procedimentos') {
        return `<div class="md:col-span-2">${lbl(c.rot)}<div id="cpx-procs" class="flex flex-wrap gap-1 mb-2"></div>
          <input class="${inp}" placeholder="buscar exame (ex.: audiometria, hemograma)…" oninput="esBuscaTab(this,'27','__proc')">
          <div id="cpx-res-__proc" class="mt-1 max-h-36 overflow-y-auto text-xs"></div>${dica}</div>`;
      }
      if (c.tipo === 'agentes') {
        return `<div class="md:col-span-2">${lbl(c.rot)}<div id="cpx-agentes" class="flex flex-col gap-2 mb-2"></div>
          <input class="${inp}" placeholder="buscar agente nocivo (ex.: ruído, poeira, benzeno)…" oninput="esBuscaTab(this,'24','__ag')">
          <div id="cpx-res-__ag" class="mt-1 max-h-36 overflow-y-auto text-xs"></div>${dica}</div>`;
      }
      return `<div class="${largo}">${lbl(c.rot)}<input data-cpx="${c.k}" type="${c.tipo === 'number' ? 'number' : c.tipo}" class="${inp}" value="${esc(v)}">${dica}</div>`;
    };
    openModal(`<div class="bg-white dark:bg-slate-900 rounded-2xl w-full flex flex-col max-h-[90vh] overflow-hidden">
      <div class="shrink-0 px-5 py-4 border-b border-slate-100 dark:border-slate-800 font-bold text-slate-800 dark:text-slate-100">${esc(d.titulo)}</div>
      <div class="flex-1 min-h-0 overflow-y-auto custom-scroll p-5 grid grid-cols-1 md:grid-cols-2 gap-4">${d.campos.map(campo).join('')}</div>
      <div class="shrink-0 px-5 py-3 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2">
        <button class="${btn('secundario')}" onclick="closeModal()">Cancelar</button>
        <button class="${btn('primario')}" onclick="esSalvarComplemento()">Salvar</button></div></div>`);
    const box = document.getElementById('modal-box');
    if (box) { box.classList.remove('max-w-3xl', 'p-6', 'overflow-y-auto'); box.classList.add('max-w-4xl', 'p-0', 'overflow-hidden'); }
    esDesenharListas();
  };

  function esDesenharListas() {
    const v = cpx.dados?.valores || {};
    const procs = document.getElementById('cpx-procs');
    if (procs) {
      const lst = v.procedimentos || [];
      procs.innerHTML = lst.length ? lst.map((p, i) => `<span class="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-violet-50 text-violet-700 text-xs">
        ${esc(p.cod)} ${esc(p.dsc || '')}<button onclick="esRemoverItem('procedimentos',${i})" class="ml-1">×</button></span>`).join('')
        : '<span class="text-xs text-slate-400">Nenhum exame listado (será enviado 0295 — avaliação clínica).</span>';
    }
    const ag = document.getElementById('cpx-agentes');
    if (ag) {
      const lst = v.agentes || [];
      ag.innerHTML = lst.map((a, i) => `<div class="rounded-xl border border-slate-200 dark:border-slate-700 p-3 text-xs">
        <div class="flex justify-between gap-2"><strong class="font-mono">${esc(a.cod)}</strong><span class="flex-1">${esc(a.dsc || '')}</span>
        <button onclick="esRemoverItem('agentes',${i})" class="text-rose-600">remover</button></div>
        ${a.cod !== '09.01.001' ? `<div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
          <select class="${inp}" onchange="esAgente(${i},'tp_aval',this.value)"><option value="2" ${a.tp_aval == '2' ? 'selected' : ''}>Avaliação qualitativa</option><option value="1" ${a.tp_aval == '1' ? 'selected' : ''}>Quantitativa</option></select>
          <input class="${inp}" placeholder="intensidade" value="${esc(a.int_conc || '')}" onchange="esAgente(${i},'int_conc',this.value)">
          <input class="${inp}" placeholder="limite de tolerância" value="${esc(a.lim_tol || '')}" onchange="esAgente(${i},'lim_tol',this.value)">
          <input class="${inp}" placeholder="técnica de medição" value="${esc(a.tec_medicao || '')}" onchange="esAgente(${i},'tec_medicao',this.value)">
          <select class="${inp}" onchange="esAgente(${i},'utiliz_epc',this.value)"><option value="0">EPC: não se aplica</option><option value="1" ${a.utiliz_epc == '1' ? 'selected' : ''}>EPC: não implementa</option><option value="2" ${a.utiliz_epc == '2' ? 'selected' : ''}>EPC: implementa</option></select>
          <select class="${inp}" onchange="esAgente(${i},'utiliz_epi',this.value)"><option value="0">EPI: não se aplica</option><option value="1" ${a.utiliz_epi == '1' ? 'selected' : ''}>EPI: não utilizado</option><option value="2" ${a.utiliz_epi == '2' ? 'selected' : ''}>EPI: utilizado</option></select>
          <input class="${inp} md:col-span-2" placeholder="CA do EPI" value="${esc(a.ca_epi || '')}" onchange="esAgente(${i},'ca_epi',this.value)"></div>` : ''}</div>`).join('');
    }
  }

  let esTimer = null;
  window.esBuscaTab = (el, tabela, alvo) => {
    clearTimeout(esTimer);
    esTimer = setTimeout(async () => {
      const box = document.getElementById(`cpx-res-${alvo}`);
      if (!el.value.trim()) { box.innerHTML = ''; return; }
      const r = await apiFetch(`/api/esocial/tabelas/${tabela}?q=${encodeURIComponent(el.value.trim())}`);
      box.innerHTML = r.map((x) => `<button class="block w-full text-left px-2 py-1 rounded hover:bg-violet-50 dark:hover:bg-slate-800"
        onclick='esEscolherTab(${JSON.stringify(alvo)}, ${JSON.stringify(x.codigo)}, ${JSON.stringify(x.descricao)})'>
        <span class="font-mono text-violet-600">${esc(x.codigo)}</span> ${esc(x.descricao)}</button>`).join('') || '<span class="text-slate-400 px-2">Nada encontrado.</span>';
    }, 250);
  };
  window.esEscolherTab = (alvo, cod, dsc) => {
    const v = cpx.dados.valores;
    if (alvo === '__proc') {
      v.procedimentos = [...(v.procedimentos || []).filter((p) => p.cod !== cod), { cod, dsc, ord: cod === '0281' ? '1' : undefined }];
    } else if (alvo === '__ag') {
      v.agentes = cod === '09.01.001' ? [{ cod, dsc }]
        : [...(v.agentes || []).filter((a) => a.cod !== cod && a.cod !== '09.01.001'), { cod, dsc, tp_aval: '2', utiliz_epc: '0', utiliz_epi: '0' }];
    } else {
      const inpEl = document.querySelector(`[data-cpx="${alvo}"]`);
      if (inpEl) inpEl.value = cod;
    }
    document.querySelectorAll('[id^="cpx-res-"]').forEach((b) => { b.innerHTML = ''; });
    esDesenharListas();
  };
  window.esRemoverItem = (lista, i) => { cpx.dados.valores[lista].splice(i, 1); esDesenharListas(); };
  window.esAgente = (i, k, val) => { cpx.dados.valores.agentes[i][k] = val; };
  window.esSalvarComplemento = async () => {
    const dados = {};
    document.querySelectorAll('[data-cpx]').forEach((el) => { dados[el.dataset.cpx] = el.value; });
    const v = cpx.dados.valores;
    if ('procedimentos' in v) dados.procedimentos = v.procedimentos;
    if ('agentes' in v) dados.agentes = v.agentes;
    await chamar(`/api/esocial/complementos/${cpx.tipo}/${cpx.id}`, { method: 'PUT', body: JSON.stringify(dados) });
    closeModal();
    toast('Dados do eSocial salvos.', 'success');
    if (cpx.recarregar) await window.esAba('gerar');
  };

  window.esGerarFolha = () => window.esGerar(`/api/esocial/gerar/folha/${document.getElementById('es-folha').value}`,
    { data_pagamento: document.getElementById('es-folha-pg').value });

  // ── lotes e totalizadores ───────────────────────────────────
  async function lotes(c) {
    const l = await chamar('/api/esocial/lotes');
    const grupo = { 1: 'Tabelas', 2: 'Não periódicos', 3: 'Periódicos' };
    c.innerHTML = `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-x-auto"><table class="w-full text-sm">
      <thead><tr class="text-[11px] text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
        <th class="px-3 py-2 text-left">Lote</th><th class="px-3 py-2 text-left">Grupo</th><th class="px-3 py-2 text-left">Eventos</th>
        <th class="px-3 py-2 text-left">Protocolo</th><th class="px-3 py-2 text-left">Situação</th><th class="px-3 py-2 text-left">Enviado em</th></tr></thead>
      <tbody>${l.map((x) => `<tr class="border-b border-slate-100 dark:border-slate-800">
        <td class="px-3 py-2">#${x.id}</td><td class="px-3 py-2">${grupo[x.grupo] || x.grupo}</td><td class="px-3 py-2">${x.qtd_eventos}</td>
        <td class="px-3 py-2 font-mono text-xs">${esc(x.protocolo || '—')}</td>
        <td class="px-3 py-2 text-xs">${esc(x.status)} ${x.cd_resposta ? `(${esc(x.cd_resposta)} — ${esc(x.desc_resposta)})` : esc(x.desc_resposta || '')}</td>
        <td class="px-3 py-2 text-xs text-slate-500">${esc(x.created_at || '')}</td></tr>`).join('')
        || '<tr><td colspan="6" class="px-3 py-10 text-center text-slate-400">Nenhum lote enviado ainda.</td></tr>'}</tbody></table></div>`;
  }

  async function totalizadores(c) {
    const t = await chamar('/api/esocial/totalizadores');
    c.innerHTML = `<p class="text-xs text-slate-500 dark:text-slate-400 mb-3">Os totalizadores são devolvidos pelo eSocial após processar a folha:
      S-5001/S-5011 (INSS), S-5002/S-5012 (IRRF) e S-5003/S-5013 (FGTS). São eles que alimentam a DCTFWeb e o FGTS Digital.</p>
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-x-auto"><table class="w-full text-sm">
      <thead><tr class="text-[11px] text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800">
        <th class="px-3 py-2 text-left">Tipo</th><th class="px-3 py-2 text-left">Descrição</th><th class="px-3 py-2 text-left">Competência</th>
        <th class="px-3 py-2 text-left">Funcionário</th><th class="px-3 py-2 text-left">Recebido em</th></tr></thead>
      <tbody>${t.map((x) => `<tr class="border-b border-slate-100 dark:border-slate-800"><td class="px-3 py-2 font-mono text-xs text-violet-600">${esc(x.tipo)}</td>
        <td class="px-3 py-2">${esc(st.cfg?.eventos?.[x.tipo] || '')}</td><td class="px-3 py-2">${esc(x.per_apur)}</td>
        <td class="px-3 py-2">${esc(x.funcionario || '')}</td><td class="px-3 py-2 text-xs text-slate-500">${esc(x.created_at)}</td></tr>`).join('')
        || '<tr><td colspan="5" class="px-3 py-10 text-center text-slate-400">Nenhum totalizador recebido ainda.</td></tr>'}</tbody></table></div>`;
  }

  // ── configuração ────────────────────────────────────────────
  async function config(c) {
    const cfg = st.cfg?.config || {};
    const classes = st.cfg?.class_trib || {};
    const campo = (k, rot, ajuda, tipo) => `<div>${lbl(rot)}<input id="es-cfg-${k}" type="${tipo || 'text'}" class="${inp}" value="${esc(cfg[k] ?? '')}">
      ${ajuda ? `<p class="text-[11px] text-slate-400 mt-1">${ajuda}</p>` : ''}</div>`;
    c.innerHTML = `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>${lbl('Ambiente de envio')}<select id="es-cfg-ambiente" class="${inp}">
            <option value="2" ${cfg.ambiente !== 1 ? 'selected' : ''}>Produção restrita (testes)</option>
            <option value="1" ${cfg.ambiente === 1 ? 'selected' : ''}>Produção (valor legal)</option></select>
            <p class="text-[11px] text-slate-400 mt-1">Comece pela produção restrita. Os dados de lá não têm valor legal.</p></div>
          <div class="md:col-span-2">${lbl('Classificação tributária (Tabela 08)')}<select id="es-cfg-class_trib" class="${inp}">
            ${Object.entries(classes).map(([k, v]) => `<option value="${k}" ${cfg.class_trib === k ? 'selected' : ''}>${k} — ${esc(v)}</option>`).join('')}</select></div>
          ${campo('cnae', 'CNAE preponderante (7 dígitos)', 'Usado no S-1005 (estabelecimento).')}
          ${campo('fpas', 'FPAS', 'Ex.: 515 comércio/serviços, 507 indústria.')}
          ${campo('cod_tercs', 'Código de terceiros', 'Simples Nacional: 0000. Demais: conforme o FPAS (ex.: 0115 para FPAS 515).')}
          ${campo('fap', 'FAP (opcional)', 'Só informe se diferente do divulgado pelo governo.')}
          ${campo('cod_lotacao', 'Código da lotação tributária', 'Identificador interno usado no S-1020 e na folha.')}
          ${campo('ide_tab_rubr', 'Identificador da tabela de rubricas', 'Até 8 caracteres.')}
          ${campo('ini_valid', 'Início de validade das tabelas (AAAA-MM)', 'Mês de início das informações no eSocial.')}
          <div>${lbl('Transmissor')}<select id="es-cfg-transmissor_tp_insc" class="${inp}">
            <option value="1" ${String(cfg.transmissor_tp_insc) !== '2' ? 'selected' : ''}>CNPJ</option><option value="2" ${String(cfg.transmissor_tp_insc) === '2' ? 'selected' : ''}>CPF</option></select></div>
          ${campo('transmissor_nr_insc', 'CNPJ/CPF do transmissor', 'Quem assina e envia (empresa, ou o contador com procuração eletrônica).')}
        </div>
        <div class="mt-5 flex justify-end"><button class="${btn('primario')}" onclick="esSalvarCfg()"><i data-lucide="save" class="w-3.5 h-3.5"></i>Salvar configuração</button></div>
      </div>`;
  }

  window.esSalvarCfg = async () => {
    const ler = (k) => document.getElementById(`es-cfg-${k}`)?.value ?? '';
    const dados = {};
    ['ambiente', 'class_trib', 'cnae', 'fpas', 'cod_tercs', 'fap', 'cod_lotacao', 'ide_tab_rubr', 'ini_valid', 'transmissor_tp_insc', 'transmissor_nr_insc']
      .forEach((k) => { dados[k] = ler(k); });
    dados.ambiente = +dados.ambiente;
    if (dados.ambiente === 1 && !confirm('Mudar para PRODUÇÃO? Os eventos enviados passam a ter valor legal.')) return;
    await chamar('/api/esocial/config', { method: 'PUT', body: JSON.stringify(dados) });
    toast('Configuração salva.', 'success');
    await renderCentralEsocial(raiz);
  };

  // ── FGTS Digital: conferência da guia ───────────────────────
  window.renderConferenciaFgts = async (el, comp) => {
    let d;
    try { d = await apiFetch(`/api/esocial/fgts/${comp}`); } catch (e) { el.innerHTML = `<p class="text-rose-600 p-4">${esc(e.message)}</p>`; return; }
    if (!d.funcionarios.length && !d.rescisoes.length) {
      el.innerHTML = `<p class="text-sm text-slate-500 p-4">Nenhuma folha processada em ${esc(comp)}.</p>`; return;
    }
    el.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div class="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-slate-900"><div class="text-xs text-slate-500">FGTS mensal (folha)</div><div class="text-xl font-bold">${brl(d.total_mensal)}</div></div>
        <div class="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 bg-white dark:bg-slate-900"><div class="text-xs text-slate-500">FGTS rescisório + multa</div><div class="text-xl font-bold">${brl(d.total_rescisorio)}</div></div>
        <div class="rounded-2xl border border-violet-300 p-4 bg-violet-50 dark:bg-violet-900/20"><div class="text-xs text-violet-700">Valor esperado na guia (GFD)</div><div class="text-xl font-bold text-violet-700">${brl(d.total_guia_estimado)}</div></div>
      </div>
      <div class="text-xs rounded-xl px-4 py-3 mb-4 ${d.todos_s1200_aceitos ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'}">
        ${d.todos_s1200_aceitos ? 'Todos os S-1200 da competência foram aceitos: o FGTS Digital já tem os dados. Emita a guia no portal e confira com o valor acima.'
          : 'Ainda há funcionários sem S-1200 aceito. O FGTS Digital só calcula a guia depois que a remuneração é aceita no eSocial (Central eSocial → Gerar eventos → Folha).'}
        ${d.s5013_recebido ? ' Totalizador S-5013 recebido.' : ''}</div>
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-x-auto"><table class="w-full text-sm">
        <thead><tr class="text-[11px] text-slate-400 uppercase border-b border-slate-100 dark:border-slate-800"><th class="px-3 py-2 text-left">Funcionário</th>
          <th class="px-3 py-2 text-right">Base FGTS</th><th class="px-3 py-2 text-right">Alíquota</th><th class="px-3 py-2 text-right">FGTS</th><th class="px-3 py-2 text-left">S-1200</th></tr></thead>
        <tbody>${d.funcionarios.map((f) => `<tr class="border-b border-slate-100 dark:border-slate-800"><td class="px-3 py-2">${esc(f.nome)}</td>
          <td class="px-3 py-2 text-right">${brl(f.base)}</td><td class="px-3 py-2 text-right">${(f.aliquota * 100).toFixed(0)}%</td>
          <td class="px-3 py-2 text-right font-semibold">${brl(f.fgts_folha)}</td><td class="px-3 py-2 text-xs">${esc(f.status_s1200)}</td></tr>`).join('')}</tbody>
      </table></div>
      <p class="text-[11px] text-slate-400 mt-3">A guia é emitida em <strong>fgtsdigital.sistema.gov.br</strong> (acesso gov.br com certificado ou procuração) e paga por PIX.</p>`;
  };

  // Atalhos usados em outras telas do DP (ficha, folha, rescisão)
  window.esEnviarCentral = async (url, corpo) => {
    let r;
    try { r = await apiFetch(url, { method: 'POST', body: JSON.stringify(corpo || {}) }); } catch (e) { toast(e.message, 'error'); return; }
    const evs = r.eventos || [];
    const erros = evs.filter((e) => e.status === 'erro_validacao');
    if (erros.length) {
      const lista = erros.flatMap((e) => e.erros || []).slice(0, 6).join('\n- ');
      alert('O evento foi para a Central do eSocial, mas faltam dados:\n\n- ' + lista + '\n\nCorrija o cadastro e gere novamente.');
    } else {
      toast(`${evs.length} evento(s) na Central do eSocial, validado(s) e pronto(s) para enviar.`, 'success');
    }
  };
  window.esFolhaParaCentral = (runId) => {
    const pg = prompt('Data do pagamento da folha (AAAA-MM-DD) para gerar também o S-1210.\nDeixe em branco para gerar só o S-1200.', '');
    if (pg === null) return;
    return window.esEnviarCentral(`/api/esocial/gerar/folha/${runId}`, { data_pagamento: pg.trim() });
  };

  window.renderCentralEsocial = renderCentralEsocial;
})();
