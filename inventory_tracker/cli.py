from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

from .db import connect
from .repository import (
    STATUSES,
    add_item,
    get_item,
    item_profit,
    list_items,
    profit_report,
    record_sale,
    update_item,
    update_status,
)


DEFAULT_DATABASE = Path("inventory.db")
CSV_FIELDS = (
    "id", "title", "platform", "category", "size", "condition",
    "purchase_price", "listing_price", "sold_price", "shipping_cost",
    "platform_fee", "status", "listing_url", "notes", "created_at", "updated_at", "sold_at",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track items listed on resale platforms.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Add an item to inventory")
    add.add_argument("title")
    add.add_argument("--platform", default="vinted")
    add.add_argument("--category")
    add.add_argument("--size")
    add.add_argument("--condition")
    add.add_argument("--purchase-price", type=float)
    add.add_argument("--listing-price", type=float)
    add.add_argument("--status", choices=STATUSES, default="draft")
    add.add_argument("--url", dest="listing_url")
    add.add_argument("--notes")

    listing = commands.add_parser("list", help="List inventory items")
    listing.add_argument("--status", choices=STATUSES)
    listing.add_argument("--csv", type=Path, metavar="FILE")

    status = commands.add_parser("status", help="Change an item's status")
    status.add_argument("item_id", type=int)
    status.add_argument("value", choices=STATUSES)

    archive = commands.add_parser("archive", help="Archive an inventory item")
    archive.add_argument("item_id", type=int)

    sell = commands.add_parser("sell", help="Record a sale")
    sell.add_argument("item_id", type=int)
    sell.add_argument("--price", type=float, required=True, dest="sold_price")
    sell.add_argument("--shipping", type=float, default=0, dest="shipping_cost")
    sell.add_argument("--fee", type=float, default=0, dest="platform_fee")

    profit = commands.add_parser("profit", help="Show profit for an item")
    profit.add_argument("item_id", type=int)

    commands.add_parser("report", help="Show an inventory profit report")

    edit = commands.add_parser("edit", help="Edit an inventory item")
    edit.add_argument("item_id", type=int)
    edit.add_argument("--title")
    edit.add_argument("--platform")
    edit.add_argument("--category")
    edit.add_argument("--size")
    edit.add_argument("--condition")
    edit.add_argument("--purchase-price", type=float)
    edit.add_argument("--listing-price", type=float)
    edit.add_argument("--status", choices=STATUSES)
    edit.add_argument("--url", dest="listing_url")
    edit.add_argument("--notes")
    return parser


def print_items(items) -> None:
    if not items:
        print("No inventory items found.")
        return
    print(f"{'ID':>3}  {'Status':<9} {'Platform':<10} {'Title':<32} {'Price':>8}")
    print("-" * 70)
    for item in items:
        price = "" if item["listing_price"] is None else f"{item['listing_price']:.2f}"
        print(
            f"{item['id']:>3}  {item['status']:<9} {item['platform']:<10} "
            f"{item['title'][:32]:<32} {price:>8}"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list" and args.csv:
            if args.csv.resolve() == args.database.resolve():
                print("CSV output path must differ from the database path.", file=sys.stderr)
                return 2
        with connect(args.database) as connection:
            if args.command == "add":
                values = {
                    key: value.strip() if isinstance(value, str) else value
                    for key, value in vars(args).items()
                    if key in {
                        "title", "platform", "category", "size", "condition",
                        "purchase_price", "listing_price", "status", "listing_url", "notes",
                    }
                    and value is not None
                }
                item_id = add_item(connection, values)
                print(f"Added item #{item_id}: {values['title']}")
            elif args.command == "list":
                items = list_items(connection, args.status)
                if args.csv:
                    with args.csv.open("w", newline="", encoding="utf-8") as output:
                        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
                        writer.writeheader()
                        writer.writerows(dict(item) for item in items)
                    print(f"Exported {len(items)} item(s) to {args.csv}")
                else:
                    print_items(items)
            elif args.command == "status":
                if not update_status(connection, args.item_id, args.value):
                    print(f"Item #{args.item_id} was not found.", file=sys.stderr)
                    return 1
                print(f"Updated item #{args.item_id} to {args.value}.")
            elif args.command == "archive":
                if not update_status(connection, args.item_id, "archived"):
                    print(f"Item #{args.item_id} was not found.", file=sys.stderr)
                    return 1
                print(f"Archived item #{args.item_id}.")
            elif args.command == "sell":
                if not record_sale(
                    connection, args.item_id, args.sold_price,
                    args.shipping_cost, args.platform_fee,
                ):
                    print(f"Item #{args.item_id} was not found.", file=sys.stderr)
                    return 1
                print(f"Recorded sale for item #{args.item_id}.")
            elif args.command == "profit":
                item = get_item(connection, args.item_id)
                if item is None:
                    print(f"Item #{args.item_id} was not found.", file=sys.stderr)
                    return 1
                profit = item_profit(item)
                if profit is None:
                    print("Profit cannot be calculated until purchase and sale/listing prices are set.", file=sys.stderr)
                    return 1
                label = "Realized profit" if item["status"] == "sold" else "Estimated profit"
                print(f"{label} for item #{args.item_id}: {profit:.2f}")
            elif args.command == "report":
                report = profit_report(connection)
                print("Inventory Report")
                print("----------------")
                print(f"Items: {report['items']}")
                print(f"Sold items: {report['sold_items']}")
                print(f"Purchase cost: {report['purchase_cost']:.2f}")
                print(f"Sales revenue: {report['revenue']:.2f}")
                print(f"Shipping costs: {report['shipping']:.2f}")
                print(f"Platform fees: {report['fees']:.2f}")
                print(f"Realized profit: {report['realized_profit']:.2f}")
                print(f"Estimated active profit: {report['estimated_profit']:.2f}")
            elif args.command == "edit":
                values = {
                    key: value.strip() if isinstance(value, str) else value
                    for key, value in vars(args).items()
                    if key in {
                        "title", "platform", "category", "size", "condition",
                        "purchase_price", "listing_price", "status", "listing_url", "notes",
                    }
                    and value is not None
                }
                if not update_item(connection, args.item_id, values):
                    print(f"Item #{args.item_id} was not found.", file=sys.stderr)
                    return 1
                print(f"Updated item #{args.item_id}.")
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

