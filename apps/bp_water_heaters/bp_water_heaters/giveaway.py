from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any


GIVEAWAY_CAMPAIGN_NAME = "2026 Free Install Sweepstakes"
GIVEAWAY_PRIZE_ARV = 3000
GIVEAWAY_FREE_ENTRY = "Free Online Entry"
GIVEAWAY_FREE_BONUS_ENTRY = "Free Bonus Entry"
GIVEAWAY_PAID_ENTRY = "Paid Flush"
GIVEAWAY_STANDARD_KIND = "Standard"
GIVEAWAY_BONUS_KIND = "Bonus"
GIVEAWAY_ELIGIBLE_STATUS = "Eligible"
GIVEAWAY_DUPLICATE_STATUS = "Duplicate"
GIVEAWAY_WINNER_STATUS = "Winner"

CSV_FIELDS = [
	"name",
	"full_name",
	"email",
	"phone",
	"property_address",
	"city",
	"state",
	"postal_code",
	"entry_source",
	"entry_kind",
	"status",
]

STREET_SUFFIXES = {
	"st": "street",
	"ave": "avenue",
	"av": "avenue",
	"rd": "road",
	"dr": "drive",
	"ln": "lane",
	"blvd": "boulevard",
	"ct": "court",
	"pl": "place",
	"cir": "circle",
	"pkwy": "parkway",
}


def campaign_status(now: datetime, start_at: datetime | None, end_at: datetime | None) -> dict[str, Any]:
	if not start_at or not end_at:
		return {"state": "not_configured", "is_open": False, "start_at": start_at, "end_at": end_at}
	if now < start_at:
		return {"state": "scheduled", "is_open": False, "start_at": start_at, "end_at": end_at}
	if now > end_at:
		return {"state": "closed", "is_open": False, "start_at": start_at, "end_at": end_at}
	return {"state": "open", "is_open": True, "start_at": start_at, "end_at": end_at}


def normalize_household_key(property_address: str, city: str, state: str, postal_code: str) -> str:
	address = _normalize_address_part(property_address)
	normalized_city = _normalize_address_part(city)
	normalized_state = _normalize_address_part(state)
	zip5 = re.sub(r"\D", "", postal_code or "")[:5]
	return "|".join([address, normalized_city, normalized_state, zip5])


def next_free_entry_award(existing_entry_kinds: list[str]) -> dict[str, str]:
	normalized_kinds = {str(kind or "").strip() for kind in existing_entry_kinds}
	if GIVEAWAY_STANDARD_KIND not in normalized_kinds:
		return {"entry_source": GIVEAWAY_FREE_ENTRY, "entry_kind": GIVEAWAY_STANDARD_KIND}
	if GIVEAWAY_BONUS_KIND not in normalized_kinds:
		return {"entry_source": GIVEAWAY_FREE_BONUS_ENTRY, "entry_kind": GIVEAWAY_BONUS_KIND}
	raise ValueError("This household already has the maximum giveaway entries.")


def eligible_entries_to_csv(rows: list[dict[str, Any]]) -> str:
	output = io.StringIO()
	writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
	writer.writeheader()
	for row in rows:
		writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
	return output.getvalue()


def _normalize_address_part(value: str) -> str:
	words = re.sub(r"[^a-z0-9\s]", " ", (value or "").lower()).split()
	expanded = [STREET_SUFFIXES.get(word, word) for word in words]
	return "-".join(expanded)
