// Cortex ERP - autenticação do frontend: injeta o Bearer token nas chamadas /api e exibe o login quando necessário.
(function () {
  const TOKEN_KEY = 'cortex_token';
  const nativeFetch = window.fetch.bind(window);

  const getToken = () => { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } };
  const setToken = (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch (e) { /* storage bloqueado */ } };
  const clearToken = () => { try { localStorage.removeItem(TOKEN_KEY); } catch (e) { /* storage bloqueado */ } };

  const isApiCall = (input) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    return url.startsWith('/api/') || url.startsWith(window.location.origin + '/api/');
  };
  const isPublicAuthCall = (input) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    return url.includes('/api/auth/login')
      || url.includes('/api/auth/register-company')
      || url.includes('/api/auth/forgot-password')
      || url.includes('/api/auth/reset-password');
  };

  window.fetch = async function (input, init) {
    if (!isApiCall(input) || isPublicAuthCall(input)) return nativeFetch(input, init);
    const opts = Object.assign({}, init);
    const headers = new Headers(opts.headers || (input instanceof Request ? input.headers : undefined));
    const token = getToken();
    if (token && !headers.has('Authorization')) headers.set('Authorization', 'Bearer ' + token);
    opts.headers = headers;
    const res = await nativeFetch(input, opts);
    // Só invalida se o token rejeitado ainda é o atual (um 401 antigo não apaga um login novo).
    if (res.status === 401 && getToken() === token) {
      clearToken();
      showLogin();
    } else if (res.status === 401 && !token) {
      showLogin();
    }
    return res;
  };

  // Abre DANFE/XML (links que não conseguem enviar o header Authorization) via fetch autenticado.
  window.openAuthed = async function (url, download) {
    const res = await window.fetch(url);
    if (!res.ok) { alert('Não foi possível abrir o documento (' + res.status + ').'); return; }
    const blob = await res.blob();
    const objUrl = URL.createObjectURL(blob);
    if (download) {
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = download;
      a.click();
    } else {
      window.open(objUrl, '_blank');
    }
    setTimeout(() => URL.revokeObjectURL(objUrl), 60000);
  };

  window.cortexLogout = function () {
    clearToken();
    window.location.reload();
  };

  // Detecta token de reset na URL (?reset_token=xxx) e abre tela de redefinição.
  function getResetTokenFromUrl() {
    try {
      return new URLSearchParams(window.location.search).get('reset_token');
    } catch (e) { return null; }
  }

  function showLogin(initialView) {
    if (document.getElementById('cortex-login-overlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'cortex-login-overlay';
    overlay.className = 'cx-login';
    overlay.innerHTML = `
      <form id="cortex-login-form" class="cx-login-card">
        <div class="cx-logo">CX</div>
        <h2>Cortex ERP</h2>
        <p>Acesse sua conta para continuar.</p>
        <label for="cortex-login-email">E-mail</label>
        <input id="cortex-login-email" type="email" required autocomplete="username" placeholder="voce@empresa.com.br">
        <label for="cortex-login-pass">Senha</label>
        <input id="cortex-login-pass" type="password" required autocomplete="current-password" placeholder="••••••••">
        <div id="cortex-login-error" class="cx-login-error"></div>
        <button type="submit">Entrar</button>
        <button type="button" id="cortex-to-forgot" class="cx-link-btn">Esqueci minha senha</button>
        <button type="button" id="cortex-to-register" class="cx-link-btn">Não tem conta? Cadastre sua empresa grátis</button>
        <div class="cx-login-foot">CONEXÃO SEGURA · JWT</div>
      </form>

      <form id="cortex-register-form" class="cx-login-card" style="display: none;">
        <div class="cx-logo">CX</div>
        <h2>Criar Conta</h2>
        <p>Comece a gerenciar seu negócio agora.</p>
        <label for="cortex-reg-company">Nome da Empresa</label>
        <input id="cortex-reg-company" type="text" required placeholder="Sua Empresa Ltda">
        <label for="cortex-reg-name">Seu Nome Completo</label>
        <input id="cortex-reg-name" type="text" required placeholder="Carlos Eduardo">
        <label for="cortex-reg-email">E-mail Corporativo</label>
        <input id="cortex-reg-email" type="email" required autocomplete="username" placeholder="admin@empresa.com.br">
        <label for="cortex-reg-pass">Senha de Acesso (mín. 6 dígitos)</label>
        <input id="cortex-reg-pass" type="password" required minlength="6" autocomplete="new-password" placeholder="••••••••">
        <label for="cortex-reg-cnpj">CNPJ (opcional)</label>
        <input id="cortex-reg-cnpj" type="text" placeholder="00.000.000/0001-00">
        <label for="cortex-reg-phone">Telefone / WhatsApp (opcional)</label>
        <input id="cortex-reg-phone" type="text" placeholder="(11) 99999-8888">
        <div id="cortex-register-error" class="cx-login-error"></div>
        <button type="submit">Criar Conta e Começar</button>
        <button type="button" id="cortex-to-login" class="cx-link-btn">Já possui conta? Fazer Login</button>
        <div class="cx-login-foot">ONBOARDING SEGURO · MULTI-TENANT</div>
      </form>

      <form id="cortex-forgot-form" class="cx-login-card" style="display: none;">
        <div class="cx-logo">CX</div>
        <h2>Recuperar Senha</h2>
        <p>Digite seu e-mail cadastrado e enviaremos um link de redefinição.</p>
        <label for="cortex-forgot-email">E-mail</label>
        <input id="cortex-forgot-email" type="email" required autocomplete="username" placeholder="voce@empresa.com.br">
        <div id="cortex-forgot-msg" class="cx-login-error" style="color: #6ee7b7;"></div>
        <div id="cortex-forgot-error" class="cx-login-error"></div>
        <button type="submit">Enviar Link de Redefinição</button>
        <button type="button" id="cortex-forgot-to-login" class="cx-link-btn">Voltar para o Login</button>
        <div class="cx-login-foot">LINK VÁLIDO POR 1 HORA</div>
      </form>

      <form id="cortex-reset-form" class="cx-login-card" style="display: none;">
        <div class="cx-logo">CX</div>
        <h2>Nova Senha</h2>
        <p>Escolha uma nova senha segura para sua conta.</p>
        <label for="cortex-reset-pass">Nova Senha (mín. 6 caracteres)</label>
        <input id="cortex-reset-pass" type="password" required minlength="6" autocomplete="new-password" placeholder="••••••••">
        <label for="cortex-reset-pass2">Confirmar Nova Senha</label>
        <input id="cortex-reset-pass2" type="password" required minlength="6" autocomplete="new-password" placeholder="••••••••">
        <div id="cortex-reset-msg" class="cx-login-error" style="color: #6ee7b7;"></div>
        <div id="cortex-reset-error" class="cx-login-error"></div>
        <button type="submit">Redefinir Senha</button>
        <div class="cx-login-foot">TOKEN DE USO ÚNICO · ASSINADO</div>
      </form>`;
    document.body.appendChild(overlay);

    const loginForm    = overlay.querySelector('#cortex-login-form');
    const registerForm = overlay.querySelector('#cortex-register-form');
    const forgotForm   = overlay.querySelector('#cortex-forgot-form');
    const resetForm    = overlay.querySelector('#cortex-reset-form');

    const showOnly = (form) => {
      [loginForm, registerForm, forgotForm, resetForm].forEach(f => f.style.display = 'none');
      form.style.display = 'block';
    };

    overlay.querySelector('#cortex-to-register').addEventListener('click', () => showOnly(registerForm));
    overlay.querySelector('#cortex-to-login').addEventListener('click', () => showOnly(loginForm));
    overlay.querySelector('#cortex-to-forgot').addEventListener('click', () => showOnly(forgotForm));
    overlay.querySelector('#cortex-forgot-to-login').addEventListener('click', () => showOnly(loginForm));

    // Abre tela de redefinição se URL contém ?reset_token=
    const urlToken = getResetTokenFromUrl();
    if (initialView === 'reset' && urlToken) {
      showOnly(resetForm);
    }

    loginForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const errBox = overlay.querySelector('#cortex-login-error');
      errBox.textContent = '';
      try {
        const res = await nativeFetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: overlay.querySelector('#cortex-login-email').value,
            password: overlay.querySelector('#cortex-login-pass').value,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { errBox.textContent = data.detail || 'Falha no login.'; return; }
        setToken(data.access_token);
        // Remove reset_token da URL antes de recarregar
        const url = new URL(window.location.href);
        url.searchParams.delete('reset_token');
        window.history.replaceState({}, '', url);
        window.location.reload();
      } catch (e) {
        errBox.textContent = 'Erro de conexão com o servidor.';
      }
    });

    registerForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const errBox = overlay.querySelector('#cortex-register-error');
      errBox.textContent = '';
      const submitBtn = registerForm.querySelector('button[type="submit"]');
      const origText = submitBtn.textContent;
      submitBtn.disabled = true;
      submitBtn.textContent = 'Criando conta...';

      try {
        const payload = {
          company_name: overlay.querySelector('#cortex-reg-company').value,
          admin_name: overlay.querySelector('#cortex-reg-name').value,
          email: overlay.querySelector('#cortex-reg-email').value,
          password: overlay.querySelector('#cortex-reg-pass').value,
          cnpj: overlay.querySelector('#cortex-reg-cnpj').value,
          phone: overlay.querySelector('#cortex-reg-phone').value,
        };

        const res = await nativeFetch('/api/auth/register-company', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          errBox.textContent = data.detail || 'Falha ao registrar empresa.';
          submitBtn.disabled = false;
          submitBtn.textContent = origText;
          return;
        }
        setToken(data.access_token);
        window.location.reload();
      } catch (e) {
        errBox.textContent = 'Erro de conexão com o servidor.';
        submitBtn.disabled = false;
        submitBtn.textContent = origText;
      }
    });

    forgotForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const errBox = overlay.querySelector('#cortex-forgot-error');
      const msgBox = overlay.querySelector('#cortex-forgot-msg');
      errBox.textContent = '';
      msgBox.textContent = '';
      const submitBtn = forgotForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Enviando...';

      try {
        const res = await nativeFetch('/api/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: overlay.querySelector('#cortex-forgot-email').value }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { errBox.textContent = data.detail || 'Erro ao processar solicitação.'; }
        else {
          msgBox.textContent = data.message || 'Solicitação enviada.';
          // Em modo dev o backend retorna dev_reset_url; mostramos o link para facilitar testes.
          if (data.dev_reset_url) {
            msgBox.textContent += ' [DEV] Link: ' + window.location.origin + data.dev_reset_url;
          }
        }
      } catch (e) {
        errBox.textContent = 'Erro de conexão com o servidor.';
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enviar Link de Redefinição';
      }
    });

    resetForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const errBox = overlay.querySelector('#cortex-reset-error');
      const msgBox = overlay.querySelector('#cortex-reset-msg');
      errBox.textContent = '';
      msgBox.textContent = '';

      const pass  = overlay.querySelector('#cortex-reset-pass').value;
      const pass2 = overlay.querySelector('#cortex-reset-pass2').value;
      if (pass !== pass2) { errBox.textContent = 'As senhas não coincidem.'; return; }

      const token = getResetTokenFromUrl();
      if (!token) { errBox.textContent = 'Token não encontrado na URL.'; return; }

      const submitBtn = resetForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Redefinindo...';

      try {
        const res = await nativeFetch('/api/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, new_password: pass }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          errBox.textContent = data.detail || 'Erro ao redefinir senha.';
        } else {
          msgBox.textContent = data.message || 'Senha redefinida! Fazendo login...';
          // Limpa token da URL e abre tela de login após 2s
          setTimeout(() => {
            const url = new URL(window.location.href);
            url.searchParams.delete('reset_token');
            window.history.replaceState({}, '', url);
            showOnly(loginForm);
          }, 2000);
        }
      } catch (e) {
        errBox.textContent = 'Erro de conexão com o servidor.';
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Redefinir Senha';
      }
    });
  }

  function addLogoutButton() {
    if (document.getElementById('btn-logout')) return; // já existe na sidebar
    const btn = document.createElement('button');
    btn.textContent = 'Sair';
    btn.className = 'cx-logout';
    btn.onclick = window.cortexLogout;
    document.body.appendChild(btn);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const resetToken = getResetTokenFromUrl();
    if (resetToken) {
      // Limpa o token do storage para forçar nova autenticação após redefinir
      clearToken();
      showLogin('reset');
    } else if (!getToken()) {
      showLogin();
    } else {
      addLogoutButton();
    }
  });
})();
