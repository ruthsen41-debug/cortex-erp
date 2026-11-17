// Cortex ERP - tela de apresentação antes do login.
// Rede de dados animada + logo que se monta; no fim, os 4 quadrados do logo voam
// até os blocos de área da tela de login (dp, rh, fiscal, financeiro) e viram o login.
// O admin principal liga/desliga em Configurações (GET/PUT /api/system/intro).
(function () {
  const CACHE_KEY = 'cortex_intro';          // último valor conhecido ('1' | '0')
  const SEEN_KEY = 'cortex_intro_seen';      // já exibida nesta sessão do navegador

  const store = {
    get(s, k) { try { return s.getItem(k); } catch (e) { return null; } },
    set(s, k, v) { try { s.setItem(k, v); } catch (e) { /* storage bloqueado */ } },
  };

  // Ordem = posição no logo 2x2 (TL, TR, BL, BR) e área de destino na tela de login.
  const SQUARES = [
    { color: '#f04410', label: 'dp' },
    { color: '#2f8fe6', label: 'rh' },
    { color: '#4f9a2a', label: 'financeiro' },
    { color: '#d97706', label: 'fiscal' },
  ];
  const CHIPS = [
    ['Depto. Pessoal', '#f04410'], ['Fiscal', '#d97706'], ['Contábil', '#7c4dcc'],
    ['Financeiro', '#4f9a2a'], ['Comercial', '#0f978d'], ['IA', '#22d3ee'],
  ];

  const uncover = () => document.documentElement.classList.remove('cx-intro-pending');

  function refreshSetting() {
    return fetch('/api/system/intro')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) store.set(localStorage, CACHE_KEY, d.enabled ? '1' : '0'); return d; })
      .catch(() => null);
  }

  // ── fundo: rede de nós conectados ───────────────────────────
  function startNetwork(canvas) {
    const ctx = canvas.getContext('2d');
    const colors = ['#22d3ee', '#2f8fe6', '#7c4dcc', '#4f9a2a', '#f04410', '#d97706'];
    let w, h, nodes, raf, dpr;
    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round(Math.min(110, (w * h) / 14000));
      nodes = Array.from({ length: n }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.45, vy: (Math.random() - 0.5) * 0.45,
        r: 1 + Math.random() * 1.8, c: colors[(Math.random() * colors.length) | 0],
      }));
    }
    function frame() {
      ctx.clearRect(0, 0, w, h);
      const max = 150;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        a.x += a.vx; a.y += a.vy;
        if (a.x < 0 || a.x > w) a.vx *= -1;
        if (a.y < 0 || a.y > h) a.vy *= -1;
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y, d = Math.sqrt(dx * dx + dy * dy);
          if (d < max) {
            ctx.strokeStyle = `rgba(120, 170, 255, ${(1 - d / max) * 0.28})`;
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      for (const a of nodes) {
        ctx.fillStyle = a.c;
        ctx.shadowColor = a.c; ctx.shadowBlur = 8;
        ctx.beginPath(); ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2); ctx.fill();
      }
      ctx.shadowBlur = 0;
      raf = requestAnimationFrame(frame);
    }
    resize();
    window.addEventListener('resize', resize);
    frame();
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }

  // Retângulos de destino: blocos de área do mosaico do login, ou o logo do topo (telas estreitas).
  function targetRects(loginOverlay) {
    const cats = [...loginOverlay.querySelectorAll('.cx-login-mosaic .cx-lcat')];
    const byLabel = {};
    cats.forEach((el) => { byLabel[el.textContent.trim()] = el; });
    const visible = cats.length && cats[0].getBoundingClientRect().width > 0;
    if (visible) {
      return { els: SQUARES.map((s) => byLabel[s.label]), rects: SQUARES.map((s) => byLabel[s.label].getBoundingClientRect()), radius: 14 };
    }
    const logo = loginOverlay.querySelector('.cx-login-brand .cx-logo');
    if (!logo) return null;
    const r = logo.getBoundingClientRect();
    const q = r.width * 0.46;
    const pos = [[r.left, r.top], [r.right - q, r.top], [r.left, r.bottom - q], [r.right - q, r.bottom - q]];
    return { els: [], rects: pos.map(([x, y]) => ({ left: x, top: y, width: q, height: q })), radius: 3 };
  }

  function play(loginOverlay, preview) {
    const intro = document.createElement('div');
    intro.className = 'cx-intro';
    intro.setAttribute('role', 'presentation');
    intro.innerHTML = `
      <canvas class="cx-intro-net"></canvas>
      <div class="cx-intro-grid"></div>
      <div class="cx-intro-center">
        <div class="cx-intro-logo">
          ${SQUARES.map((s, i) => `<div class="cx-intro-sq" data-i="${i}" style="--c:${s.color}"><span>${s.label}</span></div>`).join('')}
        </div>
        <div class="cx-intro-word"><b>cortex</b> erp</div>
        <div class="cx-intro-tag"><span class="cx-intro-type"></span><i class="cx-intro-caret"></i></div>
        <div class="cx-intro-chips">${CHIPS.map(([n, c], i) => `<span style="--c:${c};--d:${i}">${n}</span>`).join('')}</div>
        <div class="cx-intro-load"><div class="cx-intro-bar"><i></i></div><div class="cx-intro-status">Inicializando módulos <b>0%</b></div></div>
      </div>
      <button type="button" class="cx-intro-skip">Pular apresentação ›</button>`;
    document.body.appendChild(intro);
    uncover(); // a apresentação já cobre a tela: pode tirar a cobertura do <head>
    store.set(sessionStorage, SEEN_KEY, '1');

    const stopNet = startNetwork(intro.querySelector('.cx-intro-net'));
    const timers = [];
    const later = (ms, fn) => timers.push(setTimeout(fn, ms));

    // texto digitado
    const phrase = 'Gestão empresarial inteligente';
    const typeEl = intro.querySelector('.cx-intro-type');
    for (let i = 1; i <= phrase.length; i++) later(1300 + i * 38, () => { typeEl.textContent = phrase.slice(0, i); });

    // barra de carregamento
    const pct = intro.querySelector('.cx-intro-status b');
    const steps = ['Inicializando módulos', 'Conectando motor fiscal', 'Carregando folha e eSocial', 'Pronto'];
    const status = intro.querySelector('.cx-intro-status');
    for (let p = 0; p <= 100; p += 4) {
      later(2100 + p * 15, () => {
        pct.textContent = p + '%';
        intro.querySelector('.cx-intro-bar i').style.width = p + '%';
        const label = steps[Math.min(steps.length - 1, Math.floor(p / 34))];
        if (status.firstChild.nodeValue.trim() !== label) status.firstChild.nodeValue = label + ' ';
      });
    }

    let finished = false;
    function finish(fast) {
      if (finished) return;
      finished = true;
      timers.forEach(clearTimeout);
      document.removeEventListener('keydown', onKey);
      if (fast) {
        intro.classList.add('cx-intro-fade');
        setTimeout(() => { stopNet(); intro.remove(); }, 350);
        return;
      }
      morph();
    }

    // transformação: quadrados do logo -> blocos de área do login
    function morph() {
      const target = targetRects(loginOverlay);
      if (!target) {
        intro.classList.add('cx-intro-fade');
        setTimeout(() => { stopNet(); intro.remove(); }, 450);
        return;
      }
      intro.classList.add('cx-intro-out');
      const { els, rects, radius } = target;
      els.forEach((el) => { el.style.visibility = 'hidden'; });
      const sqs = [...intro.querySelectorAll('.cx-intro-sq')];
      const start = sqs.map((s) => s.getBoundingClientRect());
      const flyers = sqs.map((s, i) => {
        const f = s.cloneNode(true);
        f.classList.add('cx-intro-fly');
        Object.assign(f.style, { left: start[i].left + 'px', top: start[i].top + 'px', width: start[i].width + 'px', height: start[i].height + 'px' });
        document.body.appendChild(f);
        s.style.visibility = 'hidden';
        return f;
      });
      const dur = 900;
      const anims = flyers.map((f, i) => {
        const t = rects[i];
        return f.animate([
          { left: start[i].left + 'px', top: start[i].top + 'px', width: start[i].width + 'px', height: start[i].height + 'px', borderRadius: '12px' },
          { left: t.left + 'px', top: t.top + 'px', width: t.width + 'px', height: t.height + 'px', borderRadius: radius + 'px' },
        ], { duration: dur, delay: i * 70, easing: 'cubic-bezier(.7,0,.2,1)', fill: 'forwards' });
      });
      if (els.length) flyers.forEach((f, i) => f.querySelector('span').animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, delay: dur - 150 + i * 70, fill: 'forwards' }));
      Promise.all(anims.map((a) => a.finished)).then(() => {
        els.forEach((el) => { el.style.visibility = ''; });
        flyers.forEach((f) => f.remove());
        stopNet();
        intro.remove();
      });
    }

    function onKey(e) { if (e.key === 'Escape' || e.key === 'Enter') finish(false); }
    document.addEventListener('keydown', onKey);
    intro.querySelector('.cx-intro-skip').addEventListener('click', () => finish(false));
    later(4300, () => finish(false));

    // Se o admin desligou e o cache ainda não sabia, encerra logo.
    if (!preview) refreshSetting().then((d) => { if (d && !d.enabled) finish(true); });
  }

  // Chamado pelo auth.js depois de montar a tela de login.
  window.cxIntro = function (loginOverlay) {
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const disabled = store.get(localStorage, CACHE_KEY) === '0';
    const seen = store.get(sessionStorage, SEEN_KEY) === '1';
    const midSession = performance.now() > 8000; // login por sessão expirada: sem apresentação
    if (reduce || disabled || seen || midSession || new URLSearchParams(location.search).has('reset_token')) {
      uncover();
      refreshSetting();
      return;
    }
    play(loginOverlay);
  };

  // ── cartão em Configurações (somente admin da empresa principal) ──
  window.cxRenderIntroSetting = async function () {
    const slot = document.getElementById('cx-intro-setting');
    if (!slot) return;
    let user = {};
    try { user = JSON.parse(localStorage.getItem('cortex_user') || '{}') || {}; } catch (e) { /* */ }
    if (user.role !== 'admin' || Number(user.company_id) !== 1) return;
    const d = await refreshSetting();
    const on = d ? d.enabled : store.get(localStorage, CACHE_KEY) !== '0';
    // a tela pode ter sido redesenhada durante o fetch: busca o espaço de novo
    const live = document.getElementById('cx-intro-setting');
    if (!live) return;
    live.innerHTML = `
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xs">
        <div class="flex items-center gap-2 px-5 py-3 border-b border-slate-100 dark:border-slate-800">
          <i data-lucide="clapperboard" class="w-4 h-4 text-cyan-500"></i>
          <h3 class="font-bold text-sm text-slate-800 dark:text-slate-100">Tela de apresentação</h3>
        </div>
        <div class="p-5 flex items-center justify-between gap-4">
          <div class="text-xs text-slate-500 dark:text-slate-400">
            Animação exibida antes da tela de login (uma vez por sessão do navegador).<br>
            Vale para todos os usuários desta instalação.
          </div>
          <label class="cx-switch" title="Ligar/desligar apresentação">
            <input type="checkbox" id="cx-intro-toggle" ${on ? 'checked' : ''}>
            <span></span>
          </label>
        </div>
        <div class="px-5 pb-4 -mt-2"><button type="button" id="cx-intro-preview" class="text-xs font-semibold text-cyan-600 hover:underline">Ver apresentação agora</button></div>
      </div>`;
    if (window.lucide) lucide.createIcons();
    const toggle = document.getElementById('cx-intro-toggle');
    toggle.addEventListener('change', async () => {
      const enabled = toggle.checked;
      try {
        const r = await fetch('/api/system/intro', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled }),
        });
        const res = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(res.detail || 'Falha ao salvar');
        store.set(localStorage, CACHE_KEY, enabled ? '1' : '0');
        if (typeof showToast === 'function') showToast(enabled ? 'Apresentação ativada.' : 'Apresentação desativada.', 'success');
      } catch (e) {
        toggle.checked = !enabled;
        if (typeof showToast === 'function') showToast('Erro: ' + e.message, 'error');
      }
    });
    // pré-visualização: sem tela de login por baixo, termina com fade
    document.getElementById('cx-intro-preview').addEventListener('click', () => {
      play(document.createElement('div'), true);
    });
  };
})();
