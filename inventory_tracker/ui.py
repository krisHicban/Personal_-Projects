from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .cli import DEFAULT_DATABASE, STATUSES
from .db import connect
from .repository import add_item, list_items, update_status


class InventoryApp(tk.Tk):
    def __init__(self, database: Path = DEFAULT_DATABASE) -> None:
        super().__init__()
        self.database = database
        self.title("Inventory Tracker")
        self.geometry("920x560")
        self.minsize(760, 450)

        self.title_value = tk.StringVar()
        self.platform_value = tk.StringVar(value="vinted")
        self.category_value = tk.StringVar()
        self.size_value = tk.StringVar()
        self.condition_value = tk.StringVar()
        self.purchase_price_value = tk.StringVar()
        self.listing_price_value = tk.StringVar()
        self.status_value = tk.StringVar(value="draft")
        self.url_value = tk.StringVar()
        self.notes_value = tk.StringVar()
        self.filter_value = tk.StringVar(value="all")

        self._build_form()
        self._build_table()
        self.refresh_items()

    def _build_form(self) -> None:
        form = ttk.LabelFrame(self, text="Add inventory item", padding=10)
        form.pack(fill="x", padx=12, pady=(12, 6))

        fields = [
            ("Title", self.title_value, 0, 0),
            ("Platform", self.platform_value, 0, 2),
            ("Category", self.category_value, 0, 4),
            ("Size", self.size_value, 1, 0),
            ("Condition", self.condition_value, 1, 2),
            ("Purchase price", self.purchase_price_value, 1, 4),
            ("Listing price", self.listing_price_value, 2, 0),
            ("Listing URL", self.url_value, 2, 2),
            ("Notes", self.notes_value, 2, 4),
        ]
        for label, variable, row, column in fields:
            ttk.Label(form, text=label).grid(row=row, column=column, sticky="w", padx=4, pady=3)
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=row, column=column + 1, sticky="ew", padx=4, pady=3)

        for column in (1, 3, 5):
            form.columnconfigure(column, weight=1)

        ttk.Button(form, text="Add item", command=self.add_current_item).grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 0)
        )
        ttk.Label(form, text="Initial status").grid(row=3, column=2, sticky="w", padx=4, pady=(8, 0))
        ttk.Combobox(
            form, textvariable=self.status_value, values=STATUSES, state="readonly", width=12
        ).grid(row=3, column=3, sticky="w", padx=4, pady=(8, 0))

    def _build_table(self) -> None:
        controls = ttk.Frame(self, padding=(12, 6, 12, 0))
        controls.pack(fill="x")
        ttk.Label(controls, text="Filter status").pack(side="left")
        filter_box = ttk.Combobox(
            controls,
            textvariable=self.filter_value,
            values=("all", *STATUSES),
            state="readonly",
            width=12,
        )
        filter_box.pack(side="left", padx=8)
        filter_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_items())
        ttk.Button(controls, text="Refresh", command=self.refresh_items).pack(side="left")

        table_frame = ttk.Frame(self, padding=12)
        table_frame.pack(fill="both", expand=True)
        columns = ("id", "status", "platform", "title", "category", "size", "price")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "id": "ID", "status": "Status", "platform": "Platform", "title": "Title",
            "category": "Category", "size": "Size", "price": "Price",
        }
        widths = {"id": 45, "status": 85, "platform": 90, "title": 240, "category": 110, "size": 70, "price": 80}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], anchor="w")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(self, padding=(12, 0, 12, 12))
        actions.pack(fill="x")
        ttk.Label(actions, text="Set selected item status:").pack(side="left")
        self.selected_status = tk.StringVar(value="listed")
        ttk.Combobox(
            actions, textvariable=self.selected_status, values=STATUSES, state="readonly", width=12
        ).pack(side="left", padx=8)
        ttk.Button(actions, text="Update status", command=self.change_selected_status).pack(side="left")

    def add_current_item(self) -> None:
        if not self.title_value.get().strip():
            messagebox.showwarning("Missing title", "Please enter an item title.")
            return
        try:
            values = {
                "title": self.title_value.get().strip(),
                "platform": self.platform_value.get().strip() or "vinted",
                "category": self.category_value.get().strip() or None,
                "size": self.size_value.get().strip() or None,
                "condition": self.condition_value.get().strip() or None,
                "purchase_price": self._price(self.purchase_price_value.get()),
                "listing_price": self._price(self.listing_price_value.get()),
                "status": self.status_value.get(),
                "listing_url": self.url_value.get().strip() or None,
                "notes": self.notes_value.get().strip() or None,
            }
        except ValueError:
            messagebox.showerror("Invalid price", "Prices must be numbers, for example 24.99.")
            return
        try:
            with connect(self.database) as connection:
                item_id = add_item(
                    connection,
                    {key: value for key, value in values.items() if value is not None},
                )
        except (OSError, ValueError) as error:
            messagebox.showerror("Invalid item", str(error))
            return
        self._clear_form()
        self.refresh_items()
        messagebox.showinfo("Item added", f"Added item #{item_id}.")

    @staticmethod
    def _price(value: str) -> float | None:
        if not value.strip():
            return None
        price = float(value)
        if not math.isfinite(price) or price < 0:
            raise ValueError
        return price

    def _clear_form(self) -> None:
        for variable in (
            self.title_value, self.category_value, self.size_value, self.condition_value,
            self.purchase_price_value, self.listing_price_value, self.url_value, self.notes_value,
        ):
            variable.set("")
        self.status_value.set("draft")

    def refresh_items(self) -> None:
        status = self.filter_value.get()
        with connect(self.database) as connection:
            items = list_items(connection, None if status == "all" else status)
        for row in self.table.get_children():
            self.table.delete(row)
        for item in items:
            price = "" if item["listing_price"] is None else f"{item['listing_price']:.2f}"
            self.table.insert(
                "", "end", iid=str(item["id"]),
                values=(item["id"], item["status"], item["platform"], item["title"],
                        item["category"] or "", item["size"] or "", price),
            )

    def change_selected_status(self) -> None:
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select an item first.")
            return
        item_id = int(selected[0])
        with connect(self.database) as connection:
            update_status(connection, item_id, self.selected_status.get())
        self.refresh_items()


def main() -> None:
    InventoryApp().mainloop()


if __name__ == "__main__":
    main()

