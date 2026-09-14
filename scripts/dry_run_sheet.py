#!/usr/bin/env python3
"""Dry-run: fetch the real Google Sheet and show what WOULD be emailed,
without sending anything or writing to database/guests.csv."""
import os
import sys

here = os.path.abspath(os.path.dirname(__file__))
repo_root = os.path.abspath(os.path.join(here, ".."))
if repo_root not in sys.path:
	sys.path.insert(0, repo_root)


def _load_dotenv():
	dotenv_path = os.path.join(repo_root, ".env")
	if not os.path.isfile(dotenv_path):
		return
	with open(dotenv_path, "r", encoding="utf-8") as handle:
		for raw_line in handle:
			line = raw_line.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			key, value = line.split("=", 1)
			key = key.strip()
			if not key or key in os.environ:
				continue
			value = value.strip().strip('"').strip("'")
			os.environ[key] = value


_load_dotenv()

from src.core import load_bookings, guests_csv_path, load_guests, unsent_bookings, check_config  # noqa: E402


def main():
	source = check_config("BOOKINGS_URL=")
	print("Source:", source)
	bookings, errors = load_bookings(source)
	print("Total booking rows parsed:", len(bookings))
	for b in bookings:
		print(" -", b)
	print("Parse errors:", errors)

	guests_path = guests_csv_path()
	existing = load_guests(guests_path)
	print("Existing guests already in database/guests.csv:", len(existing))
	pending = unsent_bookings(bookings, existing)
	print("Pending (would be emailed) count:", len(pending))
	for p in pending:
		print(" PENDING ->", p["buyer_email"], p["full_name"])


if __name__ == "__main__":
	main()
