from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .db import connect
from .repository import add_item, list_items, update_status


DEFAULT_DATABASE = Path("inventory.db")
STATUSES = ("draft", "listed", "sold", "reserved", "archived")


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
    with connect(args.database) as connection:
        if args.command == "add":
            values = {
                key: value
                for key, value in vars(args).items()
                if key in {
                    "title", "platform", "category", "size", "condition",
                    "purchase_price", "listing_price", "status", "listing_url", "notes",
                }
                and value is not None
            }
            item_id = add_item(connection, values)
            print(f"Added item #{item_id}: {args.title}")
        elif args.command == "list":
            items = list_items(connection, args.status)
            if args.csv:
                with args.csv.open("w", newline="", encoding="utf-8") as output:
                    writer = csv.DictWriter(output, fieldnames=items[0].keys() if items else [])
                    if items:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

