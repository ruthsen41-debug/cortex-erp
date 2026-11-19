-- Licenças dos escritórios (Cloudflare D1)
CREATE TABLE IF NOT EXISTS licencas (
  chave            TEXT PRIMARY KEY,          -- CTX-XXXX-XXXX-XXXX
  cliente          TEXT NOT NULL,             -- nome do escritório
  cnpj             TEXT NOT NULL DEFAULT '',
  email            TEXT NOT NULL DEFAULT '',
  ativa            INTEGER NOT NULL DEFAULT 1,
  expira_em        TEXT,                      -- AAAA-MM-DD; NULL = sem vencimento
  observacao       TEXT NOT NULL DEFAULT '',
  criada_em        TEXT NOT NULL,
  ultimo_acesso    TEXT,                      -- última vez que o servidor dele verificou
  versao_instalada TEXT NOT NULL DEFAULT '',
  instalacao       TEXT NOT NULL DEFAULT ''   -- id da instalação (para notar chave copiada)
);
