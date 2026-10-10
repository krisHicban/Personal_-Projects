from __future__ import annotations

import math
import sqlite3
from numbers import Real
from typing import Any


STATUSES = ("draft", "listed", "sold", "reserved", "archived")


def _validate_text(values: dict[str, Any], key: str, *, required: bool = False) -> None:
    if key not in values:
        if required:
            raise ValueError(f"{key} is required")
        return
    value = values[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    values[key] = value.strip()
    if required and not values[key]:
        raise ValueError(f"{key} must not be empty")
    if not required and not values[key]:
        values[key] = None


def _validate_price(values: dict[str, Any], key: str) -> None:
    if key not in values or values[key] is None:
        return
    value = values[key]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{key} must be a non-negative number")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be a non-negative finite number")
    values[key] = value


def add_item(connection: sqlite3.Connection, values: dict[str, Any]) -> int:
    values = dict(values)
    allowed = {
        "title", "platform", "category", "size", "condition",
        "purchase_price", "listing_price", "status", "listing_url", "notes",
    }
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown item field(s): {', '.join(sorted(unknown))}")
    _validate_text(values, "title", required=True)
    if "platform" in values:
        _validate_text(values, "platform", required=True)
    for key in ("category", "size", "condition", "listing_url", "notes"):
        _validate_text(values, key)
    _validate_price(values, "purchase_price")
    _validate_price(values, "listing_price")
    if "status" in values and values["status"] not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")

    cursor = connection.execute(
        """INSERT INTO items (
            title, platform, category, size, condition, purchase_price,
            listing_price, status, listing_url, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            values["title"], values.get("platform", "vinted"), values.get("category"),
            values.get("size"), values.get("condition"), values.get("purchase_price"),
            values.get("listing_price"), values.get("status", "draft"),
            values.get("listing_url"), values.get("notes"),
        ),
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
    if status not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
    cursor = connection.execute(
        "UPDATE items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, item_id),
    )
    connection.commit()
    return cursor.rowcount == 1

