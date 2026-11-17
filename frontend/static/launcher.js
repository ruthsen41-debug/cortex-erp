// Cortex ERP - tela inicial de módulos em mosaico (faixas coloridas por área) e
// moldura colorida por área em cada módulo (cor em --mod, chip de área no cabeçalho).
(function () {
  // Áreas: rótulo curto (vai no bloco com seta) e cor da faixa.
  const CATS = {
    dp:   { label: 'dp',         color: '#f04410' },
    rh:   { label: 'rh',         color: '#2f8fe6' },
    fin:  { label: 'financeiro', color: '#4f9a2a' },
    com:  { label: 'comercial',  color: '#0f978d' },
    fis:  { label: 'fiscal',     color: '#d97706' },
    cont: { label: 'contábil',   color: '#7c4dcc' },
    gest: { label: 'gestão',     color: '#46566b' },
    sys:  { label: 'sistema',    color: '#46566b' },
    home: { label: 'cortex',     color: '#2f8fe6' },
  };

  // [nome no bloco, ícone lucide, aba do sistema, sub-aba do DP (opcional)]
  const ROWS = [
    { cat: 'dp', items: [
      ['Folha de pagamento', 'calculator', 'dp', 'folha'],
      ['Ponto eletrônico', 'calendar-clock', 'dp', 'ponto'],
      ['Segurança e medicina', 'briefcase-medical', 'dp', 'sst'],
      ['Gestão de benefícios', 'heart-handshake', 'dp', 'beneficios'],
      ['Férias', 'umbrella', 'dp', 'ferias'],
      ['13º salário', 'gift', 'dp', 'decimo'],
      ['Rescisão', 'user-x', 'dp', 'rescisao'],
      ['eSocial', 'send', 'dp', 'esocial_periodico'],
    ] },
    { cat: 'rh', items: [
      ['Gestão de pessoas', 'users-round', 'dp', 'funcionarios'],
      ['Cargos e salários', 'briefcase', 'dp', 'cargos'],
      ['Histórico salarial', 'trending-up', 'dp', 'historico'],
      ['Estágio e aprendiz', 'graduation-cap', 'dp', 'estagiarios'],
      ['Portal do colaborador', 'circle-user', 'dp', 'employee_portal'],
      ['Convenções coletivas', 'scroll-text', 'conventions'],
      ['Custo de pessoal', 'piggy-bank', 'dp', 'rel_custo'],
      ['Turnover', 'trending-down', 'dp', 'rel_turnover'],
    ] },
    { cat: 'fin', items: [
      ['Contas a receber', 'hand-coins', 'receivables'],
      ['Contas a pagar', 'wallet', 'payables'],
      ['Conciliação bancária', 'file-check-2', 'ofx'],
      ['DRE e relatórios', 'bar-chart-4', 'reports'],
    ] },
    { cat: 'com', items: [
      ['CRM funil', 'kanban', 'crm'],
      ['Vendas', 'shopping-bag', 'sales'],
      ['PDV frente de caixa', 'monitor-smartphone', 'pdv'],
      ['Ordens de serviço', 'wrench', 'os'],
      ['Pedidos e orçamentos', 'file-text', 'quotes'],
      ['Contratos recorrentes', 'file-pen-line', 'contracts'],
      ['Devoluções e RMA', 'undo-2', 'returns'],
      ['Estoque e cadastros', 'package-search', 'inventory'],
    ] },
    { cat: 'fis', items: [
      ['Emissor NF-e / NFS-e', 'receipt', 'invoices'],
      ['Compras e entradas', 'shopping-cart', 'purchases'],
      ['Escrita fiscal', 'book-text', 'fiscal_books'],
      ['SPED / EFD / ECF', 'file-code-2', 'sped'],
      ['Simples Nacional', 'landmark', 'simples'],
      ['Manifesto destinatário', 'file-search', 'nfe_manifest'],
      ['DIRBI', 'file-spreadsheet', 'dirbi'],
      ['Certificados digitais', 'key-round', 'certificates'],
    ] },
    { cat: 'cont', items: [
      ['Contabilidade', 'book-marked', 'accounting'],
      ['LALUR', 'book-open', 'lalur'],
      ['Patrimônio', 'building', 'patrimony'],
      ['Honorários', 'handshake', 'honorarios'],
      ['Calendário fiscal', 'calendar-check', 'obligations'],
    ] },
    { cat: 'gest', items: [
      ['Visão geral e CFO IA', 'layout-dashboard', 'dashboard'],
      ['Auditoria', 'shield-check', 'audit'],
      ['Usuários', 'users', 'users'],
      ['Configurações', 'building-2', 'settings'],
      ['Suporte', 'life-buoy', 'support'],
      ['Painel do sistema', 'shield-half', 'superadmin'],
    ] },
  ];

  // Área padrão de cada aba (quando se navega pela barra lateral).
  const TAB_CAT = {};
  ROWS.forEach((r) => r.items.forEach(([, , tab]) => { if (!TAB_CAT[tab]) TAB_CAT[tab] = r.cat; }));

  let pendingCat = null;
  // Telas do sistema (painel do dono e suporte) não mostram atalhos de nenhuma área.
  const FORCE_CAT = { superadmin: 'sys', support: 'sys' };

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function allowedTabs() {
    if (typeof currentUserRole === 'undefined' || currentUserRole === 'admin') return null;
    return (typeof ROLE_MODULES !== 'undefined' && ROLE_MODULES[currentUserRole]) || [];
  }

  function setModule(cat, title) {
    const c = CATS[cat] || CATS.gest;
    document.documentElement.style.setProperty('--mod', c.color);
    document.body.dataset.cat = cat;
    const chip = document.getElementById('cx-cat-chip');
    const t = document.getElementById('page-title');
    if (chip) chip.textContent = c.label;
    if (t) t.textContent = title;
    // Atalhos do cabeçalho: cada área mostra só os seus (data-areas="dp rh" ...).
    document.querySelectorAll('.cx-hdr-act').forEach((btn) => {
      const areas = (btn.dataset.areas || '').split(/\s+/);
      btn.style.display = areas.includes(cat) ? '' : 'none';
    });
  }

  function tabTitle(tab) {
    const nav = document.getElementById('nav-' + tab);
    return (nav && nav.dataset.label) || tab;
  }

  function renderHome() {
    try { currentTab = 'home'; } catch (e) { /* app.js ausente */ }
    if (typeof closeSidebar === 'function') closeSidebar();
    document.querySelectorAll('.nav-item').forEach((el) => el.classList.remove('active'));
    const nav = document.getElementById('nav-home');
    if (nav) nav.classList.add('active');
    setModule('home', 'Módulos');

    let user = {};
    try { user = JSON.parse(localStorage.getItem('cortex_user') || '{}') || {}; } catch (e) { /* storage bloqueado */ }
    const first = (user.name || '').trim().split(/\s+/)[0];
    const allowed = allowedTabs();

    const rows = ROWS.map((r) => {
      const items = r.items.filter(([, , tab]) => (!allowed || allowed.includes(tab))
        && (tab !== 'superadmin' || window.cxIsSuperadmin));
      if (!items.length) return '';
      const c = CATS[r.cat];
      return `
        <div class="cx-lrow${items.length <= 5 ? ' cx-wide' : ''}" style="--c:${c.color}">
          <div class="cx-lcat"><span>${esc(c.label)}</span></div>
          <div class="cx-ltiles">
            ${items.map(([name, icon, tab, sub]) => `
              <button type="button" class="cx-tile" data-name="${esc(name.toLowerCase())}"
                onclick="cxOpenTile('${tab}', '${sub || ''}', '${r.cat}')" title="Abrir ${esc(name)}">
                <i data-lucide="${icon}"></i><span>${esc(name)}</span>
              </button>`).join('')}
          </div>
        </div>`;
    }).join('');

    const main = document.getElementById('main-content');
    main.innerHTML = `
      <section class="cx-launch">
        <div class="cx-launch-head">
          <div>
            <div class="cx-launch-kicker">${first ? 'Olá, ' + esc(first) : 'Bem-vindo'}</div>
            <h1>Escolha um módulo</h1>
          </div>
          <label class="cx-launch-search">
            <i data-lucide="search"></i>
            <input id="cx-launch-filter" type="search" placeholder="Buscar módulo…" autocomplete="off">
          </label>
        </div>
        <div class="cx-launch-grid">${rows || '<p class="cx-launch-empty">Nenhum módulo liberado para o seu perfil.</p>'}</div>
      </section>`;

    const filter = document.getElementById('cx-launch-filter');
    filter.addEventListener('input', () => {
      const q = filter.value.trim().toLowerCase();
      main.querySelectorAll('.cx-lrow').forEach((row) => {
        let any = false;
        row.querySelectorAll('.cx-tile').forEach((t) => {
          const hit = !q || t.dataset.name.includes(q);
          t.hidden = !hit;
          if (hit) any = true;
        });
        row.hidden = !any;
      });
    });
    if (window.lucide) lucide.createIcons();
  }

  window.cxOpenTile = function (tab, sub, cat) {
    if (sub && tab === 'dp') {
      try { dpSubTab = sub; } catch (e) { /* dp.js ausente */ }
    }
    pendingCat = cat;
    return window.switchTab(tab);
  };

  const orig = window.switchTab;
  if (typeof orig === 'function') {
    window.switchTab = function (tab) {
      if (tab === 'home') { renderHome(); return Promise.resolve(); }
      setModule(FORCE_CAT[tab] || pendingCat || TAB_CAT[tab] || 'gest', tabTitle(tab));
      pendingCat = null;
      return orig.apply(this, arguments);
    };
  }
})();
