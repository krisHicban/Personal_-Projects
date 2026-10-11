from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'vinted',
    category TEXT,
    size TEXT,
    condition TEXT,
    purchase_price REAL CHECK (purchase_price IS NULL OR purchase_price >= 0),
    listing_price REAL CHECK (listing_price IS NULL OR listing_price >= 0),
    sold_price REAL CHECK (sold_price IS NULL OR sold_price >= 0),
    shipping_cost REAL NOT NULL DEFAULT 0 CHECK (shipping_cost >= 0),
    platform_fee REAL NOT NULL DEFAULT 0 CHECK (platform_fee >= 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'listed', 'sold', 'reserved', 'archived')),
    listing_url TEXT,
    notes TEXT,
    sold_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

MIGRATIONS = {
    "platform": "ALTER TABLE items ADD COLUMN platform TEXT NOT NULL DEFAULT 'vinted'",
    "category": "ALTER TABLE items ADD COLUMN category TEXT",
    "size": "ALTER TABLE items ADD COLUMN size TEXT",
    "condition": "ALTER TABLE items ADD COLUMN condition TEXT",
    "purchase_price": "ALTER TABLE items ADD COLUMN purchase_price REAL CHECK (purchase_price IS NULL OR purchase_price >= 0)",
    "listing_price": "ALTER TABLE items ADD COLUMN listing_price REAL CHECK (listing_price IS NULL OR listing_price >= 0)",
    "status": "ALTER TABLE items ADD COLUMN status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'listed', 'sold', 'reserved', 'archived'))",
    "listing_url": "ALTER TABLE items ADD COLUMN listing_url TEXT",
    "notes": "ALTER TABLE items ADD COLUMN notes TEXT",
    "sold_at": "ALTER TABLE items ADD COLUMN sold_at TEXT",
    "created_at": "ALTER TABLE items ADD COLUMN created_at TEXT",
    "updated_at": "ALTER TABLE items ADD COLUMN updated_at TEXT",
    "sold_price": "ALTER TABLE items ADD COLUMN sold_price REAL CHECK (sold_price IS NULL OR sold_price >= 0)",
    "shipping_cost": "ALTER TABLE items ADD COLUMN shipping_cost REAL NOT NULL DEFAULT 0 CHECK (shipping_cost >= 0)",
    "platform_fee": "ALTER TABLE items ADD COLUMN platform_fee REAL NOT NULL DEFAULT 0 CHECK (platform_fee >= 0)",
}


class DatabaseConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def connect(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, factory=DatabaseConnection)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(items)")}
    for column, migration in MIGRATIONS.items():
        if column not in columns:
            connection.execute(migration)
    connection.execute(
        "UPDATE items SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
        "updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
    )
    connection.commit()
    return connection

