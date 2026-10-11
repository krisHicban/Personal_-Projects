from __future__ import annotations

import math
import csv
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .cli import CSV_FIELDS, DEFAULT_DATABASE, STATUSES
from .db import connect
from .repository import (
    add_item,
    item_profit,
    list_items,
    profit_report,
    record_sale,
    update_item,
    update_status,
)


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
        self.search_value = tk.StringVar()
        self.platform_filter_value = tk.StringVar(value="all")
        self.sort_column = "id"
        self.sort_reverse = True
        self.visible_items = []

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
        ttk.Label(controls, text="Search").pack(side="left")
        search = ttk.Entry(controls, textvariable=self.search_value, width=22)
        search.pack(side="left", padx=(6, 12))
        search.bind("<KeyRelease>", lambda _event: self.refresh_items())
        ttk.Label(controls, text="Status").pack(side="left")
        filter_box = ttk.Combobox(
            controls,
            textvariable=self.filter_value,
            values=("all", *STATUSES),
            state="readonly",
            width=12,
        )
        filter_box.pack(side="left", padx=8)
        filter_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_items())
        ttk.Label(controls, text="Platform").pack(side="left")
        self.platform_box = ttk.Combobox(
            controls, textvariable=self.platform_filter_value,
            values=("all", "vinted"), state="readonly", width=12,
        )
        self.platform_box.pack(side="left", padx=8)
        self.platform_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_items())
        ttk.Button(controls, text="Refresh", command=self.refresh_items).pack(side="left")
        ttk.Button(controls, text="Export CSV", command=self.export_csv).pack(side="left", padx=6)
        ttk.Button(controls, text="Profit report", command=self.show_profit_report).pack(side="left")

        table_frame = ttk.Frame(self, padding=12)
        table_frame.pack(fill="both", expand=True)
        columns = ("id", "status", "platform", "title", "category", "size", "price", "profit")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "id": "ID", "status": "Status", "platform": "Platform", "title": "Title",
            "category": "Category", "size": "Size", "price": "Listing price", "profit": "Profit",
        }
        widths = {"id": 45, "status": 85, "platform": 90, "title": 210, "category": 100, "size": 65, "price": 90, "profit": 80}
        for column in columns:
            self.table.heading(column, text=headings[column], command=lambda key=column: self.sort_by(key))
            self.table.column(column, width=widths[column], anchor="w")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(self, padding=(12, 0, 12, 12))
        actions.pack(fill="x")
        ttk.Label(actions, text="Set selected item status:").pack(side="left")
        self.selected_status = tk.StringVar(value="listed")
        self.sold_price_value = tk.StringVar()
        self.shipping_cost_value = tk.StringVar(value="0")
        self.platform_fee_value = tk.StringVar(value="0")
        self.report_value = tk.StringVar()
        ttk.Combobox(
            actions, textvariable=self.selected_status, values=STATUSES, state="readonly", width=12
        ).pack(side="left", padx=8)
        ttk.Button(actions, text="Update status", command=self.change_selected_status).pack(side="left")
        ttk.Button(actions, text="Edit item", command=self.edit_selected_item).pack(side="left", padx=6)

        ttk.Label(actions, text="Sale price").pack(side="left", padx=(18, 4))
        ttk.Entry(actions, textvariable=self.sold_price_value, width=10).pack(side="left")
        ttk.Label(actions, text="Shipping").pack(side="left", padx=(8, 4))
        ttk.Entry(actions, textvariable=self.shipping_cost_value, width=8).pack(side="left")
        ttk.Label(actions, text="Fee").pack(side="left", padx=(8, 4))
        ttk.Entry(actions, textvariable=self.platform_fee_value, width=8).pack(side="left")
        ttk.Button(actions, text="Record sale", command=self.record_selected_sale).pack(side="left", padx=8)

        report_frame = ttk.Frame(self, padding=(12, 0, 12, 8))
        report_frame.pack(fill="x")
        ttk.Button(report_frame, text="Refresh profit report", command=self.refresh_report).pack(side="left")
        ttk.Label(report_frame, textvariable=self.report_value).pack(side="left", padx=12)

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
        platforms = ("all", *sorted({item["platform"] for item in items if item["platform"]}))
        self.platform_box.configure(values=platforms)
        if self.platform_filter_value.get() not in platforms:
            self.platform_filter_value.set("all")
        platform = self.platform_filter_value.get()
        search = self.search_value.get().strip().casefold()
        items = [
            item for item in items
            if (platform == "all" or item["platform"] == platform)
            and (not search or search in " ".join(
                str(item[field] or "") for field in ("title", "category", "platform", "size")
            ).casefold())
        ]
        if self.sort_column == "profit":
            items.sort(
                key=lambda item: (item_profit(item) is None, item_profit(item) or 0),
                reverse=self.sort_reverse,
            )
        else:
            items.sort(key=lambda item: (item[self.sort_column] is None, item[self.sort_column]), reverse=self.sort_reverse)
        self.visible_items = items
        for row in self.table.get_children():
            self.table.delete(row)
        for item in items:
            price = "" if item["listing_price"] is None else f"{item['listing_price']:.2f}"
            profit = item_profit(item)
            profit_text = "" if profit is None else f"{profit:.2f}"
            self.table.insert(
                "", "end", iid=str(item["id"]),
                values=(item["id"], item["status"], item["platform"], item["title"],
                        item["category"] or "", item["size"] or "", price, profit_text),
            )
        self.refresh_report()

    def sort_by(self, column: str) -> None:
        if column == "price":
            column = "listing_price"
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.refresh_items()

    def _selected_item_id(self) -> int | None:
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select an item first.")
            return None
        return int(selected[0])

    def export_csv(self) -> None:
        if not self.visible_items:
            messagebox.showinfo("Export CSV", "There are no matching items to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export inventory CSV", defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not path:
            return
        output = Path(path)
        if output.resolve() == self.database.resolve():
            messagebox.showerror("Invalid export", "The CSV path must differ from the database path.")
            return
        with output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            rows = []
            for item in self.visible_items:
                row = dict(item)
                profit = item_profit(item)
                row["profit"] = "" if profit is None else f"{profit:.2f}"
                rows.append(row)
            writer.writerows(rows)
        messagebox.showinfo("Export complete", f"Exported {len(self.visible_items)} item(s).")

    def edit_selected_item(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        with connect(self.database) as connection:
            item = connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if item is None:
            messagebox.showerror("Missing item", f"Item #{item_id} was not found.")
            return

        window = tk.Toplevel(self)
        window.title(f"Edit item #{item_id}")
        window.transient(self)
        window.grab_set()
        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        values = {
            field: tk.StringVar(value="" if item[field] is None else str(item[field]))
            for field in ("title", "platform", "category", "size", "condition",
                          "purchase_price", "listing_price", "listing_url", "notes")
        }
        fields = (
            ("Title", "title"), ("Platform", "platform"), ("Category", "category"),
            ("Size", "size"), ("Condition", "condition"), ("Purchase price", "purchase_price"),
            ("Listing price", "listing_price"), ("Listing URL", "listing_url"), ("Notes", "notes"),
        )
        for row, (label, field) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(frame, textvariable=values[field], width=38).grid(
                row=row, column=1, sticky="ew", padx=4, pady=3
            )
        status = tk.StringVar(value=item["status"])
        ttk.Label(frame, text="Status").grid(row=len(fields), column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(frame, textvariable=status, values=STATUSES, state="readonly", width=35).grid(
            row=len(fields), column=1, sticky="ew", padx=4, pady=3
        )
        frame.columnconfigure(1, weight=1)

        def save() -> None:
            try:
                changes = {
                    field: values[field].get().strip() or None
                    for field in ("platform", "category", "size", "condition", "listing_url", "notes")
                }
                changes["title"] = values["title"].get().strip()
                if not changes["title"]:
                    raise ValueError("title must not be empty")
                changes["purchase_price"] = self._price(values["purchase_price"].get())
                changes["listing_price"] = self._price(values["listing_price"].get())
                changes["status"] = status.get()
                with connect(self.database) as connection:
                    if not update_item(connection, item_id, changes):
                        raise ValueError(f"Item #{item_id} was not found")
            except (OSError, ValueError) as error:
                messagebox.showerror("Could not save item", str(error), parent=window)
                return
            window.destroy()
            self.refresh_items()

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save changes", command=save).pack(side="left", padx=4)

    def show_profit_report(self) -> None:
        with connect(self.database) as connection:
            report = profit_report(connection)
        window = tk.Toplevel(self)
        window.title("Inventory Profit Report")
        window.transient(self)
        window.grab_set()
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Inventory Profit Report", font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 12))
        labels = (
            ("Total items", "items"), ("Sold items", "sold_items"),
            ("Purchase cost", "purchase_cost"), ("Sales revenue", "revenue"),
            ("Shipping costs", "shipping"), ("Platform fees", "fees"),
            ("Realized profit", "realized_profit"), ("Estimated active profit", "estimated_profit"),
        )
        for label, key in labels:
            value = report[key] if key in ("items", "sold_items") else f"{report[key]:.2f}"
            ttk.Label(frame, text=f"{label}: {value}").pack(anchor="w", pady=2)
        ttk.Button(frame, text="Close", command=window.destroy).pack(anchor="e", pady=(12, 0))

    def change_selected_status(self) -> None:
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select an item first.")
            return
        if self.selected_status.get() == "sold":
            messagebox.showinfo(
                "Record sale",
                "Use the Sale price, Shipping, Fee, and Record sale controls to mark an item sold.",
            )
            return
        item_id = int(selected[0])
        with connect(self.database) as connection:
            update_status(connection, item_id, self.selected_status.get())
        self.refresh_items()

    def record_selected_sale(self) -> None:
        selected = self.table.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select an item first.")
            return
        try:
            sold_price = self._price(self.sold_price_value.get())
            shipping = self._price(self.shipping_cost_value.get()) or 0
            fee = self._price(self.platform_fee_value.get()) or 0
            if sold_price is None:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid sale", "Sale price, shipping, and fee must be non-negative numbers.")
            return
        item_id = int(selected[0])
        try:
            with connect(self.database) as connection:
                if not record_sale(connection, item_id, sold_price, shipping, fee):
                    messagebox.showerror("Missing item", f"Item #{item_id} was not found.")
                    return
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not record sale", str(error))
            return
        self.sold_price_value.set("")
        self.shipping_cost_value.set("0")
        self.platform_fee_value.set("0")
        self.refresh_items()
        messagebox.showinfo("Sale recorded", f"Recorded sale for item #{item_id}.")

    def refresh_report(self) -> None:
        with connect(self.database) as connection:
            report = profit_report(connection)
        self.report_value.set(
            f"Realized: {report['realized_profit']:.2f}  |  "
            f"Estimated active: {report['estimated_profit']:.2f}"
        )


def main() -> None:
    InventoryApp().mainloop()


if __name__ == "__main__":
    main()

