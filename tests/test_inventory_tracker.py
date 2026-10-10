import csv
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from inventory_tracker.cli import main
from inventory_tracker.db import connect
from inventory_tracker.repository import add_item, update_status


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

    def test_database_constraint_rejects_invalid_status(self) -> None:
        with connect(self.database) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO items (title, status) VALUES (?, ?)",
                    ("Jacket", "unknown"),
                )

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
