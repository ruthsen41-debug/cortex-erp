/* Aviso "Nova versão disponível" — como nos aplicativos de celular.
 *
 * A página guarda o build com que foi aberta (<meta name="cortex-build">, injetada
 * pelo servidor). De tempos em tempos pergunta ao servidor qual é o build atual
 * (/api/version). Se mudou, mostra uma faixa com o botão "Atualizar agora", que
 * troca o service worker, limpa o cache e recarrega a página.
 */
(function () {
  'use strict';
  const meta = document.querySelector('meta[name="cortex-build"]');
  if (!meta) return;
  const BUILD_ABERTO = meta.content;
  const INTERVALO = 5 * 60 * 1000;   // verifica a cada 5 minutos
  const ADIAR = 30 * 60 * 1000;      // "Depois" esconde por 30 minutos
  let adiadoAte = 0;
  let faixa = null;
  let atualizando = false;

  function estilo() {
    if (document.getElementById('cx-upd-style')) return;
    const css = document.createElement('style');
    css.id = 'cx-upd-style';
    css.textContent = `
      #cx-upd{position:fixed;left:50%;bottom:20px;transform:translate(-50%,140%);z-index:2147483000;
        display:flex;align-items:center;gap:14px;flex-wrap:wrap;max-width:calc(100vw - 32px);
        padding:12px 14px 12px 16px;border-radius:14px;background:var(--surface-solid,#0e1428);
        color:var(--text,#e9edff);border:1px solid var(--border-strong,rgba(129,140,248,.32));
        box-shadow:0 18px 50px -12px rgba(0,0,0,.55);font:500 14px/1.35 var(--font-ui,Inter,system-ui,sans-serif);
        transition:transform .35s cubic-bezier(.2,.9,.3,1.2)}
      #cx-upd.on{transform:translate(-50%,0)}
      #cx-upd .cx-upd-ico{width:34px;height:34px;flex:none;border-radius:10px;display:grid;place-items:center;
        background:linear-gradient(135deg,#6366f1,#22d3ee);color:#fff}
      #cx-upd .cx-upd-txt b{display:block;font-weight:700}
      #cx-upd .cx-upd-txt span{color:var(--muted,#7d87b2);font-size:12.5px}
      #cx-upd .cx-upd-acoes{display:flex;gap:8px;margin-left:auto}
      #cx-upd button{border:0;border-radius:10px;padding:8px 14px;font:600 13px var(--font-ui,Inter,sans-serif);cursor:pointer}
      #cx-upd .cx-upd-ok{background:linear-gradient(135deg,#6366f1,#22d3ee);color:#fff}
      #cx-upd .cx-upd-ok:disabled{opacity:.7;cursor:wait}
      #cx-upd .cx-upd-depois{background:transparent;color:var(--text-2,#b4bcdf);border:1px solid var(--border,rgba(129,140,248,.16))}
      @media (max-width:600px){
        #cx-upd{left:12px;right:12px;bottom:12px;max-width:none;transform:translateY(140%)}
        #cx-upd.on{transform:none}
        #cx-upd .cx-upd-txt{flex:1;min-width:0}
        #cx-upd .cx-upd-acoes{width:100%;justify-content:flex-end}}
      @keyframes cx-upd-gira{to{transform:rotate(360deg)}}
      #cx-upd .gira{animation:cx-upd-gira 1s linear infinite}`;
    document.head.appendChild(css);
  }

  const ICONE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/></svg>';

  function mostrar(versao) {
    if (atualizando || Date.now() < adiadoAte) return;
    estilo();
    if (!faixa) {
      faixa = document.createElement('div');
      faixa.id = 'cx-upd';
      faixa.setAttribute('role', 'status');
      faixa.innerHTML =
        '<div class="cx-upd-ico">' + ICONE + '</div>' +
        '<div class="cx-upd-txt"><b></b><span>Salve o que estiver fazendo antes de atualizar.</span></div>' +
        '<div class="cx-upd-acoes"><button class="cx-upd-depois" type="button">Depois</button>' +
        '<button class="cx-upd-ok" type="button">Atualizar agora</button></div>';
      document.body.appendChild(faixa);
      faixa.querySelector('.cx-upd-ok').addEventListener('click', atualizar);
      faixa.querySelector('.cx-upd-depois').addEventListener('click', () => {
        adiadoAte = Date.now() + ADIAR;
        faixa.classList.remove('on');
      });
    }
    faixa.querySelector('b').textContent =
      'Nova versão do Cortex disponível' + (versao ? ' (' + versao + ')' : '');
    requestAnimationFrame(() => faixa.classList.add('on'));
  }

  async function atualizar() {
    atualizando = true;
    if (faixa) {
      const bt = faixa.querySelector('.cx-upd-ok');
      bt.disabled = true;
      bt.textContent = 'Atualizando…';
      faixa.querySelector('.cx-upd-ico svg').classList.add('gira');
    }
    try {
      if ('serviceWorker' in navigator) {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg) {
          await reg.update().catch(() => {});
          if (reg.waiting) reg.waiting.postMessage('CORTEX_SKIP_WAITING');
        }
      }
      if (window.caches) {
        const chaves = await caches.keys();
        await Promise.all(chaves.filter((k) => k.startsWith('cortex-erp-')).map((k) => caches.delete(k)));
      }
    } catch (e) { /* recarrega mesmo assim */ }
    location.reload();
  }

  async function verificar() {
    if (atualizando || document.visibilityState === 'hidden') return null;
    try {
      const r = await fetch('/api/version', { cache: 'no-store' });
      if (!r.ok) return null;
      const info = await r.json();
      if (info.build && info.build !== BUILD_ABERTO) mostrar(info.version);
      return info;
    } catch (e) {
      return null;  // servidor reiniciando (atualização em andamento) ou sem rede
    }
  }

  // Usado pelo Painel do Sistema ("Verificar atualizações") e após instalar uma versão
  window.cortexVersao = {
    buildAberto: BUILD_ABERTO,
    versaoAberta: meta.getAttribute('data-version') || '',
    verificar: () => { adiadoAte = 0; return verificar(); },
    atualizar,
  };

  setTimeout(verificar, 20000);
  setInterval(verificar, INTERVALO);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') verificar();
  });
})();
