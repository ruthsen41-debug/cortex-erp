// Painel do Sistema (super administrador / dono do Cortex) e Suporte (lado do cliente).
// Empresas clientes, logins, tabelas legais globais, catálogo global de rubricas e solicitações.
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const brl = (v) => Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const toast = (m, t) => (typeof showToast === 'function' ? showToast(m, t) : alert(m));

  async function api(url, opts) {
    const o = Object.assign({ headers: {} }, opts || {});
    if (o.body && typeof o.body !== 'string') {
      o.body = JSON.stringify(o.body);
      o.headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(url, o);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || ('Erro ' + res.status));
    return data;
  }

  const STATUS_BADGE = {
    ativa: ['badge-success', 'Ativa'], pendente: ['badge-warning', 'Pendente'], bloqueada: ['badge-danger', 'Bloqueada'],
    aberto: ['badge-warning', 'Aberto'], em_andamento: ['badge-info', 'Em andamento'], concluido: ['badge-success', 'Concluído'],
  };
  const badge = (s) => { const b = STATUS_BADGE[s] || ['badge-secondary', s]; return `<span class="badge ${b[0]}">${esc(b[1])}</span>`; };
  const fmtDate = (s) => (s ? String(s).slice(0, 16).replace('T', ' ') : '—');

  const TIPOS_TABELA = {
    inss: 'INSS (progressivo)', irrf: 'IRRF (mensal)', fgts: 'FGTS', salario_minimo: 'Salário mínimo',
    irrf_dependente: 'Dedução por dependente (IRRF)', irrf_simplificado: 'Desconto simplificado (IRRF)',
    salario_familia: 'Salário-família',
  };
  const CATEGORIAS = { tabelas: 'Tabelas legais', rubricas: 'Rubricas', acesso: 'Acesso / logins', erro: 'Erro no sistema', melhoria: 'Sugestão de melhoria', outro: 'Outro' };

  // Modal simples próprio (não depende do modal global do app).
  function modal(title, body, onSave, saveLabel) {
    const wrap = document.createElement('div');
    wrap.className = 'modal-overlay';
    wrap.innerHTML = `<div class="modal-box" style="max-width:640px">
      <h3>${esc(title)}</h3><div class="sa-modal-body">${body}</div>
      <div class="alert alert-danger sa-modal-err" style="display:none;margin-top:.75rem"></div>
      <div class="btn-group" style="justify-content:flex-end;margin-top:1rem">
        <button class="btn btn-secondary" data-act="cancel">Cancelar</button>
        ${onSave ? `<button class="btn btn-primary" data-act="save">${esc(saveLabel || 'Salvar')}</button>` : ''}
      </div></div>`;
    document.body.appendChild(wrap);
    const close = () => wrap.remove();
    wrap.querySelector('[data-act="cancel"]').onclick = close;
    wrap.addEventListener('click', (e) => { if (e.target === wrap) close(); });
    const save = wrap.querySelector('[data-act="save"]');
    if (save) save.onclick = async () => {
      const err = wrap.querySelector('.sa-modal-err');
      err.style.display = 'none';
      save.disabled = true;
      try { await onSave(wrap); close(); }
      catch (e) { err.textContent = e.message; err.style.display = 'block'; }
      finally { save.disabled = false; }
    };
    if (window.lucide) lucide.createIcons();
    return wrap;
  }

  // ── PAINEL DO SISTEMA ─────────────────────────────────────────────────────
  let saTab = 'overview';
  const TABS = [
    ['overview', 'Visão geral'], ['companies', 'Empresas clientes'], ['tables', 'Tabelas legais'],
    ['rubrics', 'Rubricas globais'], ['support', 'Solicitações'], ['updates', 'Atualizações'],
  ];

  window.renderSuperadmin = async function (container) {
    container.innerHTML = `
      <div class="page-header">
        <div>
          <h2>Painel do Sistema</h2>
          <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">
            Área do dono do Cortex: libera clientes, mantém tabelas e rubricas de todos e atende o suporte.
          </p>
        </div>
      </div>
      <div class="tabs" style="overflow-x:auto">
        ${TABS.map(([id, l]) => `<button class="tab-btn${saTab === id ? ' active' : ''}" onclick="saSwitch('${id}')">${l}</button>`).join('')}
      </div>
      <div id="sa-body"><div class="text-muted" style="padding:1rem">Carregando...</div></div>`;
    await loadTab();
  };

  window.saSwitch = function (id) {
    saTab = id;
    const main = document.getElementById('main-content');
    if (main) window.renderSuperadmin(main);
  };

  async function loadTab() {
    const body = document.getElementById('sa-body');
    if (!body) return;
    try {
      if (saTab === 'overview') await renderOverview(body);
      else if (saTab === 'companies') await renderCompanies(body);
      else if (saTab === 'tables') await renderTables(body);
      else if (saTab === 'rubrics') await renderRubrics(body);
      else if (saTab === 'support') await renderSupportQueue(body);
      else if (saTab === 'updates') await renderUpdates(body);
    } catch (e) {
      body.innerHTML = `<div class="alert alert-danger">${esc(e.message)}</div>`;
    }
    if (window.lucide) lucide.createIcons();
  }

  // ── ATUALIZAÇÕES ("Verificar atualizações", como no celular) ────────────────
  const FASES = {
    baixando: 'Baixando', verificando: 'Conferindo o arquivo', agendada: 'Iniciando a instalação',
    preparando: 'Backup e cópia de segurança', instalando: 'Instalando', conferindo: 'Conferindo a versão nova',
    revertendo: 'Voltando a versão anterior', concluida: 'Concluída', revertida: 'Revertida', erro: 'Não concluída',
  };
  let updTimer = null;
  let updVerificacao = null;
  let updBody = null;

  function fmtBytes(n) { return n ? (n / 1048576).toFixed(0) + ' MB' : ''; }
  function updAgendar(body, ms) {
    clearTimeout(updTimer);
    updTimer = setTimeout(() => { if (body.isConnected) renderUpdates(body); }, ms);
  }

  async function renderUpdates(body) {
    clearTimeout(updTimer);
    updBody = body;
    let st;
    try {
      st = await api('/api/system/update/status');
    } catch (e) {
      // durante a instalação o servidor fica fora do ar por alguns instantes
      body.innerHTML = `<div class="card"><div class="card-body" style="display:flex;gap:.75rem;align-items:center">
        <i data-lucide="loader" class="sa-gira"></i><div><strong>O servidor está reiniciando com a versão nova…</strong>
        <div class="text-muted" style="font-size:.85rem">Esta tela continua sozinha quando ele voltar.</div></div></div></div>`;
      if (window.lucide) lucide.createIcons();
      updAgendar(body, 4000);
      return;
    }
    const v = updVerificacao || st.verificacao;
    const and = st.andamento;
    const disp = v && v.ok ? v.disponivel : null;
    const nuvem = st.modo !== 'instalado';
    const cv = window.cortexVersao || {};
    // nuvem: "nova" = o que está no ar é diferente do que está aberto neste navegador
    const nova = !!disp && (nuvem ? !!(disp.build && cv.buildAberto && disp.build !== cv.buildAberto) : !!disp.nova);
    const paginaVelha = !!(window.cortexVersao && window.cortexVersao.versaoAberta && window.cortexVersao.versaoAberta !== st.versao_atual);

    let andamentoHtml = '';
    if (and && and.fase) {
      const ativo = st.em_andamento;
      const ok = and.fase === 'concluida';
      const cls = ativo ? 'alert-info' : ok ? 'alert-success' : and.fase === 'revertida' ? 'alert-warning' : 'alert-danger';
      const pct = typeof and.progresso === 'number' ? and.progresso : null;
      andamentoHtml = `<div class="alert ${cls}" style="margin-bottom:1rem">
        <div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap">
          <strong>${ativo ? '<i data-lucide="loader" class="sa-gira" style="width:16px;height:16px;vertical-align:-3px"></i> ' : ''}${esc(FASES[and.fase] || and.fase)}
            ${and.versao_destino ? '— versão ' + esc(and.versao_destino) : ''}</strong>
          <span style="font-size:.8rem;opacity:.8">${esc(fmtDate(and.concluido_em || and.atualizado_em))}${and.origem === 'automatica' ? ' · automática' : ''}</span>
        </div>
        <div style="margin-top:.35rem">${esc(and.mensagem || '')}</div>
        ${ativo && pct !== null ? `<div style="height:6px;border-radius:99px;background:rgba(127,127,127,.25);margin-top:.6rem;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,#6366f1,#22d3ee);transition:width .4s"></div></div>` : ''}
        ${and.erro && !ativo ? `<details style="margin-top:.5rem;font-size:.8rem"><summary>Detalhe técnico</summary>${esc(and.erro)}</details>` : ''}
        ${ok && paginaVelha ? `<div style="margin-top:.6rem"><button class="btn btn-sm btn-primary" onclick="cortexVersao.atualizar()">Recarregar o sistema na versão nova</button></div>` : ''}
      </div>`;
    }

    let dispHtml;
    if (!v) {
      dispHtml = `<p class="text-muted" style="margin:0">Clique em <strong>Verificar atualizações</strong> para procurar uma versão nova.</p>`;
    } else if (!v.ok) {
      dispHtml = `<div class="alert alert-warning" style="margin:0">${esc(v.erro)}</div>`;
    } else if (nova && nuvem) {
      dispHtml = `<div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap">
          <div><div style="font-size:1.1rem;font-weight:700">Nova versão disponível${disp.versao ? ' (' + esc(disp.versao) + ')' : ''}</div>
            <div class="text-muted" style="font-size:.8rem">Salve o que estiver fazendo: a página recarrega já na versão nova.</div></div>
          <button class="btn btn-primary" onclick="cortexVersao.atualizar()">
            <i data-lucide="download" style="width:16px;height:16px"></i> Atualizar agora</button>
        </div>`;
    } else if (nova) {
      const botao = st.modo === 'instalado'
        ? `<button class="btn btn-primary" data-versao="${esc(disp.versao)}" onclick="saAplicarAtualizacao(this.dataset.versao)" ${st.em_andamento ? 'disabled' : ''}>
            <i data-lucide="download" style="width:16px;height:16px"></i> Baixar e instalar</button>`
        : '';
      dispHtml = `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap">
          <div><div style="font-size:1.1rem;font-weight:700">Versão ${esc(disp.versao)} disponível</div>
            <div class="text-muted" style="font-size:.8rem">${disp.publicada_em ? 'Publicada em ' + esc(fmtDate(disp.publicada_em)) : ''} ${disp.tamanho ? '· ' + fmtBytes(disp.tamanho) : ''}</div></div>
          ${botao}
        </div>
        ${disp.notas ? `<div style="margin-top:.75rem"><div style="font-weight:600;font-size:.85rem;margin-bottom:.25rem">O que mudou</div>
          <div style="white-space:pre-line;font-size:.875rem;color:var(--text-2)">${esc(disp.notas)}</div></div>` : ''}
        ${st.modo === 'instalado' ? `<p class="text-muted" style="font-size:.8rem;margin:.75rem 0 0">Antes de instalar, o Cortex faz backup do banco e guarda uma cópia da versão atual.
          O sistema fica fora do ar por 1 a 3 minutos. Se a versão nova não subir, ele volta sozinho para a anterior.</p>` : ''}`;
    } else {
      dispHtml = `<div style="display:flex;gap:.6rem;align-items:center"><i data-lucide="check-circle-2" style="color:#22c55e"></i>
        <div><strong>Você está na versão mais recente.</strong><div class="text-muted" style="font-size:.8rem">${nuvem ? 'Versão no ar' : 'Última versão publicada'}: ${esc(disp ? disp.versao : '—')} · verificado em ${esc(fmtDate(v.em))}</div></div></div>`;
    }

    const auto = st.auto || {};
    const autoHtml = st.modo === 'instalado'
      ? `<div class="card"><div class="card-body">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap">
          <label style="display:flex;gap:.6rem;align-items:center;margin:0;cursor:pointer">
            <input type="checkbox" id="sa-upd-auto" ${auto.auto ? 'checked' : ''} onchange="saSalvarAuto()">
            <span><strong>Atualizar automaticamente de madrugada</strong><br>
            <span class="text-muted" style="font-size:.8rem">Quando sair versão nova, o servidor instala sozinho no horário escolhido.</span></span>
          </label>
          <div style="display:flex;gap:.5rem;align-items:center"><span class="text-muted" style="font-size:.85rem">Horário</span>
            <input type="time" class="form-control" id="sa-upd-hora" value="${esc(auto.hora || '03:00')}" style="width:120px" onchange="saSalvarAuto()"></div>
        </div></div></div>`
      : `<div class="alert alert-info">Na nuvem a atualização é automática: cada versão publicada entra no ar sozinha,
        e quem estiver com o sistema aberto vê o aviso <strong>"Nova versão disponível"</strong>.</div>`;

    body.innerHTML = `
      <style>@keyframes sa-gira{to{transform:rotate(360deg)}}.sa-gira{animation:sa-gira 1s linear infinite}</style>
      ${andamentoHtml}
      <div class="card" style="margin-bottom:1rem"><div class="card-body">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:1rem">
          <div><div class="text-muted" style="font-size:.8rem">${nuvem ? 'Versão em uso' : 'Versão instalada'}</div>
            <div style="font-size:1.6rem;font-weight:800;line-height:1.1">${esc(nuvem ? (cv.versaoAberta || st.versao_atual) : st.versao_atual)}</div>
            <div class="text-muted" style="font-size:.75rem">build ${esc(nuvem ? (cv.buildAberto || st.build) : st.build)} · ${nuvem ? 'nuvem' : 'servidor instalado'}</div></div>
          <button class="btn btn-secondary" id="sa-upd-check" onclick="saVerificarAtualizacao()" ${st.em_andamento ? 'disabled' : ''}>
            <i data-lucide="refresh-cw" style="width:16px;height:16px"></i> Verificar atualizações</button>
        </div>
        ${dispHtml}
      </div></div>
      ${autoHtml}`;
    if (window.lucide) lucide.createIcons();
    if (st.em_andamento) updAgendar(body, 2500);
  }

  window.saVerificarAtualizacao = async function () {
    const bt = document.getElementById('sa-upd-check');
    if (bt) { bt.disabled = true; bt.textContent = 'Verificando…'; }
    try {
      updVerificacao = await api('/api/system/update/check', { method: 'POST' });
    } catch (e) { toast(e.message, 'error'); }
    if (updBody && updBody.isConnected) renderUpdates(updBody);
  };

  window.saAplicarAtualizacao = async function (versao) {
    if (!confirm(`Instalar a versão ${versao} agora?\n\nO sistema fica fora do ar por 1 a 3 minutos para todos os usuários. ` +
      'Peça para salvarem o que estiverem fazendo. Antes de instalar é feito backup do banco.')) return;
    try {
      await api('/api/system/update/apply', { method: 'POST' });
      toast('Atualização iniciada.', 'success');
    } catch (e) { toast(e.message, 'error'); }
    if (updBody && updBody.isConnected) renderUpdates(updBody);
  };

  window.saSalvarAuto = async function () {
    const ativo = document.getElementById('sa-upd-auto').checked;
    const hora = document.getElementById('sa-upd-hora').value || '03:00';
    try {
      await api('/api/system/update/auto', { method: 'PUT', body: { ativo, hora } });
      toast(ativo ? `Atualização automática ligada (${hora}).` : 'Atualização automática desligada.', 'success');
    } catch (e) { toast(e.message, 'error'); }
  };

  // Mesma tela, fora do Painel do Sistema: menu Administração › Atualizações (admin da empresa)
  window.renderAtualizacoes = async function (container) {
    container.innerHTML = `
      <div class="page-header"><div>
        <h2>Atualizações</h2>
        <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">Como no celular: verifique se há versão nova do Cortex e atualize com um clique.</p>
      </div></div>
      <div id="upd-body"><div class="text-muted" style="padding:1rem">Carregando...</div></div>`;
    const body = container.querySelector('#upd-body');
    try { await renderUpdates(body); }
    catch (e) { body.innerHTML = `<div class="alert alert-danger">${esc(e.message)}</div>`; }
  };

  async function renderOverview(body) {
    const d = await api('/api/superadmin/overview');
    const kpi = (v, l, tab) => `<div class="kpi-card" ${tab ? `style="cursor:pointer" onclick="saSwitch('${tab}')"` : ''}>
      <div class="kpi-value">${esc(v)}</div><div class="kpi-label">${esc(l)}</div></div>`;
    body.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.75rem;margin-bottom:1.25rem">
        ${kpi(d.empresas.pendente, 'Aguardando aprovação', 'companies')}
        ${kpi(d.empresas.ativa, 'Empresas ativas', 'companies')}
        ${kpi(d.empresas.bloqueada, 'Bloqueadas', 'companies')}
        ${kpi(d.usuarios_ativos, 'Logins ativos')}
        ${kpi(d.funcionarios_ativos, 'Funcionários (todas)')}
        ${kpi(d.suporte_aberto, 'Suporte em aberto', 'support')}
      </div>
      ${d.tabelas_faltando.length ? `<div class="alert alert-warning">
        <strong>Tabelas legais ${d.ano}:</strong> sem tabela global para ${d.tabelas_faltando.map((t) => TIPOS_TABELA[t] || t).join(', ')}.
        O motor está usando as tabelas embutidas no código.
        <button class="btn btn-sm btn-secondary" style="margin-left:.5rem" onclick="saSwitch('tables')">Abrir tabelas</button></div>` : ''}
      ${!d.rubricas_globais ? `<div class="alert alert-info">O catálogo global de rubricas está vazio.
        <button class="btn btn-sm btn-secondary" style="margin-left:.5rem" onclick="saSwitch('rubrics')">Abrir rubricas</button></div>` : ''}
      <div class="card"><div class="card-header"><strong>Cadastros aguardando aprovação</strong></div>
        <div class="card-body">
        ${d.pendentes.length ? `<div class="table-responsive"><table class="table"><thead><tr>
          <th>Empresa</th><th>CNPJ</th><th>E-mail</th><th>Cadastro</th><th></th></tr></thead><tbody>
          ${d.pendentes.map((c) => `<tr><td>${esc(c.razao_social)}</td><td>${esc(c.cnpj)}</td><td>${esc(c.email)}</td>
            <td>${fmtDate(c.created_at)}</td>
            <td style="white-space:nowrap"><button class="btn btn-sm btn-success" onclick="saApprove(${c.id})">Aprovar</button>
            <button class="btn btn-sm btn-danger" onclick="saBlock(${c.id})">Recusar</button></td></tr>`).join('')}
          </tbody></table></div>` : '<p class="text-muted" style="margin:0">Nenhum cadastro pendente.</p>'}
        </div></div>`;
  }

  // Empresas
  let companyFilter = '';
  async function renderCompanies(body) {
    const list = await api('/api/superadmin/companies' + (companyFilter ? '?status=' + companyFilter : ''));
    body.innerHTML = `
      <div class="btn-group" style="margin-bottom:.75rem">
        ${[['', 'Todas'], ['pendente', 'Pendentes'], ['ativa', 'Ativas'], ['bloqueada', 'Bloqueadas']].map(([v, l]) =>
          `<button class="btn btn-sm ${companyFilter === v ? 'btn-primary' : 'btn-secondary'}" onclick="saFilter('${v}')">${l}</button>`).join('')}
      </div>
      <div class="table-responsive"><table class="table"><thead><tr>
        <th>#</th><th>Empresa</th><th>Administrador</th><th>Logins</th><th>Funcionários</th><th>Plano</th><th>Status</th><th>Cadastro</th><th></th>
      </tr></thead><tbody>
      ${list.map((c) => `<tr>
        <td>${c.id}</td>
        <td><strong>${esc(c.nome_fantasia || c.razao_social)}</strong><div class="text-muted" style="font-size:.75rem">${esc(c.cnpj)} · ${esc(c.cidade || '')}/${esc(c.uf || '')}</div></td>
        <td>${esc(c.admin_email || c.email || '—')}</td>
        <td>${c.usuarios}</td><td>${c.funcionarios}</td><td>${esc(c.plano || '—')}</td>
        <td>${badge(c.status)}${c.bloqueio_motivo ? `<div class="text-muted" style="font-size:.72rem">${esc(c.bloqueio_motivo)}</div>` : ''}</td>
        <td>${fmtDate(c.created_at)}</td>
        <td style="white-space:nowrap">
          ${c.status === 'pendente' ? `<button class="btn btn-sm btn-success" onclick="saApprove(${c.id})">Aprovar</button>` : ''}
          ${c.status === 'bloqueada' ? `<button class="btn btn-sm btn-success" onclick="saReactivate(${c.id})">Reativar</button>` : ''}
          ${c.status !== 'bloqueada' ? `<button class="btn btn-sm btn-danger" onclick="saBlock(${c.id})">${c.status === 'pendente' ? 'Recusar' : 'Bloquear'}</button>` : ''}
          <button class="btn btn-sm btn-secondary" onclick="saCompanyDetail(${c.id})">Detalhes</button>
          ${c.status === 'ativa' ? `<button class="btn btn-sm btn-secondary" title="Entrar nesta empresa" onclick="saEnter(${c.id})">Acessar</button>` : ''}
        </td></tr>`).join('') || '<tr><td colspan="9" class="text-muted">Nenhuma empresa.</td></tr>'}
      </tbody></table></div>`;
  }

  window.saFilter = (v) => { companyFilter = v; loadTab(); };
  window.saApprove = async (id) => {
    try { await api(`/api/superadmin/companies/${id}/approve`, { method: 'POST' }); toast('Empresa aprovada. O cliente já pode entrar.', 'success'); loadTab(); }
    catch (e) { toast(e.message, 'error'); }
  };
  window.saReactivate = async (id) => {
    try { await api(`/api/superadmin/companies/${id}/reactivate`, { method: 'POST' }); toast('Empresa reativada.', 'success'); loadTab(); }
    catch (e) { toast(e.message, 'error'); }
  };
  window.saBlock = (id) => {
    modal('Bloquear acesso da empresa', `
      <p class="text-muted" style="font-size:.85rem">Todos os logins da empresa perdem o acesso na hora. Os dados são mantidos e você pode reativar depois.</p>
      <div class="form-group"><label>Motivo (aparece só para você)</label>
      <input class="form-control" id="sa-motivo" placeholder="Ex.: cadastro recusado, inadimplência..."></div>`,
    async (w) => {
      await api(`/api/superadmin/companies/${id}/block`, { method: 'POST', body: { motivo: w.querySelector('#sa-motivo').value } });
      toast('Acesso bloqueado.', 'success'); loadTab();
    }, 'Bloquear');
  };
  window.saEnter = async (id) => {
    try {
      const r = await api('/api/company/switch', { method: 'POST', body: { company_id: id } });
      if (r.access_token && typeof setToken === 'function') setToken(r.access_token);
      else if (r.access_token) localStorage.setItem('cortex_token', r.access_token);
      toast('Você entrou na empresa do cliente. Use o seletor de empresas para voltar.', 'info');
      setTimeout(() => window.location.reload(), 600);
    } catch (e) { toast(e.message, 'error'); }
  };

  window.saCompanyDetail = async (id) => {
    let c;
    try { c = await api(`/api/superadmin/companies/${id}`); } catch (e) { toast(e.message, 'error'); return; }
    modal(`${c.nome_fantasia || c.razao_social}`, `
      <div class="form-row">
        <div class="form-group"><label>Plano</label><input class="form-control" id="sa-plano" value="${esc(c.plano || '')}" placeholder="Ex.: Escritório 50 empresas"></div>
        <div class="form-group"><label>Status</label><div style="padding-top:.4rem">${badge(c.status || 'ativa')}</div></div>
      </div>
      <div class="form-group"><label>Observações internas</label>
        <textarea class="form-control" id="sa-obs" rows="2">${esc(c.observacao_admin || '')}</textarea></div>
      <div class="text-muted" style="font-size:.78rem;margin-bottom:.5rem">
        CNPJ ${esc(c.cnpj)} · ${esc(c.email || '')} · ${esc(c.telefone || '')} · aprovada em ${fmtDate(c.aprovado_em)}</div>
      <strong style="font-size:.85rem">Logins</strong>
      <div class="table-responsive"><table class="table table-sm"><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Status</th><th></th></tr></thead><tbody>
        ${c.users.map((u) => `<tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${esc(u.role)}</td>
          <td>${u.active ? badge('ativa') : '<span class="badge badge-secondary">Inativo</span>'}</td>
          <td style="white-space:nowrap">
            <button class="btn btn-sm btn-secondary" onclick="saUserToggle(${u.id}, ${u.active ? 0 : 1}, ${id})">${u.active ? 'Desativar' : 'Ativar'}</button>
            <button class="btn btn-sm btn-secondary" onclick="saUserPass(${u.id})">Nova senha</button></td></tr>`).join('') || '<tr><td colspan="5" class="text-muted">Sem logins.</td></tr>'}
      </tbody></table></div>`,
    async (w) => {
      await api(`/api/superadmin/companies/${id}`, { method: 'PUT', body: { plano: w.querySelector('#sa-plano').value, observacao_admin: w.querySelector('#sa-obs').value } });
      toast('Empresa atualizada.', 'success'); loadTab();
    });
  };
  window.saUserToggle = async (uid, active, companyId) => {
    try {
      await api(`/api/superadmin/users/${uid}`, { method: 'PUT', body: { active } });
      document.querySelectorAll('.modal-overlay').forEach((m) => m.remove());
      toast(active ? 'Login ativado.' : 'Login desativado.', 'success');
      window.saCompanyDetail(companyId);
    } catch (e) { toast(e.message, 'error'); }
  };
  window.saUserPass = (uid) => {
    modal('Definir nova senha', `<div class="form-group"><label>Nova senha (mín. 6 caracteres)</label>
      <input type="text" class="form-control" id="sa-newpass" autocomplete="off"></div>
      <p class="text-muted" style="font-size:.8rem">Informe a senha ao cliente por um canal seguro e peça para ele trocar depois.</p>`,
    async (w) => {
      await api(`/api/superadmin/users/${uid}`, { method: 'PUT', body: { password: w.querySelector('#sa-newpass').value } });
      toast('Senha redefinida.', 'success');
    });
  };

  // Tabelas legais globais
  let tableYear = new Date().getFullYear();
  async function renderTables(body) {
    const list = await api('/api/superadmin/tax-tables?ano=' + tableYear);
    const byTipo = {};
    list.forEach((t) => { byTipo[t.tipo] = t; });
    body.innerHTML = `
      <div class="alert alert-info">As tabelas publicadas aqui valem para o cálculo da folha de <strong>todos os clientes</strong>
        (têm prioridade sobre as embutidas no código). Os clientes só consultam; para mudar, eles abrem uma solicitação.</div>
      <div class="btn-group" style="margin-bottom:.75rem;align-items:center">
        <label style="font-size:.85rem">Ano</label>
        <input type="number" class="form-control" style="width:110px" value="${tableYear}" onchange="saYear(this.value)">
        <button class="btn btn-secondary" onclick="saSeedTables()">Importar tabelas embutidas de ${tableYear}</button>
      </div>
      <div class="table-responsive"><table class="table"><thead><tr><th>Tabela</th><th>Faixas / valor</th><th></th></tr></thead><tbody>
        ${Object.entries(TIPOS_TABELA).map(([tipo, label]) => {
          const t = byTipo[tipo];
          const faixas = t ? t.brackets.map((b) => (tipo === 'inss' || tipo === 'irrf')
            ? `até ${b.faixa_ate == null ? '∞' : brl(b.faixa_ate)} → ${brl(b.aliquota)}%${tipo === 'irrf' ? ` (ded. ${brl(b.deducao)})` : ''}`
            : (tipo === 'fgts' ? `${brl(b.aliquota)}%` : (tipo === 'salario_familia' ? `cota R$ ${brl(b.aliquota)} até R$ ${brl(b.faixa_ate)}` : `R$ ${brl(b.aliquota)}`))).join('<br>') : '';
          return `<tr><td><strong>${label}</strong></td>
            <td style="font-size:.8rem">${t ? faixas : '<span class="text-muted">Usando a tabela embutida no código</span>'}</td>
            <td style="white-space:nowrap"><button class="btn btn-sm btn-primary" onclick="saEditTable('${tipo}')">${t ? 'Editar' : 'Cadastrar'}</button>
            ${t ? `<button class="btn btn-sm btn-danger" onclick="saDelTable(${t.id})">Excluir</button>` : ''}</td></tr>`;
        }).join('')}
      </tbody></table></div>`;
    window._saTables = byTipo;
  }
  window.saYear = (v) => { tableYear = parseInt(v, 10) || tableYear; loadTab(); };
  window.saSeedTables = async () => {
    try { const r = await api(`/api/superadmin/tax-tables/seed-default?ano=${tableYear}`, { method: 'POST' }); toast(`${r.tabelas} tabela(s) importada(s).`, 'success'); loadTab(); }
    catch (e) { toast(e.message, 'error'); }
  };
  window.saDelTable = async (id) => {
    if (!confirm('Excluir esta tabela global? Os clientes voltam a usar a tabela embutida no código.')) return;
    try { await api(`/api/superadmin/tax-tables/${id}`, { method: 'DELETE' }); loadTab(); } catch (e) { toast(e.message, 'error'); }
  };
  window.saEditTable = (tipo) => {
    const t = (window._saTables || {})[tipo];
    const faixas = tipo === 'inss' || tipo === 'irrf';
    const rows = (t ? t.brackets : (faixas ? [{}] : [{}]));
    const rowHtml = (b) => `<tr>
      <td><input type="number" step="0.01" class="form-control sa-de" value="${b.faixa_de ?? ''}"></td>
      <td><input type="number" step="0.01" class="form-control sa-ate" value="${b.faixa_ate ?? ''}" placeholder="sem limite"></td>
      <td><input type="number" step="0.01" class="form-control sa-aliq" value="${b.aliquota ?? ''}"></td>
      ${tipo === 'irrf' ? `<td><input type="number" step="0.01" class="form-control sa-ded" value="${b.deducao ?? ''}"></td>` : ''}
      <td><button class="btn btn-sm btn-secondary" onclick="this.closest('tr').remove()">✕</button></td></tr>`;
    const valorLabel = { fgts: 'Alíquota (%)', salario_minimo: 'Valor (R$)', irrf_dependente: 'Valor por dependente (R$)', irrf_simplificado: 'Desconto (R$)', salario_familia: 'Valor da cota (R$)' }[tipo];
    const body = faixas ? `
      <p class="text-muted" style="font-size:.8rem">Uma linha por faixa. Deixe "Até" vazio na última faixa.</p>
      <table class="table table-sm"><thead><tr><th>De (R$)</th><th>Até (R$)</th><th>Alíquota (%)</th>${tipo === 'irrf' ? '<th>Dedução (R$)</th>' : ''}<th></th></tr></thead>
      <tbody id="sa-rows">${rows.map(rowHtml).join('')}</tbody></table>
      <button class="btn btn-sm btn-secondary" onclick="document.getElementById('sa-rows').insertAdjacentHTML('beforeend', window._saRowHtml())">+ Faixa</button>`
      : `<div class="form-row">
          <div class="form-group"><label>${valorLabel}</label><input type="number" step="0.01" class="form-control" id="sa-val" value="${t ? t.brackets[0].aliquota : ''}"></div>
          ${tipo === 'salario_familia' ? `<div class="form-group"><label>Remuneração limite (R$)</label><input type="number" step="0.01" class="form-control" id="sa-lim" value="${t ? (t.brackets[0].faixa_ate ?? '') : ''}"></div>` : ''}
        </div>`;
    window._saRowHtml = () => rowHtml({});
    modal(`${TIPOS_TABELA[tipo]} — ${tableYear}`, body, async (w) => {
      let brackets;
      if (faixas) {
        brackets = [...w.querySelectorAll('#sa-rows tr')].map((tr) => ({
          faixa_de: tr.querySelector('.sa-de').value || 0,
          faixa_ate: tr.querySelector('.sa-ate').value === '' ? null : tr.querySelector('.sa-ate').value,
          aliquota: tr.querySelector('.sa-aliq').value || 0,
          deducao: tr.querySelector('.sa-ded') ? (tr.querySelector('.sa-ded').value || 0) : 0,
        }));
      } else {
        const lim = w.querySelector('#sa-lim');
        brackets = [{ faixa_de: 0, faixa_ate: lim ? (lim.value || 0) : null, aliquota: w.querySelector('#sa-val').value || 0, deducao: 0 }];
      }
      await api('/api/superadmin/tax-tables', { method: 'POST', body: { ano: tableYear, tipo, brackets } });
      toast('Tabela publicada para todos os clientes.', 'success'); loadTab();
    }, 'Publicar');
  };

  // Rubricas globais
  async function renderRubrics(body) {
    const list = await api('/api/superadmin/rubrics');
    body.innerHTML = `
      <div class="alert alert-info">Catálogo de rubricas padrão do sistema. Ao <strong>publicar</strong>, as que faltam são criadas nas empresas ativas.
        As cópias publicadas ficam protegidas: o cliente não altera, mas pode criar rubricas próprias com outros códigos.</div>
      <div class="btn-group" style="margin-bottom:.75rem">
        <button class="btn btn-primary" onclick="saEditRubric()">+ Nova rubrica</button>
        <button class="btn btn-secondary" onclick="saImportRubrics()">Importar rubricas do motor de folha</button>
        <button class="btn btn-success" onclick="saPublish(false)">Publicar nas empresas</button>
        <button class="btn btn-secondary" onclick="saPublish(true)">Publicar e atualizar cópias</button>
      </div>
      <div class="table-responsive"><table class="table"><thead><tr>
        <th>Código</th><th>Nome</th><th>Tipo</th><th>INSS</th><th>IRRF</th><th>FGTS</th><th>Nat. eSocial</th><th>Fórmula</th><th>Empresas</th><th></th>
      </tr></thead><tbody>
      ${list.map((r) => `<tr${r.ativo ? '' : ' style="opacity:.55"'}>
        <td><strong>${esc(r.codigo)}</strong></td><td>${esc(r.nome)}</td><td>${esc(r.tipo)}</td>
        <td>${r.incide_inss ? '✓' : ''}</td><td>${r.incide_irrf ? '✓' : ''}</td><td>${r.incide_fgts ? '✓' : ''}</td>
        <td>${esc(r.esocial_nat_rubrica || '')}</td><td style="font-family:monospace;font-size:.75rem">${esc(r.formula || '')}</td>
        <td>${r.empresas}</td>
        <td style="white-space:nowrap"><button class="btn btn-sm btn-secondary" onclick='saEditRubric(${JSON.stringify(r).replace(/'/g, '&#39;')})'>Editar</button>
          <button class="btn btn-sm btn-danger" onclick="saDelRubric(${r.id})">Excluir</button></td></tr>`).join('')
        || '<tr><td colspan="10" class="text-muted">Catálogo vazio. Use "Importar rubricas do motor de folha" para começar.</td></tr>'}
      </tbody></table></div>`;
  }
  window.saImportRubrics = async () => {
    try { const r = await api('/api/superadmin/rubrics/import-system', { method: 'POST' }); toast(`${r.criadas} rubrica(s) importada(s).`, 'success'); loadTab(); }
    catch (e) { toast(e.message, 'error'); }
  };
  window.saPublish = async (atualizar) => {
    if (atualizar && !confirm('Atualizar também as cópias já publicadas nas empresas? Rubricas próprias dos clientes não são alteradas.')) return;
    try {
      const r = await api('/api/superadmin/rubrics/publish', { method: 'POST', body: { atualizar_existentes: atualizar } });
      toast(`${r.empresas} empresa(s): ${r.criadas} criada(s), ${r.atualizadas} atualizada(s).`, 'success'); loadTab();
    } catch (e) { toast(e.message, 'error'); }
  };
  window.saDelRubric = async (id) => {
    if (!confirm('Remover do catálogo? As cópias já publicadas nas empresas continuam.')) return;
    try { await api(`/api/superadmin/rubrics/${id}`, { method: 'DELETE' }); loadTab(); } catch (e) { toast(e.message, 'error'); }
  };
  window.saEditRubric = (r) => {
    r = r || { tipo: 'provento', incide_inss: 1, incide_irrf: 1, incide_fgts: 1, incide_13: 1, incide_ferias: 1, ativo: 1, esocial_nat_rubrica: '1000' };
    const chk = (f, l) => `<label style="font-size:.82rem;margin-right:.9rem;cursor:pointer"><input type="checkbox" class="sa-chk" data-f="${f}" ${r[f] ? 'checked' : ''}> ${l}</label>`;
    modal(r.id ? `Rubrica ${r.codigo}` : 'Nova rubrica global', `
      <div class="form-row">
        <div class="form-group"><label>Código</label><input class="form-control" id="sa-r-codigo" value="${esc(r.codigo || '')}" ${r.id ? 'disabled' : ''}></div>
        <div class="form-group" style="flex:2"><label>Nome</label><input class="form-control" id="sa-r-nome" value="${esc(r.nome || '')}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Tipo</label><select class="form-control" id="sa-r-tipo">
          ${['provento', 'desconto', 'informativo'].map((t) => `<option ${r.tipo === t ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
        <div class="form-group"><label>Natureza eSocial</label><input class="form-control" id="sa-r-nat" value="${esc(r.esocial_nat_rubrica || '')}"></div>
      </div>
      <div class="form-group">${chk('incide_inss', 'INSS')}${chk('incide_irrf', 'IRRF')}${chk('incide_fgts', 'FGTS')}${chk('incide_13', '13º')}${chk('incide_ferias', 'Férias')}${chk('aplica_todos', 'Aplica a todos')}${chk('ativo', 'Ativa')}</div>
      <div class="form-group"><label>Fórmula (opcional)</label>
        <input class="form-control" id="sa-r-formula" style="font-family:monospace" value="${esc(r.formula || '')}" placeholder="ex.: salario_hora * quantidade * 1.5"></div>`,
    async (w) => {
      const payload = {
        nome: w.querySelector('#sa-r-nome').value, tipo: w.querySelector('#sa-r-tipo').value,
        esocial_nat_rubrica: w.querySelector('#sa-r-nat').value, formula: w.querySelector('#sa-r-formula').value,
      };
      w.querySelectorAll('.sa-chk').forEach((c) => { payload[c.dataset.f] = c.checked ? 1 : 0; });
      if (r.id) await api(`/api/superadmin/rubrics/${r.id}`, { method: 'PUT', body: payload });
      else await api('/api/superadmin/rubrics', { method: 'POST', body: Object.assign({ codigo: w.querySelector('#sa-r-codigo').value }, payload) });
      toast('Rubrica salva. Publique para levar às empresas.', 'success'); loadTab();
    });
  };

  // Fila de suporte
  async function renderSupportQueue(body) {
    const list = await api('/api/superadmin/support');
    body.innerHTML = `<div class="table-responsive"><table class="table"><thead><tr>
      <th>#</th><th>Empresa</th><th>Categoria</th><th>Assunto</th><th>Aberto por</th><th>Data</th><th>Status</th><th></th></tr></thead><tbody>
      ${list.map((s) => `<tr><td>${s.id}</td><td>${esc(s.nome_fantasia || s.razao_social || '—')}</td>
        <td>${esc(CATEGORIAS[s.categoria] || s.categoria)}</td><td>${esc(s.assunto)}</td>
        <td>${esc(s.user_name || '')}<div class="text-muted" style="font-size:.72rem">${esc(s.user_email || '')}</div></td>
        <td>${fmtDate(s.created_at)}</td><td>${badge(s.status)}</td>
        <td><button class="btn btn-sm btn-primary" onclick='saAnswer(${JSON.stringify(s).replace(/'/g, '&#39;')})'>Responder</button></td></tr>`).join('')
      || '<tr><td colspan="8" class="text-muted">Nenhuma solicitação.</td></tr>'}
      </tbody></table></div>`;
  }
  window.saAnswer = (s) => {
    modal(`#${s.id} — ${s.assunto}`, `
      <div class="text-muted" style="font-size:.8rem;margin-bottom:.5rem">${esc(s.nome_fantasia || s.razao_social || '')} · ${esc(CATEGORIAS[s.categoria] || s.categoria)} · ${fmtDate(s.created_at)}</div>
      <div class="card" style="margin-bottom:.75rem"><div class="card-body" style="white-space:pre-wrap;font-size:.88rem">${esc(s.mensagem || '(sem descrição)')}</div></div>
      <div class="form-group"><label>Status</label><select class="form-control" id="sa-s-status">
        ${['aberto', 'em_andamento', 'concluido'].map((v) => `<option value="${v}" ${s.status === v ? 'selected' : ''}>${STATUS_BADGE[v][1]}</option>`).join('')}</select></div>
      <div class="form-group"><label>Resposta ao cliente</label><textarea class="form-control" id="sa-s-resp" rows="4">${esc(s.resposta || '')}</textarea></div>`,
    async (w) => {
      await api(`/api/superadmin/support/${s.id}`, { method: 'PUT', body: { status: w.querySelector('#sa-s-status').value, resposta: w.querySelector('#sa-s-resp').value } });
      toast('Resposta enviada ao cliente.', 'success'); loadTab();
    }, 'Enviar');
  };

  // ── SUPORTE (lado do cliente) ─────────────────────────────────────────────
  window.renderSupport = async function (container) {
    container.innerHTML = `
      <div class="page-header">
        <div><h2>Suporte</h2>
          <p style="font-size:.8rem;color:var(--muted);margin:.25rem 0 0">Peça atualização de tabelas, novas rubricas, liberação de acesso ou relate um problema.</p></div>
        <button class="btn btn-primary" onclick="supNew()">+ Nova solicitação</button>
      </div>
      <div id="sup-list"><div class="text-muted">Carregando...</div></div>`;
    try {
      const list = await api('/api/support');
      document.getElementById('sup-list').innerHTML = list.length ? list.map((s) => `
        <div class="card" style="margin-bottom:.75rem"><div class="card-body">
          <div style="display:flex;justify-content:space-between;gap:.5rem;flex-wrap:wrap">
            <strong>#${s.id} · ${esc(s.assunto)}</strong>${badge(s.status)}</div>
          <div class="text-muted" style="font-size:.75rem;margin:.25rem 0 .5rem">${esc(CATEGORIAS[s.categoria] || s.categoria)} · ${esc(s.user_name || '')} · ${fmtDate(s.created_at)}</div>
          <div style="white-space:pre-wrap;font-size:.88rem">${esc(s.mensagem || '')}</div>
          ${s.resposta ? `<div class="alert alert-info" style="margin:.75rem 0 0;white-space:pre-wrap"><strong>Resposta do suporte (${fmtDate(s.respondido_em)}):</strong><br>${esc(s.resposta)}</div>` : ''}
        </div></div>`).join('') : '<p class="text-muted">Nenhuma solicitação aberta ainda.</p>';
    } catch (e) {
      document.getElementById('sup-list').innerHTML = `<div class="alert alert-danger">${esc(e.message)}</div>`;
    }
  };
  window.supNew = () => {
    modal('Nova solicitação de suporte', `
      <div class="form-group"><label>Categoria</label><select class="form-control" id="sup-cat">
        ${Object.entries(CATEGORIAS).map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></div>
      <div class="form-group"><label>Assunto</label><input class="form-control" id="sup-assunto" maxlength="200" placeholder="Ex.: Atualizar tabela do INSS 2027"></div>
      <div class="form-group"><label>Descrição</label><textarea class="form-control" id="sup-msg" rows="5" placeholder="Explique o que precisa. Se for rubrica, informe nome, incidências e natureza eSocial."></textarea></div>`,
    async (w) => {
      await api('/api/support', { method: 'POST', body: {
        categoria: w.querySelector('#sup-cat').value, assunto: w.querySelector('#sup-assunto').value, mensagem: w.querySelector('#sup-msg').value } });
      toast('Solicitação enviada.', 'success');
      const main = document.getElementById('main-content');
      if (main) window.renderSupport(main);
    }, 'Enviar');
  };

  // Mostra o Painel do Sistema só para o super admin (atualiza o usuário salvo com /api/auth/me).
  async function syncSuperadminNav() {
    const nav = document.getElementById('nav-superadmin');
    let isSa = false;
    try { isSa = !!(JSON.parse(localStorage.getItem('cortex_user') || '{}') || {}).is_superadmin; } catch (e) { /* storage */ }
    if (nav) nav.style.display = isSa ? '' : 'none';
    if (!localStorage.getItem('cortex_token')) return;
    try {
      const res = await fetch('/api/auth/me');
      if (!res.ok) return;
      const me = await res.json();
      isSa = !!me.is_superadmin;
      try {
        const u = JSON.parse(localStorage.getItem('cortex_user') || '{}') || {};
        u.is_superadmin = me.is_superadmin;
        localStorage.setItem('cortex_user', JSON.stringify(u));
      } catch (e) { /* storage */ }
      if (nav) nav.style.display = isSa ? '' : 'none';
      const mudou = window.cxIsSuperadmin !== isSa;
      window.cxIsSuperadmin = isSa;
      // Primeira vez após a atualização: redesenha a tela de módulos para mostrar/esconder o bloco.
      if (mudou && typeof currentTab !== 'undefined' && currentTab === 'home') window.switchTab('home');
    } catch (e) { /* offline */ }
  }
  window.cxIsSuperadmin = (() => { try { return !!(JSON.parse(localStorage.getItem('cortex_user') || '{}') || {}).is_superadmin; } catch (e) { return false; } })();
  document.addEventListener('DOMContentLoaded', syncSuperadminNav);
})();
