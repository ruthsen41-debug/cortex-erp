// ============================================================
// DEPARTAMENTO PESSOAL — Envio de holerites por e-mail
// Usa os helpers de dp.js e dp_folha_extra.js: authHeaders, fBRL2, card2, inputCls, labelCls,
// _dpEsc, _dpxModal, _dpxPost, apiFetch.
// ============================================================

const DPE_STATUS = {
  enviado: ['Enviado', 'bg-emerald-100 text-emerald-700'],
  erro: ['Falhou', 'bg-rose-100 text-rose-700'],
  sem_email: ['Sem e-mail', 'bg-slate-100 text-slate-500'],
};

// ── Configuração (aba Parâmetros) ────────────────────────────
async function renderEmailConfig(box) {
  if (!box) return;
  let c;
  try { c = await apiFetch('/api/dp/email-config'); }
  catch (e) { box.innerHTML = `<div class="text-xs text-rose-500">${_dpEsc(e.message)}</div>`; return; }
  const origem = { empresa: 'Servidor próprio da empresa', sistema: 'Servidor do sistema (padrão)', nenhuma: 'Nenhum servidor configurado' }[c.origem];
  const v = c.origem === 'empresa' ? c : { host: '', porta: 587, seguranca: 'starttls', usuario: '', remetente: '', nome_remetente: '' };
  box.innerHTML = card2(`<div class="px-5 py-4">
    <div class="flex flex-wrap items-center justify-between gap-2 mb-1">
      <div class="text-[11px] font-bold uppercase tracking-wide text-violet-600">E-mail para envio de holerites</div>
      <span class="text-[11px] px-2 py-0.5 rounded-full ${c.origem === 'nenhuma' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}">${origem}</span>
    </div>
    <p class="text-[11px] text-slate-400 mb-3">Dados do servidor de saída (SMTP) do e-mail da empresa. No Gmail e no Outlook use uma
      "senha de app". A senha é guardada cifrada e nunca aparece de volta na tela; deixe em branco para manter a atual.</p>
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
      <div class="md:col-span-2">${labelCls('Servidor (SMTP)')}<input id="dpe-host" value="${_dpEsc(v.host)}" placeholder="smtp.gmail.com" class="${inputCls()}"></div>
      <div>${labelCls('Porta')}<input id="dpe-porta" type="number" value="${v.porta}" class="${inputCls()}"></div>
      <div>${labelCls('Segurança')}<select id="dpe-seg" class="${inputCls()}">
        ${[['starttls', 'STARTTLS (587)'], ['ssl', 'SSL (465)'], ['nenhuma', 'Nenhuma']].map(([k, t]) =>
          `<option value="${k}" ${v.seguranca === k ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
      <div>${labelCls('Usuário')}<input id="dpe-user" value="${_dpEsc(v.usuario)}" autocomplete="off" class="${inputCls()}"></div>
      <div>${labelCls(c.origem === 'empresa' && c.tem_senha ? 'Senha (gravada)' : 'Senha')}<input id="dpe-senha" type="password" autocomplete="new-password" placeholder="${c.origem === 'empresa' && c.tem_senha ? '••••••••' : ''}" class="${inputCls()}"></div>
      <div>${labelCls('E-mail do remetente')}<input id="dpe-rem" value="${_dpEsc(v.remetente)}" placeholder="rh@empresa.com.br" class="${inputCls()}"></div>
      <div>${labelCls('Nome do remetente')}<input id="dpe-nome" value="${_dpEsc(v.nome_remetente)}" placeholder="RH Empresa" class="${inputCls()}"></div>
    </div>
    <div class="grid grid-cols-1 gap-3 mb-3">
      <div>${labelCls('Assunto')}<input id="dpe-assunto" value="${_dpEsc(c.assunto)}" class="${inputCls()}"></div>
      <div>${labelCls('Texto do e-mail')}<textarea id="dpe-corpo" rows="6" class="${inputCls()}">${_dpEsc(c.corpo)}</textarea>
        <div class="text-[11px] text-slate-400 mt-1">Campos: {nome} (primeiro nome), {competencia}, {empresa}, {liquido}.</div></div>
    </div>
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div class="flex items-end gap-2">
        <div>${labelCls('Enviar teste para')}<input id="dpe-teste" type="email" placeholder="seu@email.com" class="${inputCls()}"></div>
        <button onclick="_dpeTestar()" class="text-xs px-3 py-2 rounded-xl border border-violet-200 text-violet-700 bg-violet-50 hover:bg-violet-100">Enviar teste</button>
      </div>
      <button onclick="_dpeSalvar()" class="bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-4 py-2 rounded-xl">Salvar e-mail</button>
    </div>
    <div id="dpe-msg" class="text-xs mt-3"></div>
  </div>`);
}

async function _dpeSalvar() {
  const v = id => document.getElementById(id).value;
  const body = { host: v('dpe-host'), porta: Number(v('dpe-porta')) || 587, seguranca: v('dpe-seg'), usuario: v('dpe-user'),
                 senha: v('dpe-senha'), remetente: v('dpe-rem'), nome_remetente: v('dpe-nome'),
                 assunto: v('dpe-assunto'), corpo: v('dpe-corpo') };
  const msg = document.getElementById('dpe-msg');
  try {
    const r = await fetch('/api/dp/email-config', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
                                                    body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Erro ao salvar.');
    await renderEmailConfig(document.getElementById('par-email'));
    document.getElementById('dpe-msg').innerHTML = '<span class="text-emerald-600 font-semibold">Configuração de e-mail salva.</span>';
  } catch (e) { msg.innerHTML = `<span class="text-rose-500">${_dpEsc(e.message)}</span>`; }
}

async function _dpeTestar() {
  const msg = document.getElementById('dpe-msg');
  msg.innerHTML = '<span class="text-slate-400">Enviando... (salve antes se alterou algo)</span>';
  try {
    await _dpxPost('/api/dp/email-config/teste', { para: document.getElementById('dpe-teste').value });
    msg.innerHTML = '<span class="text-emerald-600 font-semibold">E-mail de teste enviado. Confira a caixa de entrada (e o spam).</span>';
  } catch (e) { msg.innerHTML = `<span class="text-rose-500">${_dpEsc(e.message)}</span>`; }
}

// ── Envio (tela da folha) ────────────────────────────────────
async function abrirEnvioHolerites(runId) {
  const modal = _dpxModal('dpe-envio', 'Enviar holerites por e-mail', '<div class="text-xs text-slate-400">Carregando...</div>', 'max-w-4xl');
  let d;
  try { d = await apiFetch(`/api/dp/payroll/${runId}/holerites/envios`); }
  catch (e) { modal.querySelector('.p-6').innerHTML = `<div class="text-xs text-rose-500">${_dpEsc(e.message)}</div>`; return; }
  const semServidor = d.smtp_origem === 'nenhuma';
  const linhas = d.funcionarios.map(f => {
    const [rot, cls] = DPE_STATUS[f.status] || ['Não enviado', 'bg-slate-50 text-slate-400'];
    return `<tr class="border-b border-slate-100 dark:border-slate-800 text-xs">
      <td class="px-2 py-1.5"><input type="checkbox" class="dpe-emp" value="${f.employee_id}" ${f.email_valido && f.status !== 'enviado' ? 'checked' : ''} ${f.email_valido ? '' : 'disabled'}></td>
      <td class="px-2 py-1.5">${_dpEsc(f.employee_name)}</td>
      <td class="px-2 py-1.5 ${f.email_valido ? '' : 'text-rose-500'}">${_dpEsc(f.email || 'sem e-mail no cadastro')}</td>
      <td class="px-2 py-1.5 text-right">${fBRL2(f.liquido)}</td>
      <td class="px-2 py-1.5"><span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${cls}" title="${_dpEsc(f.erro)}">${rot}</span>
        ${f.enviado_em ? `<span class="text-[10px] text-slate-400 ml-1">${_dpEsc(f.enviado_em.replace('T', ' ').slice(0, 16))}</span>` : ''}</td></tr>`;
  }).join('');
  modal.querySelector('.p-6').innerHTML = `
    ${semServidor ? `<div class="text-xs text-amber-700 bg-amber-50 rounded-xl px-3 py-2 mb-3">Nenhum servidor de e-mail configurado.
      Configure em <b>DP › Parâmetros › E-mail para envio de holerites</b>.</div>`
      : `<p class="text-xs text-slate-500 mb-3">Competência ${_dpEsc(d.competencia)} · remetente <b>${_dpEsc(d.remetente)}</b>.
        Cada funcionário recebe só o próprio holerite, em anexo. Já marcados: quem tem e-mail e ainda não recebeu.</p>`}
    <table class="w-full mb-4"><thead><tr class="text-[10px] text-slate-400 uppercase border-b">
      <th class="px-2 py-1 text-left"><input type="checkbox" onchange="document.querySelectorAll('.dpe-emp:not(:disabled)').forEach(c => c.checked = this.checked)"></th>
      <th class="px-2 py-1 text-left">Funcionário</th><th class="px-2 py-1 text-left">E-mail</th>
      <th class="px-2 py-1 text-right">Líquido</th><th class="px-2 py-1 text-left">Situação</th></tr></thead>
      <tbody>${linhas}</tbody></table>
    <div class="flex justify-end">
      <button onclick="_dpeEnviar(${runId})" ${semServidor ? 'disabled' : ''}
        class="text-xs px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-40 text-white font-semibold flex items-center gap-1.5">
        <i data-lucide="mail" class="w-3.5 h-3.5"></i> Enviar selecionados</button>
    </div>
    <div id="dpe-res" class="mt-4"></div>`;
  if (window.lucide) lucide.createIcons();
}

async function _dpeEnviar(runId) {
  const ids = [...document.querySelectorAll('.dpe-emp:checked')].map(c => Number(c.value));
  const res = document.getElementById('dpe-res');
  if (!ids.length) { res.innerHTML = '<div class="text-xs text-rose-500">Selecione ao menos um funcionário.</div>'; return; }
  if (!confirm(`Enviar ${ids.length} holerite(s) por e-mail?`)) return;
  res.innerHTML = '<div class="text-xs text-slate-400">Enviando...</div>';
  try {
    const d = await _dpxPost(`/api/dp/payroll/${runId}/holerites/email`, { employee_ids: ids });
    const falhas = d.resultado.filter(r => r.status !== 'enviado')
      .map(r => `<li>${_dpEsc(r.employee_name)}: ${_dpEsc(r.erro)}</li>`).join('');
    await abrirEnvioHolerites(runId);
    document.getElementById('dpe-res').innerHTML = `
      <div class="text-xs text-emerald-700 bg-emerald-50 rounded-xl px-3 py-2 mb-2">${d.enviados} holerite(s) enviado(s).</div>
      ${falhas ? `<div class="text-xs text-rose-700 bg-rose-50 rounded-xl px-3 py-2"><b>${d.falhas} falha(s):</b><ul class="list-disc ml-5 mt-1">${falhas}</ul></div>` : ''}`;
  } catch (e) { res.innerHTML = `<div class="text-xs text-rose-500">${_dpEsc(e.message)}</div>`; }
}
