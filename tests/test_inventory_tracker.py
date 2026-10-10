import csv
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from inventory_tracker.cli import main
from inventory_tracker.db import connect
from inventory_tracker.repository import (
    add_item,
    item_profit,
    profit_report,
    record_sale,
    update_item,
    update_status,
)


class InventoryTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "inventory.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_item_normalizes_text_and_lists_it(self) -> None:
        with connect(self.database) as connection:
            item_id = add_item(connection, {"title": "  Jacket  "})
            item = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

        self.assertEqual(item["title"], "Jacket")
        self.assertEqual(item["platform"], "vinted")
        self.assertEqual(item["status"], "draft")

    def test_repository_rejects_invalid_values(self) -> None:
        with connect(self.database) as connection:
            for values in (
                {"title": "  "},
                {"title": "Jacket", "platform": "  "},
                {"title": "Jacket", "listing_price": -1},
                {"title": "Jacket", "status": "unknown"},
                {"title": "Jacket", "unexpected": "value"},
            ):
                with self.subTest(values=values), self.assertRaises(ValueError):
                    add_item(connection, values)

    def test_status_update_rejects_invalid_status(self) -> None:
        with connect(self.database) as connection:
            item_id = add_item(connection, {"title": "Jacket"})
            with self.assertRaises(ValueError):
                update_status(connection, item_id, "unknown")

    def test_edit_item_updates_fields(self) -> None:
        with connect(self.database) as connection:
            item_id = add_item(connection, {"title": "Jacket", "listing_price": 20})
            self.assertTrue(update_item(connection, item_id, {"listing_price": 25.5}))
            item = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()

        self.assertEqual(item["title"], "Jacket")
        self.assertEqual(item["listing_price"], 25.5)

    def test_edit_item_rejects_empty_changes_and_missing_item(self) -> None:
        with connect(self.database) as connection:
            item_id = add_item(connection, {"title": "Jacket"})
            with self.assertRaises(ValueError):
                update_item(connection, item_id, {})
            self.assertFalse(update_item(connection, 999, {"title": "Missing"}))

    def test_cli_edit_updates_item(self) -> None:
        self.assertEqual(main(["--database", str(self.database), "add", "Jacket"]), 0)
        self.assertEqual(
            main(["--database", str(self.database), "edit", "1", "--listing-price", "30"]),
            0,
        )
        with connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT listing_price FROM items").fetchone()[0], 30)

    def test_cli_archive_preserves_item(self) -> None:
        self.assertEqual(main(["--database", str(self.database), "add", "Jacket"]), 0)
        self.assertEqual(main(["--database", str(self.database), "archive", "1"]), 0)
        with connect(self.database) as connection:
            item = connection.execute("SELECT title, status FROM items WHERE id = 1").fetchone()
        self.assertEqual(dict(item), {"title": "Jacket", "status": "archived"})

    def test_cli_archive_reports_missing_item(self) -> None:
        self.assertEqual(main(["--database", str(self.database), "archive", "999"]), 1)

    def test_record_sale_and_calculate_profit(self) -> None:
        with connect(self.database) as connection:
            item_id = add_item(connection, {"title": "Jacket", "purchase_price": 12})
            self.assertTrue(record_sale(connection, item_id, 40, 5, 4))
            item = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
            report = profit_report(connection)

        self.assertEqual(item["status"], "sold")
        self.assertEqual(item_profit(item), 19)
        self.assertEqual(report["realized_profit"], 19)
        self.assertEqual(report["revenue"], 40)

    def test_sale_requires_purchase_price_and_valid_active_item(self) -> None:
        with connect(self.database) as connection:
            item_id = add_item(connection, {"title": "Jacket"})
            with self.assertRaises(ValueError):
                record_sale(connection, item_id, 40)
            item_id = add_item(connection, {"title": "Hat", "purchase_price": 5})
            record_sale(connection, item_id, 10)
            with self.assertRaises(ValueError):
                record_sale(connection, item_id, 12)

    def test_cli_sell_profit_and_report(self) -> None:
        self.assertEqual(
            main([
                "--database", str(self.database), "add", "Jacket",
                "--purchase-price", "12",
            ]),
            0,
        )
        self.assertEqual(
            main([
                "--database", str(self.database), "sell", "1",
                "--price", "40", "--shipping", "5", "--fee", "4",
            ]),
            0,
        )
        self.assertEqual(main(["--database", str(self.database), "profit", "1"]), 0)
        self.assertEqual(main(["--database", str(self.database), "report"]), 0)

    def test_database_constraint_rejects_invalid_status(self) -> None:
        with connect(self.database) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO items (title, status) VALUES (?, ?)",
                    ("Jacket", "unknown"),
                )

    def test_legacy_database_gets_profit_columns(self) -> None:
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
            connection.execute("INSERT INTO items (title) VALUES ('Legacy jacket')")
            connection.commit()
        finally:
            connection.close()
        with connect(self.database) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(items)")}
            item = connection.execute("SELECT * FROM items").fetchone()

        self.assertTrue({"sold_price", "shipping_cost", "platform_fee", "sold_at"} <= columns)
        self.assertEqual(item["shipping_cost"], 0)
        self.assertEqual(item["platform_fee"], 0)

    def test_empty_csv_has_headers(self) -> None:
        output = Path(self.temp_dir.name) / "items.csv"
        self.assertEqual(main(["--database", str(self.database), "list", "--csv", str(output)]), 0)
        with output.open(newline="", encoding="utf-8") as file:
            rows = list(csv.reader(file))
        self.assertEqual(rows[0][0:3], ["id", "title", "platform"])
        self.assertEqual(len(rows), 1)

    def test_csv_cannot_overwrite_database(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(["--database", str(self.database), "list", "--csv", str(self.database)])
        self.assertEqual(result, 2)
        self.assertIn("must differ", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
