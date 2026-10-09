# Inventory Tracker

A local Python CLI for tracking items sold through Vinted or other resale platforms.
It stores data in SQLite and does not require account credentials or unofficial scraping.

## Quick start

```bash
python3 -m inventory_tracker.cli add "Blue denim jacket" \
  --category jacket --size M --condition "Very good" \
  --purchase-price 12 --listing-price 35

python3 -m inventory_tracker.cli list
python3 -m inventory_tracker.cli status 1 listed
python3 -m inventory_tracker.cli list --csv inventory.csv
```

Use `--database path/to/inventory.db` to keep separate inventories.

## Desktop UI

Run the graphical interface with:

```bash
python3 -m inventory_tracker.ui
```

The window lets you add items, view and filter inventory, and update item status.

## Next steps

The storage layer is intentionally platform-neutral. A future integration can sync listings
through an official platform API or an export file, while keeping local inventory as the source
of truth.

