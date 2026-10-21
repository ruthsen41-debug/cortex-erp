"""Camada de compatibilidade PostgreSQL para o SQL escrito no dialeto SQLite.

O codigo da aplicacao usa a API do ``sqlite3`` (``conn.execute``, ``cur.lastrowid``,
``row["coluna"]``, placeholders ``?``). Quando ``DATABASE_URL`` aponta para um
PostgreSQL, ``get_conn()`` devolve um :class:`PgConnection`, que expoe a mesma
interface e traduz o SQL na hora. Com SQLite (padrao) nada aqui e usado.
"""
import re
import threading

try:  # psycopg so e necessario quando DATABASE_URL e PostgreSQL
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

# --------------------------------------------------------------------------- #
# Linhas (equivalente ao sqlite3.Row)
# --------------------------------------------------------------------------- #


class PgRow:
    """Linha acessivel por indice, por nome e via ``dict(row)``."""

    __slots__ = ("_names", "_values")

    def __init__(self, names, values):
        self._names = names
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._names.index(key)]
        except ValueError:
            raise IndexError(f"No item with that key: {key}") from None

    def keys(self):
        return list(self._names)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"PgRow({dict(zip(self._names, self._values))})"


def _row_factory(cursor):
    names = [c.name for c in (cursor.description or [])]

    def make(values):
        return PgRow(names, tuple(values))

    return make


# --------------------------------------------------------------------------- #
# Traducao de SQL (SQLite -> PostgreSQL)
# --------------------------------------------------------------------------- #

_TOKEN = re.compile(r"""('(?:[^']|'')*')|(--[^\n]*)|(\?)|(%)""")


def _convert_tokens(sql: str, has_params: bool) -> str:
    """Troca ``?`` por ``%s``, remove comentarios ``--`` e escapa ``%`` literal."""

    def repl(m):
        literal, comment, qmark, percent = m.groups()
        if literal is not None:
            return literal.replace("%", "%%") if has_params else literal
        if comment is not None:
            return ""
        if qmark is not None:
            return "%s"
        return "%%" if has_params else "%"

    return _TOKEN.sub(repl, sql)


_RE_PRAGMA_TABLE_INFO = re.compile(r"^\s*PRAGMA\s+table_info\(\s*['\"]?(\w+)['\"]?\s*\)\s*;?\s*$", re.I)
_RE_PRAGMA = re.compile(r"^\s*PRAGMA\b", re.I)
_RE_INSERT = re.compile(r"^\s*INSERT\s+(?:OR\s+(IGNORE|REPLACE)\s+)?INTO\s+(\w+)", re.I)
_RE_RETURNING = re.compile(r"\bRETURNING\b", re.I)


def _translate_ddl(sql: str) -> str:
    if not re.match(r"^\s*(CREATE|ALTER)\b", sql, re.I):
        return sql
    sql = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "SERIAL PRIMARY KEY", sql, flags=re.I)
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.I)
    sql = re.sub(
        r"\bDEFAULT\s+CURRENT_TIMESTAMP\b",
        "DEFAULT (to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'))",
        sql,
        flags=re.I,
    )
    return sql


def _translate_functions(sql: str) -> str:
    sql = re.sub(r"date\(\s*'now'\s*\)", "to_char(CURRENT_DATE, 'YYYY-MM-DD')", sql, flags=re.I)
    sql = re.sub(
        r"datetime\(\s*'now'\s*\)",
        "to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')",
        sql,
        flags=re.I,
    )
    sql = re.sub(r"\bIFNULL\(", "COALESCE(", sql, flags=re.I)
    return sql


# --------------------------------------------------------------------------- #
# Conexao / cursor
# --------------------------------------------------------------------------- #

_tables_with_id = None
_tables_lock = threading.Lock()


class PgCursor:
    def __init__(self, conn: "PgConnection"):
        self._conn = conn
        self._cur = conn._raw.cursor(row_factory=_row_factory)
        self.lastrowid = None

    # -- helpers -------------------------------------------------------------
    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def _table_has_id(self, table: str) -> bool:
        global _tables_with_id
        if _tables_with_id is None:
            with _tables_lock:
                with self._conn._raw.cursor() as c:
                    c.execute(
                        "SELECT table_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND column_name = 'id'"
                    )
                    _tables_with_id = {r[0] for r in c.fetchall()}
        return table.lower() in _tables_with_id

    def execute(self, sql, params=None):
        global _tables_with_id
        params = tuple(params) if params is not None else ()
        stripped = sql.strip()

        m = _RE_PRAGMA_TABLE_INFO.match(stripped)
        if m:
            self._cur.execute(
                "SELECT ordinal_position - 1 AS cid, column_name AS name, data_type AS type, "
                "CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull, "
                "column_default AS dflt_value, 0 AS pk "
                "FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position",
                (m.group(1).lower(),),
            )
            return self
        if _RE_PRAGMA.match(stripped):  # PRAGMA foreign_keys etc.: nao se aplica
            self._cur.execute("SELECT 1 WHERE false")
            return self

        out = _translate_ddl(_translate_functions(sql))
        ins = _RE_INSERT.match(out)
        want_id = False
        if ins:
            mode, table = ins.group(1), ins.group(2)
            if mode:  # INSERT OR IGNORE / OR REPLACE
                out = _RE_INSERT.sub(f"INSERT INTO {table}", out, count=1)
                if mode.upper() == "IGNORE":
                    out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
            if not _RE_RETURNING.search(out) and self._table_has_id(table):
                out = out.rstrip().rstrip(";") + " RETURNING id"
                want_id = True
        out = _convert_tokens(out, bool(params))

        try:
            self._cur.execute(out, params if params else None)
        except Exception as exc:
            raise _wrap_error(exc) from exc
        if re.match(r"^\s*CREATE\s+TABLE", out, re.I):
            _tables_with_id = None  # recalcula quando necessario
        self.lastrowid = None
        if want_id:
            row = self._cur.fetchone()
            self.lastrowid = row[0] if row else None
        return self

    def executemany(self, sql, seq):
        for params in seq:
            self.execute(sql, params)
        return self

    def fetchone(self):
        if self._cur.description is None:
            return None
        return self._cur.fetchone()

    def fetchall(self):
        if self._cur.description is None:
            return []
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self.fetchall())

    def close(self):
        self._cur.close()


class IntegrityError(Exception):
    """Equivalente a sqlite3.IntegrityError para o backend PostgreSQL."""


def _wrap_error(exc):
    if psycopg is not None and isinstance(exc, psycopg.errors.IntegrityError):
        return IntegrityError(str(exc))
    return exc


class PgConnection:
    def __init__(self, url: str):
        if psycopg is None:
            raise RuntimeError("DATABASE_URL aponta para PostgreSQL, mas o pacote 'psycopg' nao esta instalado.")
        self._raw = psycopg.connect(url)

    @property
    def in_transaction(self) -> bool:
        return self._raw.info.transaction_status != psycopg.pq.TransactionStatus.IDLE

    def cursor(self):
        return PgCursor(self)

    def execute(self, sql, params=None):
        return PgCursor(self).execute(sql, params)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False
