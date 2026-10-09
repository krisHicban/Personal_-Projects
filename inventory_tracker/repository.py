from __future__ import annotations

import sqlite3
from typing import Any


def add_item(connection: sqlite3.Connection, values: dict[str, Any]) -> int:
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    cursor = connection.execute(
        f"INSERT INTO items ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )
    connection.commit()
    return int(cursor.lastrowid)


def list_items(connection: sqlite3.Connection, status: str | None = None):
    if status:
        return connection.execute(
            "SELECT * FROM items WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    return connection.execute("SELECT * FROM items ORDER BY id DESC").fetchall()


def update_status(connection: sqlite3.Connection, item_id: int, status: str) -> bool:
    cursor = connection.execute(
        "UPDATE items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, item_id),
    )
    connection.commit()
    return cursor.rowcount == 1

