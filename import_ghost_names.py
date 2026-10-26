"""Import ghost names from a CSV with "Ghost name" and "Description" columns.

Usage: python import_ghost_names.py <csv_path> [limit]
"""

import csv
import sys

from google.cloud import ndb

import models


def main(csv_path, limit=None):
    """Imports ghost names from a CSV, skipping names that already exist.

    Args:
        csv_path: Path to the CSV file.
        limit: Maximum number of rows to import, or None for all rows.
    """
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))[:limit]

    with ndb.Client().context():
        for row in rows:
            name = row["Ghost name"].strip()
            description = row["Description"].strip() or None
            models.GhostName.get_or_insert(
                name.lower(), name=name, description=description
            )
            print(f"Imported {name}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
