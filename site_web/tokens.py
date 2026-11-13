"""Tokens pessoais para acessar o site ligados ao telegram_id."""

import secrets
import sqlite3

import database.database as database


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(database.DB_FILE, timeout=10)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tokens_site "
            "(token TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL)"
        )
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


def criar_token(user_id: int) -> str:
    """Gera um token e invalida o link anterior do mesmo usuário."""
    token = secrets.token_urlsafe(32)
    conn = _conectar()
    try:
        with conn:
            conn.execute("DELETE FROM tokens_site WHERE telegram_id = ?", (user_id,))
            conn.execute(
                "INSERT INTO tokens_site (token, telegram_id) VALUES (?, ?)",
                (token, user_id),
            )
    finally:
        conn.close()
    return token


def usuario_do_token(token: str) -> int | None:
    conn = _conectar()
    try:
        linha = conn.execute(
            "SELECT telegram_id FROM tokens_site WHERE token = ?", (token,)
        ).fetchone()
        return linha[0] if linha else None
    finally:
        conn.close()
