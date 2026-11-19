/**
 * Cortex ERP — servidor de atualizações e licenças (Cloudflare Worker).
 *
 * O "porteiro" do modelo híbrido:
 *   - D1 (banco LICENCAS) guarda as chaves de licença de cada escritório;
 *   - R2 (BUCKET) guarda os instaladores, que nunca ficam públicos;
 *   - o servidor do escritório pergunta "tem versão nova?" mandando a chave;
 *     se a licença estiver ativa, recebe o manifesto e um link de download
 *     assinado (HMAC) que vale por pouco tempo.
 *
 * Rotas públicas (servidor do cliente):
 *   GET  /                          saúde
 *   POST /v1/verificar              {chave, versao_atual, instalacao} -> manifesto + link
 *   GET  /v1/baixar/:versao?k&exp&sig   entrega o instalador (link assinado)
 *
 * Rotas do dono (Authorization: Bearer ADMIN_TOKEN):
 *   GET   /v1/admin/licencas
 *   POST  /v1/admin/licencas                 {cliente, cnpj, email, expira_em, observacao}
 *   PATCH /v1/admin/licencas/:chave          {ativa, cliente, cnpj, email, expira_em, observacao}
 *   GET   /v1/admin/versoes
 *   PUT   /v1/admin/versoes/:versao/arquivo  corpo = CortexERP-Setup.exe, cabeçalho X-Sha256
 *   PUT   /v1/admin/versoes/:versao/publicar {sha256, tamanho, notas}
 *
 * Segredos (wrangler secret put): ADMIN_TOKEN, LINK_SECRET.
 */

const NOME_SETUP = "CortexERP-Setup.exe";
const VALIDADE_LINK_S = 30 * 60; // o download precisa começar em até 30 minutos
const RE_VERSAO = /^\d+\.\d+\.\d+$/;
const RE_CHAVE = /^CTX(-[A-Z0-9]{4}){3}$/;
const ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // sem 0/O e 1/I, para ditar por telefone

export default {
  async fetch(request, env) {
    try {
      return await rotear(request, env);
    } catch (e) {
      if (e instanceof ErroHttp) return json({ erro: e.message }, e.status);
      console.error(e && e.stack ? e.stack : e);
      return json({ erro: "Erro interno no servidor de atualizações." }, 500);
    }
  },
};

class ErroHttp extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

async function corpo(request) {
  try {
    return await request.json();
  } catch {
    throw new ErroHttp(400, "Corpo da requisição não é um JSON válido.");
  }
}

async function rotear(request, env) {
  const url = new URL(request.url);
  const p = url.pathname.replace(/\/+$/, "") || "/";
  const m = request.method;

  if (p === "/" && m === "GET") return json({ ok: true, servico: "cortex-atualizacoes" });
  if (p === "/v1/verificar" && m === "POST") return verificar(request, env, url);

  let r;
  if ((r = p.match(/^\/v1\/baixar\/(\d+\.\d+\.\d+)$/)) && m === "GET") return baixar(env, url, r[1]);

  if (p.startsWith("/v1/admin/")) {
    await exigirAdmin(request, env);
    if (p === "/v1/admin/licencas" && m === "GET") return listarLicencas(env);
    if (p === "/v1/admin/licencas" && m === "POST") return criarLicenca(env, await corpo(request));
    if ((r = p.match(/^\/v1\/admin\/licencas\/([A-Z0-9-]+)$/)) && m === "PATCH")
      return alterarLicenca(env, r[1], await corpo(request));
    if (p === "/v1/admin/versoes" && m === "GET") return listarVersoes(env);
    if ((r = p.match(/^\/v1\/admin\/versoes\/(\d+\.\d+\.\d+)\/arquivo$/)) && m === "PUT")
      return enviarArquivo(request, env, r[1]);
    if ((r = p.match(/^\/v1\/admin\/versoes\/(\d+\.\d+\.\d+)\/publicar$/)) && m === "PUT")
      return publicarVersao(env, r[1], await corpo(request));
  }
  return json({ erro: "Rota não encontrada." }, 404);
}

// ── utilitários de segurança ────────────────────────────────────────────────
const enc = new TextEncoder();

function iguais(a, b) {
  // comparação em tempo constante (não revela quantos caracteres batem)
  const x = enc.encode(String(a));
  const y = enc.encode(String(b));
  let dif = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) dif |= (x[i] || 0) ^ (y[i] || 0);
  return dif === 0;
}

async function exigirAdmin(request, env) {
  if (!env.ADMIN_TOKEN) throw new ErroHttp(500, "ADMIN_TOKEN não configurado no Worker.");
  const h = request.headers.get("authorization") || "";
  const token = h.startsWith("Bearer ") ? h.slice(7) : "";
  if (!token || !iguais(token, env.ADMIN_TOKEN)) throw new ErroHttp(401, "Não autorizado.");
}

async function hmac(texto, segredo) {
  const chave = await crypto.subtle.importKey("raw", enc.encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", chave, enc.encode(texto));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function gerarChave() {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  const c = [...bytes].map((b) => ALFABETO[b % ALFABETO.length]).join("");
  return `CTX-${c.slice(0, 4)}-${c.slice(4, 8)}-${c.slice(8, 12)}`;
}

function hoje() {
  return new Date().toISOString().slice(0, 10);
}

function agora() {
  return new Date().toISOString().slice(0, 19) + "Z";
}

// ── licenças ────────────────────────────────────────────────────────────────
async function licencaValida(env, chave) {
  chave = String(chave || "").trim().toUpperCase();
  if (!RE_CHAVE.test(chave)) throw new ErroHttp(403, "Chave de licença inválida. Confira a chave em Atualizações.");
  const lic = await env.LICENCAS.prepare("SELECT * FROM licencas WHERE chave = ?").bind(chave).first();
  if (!lic) throw new ErroHttp(403, "Chave de licença não encontrada. Fale com o suporte do Cortex.");
  if (!lic.ativa) throw new ErroHttp(403, "Licença suspensa: as atualizações estão bloqueadas. Fale com o suporte do Cortex.");
  if (lic.expira_em && lic.expira_em < hoje())
    throw new ErroHttp(403, `Licença vencida em ${lic.expira_em.split("-").reverse().join("/")}. Fale com o suporte do Cortex para renovar.`);
  return lic;
}

async function listarLicencas(env) {
  const { results } = await env.LICENCAS.prepare("SELECT * FROM licencas ORDER BY criada_em DESC").all();
  return json({ licencas: results });
}

function limparCampos(d) {
  const out = {};
  for (const k of ["cliente", "cnpj", "email", "observacao"]) if (k in d) out[k] = String(d[k] ?? "").trim().slice(0, 200);
  if ("expira_em" in d) {
    const v = d.expira_em ? String(d.expira_em) : null;
    if (v && !/^\d{4}-\d{2}-\d{2}$/.test(v)) throw new ErroHttp(400, "expira_em deve estar no formato AAAA-MM-DD.");
    out.expira_em = v;
  }
  if ("ativa" in d) out.ativa = d.ativa ? 1 : 0;
  return out;
}

async function criarLicenca(env, d) {
  const campos = limparCampos(d);
  if (!campos.cliente) throw new ErroHttp(400, "Informe o nome do cliente (escritório).");
  for (let tentativa = 0; tentativa < 5; tentativa++) {
    const chave = gerarChave();
    try {
      await env.LICENCAS.prepare(
        "INSERT INTO licencas (chave, cliente, cnpj, email, expira_em, observacao, ativa, criada_em) VALUES (?, ?, ?, ?, ?, ?, 1, ?)"
      ).bind(chave, campos.cliente, campos.cnpj || "", campos.email || "", campos.expira_em || null, campos.observacao || "", agora()).run();
      const lic = await env.LICENCAS.prepare("SELECT * FROM licencas WHERE chave = ?").bind(chave).first();
      return json({ licenca: lic }, 201);
    } catch (e) {
      if (!String(e).includes("UNIQUE")) throw e; // colisão de chave: tenta outra
    }
  }
  throw new ErroHttp(500, "Não foi possível gerar uma chave única.");
}

async function alterarLicenca(env, chave, d) {
  const campos = limparCampos(d);
  const nomes = Object.keys(campos);
  if (!nomes.length) throw new ErroHttp(400, "Nada para alterar.");
  const res = await env.LICENCAS.prepare(`UPDATE licencas SET ${nomes.map((n) => n + " = ?").join(", ")} WHERE chave = ?`)
    .bind(...nomes.map((n) => campos[n]), chave).run();
  if (!res.meta || !res.meta.changes) throw new ErroHttp(404, "Licença não encontrada.");
  const lic = await env.LICENCAS.prepare("SELECT * FROM licencas WHERE chave = ?").bind(chave).first();
  return json({ licenca: lic });
}

// ── verificação e download (servidor do cliente) ────────────────────────────
async function manifestoAtual(env) {
  const obj = await env.BUCKET.get("latest.json");
  if (!obj) throw new ErroHttp(404, "Nenhuma versão publicada ainda.");
  return obj.json();
}

async function verificar(request, env, url) {
  if (!env.LINK_SECRET) throw new ErroHttp(500, "LINK_SECRET não configurado no Worker.");
  const d = await corpo(request);
  const lic = await licencaValida(env, d.chave);
  const versaoAtual = RE_VERSAO.test(String(d.versao_atual || "")) ? d.versao_atual : "";
  const instalacao = String(d.instalacao || "").slice(0, 64);
  await env.LICENCAS.prepare(
    "UPDATE licencas SET ultimo_acesso = ?, versao_instalada = ?, instalacao = CASE WHEN ? = '' THEN instalacao ELSE ? END WHERE chave = ?"
  ).bind(agora(), versaoAtual, instalacao, instalacao, lic.chave).run();

  const man = await manifestoAtual(env);
  const exp = Math.floor(Date.now() / 1000) + VALIDADE_LINK_S;
  const sig = await hmac(`${man.versao}|${lic.chave}|${exp}`, env.LINK_SECRET);
  const link = new URL(`/v1/baixar/${man.versao}`, url.origin);
  link.searchParams.set("k", lic.chave);
  link.searchParams.set("exp", String(exp));
  link.searchParams.set("sig", sig);
  return json({
    versao: man.versao,
    sha256: man.sha256,
    tamanho: man.tamanho,
    notas: man.notas || "",
    publicada_em: man.publicada_em || "",
    url: link.toString(),
    licenca: { cliente: lic.cliente, expira_em: lic.expira_em },
  });
}

async function baixar(env, url, versao) {
  const k = url.searchParams.get("k") || "";
  const exp = Number(url.searchParams.get("exp") || 0);
  const sig = url.searchParams.get("sig") || "";
  if (!env.LINK_SECRET || !k || !exp || !sig) throw new ErroHttp(403, "Link de download inválido.");
  if (exp < Date.now() / 1000) throw new ErroHttp(403, "Link de download vencido. Clique em Verificar atualizações de novo.");
  if (!iguais(sig, await hmac(`${versao}|${k}|${exp}`, env.LINK_SECRET))) throw new ErroHttp(403, "Link de download inválido.");
  await licencaValida(env, k); // licença suspensa depois do link gerado também bloqueia

  const obj = await env.BUCKET.get(`versoes/${versao}/${NOME_SETUP}`);
  if (!obj) throw new ErroHttp(404, "Instalador desta versão não encontrado.");
  return new Response(obj.body, {
    headers: {
      "content-type": "application/octet-stream",
      "content-length": String(obj.size),
      "content-disposition": `attachment; filename="CortexERP-Setup-${versao}.exe"`,
      "cache-control": "no-store",
    },
  });
}

// ── publicação de versões (script lancar_versao.ps1) ────────────────────────
async function enviarArquivo(request, env, versao) {
  const sha = String(request.headers.get("x-sha256") || "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(sha)) throw new ErroHttp(400, "Envie o cabeçalho X-Sha256 com o SHA-256 do instalador.");
  if (!request.body) throw new ErroHttp(400, "Corpo vazio.");
  // o R2 confere o SHA-256 enquanto grava e recusa se o arquivo chegou diferente
  let obj;
  try {
    obj = await env.BUCKET.put(`versoes/${versao}/${NOME_SETUP}`, request.body, {
      sha256: sha,
      httpMetadata: { contentType: "application/octet-stream" },
      customMetadata: { sha256: sha, enviado_em: agora() },
    });
  } catch (e) {
    console.error(e);
    throw new ErroHttp(400, "O instalador chegou diferente do SHA-256 informado (envio corrompido). Nada foi gravado.");
  }
  return json({ ok: true, versao, tamanho: obj.size, sha256: sha });
}

async function publicarVersao(env, versao, d) {
  const sha = String(d.sha256 || "").toLowerCase();
  const head = await env.BUCKET.head(`versoes/${versao}/${NOME_SETUP}`);
  if (!head) throw new ErroHttp(400, `Envie primeiro o instalador da versão ${versao}.`);
  if ((head.customMetadata || {}).sha256 !== sha) throw new ErroHttp(400, "O SHA-256 informado não confere com o instalador enviado.");
  const man = {
    versao,
    sha256: sha,
    tamanho: head.size,
    notas: String(d.notas || "").slice(0, 20000),
    publicada_em: d.publicada_em || agora(),
    arquivo: NOME_SETUP,
  };
  const corpoJson = JSON.stringify(man, null, 2);
  const meta = { httpMetadata: { contentType: "application/json" } };
  await env.BUCKET.put(`versoes/${versao}/manifesto.json`, corpoJson, meta);
  await env.BUCKET.put("latest.json", corpoJson, meta);
  return json({ ok: true, manifesto: man });
}

async function listarVersoes(env) {
  const lista = await env.BUCKET.list({ prefix: "versoes/" });
  const versoes = {};
  for (const o of lista.objects) {
    const [, v, nome] = o.key.split("/");
    versoes[v] = versoes[v] || { versao: v };
    if (nome === NOME_SETUP) Object.assign(versoes[v], { tamanho: o.size, enviado_em: o.uploaded });
  }
  let atual = null;
  try { atual = (await manifestoAtual(env)).versao; } catch { /* nenhuma publicada */ }
  return json({ atual, versoes: Object.values(versoes).sort((a, b) => cmpVersao(b.versao, a.versao)) });
}

function cmpVersao(a, b) {
  const x = a.split(".").map(Number), y = b.split(".").map(Number);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] - y[i];
  return 0;
}
