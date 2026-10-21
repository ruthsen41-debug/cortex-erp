"""
Cortex ERP – Backup Automatizado (Disaster Recovery)
=====================================================
Uso:
    python scripts/backup.py                  # backup completo (SQLite ou PostgreSQL)
    python scripts/backup.py --keep 14        # mantém os últimos 14 backups (padrão: 7)
    python scripts/backup.py --dest /mnt/nas  # diretório de destino customizado

Agendamento (Linux):
    crontab -e
    0 2 * * * /usr/bin/python3 /app/scripts/backup.py --keep 14 >> /app/data/backup.log 2>&1

Agendamento (Windows – Task Scheduler):
    schtasks /Create /TN "CortexERP_Backup" /TR "python C:\...\scripts\backup.py" /SC DAILY /ST 02:00
"""

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_BACKUP_DIR = DATA_DIR / "backups"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _compress(src: Path, dst: Path) -> None:
    """Comprime src com gzip e salva em dst."""
    with open(src, "rb") as f_in, gzip.open(dst, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)


def backup_sqlite(backup_dir: Path) -> Path:
    """Copia o banco SQLite para o diretório de backup usando a API de backup do sqlite3."""
    import sqlite3

    db_path = Path(os.environ.get("DB_PATH", str(DATA_DIR / "cortex_erp.db")))
    if not db_path.exists():
        raise FileNotFoundError(f"Banco de dados não encontrado: {db_path}")

    dest_raw = backup_dir / f"cortex_erp_{TIMESTAMP}.db"
    dest_gz  = backup_dir / f"cortex_erp_{TIMESTAMP}.db.gz"

    _log(f"Iniciando backup SQLite: {db_path}")
    src_conn = sqlite3.connect(str(db_path), check_same_thread=False)
    dst_conn = sqlite3.connect(str(dest_raw))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    _log(f"Comprimindo → {dest_gz.name}")
    _compress(dest_raw, dest_gz)
    dest_raw.unlink()

    size_kb = dest_gz.stat().st_size // 1024
    _log(f"Backup SQLite concluído: {dest_gz.name} ({size_kb} KB)")
    return dest_gz


def backup_postgres(backup_dir: Path, db_url: str) -> Path:
    """Executa pg_dump e comprime o resultado."""
    import urllib.parse

    parsed = urllib.parse.urlparse(db_url)
    host   = parsed.hostname or "localhost"
    port   = parsed.port or 5432
    user   = parsed.username or "cortex"
    dbname = parsed.path.lstrip("/") or "cortex"

    dest_sql = backup_dir / f"cortex_erp_{TIMESTAMP}.sql"
    dest_gz  = backup_dir / f"cortex_erp_{TIMESTAMP}.sql.gz"

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    cmd = [
        "pg_dump",
        "-h", host,
        "-p", str(port),
        "-U", user,
        "-d", dbname,
        "-f", str(dest_sql),
        "--no-owner",
        "--no-acl",
    ]

    _log(f"Iniciando pg_dump: {user}@{host}:{port}/{dbname}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump falhou:\n{result.stderr}")

    _log(f"Comprimindo → {dest_gz.name}")
    _compress(dest_sql, dest_gz)
    dest_sql.unlink()

    size_kb = dest_gz.stat().st_size // 1024
    _log(f"Backup PostgreSQL concluído: {dest_gz.name} ({size_kb} KB)")
    return dest_gz


def rotate_backups(backup_dir: Path, keep: int) -> None:
    """Remove backups antigos mantendo apenas os últimos `keep` arquivos."""
    files = sorted(
        backup_dir.glob("cortex_erp_*_*.gz"),
        key=lambda p: p.stat().st_mtime,
    )
    to_delete = files[:-keep] if len(files) > keep else []
    for f in to_delete:
        f.unlink()
        _log(f"Removido backup antigo: {f.name}")
    if to_delete:
        _log(f"Rotação concluída: {len(to_delete)} arquivo(s) removido(s), {keep} mantido(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup do banco de dados Cortex ERP")
    parser.add_argument("--keep", type=int, default=7, help="Número de backups a manter (padrão: 7)")
    parser.add_argument("--dest", type=str, default="", help="Diretório de destino do backup")
    args = parser.parse_args()

    backup_dir = Path(args.dest) if args.dest else DEFAULT_BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_url = os.environ.get("DATABASE_URL", "").strip()

    try:
        if db_url.startswith(("postgres://", "postgresql://")):
            backup_postgres(backup_dir, db_url)
        else:
            backup_sqlite(backup_dir)

        rotate_backups(backup_dir, args.keep)
        _log("Backup finalizado com sucesso.")
    except Exception as exc:
        _log(f"ERRO no backup: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
