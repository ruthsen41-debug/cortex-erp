// ============================================================
// DEPARTAMENTO PESSOAL — Pacote de modelos de documentos
// Contratos, acordos de jornada, férias, benefícios e termos, com texto personalizável por empresa.
// Usa os helpers de dp.js e dp_folha_extra.js: authHeaders, inputCls, labelCls, _dpEsc, dpEmployees,
// openAuthDoc, _dpxModal, _dpxPost, apiFetch, showToast.
// ============================================================

let _mdModelos = [];
let _mdGrupos = [];

async function renderModelosDocumentos(box) {
  if (!box) return;
  box.innerHTML = '<div class="text-xs text-slate-400 p-4">Carregando modelos…</div>';
  try {
    const r = await apiFetch('/api/dp/modelos-documentos');
    _mdModelos = r.modelos || [];
    _mdGrupos = r.grupos || [];
  } catch (e) {
    box.innerHTML = `<div class="text-xs text-rose-500 p-4">${_dpEsc(e.message)}</div>`;
    return;
  }
  const emps = dpEmployees.filter(e => e.active).map(e => `<option value="${e.id}">${_dpEsc(e.name)}</option>`).join('')
    + dpEmployees.filter(e => !e.active).map(e => `<option value="${e.id}">${_dpEsc(e.name)} (desligado)</option>`).join('');
  box.innerHTML = `
    <div class="flex flex-wrap items-end justify-between gap-3 mt-10 mb-4">
      <div>
        <h2 class="font-bold text-slate-800 dark:text-slate-100 text-lg mb-1">Modelos de documentos</h2>
        <p class="text-xs text-slate-400">Escolha o funcionário e clique em <b>Gerar</b>. Os dados saem do cadastro.
          Em <b>Editar</b> você adapta o texto ao jeito da empresa, e pode voltar ao padrão quando quiser.</p>
      </div>
      <button onclick="_mdEditar(null)" class="text-xs px-3 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white flex items-center gap-1.5">
        <i data-lucide="file-plus" class="w-3.5 h-3.5"></i> Novo modelo</button>
    </div>
    <div class="flex flex-wrap gap-3 mb-5">
      <div class="min-w-[260px] flex-1">${labelCls('Funcionário')}<select id="md-emp" class="${inputCls()}">${emps}</select></div>
      <div class="min-w-[220px]">${labelCls('Procurar')}<input id="md-busca" oninput="_mdFiltrar()" placeholder="ex.: férias, contrato" class="${inputCls()}"></div>
    </div>
    <div id="md-lista"></div>`;
  _mdFiltrar();
}

function _mdFiltrar() {
  const alvo = document.getElementById('md-lista');
  if (!alvo) return;
  const q = (document.getElementById('md-busca')?.value || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const casa = m => !q || `${m.titulo} ${m.descricao} ${m.base_legal} ${m.grupo}`.toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '').includes(q);
  const html = _mdGrupos.map(g => {
    const itens = _mdModelos.filter(m => m.grupo === g && casa(m));
    if (!itens.length) return '';
    return `<div class="mb-6">
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600 mb-2">${_dpEsc(g)}</div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">${itens.map(_mdCartao).join('')}</div></div>`;
  }).join('');
  alvo.innerHTML = html || '<div class="text-xs text-slate-400">Nenhum modelo encontrado.</div>';
  if (window.lucide) lucide.createIcons();
}

function _mdCartao(m) {
  const selo = m.proprio ? '<span class="text-[10px] px-2 py-0.5 rounded-full bg-sky-100 text-sky-700">Próprio</span>'
    : m.personalizado ? '<span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">Personalizado</span>' : '';
  return `<div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 flex flex-col gap-2">
    <div class="flex items-start justify-between gap-2">
      <span class="font-bold text-sm text-slate-800 dark:text-slate-100">${_dpEsc(m.titulo)}</span>${selo}</div>
    <p class="text-[11px] text-slate-500 dark:text-slate-400">${_dpEsc(m.descricao)}</p>
    ${m.base_legal ? `<p class="text-[10px] text-slate-400">${_dpEsc(m.base_legal)}</p>` : ''}
    <div class="flex gap-2 mt-auto pt-1">
      <button onclick="_mdGerar('${m.codigo}')" class="flex-1 text-xs px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white flex items-center justify-center gap-1.5">
        <i data-lucide="printer" class="w-3.5 h-3.5"></i> Gerar</button>
      <button onclick="_mdEditar('${m.codigo}')" title="Editar o texto do modelo" class="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-1.5">
        <i data-lucide="pencil" class="w-3.5 h-3.5"></i> Editar</button>
    </div></div>`;
}

function _mdEmpId() {
  const v = document.getElementById('md-emp')?.value;
  if (!v) { alert('Cadastre ou selecione um funcionário.'); return null; }
  return v;
}

function _mdCampoHtml(c) {
  const padrao = String(c.padrao || '').includes('{{') ? '' : (c.padrao || '');
  const ph = String(c.padrao || '').includes('{{') ? 'em branco: usa o cadastro' : '';
  let input;
  if (c.tipo === 'select') {
    input = `<select id="mdc-${c.nome}" class="${inputCls()}">${c.opcoes.map(([k, t]) =>
      `<option value="${_dpEsc(k)}" ${k === padrao ? 'selected' : ''}>${_dpEsc(t)}</option>`).join('')}</select>`;
  } else if (c.tipo === 'textarea') {
    input = `<textarea id="mdc-${c.nome}" rows="3" class="${inputCls()}">${_dpEsc(padrao)}</textarea>`;
  } else {
    const tipo = c.tipo === 'number' ? 'number' : c.tipo === 'date' ? 'date' : 'text';
    input = `<input id="mdc-${c.nome}" type="${tipo}" ${tipo === 'number' ? 'step="any"' : ''} value="${_dpEsc(padrao)}" placeholder="${ph}" class="${inputCls()}">`;
  }
  return `<div class="${c.tipo === 'textarea' ? 'md:col-span-2' : ''}">${labelCls(c.rotulo)}${input}
    ${c.ajuda ? `<p class="text-[10px] text-slate-400 mt-1">${_dpEsc(c.ajuda)}</p>` : ''}</div>`;
}

function _mdGerar(codigo) {
  const emp = _mdEmpId();
  if (!emp) return;
  const m = _mdModelos.find(x => x.codigo === codigo);
  if (!m) return;
  if (!m.campos || !m.campos.length) {
    openAuthDoc(`/api/dp/employees/${emp}/modelo/${encodeURIComponent(codigo)}`);
    return;
  }
  const nome = dpEmployees.find(e => String(e.id) === String(emp))?.name || '';
  _dpxModal('md-modal-gerar', `${_dpEsc(m.titulo)} — ${_dpEsc(nome)}`, `
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">${m.campos.map(_mdCampoHtml).join('')}</div>
    <div class="flex justify-end gap-2 mt-5">
      <button onclick="document.getElementById('md-modal-gerar').remove()" class="text-xs px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700">Cancelar</button>
      <button onclick="_mdGerarConfirma('${codigo}', '${emp}')" class="text-xs px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white flex items-center gap-1.5">
        <i data-lucide="printer" class="w-3.5 h-3.5"></i> Gerar documento</button>
    </div>`, 'max-w-2xl');
}

function _mdGerarConfirma(codigo, emp) {
  const m = _mdModelos.find(x => x.codigo === codigo);
  const qs = new URLSearchParams();
  (m?.campos || []).forEach(c => {
    const v = document.getElementById(`mdc-${c.nome}`)?.value;
    if (v !== undefined && v !== '') qs.set(c.nome, v);
  });
  openAuthDoc(`/api/dp/employees/${emp}/modelo/${encodeURIComponent(codigo)}?${qs.toString()}`);
}

// ── Editor de modelo ─────────────────────────────────────────
async function _mdEditar(codigo) {
  let m;
  if (codigo) {
    try { m = await apiFetch(`/api/dp/modelos-documentos/${encodeURIComponent(codigo)}`); }
    catch (e) { showToast(e.message, 'error'); return; }
  } else {
    let vars = {};
    try { vars = (await apiFetch('/api/dp/modelos-documentos/carta_recomendacao')).variaveis; } catch { /* lista vazia */ }
    m = { codigo: null, titulo: '', proprio: true, personalizado: false, variaveis: vars, calculadas: [],
          texto: '# Título do documento\n\nEu, **{{empregado.nome}}**, CPF {{empregado.cpf}}, declaro que ...\n\n{{local_data}}.\n\n[[assinaturas: empregado, empregador]]' };
  }
  const vars = Object.entries(m.variaveis || {});
  const calc = m.calculadas || [];
  const chip = (k, t) => `<button type="button" onclick="_mdInserir('{{${k}}}')" title="${_dpEsc(t)}"
      class="text-left w-full text-[11px] px-2 py-1 rounded hover:bg-violet-50 dark:hover:bg-slate-800">
      <code class="text-violet-700 dark:text-violet-300">{{${_dpEsc(k)}}}</code><br><span class="text-slate-400">${_dpEsc(t)}</span></button>`;
  const acaoExtra = m.codigo && m.personalizado
    ? `<button onclick="_mdRestaurar('${m.codigo}', ${m.proprio})" class="text-xs px-4 py-2 rounded-lg border border-rose-200 text-rose-600 hover:bg-rose-50">
         ${m.proprio ? 'Excluir modelo' : 'Voltar ao texto padrão'}</button>` : '<span></span>';
  _dpxModal('md-modal-editar', m.codigo ? `Editar modelo — ${_dpEsc(m.titulo)}` : 'Novo modelo de documento', `
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="lg:col-span-2 flex flex-col gap-3">
        <div>${labelCls('Título')}<input id="md-ed-titulo" value="${_dpEsc(m.titulo)}" maxlength="120" class="${inputCls()}"></div>
        <div>${labelCls('Texto')}<textarea id="md-ed-texto" rows="22" spellcheck="true"
          class="${inputCls()} font-mono text-xs leading-relaxed">${_dpEsc(m.texto)}</textarea></div>
        <div class="text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 leading-relaxed">
          <b>Como escrever:</b> <code># Título</code> · <code>## Cláusula</code> · <code>**negrito**</code> ·
          <code>- item de lista</code> · linha em branco separa parágrafos.<br>
          Blocos: <code>[[assinaturas: empregador, empregado, testemunhas, recebido]]</code>,
          <code>[[dependentes_salario_familia]]</code>, <code>[[dependentes_ir]]</code>, <code>[[vale_transporte]]</code>.
          ${m.base_legal ? `<br><b>Base legal do modelo:</b> ${_dpEsc(m.base_legal)}` : ''}
        </div>
      </div>
      <div class="flex flex-col gap-2">
        <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600">Clique para inserir</div>
        <div class="border border-slate-200 dark:border-slate-700 rounded-lg max-h-[520px] overflow-y-auto p-1">
          ${calc.length ? `<div class="text-[10px] font-semibold text-slate-500 px-2 pt-1">Deste modelo</div>${calc.map(k => chip(k, 'campo do modelo')).join('')}
            <div class="text-[10px] font-semibold text-slate-500 px-2 pt-2">Cadastro</div>` : ''}
          ${vars.map(([k, t]) => chip(k, t)).join('')}
        </div>
      </div>
    </div>
    <div class="flex flex-wrap justify-between gap-2 mt-5">
      ${acaoExtra}
      <div class="flex gap-2">
        <button onclick="_mdPrevia('${m.codigo || '_novo'}')" class="text-xs px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 flex items-center gap-1.5">
          <i data-lucide="eye" class="w-3.5 h-3.5"></i> Prévia com o funcionário selecionado</button>
        <button onclick="_mdSalvar(${m.codigo ? `'${m.codigo}'` : 'null'})" class="text-xs px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white flex items-center gap-1.5">
          <i data-lucide="save" class="w-3.5 h-3.5"></i> Salvar</button>
      </div>
    </div>`, 'max-w-6xl');
}

function _mdInserir(trecho) {
  const ta = document.getElementById('md-ed-texto');
  if (!ta) return;
  const ini = ta.selectionStart ?? ta.value.length, fim = ta.selectionEnd ?? ta.value.length;
  ta.value = ta.value.slice(0, ini) + trecho + ta.value.slice(fim);
  ta.focus();
  ta.selectionStart = ta.selectionEnd = ini + trecho.length;
}

async function _mdPrevia(codigo) {
  const emp = _mdEmpId();
  if (!emp) return;
  const w = window.open('', '_blank');
  if (w) w.document.write('<p style="font-family:Arial;padding:24px;color:#555">Gerando prévia…</p>');
  try {
    const r = await fetch(`/api/dp/modelos-documentos/${encodeURIComponent(codigo)}/previa`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ employee_id: Number(emp), texto: document.getElementById('md-ed-texto').value,
                             titulo: document.getElementById('md-ed-titulo').value }) });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      if (w) w.close();
      alert(typeof e.detail === 'string' ? e.detail : `Erro na prévia (${r.status}).`);
      return;
    }
    const html = await r.text();
    if (!w) { alert('Permita pop-ups deste site para ver a prévia.'); return; }
    w.document.open(); w.document.write(html); w.document.close();
  } catch {
    if (w) w.close();
    alert('Erro de conexão ao gerar a prévia.');
  }
}

async function _mdSalvar(codigo) {
  const body = { titulo: document.getElementById('md-ed-titulo').value.trim(),
                 texto: document.getElementById('md-ed-texto').value };
  try {
    if (codigo) await apiFetch(`/api/dp/modelos-documentos/${encodeURIComponent(codigo)}`, { method: 'PUT', body: JSON.stringify(body) });
    else await _dpxPost('/api/dp/modelos-documentos', body);
    document.getElementById('md-modal-editar')?.remove();
    showToast('Modelo salvo.', 'success');
    await renderModelosDocumentos(document.getElementById('dp-modelos-box'));
  } catch (e) { showToast(e.message, 'error'); }
}

async function _mdRestaurar(codigo, proprio) {
  if (!confirm(proprio ? 'Excluir este modelo próprio?' : 'Descartar a personalização e voltar ao texto padrão?')) return;
  try {
    await apiFetch(`/api/dp/modelos-documentos/${encodeURIComponent(codigo)}`, { method: 'DELETE' });
    document.getElementById('md-modal-editar')?.remove();
    showToast(proprio ? 'Modelo excluído.' : 'Texto padrão restaurado.', 'success');
    await renderModelosDocumentos(document.getElementById('dp-modelos-box'));
  } catch (e) { showToast(e.message, 'error'); }
}
